"""API dependencies.

Provides dependency injection for database sessions and other shared resources.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db as get_async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields a database session.

    This is a thin wrapper around the existing `get_db` function from
    ``app.database`` to match the FastAPI dependency pattern.
    """
    async with AsyncSessionLocal() as session:
        yield session