"""Patient-facing sharing endpoints: view links, accept invites, revoke."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.sharing import DoctorPatientLink, LinkStatus
from app.models.user import User
from app.services import sharing

router = APIRouter(prefix="/sharing", tags=["sharing"])


@router.get("/links")
async def list_links(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all sharing links for the current user (as patient or doctor)."""
    stmt = select(DoctorPatientLink).where(
        (DoctorPatientLink.patient_id == user.id) | (DoctorPatientLink.doctor_id == user.id)
    ).order_by(DoctorPatientLink.created_at.desc())
    result = await db.execute(stmt)
    return [
        {
            "id": str(link.id),
            "doctor_id": str(link.doctor_id),
            "patient_id": str(link.patient_id),
            "status": link.status.value,
            "created_at": link.created_at.isoformat(),
        }
        for link in result.scalars()
    ]


@router.post("/accept/{link_id}")
async def accept_link(
    link_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept a pending sharing invite."""
    link = await sharing.accept_invite(db, user.id, link_id)
    return {"id": str(link.id), "status": link.status.value}


@router.post("/revoke/{link_id}")
async def revoke_link(
    link_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a sharing link."""
    link = await sharing.revoke_link(db, user.id, link_id)
    return {"id": str(link.id), "status": link.status.value}
