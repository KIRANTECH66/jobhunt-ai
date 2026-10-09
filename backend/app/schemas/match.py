"""Job matching schemas (FR-04).

A ``MatchResult`` carries the score plus the evidence behind it. Every major
positive or negative assessment must have supporting evidence, and missing or
uncertain qualifications are recorded as ``unknowns`` rather than assumed.

The score is deterministic for clearly structured criteria (skill overlap,
role keywords, seniority, location, compensation when known). Semantic
comparison is deferred to a later milestone; this module defines the contract
that the LLM-assisted matcher will fill in.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Recommendation(str, Enum):
    strong_match = "strong_match"
    possible_match = "possible_match"
    skip = "skip"


class MatchEvidence(BaseModel):
    """One piece of evidence supporting a positive or negative assessment."""

    model_config = ConfigDict(extra="allow")

    criterion: str = Field(description="Which scoring criterion this evidence addresses.")
    type: str = Field(description="'strength' or 'gap' or 'unknown'.")
    statement: str = Field(description="Plain-language explanation.")
    source: str = Field(description="Where the evidence came from, e.g. profile skill or job requirement.")
    location: Optional[str] = Field(default=None, description="Where in the source the claim applies.")


class ScoringConfig(BaseModel):
    """Configurable scoring weights (FR-04)."""

    model_config = ConfigDict(extra="allow")

    weight_skills: float = 0.35
    weight_role: float = 0.25
    weight_seniority: float = 0.15
    weight_location: float = 0.10
    weight_compensation: float = 0.10
    weight_industry: float = 0.05
    threshold: float = Field(default=60.0, description="Minimum score for application-preparation recommendation.")


class MatchResult(BaseModel):
    """The output of scoring one job against the candidate profile."""

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(default=None)
    job_id: Optional[str] = Field(default=None)
    profile_id: Optional[str] = Field(default=None)
    profile_version: Optional[int] = Field(default=None)
    score: float = Field(ge=0.0, le=100.0)
    recommendation: Recommendation
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    evidence: list[MatchEvidence] = Field(default_factory=list)
    scoring_version: str = Field(default="v1-deterministic")
    created_at: Optional[str] = Field(default=None)

    @property
    def meets_threshold(self) -> bool:
        return self.score >= 60.0


class MatchResultCreate(BaseModel):
    """Request body for persisting a computed match result."""

    model_config = ConfigDict(extra="allow")

    job_id: str
    profile_id: str
    profile_version: int
    score: float = Field(ge=0.0, le=100.0)
    recommendation: Recommendation
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    evidence: list[MatchEvidence] = Field(default_factory=list)
    scoring_version: str = "v1-deterministic"