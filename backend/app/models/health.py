"""Health data models: daily stats, activities, sleep, heart rate, sync log."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class DailyStat(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "daily_stats"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_daily_stat_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)


class Activity(TimestampMixin, Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    activity_type: Mapped[str] = mapped_column(String(128), default="")
    data: Mapped[dict] = mapped_column(JSONB, default=dict)


class SleepRecord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sleep_records"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_sleep_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)


class HeartRateRecord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "heart_rate_records"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_hr_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)


class SyncStatus(str, enum.Enum):
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class SyncLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sync_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[SyncStatus] = mapped_column(default=SyncStatus.STARTED)
    records_synced: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
