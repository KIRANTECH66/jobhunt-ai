"""Test deterministic fallback scenarios.

Verifies that the JobMatcherAgent falls back to deterministic scoring when:
1. Model timeout
2. Provider error
3. Malformed response
4. Schema validation failure
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.job_matcher import JobMatcherAgent
from app.harness.harness import HarnessError
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
def profile() -> CandidateProfile:
    return CandidateProfile(
        profile_data=ProfileData(
            full_name="Test User",
            skills=[Skill(name="Python", years_of_experience=5.0)],
            work_experience=[WorkExperience(company="TechCorp", title="Engineer", start_date="2018-01-01", end_date=None)],
        ),
        preferences_data=ProfilePreferences(target_titles=["Engineer"]),
    )


@pytest.fixture
def job() -> JobPosting:
    return JobPosting(company="TechCorp", title="Engineer", description="Need Python")


class TestFallbackScenarios:
    """Test all fallback paths in JobMatcherAgent."""

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self, profile, job) -> None:
        """Test fallback when model raises TimeoutError."""
        agent = JobMatcherAgent()
        with patch.object(agent.harness, 'run') as mock_run:
            mock_run.return_value = type('MockResult', (), {
                'success': False,
                'error': HarnessError(agent_name='job_matcher', error_type='timeout', message='Model timeout'),
                'output': None,
                'trace': {},
                'usage': {},
                'tool_calls': [],
                'tool_results': [],
            })()

            result = await agent.match(profile, job)
            assert isinstance(result, MatchResult)
            assert result.scoring_version == "v1-deterministic"

    @pytest.mark.asyncio
    async def test_fallback_on_provider_error(self, profile, job) -> None:
        """Test fallback when model raises RuntimeError (provider error)."""
        agent = JobMatcherAgent()
        with patch.object(agent.harness, 'run') as mock_run:
            mock_run.return_value = type('MockResult', (), {
                'success': False,
                'error': HarnessError(agent_name='job_matcher', error_type='unexpected', message='OpenAI API error'),
                'output': None,
                'trace': {},
                'usage': {},
                'tool_calls': [],
                'tool_results': [],
            })()

            result = await agent.match(profile, job)
            assert isinstance(result, MatchResult)
            assert result.scoring_version == "v1-deterministic"

    @pytest.mark.asyncio
    async def test_fallback_on_malformed_response(self, profile, job) -> None:
        """Test fallback when model returns malformed JSON."""
        agent = JobMatcherAgent()
        with patch.object(agent.harness, 'run') as mock_run:
            mock_run.return_value = type('MockResult', (), {
                'success': True,
                'error': None,
                'output': "not valid json {{{",
                'trace': {},
                'usage': {},
                'tool_calls': [],
                'tool_results': [],
            })()

            result = await agent.match(profile, job)
            assert isinstance(result, MatchResult)
            assert result.scoring_version == "v1-deterministic"

    @pytest.mark.asyncio
    async def test_fallback_on_schema_validation_failure(self, profile, job) -> None:
        """Test fallback when model returns output missing required fields."""
        agent = JobMatcherAgent()
        with patch.object(agent.harness, 'run') as mock_run:
            mock_run.return_value = type('MockResult', (), {
                'success': True,
                'error': None,
                'output': {"partial": "data"},  # Missing score, recommendation, etc.
                'trace': {},
                'usage': {},
                'tool_calls': [],
                'tool_results': [],
            })()

            result = await agent.match(profile, job)
            assert isinstance(result, MatchResult)
            assert result.scoring_version == "v1-deterministic"

    @pytest.mark.asyncio
    async def test_fallback_identifies_source(self, profile, job) -> None:
        """Test that the result identifies whether it came from LLM or fallback."""
        agent = JobMatcherAgent()

        # Test LLM path
        with patch.object(agent.harness, 'run') as mock_run:
            mock_run.return_value = type('MockResult', (), {
                'success': True,
                'error': None,
                'output': {
                    "score": 80,
                    "recommendation": "strong_match",
                    "strengths": ["Python"],
                    "gaps": [],
                    "unknowns": [],
                    "evidence": [],
                },
                'trace': {},
                'usage': {},
                'tool_calls': [],
                'tool_results': [],
            })()
            result = await agent.match(profile, job)
            assert result.scoring_version == "v2-llm-assisted"

        # Test fallback path
        with patch.object(agent.harness, 'run') as mock_run:
            mock_run.return_value = type('MockResult', (), {
                'success': False,
                'error': HarnessError(agent_name='job_matcher', error_type='timeout', message='timeout'),
                'output': None,
                'trace': {},
                'usage': {},
                'tool_calls': [],
                'tool_results': [],
            })()
            result = await agent.match(profile, job)
            assert result.scoring_version == "v1-deterministic"
