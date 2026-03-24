"""LLM-powered analysis of Garmin health data using Claude.

Two-step approach:
1. Claude generates a SQL query from the user's natural language question
2. Query runs against the database (read-only)
3. Claude summarizes the results in plain English with insights
"""

import json
import logging
import os
import sqlite3
from datetime import date

import anthropic

from . import database as db

logger = logging.getLogger(__name__)

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


def analyze(question: str, days: int = 30) -> str:
    """Ask a free-form question about the user's health data.

    Uses a two-step LLM approach:
    1. Generate SQL from the question
    2. Run the query and summarize results
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "Error: ANTHROPIC_API_KEY not set. Please add it to your .env file."

    # Check we have data
    try:
        min_date, max_date = db.get_date_range()
        if not min_date:
            return "No data available yet. Please sync your Garmin data first."
    except Exception:
        return "No data available yet. Please sync your Garmin data first."

    today = date.today().isoformat()
    client = anthropic.Anthropic(api_key=api_key)

    # Step 1: Generate SQL
    sql_prompt = SQL_SYSTEM_PROMPT.replace("{today}", today)
    try:
        sql_response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            system=sql_prompt,
            messages=[{"role": "user", "content": question}],
        )
        raw_text = sql_response.content[0].text.strip()

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
        # Fall back to summary-based approach
        return _fallback_analyze(client, question, days)

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
        # Fall back to summary-based approach on SQL error
        return _fallback_analyze(client, question, days)

    results_text = _format_results(rows, columns)

    # Step 3: Summarize results
    try:
        summary_response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"My question: {question}\n\n"
                        f"SQL query used: {sql}\n"
                        f"Query explanation: {explanation}\n\n"
                        f"Data available from {min_date} to {max_date}.\n\n"
                        f"Query results:\n{results_text}"
                    ),
                }
            ],
        )
        return summary_response.content[0].text
    except Exception:
        logger.exception("Summary generation failed")
        # At least return the raw results
        return f"**Query:** {explanation}\n\n{results_text}"


def _fallback_analyze(client: anthropic.Anthropic, question: str, days: int) -> str:
    """Fallback: use the text summary approach if SQL generation fails."""
    data_summary = db.get_data_summary(days=days)
    if not data_summary.strip() or "===" not in data_summary:
        return "No data available yet. Please sync your Garmin data first."

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SUMMARY_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Here is my recent health data:\n\n{data_summary}\n\nMy question: {question}"
                ),
            }
        ],
    )
    return message.content[0].text
