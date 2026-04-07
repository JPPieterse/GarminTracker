"""FastAPI application factory."""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.middleware import SecurityHeadersMiddleware, limiter


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

    app = FastAPI(
        title="ZEV API",
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # ── Middleware (order matters — outermost first) ──────────────────────
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Rate limiter ─────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── Routers ──────────────────────────────────────────────────────────
    from app.api.auth import router as auth_router
    from app.api.billing import router as billing_router
    from app.api.doctor import router as doctor_router
    from app.api.health import router as health_router
    from app.api.sharing import router as sharing_router
    from app.api.voice import router as voice_router

    app.include_router(auth_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(doctor_router, prefix="/api")
    app.include_router(billing_router, prefix="/api")
    app.include_router(voice_router, prefix="/api")
    app.include_router(sharing_router, prefix="/api")

    @app.get("/api/ping")
    async def ping():
        return {"status": "ok"}

    @app.on_event("startup")
    async def _create_tables():
        """Auto-create tables for SQLite dev mode. Use Alembic in production."""
        from app.core.database import engine
        from app.models.base import Base

        # Import all models so they register with Base.metadata
        import app.models.user  # noqa: F401
        import app.models.health  # noqa: F401
        import app.models.chat  # noqa: F401
        import app.models.billing  # noqa: F401
        import app.models.sharing  # noqa: F401

        if settings.DATABASE_URL.startswith("sqlite"):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

    return app


app = create_app()
