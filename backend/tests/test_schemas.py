"""Test Pydantic schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.job import JobPostingCreate, JobSourceRecord
from app.schemas.match import MatchResult, MatchResultCreate, Recommendation
from app.schemas.profile import (
    CandidateProfile,
    ContactInfo,
    Education,
    FactSource,
    ProfileData,
    ProfilePreferences,
    ProfileUpdate,
    Skill,
    WorkExperience,
)
from app.schemas.application import Application, ApplicationCreate, Document, DocumentType


@pytest.mark.asyncio
async def test_profile_schema() -> None:
    """Test profile schema validation."""
    profile = CandidateProfile(
        profile_data=ProfileData(
            full_name="Test User",
            contact=ContactInfo(email="test@example.com"),
            skills=[
                Skill(
                    name="Python",
                    years_of_experience=5.0,
                    proficiency="expert",
                    source=FactSource.user_confirmed,
                    source_reference="Resume page 3",
                )
            ],
            work_experience=[
                WorkExperience(
                    company="TechCorp",
                    title="Senior Python Engineer",
                    start_date="2020-01-01",
                    end_date=None,
                    description="Led Django development team",
                )
            ],
        ),
        preferences_data=ProfilePreferences(
            target_titles=["Senior Python Engineer", "Backend Engineer"],
            preferred_locations=["San Francisco, CA", "Remote"],
            work_arrangements=["hybrid", "remote"],
            min_compensation=120000,
        ),
    )
    assert profile.profile_data.full_name == "Test User"
    assert profile.version == 1
    assert len(profile.profile_data.skills) == 1
    assert profile.profile_data.skills[0].name == "Python"

@pytest.mark.asyncio
async def test_profile_update_schema() -> None:
    """Test profile update schema."""
    update = ProfileUpdate(
        profile_data=ProfileData(
            full_name="Updated Name",
            skills=[
                Skill(
                    name="Python",
                    years_of_experience=6.0,
                    proficiency="expert",
                    source=FactSource.user_confirmed,
                    source_reference="Resume page 3",
                )
            ],
        ),
        preferences_data=None,
    )
    assert update.profile_data is not None
    assert update.profile_data.full_name == "Updated Name"
    assert update.preferences_data is None

@pytest.mark.asyncio
async def test_job_posting_schema() -> None:
    """Test job posting schema validation."""
    posting = JobPostingCreate(
        company="TechCorp Inc",
        title="Senior Python Engineer",
        location="San Francisco, CA",
        work_arrangement="hybrid",
        employment_type="full_time",
        description="We are seeking a Senior Python Engineer with 5+ years of experience in Django, REST APIs, and PostgreSQL.",
        url="https://techcorp.com/jobs/senior-python-engineer",
        posted_at="2026-10-01T00:00:00Z",
        external_id="TC-SENIOR-PYTHON-001",
    )
    assert posting.company == "TechCorp Inc"
    assert posting.title == "Senior Python Engineer"
    assert posting.external_id == "TC-SENIOR-PYTHON-001"

@pytest.mark.asyncio
async def test_match_result_schema() -> None:
    """Test match result schema validation."""
    match_result = MatchResult(
        job_id="job-123",
        profile_id="profile-456",
        profile_version=1,
        score=85.5,
        recommendation=Recommendation.strong_match,
        strengths=["Python experience", "Django experience"],
        gaps=["No PostgreSQL experience"],
        unknowns=["Compensation not specified"],
        evidence=[
            {
                "criterion": "skills",
                "type": "strength",
                "statement": "Python experience",
                "source": "profile skills",
            }
        ],
    )
    assert match_result.score == 85.5
    assert match_result.recommendation == Recommendation.strong_match
    assert len(match_result.strengths) == 2

@pytest.mark.asyncio
async def test_application_document_schema() -> None:
    """Test application and document schema validation."""
    application = ApplicationCreate(
        job_id="job-123",
        profile_id="profile-456",
        notes="Initial application",
    )
    assert application.job_id == "job-123"
    assert application.profile_id == "profile-456"

    document = Document(
        application_id="app-789",
        document_type=DocumentType.resume,
        version=1,
        content="# Resume Content",
        source_profile_version=1,
        source_job_content_hash="abc123",
    )
    assert document.document_type == DocumentType.resume
    assert document.version == 1
    assert document.content == "# Resume Content"