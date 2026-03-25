"""Auth0 JWT validation, dev-mode bypass, role enforcement, Fernet encryption."""

from __future__ import annotations

import functools
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

# ── JWKS cache ───────────────────────────────────────────────────────────────

_jwks_cache: dict[str, Any] | None = None


async def _get_jwks() -> dict[str, Any]:
    global _jwks_cache
    if _jwks_cache is None:
        url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            resp.raise_for_status()
            _jwks_cache = resp.json()
    return _jwks_cache


def _find_rsa_key(jwks: dict[str, Any], kid: str) -> dict[str, str] | None:
    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            return {k: key[k] for k in ("kty", "kid", "use", "n", "e")}
    return None


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


# ── Dev user (when AUTH0_DOMAIN is empty) ────────────────────────────────────

_DEV_USER_PAYLOAD = {
    "sub": "dev|local",
    "email": "dev@localhost",
    "name": "Dev User",
}


# ── Token verification ──────────────────────────────────────────────────────

async def _verify_token(token: str) -> dict[str, Any]:
    """Verify an Auth0 JWT and return the decoded payload."""
    if not settings.AUTH0_DOMAIN:
        # Dev mode — accept any token or none
        return _DEV_USER_PAYLOAD

    jwks = await _get_jwks()
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token header") from exc

    rsa_key = _find_rsa_key(jwks, unverified_header.get("kid", ""))
    if rsa_key is None:
        raise HTTPException(status_code=401, detail="Unable to find signing key")

    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.AUTH0_AUDIENCE,
            issuer=f"https://{settings.AUTH0_DOMAIN}/",
        )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return payload


# ── Auto-provision + current user dependency ─────────────────────────────────

async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate JWT, auto-provision user on first login, return User ORM object."""
    if not settings.AUTH0_DOMAIN:
        # Dev mode — return or create dev user
        payload = _DEV_USER_PAYLOAD
        token_str = ""
    else:
        if creds is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        token_str = creds.credentials  # noqa: F841
        payload = await _verify_token(creds.credentials)

    sub = payload["sub"]
    provider, _, subject = sub.partition("|")

    stmt = select(User).where(User.auth_provider == provider, User.auth_subject == subject)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=payload.get("email", ""),
            name=payload.get("name", ""),
            auth_provider=provider,
            auth_subject=subject,
            role=UserRole.PATIENT,
        )
        db.add(user)
        await db.flush()

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
