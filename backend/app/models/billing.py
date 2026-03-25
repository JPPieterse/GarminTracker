"""Subscription tiers and usage tracking."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class SubscriptionTier(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"
    PRO_DOCTOR = "PRO_DOCTOR"
    DOCTOR = "DOCTOR"


class Subscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    tier: Mapped[SubscriptionTier] = mapped_column(default=SubscriptionTier.FREE)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    active: Mapped[bool] = mapped_column(default=True)


class UsageType(str, enum.Enum):
    AI_QUERY = "AI_QUERY"
    SYNC = "SYNC"
    UPLOAD = "UPLOAD"


class UsageRecord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "usage_records"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    usage_type: Mapped[UsageType]
    count: Mapped[int] = mapped_column(Integer, default=1)
