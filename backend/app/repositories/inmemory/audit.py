"""In-memory audit repository for testing."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.audit import AuditEvent, AuditEventCreate, AuditOutcome


class InMemoryAuditRepository:
    """In-memory implementation of the audit repository for testing."""

    def __init__(self) -> None:
        self.events: dict[int, dict] = {}
        self.next_id = 1

    async def save_audit_event(self, event: AuditEventCreate | dict) -> int:
        """Persist an audit event and return its internal ID.

        Accepts either an AuditEventCreate model or a plain dict for flexibility
        in tests.
        """
        audit_id = self.next_id
        self.next_id += 1

        if isinstance(event, dict):
            event_data = event.copy()
            event_data["id"] = audit_id
            event_data.setdefault("workflow_id", None)
            event_data.setdefault("agent_name", None)
            event_data.setdefault("outcome", "success")
            event_data.setdefault("metadata", None)
        else:
            event_data = {
                "id": audit_id,
                "workflow_id": event.workflow_id,
                "agent_name": event.agent_name,
                "action": event.action,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "outcome": event.outcome.value,
                "event_metadata": event.metadata,
                "created_at": datetime.now(timezone.utc),
            }

        self.events[audit_id] = event_data
        return audit_id

    async def get_recent(self, limit: int = 100) -> list[dict]:
        """Return the most recent audit events."""
        # Sort by ID descending (most recent first) and limit
        sorted_events = sorted(self.events.items(), key=lambda x: x[0], reverse=True)
        return [event for _, event in sorted_events[:limit]]

    async def get_by_workflow(self, workflow_id: str) -> list[dict]:
        """Return all audit events for a workflow."""
        return [
            event
            for event in self.events.values()
            if event.get("workflow_id") == workflow_id
        ]