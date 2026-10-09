"""Pydantic v2 schemas for the JobHunt AI backend.

These are the typed contracts used by the API, the services, and the future
agent harness. They mirror the PRD data model (section 8) but are kept
decoupled from the SQLAlchemy models so the wire/API shape can evolve
independently of the persistence layer.
"""

from __future__ import annotations

from app.schemas.audit import AuditEvent, AuditEventCreate
from app.schemas.application import (
    Application,
    ApplicationCreate,
    ApplicationStatus,
    ApplicationStatusUpdate,
    ApprovalDecision,
    ApprovalRequest,
    Document,
    DocumentType,
)
from app.schemas.job import (
    EmploymentType,
    JobPosting,
    JobPostingCreate,
    JobSourceRecord,
    JobStatus,
    NormalizedJob,
    WorkArrangement,
)
from app.schemas.match import (
    MatchEvidence,
    MatchResult,
    MatchResultCreate,
    Recommendation,
    ScoringConfig,
)
from app.schemas.profile import (
    CandidateProfile,
    ContactInfo,
    Education,
    FactSource,
    ProfileData,
    ProfilePreferences,
    ProfileUpdate,
    Project,
    Skill,
    WorkExperience,
)

__all__ = [
    "AuditEvent",
    "AuditEventCreate",
    "Application",
    "ApplicationCreate",
    "ApplicationStatus",
    "ApplicationStatusUpdate",
    "ApprovalDecision",
    "ApprovalRequest",
    "Document",
    "DocumentType",
    "EmploymentType",
    "JobPosting",
    "JobPostingCreate",
    "JobSourceRecord",
    "JobStatus",
    "NormalizedJob",
    "WorkArrangement",
    "MatchEvidence",
    "MatchResult",
    "MatchResultCreate",
    "Recommendation",
    "ScoringConfig",
    "CandidateProfile",
    "ContactInfo",
    "Education",
    "FactSource",
    "ProfileData",
    "ProfilePreferences",
    "ProfileUpdate",
    "Project",
    "Skill",
    "WorkExperience",
]