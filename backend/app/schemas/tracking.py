"""Application tracking schemas (FR-07, FR-08).

Tracks one job through the full pipeline: discovered -> matched ->
shortlisted -> draft-ready -> pending-approval -> submitted -> interview ->
rejected -> offer -> withdrawn. Records timestamps, application IDs,
resume versions, and source references so the pipeline is auditable.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TrackingStatus(str, Enum):
    """Pipeline statuses for an application."""

    discovered = "discovered"
    matched = "matched"
    shortlisted = "shortlisted"
    drafting = "drafting"
    draft_ready = "draft_ready"
    pending_review = "pending_review"
    ready_for_approval = "ready_for_approval"
    approved = "approved"
    submitted = "submitted"
    submission_confirmed = "submission_confirmed"
    interviewing = "interviewing"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"
    archived = "archived"


class TrackingEvent(BaseModel):
    """One state-transition event in an application's lifecycle."""

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(default=None)
    application_id: str
    from_status: Optional[str] = Field(
        default=None, description="Previous status, or None for the initial event."
    )
    to_status: TrackingStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent: Optional[str] = Field(
        default=None, description="Agent or system component that triggered the event."
    )
    reason: Optional[str] = Field(
        default=None, description="Why the transition happened."
    )
    metadata: Optional[dict] = Field(
        default=None, description="Additional context, e.g. resume version, match score."
    )


class TrackingSummary(BaseModel):
    """Aggregate view of the application pipeline."""

    model_config = ConfigDict(extra="allow")

    total: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    submitted: int = 0
    interviewing: int = 0
    offers: int = 0
    rejections: int = 0
    pending_approval: int = 0
    follow_ups_due: int = 0
    last_updated: Optional[datetime] = None


class TrackingRecord(BaseModel):
    """Full tracking record for one application.

    Wraps the persisted Application row plus its lifecycle event history.
    """

    model_config = ConfigDict(extra="allow")

    application_id: str
    job_id: str
    profile_id: str
    status: TrackingStatus
    current_resume_version: Optional[int] = Field(
        default=None, description="Version of the resume currently bound."
    )
    current_cover_letter_version: Optional[int] = Field(
        default=None, description="Version of the cover letter currently bound."
    )
    match_score: Optional[float] = Field(default=None)
    submitted_at: Optional[datetime] = Field(default=None)
    submission_confirmed: bool = Field(
        default=False,
        description="True only when a trusted integration reports success.",
    )
    follow_up_at: Optional[datetime] = Field(default=None)
    events: list[TrackingEvent] = Field(default_factory=list)
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)


class FollowUpReminder(BaseModel):
    """A scheduled follow-up action for an application."""

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(default=None)
    application_id: str
    job_id: str
    status: TrackingStatus
    action: str = Field(description="e.g. 'follow_up', 'check_status', 'withdraw'")
    due_at: datetime
    completed: bool = False
    created_at: Optional[datetime] = Field(default=None)


class TrackingStatusUpdate(BaseModel):
    """Request to change an application's tracking status."""

    model_config = ConfigDict(extra="allow")

    status: TrackingStatus
    reason: Optional[str] = Field(default=None)
    agent: Optional[str] = Field(default=None)
    metadata: Optional[dict] = Field(default=None)
    follow_up_at: Optional[datetime] = Field(default=None)