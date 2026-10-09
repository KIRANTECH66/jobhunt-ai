"""Job Matcher agent.

Uses the shared Agent Harness + model adapter to evaluate job postings against
a candidate profile. Falls back to deterministic scoring when the LLM is
unavailable or returns invalid output.

The agent:
1. Reads the candidate profile and job posting via tools
2. Invokes the model for semantic comparison
3. Validates the structured output
4. Returns a MatchResult with evidence, gaps, and unknowns
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.harness.harness import AgentHarness, AgentSpec, HarnessResult
from app.schemas.job import JobPosting
from app.schemas.match import MatchEvidence, MatchResult, MatchResultCreate, Recommendation, ScoringConfig
from app.schemas.profile import CandidateProfile
from app.services.scoring import MatchScorer

logger = logging.getLogger(__name__)


class JobMatcherAgent:
    """Agent that evaluates job postings against a candidate profile.

    Uses the shared Agent Harness for safe execution. Falls back to the
    deterministic scorer when the LLM is unavailable or returns invalid
    output.
    """

    def __init__(
        self,
        harness: AgentHarness | None = None,
        deterministic_scorer: MatchScorer | None = None,
        scoring_config: ScoringConfig | None = None,
    ) -> None:
        self.harness = harness or AgentHarness()
        self.deterministic_scorer = deterministic_scorer or MatchScorer(scoring_config)
        self.scoring_config = scoring_config

    @property
    def spec(self) -> AgentSpec:
        """Return the agent specification."""
        return AgentSpec(
            name="job_matcher",
            instructions=(
                "You are a job matcher. Evaluate the candidate profile against the job posting. "
                "Return a JSON object with:\n"
                "- score: number 0-100\n"
                "- recommendation: 'strong_match', 'possible_match', or 'skip'\n"
                "- strengths: list of strings\n"
                "- gaps: list of strings\n"
                "- unknowns: list of strings\n"
                "- evidence: list of {criterion, type, statement, source}\n"
                "Be honest about missing information. Never invent qualifications."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "profile_id": {"type": "string"},
                    "job_posting": {"type": "object"},
                    "profile": {"type": "object"},
                },
                "required": ["job_id", "profile_id", "job_posting", "profile"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "score": {"type": "number"},
                    "recommendation": {"type": "string"},
                    "strengths": {"type": "array"},
                    "gaps": {"type": "array"},
                    "unknowns": {"type": "array"},
                    "evidence": {"type": "array"},
                },
                "required": ["score", "recommendation", "strengths", "gaps", "unknowns", "evidence"],
            },
            tools=["get_candidate_profile", "get_job_posting", "save_match_result"],
            max_retries=2,
        )

    async def match(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        *,
        profile_id: str | None = None,
        job_id: str | None = None,
    ) -> MatchResult:
        """Evaluate a job posting against a candidate profile.

        Returns a MatchResult with the score, recommendation, strengths, gaps,
        unknowns, and evidence. Falls back to deterministic scoring if the LLM
        is unavailable or returns invalid output.
        """
        # Try the LLM-assisted path first
        try:
            result = await self._llm_match(profile, job, profile_id, job_id)
            if result:
                return result
        except Exception as e:
            logger.warning("LLM matching failed, falling back to deterministic: %s", e)

        # Fall back to deterministic scoring
        return self._deterministic_match(profile, job, profile_id, job_id)

    async def _llm_match(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        profile_id: str | None,
        job_id: str | None,
    ) -> MatchResult | None:
        """Use the harness + model adapter for semantic matching."""
        spec = self.spec
        payload = {
            "job_id": job_id or job.id or "unknown",
            "profile_id": profile_id or profile.id or "unknown",
            "job_posting": job.model_dump(),
            "profile": profile.model_dump(),
        }

        result: HarnessResult = await self.harness.run(spec, payload)
        if not result.success:
            logger.warning("LLM matching failed: %s", result.error)
            return None

        output = result.output
        try:
            # Validate that the output has the required fields
            required_fields = ["score", "recommendation", "strengths", "gaps", "unknowns", "evidence"]
            for field in required_fields:
                if field not in output:
                    raise ValueError(f"Missing required field: {field}")

            # Convert the LLM output to a MatchResult
            evidence = [
                MatchEvidence(
                    criterion=e.get("criterion", "unknown"),
                    type=e.get("type", "unknown"),
                    statement=e.get("statement", ""),
                    source=e.get("source", "llm"),
                    location=e.get("location"),
                )
                for e in output.get("evidence", [])
            ]

            return MatchResult(
                job_id=job_id or job.id,
                profile_id=profile_id or profile.id,
                profile_version=profile.version,
                score=float(output.get("score", 0.0)),
                recommendation=Recommendation(output.get("recommendation", "skip")),
                strengths=list(output.get("strengths", [])),
                gaps=list(output.get("gaps", [])),
                unknowns=list(output.get("unknowns", [])),
                evidence=evidence,
                scoring_version="v2-llm-assisted",
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("Invalid LLM output: %s", e)
            return None

    def _deterministic_match(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        profile_id: str | None,
        job_id: str | None,
    ) -> MatchResult:
        """Use the deterministic scorer as a fallback."""
        match_result = self.deterministic_scorer.score_job(profile, job)
        return MatchResult(
            job_id=job_id or job.id,
            profile_id=profile_id or profile.id,
            profile_version=profile.version,
            score=match_result.score,
            recommendation=match_result.recommendation,
            strengths=match_result.strengths,
            gaps=match_result.gaps,
            unknowns=match_result.unknowns,
            evidence=match_result.evidence,
            scoring_version="v1-deterministic",
        )

    async def save_match(
        self,
        match_result: MatchResult,
        job_id: str,
        profile_id: str,
    ) -> str:
        """Save a match result.

        Returns the match ID.
        """
        # In a real implementation, this would call save_match_result via the harness
        # For now, we just return a placeholder ID
        return f"match-{job_id}-{profile_id}"