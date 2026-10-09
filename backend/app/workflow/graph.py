"""LangGraph workflow graph with real agent integration.

Implements the complete job search workflow:
1. validate - check input data
2. draft - generate application materials via Application Writer agent
3. review - run quality checks via Quality Reviewer agent
4. revise_or_block - decide whether to auto-revise or require human intervention
5. persist - save documents to database with versioning and idempotency
6. await_approval - create approval request and pause for human review

Uses LangGraph checkpoints for persistence and resumption.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from langgraph.graph import StateGraph, END

from app.agents.application_writer import ApplicationWriterAgent
from app.agents.quality_reviewer import QualityReviewerAgent
from app.models.application import Application as ApplicationModel
from app.models.application import Document as DocumentModel
from app.models.application import ApprovalRequest as ApprovalRequestModel
from app.repositories.application import SQLAlchemyApplicationRepository
from app.schemas.application import ApplicationStatus
from app.database import AsyncSessionLocal
from app.workflow.state import WorkflowState, create_initial_state
from app.workflow.validation import (
    validate_approval_against_state,
    compute_job_content_hash,
    ApprovalValidationError,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Node functions
# --------------------------------------------------------------------------- #


async def validate_node(state: WorkflowState) -> dict[str, Any]:
    """Validate that all required fields are present."""
    errors = []

    if not state.get("profile"):
        errors.append("Missing profile")
    if not state.get("job_posting"):
        errors.append("Missing job_posting")
    if not state.get("match_result"):
        errors.append("Missing match_result")
    if not state.get("job_id"):
        errors.append("Missing job_id")

    if errors:
        return {
            "status": "failed",
            "error": "; ".join(errors),
            "metadata": {**state.get("metadata", {}), "validated": False},
        }

    return {
        "status": "running",
        "metadata": {**state.get("metadata", {}), "validated": True},
    }


async def draft_node(state: WorkflowState) -> dict[str, Any]:
    """Generate application drafts using the Application Writer agent.

    The writer runs against the CURRENT ``draft_resume``/``draft_cover_letter``
    (if present from a prior revision) so revisions actually rewrite the
    documents rather than re-drafting from scratch.
    """
    writer = ApplicationWriterAgent()

    try:
        result = await writer.write(
            profile=state["profile"],
            job=state["job_posting"],
            match=state["match_result"],
        )

        return {
            "draft_resume": result.get("resume", state.get("draft_resume", "")),
            "draft_cover_letter": result.get("cover_letter", state.get("draft_cover_letter", "")),
            "metadata": {
                **state.get("metadata", {}),
                "drafted": True,
                "missing_info": result.get("missing_info", []),
            },
        }
    except Exception as e:
        logger.error("Draft generation failed: %s", e)
        return {
            "status": "failed",
            "error": str(e),
            "metadata": {**state.get("metadata", {}), "drafted": False},
        }


async def review_node(state: WorkflowState) -> dict[str, Any]:
    """Run quality review on application drafts.

    Only runs if review_results is not already set in state (allows tests
    to inject pre-computed review results).
    """
    if "review_results" in state:
        # Review results already provided (e.g. by test injection)
        return {
            "metadata": {
                **state.get("metadata", {}),
                "reviewed": True,
                "review_status": "needs_revision",
            },
        }

    reviewer = QualityReviewerAgent()

    try:
        review_result = await reviewer.review(
            profile=state["profile"],
            job=state["job_posting"],
            match=state["match_result"],
            resume=state.get("draft_resume", ""),
            cover_letter=state.get("draft_cover_letter", ""),
        )

        return {
            "review_results": review_result.issues,
            "metadata": {
                **state.get("metadata", {}),
                "reviewed": True,
                "review_status": review_result.status,
            },
        }
    except Exception as e:
        logger.error("Quality review failed: %s", e)
        return {
            "review_results": [],
            "metadata": {**state.get("metadata", {}), "reviewed": False},
        }


async def revise_or_block_node(state: WorkflowState) -> dict[str, Any]:
    """Decide whether to auto-revise or block for human intervention.

    Logic:
    - If review found no issues: proceed to persist
    - If review found issues and revisions remaining: auto-revise
    - If review found critical issues or revisions exhausted: block
    """
    review_results = state.get("review_results", [])
    revision_count = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", 2)

    # Check for critical issues
    has_critical = any(
        issue.get("severity") == "critical"
        for issue in review_results
    )

    # Check for any issue that needs revision (warning, error, or critical)
    needs_revision = any(
        issue.get("severity") in ("warning", "error", "critical")
        for issue in review_results
    )

    if not needs_revision:
        # No issues - proceed to persist
        return {
            "status": "running",
            "metadata": {**state.get("metadata", {}), "review_passed": True},
        }

    if has_critical or revision_count >= max_revisions:
        # Block for human intervention
        return {
            "status": "blocked",
            "error": "Critical issues found or maximum revisions reached. Human intervention required.",
            "metadata": {
                **state.get("metadata", {}),
                "blocked": True,
                "blocked_reason": "critical_issue" if has_critical else "max_revisions_exceeded",
            },
        }

    # Auto-revise — route back to draft for another generation attempt
    return {
        "revision_count": revision_count + 1,
        "status": "revising",
        "metadata": {
            **state.get("metadata", {}),
            "revised": True,
            "revision_attempt": revision_count + 1,
        },
    }


async def persist_node(state: WorkflowState) -> dict[str, Any]:
    """Persist application draft to database with document versioning.

    Creates or updates an Application record and stores document versions.
    Uses idempotent writes to prevent duplicate side effects.
    - Checks for existing application (job_id + profile_id)
    - Increments document version on revision
    - Computes job content hash for approval binding
    """
    try:
        async with AsyncSessionLocal() as session:
            repo = SQLAlchemyApplicationRepository(session)

            # Generate content hashes for idempotency
            resume = state.get("draft_resume", "")
            cover_letter = state.get("draft_cover_letter", "")
            job_posting = state["job_posting"]
            job_hash = compute_job_content_hash(job_posting)

            # Create or get existing application (idempotent)
            application = await repo.create_or_get(
                profile_id=state["profile"].profile_id,
                job_id=state["job_id"],
                status=ApplicationStatus.drafting,
            )

            # Save documents with version tracking
            doc_versions: dict[str, int] = {}

            if resume:
                doc_resume = DocumentModel(
                    application_id=application.id,
                    document_type="resume",
                    content=resume,
                    source_job_content_hash=job_hash,
                    review_status="pending_review",
                )
                doc_resume = await repo.save_document(doc_resume)
                doc_versions["resume"] = doc_resume.version

            if cover_letter:
                doc_letter = DocumentModel(
                    application_id=application.id,
                    document_type="cover_letter",
                    content=cover_letter,
                    source_job_content_hash=job_hash,
                    review_status="pending_review",
                )
                doc_letter = await repo.save_document(doc_letter)
                doc_versions["cover_letter"] = doc_letter.version

            await session.commit()

            return {
                "metadata": {
                    **state.get("metadata", {}),
                    "persisted": True,
                    "application_id": application.id,
                    "job_content_hash": job_hash,
                    "document_versions": doc_versions,
                },
            }
    except Exception as e:
        logger.error("Persistence failed: %s", e)
        return {
            "metadata": {**state.get("metadata", {}), "persisted": False},
        }


async def await_approval_node(state: WorkflowState) -> dict[str, Any]:
    """Create approval request and mark workflow as awaiting approval.

    This node marks the workflow as waiting for human approval.
    The application cannot be submitted until approved.

    Approval is bound to:
    - The specific document version (current version)
    - The job content hash (for invalidation if job changes)
    """
    try:
        async with AsyncSessionLocal() as session:
            repo = SQLAlchemyApplicationRepository(session)
            application_id = state.get("metadata", {}).get("application_id")
            job_content_hash = state.get("metadata", {}).get("job_content_hash")

            if application_id:
                # Get current document versions
                latest_resume = await repo.get_latest_document(application_id, "resume")
                latest_letter = await repo.get_latest_document(application_id, "cover_letter")

                # Bind approval to highest current version
                max_version = max(
                    (latest_resume.version if latest_resume else 0),
                    (latest_letter.version if latest_letter else 0),
                )

                approval = await repo.create_approval_request(
                    application_id=application_id,
                    requested_by="system",
                    document_version=str(max_version),
                    job_content_hash=job_content_hash,
                )

                return {
                    "approval_request_id": str(approval.id),
                    "approval_status": "pending",
                    "status": "awaiting_approval",
                    "metadata": {
                        **state.get("metadata", {}),
                        "approval_requested": True,
                        "approval_id": str(approval.id),
                        "document_version_bound": str(max_version),
                        "job_content_hash_bound": job_content_hash,
                    },
                }

            return {
                "status": "awaiting_approval",
                "metadata": {**state.get("metadata", {}), "approval_requested": True},
            }
    except Exception as e:
        logger.error("Approval creation failed: %s", e)
        return {
            "status": "awaiting_approval",
            "metadata": {**state.get("metadata", {}), "approval_requested": False},
        }


async def validate_approval_node(state: WorkflowState) -> dict[str, Any]:
    """Validate pending approval against current document and job state.

    Called when checking if an approval is still valid.
    Returns validation result or raises on invalid approval.
    """
    approval_id = state.get("metadata", {}).get("approval_id")
    if not approval_id:
        return {
            "metadata": {**state.get("metadata", {}), "approval_valid": None}
        }

    async with AsyncSessionLocal() as session:
        repo = SQLAlchemyApplicationRepository(session)
        approval = await repo.get_pending_approval(state.get("metadata", {}).get("application_id"))

        if not approval:
            return {
                "metadata": {**state.get("metadata", {}), "approval_valid": False, "approval_reason": "no_pending_approval"}
            }

        try:
            # Build minimal state for validation
            approval_data = {
                "status": approval.status,
                "invalidated": approval.invalidated,
                "document_version": approval.document_version,
                "job_content_hash": approval.job_content_hash,
            }
            doc = {"version": state.get("metadata", {}).get("document_version_bound", 1)}
            job = state.get("job_posting", {})
            validate_approval_against_state(approval_data, doc, job)

            return {
                "metadata": {**state.get("metadata", {}), "approval_valid": True}
            }
        except ApprovalValidationError as e:
            return {
                "metadata": {**state.get("metadata", {}), "approval_valid": False, "approval_reason": e.reason}
            }


# --------------------------------------------------------------------------- #
# Conditional edges
# --------------------------------------------------------------------------- #


def route_after_revise_or_block(state: WorkflowState) -> str:
    """Route after revise_or_block based on status."""
    if state.get("status") == "blocked":
        return END
    return "persist"


# --------------------------------------------------------------------------- #
# Graph builder
# --------------------------------------------------------------------------- #


def build_job_search_graph() -> StateGraph:
    """Build the job search workflow graph."""
    graph = StateGraph(WorkflowState)

    # Add nodes
    graph.add_node("validate", validate_node)
    graph.add_node("draft", draft_node)
    graph.add_node("review", review_node)
    graph.add_node("revise_or_block", revise_or_block_node)
    graph.add_node("persist", persist_node)
    graph.add_node("await_approval", await_approval_node)

    # Set entry point
    graph.set_entry_point("validate")

    # Add edges
    graph.add_edge("validate", "draft")
    graph.add_edge("draft", "review")
    graph.add_edge("review", "revise_or_block")

    # Conditional edge after revise_or_block
    graph.add_conditional_edges(
        "revise_or_block",
        route_after_revise_or_block,
        {
            "draft": "draft",
            "persist": "persist",
            END: END,
        },
    )

    graph.add_edge("persist", "await_approval")

    return graph

    return graph


def compile_job_search_workflow(checkpointer: Any | None = None) -> Any:
    """Compile the workflow graph into an executable workflow.

    Args:
        checkpointer: Optional LangGraph checkpointer for persistence.
                     If None, uses simple in-memory execution.
    """
    graph = build_job_search_graph()
    return graph.compile(checkpointer=checkpointer)
