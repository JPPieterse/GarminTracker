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


@pytest.mark.asyncio
async def test_handle_meal_log_extracts_json(db_session, test_user):
    """_handle_meal_log extracts structured data from response and saves MealLog."""
    from app.services.llm_analyzer import _handle_meal_log
    from app.models.meal import MealLog, MealType
    from sqlalchemy import select

    response_text = '''That looks like a solid post-workout meal! I can see grilled chicken breast with brown rice and steamed broccoli.

[MEAL_LOG]
```json
{"calories": 650, "protein_g": 42, "carbs_g": 55, "fat_g": 22, "fiber_g": 8, "sodium_mg": 480, "ingredients": "grilled chicken breast ~180g, brown rice ~1 cup, steamed broccoli ~1 cup, olive oil drizzle", "confidence": "HIGH"}
```

Great choice for recovery — that's about 42g of protein which is right in the sweet spot after a workout.'''

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
