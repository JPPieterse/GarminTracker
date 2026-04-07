"""Extended Garmin data models — HRV, training readiness, body composition, stress detail, performance."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class HrvRecord(UUIDMixin, TimestampMixin, Base):
    """Heart rate variability data — key recovery and readiness indicator."""
    __tablename__ = "hrv_records"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_hrv_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class TrainingReadinessRecord(UUIDMixin, TimestampMixin, Base):
    """Training readiness + training status — daily readiness score and training state."""
    __tablename__ = "training_readiness_records"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_readiness_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class BodyCompositionRecord(UUIDMixin, TimestampMixin, Base):
    """Body composition — weight, body fat %, muscle mass, BMI, etc."""
    __tablename__ = "body_composition_records"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_bodycomp_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class StressDetailRecord(UUIDMixin, TimestampMixin, Base):
    """Detailed stress timeline + body battery events for a day."""
    __tablename__ = "stress_detail_records"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_stress_detail_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class PerformanceMetric(UUIDMixin, TimestampMixin, Base):
    """Performance metrics — VO2 max, race predictions, fitness age, endurance score."""
    __tablename__ = "performance_metrics"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_perf_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
