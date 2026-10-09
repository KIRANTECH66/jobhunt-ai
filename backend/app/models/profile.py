"""Candidate profile model (FR-01)."""

from __future__ import annotations

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, Timestamped


class CandidateProfile(Timestamped, Base):
    """A versioned candidate profile.

    ``version`` is incremented on every substantive change so documents
    generated from an older profile retain their source context.
    """

    __tablename__ = "candidate_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    profile_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    preferences_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<CandidateProfile id={self.id!r} version={self.version}>"