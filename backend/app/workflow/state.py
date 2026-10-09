"""Workflow state schema.

Defines the TypedDict that flows through the LangGraph workflow. This is the
single source of truth for workflow state and checkpointing.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from app.schemas.job import JobPosting
from app.schemas.match import MatchResult
from app.schemas.profile import CandidateProfile


class WorkflowState(TypedDict, total=False):
    """State that flows through the job search workflow.

    Fields:
        workflow_id: Unique identifier for this workflow run.
        status: Current workflow status.
        profile: Candidate profile (loaded at start).
        job_id: Target job ID.
        job_posting: Normalized job posting.
        match_result: Computed match result.
        draft_resume: Generated resume draft (Markdown).
        draft_cover_letter: Generated cover letter draft (Markdown).
        review_results: List of quality review findings.
        revision_count: Number of automatic revision attempts.
        max_revisions: Maximum allowed automatic revisions.
        approval_request_id: ID of the approval request (if any).
        approval_status: Current approval status.
        error: Any error that occurred during execution.
        metadata: Additional workflow metadata.
    """

    workflow_id: str
    status: str  # 'running', 'paused', 'completed', 'failed'
    profile: CandidateProfile
    job_id: str
    job_posting: JobPosting
    match_result: MatchResult
    draft_resume: str | None
    draft_cover_letter: str | None
    review_results: list[dict[str, Any]]
    revision_count: int
    max_revisions: int
    approval_request_id: str | None
    approval_status: str  # 'pending', 'approved', 'rejected'
    error: str | None
    metadata: dict[str, Any]


def create_initial_state(
    *,
    workflow_id: str,
    profile: CandidateProfile,
    job_id: str,
    job_posting: JobPosting,
    match_result: MatchResult,
    max_revisions: int = 2,
) -> WorkflowState:
    """Create initial workflow state."""
    return WorkflowState(
        workflow_id=workflow_id,
        status="running",
        profile=profile,
        job_id=job_id,
        job_posting=job_posting,
        match_result=match_result,
        draft_resume=None,
        draft_cover_letter=None,
        review_results=[],
        revision_count=0,
        max_revisions=max_revisions,
        approval_request_id=None,
        approval_status="pending",
        error=None,
        metadata={},
    )