"""Audit event model (FR-10).

Records important state transitions and agent actions so the system is
observable and debuggable. Only the minimum necessary data is stored — never
secrets, authentication tokens, or unnecessary raw personal information.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, Timestamped


class AuditEvent(Timestamped, Base):
    """A persisted audit event."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), default="success", nullable=False)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<AuditEvent id={self.id} action={self.action!r} outcome={self.outcome!r}>"