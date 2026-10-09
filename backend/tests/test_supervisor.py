"""Tests for the multi-agent supervisor.

Verifies that:
- The supervisor runs matching before invoking the workflow.
- A successful match produces workflows that complete.
- Workflow failures surface as SupervisorError with phase metadata.
- The supervisor delegates tool calls and tool results correctly.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.job_matcher import JobMatcherAgent
from app.agents.supervisor import Supervisor, SupervisorError
from app.harness.harness import HarnessError
from app.schemas.job import JobPosting
from app.schemas.match import MatchResult, Recommendation
from app.schemas.profile import (
    CandidateProfile,
    ProfileData,
    ProfilePreferences,
    Skill,
    WorkExperience,
)
from app.workflow.state import WorkflowState


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def profile() -> CandidateProfile:
    return CandidateProfile(
        profile_id="test-profile",
        profile_data=ProfileData(
            full_name="Test Candidate",
            skills=[Skill(name="Python", years_of_experience=5)],
            work_experience=[
                WorkExperience(
                    title="Developer",
                    company="Tech Corp",
                    start_date="2020-01-01",
                )
            ],
        ),
        preferences_data=ProfilePreferences(),
    )


@pytest.fixture
def job() -> JobPosting:
    return JobPosting(
        job_id="job-1",
        title="Senior Python Developer",
        company="Startup Inc",
        description="Looking for Python devs.",
    )


# --------------------------------------------------------------------------- #
# Test data
# --------------------------------------------------------------------------- #


def make_match_result(profile_id: str = "test-profile", job_id: str = "job-1") -> MatchResult:
    return MatchResult(
        match_id="match-1",
        profile_id=profile_id,
        job_id=job_id,
        score=85.0,
        recommendation=Recommendation.strong_match,
    )


def make_workflow_state(profile_id: str, job_id: str) -> dict[str, Any]:
    return {
        "workflow_id": f"wf-{job_id}-{profile_id}",
        "status": "running",
        "profile": {
            "profile_id": profile_id,
            "profile_data": {
                "full_name": "Test Candidate",
                "skills": [{"name": "Python", "years_of_experience": 5}],
                "work_experience": [{"title": "Developer", "company": "Tech Corp", "start_date": "2020-01-01"}],
            },
            "preferences_data": {},
        },
        "job_id": job_id,
        "job_posting": {"job_id": job_id, "title": "Senior Python Developer", "company": "Startup Inc"},
        "match_result": {"match_id": "match-1", "profile_id": profile_id, "job_id": job_id, "score": 85.0},
        "draft_resume": None,
        "draft_cover_letter": None,
        "review_results": [],
        "revision_count": 0,
        "max_revisions": 2,
        "approval_request_id": None,
        "approval_status": "pending",
        "error": None,
        "metadata": {},
    }


# --------------------------------------------------------------------------- #
# Supervisor success path
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_supervisor_runs_match_and_workflow(profile, job) -> None:
    """The supervisor invokes matching, then passes the result to the workflow."""
    mock_workflow = AsyncMock()
    mock_workflow.ainvoke = AsyncMock(return_value={
        "status": "awaiting_approval",
        "draft_resume": "# Resume",
        "draft_cover_letter": "# Cover",
        "metadata": {"application_id": "app-1"},
        "approval_request_id": "approval-1",
        "approval_status": "pending",
    })

    supervisor = Supervisor(matcher=MagicMock(), workflow=mock_workflow)
    supervisor.matcher.match = AsyncMock(return_value=make_match_result())

    result = await supervisor.run(profile=profile, job=job)

    assert result["status"] == "awaiting_approval"
    assert result["draft_resume"] == "# Resume"
    assert "match_result" in result
    assert result["match_result"]["score"] == 85.0
    assert result["approval_request_id"] == "approval-1"

    # The matcher was called once.
    supervisor.matcher.match.assert_called_once()
    # The workflow was invoked once with the returned state.
    mock_workflow.ainvoke.assert_called_once()
    called_state = mock_workflow.ainvoke.call_args[0][0]
    assert called_state.get("job_id") == job.job_id or called_state.get("job_id") == job.id


@pytest.mark.asyncio
async def test_supervisor_propagates_workflow_failure(profile, job) -> None:
    """A workflow exception raises SupervisorError with phase='workflow'."""
    mock_workflow = AsyncMock()
    mock_workflow.ainvoke = AsyncMock(side_effect=RuntimeError("db down"))

    supervisor = Supervisor(matcher=MagicMock(), workflow=mock_workflow)
    supervisor.matcher.match = AsyncMock(return_value=make_match_result())

    with pytest.raises(SupervisorError, match="workflow"):
        await supervisor.run(profile=profile, job=job)


@pytest.mark.asyncio
async def test_supervisor_propagates_matching_failure(profile, job) -> None:
    """A harness-level matching failure raises SupervisorError with phase='match'."""
    mock_workflow = MagicMock()
    supervisor = Supervisor(matcher=MagicMock(), workflow=mock_workflow)
    supervisor.matcher.match = AsyncMock(side_effect=HarnessError(
        agent_name="job_matcher",
        error_type="retry_exhausted",
        message="LLM unreachable",
    ))

    with pytest.raises(SupervisorError, match="match"):
        await supervisor.run(profile=profile, job=job)


@pytest.mark.asyncio
async def test_supervisor_with_tool_calls_in_workflow(profile, job) -> None:
    """The workflow returns a state reflecting tool calls and results."""
    mock_workflow = AsyncMock()
    mock_workflow.ainvoke = AsyncMock(return_value={
        "status": "awaiting_approval",
        "draft_resume": "Resume",
        "draft_cover_letter": "Cover",
        "tool_calls": [
            {"id": "c1", "name": "get_candidate_profile", "arguments": {"profile_id": "p1"}}
        ],
        "tool_results": [
            {"tool_name": "get_candidate_profile", "success": True, "content": {"id": "p1"}}
        ],
        "metadata": {"persisted": True, "application_id": "app-1"},
        "approval_request_id": "approval-1",
        "approval_status": "pending",
    })

    supervisor = Supervisor(matcher=MagicMock(), workflow=mock_workflow)
    supervisor.matcher.match = AsyncMock(return_value=make_match_result())

    result = await supervisor.run(profile=profile, job=job)
    assert "tool_calls" in result
    assert result["tool_calls"][0]["name"] == "get_candidate_profile"


# --------------------------------------------------------------------------- #
# Workflow integration with real agents
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_supervisor_with_mock_harness_workflow(profile, job) -> None:
    """Supervisor integrates with a mock harness inside the workflow nodes."""
    from app.workflow.graph import build_job_search_graph

    graph = build_job_search_graph()
    workflow = graph.compile()

    supervisor = Supervisor(workflow=workflow)
    # The default JobMatcherAgent returns a deterministic match when no tools
    # are available (as in this test), so matching should succeed.
    result = await supervisor.run(profile=profile, job=job)
    # The workflow reaches approval because review_results is empty (no issues).
    assert result["status"] == "awaiting_approval"
    assert result["draft_resume"] is not None
    assert result["draft_cover_letter"] is not None


@pytest.mark.asyncio
async def test_supervisor_workflow_fallback_on_draft_failure(profile, job) -> None:
    """If drafting fails, the supervisor still surfaces the error."""
    from app.workflow.graph import build_job_search_graph

    graph = build_job_search_graph()
    workflow = graph.compile()

    # Simulate a draft failure by injecting review results with critical issue
    original_draft = workflow.graph.nodes["draft"]

    async def failing_draft(state):
        return {
            "status": "failed",
            "error": "draft generation failed",
            "metadata": {"drafted": False},
        }

    workflow.graph.nodes["draft"] = failing_draft
    try:
        supervisor = Supervisor(workflow=workflow)
        result = await supervisor.run(profile=profile, job=job)
        # A failed draft makes the workflow terminal with an error.
        assert result["status"] == "failed"
        assert "error" in result
    finally:
        workflow.graph.nodes["draft"] = original_draft


# --------------------------------------------------------------------------- #
# API endpoint integration
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_run_workflow_endpoint(client, db_session) -> None:
    """POST /api/v1/workflows triggers the workflow and returns results."""
    from app.models._base import Base
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    # Ensure tables exist
    async with db_session.begin():
        await db_session.execute(Base.metadata.create_all())

    profile_data = {
        "full_name": "Test User",
        "contact": None,
        "summary": "Experienced Python dev.",
        "skills": [{"name": "Python", "years_of_experience": 5.0, "proficiency": None, "source": "user_supplied", "source_reference": None}],
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
    response = client.put("/api/v1/profiles/current", json={"profile_data": profile_data, "preferences_data": preferences_data})
    assert response.status_code == 200

    posting_data = {
        "company": "TechCorp",
        "title": "Senior Python Engineer",
        "location": "Remote",
        "description": "Python required.",
        "url": "https://example.com/jobs/1",
        "source": "fixture",
        "external_id": "TC-SENIOR-001",
    }
    ingest_response = client.post("/api/v1/jobs/ingest", json=posting_data)
    assert ingest_response.status_code == 200
    job_id = ingest_response.json()["job_id"]

    run_response = client.post(f"/api/v1/workflows?job_id={job_id}")
    assert run_response.status_code == 200
    body = run_response.json()
    assert "status" in body
    assert "match_result" in body
    assert "draft_resume" in body
    assert "draft_cover_letter" in body


@pytest.mark.asyncio
async def test_run_workflow_missing_profile(client) -> None:
    """Endpoint returns 404 when no profile exists."""
    response = client.post("/api/v1/workflows?job_id=some-job")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_run_workflow_missing_job(client, db_session) -> None:
    """Endpoint returns 404 when the job does not exist."""
    from app.models._base import Base
    async with db_session.begin():
        await db_session.execute(Base.metadata.create_all())

    profile_data = {
        "full_name": "Test User",
        "contact": None,
        "summary": None,
        "skills": [],
        "work_experience": [],
        "education": [],
        "certifications": [],
        "projects": [],
        "resume_text": None,
    }
    preferences_data = {"target_titles": [], "preferred_industries": [], "preferred_locations": [], "work_arrangements": [], "employment_types": [], "min_compensation": None, "compensation_currency": None, "work_authorization": None, "additional": {}}
    client.put("/api/v1/profiles/current", json={"profile_data": profile_data, "preferences_data": preferences_data})

    response = client.post("/api/v1/workflows?job_id=nonexistent-job")
    assert response.status_code == 404
