"""Google OAuth2 verification, JWT signing, dev-mode bypass, role enforcement, Fernet encryption."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)

# ── JWT helpers (sign our own tokens after Google login) ────────────────────

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24 * 7  # 1 week


def create_access_token(user_id: str, email: str, name: str) -> str:
    """Create a signed JWT for an authenticated user."""
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify one of our JWTs."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ── Google OAuth2 helpers ──────────────────────────────────────────────────

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


async def exchange_google_code(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange an authorization code for Google tokens."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail=f"Google token exchange failed: {resp.text}")
        return resp.json()


async def get_google_userinfo(access_token: str) -> dict[str, Any]:
    """Fetch user profile from Google using an access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Failed to fetch Google user info")
        return resp.json()


# ── Fernet helpers ───────────────────────────────────────────────────────────

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not settings.ENCRYPTION_KEY:
            raise RuntimeError("ENCRYPTION_KEY not set")
        _fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string and return the Fernet token as a string."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a Fernet token back to plaintext."""
    return _get_fernet().decrypt(token.encode()).decode()


# ── Dev user (when GOOGLE_CLIENT_ID is empty) ────────────────────────────────

_DEV_USER_PAYLOAD = {
    "sub": "dev|local",
    "email": "dev@localhost",
    "name": "Dev User",
}


# ── Token verification ──────────────────────────────────────────────────────

async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate our JWT, auto-provision user on first login, return User ORM object."""
    if not settings.GOOGLE_CLIENT_ID:
        # Dev mode — return or create dev user
        payload = _DEV_USER_PAYLOAD
    else:
        if creds is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            payload = decode_access_token(creds.credentials)
        except JWTError as exc:
            raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

    sub = payload["sub"]

    if sub == "dev|local":
        # Dev mode — find or create dev user by auth_subject
        stmt = select(User).where(User.auth_subject == sub)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                email=payload.get("email", ""),
                name=payload.get("name", ""),
                auth_provider="dev",
                auth_subject=sub,
                role=UserRole.PATIENT,
            )
            db.add(user)
            await db.flush()
    else:
        # Production — sub is the user's database UUID
        import uuid as _uuid
        stmt = select(User).where(User.id == _uuid.UUID(sub))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

    return user


# ── Role enforcement ─────────────────────────────────────────────────────────

def require_role(*roles: UserRole):
    """Return a FastAPI dependency that asserts the user has one of the given roles."""

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(r.value for r in roles)}",
            )
        return user

    return _check
