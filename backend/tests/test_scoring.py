"""Test deterministic match scoring."""

from __future__ import annotations

import asyncio

import pytest

from app.schemas.profile import CandidateProfile, ProfileData, ProfilePreferences, Skill, WorkExperience
from app.schemas.job import JobPosting
from app.services.scoring import MatchScorer


def test_skills_scoring() -> None:
    """Test skills scoring."""
    async def run_test() -> None:
        profile = CandidateProfile(
            profile_data=ProfileData(
                full_name="Test User",
                skills=[
                    Skill(name="Python", years_of_experience=5.0),
                    Skill(name="Django", years_of_experience=3.0),
                    Skill(name="PostgreSQL", years_of_experience=4.0),
                ],
            ),
            preferences_data=ProfilePreferences(),
        )

        job = JobPosting(
            company="TechCorp",
            title="Senior Python Engineer",
            description="We need Python, Django, and PostgreSQL experience.",
        )

        scorer = MatchScorer()
        result = scorer.score_job(profile, job)

        # Should find all three skills
        assert result.score > 0
        assert any("python" in s.lower() for s in result.strengths)
        assert any("django" in s.lower() for s in result.strengths)

    asyncio.run(run_test())


def test_role_scoring() -> None:
    """Test role alignment scoring."""
    async def run_test() -> None:
        profile = CandidateProfile(
            profile_data=ProfileData(
                full_name="Test User",
                skills=[Skill(name="Python", years_of_experience=5.0)],
            ),
            preferences_data=ProfilePreferences(
                target_titles=["Senior Python Engineer", "Backend Engineer"],
            ),
        )

        job = JobPosting(
            company="TechCorp",
            title="Senior Python Engineer",
        )

        scorer = MatchScorer()
        result = scorer.score_job(profile, job)

        assert result.score > 0
        assert any("Senior Python Engineer" in s for s in result.strengths)

    asyncio.run(run_test())


def test_seniority_scoring() -> None:
    """Test seniority alignment scoring."""
    async def run_test() -> None:
        profile = CandidateProfile(
            profile_data=ProfileData(
                full_name="Test User",
                work_experience=[
                    WorkExperience(
                        company="TechCorp",
                        title="Senior Python Engineer",
                        start_date="2018-01-01",
                        end_date="2023-12-31",
                    ),
                    WorkExperience(
                        company="StartupXYZ",
                        title="Software Engineer",
                        start_date="2015-01-01",
                        end_date="2017-12-31",
                    ),
                ],
            ),
            preferences_data=ProfilePreferences(),
        )

        job = JobPosting(
            company="TechCorp",
            title="Senior Python Engineer",
        )

        scorer = MatchScorer()
        result = scorer.score_job(profile, job)

        # Should have positive seniority score
        assert result.score > 0

    asyncio.run(run_test())


def test_location_scoring() -> None:
    """Test location scoring."""
    async def run_test() -> None:
        profile = CandidateProfile(
            profile_data=ProfileData(
                full_name="Test User",
                skills=[Skill(name="Python", years_of_experience=5.0)],
            ),
            preferences_data=ProfilePreferences(
                preferred_locations=["San Francisco, CA", "Remote"],
                work_arrangements=["hybrid", "remote"],
            ),
        )

        job = JobPosting(
            company="TechCorp",
            title="Senior Python Engineer",
            location="San Francisco, CA",
            work_arrangement="hybrid",
        )

        scorer = MatchScorer()
        result = scorer.score_job(profile, job)

        assert result.score > 0
        assert any("San Francisco" in s for s in result.strengths)
        assert any("hybrid" in s.lower() for s in result.strengths)

    asyncio.run(run_test())


def test_unknown_compensation() -> None:
    """Test that missing compensation is marked as unknown."""
    async def run_test() -> None:
        profile = CandidateProfile(
            profile_data=ProfileData(
                full_name="Test User",
                skills=[Skill(name="Python", years_of_experience=5.0)],
            ),
            preferences_data=ProfilePreferences(
                min_compensation=100000,
            ),
        )

        job = JobPosting(
            company="TechCorp",
            title="Senior Python Engineer",
            description="No salary information provided.",
        )

        scorer = MatchScorer()
        result = scorer.score_job(profile, job)

        assert any("compensation" in u.lower() for u in result.unknowns)

    asyncio.run(run_test())


def test_recommendation_thresholds() -> None:
    """Test recommendation logic."""
    async def run_test() -> None:
        profile = CandidateProfile(
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
                min_compensation=120000,
            ),
        )

        job = JobPosting(
            company="TechCorp",
            title="Senior Python Engineer",
            location="San Francisco, CA",
            work_arrangement="hybrid",
            description="We need Python and Django experience.",
        )

        scorer = MatchScorer()
        result = scorer.score_job(profile, job)

        # Should be a strong match
        assert result.recommendation.value == "strong_match"

    asyncio.run(run_test())