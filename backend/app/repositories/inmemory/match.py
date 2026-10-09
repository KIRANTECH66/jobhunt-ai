"""In-memory match repository for testing."""

from __future__ import annotations

from typing import Any

from app.schemas.match import MatchResult


class InMemoryMatchRepository:
    """In-memory implementation of the match repository for testing."""

    def __init__(self) -> None:
        self.matches: dict[str, dict] = {}
        self.next_id = 1

    async def save_match_result(self, match_result: MatchResult | dict) -> str:
        """Persist a match result and return its internal ID.

        Accepts either a MatchResult model or a plain dict for flexibility
        in tests.
        """
        match_id = str(self.next_id)
        self.next_id += 1

        if isinstance(match_result, dict):
            match_data = match_result.copy()
            match_data["id"] = match_id
        else:
            match_data = {
                "id": match_id,
                "job_id": match_result.job_id,
                "profile_id": match_result.profile_id,
                "profile_version": match_result.profile_version,
                "score": match_result.score,
                "recommendation": match_result.recommendation.value,
                "strengths": match_result.strengths,
                "gaps": match_result.gaps,
                "unknowns": match_result.unknowns,
                "evidence": [e.model_dump() for e in match_result.evidence],
                "scoring_version": match_result.scoring_version,
            }

        self.matches[match_id] = match_data
        return match_id

    async def get_by_job_id(self, job_id: str) -> dict | None:
        """Return the latest match result for a job."""
        # Find all matches for this job and return the most recent one
        job_matches = [
            (match_id, match)
            for match_id, match in self.matches.items()
            if match.get("job_id") == job_id
        ]
        if not job_matches:
            return None
        # Return the match with the highest ID (most recent)
        latest_match_id, latest_match = max(job_matches, key=lambda x: int(x[0]))
        return latest_match