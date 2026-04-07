"""Text-to-SQL analyzer with Ollama and Anthropic backends, chat history."""

from __future__ import annotations

import re
import uuid
from typing import Any, AsyncGenerator

import anthropic
import httpx
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chat import ChatMessage, ChatRole
from app.models.user import UserProfile
from app.services.knowledge import get_relevant_knowledge

logger = structlog.get_logger()

# ── Schema description for the LLM ──────────────────────────────────────────

DB_SCHEMA = """
Tables (SQLite with JSON columns):
- daily_stats: id (UUID), user_id (UUID), date (DATE), data (JSON)
  JSON fields in data: totalSteps (int), totalDistanceMeters (float), totalKilocalories (float),
  activeKilocalories (float), restingHeartRate (int), maxHeartRate (int),
  averageStressLevel (int), bodyBatteryHighestValue (int), bodyBatteryLowestValue (int),
  bodyBatteryMostRecentValue (int), averageSpo2 (float), dailyStepGoal (int),
  floorsAscended (int), moderateIntensityMinutes (int), vigorousIntensityMinutes (int)

- activities: id (BIGINT), user_id (UUID), date (DATE), activity_type (VARCHAR), data (JSON)
  JSON fields in data: activityName (str), distance (float, meters), duration (float, seconds),
  movingDuration (float, seconds), averageHR (float), maxHR (float), calories (float)
  Common activity_type values: running, cycling, strength_training, walking, meditation, hiking

- sleep_records: id (UUID), user_id (UUID), date (DATE), data (JSON)
  JSON fields in data: sleepTimeSeconds (int), deepSleepSeconds (int), lightSleepSeconds (int),
  remSleepSeconds (int), awakeSleepSeconds (int), avgHeartRate (float), averageSpO2Value (float),
  avgSleepStress (float), averageRespirationValue (float)

- heart_rate_records: id (UUID), user_id (UUID), date (DATE), data (JSON)
  JSON fields in data: restingHeartRate (int), maxHeartRate (int), minHeartRate (int)

IMPORTANT — Use SQLite json_extract() syntax:
  json_extract(data, '$.fieldName') to get a value
  CAST(json_extract(data, '$.fieldName') AS REAL) for numeric comparisons/aggregations
Every query MUST include WHERE user_id = :user_id
"""

def _sql_system_prompt() -> str:
    from datetime import date
    today = date.today().isoformat()
    return f"""You are a health data analyst. Convert natural language questions into
SQLite SQL queries against a Garmin health database.

Today's date is {today}.

{DB_SCHEMA}

Rules:
1. Always include WHERE user_id = :user_id
2. Use SQLite json_extract(data, '$.fieldName') to access JSON fields
3. Return ONLY the SQL query, no explanation
4. Use date ranges when the user mentions time periods (dates are ISO format: YYYY-MM-DD)
5. When user says "last month" or "March", use the most recent occurrence relative to today
6. Never modify or delete data — SELECT only
7. For time calculations: sleep/duration values are in seconds, divide by 3600.0 for hours
"""

SUMMARY_SYSTEM_PROMPT = """You are a friendly health data assistant. Given a user's question and
the raw data results from their Garmin health database, provide a clear, conversational answer.

Rules:
1. Be concise but informative — 2-4 sentences max
2. Include the actual numbers from the data
3. Add brief context or encouragement when appropriate (e.g. "That's above average!")
4. Convert raw units: meters to km, seconds to hours/minutes, etc.
5. If the data is empty or null, say you don't have data for that period
6. Never mention SQL, databases, or technical details — just answer naturally
7. If you have the user's profile context, relate your answer to their goals and training
"""


async def _get_user_profile(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Load the user's free-form profile context for the AI."""
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if profile is None or not profile.context.strip():
        return ""

    return f"\n\nUser Profile & Context:\n{profile.context}"


def _extract_sql(raw: str) -> str:
    """Extract SQL from a response that may include markdown code fences."""
    match = re.search(r"```sql\s*(.*?)\s*```", raw, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)\s*```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw.strip()


def _validate_sql(sql: str) -> str:
    """Basic safety checks on generated SQL."""
    upper = sql.upper()
    forbidden = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE",
        "GRANT", "REVOKE", "COPY", "EXECUTE", "PERFORM", "CALL",
    ]
    dangerous_funcs = [
        "pg_read_file", "pg_write_file", "pg_ls_dir", "lo_import", "lo_export",
        "load_extension", "fts3_tokenizer",
    ]
    lower_sql = sql.lower()
    for func in dangerous_funcs:
        if func in lower_sql:
            raise ValueError(f"Forbidden SQL function: {func}")
    for kw in forbidden:
        if re.search(rf"\b{kw}\b", upper):
            raise ValueError(f"Forbidden SQL keyword: {kw}")
    if ":user_id" not in sql and "user_id" not in sql.lower():
        raise ValueError("Query must filter by user_id")
    return sql


# ── Chat history helpers ─────────────────────────────────────────────────────

async def _get_recent_history(db: AsyncSession, user_id: uuid.UUID, limit: int = 10) -> list[dict]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = list(reversed(result.scalars().all()))
    return [{"role": m.role.value.lower(), "content": m.content} for m in messages]


async def _save_message(
    db: AsyncSession,
    user_id: uuid.UUID,
    role: ChatRole,
    content: str,
    sql_query: str | None = None,
    model_used: str | None = None,
) -> ChatMessage:
    msg = ChatMessage(
        user_id=user_id,
        role=role,
        content=content,
        sql_query=sql_query,
        model_used=model_used,
    )
    db.add(msg)
    await db.flush()
    return msg


# ── LLM backends ─────────────────────────────────────────────────────────────

async def _ask_anthropic(question: str, history: list[dict]) -> tuple[str, str]:
    """Call Anthropic Claude API."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    messages = [*history, {"role": "user", "content": question}]
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=_sql_system_prompt(),
        messages=messages,
    )
    text_content = response.content[0].text
    return text_content, "claude-sonnet-4-20250514"


async def _ask_ollama(question: str, history: list[dict], model: str = "llama3") -> tuple[str, str]:
    """Call local Ollama API."""
    messages = [
        {"role": "system", "content": _sql_system_prompt()},
        *history,
        {"role": "user", "content": question},
    ]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
    return data["message"]["content"], model


async def _summarize_results(
    question: str,
    results: list[dict],
    profile_context: str = "",
    coach_prompt: str = "",
) -> str:
    """Use Claude to turn raw SQL results into a natural-language answer."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    import json

    system = SUMMARY_SYSTEM_PROMPT
    if coach_prompt:
        system += f"\n\n{coach_prompt}"

    # Inject relevant domain knowledge for context-aware summaries
    knowledge = get_relevant_knowledge(question)
    if knowledge:
        system += f"\n{knowledge}"

    content = f"User's question: {question}\n\nData results:\n{json.dumps(results, indent=2, default=str)}"
    if profile_context:
        content += f"\n{profile_context}"

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text


async def _stream_anthropic(question: str, history: list[dict]) -> AsyncGenerator[str, None]:
    """Stream response from Anthropic Claude API."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    messages = [*history, {"role": "user", "content": question}]
    async with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=_sql_system_prompt(),
        messages=messages,
    ) as stream:
        async for text_chunk in stream.text_stream:
            yield text_chunk


# ── Public interface ─────────────────────────────────────────────────────────

async def get_available_models() -> list[dict[str, str]]:
    """List available LLM models."""
    models: list[dict[str, str]] = []
    if settings.ANTHROPIC_API_KEY:
        models.append({"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "provider": "anthropic"})
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                for m in resp.json().get("models", []):
                    models.append({"id": m["name"], "name": m["name"], "provider": "ollama"})
    except Exception:
        pass
    return models


ROUTE_SYSTEM_PROMPT = """Classify the user's message into one of two categories:
- DATA: The user is asking a question that requires looking up their health/fitness data (steps, sleep, heart rate, activities, etc.)
- CHAT: The user is sharing information, asking for advice, having a conversation, discussing goals, or anything that does NOT need a database lookup.

Reply with ONLY the word DATA or CHAT. Nothing else."""


async def _route_message(question: str) -> str:
    """Determine if a message needs data lookup or is conversational."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=10,
        system=ROUTE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
    )
    result = response.content[0].text.strip().upper()
    return "DATA" if "DATA" in result else "CHAT"


CHAT_SYSTEM_PROMPT = """You are an AI health and fitness coach on ZEV (Zone Enhanced Vitals).
You're having a natural conversation with the user about their health, fitness, goals, and wellbeing.

## Program Feature

You can create and update the user's training program. The program appears in their "Program" tab
where they follow it during workouts, log weights/reps, and track progress.

When the user asks you to create a program, adjust exercises, change the split, swap exercises,
modify sets/reps, or make any program change, include a [PROGRAM_UPDATE] tag in your response.

Format:
[PROGRAM_UPDATE]
```json
{... complete program JSON ...}
```

The JSON must follow this structure:
{
  "name": "Program Name",
  "coach_note": "A training note for the user — what to focus on this phase, key priorities, weekly reminders, or motivational context. This appears at the top of their Program page. 2-4 sentences.",
  "days": [
    {
      "id": "unique-day-id",
      "name": "Day Name",
      "day_label": "Monday",
      "exercises": [
        {
          "id": "unique-exercise-id",
          "name": "Exercise Name",
          "sets": 4,
          "rep_range": "6-8",
          "description": "Brief description of the movement.",
          "muscles_targeted": ["primary muscle", "secondary"],
          "muscles_warning": "What you should NOT feel",
          "form_cues": "Key form points",
          "youtube_search": "exercise name form"
        }
      ]
    }
  ]
}

IMPORTANT program rules:
- Always include a "coach_note" — this is your voice at the top of their training page. Use it to set
  the tone for this training phase, remind them of priorities, or give context for the program design.
- When updating, output the COMPLETE program (all days, all exercises) — not just the changed parts
- Every exercise needs ALL fields filled in
- Use 4-7 exercises per day
- If the user just wants one exercise swapped, still output the full program with that change made
- Include the [PROGRAM_UPDATE] tag so the system can detect and save the update
- After the JSON block, add a brief conversational summary of what you changed

If the user already has a program and asks about it, reference it naturally. You can see their
current program in the context below (if one exists).

## General Rules

1. Be conversational, warm, and knowledgeable
2. Give practical, actionable advice
3. Reference the user's profile context when relevant
4. If the user shares body composition data, measurements, or test results, acknowledge them,
   explain what they mean, and relate them to the user's goals
5. Keep responses concise — 2-5 sentences unless the topic warrants more detail (program updates can be longer)
6. If the user asks something that would need their actual tracked data (steps, sleep, HR),
   let them know you can look that up if they ask specifically
"""


async def _chat_response(
    question: str,
    history: list[dict],
    profile_context: str = "",
    coach_prompt: str = "",
    program_context: str = "",
) -> str:
    """Generate a conversational response (no SQL)."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    system = CHAT_SYSTEM_PROMPT
    if coach_prompt:
        system += f"\n\n{coach_prompt}"
    if profile_context:
        system += f"\n{profile_context}"
    if program_context:
        system += f"\n{program_context}"

    # Inject relevant domain knowledge
    knowledge = get_relevant_knowledge(question)
    if knowledge:
        system += f"\n{knowledge}"

    # Use higher token limit when program updates might be needed
    needs_program = any(
        kw in question.lower()
        for kw in ["program", "exercise", "swap", "change", "replace", "add", "remove",
                    "workout", "split", "routine", "plan", "build me", "create a", "adjust"]
    )
    max_tokens = 4096 if needs_program else 1024

    messages = [*history, {"role": "user", "content": question}]
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return response.content[0].text


async def _get_program_context(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Load the user's active workout program as context for the coach."""
    from app.models.workout import WorkoutProgram
    import json

    stmt = select(WorkoutProgram).where(
        WorkoutProgram.user_id == user_id, WorkoutProgram.active.is_(True)
    )
    result = await db.execute(stmt)
    program = result.scalar_one_or_none()

    if not program:
        return "\n\n## Current Training Program\nNo program created yet. The user can ask you to create one."

    # Summarize program compactly for context
    days = program.program_data.get("days", [])
    summary_parts = [f"## Current Training Program: {program.name}"]
    for day in days:
        exercises = ", ".join(
            f"{ex['name']} ({ex['sets']}x{ex['rep_range']})"
            for ex in day.get("exercises", [])
        )
        summary_parts.append(f"- **{day['day_label']} — {day['name']}**: {exercises}")

    return "\n\n" + "\n".join(summary_parts)


async def _handle_program_update(db: AsyncSession, user_id: uuid.UUID, answer_text: str, coach_id: str) -> str:
    """Detect [PROGRAM_UPDATE] in the response, extract JSON, save the updated program."""
    import json
    from app.models.workout import WorkoutProgram

    if "[PROGRAM_UPDATE]" not in answer_text:
        return answer_text

    # Extract JSON from the response
    json_match = re.search(r"\[PROGRAM_UPDATE\]\s*```(?:json)?\s*(.*?)\s*```", answer_text, re.DOTALL)
    if not json_match:
        # Try without code fences
        json_match = re.search(r"\[PROGRAM_UPDATE\]\s*(\{.*\})", answer_text, re.DOTALL)

    if not json_match:
        logger.warning("program_update_tag_found_but_no_json")
        return answer_text.replace("[PROGRAM_UPDATE]", "").strip()

    try:
        program_data = json.loads(json_match.group(1))
        program_name = program_data.pop("name", "Training Program")
        coach_note = program_data.pop("coach_note", "")

        # Deactivate existing programs
        existing = await db.execute(
            select(WorkoutProgram).where(
                WorkoutProgram.user_id == user_id, WorkoutProgram.active.is_(True)
            )
        )
        for prog in existing.scalars():
            prog.active = False

        # Create new program
        program = WorkoutProgram(
            user_id=user_id,
            coach_id=coach_id or "aria",
            name=program_name,
            coach_note=coach_note,
            active=True,
            program_data=program_data,
        )
        db.add(program)
        await db.flush()

        logger.info("program_updated_from_chat", user_id=str(user_id), program_name=program_name)

    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("program_update_json_parse_failed", error=str(exc))

    # Clean the response — remove the JSON block, keep the conversational part
    clean = re.sub(
        r"\[PROGRAM_UPDATE\]\s*```(?:json)?\s*.*?\s*```",
        "",
        answer_text,
        flags=re.DOTALL,
    ).strip()
    if not clean:
        clean = re.sub(r"\[PROGRAM_UPDATE\]\s*\{.*\}", "", answer_text, flags=re.DOTALL).strip()

    # Add a note that the program was updated
    if clean:
        clean += "\n\n✅ *Program updated — check your Program tab!*"
    else:
        clean = "I've updated your training program! Check your Program tab to see the changes."

    return clean


async def ask(
    db: AsyncSession,
    user_id: uuid.UUID,
    question: str,
    model: str | None = None,
    coach_id: str | None = None,
) -> dict[str, Any]:
    """Route a message to either data lookup (SQL) or conversational chat."""
    from app.services.coaches import get_coach

    history = await _get_recent_history(db, user_id)
    await _save_message(db, user_id, ChatRole.USER, question)

    # Load user profile, coach persona, and current program
    profile_context = await _get_user_profile(db, user_id)
    program_context = await _get_program_context(db, user_id)
    coach = get_coach(coach_id) if coach_id else None
    coach_prompt = coach["system_addendum"] if coach else ""

    try:
        # Route: does this need a data lookup or is it conversational?
        route = await _route_message(question)
        model_used = "claude-sonnet-4-20250514"

        if route == "CHAT":
            # Pure conversation — no SQL needed
            answer_text = await _chat_response(
                question, history, profile_context, coach_prompt, program_context
            )
            # Check if the coach wants to update the program
            answer_text = await _handle_program_update(db, user_id, answer_text, coach_id or "")
            await _save_message(db, user_id, ChatRole.ASSISTANT, answer_text, model_used=model_used)
            return {"answer": answer_text, "results": [], "model": model_used, "count": 0}

        # DATA route — generate SQL, execute, summarize
        if model and model.startswith("claude"):
            raw_sql, model_used = await _ask_anthropic(question, history)
        elif model:
            raw_sql, model_used = await _ask_ollama(question, history, model=model)
        elif settings.ANTHROPIC_API_KEY:
            raw_sql, model_used = await _ask_anthropic(question, history)
        else:
            raw_sql, model_used = await _ask_ollama(question, history)

        sql = _extract_sql(raw_sql)
        sql = _validate_sql(sql)

        # Execute — SQLite stores UUIDs without dashes
        user_id_str = str(user_id).replace("-", "")
        result = await db.execute(text(sql), {"user_id": user_id_str})
        rows = [dict(row._mapping) for row in result.fetchall()]

        # Stringify UUIDs / dates for JSON
        for row in rows:
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()
                elif isinstance(v, uuid.UUID):
                    row[k] = str(v)

        # Summarize results into natural language
        if rows and settings.ANTHROPIC_API_KEY:
            answer_text = await _summarize_results(question, rows, profile_context, coach_prompt)
        elif rows:
            answer_text = f"Found {len(rows)} result(s): {rows}"
        else:
            answer_text = "I don't have any data matching that query. Try asking about a different time period or metric."

        await _save_message(db, user_id, ChatRole.ASSISTANT, answer_text, sql_query=sql, model_used=model_used)

        return {"answer": answer_text, "sql": sql, "results": rows, "model": model_used, "count": len(rows)}

    except ValueError as exc:
        # If SQL validation fails, fall back to chat mode
        logger.warning("sql_validation_failed_falling_back_to_chat", error=str(exc))
        answer_text = await _chat_response(
            question, history, profile_context, coach_prompt, program_context
        )
        answer_text = await _handle_program_update(db, user_id, answer_text, coach_id or "")
        await _save_message(db, user_id, ChatRole.ASSISTANT, answer_text, model_used="claude-sonnet-4-20250514")
        return {"answer": answer_text, "results": [], "model": "claude-sonnet-4-20250514", "count": 0}

    except Exception as exc:
        logger.error("llm_ask_failed", user_id=str(user_id), error=str(exc))
        error_msg = "Sorry, I couldn't process that question. Please try rephrasing it."
        await _save_message(db, user_id, ChatRole.ASSISTANT, error_msg, model_used=model or "unknown")
        return {"answer": error_msg, "results": [], "model": model or "unknown", "count": 0}


async def ask_stream(
    db: AsyncSession,
    user_id: uuid.UUID,
    question: str,
) -> AsyncGenerator[str, None]:
    """Stream LLM response chunks for SSE endpoint."""
    history = await _get_recent_history(db, user_id)
    await _save_message(db, user_id, ChatRole.USER, question)

    full_response = ""
    async for chunk in _stream_anthropic(question, history):
        full_response += chunk
        yield chunk

    await _save_message(db, user_id, ChatRole.ASSISTANT, full_response, model_used="claude-sonnet-4-20250514")
