"""SQLAlchemy 2.0 ORM models mirroring the PRD data model (section 8).

Tables:
  candidate_profiles  - versioned candidate profile (FR-01)
  job_postings        - normalized job postings (FR-02, FR-03)
  job_matches         - computed match results (FR-04)
  applications        - application pipeline workspaces (FR-07)
  documents           - versioned application documents (FR-05)
  approval_requests   - human-approval gates (FR-08)
  workflow_runs       - workflow execution records (FR-09)
  audit_events        - observability / audit trail (FR-10)

JSON columns use SQLAlchemy's portable ``JSON`` type so the same models work
on SQLite and PostgreSQL.
"""

from __future__ import annotations

from app.models.audit import AuditEvent
from app.models.application import Application, ApprovalRequest, Document
from app.models.job import JobPosting, JobSourceRecord
from app.models.match import JobMatch
from app.models.profile import CandidateProfile
from app.models.workflow import WorkflowRun

__all__ = [
    "AuditEvent",
    "Application",
    "ApprovalRequest",
    "Document",
    "JobPosting",
    "JobSourceRecord",
    "JobMatch",
    "CandidateProfile",
    "WorkflowRun",
]