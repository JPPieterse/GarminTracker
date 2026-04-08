"""User, profile, and Garmin credential models."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserRole(str, enum.Enum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    auth_provider: Mapped[str] = mapped_column(String(64))
    auth_subject: Mapped[str] = mapped_column(String(256))
    role: Mapped[UserRole] = mapped_column(default=UserRole.PATIENT)

    # Relationships
    garmin_credential: Mapped[GarminCredential | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    profile: Mapped[UserProfile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class UserProfile(UUIDMixin, TimestampMixin, Base):
    """Persistent user profile — free-form context the AI always has access to.

    This is the user's personal context document. They can write anything here
    in natural language: goals, training habits, injuries, diet, personal
    records, what they're working towards, etc. The entire contents get
    injected into every AI query as context.
    """
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    # One big free-form document — the user writes this in natural language
    context: Mapped[str] = mapped_column(Text, default="")

    # IANA timezone string, e.g. "Africa/Johannesburg"
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped[User] = relationship(back_populates="profile")


class GarminCredential(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "garmin_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    encrypted_email: Mapped[str] = mapped_column(Text)
    encrypted_password: Mapped[str] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="garmin_credential")
