"""Tests for usage tracking service."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import UsageType
from app.models.user import User
from app.services.usage import check_ai_quota, get_usage_stats, track_usage


@pytest.mark.asyncio
async def test_track_usage(db_session: AsyncSession, test_user: User):
    record = await track_usage(db_session, test_user.id, UsageType.SYNC)
    await db_session.commit()
    assert record.usage_type == UsageType.SYNC
    assert record.count == 1


@pytest.mark.asyncio
async def test_ai_quota_free_tier(db_session: AsyncSession, test_user: User):
    # Should start with quota available
    assert await check_ai_quota(db_session, test_user.id) is True

    # Use up all 5 free queries
    for _ in range(5):
        await track_usage(db_session, test_user.id, UsageType.AI_QUERY)
    await db_session.commit()

    assert await check_ai_quota(db_session, test_user.id) is False


@pytest.mark.asyncio
async def test_usage_stats(db_session: AsyncSession, test_user: User):
    await track_usage(db_session, test_user.id, UsageType.AI_QUERY)
    await track_usage(db_session, test_user.id, UsageType.SYNC)
    await db_session.commit()

    stats = await get_usage_stats(db_session, test_user.id)
    assert stats["tier"] == "FREE"
    assert stats["ai_query"] == 1
    assert stats["sync"] == 1
    assert stats["ai_query_limit"] == 5
    assert stats["ai_queries_remaining"] == 4
