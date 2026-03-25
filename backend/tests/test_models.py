"""Tests for SQLAlchemy model creation."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Subscription, SubscriptionTier
from app.models.chat import ChatMessage, ChatRole
from app.models.health import DailyStat
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    user = User(
        email="model@test.com",
        name="Model Test",
        auth_provider="test",
        auth_subject="123",
        role=UserRole.PATIENT,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None
    assert user.email == "model@test.com"


@pytest.mark.asyncio
async def test_create_daily_stat(db_session: AsyncSession, test_user: User):
    stat = DailyStat(
        user_id=test_user.id,
        date=date(2026, 3, 25),
        data={"totalSteps": 10000, "restingHeartRate": 62},
    )
    db_session.add(stat)
    await db_session.commit()
    await db_session.refresh(stat)
    assert stat.data["totalSteps"] == 10000


@pytest.mark.asyncio
async def test_create_subscription(db_session: AsyncSession, test_user: User):
    sub = Subscription(user_id=test_user.id, tier=SubscriptionTier.PRO, active=True)
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    assert sub.tier == SubscriptionTier.PRO


@pytest.mark.asyncio
async def test_create_chat_message(db_session: AsyncSession, test_user: User):
    msg = ChatMessage(
        user_id=test_user.id,
        role=ChatRole.USER,
        content="How many steps did I walk today?",
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)
    assert msg.role == ChatRole.USER
    assert msg.sql_query is None
