"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All configuration is pulled from environment variables / .env file."""

    # ── General ──────────────────────────────────────────────
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/garmintracker"

    # ── Auth0 ────────────────────────────────────────────────
    AUTH0_DOMAIN: str = ""
    AUTH0_CLIENT_ID: str = ""
    AUTH0_CLIENT_SECRET: str = ""
    AUTH0_AUDIENCE: str = ""

    # ── Encryption (Fernet key for PII) ──────────────────────
    ENCRYPTION_KEY: str = ""

    # ── Garmin (default / legacy single-user) ────────────────
    GARMIN_EMAIL: str = ""
    GARMIN_PASSWORD: str = ""

    # ── AI / LLM ─────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # ── Stripe ───────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_PRO: str = ""
    STRIPE_PRICE_DOCTOR: str = ""

    # ── Cloudflare R2 (S3-compatible) ────────────────────────
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "garmintracker"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
