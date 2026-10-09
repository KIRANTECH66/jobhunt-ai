"""Application, document, and approval schemas (FR-05–FR-08).

These are intentionally minimal for Milestone 1: the application pipeline,
document generation, and human-approval gate are not yet implemented. The
schemas exist so the data model is defined and Milestone 3 can build on them
without redesigning the contracts.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ApplicationStatus(str, Enum):
    """Pipeline statuses (FR-07)."""

    discovered = "discovered"
    shortlisted = "shortlisted"
    drafting = "drafting"
    pending_review = "pending_review"
    ready_for_approval = "ready_for_approval"
    approved = "approved"
    applied = "applied"
    interviewing = "interviewing"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"
    archived = "archived"


class DocumentType(str, Enum):
    resume = "resume"
    cover_letter = "cover_letter"
    application_notes = "application_notes"


class DocumentReviewStatus(str, Enum):
    not_reviewed = "not_reviewed"
    passed = "passed"
    needs_revision = "needs_revision"
    blocked = "blocked"


class Document(BaseModel):
    """A versioned application document. Immutable after approval."""

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(default=None)
    application_id: Optional[str] = Field(default=None)
    document_type: DocumentType
    version: int = Field(default=1, description="Monotonically increasing per document type.")
    content: str = Field(default="")
    source_profile_version: Optional[int] = Field(default=None)
    source_job_content_hash: Optional[str] = Field(default=None)
    provenance: Optional[dict] = Field(
        default=None, description="Structured claim provenance where practical."
    )
    review_status: DocumentReviewStatus = DocumentReviewStatus.not_reviewed
    review_issues: list[dict] = Field(default_factory=list)
    created_at: Optional[datetime] = Field(default=None)


class ApplicationCreate(BaseModel):
    """Create an application workspace for a job."""

    model_config = ConfigDict(extra="allow")

    job_id: str
    profile_id: str
    notes: Optional[str] = Field(default=None)


class ApplicationStatusUpdate(BaseModel):
    """Manual status change by the user."""

    model_config = ConfigDict(extra="allow")

    status: ApplicationStatus
    note: Optional[str] = Field(default=None)
    follow_up_at: Optional[datetime] = Field(default=None)


class Application(BaseModel):
    """An application workspace tracking one job through the pipeline."""

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(default=None)
    job_id: Optional[str] = Field(default=None)
    profile_id: Optional[str] = Field(default=None)
    status: ApplicationStatus = ApplicationStatus.discovered
    current_resume_document_id: Optional[str] = Field(default=None)
    current_cover_letter_document_id: Optional[str] = Field(default=None)
    applied_at: Optional[datetime] = Field(default=None)
    follow_up_at: Optional[datetime] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)


class ApprovalDecision(str, Enum):
    approve = "approve"
    reject = "reject"
    request_changes = "request_changes"


class ApprovalRequest(BaseModel):
    """A human-approval gate bound to a specific job and document version.

    For the MVP, approval never triggers external submission. The user reviews
    the materials and submits the application independently.
    """

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(default=None)
    application_id: Optional[str] = Field(default=None)
    action: str = Field(default="submit_application")
    document_version: Optional[str] = Field(default=None)
    job_content_hash: Optional[str] = Field(default=None)
    status: str = Field(default="pending")  # pending, approved, rejected, superseded
    decision: Optional[ApprovalDecision] = Field(default=None)
    decided_at: Optional[datetime] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)