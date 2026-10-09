"""Job posting and source-record models (FR-02, FR-03)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, func, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._base import Base, Timestamped


class JobSourceRecord(Timestamped, Base):
    """One copy of a posting as seen by one source.

    A single job posting may have many source records (it appears on multiple
    sources, or was re-verified). The uniqueness constraint is on
    (source, external_id) when an external ID exists.
    """

    __tablename__ = "job_source_records"
    __table_args__ = (
        # Enforce uniqueness for (source, external_id) when an external ID exists.
        # SQLite allows multiple NULLs in a unique index, so this is safe there too.
        Index(
            "uq_source_external",
            "source",
            "external_id",
            unique=True,
            sqlite_where=text("external_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_postings.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    job: Mapped["JobPosting"] = relationship(back_populates="sources")


class JobPosting(Timestamped, Base):
    """A normalized job posting.

    The canonical record; ``content_hash`` is a stable fingerprint of the
    normalized content used as a secondary dedup signal.
    """

    __tablename__ = "job_postings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_arrangement: Mapped[str | None] = mapped_column(String(32), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    is_expired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    sources: Mapped[list["JobSourceRecord"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("uq_job_external", "source", "external_id", unique=True),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<JobPosting id={self.id!r} company={self.company!r} title={self.title!r}>"