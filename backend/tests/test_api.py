"""Test API endpoints.

Uses an isolated in-memory SQLite database by mocking the database dependency.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from unittest.mock import patch, AsyncMock

from app.models._base import Base


# Module-level in-memory engine for API tests
_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="session")
async def db_session():
    """Create a session for API tests (session-scoped)."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        yield session

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _get_test_db():
    """Return the test database session."""
    return db_session


@pytest.fixture
def test_client(db_session):
    """Create a test client with an isolated database."""
    from app.main import app
    from app.api import deps

    # Override the get_db dependency to use our test session
    async def override_get_db():
        yield db_session

    app.dependency_overrides[deps.get_db] = override_get_db

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


def test_health_endpoint(test_client: TestClient) -> None:
    """Test health check endpoint."""
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_profile_not_found(test_client: TestClient) -> None:
    """Test getting profile when none exists."""
    response = test_client.get("/api/v1/profiles/current")
    assert response.status_code == 404


def test_create_and_get_profile(test_client: TestClient) -> None:
    """Test creating and retrieving a profile."""
    profile_data = {
        "full_name": "Test User",
        "contact": None,
        "summary": None,
        "skills": [
            {
                "name": "Python",
                "years_of_experience": 5.0,
                "proficiency": None,
                "source": "user_supplied",
                "source_reference": None,
            }
        ],
        "work_experience": [],
        "education": [],
        "certifications": [],
        "projects": [],
        "resume_text": None,
    }
    preferences_data = {
        "target_titles": ["Senior Python Engineer"],
        "preferred_industries": [],
        "preferred_locations": [],
        "work_arrangements": [],
        "employment_types": [],
        "min_compensation": None,
        "compensation_currency": None,
        "work_authorization": None,
        "additional": {},
    }

    # Create profile
    response = test_client.put(
        "/api/v1/profiles/current",
        json={"profile_data": profile_data, "preferences_data": preferences_data},
    )
    assert response.status_code == 200
    data = response.json()
    profile_id = data["id"]
    assert data["version"] == 1
    assert data["profile_data"]["full_name"] == "Test User"

    # Get profile
    response = test_client.get("/api/v1/profiles/current")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == profile_id
    assert data["profile_data"]["full_name"] == "Test User"


def test_update_profile(test_client: TestClient) -> None:
    """Test updating an existing profile."""
    # First create a profile
    profile_data = {
        "full_name": "Test User",
        "contact": None,
        "summary": None,
        "skills": [
            {
                "name": "Python",
                "years_of_experience": 5.0,
                "proficiency": None,
                "source": "user_supplied",
                "source_reference": None,
            }
        ],
        "work_experience": [],
        "education": [],
        "certifications": [],
        "projects": [],
        "resume_text": None,
    }
    preferences_data = {
        "target_titles": ["Senior Python Engineer"],
        "preferred_industries": [],
        "preferred_locations": [],
        "work_arrangements": [],
        "employment_types": [],
        "min_compensation": None,
        "compensation_currency": None,
        "work_authorization": None,
        "additional": {},
    }

    response = test_client.put(
        "/api/v1/profiles/current",
        json={"profile_data": profile_data, "preferences_data": preferences_data},
    )
    assert response.status_code == 200
    original_profile_id = response.json()["id"]
    original_version = response.json()["version"]

    # Update the profile
    updated_profile_data = profile_data.copy()
    updated_profile_data["full_name"] = "Updated User"
    updated_preferences_data = preferences_data.copy()
    updated_preferences_data["target_titles"] = ["Lead Engineer"]

    response = test_client.put(
        "/api/v1/profiles/current",
        json={
            "profile_data": updated_profile_data,
            "preferences_data": updated_preferences_data,
        },
    )
    assert response.status_code == 200
    updated_data = response.json()
    assert updated_data["version"] == original_version + 1
    assert updated_data["profile_data"]["full_name"] == "Updated User"
    assert updated_data["preferences_data"]["target_titles"] == ["Lead Engineer"]


def test_ingest_job_posting(test_client: TestClient) -> None:
    """Test ingesting a job posting."""
    posting_data = {
        "company": "TechCorp Inc",
        "title": "Senior Python Engineer",
        "location": "San Francisco, CA",
        "work_arrangement": "hybrid",
        "employment_type": "full_time",
        "description": "We are seeking a Senior Python Engineer with 5+ years of experience in Django, REST APIs, and PostgreSQL.",
        "url": "https://techcorp.com/jobs/senior-python-engineer",
        "posted_at": "2026-10-01T00:00:00Z",
        "external_id": "TC-SENIOR-PYTHON-001",
    }

    response = test_client.post("/api/v1/jobs/ingest", json=posting_data)
    assert response.status_code == 200
    data = response.json()
    assert data["is_new"] is True
    job_id = data["job_id"]
    assert job_id is not None

    # Ingest the same job again - should be idempotent
    response = test_client.post("/api/v1/jobs/ingest", json=posting_data)
    assert response.status_code == 200
    data = response.json()
    assert data["is_new"] is False
    assert data["job_id"] == job_id


def test_list_jobs(test_client: TestClient) -> None:
    """Test listing jobs."""
    # First ingest a job
    posting_data = {
        "company": "TechCorp Inc",
        "title": "Senior Python Engineer",
        "location": "San Francisco, CA",
        "description": "We are seeking a Senior Python Engineer.",
        "url": "https://techcorp.com/jobs/senior-python-engineer",
        "source": "fixture",
        "external_id": "TC-SENIOR-PYTHON-001",
    }
    test_client.post("/api/v1/jobs/ingest", json=posting_data)

    # List jobs
    response = test_client.get("/api/v1/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) >= 1
    assert jobs[0]["company"] == "TechCorp Inc"
    assert jobs[0]["title"] == "Senior Python Engineer"


def test_get_job_not_found(test_client: TestClient) -> None:
    """Test getting a non-existent job."""
    response = test_client.get("/api/v1/jobs/non-existent-job-id")
    assert response.status_code == 404


def test_get_match_not_found(test_client: TestClient) -> None:
    """Test getting a match for a job with no matches."""
    response = test_client.get("/api/v1/jobs/non-existent-job-id/match")
    assert response.status_code == 404