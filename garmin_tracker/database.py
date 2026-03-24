"""SQLite database for storing Garmin health data."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "garmin.db"


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                data JSON NOT NULL,
                synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                activity_type TEXT,
                name TEXT,
                duration_seconds REAL,
                distance_meters REAL,
                calories REAL,
                avg_hr REAL,
                max_hr REAL,
                data JSON NOT NULL,
                synced_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_activities_date ON activities(date);

            CREATE TABLE IF NOT EXISTS sleep (
                date TEXT PRIMARY KEY,
                duration_seconds REAL,
                deep_seconds REAL,
                light_seconds REAL,
                rem_seconds REAL,
                awake_seconds REAL,
                data JSON NOT NULL,
                synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS heart_rate (
                date TEXT PRIMARY KEY,
                resting_hr INTEGER,
                max_hr INTEGER,
                min_hr INTEGER,
                data JSON NOT NULL,
                synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                message TEXT
            );
        """)


def save_daily_stats(dt: str, data: dict):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO daily_stats (date, data, synced_at) VALUES (?, ?, ?)",
            (dt, json.dumps(data), datetime.utcnow().isoformat()),
        )


def save_activity(activity: dict):
    activity_id = activity.get("activityId")
    dt = activity.get("startTimeLocal", "")[:10]
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO activities
            (id, date, activity_type, name, duration_seconds, distance_meters,
             calories, avg_hr, max_hr, data, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                activity_id,
                dt,
                activity.get("activityType", {}).get("typeKey", "unknown"),
                activity.get("activityName", ""),
                activity.get("duration"),
                activity.get("distance"),
                activity.get("calories"),
                activity.get("averageHR"),
                activity.get("maxHR"),
                json.dumps(activity),
                datetime.utcnow().isoformat(),
            ),
        )


def save_sleep(dt: str, data: dict):
    sleep_data = data if isinstance(data, dict) else {}
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO sleep
            (date, duration_seconds, deep_seconds, light_seconds, rem_seconds,
             awake_seconds, data, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dt,
                sleep_data.get("sleepTimeInSeconds"),
                sleep_data.get("deepSleepSeconds"),
                sleep_data.get("lightSleepSeconds"),
                sleep_data.get("remSleepSeconds"),
                sleep_data.get("awakeSleepSeconds"),
                json.dumps(sleep_data),
                datetime.utcnow().isoformat(),
            ),
        )


def save_heart_rate(dt: str, data: dict):
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO heart_rate
            (date, resting_hr, max_hr, min_hr, data, synced_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                dt,
                data.get("restingHeartRate"),
                data.get("maxHeartRate"),
                data.get("minHeartRate"),
                json.dumps(data),
                datetime.utcnow().isoformat(),
            ),
        )


def get_data_summary(days: int = 30) -> str:
    """Get a text summary of recent data for LLM context."""
    with get_db() as conn:
        stats = conn.execute(
            "SELECT date, data FROM daily_stats ORDER BY date DESC LIMIT ?",
            (days,),
        ).fetchall()

        activities = conn.execute(
            "SELECT date, activity_type, name, duration_seconds, distance_meters, "
            "calories, avg_hr, max_hr FROM activities ORDER BY date DESC LIMIT ?",
            (days * 3,),
        ).fetchall()

        sleep_rows = conn.execute(
            "SELECT date, duration_seconds, deep_seconds, light_seconds, rem_seconds "
            "FROM sleep ORDER BY date DESC LIMIT ?",
            (days,),
        ).fetchall()

        hr_rows = conn.execute(
            "SELECT date, resting_hr, max_hr, min_hr FROM heart_rate ORDER BY date DESC LIMIT ?",
            (days,),
        ).fetchall()

    lines = []
    lines.append(f"=== HEALTH DATA SUMMARY (last {days} days) ===\n")

    if stats:
        lines.append("--- Daily Stats ---")
        for row in stats:
            d = json.loads(row["data"])
            lines.append(
                f"{row['date']}: steps={d.get('totalSteps', 'N/A')}, "
                f"calories={d.get('totalKilocalories', 'N/A')}, "
                f"active_min="
                f"{d.get('activeSeconds', 0) // 60 if d.get('activeSeconds') else 'N/A'}, "
                f"stress={d.get('averageStressLevel', 'N/A')}"
            )

    if activities:
        lines.append("\n--- Activities ---")
        for row in activities:
            dur = f"{row['duration_seconds'] / 60:.0f}min" if row["duration_seconds"] else "N/A"
            dist = f"{row['distance_meters'] / 1000:.1f}km" if row["distance_meters"] else ""
            lines.append(
                f"{row['date']}: {row['activity_type']} - {row['name']} "
                f"({dur}, {dist}, cal={row['calories']}, "
                f"avgHR={row['avg_hr']}, maxHR={row['max_hr']})"
            )

    if sleep_rows:
        lines.append("\n--- Sleep ---")
        for row in sleep_rows:
            total = f"{row['duration_seconds'] / 3600:.1f}h" if row["duration_seconds"] else "N/A"
            deep = f"{row['deep_seconds'] / 3600:.1f}h" if row["deep_seconds"] else "N/A"
            rem = f"{row['rem_seconds'] / 3600:.1f}h" if row["rem_seconds"] else "N/A"
            lines.append(f"{row['date']}: total={total}, deep={deep}, rem={rem}")

    if hr_rows:
        lines.append("\n--- Heart Rate ---")
        for row in hr_rows:
            lines.append(
                f"{row['date']}: resting={row['resting_hr']}, "
                f"max={row['max_hr']}, min={row['min_hr']}"
            )

    return "\n".join(lines)


def get_date_range():
    """Get the min and max dates we have data for."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT MIN(date) as min_date, MAX(date) as max_date FROM daily_stats"
        ).fetchone()
        return row["min_date"], row["max_date"]


def get_chart_data(metric: str, days: int = 30) -> list[dict]:
    """Get time-series data for charts."""
    with get_db() as conn:
        if metric == "steps":
            rows = conn.execute(
                "SELECT date, json_extract(data, '$.totalSteps') as value "
                "FROM daily_stats ORDER BY date DESC LIMIT ?",
                (days,),
            ).fetchall()
        elif metric == "calories":
            rows = conn.execute(
                "SELECT date, json_extract(data, '$.totalKilocalories') as value "
                "FROM daily_stats ORDER BY date DESC LIMIT ?",
                (days,),
            ).fetchall()
        elif metric == "resting_hr":
            rows = conn.execute(
                "SELECT date, resting_hr as value FROM heart_rate ORDER BY date DESC LIMIT ?",
                (days,),
            ).fetchall()
        elif metric == "sleep":
            rows = conn.execute(
                "SELECT date, ROUND(duration_seconds / 3600.0, 1) as value "
                "FROM sleep ORDER BY date DESC LIMIT ?",
                (days,),
            ).fetchall()
        elif metric == "stress":
            rows = conn.execute(
                "SELECT date, json_extract(data, '$.averageStressLevel') as value "
                "FROM daily_stats ORDER BY date DESC LIMIT ?",
                (days,),
            ).fetchall()
        else:
            return []

    return [
        {"date": r["date"], "value": r["value"]} for r in reversed(rows) if r["value"] is not None
    ]
