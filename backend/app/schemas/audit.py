"""Audit event schemas (FR-10).

Audit events record important state transitions and agent actions so the
system is observable and debuggable. Only the minimum necessary data is
stored — never secrets, authentication tokens, or unnecessary raw personal
information.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditOutcome(str, Enum):
    success = "success"
    failure = "failure"
    denied = "denied"
    skipped = "skipped"


class AuditEvent(BaseModel):
    """A persisted audit event."""

    model_config = ConfigDict(extra="allow")

    id: Optional[int] = Field(default=None)
    workflow_id: Optional[str] = Field(default=None)
    agent_name: Optional[str] = Field(default=None)
    action: str = Field(description="What happened, e.g. 'job.ingested'.")
    entity_type: Optional[str] = Field(default=None, description="Type of the affected entity.")
    entity_id: Optional[str] = Field(default=None, description="ID of the affected entity.")
    outcome: AuditOutcome = AuditOutcome.success
    metadata: Optional[dict] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)


class AuditEventCreate(BaseModel):
    """Request body for recording an audit event."""

    model_config = ConfigDict(extra="allow")

    workflow_id: Optional[str] = None
    agent_name: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    outcome: AuditOutcome = AuditOutcome.success
    metadata: Optional[dict] = None