"""Auth endpoints: current user info, config, Garmin credential management."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import encrypt_value, get_current_user
from app.models.user import GarminCredential, User

router = APIRouter(prefix="/auth", tags=["auth"])


class GarminConnectRequest(BaseModel):
    email: str
    password: str


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role.value,
    }


@router.get("/config")
async def get_auth_config():
    """Return Auth0 configuration for the frontend."""
    return {
        "domain": settings.AUTH0_DOMAIN,
        "client_id": settings.AUTH0_CLIENT_ID,
        "audience": settings.AUTH0_AUDIENCE,
    }


@router.post("/garmin/connect")
async def connect_garmin(
    body: GarminConnectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store encrypted Garmin credentials for the authenticated user."""
    # Remove existing
    await db.execute(delete(GarminCredential).where(GarminCredential.user_id == user.id))

    cred = GarminCredential(
        user_id=user.id,
        encrypted_email=encrypt_value(body.email),
        encrypted_password=encrypt_value(body.password),
    )
    db.add(cred)
    await db.flush()
    return {"status": "connected"}


@router.post("/garmin/disconnect")
async def disconnect_garmin(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove stored Garmin credentials."""
    await db.execute(delete(GarminCredential).where(GarminCredential.user_id == user.id))
    return {"status": "disconnected"}
