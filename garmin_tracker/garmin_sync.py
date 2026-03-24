"""Sync data from Garmin Connect to local database."""

import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path

from garminconnect import Garmin

from . import database as db

logger = logging.getLogger(__name__)

_client: Garmin | None = None


def get_client() -> Garmin:
    global _client
    if _client is None:
        email = os.environ.get("GARMIN_EMAIL")
        password = os.environ.get("GARMIN_PASSWORD")
        if not email or not password:
            raise ValueError("GARMIN_EMAIL and GARMIN_PASSWORD must be set")
        token_dir = str(Path(__file__).resolve().parent.parent / ".garminconnect")
        _client = Garmin(email, password)
        try:
            _client.login(token_dir)
        except Exception:
            _client.login()
            _client.garth.dump(token_dir)
    return _client


def sync_date(dt: date) -> dict:
    """Sync all data for a single date. Returns summary of what was synced."""
    client = get_client()
    date_str = dt.isoformat()
    synced = {}

    # Daily stats (steps, calories, stress, etc.)
    try:
        stats = client.get_stats(date_str)
        if stats:
            db.save_daily_stats(date_str, stats)
            synced["daily_stats"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch daily stats for {date_str}: {e}")
        synced["daily_stats"] = str(e)

    time.sleep(0.5)  # Respect rate limits

    # Activities
    try:
        activities = client.get_activities_by_date(date_str, date_str)
        for act in activities or []:
            db.save_activity(act)
        synced["activities"] = len(activities or [])
    except Exception as e:
        logger.warning(f"Failed to fetch activities for {date_str}: {e}")
        synced["activities"] = str(e)

    time.sleep(0.5)

    # Sleep
    try:
        sleep = client.get_sleep_data(date_str)
        if sleep and sleep.get("dailySleepDTO"):
            db.save_sleep(date_str, sleep["dailySleepDTO"])
            synced["sleep"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch sleep for {date_str}: {e}")
        synced["sleep"] = str(e)

    time.sleep(0.5)

    # Heart rate
    try:
        hr = client.get_heart_rates(date_str)
        if hr:
            db.save_heart_rate(date_str, hr)
            synced["heart_rate"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch heart rate for {date_str}: {e}")
        synced["heart_rate"] = str(e)

    return synced


def sync_range(start: date, end: date) -> list[dict]:
    """Sync data for a range of dates."""
    results = []
    current = start
    while current <= end:
        logger.info(f"Syncing {current.isoformat()}...")
        result = sync_date(current)
        results.append({"date": current.isoformat(), **result})
        current += timedelta(days=1)
        time.sleep(1)  # Extra delay between days
    return results


def sync_recent(days: int = 7) -> list[dict]:
    """Sync the last N days of data."""
    end = date.today()
    start = end - timedelta(days=days - 1)
    return sync_range(start, end)
