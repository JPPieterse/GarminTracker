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

logger = structlog.get_logger()

# ── Schema description for the LLM ──────────────────────────────────────────

DB_SCHEMA = """
Tables (PostgreSQL with JSONB):
- daily_stats: id (UUID), user_id (UUID), date (DATE), data (JSONB)
  JSONB fields: totalSteps, totalDistanceMeters, activeKilocalories, restingHeartRate,
  maxHeartRate, averageStressLevel, bodyBatteryHighestValue, bodyBatteryLowestValue, etc.

- activities: id (BIGINT, Garmin activity ID), user_id (UUID), date (DATE),
  activity_type (VARCHAR), data (JSONB)
  JSONB fields: activityName, distance, duration, averageHR, maxHR, calories, etc.

- sleep_records: id (UUID), user_id (UUID), date (DATE), data (JSONB)
  JSONB fields: dailySleepDTO.sleepTimeSeconds, dailySleepDTO.deepSleepSeconds, etc.

- heart_rate_records: id (UUID), user_id (UUID), date (DATE), data (JSONB)

Important: Use PostgreSQL JSONB syntax:
  data->>'fieldName' for text,
  (data->>'fieldName')::numeric for numbers,
  data->'nested'->'field' for nested access.
Every query MUST include WHERE user_id = :user_id
"""

SYSTEM_PROMPT = f"""You are a health data analyst. Convert natural language questions into
PostgreSQL SQL queries against a Garmin health database.

{DB_SCHEMA}

Rules:
1. Always include WHERE user_id = :user_id
2. Use PostgreSQL JSONB operators (->>, ::numeric)
3. Return ONLY the SQL query, no explanation
4. Use date ranges when the user mentions time periods
5. Never modify or delete data — SELECT only
"""


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
    # Block dangerous PostgreSQL functions
    dangerous_funcs = ["pg_read_file", "pg_write_file", "pg_ls_dir", "lo_import", "lo_export"]
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
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    text_content = response.content[0].text
    return text_content, "claude-sonnet-4-20250514"


async def _ask_ollama(question: str, history: list[dict], model: str = "llama3") -> tuple[str, str]:
    """Call local Ollama API."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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


async def _stream_anthropic(question: str, history: list[dict]) -> AsyncGenerator[str, None]:
    """Stream response from Anthropic Claude API."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    messages = [*history, {"role": "user", "content": question}]
    async with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
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


async def ask(
    db: AsyncSession,
    user_id: uuid.UUID,
    question: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Convert a natural-language question to SQL, execute it, and return results."""
    history = await _get_recent_history(db, user_id)
    await _save_message(db, user_id, ChatRole.USER, question)

    # Pick backend
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

    # Execute
    result = await db.execute(text(sql), {"user_id": user_id})
    rows = [dict(row._mapping) for row in result.fetchall()]

    # Stringify UUIDs / dates for JSON
    for row in rows:
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
            elif isinstance(v, uuid.UUID):
                row[k] = str(v)

    # Save assistant response
    summary = f"Found {len(rows)} result(s)"
    await _save_message(db, user_id, ChatRole.ASSISTANT, summary, sql_query=sql, model_used=model_used)

    return {"sql": sql, "results": rows, "model": model_used, "count": len(rows)}


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
