"""Test fixtures for JobHunt AI backend.

Provides:
- Async database session fixture
- In-memory repositories for testing
- Test client for FastAPI endpoints
"""

from __future__ import annotations

import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models._base import Base
from app.repositories.inmemory.job import InMemoryJobRepository
from app.repositories.inmemory.profile import InMemoryProfileRepository
from app.repositories.inmemory.match import InMemoryMatchRepository
from app.repositories.inmemory.audit import InMemoryAuditRepository

# Create an in-memory SQLite engine for testing
engine = create_async_engine("sqlite+aiosqlite:///:memory:")
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Create a new database session for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def test_client():
    """Create a test client for FastAPI endpoints.

    Note: The API tests use their own isolated database via a separate fixture
    defined in test_api.py to avoid shared state issues.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def job_repository() -> InMemoryJobRepository:
    """In-memory job repository for testing."""
    return InMemoryJobRepository()


@pytest.fixture
def profile_repository() -> InMemoryProfileRepository:
    """In-memory profile repository for testing."""
    return InMemoryProfileRepository()


@pytest.fixture
def match_repository() -> InMemoryMatchRepository:
    """In-memory match repository for testing."""
    return InMemoryMatchRepository()


@pytest.fixture
def audit_repository() -> InMemoryAuditRepository:
    """In-memory audit repository for testing."""
    return InMemoryAuditRepository()