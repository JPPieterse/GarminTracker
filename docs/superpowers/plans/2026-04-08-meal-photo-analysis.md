# Meal Photo Analysis & Always-On Coach Data Context — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the ZEV coach always-on access to recent health data, add timezone awareness, and let users photograph meals for AI-powered nutrition logging via WhatsApp-style attachment UX.

**Architecture:** Vision-in-chat approach — meal photos go directly into a Claude API call as image content blocks alongside the coach persona. Structured nutrition data is extracted via `[MEAL_LOG]` tags (same pattern as existing `[PROGRAM_UPDATE]`). A new `MealLog` model stores the extracted data. The coach system prompt is enhanced with a compact health data snapshot (up to 14 days) on every interaction.

**Tech Stack:** Python/FastAPI backend, SQLAlchemy + SQLite, Anthropic Claude API (vision), Next.js/React frontend, Lucide icons

**Spec:** `docs/superpowers/specs/2026-04-08-meal-photo-analysis-design.md`

---

## File Map

### New Files
| File | Responsibility |
|------|----------------|
| `backend/app/models/meal.py` | MealLog SQLAlchemy model + enums |
| `backend/knowledge/meal-photo-analysis.md` | Domain knowledge for visual portion estimation |
| `backend/tests/test_meal.py` | Tests for meal model, snapshot builder, meal log extraction |

### Modified Files
| File | Changes |
|------|---------|
| `backend/app/models/user.py` | Add `timezone` field to UserProfile |
| `backend/app/models/__init__.py` | Import MealLog |
| `backend/app/services/llm_analyzer.py` | Add `_build_recent_snapshot()`, `_build_today_meal_summary()`, `_handle_meal_log()`, `analyze_meal()`, update `CHAT_SYSTEM_PROMPT`, update `DB_SCHEMA`, inject timezone + snapshot into all paths |
| `backend/app/services/knowledge.py` | Add meal-photo-analysis module + keyword triggers |
| `backend/app/api/health.py` | Add `POST /health/meal/analyze` endpoint |
| `backend/app/main.py` | Import meal model for table creation |
| `frontend/app/dashboard/ask/page.tsx` | Attach button, popover, thumbnail preview, "Sent a photo" bubbles, meal upload flow |
| `frontend/lib/api.ts` | Add `analyzeMeal()` function |
| `frontend/lib/types.ts` | Add `MealAnalysisResponse` type |

---

### Task 1: MealLog Data Model

**Files:**
- Create: `backend/app/models/meal.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_meal.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_meal.py`:

```python
"""Tests for the MealLog model."""

import uuid
from datetime import date, time

import pytest

from app.models.meal import MealLog, MealType, MealConfidence


@pytest.mark.asyncio
async def test_create_meal_log(db_session, test_user):
    """MealLog can be created with all fields and persisted."""
    meal = MealLog(
        user_id=test_user.id,
        date=date(2026, 4, 8),
        time=time(12, 30),
        meal_type=MealType.LUNCH,
        calories=650,
        protein_g=42.0,
        carbs_g=55.0,
        fat_g=22.0,
        fiber_g=8.0,
        sodium_mg=480.0,
        ingredients="grilled chicken breast ~180g, brown rice ~1 cup, steamed broccoli ~1 cup",
        confidence=MealConfidence.HIGH,
        notes="post-workout meal",
        hydration_ml=500,
    )
    db_session.add(meal)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(
        select(MealLog).where(MealLog.user_id == test_user.id)
    )
    saved = result.scalar_one()

    assert saved.calories == 650
    assert saved.protein_g == 42.0
    assert saved.meal_type == MealType.LUNCH
    assert saved.confidence == MealConfidence.HIGH
    assert saved.ingredients == "grilled chicken breast ~180g, brown rice ~1 cup, steamed broccoli ~1 cup"


@pytest.mark.asyncio
async def test_meal_log_optional_fields(db_session, test_user):
    """MealLog works with only required fields."""
    meal = MealLog(
        user_id=test_user.id,
        date=date(2026, 4, 8),
        time=time(8, 0),
        meal_type=MealType.BREAKFAST,
        calories=400,
        protein_g=25.0,
        carbs_g=45.0,
        fat_g=15.0,
        ingredients="oats with banana and peanut butter",
        confidence=MealConfidence.MEDIUM,
    )
    db_session.add(meal)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(
        select(MealLog).where(MealLog.user_id == test_user.id)
    )
    saved = result.scalar_one()

    assert saved.fiber_g is None
    assert saved.sodium_mg is None
    assert saved.hydration_ml is None
    assert saved.notes is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/backend && python -m pytest tests/test_meal.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.meal'`

- [ ] **Step 3: Create the MealLog model**

Create `backend/app/models/meal.py`:

```python
"""Meal logging model — stores nutrition data extracted from photo analysis."""

from __future__ import annotations

import enum
import uuid
from datetime import date, time

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class MealType(str, enum.Enum):
    BREAKFAST = "BREAKFAST"
    LUNCH = "LUNCH"
    DINNER = "DINNER"
    SNACK = "SNACK"


class MealConfidence(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class MealLog(UUIDMixin, TimestampMixin, Base):
    """A single meal entry with estimated nutrition data."""

    __tablename__ = "meal_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    time: Mapped[time] = mapped_column(Time)
    meal_type: Mapped[MealType] = mapped_column(String(16))
    calories: Mapped[int] = mapped_column(Integer)
    protein_g: Mapped[float] = mapped_column(Float)
    carbs_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    fiber_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    sodium_mg: Mapped[float | None] = mapped_column(Float, nullable=True)
    ingredients: Mapped[str] = mapped_column(Text)
    confidence: Mapped[MealConfidence] = mapped_column(String(8))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    hydration_ml: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 4: Register the model in `__init__.py`**

Add to `backend/app/models/__init__.py`:

```python
from app.models.meal import MealLog  # noqa: F401
```

- [ ] **Step 5: Import meal model in `main.py` for table auto-creation**

In `backend/app/main.py`, inside `_create_tables()`, add after the other model imports:

```python
        import app.models.meal  # noqa: F401
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/backend && python -m pytest tests/test_meal.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
cd C:/Users/JPPieterse/personal/GarminTracker
git add backend/app/models/meal.py backend/app/models/__init__.py backend/app/main.py backend/tests/test_meal.py
git commit -m "feat: add MealLog model for nutrition tracking"
```

---

### Task 2: Add Timezone to UserProfile

**Files:**
- Modify: `backend/app/models/user.py`
- Test: `backend/tests/test_meal.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_meal.py`:

```python
from app.models.user import UserProfile


@pytest.mark.asyncio
async def test_user_profile_timezone(db_session, test_user):
    """UserProfile stores timezone string."""
    profile = UserProfile(
        user_id=test_user.id,
        context="Test user context",
        timezone="Africa/Johannesburg",
    )
    db_session.add(profile)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == test_user.id)
    )
    saved = result.scalar_one()
    assert saved.timezone == "Africa/Johannesburg"


@pytest.mark.asyncio
async def test_user_profile_timezone_defaults_none(db_session, test_user):
    """UserProfile.timezone defaults to None when not set."""
    profile = UserProfile(
        user_id=test_user.id,
        context="Test user context",
    )
    db_session.add(profile)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == test_user.id)
    )
    saved = result.scalar_one()
    assert saved.timezone is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/backend && python -m pytest tests/test_meal.py::test_user_profile_timezone -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'timezone'`

- [ ] **Step 3: Add timezone field to UserProfile**

In `backend/app/models/user.py`, add to the `UserProfile` class after `context`:

```python
    # IANA timezone string, e.g. "Africa/Johannesburg"
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

Also add `String` to the sqlalchemy import if not present (it already is).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/backend && python -m pytest tests/test_meal.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd C:/Users/JPPieterse/personal/GarminTracker
git add backend/app/models/user.py backend/tests/test_meal.py
git commit -m "feat: add timezone field to UserProfile"
```

---

### Task 3: Build Recent Health Data Snapshot

**Files:**
- Modify: `backend/app/services/llm_analyzer.py`
- Test: `backend/tests/test_meal.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_meal.py`:

```python
from datetime import date, time, timedelta


@pytest.mark.asyncio
async def test_build_recent_snapshot_with_data(db_session, test_user):
    """Snapshot includes recent daily stats and formats them compactly."""
    from app.models.health import DailyStat

    today = date.today()
    db_session.add(DailyStat(
        user_id=test_user.id,
        date=today,
        data={
            "totalSteps": 8420,
            "totalKilocalories": 2150,
            "averageStressLevel": 34,
            "bodyBatteryHighestValue": 78,
            "restingHeartRate": 58,
        },
    ))
    await db_session.commit()

    from app.services.llm_analyzer import _build_recent_snapshot
    snapshot = await _build_recent_snapshot(db_session, test_user.id)

    assert "8,420" in snapshot  # steps formatted with comma
    assert "2,150" in snapshot  # calories
    assert str(today) in snapshot


@pytest.mark.asyncio
async def test_build_recent_snapshot_empty(db_session, test_user):
    """Snapshot handles no data gracefully."""
    from app.services.llm_analyzer import _build_recent_snapshot
    snapshot = await _build_recent_snapshot(db_session, test_user.id)

    assert "No health data" in snapshot


@pytest.mark.asyncio
async def test_build_recent_snapshot_shows_gap(db_session, test_user):
    """Snapshot shows how long since last data when there's a gap."""
    from app.models.health import DailyStat

    old_date = date.today() - timedelta(days=10)
    db_session.add(DailyStat(
        user_id=test_user.id,
        date=old_date,
        data={"totalSteps": 5000},
    ))
    await db_session.commit()

    from app.services.llm_analyzer import _build_recent_snapshot
    snapshot = await _build_recent_snapshot(db_session, test_user.id)

    assert "10 days ago" in snapshot or "ago" in snapshot
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/backend && python -m pytest tests/test_meal.py::test_build_recent_snapshot_with_data -v`
Expected: FAIL — `ImportError: cannot import name '_build_recent_snapshot'`

- [ ] **Step 3: Implement `_build_recent_snapshot`**

Add to `backend/app/services/llm_analyzer.py`, after the `_get_user_profile` function (around line 118):

```python
async def _build_recent_snapshot(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_timezone: str | None = None,
) -> str:
    """Build a compact summary of recent health data for the coach's context.

    Pulls up to 14 days of data, starting from the most recent date that has records.
    If the user hasn't synced recently, includes the gap duration.
    """
    from datetime import date as date_type, datetime, timedelta, timezone as tz
    from app.models.health import DailyStat, SleepRecord, HeartRateRecord, Activity
    from app.models.garmin_extended import (
        HrvRecord, TrainingReadinessRecord, BodyCompositionRecord,
        StressDetailRecord, PerformanceMetric,
    )
    from app.models.meal import MealLog

    today = date_type.today()

    # Find the most recent date with any data
    from sqlalchemy import func as sqlfunc, union_all
    date_queries = union_all(
        select(sqlfunc.max(DailyStat.date)).where(DailyStat.user_id == user_id),
        select(sqlfunc.max(SleepRecord.date)).where(SleepRecord.user_id == user_id),
        select(sqlfunc.max(Activity.date)).where(Activity.user_id == user_id),
    )
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
    activities_by_date: dict[date_type, list] = {}
    for a in activity_result.scalars():
        activities_by_date.setdefault(a.date, []).append(a)

    meal_stmt = select(MealLog).where(
        MealLog.user_id == user_id,
        MealLog.date.between(lookback_start, latest_date),
    ).order_by(MealLog.date.desc())
    meal_result = await db.execute(meal_stmt)
    meals_by_date: dict[date_type, list] = {}
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/backend && python -m pytest tests/test_meal.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
cd C:/Users/JPPieterse/personal/GarminTracker
git add backend/app/services/llm_analyzer.py backend/tests/test_meal.py
git commit -m "feat: add _build_recent_snapshot for always-on health context"
```

---

### Task 4: Update Coach System Prompts & Inject Snapshot

**Files:**
- Modify: `backend/app/services/llm_analyzer.py`

- [ ] **Step 1: Update `CHAT_SYSTEM_PROMPT`**

In `backend/app/services/llm_analyzer.py`, replace the line:

```python
6. If the user asks something that would need their actual tracked data (steps, sleep, HR),
   let them know you can look that up if they ask specifically
```

with:

```python
6. You always have access to the user's recent health data (shown below). Reference it
   naturally in conversation — don't wait for them to ask. For historical queries beyond
   what's shown, the system will automatically look up the data.
```

- [ ] **Step 2: Add timezone injection helper**

Add after `_build_recent_snapshot` in `llm_analyzer.py`:

```python
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
```

- [ ] **Step 3: Inject snapshot + timezone into the `ask()` function**

In the `ask()` function (around line 511), after loading `profile_context` and `program_context`, add:

```python
    # Load user timezone
    from app.models.user import UserProfile
    tz_stmt = select(UserProfile.timezone).where(UserProfile.user_id == user_id)
    tz_result = await db.execute(tz_stmt)
    user_timezone = tz_result.scalar_one_or_none()

    # Build always-on health snapshot
    snapshot = await _build_recent_snapshot(db, user_id, user_timezone)
    timezone_ctx = _build_timezone_context(user_timezone)
```

Then in the CHAT route, update `_chat_response` call to include snapshot and timezone:

```python
            answer_text = await _chat_response(
                question, history, profile_context, coach_prompt, program_context,
                snapshot=snapshot, timezone_ctx=timezone_ctx,
            )
```

And in the DATA route, include snapshot in the summary call:

```python
            answer_text = await _summarize_results(
                question, rows, profile_context, coach_prompt, snapshot=snapshot,
            )
```

- [ ] **Step 4: Update `_chat_response` signature and body**

Update `_chat_response` to accept and inject `snapshot` and `timezone_ctx`:

```python
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
    if timezone_ctx:
        system += timezone_ctx
    if program_context:
        system += f"\n{program_context}"
    if snapshot:
        system += snapshot

    # ... rest unchanged
```

- [ ] **Step 5: Update `_summarize_results` to accept snapshot**

```python
async def _summarize_results(
    question: str,
    results: list[dict],
    profile_context: str = "",
    coach_prompt: str = "",
    snapshot: str = "",
) -> str:
    """Use Claude to turn raw SQL results into a natural-language answer."""
    # ... existing code ...
    if snapshot:
        system += snapshot
    # ... rest unchanged
```

- [ ] **Step 6: Also inject into the ValueError fallback path**

In the `except ValueError` block of `ask()`, pass the same snapshot and timezone:

```python
        answer_text = await _chat_response(
            question, history, profile_context, coach_prompt, program_context,
            snapshot=snapshot, timezone_ctx=timezone_ctx,
        )
```

- [ ] **Step 7: Commit**

```bash
cd C:/Users/JPPieterse/personal/GarminTracker
git add backend/app/services/llm_analyzer.py
git commit -m "feat: inject health snapshot + timezone into all coach interactions"
```

---

### Task 5: Meal Photo Analysis Knowledge Module

**Files:**
- Create: `backend/knowledge/meal-photo-analysis.md`
- Modify: `backend/app/services/knowledge.py`

- [ ] **Step 1: Create the knowledge module**

Create `backend/knowledge/meal-photo-analysis.md`:

```markdown
# Meal Photo Analysis — Visual Estimation Guide

## Visual Portion Estimation

Use these hand-based references to estimate portions from photos:
- **Palm** = ~1 protein serving (~100-120g cooked meat/fish)
- **Fist** = ~1 cup of carbs (rice, pasta, vegetables)
- **Thumb tip** = ~1 teaspoon (oil, butter)
- **Thumb (full)** = ~1 tablespoon
- **Cupped hand** = ~1/2 cup (nuts, dried fruit, grains)

Estimate plate-to-food ratio: a standard dinner plate is 10-11 inches. A half-covered plate is roughly 1 serving of a main dish.

## Common Food Caloric Density (per 100g cooked unless noted)

**Proteins:**
- Chicken breast: ~165cal, 31g P, 0g C, 3.6g F
- Salmon: ~208cal, 20g P, 0g C, 13g F
- Beef mince (lean): ~250cal, 26g P, 0g C, 15g F
- Eggs (1 large): ~72cal, 6g P, 0.4g C, 5g F
- Biltong: ~250cal, 55g P, 1g C, 3g F

**Carbs:**
- Cooked rice (white): ~130cal, 2.7g P, 28g C, 0.3g F per cup
- Cooked rice (brown): ~216cal, 5g P, 45g C, 1.8g F per cup
- Pasta (cooked): ~220cal, 8g P, 43g C, 1.3g F per cup
- Bread (1 slice): ~80cal, 3g P, 15g C, 1g F
- Pap/maize meal (cooked): ~120cal, 2.7g P, 26g C, 0.5g F per cup
- Potato (baked, medium): ~160cal, 4g P, 37g C, 0.2g F

**Fats/Oils:**
- Olive oil: ~120cal per tablespoon, 14g F
- Butter: ~100cal per tablespoon, 11g F
- Peanut butter: ~94cal per tablespoon, 4g P, 3g C, 8g F
- Avocado (half): ~120cal, 1.5g P, 6g C, 11g F

## Cooking Method Adjustments

- **Fried vs grilled/baked:** add 30-50% calories from oil absorption
- **Creamy sauces:** add 150-300cal per generous serving
- **Light sauces (tomato-based):** add 50-100cal per serving
- **Cheese topping:** add ~110cal per 30g
- **Salad dressing:** add 150-200cal per 2 tablespoons (creamy), 80-120cal (vinaigrette)

## Common Estimation Pitfalls

- Hidden oils in restaurant cooking (often 2-3x home cooking amounts)
- Nuts and seeds are calorie-dense (~550-650cal/100g) — small handfuls add up fast
- Sauces, gravies, and dressings are often the biggest hidden calorie source
- Portion underestimation bias: people typically underestimate portions by 20-40%
- Drinks with calories: fruit juice (~110cal/glass), regular soda (~140cal/can), milk (~150cal/glass)

## South African Dishes

- **Bunny chow (quarter):** ~600-900cal depending on filling (bean ~600, mutton ~900)
- **Boerewors (1 link/100g):** ~280cal, 15g P, 2g C, 24g F
- **Biltong (100g):** ~250cal, 55g P, 1g C, 3g F
- **Droewors (100g):** ~350cal, 45g P, 2g C, 18g F
- **Pap with tomato relish:** ~300-400cal per serving (depends on butter/oil added)
- **Vetkoek (1 medium):** ~350cal, 6g P, 40g C, 18g F
- **Chakalaka (1 cup):** ~80cal, 3g P, 12g C, 2g F
- **Bobotie (1 serving):** ~450cal, 28g P, 20g C, 28g F
- **Braai meat (typical plate):** estimate per piece — chop ~250cal, wors ~280cal, steak ~300cal
- **Gatsby (half):** ~800-1200cal depending on filling

## Photo Analysis Tips

When the photo is unclear:
1. Ask about the protein source and cooking method first — these have the highest variance
2. Ask about added fats (oil, butter, cheese, dressing) — these are the most commonly missed
3. Estimate plate size relative to known objects if possible
4. When genuinely uncertain, give a range rather than a single number
5. Round to the nearest 25cal for individual items, nearest 50cal for total meal
```

- [ ] **Step 2: Add keyword triggers to knowledge.py**

In `backend/app/services/knowledge.py`, add a new entry to `_MODULE_KEYWORDS` after `"nutrition-fundamentals"`:

```python
    "meal-photo-analysis": [
        "photo", "picture", "image", "meal", "food", "ate", "eating",
        "plate", "portion", "serving", "snack", "breakfast", "lunch",
        "dinner", "macros", "calories", "nutrition", "what did i eat",
    ],
```

- [ ] **Step 3: Verify the module loads**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/backend && python -c "from app.services.knowledge import get_relevant_knowledge; r = get_relevant_knowledge('what macros are in this meal photo'); print('OK' if 'Portion' in r else 'FAIL')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd C:/Users/JPPieterse/personal/GarminTracker
git add backend/knowledge/meal-photo-analysis.md backend/app/services/knowledge.py
git commit -m "feat: add meal photo analysis knowledge module"
```

---

### Task 6: Meal Log Extraction & `analyze_meal()` Backend

**Files:**
- Modify: `backend/app/services/llm_analyzer.py`
- Test: `backend/tests/test_meal.py`

- [ ] **Step 1: Write the failing test for `[MEAL_LOG]` extraction**

Append to `backend/tests/test_meal.py`:

```python
@pytest.mark.asyncio
async def test_handle_meal_log_extracts_json(db_session, test_user):
    """_handle_meal_log extracts structured data from response and saves MealLog."""
    from app.services.llm_analyzer import _handle_meal_log
    from app.models.meal import MealLog, MealType
    from sqlalchemy import select

    response_text = """That looks like a solid post-workout meal! I can see grilled chicken breast with brown rice and steamed broccoli.

[MEAL_LOG]
```json
{"calories": 650, "protein_g": 42, "carbs_g": 55, "fat_g": 22, "fiber_g": 8, "sodium_mg": 480, "ingredients": "grilled chicken breast ~180g, brown rice ~1 cup, steamed broccoli ~1 cup, olive oil drizzle", "confidence": "HIGH"}
```

Great choice for recovery — that's about 42g of protein which is right in the sweet spot after a workout."""

    clean = await _handle_meal_log(db_session, test_user.id, response_text, user_timezone=None)

    # Tag should be stripped
    assert "[MEAL_LOG]" not in clean
    assert "grilled chicken breast" in clean  # conversational text preserved

    # MealLog should be saved
    result = await db_session.execute(
        select(MealLog).where(MealLog.user_id == test_user.id)
    )
    meal = result.scalar_one()
    assert meal.calories == 650
    assert meal.protein_g == 42.0
    assert meal.confidence.value == "HIGH"


@pytest.mark.asyncio
async def test_handle_meal_log_no_tag(db_session, test_user):
    """_handle_meal_log returns text unchanged when no tag present."""
    from app.services.llm_analyzer import _handle_meal_log

    text = "Sure, here's some advice about protein intake."
    result = await _handle_meal_log(db_session, test_user.id, text, user_timezone=None)
    assert result == text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/backend && python -m pytest tests/test_meal.py::test_handle_meal_log_extracts_json -v`
Expected: FAIL — `ImportError: cannot import name '_handle_meal_log'`

- [ ] **Step 3: Implement `_handle_meal_log`**

Add to `backend/app/services/llm_analyzer.py`, after `_handle_program_update`:

```python
async def _handle_meal_log(
    db: AsyncSession,
    user_id: uuid.UUID,
    answer_text: str,
    user_timezone: str | None = None,
) -> str:
    """Detect [MEAL_LOG] in the response, extract JSON, save MealLog record."""
    import json
    from datetime import datetime, timezone as tz, date as date_type, time as time_type
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/backend && python -m pytest tests/test_meal.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Implement `_build_today_meal_summary` and `analyze_meal`**

Add `_build_today_meal_summary` after `_handle_meal_log`:

```python
async def _build_today_meal_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_timezone: str | None = None,
) -> str:
    """Build a summary of today's meals for context in meal analysis."""
    from datetime import datetime, timezone as tz, date as date_type
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
```

Add `analyze_meal` as a new public function:

```python
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

    await _save_message(db, user_id, ChatRole.ASSISTANT, answer_text, model_used=model_used)

    return {"answer": answer_text, "results": [], "model": model_used, "count": 0}
```

- [ ] **Step 6: Update `DB_SCHEMA` with meal_logs table**

In the `DB_SCHEMA` string, add after the `performance_metrics` entry:

```python
- meal_logs: id (UUID), user_id (UUID), date (DATE), time (TIME), meal_type (VARCHAR: BREAKFAST/LUNCH/DINNER/SNACK),
  calories (INT), protein_g (FLOAT), carbs_g (FLOAT), fat_g (FLOAT),
  fiber_g (FLOAT, nullable), sodium_mg (FLOAT, nullable), ingredients (TEXT),
  confidence (VARCHAR: HIGH/MEDIUM/LOW), notes (TEXT, nullable), hydration_ml (INT, nullable)
```

- [ ] **Step 7: Run all tests**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/backend && python -m pytest tests/test_meal.py -v`
Expected: PASS (9 tests)

- [ ] **Step 8: Commit**

```bash
cd C:/Users/JPPieterse/personal/GarminTracker
git add backend/app/services/llm_analyzer.py backend/tests/test_meal.py
git commit -m "feat: add analyze_meal with vision, meal log extraction, and today's meal summary"
```

---

### Task 7: Meal Photo API Endpoint

**Files:**
- Modify: `backend/app/api/health.py`
- Test: `backend/tests/test_meal.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_meal.py`:

```python
from unittest.mock import AsyncMock, patch
import io


@pytest.mark.asyncio
async def test_meal_analyze_endpoint_rejects_no_image(client):
    """POST /health/meal/analyze returns 422 without an image."""
    response = await client.post("/api/health/meal/analyze")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_meal_analyze_endpoint_calls_analyze(client, db_session, test_user):
    """POST /health/meal/analyze calls analyze_meal and returns the answer."""
    mock_result = {"answer": "Nice meal!", "results": [], "model": "test", "count": 0}

    with patch("app.api.health.llm_analyzer.analyze_meal", new_callable=AsyncMock, return_value=mock_result):
        # Create a tiny valid PNG (1x1 pixel)
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
            b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        response = await client.post(
            "/api/health/meal/analyze",
            files={"image": ("meal.png", io.BytesIO(png_bytes), "image/png")},
            data={"message": "lunch"},
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "Nice meal!"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/backend && python -m pytest tests/test_meal.py::test_meal_analyze_endpoint_calls_analyze -v`
Expected: FAIL — 404 (route doesn't exist yet)

- [ ] **Step 3: Add the endpoint**

In `backend/app/api/health.py`, add near the top imports:

```python
import base64
from fastapi import UploadFile, File, Form
from app.services import llm_analyzer
```

Then add the endpoint after the existing `/health/sync` route:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/backend && python -m pytest tests/test_meal.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
cd C:/Users/JPPieterse/personal/GarminTracker
git add backend/app/api/health.py backend/tests/test_meal.py
git commit -m "feat: add POST /health/meal/analyze endpoint"
```

---

### Task 8: Frontend — API Client & Types

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/types.ts`

- [ ] **Step 1: Add `MealAnalysisResponse` type**

In `frontend/lib/types.ts`, the existing `AskResponse` type already matches the backend response shape (`answer`, `model`). No new type needed — we'll reuse `AskResponse`.

- [ ] **Step 2: Add `analyzeMeal` to the API client**

In `frontend/lib/api.ts`, add after the existing `syncData` function:

```typescript
export async function analyzeMeal(
  image: File,
  message?: string,
  coach?: string
): Promise<AskResponse> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const formData = new FormData();
  formData.append("image", image);
  if (message) formData.append("message", message);
  if (coach) formData.append("coach", coach);

  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch("/api/health/meal/analyze", {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const body = await res.text();
    let message = `Request failed (${res.status})`;
    try {
      const json = JSON.parse(body);
      message = json.detail || json.message || message;
    } catch {
      // use default
    }
    throw new ApiError(message, res.status);
  }

  return res.json();
}
```

Note: We do NOT set `Content-Type` header — the browser sets `multipart/form-data` with the boundary automatically when using `FormData`.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/JPPieterse/personal/GarminTracker
git add frontend/lib/api.ts
git commit -m "feat: add analyzeMeal API client function"
```

---

### Task 9: Frontend — WhatsApp Attachment UX

**Files:**
- Modify: `frontend/app/dashboard/ask/page.tsx`

- [ ] **Step 1: Add imports and state**

At the top of the file, update the lucide import:

```typescript
import { Send, Mic, MicOff, Volume2, ArrowLeft, Check, CheckCheck, Paperclip, ImageIcon, Camera, X } from "lucide-react";
```

Add the `analyzeMeal` import:

```typescript
import {
  askQuestion,
  getCoaches,
  getChatHistory,
  getOnboardingStatus,
  sendOnboardingMessage,
  analyzeMeal,
} from "@/lib/api";
```

In the `CoachChat` component, add state after existing state declarations:

```typescript
  const [pendingImage, setPendingImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const galleryInputRef = useRef<HTMLInputElement | null>(null);
  const cameraInputRef = useRef<HTMLInputElement | null>(null);
```

- [ ] **Step 2: Add image handling functions**

After `toggleListening` function, add:

```typescript
  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingImage(file);
    setImagePreview(URL.createObjectURL(file));
    setShowAttachMenu(false);
    // Reset the input so re-selecting the same file triggers onChange
    e.target.value = "";
  };

  const clearImage = () => {
    setPendingImage(null);
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImagePreview(null);
  };
```

- [ ] **Step 3: Update `handleSend` to support image uploads**

Replace the existing `handleSend` function:

```typescript
  const handleSend = async (text?: string) => {
    const msg = text || question;
    if ((!msg.trim() && !pendingImage) || loading) return;
    setQuestion("");

    // Build display text
    const displayText = pendingImage
      ? `Sent a photo${msg.trim() ? ": " + msg.trim() : ""}`
      : msg;

    const userMsg: ChatMsg = { role: "user", content: displayText, time: timeNow() };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    // Capture and clear image before async
    const imageToSend = pendingImage;
    clearImage();

    try {
      if (needsOnboarding) {
        // Onboarding flow — no image support during onboarding
        const newApiHistory = [
          ...onboardingHistory,
          { role: "user", content: msg },
        ];
        const result = await sendOnboardingMessage(msg, onboardingHistory);
        setOnboardingHistory([
          ...newApiHistory,
          { role: "assistant", content: result.reply },
        ]);
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: result.reply, time: timeNow() },
        ]);
        if (result.complete) {
          setNeedsOnboarding(false);
          setTimeout(() => {
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content: "Profile saved! From now on, I'll remember everything about you. Go ahead — ask me anything about your health data.",
                time: timeNow(),
              },
            ]);
          }, 1500);
        }
      } else if (imageToSend) {
        // Meal photo analysis
        const result = await analyzeMeal(imageToSend, msg.trim(), coach.id);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: result.answer || "I had trouble analyzing that photo. Could you try again?",
            time: timeNow(),
          },
        ]);
      } else {
        // Regular ask with coach
        const result = await askQuestion(msg.trim(), undefined, coach.id);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: result.answer || "Hmm, I couldn't find data for that. Try rephrasing?",
            time: timeNow(),
          },
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: err instanceof Error ? err.message : "Something went wrong.",
          time: timeNow(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };
```

- [ ] **Step 4: Add hidden file inputs and image preview to the JSX**

In the JSX, right before the `{/* Input bar — WhatsApp style */}` comment, add:

```tsx
      {/* Hidden file inputs */}
      <input
        ref={galleryInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleImageSelect}
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={handleImageSelect}
      />
```

Right after the opening of the input bar div (`<div className="flex items-center gap-2 px-3 py-3 border-t border-border bg-card">`), but BEFORE the mic button, add the image preview and attach button:

Replace the entire input bar section:

```tsx
      {/* Image preview */}
      {imagePreview && (
        <div className="px-3 py-2 border-t border-border bg-card">
          <div className="relative inline-block">
            <img
              src={imagePreview}
              alt="Meal preview"
              className="h-20 w-20 object-cover rounded-lg border border-border"
            />
            <button
              onClick={clearImage}
              className="absolute -top-2 -right-2 bg-dark border border-border rounded-full p-0.5 text-[#888] hover:text-red-400 transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Input bar — WhatsApp style */}
      <div className="flex items-center gap-2 px-3 py-3 border-t border-border bg-card">
        {/* Attach button */}
        <div className="relative">
          <button
            onClick={() => setShowAttachMenu(!showAttachMenu)}
            className="p-2.5 rounded-full text-[#888] hover:text-[#e0e0e0] hover:bg-border/30 transition-colors"
          >
            <Paperclip size={20} />
          </button>
          {showAttachMenu && (
            <div className="absolute bottom-12 left-0 bg-card border border-border rounded-xl shadow-lg py-2 min-w-[160px] z-10">
              <button
                onClick={() => { galleryInputRef.current?.click(); setShowAttachMenu(false); }}
                className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-[#e0e0e0] hover:bg-border/30 transition-colors"
              >
                <ImageIcon size={18} className="text-brand" />
                Gallery
              </button>
              <button
                onClick={() => { cameraInputRef.current?.click(); setShowAttachMenu(false); }}
                className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-[#e0e0e0] hover:bg-border/30 transition-colors"
              >
                <Camera size={18} className="text-[#66bb6a]" />
                Camera
              </button>
            </div>
          )}
        </div>

        <button
          onClick={toggleListening}
          className={`p-2.5 rounded-full transition-colors ${
            isListening
              ? "bg-red-500/10 text-red-400"
              : "text-[#888] hover:text-[#e0e0e0] hover:bg-border/30"
          }`}
        >
          {isListening ? <MicOff size={20} /> : <Mic size={20} />}
        </button>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder={pendingImage ? "Add a message about this meal..." : "Type a message..."}
          disabled={loading}
          className="flex-1 bg-dark border border-border rounded-full px-4 py-2.5 text-sm text-[#e0e0e0] placeholder-[#666] focus:outline-none focus:border-brand/40 transition-colors disabled:opacity-50"
        />
        <button
          onClick={() => handleSend()}
          disabled={loading || (!question.trim() && !pendingImage)}
          className="p-2.5 bg-brand rounded-full text-dark hover:bg-brand/90 transition-colors disabled:opacity-50"
        >
          <Send size={18} />
        </button>
      </div>
```

- [ ] **Step 5: Close the attach menu when clicking outside**

Add a useEffect in the CoachChat component:

```typescript
  // Close attach menu on outside click
  useEffect(() => {
    if (!showAttachMenu) return;
    const close = () => setShowAttachMenu(false);
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [showAttachMenu]);
```

Update the attach button to stop propagation:

```tsx
          <button
            onClick={(e) => { e.stopPropagation(); setShowAttachMenu(!showAttachMenu); }}
```

- [ ] **Step 6: Verify the frontend builds**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/frontend && npx next build 2>&1 | tail -10`
Expected: Build succeeds with no errors

- [ ] **Step 7: Commit**

```bash
cd C:/Users/JPPieterse/personal/GarminTracker
git add frontend/app/dashboard/ask/page.tsx
git commit -m "feat: add WhatsApp-style meal photo attachment UX"
```

---

### Task 10: Integration Test & Final Verification

**Files:**
- Test: `backend/tests/test_meal.py`

- [ ] **Step 1: Run full backend test suite**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/backend && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run frontend build**

Run: `cd C:/Users/JPPieterse/personal/GarminTracker/frontend && npx next build 2>&1 | tail -10`
Expected: Build succeeds

- [ ] **Step 3: Manual smoke test checklist**

Start both services and verify in the browser:
1. Open http://localhost:3000, navigate to coach chat
2. Verify the paperclip attach button appears to the left of the mic button
3. Click paperclip — verify Gallery and Camera options appear
4. Select a photo from Gallery — verify thumbnail preview appears above input
5. Click X on preview — verify it clears
6. Select photo again, type a message, click Send — verify "Sent a photo: message" appears in chat
7. Verify coach responds with meal analysis (requires valid Anthropic API key)
8. Ask the coach a general question — verify it references recent health data without being asked

- [ ] **Step 4: Final commit**

```bash
cd C:/Users/JPPieterse/personal/GarminTracker
git add -A
git commit -m "feat: complete meal photo analysis feature with always-on health context"
```
