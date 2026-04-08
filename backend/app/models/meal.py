"""Meal logging model — stores nutrition data extracted from photo analysis."""

from __future__ import annotations

import enum
import uuid
from datetime import date, time

from sqlalchemy import Date, Enum, Float, ForeignKey, Integer, String, Text, Time
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
    meal_type: Mapped[MealType] = mapped_column(Enum(MealType, native_enum=False))
    calories: Mapped[int] = mapped_column(Integer)
    protein_g: Mapped[float] = mapped_column(Float)
    carbs_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    fiber_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    sodium_mg: Mapped[float | None] = mapped_column(Float, nullable=True)
    ingredients: Mapped[str] = mapped_column(Text)
    confidence: Mapped[MealConfidence] = mapped_column(Enum(MealConfidence, native_enum=False))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    hydration_ml: Mapped[int | None] = mapped_column(Integer, nullable=True)
