"""Match repository.

Manages persistence of job match results.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobMatch
from app.schemas.match import MatchResult


class SQLAlchemyMatchRepository:
    """Repository for managing job match results."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_match_result(self, match_result: MatchResult) -> str:
        """Persist a match result and return its internal ID."""
        match_id = str(uuid.uuid4())
        match = JobMatch(
            id=match_id,
            job_id=match_result.job_id,
            profile_id=match_result.profile_id,
            profile_version=match_result.profile_version,
            score=match_result.score,
            recommendation=match_result.recommendation.value,
            strengths=match_result.strengths,
            gaps=match_result.gaps,
            unknowns=match_result.unknowns,
            evidence=[e.model_dump() for e in match_result.evidence],
            scoring_version=match_result.scoring_version,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(match)
        await self.session.commit()
        await self.session.refresh(match)
        return match.id

    async def get_by_job_id(self, job_id: str) -> MatchResult | None:
        """Return the latest match result for a job."""
        stmt = select(JobMatch).where(JobMatch.job_id == job_id).order_by(JobMatch.created_at.desc())
        result = await self.session.execute(stmt)
        match = result.scalar_one_or_none()
        if match is None:
            return None
        return MatchResult(
            id=match.id,
            job_id=match.job_id,
            profile_id=match.profile_id,
            profile_version=match.profile_version,
            score=match.score,
            recommendation=match.recommendation,
            strengths=match.strengths,
            gaps=match.gaps,
            unknowns=match.unknowns,
            evidence=match.evidence,
            scoring_version=match.scoring_version,
            created_at=match.created_at.isoformat() if match.created_at else None,
        )