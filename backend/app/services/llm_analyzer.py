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

- hrv_records: id (UUID), user_id (UUID), date (DATE), data (JSON)
  JSON fields in data: hrvSummary.lastNightAvg (float), hrvSummary.lastNight5MinHigh (int),
  hrvSummary.status (str: BALANCED/UNBALANCED/LOW), hrvSummary.baseline.lowUpper (int),
  hrvSummary.baseline.balancedLow (int), hrvSummary.baseline.balancedUpper (int)

- training_readiness_records: id (UUID), user_id (UUID), date (DATE), data (JSON)
  JSON fields: data.readiness (training readiness object), data.status (training status object)
  Readiness fields: score (int 0-100), level (str: PRIME/HIGH/MODERATE/LOW)
  Status fields: trainingStatus (str: PRODUCTIVE/PEAKING/RECOVERY/UNPRODUCTIVE/DETRAINING/OVERREACHING)

- body_composition_records: id (UUID), user_id (UUID), date (DATE), data (JSON)
  JSON fields: weight (float, grams), bmi (float), bodyFat (float, percentage),
  muscleMass (float, grams), boneMass (float, grams), bodyWater (float, percentage)

- stress_detail_records: id (UUID), user_id (UUID), date (DATE), data (JSON)
  JSON fields: data.stress_timeline (array of stress values throughout day),
  data.body_battery_events (array of drain/charge events with types and impacts)

- performance_metrics: id (UUID), user_id (UUID), date (DATE), data (JSON)
  JSON fields: data.max_metrics (VO2 max, training load), data.fitness_age (fitness age data),
  data.race_predictions (predicted 5K, 10K, half marathon, marathon times)

- meal_logs: id (UUID), user_id (UUID), date (DATE), time (TIME), meal_type (VARCHAR: BREAKFAST/LUNCH/DINNER/SNACK),
  calories (INT), protein_g (FLOAT), carbs_g (FLOAT), fat_g (FLOAT),
  fiber_g (FLOAT, nullable), sodium_mg (FLOAT, nullable), ingredients (TEXT),
  confidence (VARCHAR: HIGH/MEDIUM/LOW), notes (TEXT, nullable), hydration_ml (INT, nullable)

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


async def _build_recent_snapshot(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_timezone: str | None = None,
) -> str:
    """Build a compact summary of recent health data for the coach's context.

    Pulls up to 14 days of data, starting from the most recent date that has records.
    If the user hasn't synced recently, includes the gap duration.
    """
    from datetime import date as date_type, timedelta
    from app.models.health import DailyStat, SleepRecord, HeartRateRecord, Activity
    from app.models.garmin_extended import (
        HrvRecord, TrainingReadinessRecord, BodyCompositionRecord,
        StressDetailRecord, PerformanceMetric,
    )
    from app.models.meal import MealLog
    from sqlalchemy import func as sqlfunc, union_all

    today = date_type.today()

    # Find the most recent date with any data
    date_queries = union_all(
        select(sqlfunc.max(DailyStat.date)).where(DailyStat.user_id == user_id),
        select(sqlfunc.max(SleepRecord.date)).where(SleepRecord.user_id == user_id),
        select(sqlfunc.max(Activity.date)).where(Activity.user_id == user_id),
    ).subquery()
    result = await db.execute(select(sqlfunc.max(date_queries.c[0])))
    latest_date = result.scalar_one_or_none()

    if not latest_date:
        return "\n\n## Recent Health Data\nNo health data synced yet."

    gap_days = (today - latest_date).days
    lookback_start = latest_date - timedelta(days=13)  # up to 14 days total

    lines = ["\n\n## Recent Health Data"]
    if gap_days > 1:
        lines.append(f"Last data: {latest_date.isoformat()} ({gap_days} days ago)")
    elif gap_days == 1:
        lines.append(f"Last data: yesterday ({latest_date.isoformat()})")
    else:
        lines.append(f"Last sync: {latest_date.isoformat()} (today)")

    # Fetch all data in range
    daily_stmt = select(DailyStat).where(
        DailyStat.user_id == user_id,
        DailyStat.date.between(lookback_start, latest_date),
    ).order_by(DailyStat.date.desc())
    daily_result = await db.execute(daily_stmt)
    daily_by_date = {r.date: r.data for r in daily_result.scalars()}

    sleep_stmt = select(SleepRecord).where(
        SleepRecord.user_id == user_id,
        SleepRecord.date.between(lookback_start, latest_date),
    ).order_by(SleepRecord.date.desc())
    sleep_result = await db.execute(sleep_stmt)
    sleep_by_date = {r.date: r.data for r in sleep_result.scalars()}

    hr_stmt = select(HeartRateRecord).where(
        HeartRateRecord.user_id == user_id,
        HeartRateRecord.date.between(lookback_start, latest_date),
    ).order_by(HeartRateRecord.date.desc())
    hr_result = await db.execute(hr_stmt)
    hr_by_date = {r.date: r.data for r in hr_result.scalars()}

    hrv_stmt = select(HrvRecord).where(
        HrvRecord.user_id == user_id,
        HrvRecord.date.between(lookback_start, latest_date),
    ).order_by(HrvRecord.date.desc())
    hrv_result = await db.execute(hrv_stmt)
    hrv_by_date = {r.date: r.data for r in hrv_result.scalars()}

    readiness_stmt = select(TrainingReadinessRecord).where(
        TrainingReadinessRecord.user_id == user_id,
        TrainingReadinessRecord.date.between(lookback_start, latest_date),
    ).order_by(TrainingReadinessRecord.date.desc())
    readiness_result = await db.execute(readiness_stmt)
    readiness_by_date = {r.date: r.data for r in readiness_result.scalars()}

    activity_stmt = select(Activity).where(
        Activity.user_id == user_id,
        Activity.date.between(lookback_start, latest_date),
    ).order_by(Activity.date.desc())
    activity_result = await db.execute(activity_stmt)
    activities_by_date: dict = {}
    for a in activity_result.scalars():
        activities_by_date.setdefault(a.date, []).append(a)

    meal_stmt = select(MealLog).where(
        MealLog.user_id == user_id,
        MealLog.date.between(lookback_start, latest_date),
    ).order_by(MealLog.date.desc())
    meal_result = await db.execute(meal_stmt)
    meals_by_date: dict = {}
    for m in meal_result.scalars():
        meals_by_date.setdefault(m.date, []).append(m)

    # Build per-day summaries
    all_dates = sorted(
        set(daily_by_date) | set(sleep_by_date) | set(activities_by_date) | set(meals_by_date),
        reverse=True,
    )

    for d in all_dates:
        day_label = d.isoformat()
        if d == today:
            day_label += " (today)"
        elif d == today - timedelta(days=1):
            day_label += " (yesterday)"
        lines.append(f"\n### {day_label}")

        ds = daily_by_date.get(d, {})
        if ds:
            parts = []
            if ds.get("totalSteps"):
                parts.append(f"Steps: {ds['totalSteps']:,}")
            if ds.get("totalKilocalories"):
                parts.append(f"Calories: {ds['totalKilocalories']:,}")
            if ds.get("averageStressLevel"):
                parts.append(f"Stress: {ds['averageStressLevel']}")
            if ds.get("bodyBatteryHighestValue"):
                parts.append(f"Body Battery: {ds['bodyBatteryHighestValue']}")
            if parts:
                lines.append(f"- {' | '.join(parts)}")

        sl = sleep_by_date.get(d, {})
        if sl:
            parts = []
            if sl.get("sleepTimeSeconds"):
                hrs = round(sl["sleepTimeSeconds"] / 3600, 1)
                deep = round(sl.get("deepSleepSeconds", 0) / 3600, 1)
                rem = round(sl.get("remSleepSeconds", 0) / 3600, 1)
                parts.append(f"Sleep: {hrs}h (deep {deep}h, REM {rem}h)")
            if sl.get("avgHeartRate"):
                parts.append(f"Sleep HR: {sl['avgHeartRate']}")
            if parts:
                lines.append(f"- {' | '.join(parts)}")

        hr = hr_by_date.get(d, {})
        hrv = hrv_by_date.get(d, {})
        hr_parts = []
        if hr.get("restingHeartRate"):
            hr_parts.append(f"Resting HR: {hr['restingHeartRate']}")
        hrv_summary = hrv.get("hrvSummary", {}) if hrv else {}
        if hrv_summary.get("lastNightAvg"):
            status = hrv_summary.get("status", "")
            baseline = hrv_summary.get("baseline", {})
            bl_str = ""
            if baseline.get("balancedLow") and baseline.get("balancedUpper"):
                bl_str = f", baseline {baseline['balancedLow']}-{baseline['balancedUpper']}"
            hr_parts.append(f"HRV: {hrv_summary['lastNightAvg']:.0f} ({status}{bl_str})")
        if hr_parts:
            lines.append(f"- {' | '.join(hr_parts)}")

        rd = readiness_by_date.get(d, {})
        rd_parts = []
        if rd.get("readiness", {}).get("score"):
            level = rd["readiness"].get("level", "")
            rd_parts.append(f"Training Readiness: {rd['readiness']['score']} ({level})")
        if rd.get("status", {}).get("trainingStatus"):
            rd_parts.append(f"Status: {rd['status']['trainingStatus']}")
        if rd_parts:
            lines.append(f"- {' | '.join(rd_parts)}")

        acts = activities_by_date.get(d, [])
        if acts:
            act_strs = []
            for a in acts:
                s = a.activity_type.replace("_", " ").title()
                dist = a.data.get("distance")
                dur = a.data.get("duration") or a.data.get("movingDuration")
                avg_hr = a.data.get("averageHR") or a.data.get("avgHR")
                if dist:
                    s += f" {dist/1000:.1f}km"
                if dur:
                    s += f" ({dur/60:.0f}min"
                    if avg_hr:
                        s += f", avg HR {avg_hr:.0f}"
                    s += ")"
                act_strs.append(s)
            lines.append(f"- Activities: {', '.join(act_strs)}")

        day_meals = meals_by_date.get(d, [])
        if day_meals:
            meal_strs = []
            total_cal = 0
            total_protein = 0.0
            for m in day_meals:
                meal_strs.append(f"{m.meal_type.value.title()} {m.calories}cal ({m.protein_g:.0f}g P)")
                total_cal += m.calories
                total_protein += m.protein_g
            lines.append(f"- Meals: {', '.join(meal_strs)} — total: {total_cal}cal, {total_protein:.0f}g protein")

    return "\n".join(lines)


def _build_timezone_context(user_timezone: str | None) -> str:
    """Build a timezone context string for the coach prompt."""
    if not user_timezone:
        return ""
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime, timezone as tz
        now_utc = datetime.now(tz.utc)
        user_now = now_utc.astimezone(ZoneInfo(user_timezone))
        time_str = user_now.strftime("%H:%M %Z")
        date_str = user_now.strftime("%Y-%m-%d")
        return f"\n\nThe user's current local time is {time_str} ({user_timezone}). Today's date in their timezone is {date_str}."
    except Exception:
        return ""


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
    coach_id: str | None = None,
) -> ChatMessage:
    msg = ChatMessage(
        user_id=user_id,
        role=role,
        content=content,
        sql_query=sql_query,
        model_used=model_used,
        coach_id=coach_id,
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
    snapshot: str = "",
) -> str:
    """Use Claude to turn raw SQL results into a natural-language answer."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    import json

    system = SUMMARY_SYSTEM_PROMPT
    if coach_prompt:
        system += f"\n\n{coach_prompt}"

    if snapshot:
        system += snapshot

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

ONLY create or modify the program when the user EXPLICITLY asks you to. Examples of explicit requests:
"Create me a program", "Change my Monday exercises", "Swap squats for leg press", "Update my plan".

Do NOT proactively suggest or create program changes during general conversation. Discussing training
ideas, goals, or preferences is just conversation — it does not mean "update my program". Wait for
the user to clearly ask for a change before including the [PROGRAM_UPDATE] tag.

When the user does explicitly ask for a program change, include a [PROGRAM_UPDATE] tag in your response.

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
6. You always have access to the user's recent health data (shown below). Reference it
   naturally in conversation — don't wait for them to ask. For historical queries beyond
   what's shown, the system will automatically look up the data.
"""


async def _chat_response(
    question: str,
    history: list[dict],
    profile_context: str = "",
    coach_prompt: str = "",
    program_context: str = "",
    snapshot: str = "",
    timezone_ctx: str = "",
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
    if timezone_ctx:
        system += timezone_ctx

    if snapshot:
        system += snapshot

    # Inject relevant domain knowledge
    knowledge = get_relevant_knowledge(question)
    if knowledge:
        system += f"\n{knowledge}"

    # Use higher token limit when program updates might be needed.
    # Check both the current question AND recent history — user might say "yes"
    # in response to "Ready for me to create that program?"
    combined_text = question.lower()
    for h in history[-3:]:
        combined_text += " " + h.get("content", "").lower()
    needs_program = any(
        kw in combined_text
        for kw in ["program", "exercise", "swap", "change", "replace", "add", "remove",
                    "workout", "split", "routine", "plan", "build me", "create a", "adjust",
                    "create", "lock in", "map out", "design", "ready"]
    )
    max_tokens = 8192 if needs_program else 1024

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

    # Detect program data — either via explicit tag or via a JSON block with program structure
    has_tag = "[PROGRAM_UPDATE]" in answer_text
    has_program_json = not has_tag and '```json' in answer_text and '"days"' in answer_text and '"exercises"' in answer_text

    if not has_tag and not has_program_json:
        return answer_text

    # If no tag but looks like program JSON, treat it as tagged
    if has_program_json and not has_tag:
        answer_text = answer_text.replace('```json', '[PROGRAM_UPDATE]\n```json', 1)

    # Extract JSON from the response
    json_match = re.search(r"\[PROGRAM_UPDATE\]\s*```(?:json)?\s*(.*?)\s*```", answer_text, re.DOTALL)
    if not json_match:
        # Try without code fences
        json_match = re.search(r"\[PROGRAM_UPDATE\]\s*(\{.*\})", answer_text, re.DOTALL)

    if not json_match:
        logger.warning("program_update_tag_found_but_no_json")
        # Fall through to cleanup code below to strip the JSON block
    else:
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

    # Clean the response — remove the tag and any JSON block (fenced or bare)
    # First try: complete fenced code block with closing ```
    clean = re.sub(
        r"\[PROGRAM_UPDATE\]\s*```(?:json)?\s*.*?```",
        "",
        answer_text,
        flags=re.DOTALL,
    ).strip()
    # If tag still present, the JSON block may be truncated (no closing ```)
    if "[PROGRAM_UPDATE]" in clean:
        clean = re.sub(r"\[PROGRAM_UPDATE\]\s*```(?:json)?\s*.*", "", clean, flags=re.DOTALL).strip()
    # If tag still present, remove tag + bare JSON object
    if "[PROGRAM_UPDATE]" in clean:
        clean = re.sub(r"\[PROGRAM_UPDATE\]\s*\{.*", "", clean, flags=re.DOTALL).strip()
    # Catch any orphaned JSON blocks (LLM omitted tag, complete or truncated)
    if "```json" in clean:
        clean = re.sub(r"```json\s*\{.*?(```|$)", "", clean, flags=re.DOTALL).strip()
    # Remove any remaining [PROGRAM_UPDATE] tags
    clean = clean.replace("[PROGRAM_UPDATE]", "").strip()

    # Add a note that the program was updated
    if clean:
        clean += "\n\n✅ *Program updated — check your Program tab!*"
    else:
        clean = "I've updated your training program! Check your Program tab to see the changes."

    return clean


async def _handle_meal_log(
    db: AsyncSession,
    user_id: uuid.UUID,
    answer_text: str,
    user_timezone: str | None = None,
) -> str:
    """Detect [MEAL_LOG] in the response, extract JSON, save MealLog record."""
    import json
    from datetime import datetime, timezone as tz
    from app.models.meal import MealLog, MealType, MealConfidence

    if "[MEAL_LOG]" not in answer_text:
        return answer_text

    # Extract JSON — try with code fences first, then bare JSON
    json_match = re.search(r"\[MEAL_LOG\]\s*```(?:json)?\s*(.*?)\s*```", answer_text, re.DOTALL)
    if not json_match:
        json_match = re.search(r"\[MEAL_LOG\]\s*(\{.*?\})", answer_text, re.DOTALL)

    if not json_match:
        logger.warning("meal_log_tag_found_but_no_json")
        return answer_text.replace("[MEAL_LOG]", "").strip()

    try:
        data = json.loads(json_match.group(1))

        # Determine local time
        now_utc = datetime.now(tz.utc)
        if user_timezone:
            try:
                from zoneinfo import ZoneInfo
                local_now = now_utc.astimezone(ZoneInfo(user_timezone))
            except Exception:
                local_now = now_utc
        else:
            local_now = now_utc

        local_date = local_now.date()
        local_time = local_now.time().replace(microsecond=0)

        # Auto-infer meal type from local hour
        hour = local_now.hour
        if hour < 10:
            meal_type = MealType.BREAKFAST
        elif hour < 14:
            meal_type = MealType.LUNCH
        elif hour < 17:
            meal_type = MealType.SNACK
        else:
            meal_type = MealType.DINNER

        confidence_str = data.get("confidence", "MEDIUM").upper()
        try:
            confidence = MealConfidence(confidence_str)
        except ValueError:
            confidence = MealConfidence.MEDIUM

        meal = MealLog(
            user_id=user_id,
            date=local_date,
            time=local_time,
            meal_type=meal_type,
            calories=int(data.get("calories", 0)),
            protein_g=float(data.get("protein_g", 0)),
            carbs_g=float(data.get("carbs_g", 0)),
            fat_g=float(data.get("fat_g", 0)),
            fiber_g=float(data["fiber_g"]) if data.get("fiber_g") is not None else None,
            sodium_mg=float(data["sodium_mg"]) if data.get("sodium_mg") is not None else None,
            ingredients=data.get("ingredients", ""),
            confidence=confidence,
            notes=data.get("notes"),
            hydration_ml=int(data["hydration_ml"]) if data.get("hydration_ml") is not None else None,
        )
        db.add(meal)
        await db.flush()

        logger.info("meal_logged", user_id=str(user_id), calories=meal.calories)

    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.error("meal_log_json_parse_failed", error=str(exc))

    # Clean the tag from response
    clean = re.sub(
        r"\[MEAL_LOG\]\s*```(?:json)?\s*.*?\s*```",
        "",
        answer_text,
        flags=re.DOTALL,
    ).strip()
    if not clean:
        clean = re.sub(r"\[MEAL_LOG\]\s*\{.*?\}", "", answer_text, flags=re.DOTALL).strip()

    return clean or "I've logged that meal for you!"


async def _build_today_meal_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_timezone: str | None = None,
) -> str:
    """Build a summary of today's meals for context in meal analysis."""
    from datetime import datetime, timezone as tz
    from app.models.meal import MealLog

    now_utc = datetime.now(tz.utc)
    if user_timezone:
        try:
            from zoneinfo import ZoneInfo
            local_now = now_utc.astimezone(ZoneInfo(user_timezone))
        except Exception:
            local_now = now_utc
    else:
        local_now = now_utc

    today = local_now.date()

    stmt = select(MealLog).where(
        MealLog.user_id == user_id,
        MealLog.date == today,
    ).order_by(MealLog.time)
    result = await db.execute(stmt)
    meals = list(result.scalars())

    if not meals:
        return "\n\nNo meals logged today yet."

    total_cal = sum(m.calories for m in meals)
    total_protein = sum(m.protein_g for m in meals)
    total_carbs = sum(m.carbs_g for m in meals)
    total_fat = sum(m.fat_g for m in meals)

    parts = [f"\n\n## Today's Meals So Far ({total_cal} cal, {total_protein:.0f}g P, {total_carbs:.0f}g C, {total_fat:.0f}g F)"]
    for m in meals:
        parts.append(f"- {m.meal_type.value.title()} ({m.time.strftime('%H:%M')}): {m.calories}cal — {m.ingredients}")

    return "\n".join(parts)


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

    # Load user timezone
    tz_stmt = select(UserProfile.timezone).where(UserProfile.user_id == user_id)
    tz_result = await db.execute(tz_stmt)
    user_timezone = tz_result.scalar_one_or_none()

    # Build always-on health snapshot
    snapshot = await _build_recent_snapshot(db, user_id, user_timezone)
    timezone_ctx = _build_timezone_context(user_timezone)

    try:
        # Route: does this need a data lookup or is it conversational?
        route = await _route_message(question)
        model_used = "claude-sonnet-4-20250514"

        if route == "CHAT":
            # Pure conversation — no SQL needed
            answer_text = await _chat_response(
                question, history, profile_context, coach_prompt, program_context,
                snapshot=snapshot, timezone_ctx=timezone_ctx
            )
            # Check if the coach wants to update the program
            answer_text = await _handle_program_update(db, user_id, answer_text, coach_id or "")
            await _save_message(db, user_id, ChatRole.ASSISTANT, answer_text, model_used=model_used, coach_id=coach_id)
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
            answer_text = await _summarize_results(question, rows, profile_context, coach_prompt, snapshot=snapshot)
        elif rows:
            answer_text = f"Found {len(rows)} result(s): {rows}"
        else:
            answer_text = "I don't have any data matching that query. Try asking about a different time period or metric."

        await _save_message(db, user_id, ChatRole.ASSISTANT, answer_text, sql_query=sql, model_used=model_used, coach_id=coach_id)

        return {"answer": answer_text, "sql": sql, "results": rows, "model": model_used, "count": len(rows)}

    except ValueError as exc:
        # If SQL validation fails, fall back to chat mode
        logger.warning("sql_validation_failed_falling_back_to_chat", error=str(exc))
        answer_text = await _chat_response(
            question, history, profile_context, coach_prompt, program_context,
            snapshot=snapshot, timezone_ctx=timezone_ctx
        )
        answer_text = await _handle_program_update(db, user_id, answer_text, coach_id or "")
        await _save_message(db, user_id, ChatRole.ASSISTANT, answer_text, model_used="claude-sonnet-4-20250514", coach_id=coach_id)
        return {"answer": answer_text, "results": [], "model": "claude-sonnet-4-20250514", "count": 0}

    except Exception as exc:
        logger.error("llm_ask_failed", user_id=str(user_id), error=str(exc))
        error_msg = "Sorry, I couldn't process that question. Please try rephrasing it."
        await _save_message(db, user_id, ChatRole.ASSISTANT, error_msg, model_used=model or "unknown", coach_id=coach_id)
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


MEAL_ANALYSIS_SYSTEM_PROMPT = """You are analyzing a photo of a meal to estimate its nutritional content.
You are also an AI health coach having a natural conversation.

## Estimation Approach
- Give your best practical estimate based on what you can see
- You are providing coaching guidance for everyday wellness, NOT clinical measurements
- If a meal is complex or portions are hard to judge, say so honestly and give a range
- This is not competition prep or medical dietary management — frame estimates as approximations
- When genuinely uncertain about an ingredient or portion, ask a clarifying question

## Response Format
1. First, respond conversationally as the coach — comment on the meal, relate it to the user's goals
2. Include a [MEAL_LOG] tag with structured JSON:

[MEAL_LOG]
```json
{"calories": 650, "protein_g": 42, "carbs_g": 55, "fat_g": 22, "fiber_g": 8, "sodium_mg": 480, "ingredients": "item1 ~portion, item2 ~portion", "confidence": "HIGH"}
```

3. After the tag, continue conversationally — add context about daily totals, suggestions, etc.

Confidence levels:
- HIGH: Clear photo, identifiable ingredients, standard portions
- MEDIUM: Some ambiguity in portions or preparation — mention this
- LOW: Blurry photo, complex mixed dish, genuinely uncertain — give rough range and ask questions
"""


async def analyze_meal(
    db: AsyncSession,
    user_id: uuid.UUID,
    image_base64: str,
    media_type: str,
    message: str = "",
    coach_id: str | None = None,
) -> dict[str, Any]:
    """Analyze a meal photo using Claude vision and log nutrition data."""
    from app.services.coaches import get_coach
    from app.models.user import UserProfile

    history = await _get_recent_history(db, user_id)
    user_content = message or "Here's a photo of my meal."
    await _save_message(db, user_id, ChatRole.USER, f"Sent a photo{': ' + message if message else ''}")

    # Load context
    profile_context = await _get_user_profile(db, user_id)

    tz_stmt = select(UserProfile.timezone).where(UserProfile.user_id == user_id)
    tz_result = await db.execute(tz_stmt)
    user_timezone = tz_result.scalar_one_or_none()

    snapshot = await _build_recent_snapshot(db, user_id, user_timezone)
    timezone_ctx = _build_timezone_context(user_timezone)
    meal_summary = await _build_today_meal_summary(db, user_id, user_timezone)

    coach = get_coach(coach_id) if coach_id else None
    coach_prompt = coach["system_addendum"] if coach else ""

    # Build system prompt
    system = MEAL_ANALYSIS_SYSTEM_PROMPT
    if coach_prompt:
        system += f"\n\n{coach_prompt}"
    if profile_context:
        system += f"\n{profile_context}"
    if timezone_ctx:
        system += timezone_ctx
    if snapshot:
        system += snapshot
    if meal_summary:
        system += meal_summary

    # Inject knowledge
    knowledge = get_relevant_knowledge("meal food photo calories macros nutrition")
    if knowledge:
        system += f"\n{knowledge}"

    # Build message with image
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    messages = [
        *history,
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_base64,
                    },
                },
                {
                    "type": "text",
                    "text": user_content,
                },
            ],
        },
    ]

    model_used = "claude-sonnet-4-20250514"
    response = await client.messages.create(
        model=model_used,
        max_tokens=1024,
        system=system,
        messages=messages,
    )

    answer_text = response.content[0].text

    # Extract and save meal log
    answer_text = await _handle_meal_log(db, user_id, answer_text, user_timezone)

    await _save_message(db, user_id, ChatRole.ASSISTANT, answer_text, model_used=model_used, coach_id=coach_id)

    return {"answer": answer_text, "results": [], "model": model_used, "count": 0}
