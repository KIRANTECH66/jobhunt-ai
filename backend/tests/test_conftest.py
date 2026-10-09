"""Tests for the base fixtures.

Verifies that the fixtures are properly configured and work as expected.
"""

from __future__ import annotations

import asyncio
import pytest
from sqlalchemy import select

from app.models import CandidateProfile


@pytest.mark.asyncio
async def test_db_session(db_session) -> None:
    """Test that the database session fixture works correctly."""
    # Create a test profile
    profile = CandidateProfile(
        id="test-profile",
        version=1,
        profile_data={"full_name": "Test User"},
        preferences_data={},
    )
    db_session.add(profile)
    await db_session.commit()

    # Verify the profile was saved
    result = await db_session.execute(select(CandidateProfile).where(CandidateProfile.id == "test-profile"))
    saved_profile = result.scalar_one()
    assert saved_profile is not None
    assert saved_profile.profile_data["full_name"] == "Test User"


def test_test_client(test_client) -> None:
    """Test that the test client fixture works correctly."""
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_job_repository(job_repository) -> None:
    """Test that the in-memory job repository fixture works correctly."""
    # Test saving a job
    job_id = await job_repository.save_job_posting(
        {
            "company": "Test Corp",
            "title": "Software Engineer",
            "location": "New York, NY",
            "description": "Great job",
            "url": "https://example.com/job/1",
            "source": "fixture",
            "external_id": "EXT-001",
        }
    )
    assert job_id is not None

    # Test retrieving the job
    retrieved_job = await job_repository.get_by_id(job_id)
    assert retrieved_job is not None
    assert retrieved_job["company"] == "Test Corp"


@pytest.mark.asyncio
async def test_profile_repository(profile_repository) -> None:
    """Test that the in-memory profile repository fixture works correctly."""
    # Test saving a profile
    profile_id = await profile_repository.create(
        {
            "full_name": "Test User",
            "skills": [
                {
                    "name": "Python",
                    "years_of_experience": 5.0,
                    "proficiency": None,
                    "source": "user_supplied",
                    "source_reference": None,
                }
            ],
        },
        {
            "target_titles": ["Senior Python Engineer"],
            "preferred_industries": [],
            "preferred_locations": [],
            "work_arrangements": [],
            "employment_types": [],
            "min_compensation": None,
            "compensation_currency": None,
            "work_authorization": None,
            "additional": {},
        },
    )
    assert profile_id is not None

    # Test retrieving the profile
    retrieved_profile = await profile_repository.get_current()
    assert retrieved_profile is not None
    assert retrieved_profile["profile_data"]["full_name"] == "Test User"


@pytest.mark.asyncio
async def test_match_repository(match_repository) -> None:
    """Test that the in-memory match repository fixture works correctly."""
    # Test saving a match result
    match_id = await match_repository.save_match_result(
        {
            "job_id": "job-1",
            "profile_id": "profile-1",
            "profile_version": 1,
            "score": 85.0,
            "recommendation": "strong_match",
            "strengths": ["Python experience", "Django experience"],
            "gaps": ["No PostgreSQL experience"],
            "unknowns": ["Compensation not specified"],
            "evidence": [
                {
                    "criterion": "skills",
                    "type": "strength",
                    "statement": "Python experience",
                    "source": "profile skills",
                }
            ],
        }
    )
    assert match_id is not None

    # Test retrieving the match result
    retrieved_match = await match_repository.get_by_job_id("job-1")
    assert retrieved_match is not None
    assert retrieved_match["score"] == 85.0


@pytest.mark.asyncio
async def test_audit_repository(audit_repository) -> None:
    """Test that the in-memory audit repository fixture works correctly."""
    # Test saving an audit event
    audit_id = await audit_repository.save_audit_event(
        {
            "action": "job.ingested",
            "entity_type": "job",
            "entity_id": "job-1",
            "outcome": "success",
            "metadata": {"source": "fixture"},
        }
    )
    assert audit_id is not None

    # Test retrieving the audit event
    recent_events = await audit_repository.get_recent()
    assert len(recent_events) == 1
    assert recent_events[0]["action"] == "job.ingested"