"""Job posting schemas (FR-02, FR-03).

A ``NormalizedJob`` is what the system works with after a source adapter has
turned a raw posting into the common schema. ``JobSourceRecord`` tracks the
provenance of each copy of a posting so deduplication can attribute it back to
a specific source and external identifier.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(str, Enum):
    """Lifecycle status of a job posting record."""

    active = "active"
    expired = "expired"
    unavailable = "unavailable"
    unknown = "unknown"


class WorkArrangement(str, Enum):
    onsite = "onsite"
    hybrid = "hybrid"
    remote = "remote"
    flexible = "flexible"


class EmploymentType(str, Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"
    temporary = "temporary"


class JobSourceRecord(BaseModel):
    """One copy of a posting as seen by one source."""

    model_config = ConfigDict(extra="allow")

    source: str = Field(description="Identifier of the permitted source, e.g. 'fixture'.")
    external_id: Optional[str] = Field(
        default=None, description="Source-specific job identifier, when available."
    )
    url: Optional[str] = Field(default=None, description="Original URL on the source.")
    posted_at: Optional[datetime] = Field(default=None)
    retrieved_at: datetime = Field(description="When this copy was retrieved.")
    raw: Optional[dict] = Field(
        default=None, description="Original raw payload, retained for provenance."
    )


class JobPosting(BaseModel):
    """The normalized, common-schema view of a job posting."""

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(default=None, description="Stable internal job ID.")
    source: Optional[str] = Field(default=None, description="Primary source identifier.")
    external_id: Optional[str] = Field(default=None)
    company: str
    title: str
    location: Optional[str] = Field(default=None)
    work_arrangement: Optional[WorkArrangement] = Field(default=None)
    employment_type: Optional[EmploymentType] = Field(default=None)
    description: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)
    posted_at: Optional[datetime] = Field(default=None)
    first_seen_at: Optional[datetime] = Field(default=None)
    last_verified_at: Optional[datetime] = Field(default=None)
    content_hash: Optional[str] = Field(default=None)
    status: JobStatus = JobStatus.unknown
    sources: list[JobSourceRecord] = Field(default_factory=list)


class NormalizedJob(BaseModel):
    """A job plus the provenance of its source copies, as returned by ingestion."""

    model_config = ConfigDict(extra="allow")

    job: JobPosting
    sources: list[JobSourceRecord] = Field(default_factory=list)
    is_new: bool = Field(default=False, description="True when this created a new job record.")
    matched_existing_id: Optional[str] = Field(
        default=None, description="Existing internal job ID when dedup matched."
    )


class JobPostingCreate(BaseModel):
    """Request body for direct job posting creation (mainly used by fixtures/tests)."""

    model_config = ConfigDict(extra="allow")

    company: str
    title: str
    location: Optional[str] = None
    work_arrangement: Optional[WorkArrangement] = None
    employment_type: Optional[EmploymentType] = None
    description: Optional[str] = None
    url: Optional[str] = None
    posted_at: Optional[datetime] = None
    source: str = "fixture"
    external_id: Optional[str] = None