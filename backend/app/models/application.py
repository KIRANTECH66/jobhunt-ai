"""Application, document, and approval models (FR-05, FR-07, FR-08)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._base import Base, Timestamped


class Application(Timestamped, Base):
    """An application workspace tracking one job through the pipeline (FR-07)."""

    __tablename__ = "applications"
    __table_args__ = (
        # One application workspace per (job, profile) pair.
        Index("uq_application_job_profile", "job_id", "profile_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_postings.id"), nullable=False)
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_profiles.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="discovered", nullable=False)
    current_resume_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    current_cover_letter_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["ApprovalRequest"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Application id={self.id!r} job_id={self.job_id!r} status={self.status!r}>"


class Document(Timestamped, Base):
    """A versioned application document. Immutable after approval (FR-05)."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    application_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("applications.id"), nullable=True)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_job_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provenance: Mapped[dict | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="not_reviewed", nullable=False)
    review_issues: Mapped[list | None] = mapped_column(Text, nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    application: Mapped["Application | None"] = relationship(back_populates="documents")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Document id={self.id!r} type={self.document_type!r} version={self.version}>"


class ApprovalRequest(Timestamped, Base):
    """A human-approval gate bound to a specific job and document version (FR-08).

    For the MVP, approval never triggers external submission. The user reviews
    the materials and submits the application independently.
    """

    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    application_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("applications.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), default="submit_application", nullable=False)
    document_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    application: Mapped["Application | None"] = relationship(back_populates="approvals")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<ApprovalRequest id={self.id!r} status={self.status!r} decision={self.decision!r}>"