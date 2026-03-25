"""Doctor portal endpoints: patients list, patient data, annotations, records."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.health import DailyStat, Activity, SleepRecord, HeartRateRecord
from app.models.sharing import AuditAction, AuditLog, DoctorAnnotation, MedicalRecord
from app.models.user import User, UserRole
from app.services.sharing import (
    add_annotation,
    create_invite,
    get_doctor_patients,
    verify_doctor_patient_link,
)
from app.services.storage import upload_file

router = APIRouter(prefix="/doctor", tags=["doctor"])


class InviteRequest(BaseModel):
    patient_email: str


class AnnotationRequest(BaseModel):
    content: str
    metadata_json: dict | None = None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/patients")
async def list_patients(
    doctor: User = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    """List all patients linked to this doctor."""
    return await get_doctor_patients(db, doctor.id)


@router.post("/invite")
async def invite_patient(
    body: InviteRequest,
    doctor: User = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    """Send a sharing invite to a patient."""
    link = await create_invite(db, doctor.id, body.patient_email)
    return {"link_id": str(link.id), "invite_code": link.invite_code, "status": link.status.value}


@router.get("/patients/{patient_id}/data")
async def get_patient_data(
    patient_id: uuid.UUID,
    doctor: User = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    """View a linked patient's health data (with audit)."""
    await verify_doctor_patient_link(db, doctor.id, patient_id)

    # Audit the access
    db.add(AuditLog(actor_id=doctor.id, patient_id=patient_id, action=AuditAction.VIEW_DATA))
    await db.flush()

    # Fetch recent data
    stats_stmt = select(DailyStat).where(DailyStat.user_id == patient_id).order_by(DailyStat.date.desc()).limit(30)
    activities_stmt = select(Activity).where(Activity.user_id == patient_id).order_by(Activity.date.desc()).limit(20)
    sleep_stmt = select(SleepRecord).where(SleepRecord.user_id == patient_id).order_by(SleepRecord.date.desc()).limit(14)
    hr_stmt = select(HeartRateRecord).where(HeartRateRecord.user_id == patient_id).order_by(HeartRateRecord.date.desc()).limit(14)

    stats_result = await db.execute(stats_stmt)
    activities_result = await db.execute(activities_stmt)
    sleep_result = await db.execute(sleep_stmt)
    hr_result = await db.execute(hr_stmt)

    return {
        "daily_stats": [{"date": r.date.isoformat(), "data": r.data} for r in stats_result.scalars()],
        "activities": [{"id": r.id, "date": r.date.isoformat(), "type": r.activity_type, "data": r.data} for r in activities_result.scalars()],
        "sleep": [{"date": r.date.isoformat(), "data": r.data} for r in sleep_result.scalars()],
        "heart_rate": [{"date": r.date.isoformat(), "data": r.data} for r in hr_result.scalars()],
    }


@router.post("/patients/{patient_id}/annotations")
async def create_annotation(
    patient_id: uuid.UUID,
    body: AnnotationRequest,
    doctor: User = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    """Add an annotation to a patient's record."""
    ann = await add_annotation(db, doctor.id, patient_id, body.content, body.metadata_json)
    return {"id": str(ann.id), "content": ann.content}


@router.post("/patients/{patient_id}/records")
async def upload_medical_record(
    patient_id: uuid.UUID,
    title: str = Form(...),
    file: UploadFile = File(...),
    doctor: User = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    """Upload a medical record for a patient."""
    await verify_doctor_patient_link(db, doctor.id, patient_id)

    contents = await file.read()
    file_key = await upload_file(contents, file.filename or "document", file.content_type or "application/octet-stream", prefix=f"records/{patient_id}")

    record = MedicalRecord(
        patient_id=patient_id,
        doctor_id=doctor.id,
        title=title,
        file_key=file_key,
    )
    db.add(record)
    db.add(AuditLog(actor_id=doctor.id, patient_id=patient_id, action=AuditAction.ADD_RECORD, detail=title))
    await db.flush()
    return {"id": str(record.id), "title": record.title, "file_key": record.file_key}


@router.get("/patients/{patient_id}/records")
async def list_medical_records(
    patient_id: uuid.UUID,
    doctor: User = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    """List medical records for a patient."""
    await verify_doctor_patient_link(db, doctor.id, patient_id)

    stmt = select(MedicalRecord).where(
        MedicalRecord.patient_id == patient_id,
        MedicalRecord.doctor_id == doctor.id,
    ).order_by(MedicalRecord.created_at.desc())
    result = await db.execute(stmt)
    return [
        {"id": str(r.id), "title": r.title, "file_key": r.file_key, "created_at": r.created_at.isoformat()}
        for r in result.scalars()
    ]
