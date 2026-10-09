"""Supervisor coordinator for the job search workflow.

The supervisor is a thin coordination layer over the LangGraph workflow. It
does not implement agent logic itself; instead it:

1. Loads the candidate profile and target job from the repositories.
2. Runs the matcher agent to produce a validated ``MatchResult``.
3. Invokes the compiled workflow with the matched inputs.
4. Aggregates terminal state (drafts, review results, approval request) into
   a structured result that the API layer can expose.

It preserves the existing agent boundaries: the matcher, writer, and reviewer
each keep their own harness and fallback semantics. The supervisor only
orchestrates ordering and failure propagation.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.job_matcher import JobMatcherAgent
from app.harness.harness import HarnessError, HarnessResult
from app.schemas.job import JobPosting
from app.schemas.match import MatchResult
from app.schemas.profile import CandidateProfile
from app.workflow.state import create_initial_state

logger = logging.getLogger(__name__)


class SupervisorError(Exception):
    """Raised when the supervisor cannot complete a workflow run."""

    def __init__(self, message: str, *, phase: str, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.phase = phase
        self.cause = cause


class Supervisor:
    """Coordinates matching + workflow execution for a single application."""

    def __init__(
        self,
        matcher: JobMatcherAgent | None = None,
        workflow=None,
    ) -> None:
        self.matcher = matcher or JobMatcherAgent()
        self._workflow = workflow

    @property
    def workflow(self):
        """Lazily build the compiled workflow so tests can inject one."""
        if self._workflow is None:
            # Import deferred to avoid circular imports with app.workflow.graph.
            from app.workflow.graph import compile_job_search_workflow
            self._workflow = compile_job_search_workflow()
        return self._workflow

    async def run(
        self,
        *,
        profile: CandidateProfile,
        job: JobPosting,
        profile_id: str | None = None,
        job_id: str | None = None,
        max_revisions: int = 2,
    ) -> dict[str, Any]:
        """Run the full pipeline: match -> draft -> review -> persist -> await approval.

        Returns a dict with the terminal workflow state plus the match result
        and any supervisor-level error. The match result is always included so
        callers can inspect it even when the downstream workflow fails.
        """
        pid = profile_id or profile.profile_id or profile.id or "unknown"
        jid = job_id or job.job_id or job.id or "unknown"

        # Phase 1: matching. A failure here is recoverable — the deterministic
        # scorer inside JobMatcherAgent already handles LLM failures, but a
        # HarnessError still means the agent could not produce a result.
        try:
            match_result: MatchResult = await self.matcher.match(
                profile, job, profile_id=pid, job_id=jid
            )
        except Exception as e:
            logger.warning("Matching failed for job %s: %s", jid, e)
            raise SupervisorError(
                f"Matching phase failed for job {jid}: {e}",
                phase="match",
                cause=e,
            ) from e

        # Phase 2: workflow. A failure here is terminal for this run.
        state = create_initial_state(
            workflow_id=f"wf-{jid}-{pid}",
            profile=profile,
            job_id=jid,
            job_posting=job,
            match_result=match_result,
            max_revisions=max_revisions,
        )

        try:
            terminal = await self.workflow.ainvoke(state)
        except Exception as e:
            logger.error("Workflow execution failed for job %s: %s", jid, e)
            raise SupervisorError(
                f"Workflow phase failed for job {jid}: {e}",
                phase="workflow",
                cause=e,
            ) from e

        return {
            "workflow_id": terminal.get("workflow_id"),
            "status": terminal.get("status"),
            "error": terminal.get("error"),
            "match_result": match_result.model_dump(),
            "draft_resume": terminal.get("draft_resume"),
            "draft_cover_letter": terminal.get("draft_cover_letter"),
            "review_results": terminal.get("review_results", []),
            "revision_count": terminal.get("revision_count"),
            "metadata": terminal.get("metadata", {}),
            "approval_request_id": terminal.get("approval_request_id"),
            "approval_status": terminal.get("approval_status"),
        }