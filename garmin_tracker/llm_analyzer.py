"""LLM-powered analysis of Garmin health data.

Supports two backends:
- Ollama (local models, no API key needed)
- Anthropic API (cloud, requires ANTHROPIC_API_KEY)

Two-step approach:
1. LLM generates a SQL query from the user's natural language question
2. Query runs against the database (read-only)
3. LLM summarizes the results in plain English with insights
"""

import json
import logging
import os
import sqlite3
from datetime import date

import httpx

from . import database as db

logger = logging.getLogger(__name__)

# --- Model Registry ---

MODELS = {
    # Local models (Ollama)
    "phi4-mini": {"name": "Phi-4 Mini (3.8B)", "backend": "ollama", "model_id": "phi4-mini", "size": "~2.5 GB"},
    "qwen2.5-coder:1.5b": {"name": "Qwen 2.5 Coder 1.5B", "backend": "ollama", "model_id": "qwen2.5-coder:1.5b", "size": "~1 GB"},
    "qwen2.5-coder:7b": {"name": "Qwen 2.5 Coder 7B", "backend": "ollama", "model_id": "qwen2.5-coder:7b", "size": "~4.5 GB"},
    "gemma2:2b": {"name": "Gemma 2 2B", "backend": "ollama", "model_id": "gemma2:2b", "size": "~1.5 GB"},
    "llama3.2:3b": {"name": "Llama 3.2 3B", "backend": "ollama", "model_id": "llama3.2:3b", "size": "~2 GB"},
    # Cloud models (Anthropic)
    "haiku": {"name": "Claude Haiku 4.5 (API)", "backend": "anthropic", "model_id": "claude-haiku-4-5-20251001", "size": "cloud"},
    "sonnet": {"name": "Claude Sonnet 4.6 (API)", "backend": "anthropic", "model_id": "claude-sonnet-4-6-20250514", "size": "cloud"},
}

DEFAULT_MODEL = "phi4-mini"
OLLAMA_BASE = "http://localhost:11434"

SCHEMA_DESCRIPTION = """
You have access to a SQLite database with these tables:

CREATE TABLE daily_stats (
    date TEXT PRIMARY KEY,          -- 'YYYY-MM-DD'
    data JSON NOT NULL              -- Full Garmin daily summary. Key fields inside JSON:
                                    --   totalSteps, totalDistanceMeters, totalKilocalories,
                                    --   activeKilocalories, activeSeconds, sedentarySeconds,
                                    --   floorsAscended, averageStressLevel, maxStressLevel,
                                    --   stepsGoal, moderateIntensityMinutes,
                                    --   vigorousIntensityMinutes,
                                    --   bodyBatteryHighestValue, bodyBatteryLowestValue,
                                    --   averageSpO2, lowestSpO2
);

CREATE TABLE activities (
    id INTEGER PRIMARY KEY,         -- Garmin activity ID
    date TEXT NOT NULL,             -- 'YYYY-MM-DD'
    activity_type TEXT,             -- e.g. 'running', 'cycling', 'walking', 'strength_training'
    name TEXT,                      -- User-given name like 'Morning Run'
    duration_seconds REAL,
    distance_meters REAL,
    calories REAL,
    avg_hr REAL,                   -- Average heart rate during activity
    max_hr REAL,                   -- Max heart rate during activity
    data JSON NOT NULL             -- Full activity JSON
);

CREATE TABLE sleep (
    date TEXT PRIMARY KEY,
    duration_seconds REAL,         -- Total sleep time
    deep_seconds REAL,             -- Deep sleep duration
    light_seconds REAL,            -- Light sleep duration
    rem_seconds REAL,              -- REM sleep duration
    awake_seconds REAL             -- Time awake during sleep
);

CREATE TABLE heart_rate (
    date TEXT PRIMARY KEY,
    resting_hr INTEGER,            -- Resting heart rate
    max_hr INTEGER,                -- Daily max heart rate
    min_hr INTEGER                 -- Daily min heart rate
);

NOTES:
- All dates are TEXT in 'YYYY-MM-DD' format. Use date() and strftime() for date math.
- Use json_extract(data, '$.fieldName') to access JSON fields in daily_stats.
- To convert seconds to hours: column / 3600.0
- To convert seconds to minutes: column / 60.0
- To convert meters to kilometers: column / 1000.0
"""

SQL_SYSTEM_PROMPT = f"""You are a health data analyst that writes SQL queries.
The user has a Garmin smartwatch and their health data is stored in SQLite.

{SCHEMA_DESCRIPTION}

Today's date is {{today}}.

Given the user's question, write a SQLite query to retrieve the relevant data.
Return ONLY a JSON object in this exact format:
{{"sql": "SELECT ...", "explanation": "Brief description of what this query returns"}}

Rules:
- ONLY use SELECT statements. Never INSERT, UPDATE, DELETE, DROP, or ALTER.
- Use only tables and columns from the schema above.
- For JSON fields in daily_stats, use json_extract(data, '$.fieldName').
- For relative dates, use date('now', '-N days') or date('{{today}}', '-N days').
- Add ORDER BY and LIMIT where appropriate to keep results manageable.
- Maximum LIMIT 200 rows.
- If the question is ambiguous, make a reasonable assumption and explain it.
- If the question cannot be answered from the available data, return:
  {{"sql": null, "explanation": "Why this can't be answered"}}
"""

SUMMARY_SYSTEM_PROMPT = """You are a helpful health and fitness analyst. The user wears a Garmin
smartwatch and asked a question about their health data. A SQL query was run against their
database and you now have the results.

Analyze the results and provide a clear, insightful answer to their question.
- Reference specific numbers and dates from the data.
- Spot trends, patterns, or anomalies if relevant.
- Give actionable recommendations when appropriate.
- Keep it concise and well-structured. Use bullet points for clarity.
- Note: you are an AI, not a medical professional. Mention this if giving health advice."""


# --- Backend Dispatch ---

def _call_llm(system: str, user: str, model_key: str, max_tokens: int = 1024) -> str:
    """Route LLM call to the appropriate backend."""
    model_info = MODELS.get(model_key, MODELS[DEFAULT_MODEL])

    if model_info["backend"] == "ollama":
        return _call_ollama(system, user, model_info["model_id"], max_tokens)
    else:
        return _call_anthropic(system, user, model_info["model_id"], max_tokens)


def _call_ollama(system: str, user: str, model_id: str, max_tokens: int) -> str:
    """Call Ollama local API."""
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE}/api/chat",
            json={
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
            timeout=300.0,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except httpx.ConnectError:
        raise ConnectionError(
            "Ollama is not running. Start it with 'ollama serve' or launch the Ollama app."
        )


def _call_anthropic(system: str, user: str, model_id: str, max_tokens: int) -> str:
    """Call Anthropic API."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set. Add it on the Settings page.")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model_id,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text.strip()


# --- Query Helpers ---

def _get_readonly_connection():
    """Open a read-only database connection."""
    uri = f"file:{db.DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _run_query(sql: str) -> tuple[list[dict], list[str]]:
    """Execute a read-only SQL query. Returns (rows, column_names)."""
    conn = _get_readonly_connection()
    try:
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        return rows, columns
    finally:
        conn.close()


def _format_results(rows: list[dict], columns: list[str], max_rows: int = 50) -> str:
    """Format query results as a readable text table."""
    if not rows:
        return "(No results)"

    truncated = len(rows) > max_rows
    display_rows = rows[:max_rows]

    lines = []
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in display_rows:
        lines.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")

    if truncated:
        lines.append(f"\n... ({len(rows)} total rows, showing first {max_rows})")

    return "\n".join(lines)


# --- Public API ---

def get_available_models() -> list[dict]:
    """Return list of available models with their info."""
    models = []
    for key, info in MODELS.items():
        models.append({
            "id": key,
            "name": info["name"],
            "backend": info["backend"],
            "size": info["size"],
        })
    return models


def check_ollama_status() -> dict:
    """Check if Ollama is running and which models are pulled."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5.0)
        resp.raise_for_status()
        pulled = [m["name"] for m in resp.json().get("models", [])]
        return {"running": True, "models": pulled}
    except Exception:
        return {"running": False, "models": []}


def analyze(question: str, days: int = 30, model: str | None = None) -> str:
    """Ask a free-form question about the user's health data."""
    model_key = model or os.environ.get("DEFAULT_MODEL", DEFAULT_MODEL)

    # Check we have data
    try:
        min_date, max_date = db.get_date_range()
        if not min_date:
            return "No data available yet. Please sync your Garmin data first."
    except Exception:
        return "No data available yet. Please sync your Garmin data first."

    today = date.today().isoformat()

    # Step 1: Generate SQL
    sql_prompt = SQL_SYSTEM_PROMPT.replace("{today}", today)
    try:
        raw_text = _call_llm(sql_prompt, question, model_key, max_tokens=512)

        # Parse JSON from response (handle markdown code blocks)
        if "```" in raw_text:
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        parsed = json.loads(raw_text)
        sql = parsed.get("sql")
        explanation = parsed.get("explanation", "")
    except (json.JSONDecodeError, IndexError, KeyError) as e:
        logger.warning(f"Failed to parse SQL response: {e}")
        return _fallback_analyze(question, days, model_key)
    except (ConnectionError, ValueError) as e:
        return str(e)

    if not sql:
        return f"I can't answer that from the available Garmin data. {explanation}"

    # Validate: only SELECT allowed
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        return "I can only run read-only queries against your data."

    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "ATTACH"]
    for keyword in forbidden:
        if keyword in sql_upper.split():
            return "I can only run read-only queries against your data."

    # Step 2: Execute query
    try:
        rows, columns = _run_query(sql)
    except sqlite3.Error as e:
        logger.warning(f"SQL query failed: {e}\nQuery: {sql}")
        return _fallback_analyze(question, days, model_key)

    results_text = _format_results(rows, columns)

    # Step 3: Summarize results
    try:
        summary_user = (
            f"My question: {question}\n\n"
            f"SQL query used: {sql}\n"
            f"Query explanation: {explanation}\n\n"
            f"Data available from {min_date} to {max_date}.\n\n"
            f"Query results:\n{results_text}"
        )
        return _call_llm(SUMMARY_SYSTEM_PROMPT, summary_user, model_key, max_tokens=1024)
    except Exception:
        logger.exception("Summary generation failed")
        return f"**Query:** {explanation}\n\n{results_text}"


def _fallback_analyze(question: str, days: int, model_key: str) -> str:
    """Fallback: use the text summary approach if SQL generation fails."""
    data_summary = db.get_data_summary(days=days)
    if not data_summary.strip() or "===" not in data_summary:
        return "No data available yet. Please sync your Garmin data first."

    user_msg = f"Here is my recent health data:\n\n{data_summary}\n\nMy question: {question}"
    return _call_llm(SUMMARY_SYSTEM_PROMPT, user_msg, model_key, max_tokens=1024)
