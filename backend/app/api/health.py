"""Health data endpoints: sync, ask, chart, stats, models, export, delete account."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.billing import UsageType
from app.models.chat import ChatMessage
from app.models.health import Activity, DailyStat, HeartRateRecord, SleepRecord
from app.models.user import GarminCredential, User
from app.services import garmin_sync, llm_analyzer, usage

router = APIRouter(prefix="/health", tags=["health"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class SyncRequest(BaseModel):
    date: date | None = None


class AskRequest(BaseModel):
    question: str
    model: str | None = None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/sync")
async def sync_data(
    body: SyncRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a Garmin data sync for the authenticated user."""
    await usage.track_usage(db, user.id, UsageType.SYNC)
    log = await garmin_sync.sync_user_data(db, user.id, body.date)
    return {
        "status": log.status.value,
        "records_synced": log.records_synced,
        "error": log.error_message,
    }


@router.post("/ask")
async def ask_question(
    body: AskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ask a natural-language question about your health data."""
    if not await usage.check_ai_quota(db, user.id):
        raise HTTPException(status_code=429, detail="Monthly AI query limit reached. Upgrade to Pro.")

    await usage.track_usage(db, user.id, UsageType.AI_QUERY)
    result = await llm_analyzer.ask(db, user.id, body.question, model=body.model)
    return result


@router.get("/chart/{metric}")
async def get_chart_data(
    metric: str,
    start: date = Query(...),
    end: date = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return time-series data for a specific metric (for charting)."""
    stmt = (
        select(DailyStat.date, DailyStat.data)
        .where(DailyStat.user_id == user.id, DailyStat.date.between(start, end))
        .order_by(DailyStat.date)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return {
        "metric": metric,
        "data": [
            {"date": row.date.isoformat(), "value": row.data.get(metric)}
            for row in rows
        ],
    }


@router.get("/stats")
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return usage statistics for the current user."""
    return await usage.get_usage_stats(db, user.id)


@router.get("/models")
async def list_models():
    """List available AI models."""
    return await llm_analyzer.get_available_models()


@router.get("/export")
async def export_data(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """GDPR data export — returns all user data as a zip archive."""
    from fastapi.responses import StreamingResponse

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Daily stats
        stmt = select(DailyStat).where(DailyStat.user_id == user.id).order_by(DailyStat.date)
        result = await db.execute(stmt)
        stats = [{"date": r.date.isoformat(), "data": r.data} for r in result.scalars()]
        zf.writestr("daily_stats.json", json.dumps(stats, indent=2, default=str))

        # Activities
        stmt = select(Activity).where(Activity.user_id == user.id).order_by(Activity.date)
        result = await db.execute(stmt)
        acts = [{"id": r.id, "date": r.date.isoformat(), "type": r.activity_type, "data": r.data} for r in result.scalars()]
        zf.writestr("activities.json", json.dumps(acts, indent=2, default=str))

        # Sleep
        stmt = select(SleepRecord).where(SleepRecord.user_id == user.id).order_by(SleepRecord.date)
        result = await db.execute(stmt)
        sleeps = [{"date": r.date.isoformat(), "data": r.data} for r in result.scalars()]
        zf.writestr("sleep_records.json", json.dumps(sleeps, indent=2, default=str))

        # Heart rate
        stmt = select(HeartRateRecord).where(HeartRateRecord.user_id == user.id).order_by(HeartRateRecord.date)
        result = await db.execute(stmt)
        hrs = [{"date": r.date.isoformat(), "data": r.data} for r in result.scalars()]
        zf.writestr("heart_rate_records.json", json.dumps(hrs, indent=2, default=str))

        # Chat history
        stmt = select(ChatMessage).where(ChatMessage.user_id == user.id).order_by(ChatMessage.created_at)
        result = await db.execute(stmt)
        chats = [
            {"role": r.role.value, "content": r.content, "sql_query": r.sql_query, "created_at": r.created_at.isoformat()}
            for r in result.scalars()
        ]
        zf.writestr("chat_history.json", json.dumps(chats, indent=2, default=str))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=garmintracker_export.zip"},
    )


@router.delete("/account")
async def delete_account(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """GDPR account deletion — cascade deletes all user data."""
    await db.execute(delete(User).where(User.id == user.id))
    return {"status": "deleted"}
