"""Doctor-patient sharing service with audit logging."""

from __future__ import annotations

import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sharing import (
    AuditAction,
    AuditLog,
    DoctorAnnotation,
    DoctorPatientLink,
    LinkStatus,
)
from app.models.user import User


def _audit(actor_id: uuid.UUID, patient_id: uuid.UUID, action: AuditAction, detail: str = "") -> AuditLog:
    return AuditLog(actor_id=actor_id, patient_id=patient_id, action=action, detail=detail)


async def create_invite(db: AsyncSession, doctor_id: uuid.UUID, patient_email: str) -> DoctorPatientLink:
    """Doctor creates an invite for a patient by email."""
    stmt = select(User).where(User.email == patient_email)
    result = await db.execute(stmt)
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Check for existing active link
    stmt = select(DoctorPatientLink).where(
        DoctorPatientLink.doctor_id == doctor_id,
        DoctorPatientLink.patient_id == patient.id,
        DoctorPatientLink.status.in_([LinkStatus.PENDING, LinkStatus.ACTIVE]),
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Link already exists")

    link = DoctorPatientLink(
        doctor_id=doctor_id,
        patient_id=patient.id,
        status=LinkStatus.PENDING,
        invite_code=secrets.token_urlsafe(32),
    )
    db.add(link)
    await db.flush()
    return link


async def accept_invite(db: AsyncSession, user_id: uuid.UUID, link_id: uuid.UUID) -> DoctorPatientLink:
    """Patient accepts a pending invite."""
    stmt = select(DoctorPatientLink).where(
        DoctorPatientLink.id == link_id,
        DoctorPatientLink.patient_id == user_id,
        DoctorPatientLink.status == LinkStatus.PENDING,
    )
    result = await db.execute(stmt)
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Invite not found")

    link.status = LinkStatus.ACTIVE
    db.add(_audit(user_id, user_id, AuditAction.ACCEPT_INVITE, f"link={link.id}"))
    await db.flush()
    return link


async def revoke_link(db: AsyncSession, user_id: uuid.UUID, link_id: uuid.UUID) -> DoctorPatientLink:
    """Either party can revoke an active or pending link."""
    stmt = select(DoctorPatientLink).where(
        DoctorPatientLink.id == link_id,
        DoctorPatientLink.status.in_([LinkStatus.PENDING, LinkStatus.ACTIVE]),
        (DoctorPatientLink.doctor_id == user_id) | (DoctorPatientLink.patient_id == user_id),
    )
    result = await db.execute(stmt)
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    link.status = LinkStatus.REVOKED
    db.add(_audit(user_id, link.patient_id, AuditAction.REVOKE_LINK, f"link={link.id}"))
    await db.flush()
    return link


async def get_doctor_patients(db: AsyncSession, doctor_id: uuid.UUID) -> list[dict]:
    """List all active patients for a doctor."""
    stmt = (
        select(DoctorPatientLink, User)
        .join(User, User.id == DoctorPatientLink.patient_id)
        .where(
            DoctorPatientLink.doctor_id == doctor_id,
            DoctorPatientLink.status == LinkStatus.ACTIVE,
        )
    )
    result = await db.execute(stmt)
    return [
        {
            "link_id": str(link.id),
            "patient_id": str(user.id),
            "patient_name": user.name,
            "patient_email": user.email,
            "linked_at": link.created_at.isoformat(),
        }
        for link, user in result.all()
    ]


async def verify_doctor_patient_link(
    db: AsyncSession, doctor_id: uuid.UUID, patient_id: uuid.UUID
) -> DoctorPatientLink:
    """Verify an active link exists between doctor and patient, raise 403 otherwise."""
    stmt = select(DoctorPatientLink).where(
        and_(
            DoctorPatientLink.doctor_id == doctor_id,
            DoctorPatientLink.patient_id == patient_id,
            DoctorPatientLink.status == LinkStatus.ACTIVE,
        )
    )
    result = await db.execute(stmt)
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=403, detail="No active link with this patient")
    return link


async def add_annotation(
    db: AsyncSession,
    doctor_id: uuid.UUID,
    patient_id: uuid.UUID,
    content: str,
    metadata_json: dict | None = None,
) -> DoctorAnnotation:
    """Add a doctor annotation for a patient (with audit)."""
    await verify_doctor_patient_link(db, doctor_id, patient_id)

    annotation = DoctorAnnotation(
        doctor_id=doctor_id,
        patient_id=patient_id,
        content=content,
        metadata_json=metadata_json,
    )
    db.add(annotation)
    db.add(_audit(doctor_id, patient_id, AuditAction.ADD_ANNOTATION))
    await db.flush()
    return annotation
