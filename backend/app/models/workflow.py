"""Workflow run model (FR-09).

Minimal for Milestone 1: the schema exists so the orchestration milestone can
persist workflow state and checkpoints without redesigning the table.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, Timestamped


class WorkflowRun(Timestamped, Base):
    """A workflow execution record."""

    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_type: Mapped[str] = mapped_column(String(64), default="job_search", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    state_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    checkpoint_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<WorkflowRun id={self.id!r} type={self.workflow_type!r} status={self.status!r}>"