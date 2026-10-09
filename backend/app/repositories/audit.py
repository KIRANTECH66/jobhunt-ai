"""Audit repository.

Manages persistence of audit events for observability and debugging.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent
from app.schemas.audit import AuditEvent as AuditEventSchema, AuditEventCreate, AuditOutcome


class SQLAlchemyAuditRepository:
    """Repository for managing audit events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_audit_event(self, event: AuditEventCreate) -> int:
        """Persist an audit event and return its internal ID."""
        audit_id = uuid.uuid4().int & ((1 << 63) - 1)  # Positive 63-bit integer
        audit_event = AuditEvent(
            id=audit_id,
            workflow_id=event.workflow_id,
            agent_name=event.agent_name,
            action=event.action,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            outcome=event.outcome.value,
            event_metadata=event.metadata,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(audit_event)
        await self.session.commit()
        await self.session.refresh(audit_event)
        return audit_event.id

    async def get_recent(self, limit: int = 100) -> list[AuditEventSchema]:
        """Return the most recent audit events."""
        stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        events = result.scalars().all()
        return [
            AuditEventSchema(
                id=event.id,
                workflow_id=event.workflow_id,
                agent_name=event.agent_name,
                action=event.action,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                outcome=event.outcome,
                metadata=event.event_metadata,
                created_at=event.created_at.isoformat() if event.created_at else None,
            )
            for event in events
        ]

    async def get_by_workflow(self, workflow_id: str) -> list[AuditEventSchema]:
        """Return all audit events for a workflow."""
        stmt = select(AuditEvent).where(AuditEvent.workflow_id == workflow_id).order_by(AuditEvent.created_at)
        result = await self.session.execute(stmt)
        events = result.scalars().all()
        return [
            AuditEventSchema(
                id=event.id,
                workflow_id=event.workflow_id,
                agent_name=event.agent_name,
                action=event.action,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                outcome=event.outcome,
                metadata=event.event_metadata,
                created_at=event.created_at.isoformat() if event.created_at else None,
            )
            for event in events
        ]