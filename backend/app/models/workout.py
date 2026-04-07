"""Workout program, session, and set tracking models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class WorkoutProgram(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workout_programs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    coach_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(256), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    program_data: Mapped[dict] = mapped_column(JSON, default=dict)

    sessions: Mapped[list[WorkoutSession]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )


class WorkoutSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workout_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_programs.id", ondelete="CASCADE"), index=True
    )
    day_id: Mapped[str] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    coach_debrief: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    program: Mapped[WorkoutProgram] = relationship(back_populates="sessions")
    sets: Mapped[list[WorkoutSet]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class WorkoutSet(UUIDMixin, Base):
    __tablename__ = "workout_sets"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[str] = mapped_column(String(128))
    set_number: Mapped[int] = mapped_column(Integer)
    weight_kg: Mapped[float] = mapped_column(Float)
    reps: Mapped[int] = mapped_column(Integer)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(__import__("datetime").timezone.utc),
    )

    session: Mapped[WorkoutSession] = relationship(back_populates="sets")
