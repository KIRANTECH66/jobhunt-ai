"""Test the LLM-assisted Job Matcher agent."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.job_matcher import JobMatcherAgent
from app.harness.harness import AgentHarness
from app.schemas.job import JobPosting
from app.schemas.match import MatchResult
from app.schemas.profile import (
    CandidateProfile,
    ProfileData,
    ProfilePreferences,
    Skill,
    WorkExperience,
)


@pytest.fixture
def test_profile() -> CandidateProfile:
    """Create a test candidate profile."""
    return CandidateProfile(
        profile_data=ProfileData(
            full_name="Test User",
            skills=[
                Skill(name="Python", years_of_experience=5.0),
                Skill(name="Django", years_of_experience=3.0),
            ],
            work_experience=[
                WorkExperience(
                    company="TechCorp",
                    title="Senior Python Engineer",
                    start_date="2018-01-01",
                    end_date=None,
                ),
            ],
        ),
        preferences_data=ProfilePreferences(
            target_titles=["Senior Python Engineer"],
            preferred_locations=["San Francisco, CA"],
            work_arrangements=["hybrid"],
        ),
    )


@pytest.fixture
def test_job() -> JobPosting:
    """Create a test job posting."""
    return JobPosting(
        company="TechCorp Inc",
        title="Senior Python Engineer",
        location="San Francisco, CA",
        work_arrangement="hybrid",
        description="We need Python and Django experience.",
    )


@pytest.mark.asyncio
async def test_matcher_fallback_to_deterministic(test_profile: CandidateProfile, test_job: JobPosting) -> None:
    """Test that the matcher falls back to deterministic scoring when LLM fails."""
    agent = JobMatcherAgent()

    # Mock the harness to fail
    with patch.object(agent.harness, 'run') as mock_run:
        mock_run.return_value = type('MockResult', (), {
            'success': False,
            'error': type('MockError', (), {
                'error_type': 'timeout',
                'message': 'Model timeout',
            })(),
            'output': None,
            'trace': {},
            'usage': {},
            'tool_calls': [],
            'tool_results': [],
        })()

        result = await agent.match(test_profile, test_job)
        assert isinstance(result, MatchResult)
        assert result.scoring_version == "v1-deterministic"


@pytest.mark.asyncio
async def test_matcher_uses_llm_when_available(test_profile: CandidateProfile, test_job: JobPosting) -> None:
    """Test that the matcher uses the LLM when available."""
    agent = JobMatcherAgent()

    # Mock the harness to return valid output
    mock_output = {
        "score": 90.0,
        "recommendation": "strong_match",
        "strengths": ["Python experience", "Django experience"],
        "gaps": ["No PostgreSQL"],
        "unknowns": ["Compensation"],
        "evidence": [
            {
                "criterion": "skills",
                "type": "strength",
                "statement": "Python experience",
                "source": "profile",
            }
        ],
    }

    with patch.object(agent.harness, 'run') as mock_run:
        mock_run.return_value = type('MockResult', (), {
            'success': True,
            'error': None,
            'output': mock_output,
            'trace': {},
            'usage': {},
            'tool_calls': [],
            'tool_results': [],
        })()

        result = await agent.match(test_profile, test_job)
        assert isinstance(result, MatchResult)
        assert result.score == 90.0
        assert result.scoring_version == "v2-llm-assisted"


@pytest.mark.asyncio
async def test_matcher_invalid_llm_output_falls_back(test_profile: CandidateProfile, test_job: JobPosting) -> None:
    """Test that invalid LLM output falls back to deterministic scoring."""
    agent = JobMatcherAgent()

    # Mock the harness to return invalid output
    mock_output = {"wrong_field": 123}

    with patch.object(agent.harness, 'run') as mock_run:
        mock_run.return_value = type('MockResult', (), {
            'success': True,
            'error': None,
            'output': mock_output,
            'trace': {},
            'usage': {},
            'tool_calls': [],
            'tool_results': [],
        })()

        result = await agent.match(test_profile, test_job)
        assert isinstance(result, MatchResult)
        assert result.scoring_version == "v1-deterministic"


@pytest.mark.asyncio
async def test_matcher_exact_match(test_profile: CandidateProfile, test_job: JobPosting) -> None:
    """Test matching with an exact match."""
    agent = JobMatcherAgent()
    result = await agent.match(test_profile, test_job)
    assert result.score > 50  # Should be a good match


@pytest.mark.asyncio
async def test_matcher_no_match() -> None:
    """Test matching with no valid match."""
    profile = CandidateProfile(
        profile_data=ProfileData(
            full_name="Test User",
            skills=[Skill(name="Rust", years_of_experience=2.0)],
        ),
        preferences_data=ProfilePreferences(
            target_titles=["Rust Developer"],
            preferred_locations=["Remote"],
            work_arrangements=["remote"],
        ),
    )
    job = JobPosting(
        company="TechCorp",
        title="Senior Python Engineer",
        location="San Francisco, CA",
        work_arrangement="hybrid",
        description="We need Python and Django experience.",
    )
    agent = JobMatcherAgent()
    result = await agent.match(profile, job)
    assert result.score < 50  # Should be a poor match