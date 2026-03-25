"""Multi-user Garmin Connect sync service with encrypted credentials."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import structlog
from garminconnect import Garmin
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
from app.models.user import GarminCredential

logger = structlog.get_logger()


async def _get_garmin_client(db: AsyncSession, user_id: uuid.UUID) -> Garmin:
    """Decrypt stored credentials and return an authenticated Garmin client."""
    stmt = select(GarminCredential).where(GarminCredential.user_id == user_id)
    result = await db.execute(stmt)
    cred = result.scalar_one_or_none()
    if cred is None:
        raise ValueError("No Garmin credentials stored for this user")

    email = decrypt_value(cred.encrypted_email)
    password = decrypt_value(cred.encrypted_password)

    client = Garmin(email, password)
    client.login()
    return client


def _today() -> date:
    return datetime.now(timezone.utc).date()


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
        stats = client.get_stats(date_str)
        if stats:
            stmt = (
                pg_insert(DailyStat)
                .values(user_id=user_id, date=target, data=stats)
                .on_conflict_do_update(
                    constraint="uq_daily_stat_user_date",
                    set_={"data": stats},
                )
            )
            await db.execute(stmt)
            records += 1

        # Activities
        activities = client.get_activities_by_date(date_str, date_str)
        for act in activities or []:
            act_id = act.get("activityId")
            if act_id:
                stmt = (
                    pg_insert(Activity)
                    .values(
                        id=act_id,
                        user_id=user_id,
                        date=target,
                        activity_type=act.get("activityType", {}).get("typeKey", ""),
                        data=act,
                    )
                    .on_conflict_do_update(
                        index_elements=["id"],
                        set_={"data": act},
                    )
                )
                await db.execute(stmt)
                records += 1

        # Sleep
        sleep = client.get_sleep_data(date_str)
        if sleep:
            stmt = (
                pg_insert(SleepRecord)
                .values(user_id=user_id, date=target, data=sleep)
                .on_conflict_do_update(
                    constraint="uq_sleep_user_date",
                    set_={"data": sleep},
                )
            )
            await db.execute(stmt)
            records += 1

        # Heart rate
        hr = client.get_heart_rates(date_str)
        if hr:
            stmt = (
                pg_insert(HeartRateRecord)
                .values(user_id=user_id, date=target, data=hr)
                .on_conflict_do_update(
                    constraint="uq_hr_user_date",
                    set_={"data": hr},
                )
            )
            await db.execute(stmt)
            records += 1

        log.status = SyncStatus.SUCCESS
        log.records_synced = records

    except Exception as exc:
        logger.error("garmin_sync_failed", user_id=str(user_id), error=str(exc))
        log.status = SyncStatus.FAILED
        log.error_message = str(exc)[:2000]

    log.finished_at = datetime.now(timezone.utc)
    return log
