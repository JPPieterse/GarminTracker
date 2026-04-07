"""Multi-user Garmin Connect sync service with encrypted credentials."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import structlog
from garminconnect import Garmin
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value
from app.models.health import (
    Activity,
    DailyStat,
    HeartRateRecord,
    SleepRecord,
    SyncLog,
    SyncStatus,
)
from app.models.garmin_extended import (
    BodyCompositionRecord,
    HrvRecord,
    PerformanceMetric,
    StressDetailRecord,
    TrainingReadinessRecord,
)
from app.models.user import GarminCredential

logger = structlog.get_logger()

# Token store directory — persists Garmin OAuth tokens to avoid repeated logins
_TOKEN_DIR = Path(os.environ.get("USERPROFILE", os.path.expanduser("~"))) / "personal" / "GarminTracker" / ".garminconnect"


async def _get_garmin_client(db: AsyncSession, user_id: uuid.UUID) -> Garmin:
    """Decrypt stored credentials and return an authenticated Garmin client."""
    stmt = select(GarminCredential).where(GarminCredential.user_id == user_id)
    result = await db.execute(stmt)
    cred = result.scalar_one_or_none()
    if cred is None:
        raise ValueError("No Garmin credentials stored. Go to Settings → Connect Garmin first.")

    email = decrypt_value(cred.encrypted_email)
    password = decrypt_value(cred.encrypted_password)

    # Per-user token directory so tokens are cached between syncs
    user_token_dir = _TOKEN_DIR / str(user_id)
    user_token_dir.mkdir(parents=True, exist_ok=True)

    def _login():
        c = Garmin(email, password)
        c.login(tokenstore=str(user_token_dir))
        return c

    return await asyncio.to_thread(_login)


def _today() -> date:
    return datetime.now(timezone.utc).date()


async def _upsert_daily_stat(db: AsyncSession, user_id: uuid.UUID, target: date, data: dict) -> None:
    """Insert or update a daily stat record."""
    stmt = select(DailyStat).where(DailyStat.user_id == user_id, DailyStat.date == target)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.data = data
    else:
        db.add(DailyStat(user_id=user_id, date=target, data=data))


async def _upsert_activity(db: AsyncSession, user_id: uuid.UUID, target: date, act: dict) -> None:
    """Insert or update an activity record."""
    act_id = act.get("activityId")
    if not act_id:
        return
    stmt = select(Activity).where(Activity.id == act_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.data = act
    else:
        db.add(Activity(
            id=act_id,
            user_id=user_id,
            date=target,
            activity_type=act.get("activityType", {}).get("typeKey", ""),
            data=act,
        ))


async def _upsert_sleep(db: AsyncSession, user_id: uuid.UUID, target: date, data: dict) -> None:
    """Insert or update a sleep record."""
    stmt = select(SleepRecord).where(SleepRecord.user_id == user_id, SleepRecord.date == target)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.data = data
    else:
        db.add(SleepRecord(user_id=user_id, date=target, data=data))


async def _upsert_hr(db: AsyncSession, user_id: uuid.UUID, target: date, data: dict) -> None:
    """Insert or update a heart rate record."""
    stmt = select(HeartRateRecord).where(HeartRateRecord.user_id == user_id, HeartRateRecord.date == target)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.data = data
    else:
        db.add(HeartRateRecord(user_id=user_id, date=target, data=data))


async def _upsert_generic(db: AsyncSession, model_class, user_id: uuid.UUID, target: date, data: dict) -> None:
    """Generic upsert for any model with user_id + date + data columns."""
    stmt = select(model_class).where(model_class.user_id == user_id, model_class.date == target)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.data = data
    else:
        db.add(model_class(user_id=user_id, date=target, data=data))


async def sync_user_data(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_date: date | None = None,
) -> SyncLog:
    """Pull a day's worth of Garmin data for a user and upsert into the database."""
    target = target_date or _today()
    date_str = target.isoformat()
    now = datetime.now(timezone.utc)

    log = SyncLog(user_id=user_id, status=SyncStatus.STARTED, started_at=now)
    db.add(log)
    await db.flush()

    records = 0
    try:
        client = await _get_garmin_client(db, user_id)

        # Daily stats
        stats = await asyncio.to_thread(client.get_stats, date_str)
        if stats:
            await _upsert_daily_stat(db, user_id, target, stats)
            records += 1

        # Activities
        activities = await asyncio.to_thread(client.get_activities_by_date, date_str, date_str)
        for act in activities or []:
            await _upsert_activity(db, user_id, target, act)
            records += 1

        # Sleep
        sleep = await asyncio.to_thread(client.get_sleep_data, date_str)
        if sleep:
            await _upsert_sleep(db, user_id, target, sleep)
            records += 1

        # Heart rate
        hr = await asyncio.to_thread(client.get_heart_rates, date_str)
        if hr:
            await _upsert_hr(db, user_id, target, hr)
            records += 1

        # ── Extended metrics (best-effort — don't fail sync if these error) ──

        # HRV
        try:
            hrv = await asyncio.to_thread(client.get_hrv_data, date_str)
            if hrv:
                await _upsert_generic(db, HrvRecord, user_id, target, hrv)
                records += 1
        except Exception as exc:
            logger.debug("hrv_sync_skipped", error=str(exc))

        # Training readiness + status (combined into one record)
        try:
            readiness = await asyncio.to_thread(client.get_training_readiness, date_str)
            status = await asyncio.to_thread(client.get_training_status, date_str)
            combined = {}
            if readiness:
                combined["readiness"] = readiness
            if status:
                combined["status"] = status
            if combined:
                await _upsert_generic(db, TrainingReadinessRecord, user_id, target, combined)
                records += 1
        except Exception as exc:
            logger.debug("readiness_sync_skipped", error=str(exc))

        # Body composition
        try:
            body = await asyncio.to_thread(client.get_body_composition, date_str)
            if body:
                await _upsert_generic(db, BodyCompositionRecord, user_id, target, body)
                records += 1
        except Exception as exc:
            logger.debug("body_comp_sync_skipped", error=str(exc))

        # Stress detail + body battery events
        try:
            stress = await asyncio.to_thread(client.get_all_day_stress, date_str)
            bb_events = await asyncio.to_thread(client.get_body_battery_events, date_str)
            combined_stress = {}
            if stress:
                combined_stress["stress_timeline"] = stress
            if bb_events:
                combined_stress["body_battery_events"] = bb_events
            if combined_stress:
                await _upsert_generic(db, StressDetailRecord, user_id, target, combined_stress)
                records += 1
        except Exception as exc:
            logger.debug("stress_detail_sync_skipped", error=str(exc))

        # Performance metrics (VO2 max, race predictions, fitness age)
        try:
            perf = {}
            max_metrics = await asyncio.to_thread(client.get_max_metrics, date_str)
            if max_metrics:
                perf["max_metrics"] = max_metrics
            try:
                fitness_age = await asyncio.to_thread(client.get_fitnessage_data, date_str)
                if fitness_age:
                    perf["fitness_age"] = fitness_age
            except Exception:
                pass
            try:
                race_pred = await asyncio.to_thread(client.get_race_predictions)
                if race_pred:
                    perf["race_predictions"] = race_pred
            except Exception:
                pass
            if perf:
                await _upsert_generic(db, PerformanceMetric, user_id, target, perf)
                records += 1
        except Exception as exc:
            logger.debug("performance_sync_skipped", error=str(exc))

        log.status = SyncStatus.SUCCESS
        log.records_synced = records

    except Exception as exc:
        logger.error("garmin_sync_failed", user_id=str(user_id), error=str(exc))
        log.status = SyncStatus.FAILED
        log.error_message = str(exc)[:2000]

    log.finished_at = datetime.now(timezone.utc)
    return log
