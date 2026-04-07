"""Doctor-patient sharing, medical records, annotations, audit log."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class LinkStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class DoctorPatientLink(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "doctor_patient_links"

    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[LinkStatus] = mapped_column(default=LinkStatus.PENDING)
    invite_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)


class MedicalRecord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "medical_records"

    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text, default="")
    file_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class DoctorAnnotation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "doctor_annotations"

    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AuditAction(str, enum.Enum):
    VIEW_DATA = "VIEW_DATA"
    ADD_ANNOTATION = "ADD_ANNOTATION"
    ADD_RECORD = "ADD_RECORD"
    ACCEPT_INVITE = "ACCEPT_INVITE"
    REVOKE_LINK = "REVOKE_LINK"


class AuditLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    action: Mapped[AuditAction]
    detail: Mapped[str] = mapped_column(Text, default="")
