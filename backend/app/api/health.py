"""Health data endpoints: sync, ask, chart, stats, models, export, delete account."""

import base64
import io
import json
import zipfile
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.billing import UsageType
from app.models.chat import ChatMessage
from app.models.health import Activity, DailyStat, HeartRateRecord, SleepRecord
from app.models.user import GarminCredential, User, UserProfile
from app.services import coaches, garmin_sync, knowledge, llm_analyzer, usage

router = APIRouter(prefix="/health", tags=["health"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class SyncRequest(BaseModel):
    date: Optional[date] = None


class AskRequest(BaseModel):
    question: str
    model: Optional[str] = None
    coach: Optional[str] = None


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/coaches")
async def list_coaches():
    """Return all available AI coaches."""
    return coaches.get_all_coaches()


@router.get("/knowledge/modules")
async def list_knowledge_modules():
    """List all knowledge modules and their availability status."""
    return knowledge.list_available_modules()


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


@router.post("/meal/analyze")
async def analyze_meal_photo(
    image: UploadFile = File(...),
    message: str = Form(""),
    coach: str = Form(""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyze a meal photo and log estimated nutrition data."""
    contents = await image.read()
    image_b64 = base64.b64encode(contents).decode("utf-8")
    media_type = image.content_type or "image/jpeg"

    await usage.track_usage(db, user.id, UsageType.AI_QUERY)

    result = await llm_analyzer.analyze_meal(
        db=db,
        user_id=user.id,
        image_base64=image_b64,
        media_type=media_type,
        message=message,
        coach_id=coach or None,
    )
    return result


@router.get("/chat/history")
async def get_chat_history(
    limit: int = Query(50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return recent chat messages for the coach interface."""
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = list(reversed(result.scalars().all()))

    return [
        {
            "role": m.role.value.lower(),
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "coach_id": m.coach_id,
        }
        for m in messages
    ]


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
    result = await llm_analyzer.ask(db, user.id, body.question, model=body.model, coach_id=body.coach)
    return result


# Mapping from frontend metric names to Garmin JSON fields
_DAILY_STAT_FIELDS = {
    "steps": "totalSteps",
    "calories": "totalKilocalories",
    "active_calories": "activeKilocalories",
    "distance": "totalDistanceMeters",
    "stress": "averageStressLevel",
    "body_battery": "bodyBatteryMostRecentValue",
    "body_battery_high": "bodyBatteryHighestValue",
    "body_battery_low": "bodyBatteryLowestValue",
    "spo2": "averageSpo2",
    "respiration": "avgWakingRespirationValue",
    "floors": "floorsAscended",
    "intensity_minutes": "moderateIntensityMinutes",
    "vigorous_minutes": "vigorousIntensityMinutes",
}

_SLEEP_FIELDS = {
    "sleep_total": "sleepTimeSeconds",
    "sleep_deep": "deepSleepSeconds",
    "sleep_light": "lightSleepSeconds",
    "sleep_rem": "remSleepSeconds",
    "sleep_awake": "awakeSleepSeconds",
    "sleep_hr": "avgHeartRate",
    "sleep_spo2": "averageSpO2Value",
    "sleep_stress": "avgSleepStress",
    "sleep_respiration": "averageRespirationValue",
}

_HR_FIELDS = {
    "heart_rate": "restingHeartRate",
    "hr_max": "maxHeartRate",
    "hr_min": "minHeartRate",
}


def _seconds_to_hours(val):
    """Convert seconds to hours rounded to 1 decimal."""
    return round(val / 3600, 1) if val else None


@router.get("/onboarding/status")
async def onboarding_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if the user needs onboarding."""
    stmt = select(UserProfile).where(UserProfile.user_id == user.id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    needs_onboarding = profile is None or not profile.context.strip()
    return {"needs_onboarding": needs_onboarding}


class OnboardingMessage(BaseModel):
    message: str
    history: list[dict] = []


ONBOARDING_SYSTEM_PROMPT_TEMPLATE = """You are the onboarding coach for ZEV (Zone Enhanced Vitals), a personal health and fitness AI platform.
This is the user's first conversation. Your job is to get to know them through a friendly, natural chat.

IMPORTANT: You already have access to the user's Garmin health data. Reference it naturally in conversation
to show you've already been looking at their numbers. This builds trust and shows the value of the app immediately.

{data_summary}

You need to gather the following information (but don't make it feel like a form — be conversational):
- Basic info: age, sex, height, weight
- Fitness level and experience
- Current training routine (what sports/activities, how often, typical schedule)
- Fitness goals (short-term and long-term)
- Any injuries, health conditions, or limitations
- Diet preferences or goals
- Sleep habits and schedule
- What they most want help with from this app

Rules:
1. Lead with what you already know from their data — "I can see you've been averaging X steps" etc.
2. Ask 2-3 questions at a time max
3. Be warm and encouraging, like a personal trainer meeting someone for the first time
4. React to their answers — show you're listening before asking more
5. After you have enough info (usually 3-5 exchanges), summarize what you've learned and let them know you're saving it
6. When you have enough info, end your message with the EXACT tag: [ONBOARDING_COMPLETE]
7. Keep it concise — no long paragraphs"""


PROFILE_EXTRACTION_PROMPT = """Extract a clean, well-organized health profile from this onboarding conversation.
Write it as a natural-language document that will be used as persistent context for an AI health assistant.
Organize it clearly with sections but keep it readable — not a form, more like notes a personal trainer would keep.
Include everything the user mentioned. Be concise but complete."""


async def _build_data_summary(db: AsyncSession, user_id) -> str:
    """Build a summary of the user's health data for the onboarding prompt."""
    from sqlalchemy import func as sqlfunc
    from datetime import timedelta

    lines = []
    end_date = date.today()
    start_30 = end_date - timedelta(days=30)
    start_90 = end_date - timedelta(days=90)

    # Total days tracked
    days_result = await db.execute(
        select(sqlfunc.count(sqlfunc.distinct(DailyStat.date)))
        .where(DailyStat.user_id == user_id)
    )
    total_days = days_result.scalar_one()
    if total_days == 0:
        return "The user has no health data synced yet."

    # Date range
    range_result = await db.execute(
        select(sqlfunc.min(DailyStat.date), sqlfunc.max(DailyStat.date))
        .where(DailyStat.user_id == user_id)
    )
    row = range_result.one()
    lines.append(f"Data available: {total_days} days ({row[0]} to {row[1]})")

    # Recent daily stats averages (last 30 days)
    stmt = select(DailyStat.data).where(
        DailyStat.user_id == user_id,
        DailyStat.date >= start_30,
    )
    result = await db.execute(stmt)
    stats = [r[0] for r in result.all() if r[0]]

    if stats:
        steps = [s.get("totalSteps") for s in stats if s.get("totalSteps")]
        if steps:
            lines.append(f"Avg daily steps (30d): {round(sum(steps)/len(steps)):,}")

        stress = [s.get("averageStressLevel") for s in stats if s.get("averageStressLevel")]
        if stress:
            lines.append(f"Avg stress level (30d): {round(sum(stress)/len(stress))}")

        bb = [s.get("bodyBatteryHighestValue") for s in stats if s.get("bodyBatteryHighestValue")]
        if bb:
            lines.append(f"Avg peak body battery (30d): {round(sum(bb)/len(bb))}")

        rhr = [s.get("restingHeartRate") for s in stats if s.get("restingHeartRate")]
        if rhr:
            lines.append(f"Avg resting heart rate (30d): {round(sum(rhr)/len(rhr))} bpm")

    # Sleep summary
    stmt = select(SleepRecord.data).where(
        SleepRecord.user_id == user_id,
        SleepRecord.date >= start_30,
    )
    result = await db.execute(stmt)
    sleeps = [r[0] for r in result.all() if r[0]]

    if sleeps:
        durations = [s.get("sleepTimeSeconds") for s in sleeps if s.get("sleepTimeSeconds")]
        if durations:
            avg_hrs = round(sum(durations) / len(durations) / 3600, 1)
            lines.append(f"Avg sleep duration (30d): {avg_hrs} hours")

        deep = [s.get("deepSleepSeconds") for s in sleeps if s.get("deepSleepSeconds")]
        if deep:
            avg_deep = round(sum(deep) / len(deep) / 3600, 1)
            lines.append(f"Avg deep sleep (30d): {avg_deep} hours")

    # Activity summary
    stmt = select(Activity.activity_type, sqlfunc.count(Activity.id)).where(
        Activity.user_id == user_id,
        Activity.date >= start_90,
    ).group_by(Activity.activity_type)
    result = await db.execute(stmt)
    activities = result.all()

    if activities:
        act_parts = [f"{count}x {atype}" for atype, count in activities]
        lines.append(f"Activities (90d): {', '.join(act_parts)}")

    # Running specifics
    stmt = select(Activity.data).where(
        Activity.user_id == user_id,
        Activity.activity_type == "running",
        Activity.date >= start_90,
    )
    result = await db.execute(stmt)
    runs = [r[0] for r in result.all() if r[0]]

    if runs:
        distances = [r.get("distance", 0) for r in runs if r.get("distance")]
        if distances:
            total_km = round(sum(distances) / 1000, 1)
            avg_km = round(sum(distances) / len(distances) / 1000, 1)
            lines.append(f"Running (90d): {len(runs)} runs, {total_km} km total, avg {avg_km} km/run")

    if not lines:
        return "The user has health data synced but no recent activity."

    return "User's Health Data Summary:\n" + "\n".join(f"- {l}" for l in lines)


@router.post("/onboarding/chat")
async def onboarding_chat(
    body: OnboardingMessage,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Handle onboarding conversation turns."""
    import anthropic
    from app.core.config import settings
    from app.models.chat import ChatMessage, ChatRole

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Build data-aware system prompt
    data_summary = await _build_data_summary(db, user.id)
    system_prompt = ONBOARDING_SYSTEM_PROMPT_TEMPLATE.format(data_summary=data_summary)

    messages = body.history.copy()
    if body.message:
        messages.append({"role": "user", "content": body.message})
        # Save user message to DB
        db.add(ChatMessage(user_id=user.id, role=ChatRole.USER, content=body.message))
        await db.flush()

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=system_prompt,
        messages=messages if messages else [{"role": "user", "content": "Hi, I just signed up!"}],
    )

    assistant_reply = response.content[0].text
    is_complete = "[ONBOARDING_COMPLETE]" in assistant_reply
    display_reply = assistant_reply.replace("[ONBOARDING_COMPLETE]", "").strip()

    # Save assistant message to DB
    db.add(ChatMessage(
        user_id=user.id,
        role=ChatRole.ASSISTANT,
        content=display_reply,
        model_used="claude-sonnet-4-20250514",
    ))
    await db.flush()

    # If onboarding is complete, extract and save the profile
    if is_complete:
        full_convo = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in messages
        )
        full_convo += f"\nAssistant: {assistant_reply}"

        extraction = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=PROFILE_EXTRACTION_PROMPT,
            messages=[{"role": "user", "content": full_convo}],
        )
        profile_text = extraction.content[0].text

        stmt = select(UserProfile).where(UserProfile.user_id == user.id)
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = UserProfile(user_id=user.id)
            db.add(profile)
        profile.context = profile_text
        await db.flush()

    updated_history = messages + [{"role": "assistant", "content": assistant_reply}]

    return {
        "reply": display_reply,
        "history": updated_history,
        "complete": is_complete,
    }


@router.get("/chart/{metric}")
async def get_chart_data(
    metric: str,
    days: int = Query(30),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return time-series data for a specific metric (for charting)."""
    from datetime import timedelta
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Determine which table and field to query
    if metric in _DAILY_STAT_FIELDS:
        field = _DAILY_STAT_FIELDS[metric]
        stmt = (
            select(DailyStat.date, DailyStat.data)
            .where(DailyStat.user_id == user.id, DailyStat.date.between(start_date, end_date))
            .order_by(DailyStat.date)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {"date": row.date.isoformat(), "value": row.data.get(field)}
            for row in rows
            if row.data.get(field) is not None
        ]

    elif metric in _SLEEP_FIELDS:
        field = _SLEEP_FIELDS[metric]
        is_duration = field.endswith("Seconds")
        stmt = (
            select(SleepRecord.date, SleepRecord.data)
            .where(SleepRecord.user_id == user.id, SleepRecord.date.between(start_date, end_date))
            .order_by(SleepRecord.date)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                "date": row.date.isoformat(),
                "value": _seconds_to_hours(row.data.get(field)) if is_duration else row.data.get(field),
            }
            for row in rows
            if row.data.get(field) is not None
        ]

    elif metric in _HR_FIELDS:
        field = _HR_FIELDS[metric]
        stmt = (
            select(HeartRateRecord.date, HeartRateRecord.data)
            .where(HeartRateRecord.user_id == user.id, HeartRateRecord.date.between(start_date, end_date))
            .order_by(HeartRateRecord.date)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {"date": row.date.isoformat(), "value": row.data.get(field)}
            for row in rows
            if row.data.get(field) is not None
        ]

    else:
        # Fallback — try daily_stats raw field name
        stmt = (
            select(DailyStat.date, DailyStat.data)
            .where(DailyStat.user_id == user.id, DailyStat.date.between(start_date, end_date))
            .order_by(DailyStat.date)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {"date": row.date.isoformat(), "value": row.data.get(metric)}
            for row in rows
            if row.data.get(metric) is not None
        ]


@router.get("/sleep/breakdown")
async def get_sleep_breakdown(
    days: int = Query(30),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return sleep stage breakdown (stacked bar chart data)."""
    from datetime import timedelta
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    stmt = (
        select(SleepRecord.date, SleepRecord.data)
        .where(SleepRecord.user_id == user.id, SleepRecord.date.between(start_date, end_date))
        .order_by(SleepRecord.date)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "date": row.date.isoformat(),
            "deep": _seconds_to_hours(row.data.get("deepSleepSeconds")),
            "light": _seconds_to_hours(row.data.get("lightSleepSeconds")),
            "rem": _seconds_to_hours(row.data.get("remSleepSeconds")),
            "awake": _seconds_to_hours(row.data.get("awakeSleepSeconds")),
            "total": _seconds_to_hours(row.data.get("sleepTimeSeconds")),
        }
        for row in rows
        if row.data.get("sleepTimeSeconds")
    ]


@router.get("/activities/summary")
async def get_activities_summary(
    days: int = Query(90),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return activity summaries for charts."""
    from datetime import timedelta
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    stmt = (
        select(Activity)
        .where(Activity.user_id == user.id, Activity.date.between(start_date, end_date))
        .order_by(Activity.date)
    )
    result = await db.execute(stmt)
    activities = result.scalars().all()

    return [
        {
            "date": a.date.isoformat(),
            "type": a.activity_type,
            "name": a.data.get("activityName", a.data.get("name", "")),
            "duration_min": round(a.data.get("duration", 0) / 60, 1) if a.data.get("duration") else round(a.data.get("movingDuration", 0) / 60, 1),
            "distance_km": round(a.data.get("distance", 0) / 1000, 2) if a.data.get("distance") else None,
            "calories": a.data.get("calories"),
            "avg_hr": a.data.get("averageHR") or a.data.get("avgHR"),
            "max_hr": a.data.get("maxHR"),
        }
        for a in activities
    ]


@router.get("/stats")
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return dashboard statistics for the current user."""
    from sqlalchemy import func as sqlfunc

    # Count days with data
    days_result = await db.execute(
        select(sqlfunc.count(sqlfunc.distinct(DailyStat.date)))
        .where(DailyStat.user_id == user.id)
    )
    total_days = days_result.scalar_one()

    # Count activities
    act_result = await db.execute(
        select(sqlfunc.count(Activity.id)).where(Activity.user_id == user.id)
    )
    total_activities = act_result.scalar_one()

    # Date range
    range_result = await db.execute(
        select(sqlfunc.min(DailyStat.date), sqlfunc.max(DailyStat.date))
        .where(DailyStat.user_id == user.id)
    )
    row = range_result.one()
    date_range = (
        {"start": row[0].isoformat(), "end": row[1].isoformat()}
        if row[0]
        else None
    )

    # AI queries this month
    ai_stats = await usage.get_usage_stats(db, user.id)

    return {
        "total_days": total_days,
        "total_activities": total_activities,
        "date_range": date_range,
        "ai_queries": ai_stats.get("ai_query", 0),
    }


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
        headers={"Content-Disposition": "attachment; filename=zev_export.zip"},
    )


@router.delete("/account")
async def delete_account(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """GDPR account deletion — cascade deletes all user data."""
    await db.execute(delete(User).where(User.id == user.id))
    return {"status": "deleted"}
