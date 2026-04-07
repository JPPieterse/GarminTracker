"""Usage tracking and AI quota enforcement."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Subscription, SubscriptionTier, UsageRecord, UsageType

FREE_AI_QUERIES_PER_MONTH = 100


async def track_usage(
    db: AsyncSession,
    user_id: uuid.UUID,
    usage_type: UsageType,
    count: int = 1,
) -> UsageRecord:
    """Record a usage event."""
    record = UsageRecord(user_id=user_id, usage_type=usage_type, count=count)
    db.add(record)
    await db.flush()
    return record


async def _get_subscription_tier(db: AsyncSession, user_id: uuid.UUID) -> SubscriptionTier:
    stmt = select(Subscription).where(Subscription.user_id == user_id, Subscription.active.is_(True))
    result = await db.execute(stmt)
    sub = result.scalar_one_or_none()
    return sub.tier if sub else SubscriptionTier.FREE


async def _count_ai_queries_this_month(db: AsyncSession, user_id: uuid.UUID) -> int:
    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stmt = (
        select(func.coalesce(func.sum(UsageRecord.count), 0))
        .where(
            UsageRecord.user_id == user_id,
            UsageRecord.usage_type == UsageType.AI_QUERY,
            UsageRecord.created_at >= start_of_month,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one()


async def check_ai_quota(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Return True if the user can make another AI query."""
    tier = await _get_subscription_tier(db, user_id)
    if tier != SubscriptionTier.FREE:
        return True
    used = await _count_ai_queries_this_month(db, user_id)
    return used < FREE_AI_QUERIES_PER_MONTH


async def get_usage_stats(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Return usage breakdown for the current month."""
    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    tier = await _get_subscription_tier(db, user_id)

    stats: dict = {"tier": tier.value, "period_start": start_of_month.isoformat()}
    for ut in UsageType:
        stmt = (
            select(func.coalesce(func.sum(UsageRecord.count), 0))
            .where(
                UsageRecord.user_id == user_id,
                UsageRecord.usage_type == ut,
                UsageRecord.created_at >= start_of_month,
            )
        )
        result = await db.execute(stmt)
        stats[ut.value.lower()] = result.scalar_one()

    if tier == SubscriptionTier.FREE:
        stats["ai_query_limit"] = FREE_AI_QUERIES_PER_MONTH
        stats["ai_queries_remaining"] = max(0, FREE_AI_QUERIES_PER_MONTH - stats["ai_query"])

    return stats
