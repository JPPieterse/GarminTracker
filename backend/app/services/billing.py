"""Stripe billing: checkout sessions, webhook processing, subscription management."""

from __future__ import annotations

import uuid

import stripe
import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import Subscription, SubscriptionTier

logger = structlog.get_logger()

stripe.api_key = settings.STRIPE_SECRET_KEY

PRICE_TO_TIER: dict[str, SubscriptionTier] = {}
if settings.STRIPE_PRICE_PRO:
    PRICE_TO_TIER[settings.STRIPE_PRICE_PRO] = SubscriptionTier.PRO
if settings.STRIPE_PRICE_DOCTOR:
    PRICE_TO_TIER[settings.STRIPE_PRICE_DOCTOR] = SubscriptionTier.DOCTOR


async def _get_or_create_subscription(db: AsyncSession, user_id: uuid.UUID) -> Subscription:
    stmt = select(Subscription).where(Subscription.user_id == user_id)
    result = await db.execute(stmt)
    sub = result.scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user_id, tier=SubscriptionTier.FREE)
        db.add(sub)
        await db.flush()
    return sub


async def create_checkout_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout Session and return its URL."""
    sub = await _get_or_create_subscription(db, user_id)

    params: dict = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"user_id": str(user_id)},
    }
    if sub.stripe_customer_id:
        params["customer"] = sub.stripe_customer_id

    session = stripe.checkout.Session.create(**params)
    return session.url


async def handle_webhook_event(db: AsyncSession, event: dict) -> None:
    """Process a Stripe webhook event."""
    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        user_id = uuid.UUID(data["metadata"]["user_id"])
        sub = await _get_or_create_subscription(db, user_id)
        sub.stripe_customer_id = data.get("customer")

        # Retrieve subscription to find the price
        stripe_sub = stripe.Subscription.retrieve(data["subscription"])
        price_id = stripe_sub["items"]["data"][0]["price"]["id"]
        sub.tier = PRICE_TO_TIER.get(price_id, SubscriptionTier.PRO)
        sub.stripe_subscription_id = data["subscription"]
        sub.active = True

    elif event_type == "customer.subscription.deleted":
        stripe_sub_id = data["id"]
        stmt = select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
        result = await db.execute(stmt)
        sub = result.scalar_one_or_none()
        if sub:
            sub.active = False
            sub.tier = SubscriptionTier.FREE

    elif event_type == "customer.subscription.updated":
        stripe_sub_id = data["id"]
        stmt = select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
        result = await db.execute(stmt)
        sub = result.scalar_one_or_none()
        if sub:
            price_id = data["items"]["data"][0]["price"]["id"]
            sub.tier = PRICE_TO_TIER.get(price_id, sub.tier)
            sub.active = data["status"] == "active"


async def get_subscription(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Get the user's current subscription info."""
    sub = await _get_or_create_subscription(db, user_id)
    return {
        "tier": sub.tier.value,
        "active": sub.active,
        "stripe_customer_id": sub.stripe_customer_id,
        "stripe_subscription_id": sub.stripe_subscription_id,
    }


async def cancel_subscription(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Cancel the user's Stripe subscription."""
    sub = await _get_or_create_subscription(db, user_id)
    if not sub.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription to cancel")

    stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)
    return {"status": "cancelling_at_period_end"}
