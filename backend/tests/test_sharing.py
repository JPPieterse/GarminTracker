"""Tests for doctor-patient sharing service."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sharing import LinkStatus
from app.models.user import User
from app.services.sharing import accept_invite, create_invite, get_doctor_patients, revoke_link


@pytest.mark.asyncio
async def test_create_and_accept_invite(db_session: AsyncSession, doctor_user: User, test_user: User):
    link = await create_invite(db_session, doctor_user.id, test_user.email)
    await db_session.commit()
    assert link.status == LinkStatus.PENDING

    link = await accept_invite(db_session, test_user.id, link.id)
    await db_session.commit()
    assert link.status == LinkStatus.ACTIVE


@pytest.mark.asyncio
async def test_get_doctor_patients(db_session: AsyncSession, doctor_user: User, test_user: User):
    link = await create_invite(db_session, doctor_user.id, test_user.email)
    await accept_invite(db_session, test_user.id, link.id)
    await db_session.commit()

    patients = await get_doctor_patients(db_session, doctor_user.id)
    assert len(patients) == 1
    assert patients[0]["patient_email"] == test_user.email


@pytest.mark.asyncio
async def test_revoke_link(db_session: AsyncSession, doctor_user: User, test_user: User):
    link = await create_invite(db_session, doctor_user.id, test_user.email)
    await accept_invite(db_session, test_user.id, link.id)
    await db_session.commit()

    link = await revoke_link(db_session, doctor_user.id, link.id)
    await db_session.commit()
    assert link.status == LinkStatus.REVOKED


@pytest.mark.asyncio
async def test_duplicate_invite_rejected(db_session: AsyncSession, doctor_user: User, test_user: User):
    await create_invite(db_session, doctor_user.id, test_user.email)
    await db_session.commit()

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await create_invite(db_session, doctor_user.id, test_user.email)
    assert exc_info.value.status_code == 409
