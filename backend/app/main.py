"""Main FastAPI application for JobHunt AI.

Configures the application, includes API routers, and sets up middleware.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import settings
from app.database import engine
from app.models._base import Base


async def _create_tables() -> None:
    """Create database tables on startup.

    Migrations (via Alembic) are the documented schema-evolution mechanism.
    This synchronous ``create_all`` call is a convenience for local
    development and testing; for deployed use run ``alembic upgrade head``.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description="JobHunt AI - Personal career copilot backend",
        version="0.1.0",
        on_startup=[_create_tables],
    )

    # CORS middleware for development.
    #
    # Wildcard origins and credentialed requests are mutually exclusive per the
    # Fetch specification: a credentialed request to `Origin: *` is rejected by
    # browsers. With a wildcard origin we must not set allow_credentials, so
    # credentialed cross-origin calls are intentionally unsupported in dev.
    # Before enabling credentialed requests, replace the wildcard with an
    # explicit origin list (see settings.cors_origins).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()