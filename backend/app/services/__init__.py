"""Service layer.

Pure-logic services that the orchestrator and API call into. They are
intentionally free of framework concerns (no FastAPI, no SQLAlchemy sessions)
so they can be unit-tested directly.
"""

from __future__ import annotations

from app.services.dedup import DedupService
from app.services.normalization import NormalizationService
from app.services.scoring import MatchScorer

__all__ = ["DedupService", "NormalizationService", "MatchScorer"]