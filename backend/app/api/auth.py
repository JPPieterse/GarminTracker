"""Auth endpoints: Google OAuth login/callback, user profile, Garmin credential management."""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    encrypt_value,
    exchange_google_code,
    get_current_user,
    get_google_userinfo,
)
from app.models.user import GarminCredential, User, UserProfile, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


# ── Google OAuth flow ──────────────────────────────────────────────────────


@router.get("/google/login")
async def google_login(request: Request):
    """Redirect the user to Google's OAuth consent screen."""
    if not settings.GOOGLE_CLIENT_ID:
        # Dev mode — issue a dev token and redirect straight to dashboard
        token = create_access_token("dev|local", "dev@localhost", "Dev User")
        return RedirectResponse(f"http://localhost:3000/callback?token={token}")

    redirect_uri = str(request.url_for("google_callback"))
    params = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    })
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Google's OAuth callback — exchange code, create/find user, issue JWT."""
    redirect_uri = str(request.url_for("google_callback"))

    # Exchange authorization code for tokens
    tokens = await exchange_google_code(code, redirect_uri)
    google_access_token = tokens["access_token"]

    # Get user info from Google
    userinfo = await get_google_userinfo(google_access_token)
    google_id = userinfo["id"]
    email = userinfo.get("email", "")
    name = userinfo.get("name", "")

    # Find or create user
    stmt = select(User).where(User.auth_provider == "google", User.auth_subject == google_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=email,
            name=name,
            auth_provider="google",
            auth_subject=google_id,
            role=UserRole.PATIENT,
        )
        db.add(user)
        await db.flush()
    else:
        # Update name/email in case they changed on Google's side
        user.email = email
        user.name = name
        await db.flush()

    # Issue our own JWT
    token = create_access_token(str(user.id), user.email, user.name)

    # Redirect to frontend with token
    frontend_url = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "http://localhost:3000"
    return RedirectResponse(f"{frontend_url}/callback?token={token}")


# ── Auth config (tells frontend whether Google is configured) ───────────────


@router.get("/config")
async def get_auth_config():
    """Return auth configuration for the frontend."""
    return {
        "configured": bool(settings.GOOGLE_CLIENT_ID),
        "provider": "google",
    }


# ── User profile ────────────────────────────────────────────────────────────


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


# ── Garmin credential management ───────────────────────────────────────────


@router.post("/garmin/connect")
async def connect_garmin(
    body: GarminConnectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store encrypted Garmin credentials for the authenticated user."""
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


# ── Health Profile (persistent AI context) ─────────────────────────────────


class ProfileUpdate(BaseModel):
    context: str = ""


@router.get("/profile")
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the user's health profile context."""
    stmt = select(UserProfile).where(UserProfile.user_id == user.id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    return {"context": profile.context if profile else ""}


@router.put("/profile")
async def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update the user's health profile context."""
    stmt = select(UserProfile).where(UserProfile.user_id == user.id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    profile.context = body.context
    await db.flush()
    return {"status": "updated"}
