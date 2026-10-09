"""Job match model (FR-04)."""

from __future__ import annotations

from sqlalchemy import JSON, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, Timestamped


class JobMatch(Timestamped, Base):
    """A computed match result for one job against one profile version."""

    __tablename__ = "job_matches"
    __table_args__ = (
        Index("uq_match_job_profile", "job_id", "profile_id", "profile_version", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), nullable=False)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(32), nullable=False)
    strengths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    gaps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    unknowns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    scoring_version: Mapped[str] = mapped_column(String(32), default="v1-deterministic", nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<JobMatch id={self.id!r} job_id={self.job_id!r} score={self.score}>"