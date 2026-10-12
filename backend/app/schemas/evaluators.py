"""Evaluation schemas for resume evaluators (Recruiter, Hiring Manager, ATS).

All three evaluators assess the same job description and the same current
resume version. Each returns structured findings with evidence, severity,
and recommended changes so the Resume Agent can act on them.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    """Severity of an evaluation finding."""

    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class FindingCategory(str, Enum):
    """Categories of evaluation findings."""

    # Recruiter
    relevance = "relevance"
    required_vs_preferred = "required_vs_preferred"
    narrative = "narrative"
    seniority = "seniority"
    unsupported_claim = "unsupported_claim"
    readability = "readability"
    # Hiring Manager
    technical_depth = "technical_depth"
    impact_ownership = "impact_ownership"
    competency_gap = "competency_gap"
    project_relevance = "project_relevance"
    # ATS
    keyword_coverage = "keyword_coverage"
    section_structure = "section_structure"
    formatting = "formatting"
    parseability = "parseability"
    ambiguous_terminology = "ambiguous_terminology"
    missing_section = "missing_section"
    # Cross-cutting
    factual_consistency = "factual_consistency"
    pii_disclosure = "pii_disclosure"


class EvaluationFinding(BaseModel):
    """One structured finding from an evaluator.

    Every finding carries:
    - ``evidence``: the exact quote or fact that supports the finding
    - ``recommendation``: an actionable change the Resume Agent can make
    - ``confidence``: how certain the evaluator is (0.0-1.0)
    """

    model_config = ConfigDict(extra="allow")

    evaluator: str = Field(description="Which evaluator produced this finding.")
    category: FindingCategory
    severity: Severity
    section: Optional[str] = Field(
        default=None,
        description="Resume section the finding applies to, e.g. 'experience', 'skills'.",
    )
    message: str = Field(description="Plain-language description of the issue.")
    evidence: str = Field(
        default="",
        description="Quote from the resume or JD that supports this finding.",
    )
    recommendation: str = Field(description="Actionable change to address the finding.")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Evaluator confidence in this finding."
    )


class EvaluatorResult(BaseModel):
    """Result from one evaluator against a specific resume version."""

    model_config = ConfigDict(extra="allow")

    evaluator: str = Field(description="Evaluator name: 'recruiter', 'hiring_manager', 'ats'.")
    evaluator_version: str = Field(default="v1")
    persona: Optional[str] = Field(
        default=None,
        description="For hiring_manager: which persona was used.",
    )
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    summary: str = Field(default="")
    findings: list[EvaluationFinding] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    """Aggregated evaluation report from all evaluators.

    Produced by the Resume Improvement Loop after running all evaluators
    against the same resume version and JD.
    """

    model_config = ConfigDict(extra="allow")

    resume_version: int
    job_id: str
    job_content_hash: Optional[str] = None
    evaluator_results: list[EvaluatorResult] = Field(default_factory=list)
    aggregated_score: float = Field(default=0.0, ge=0.0, le=100.0)
    previous_score: Optional[float] = Field(
        default=None, description="Score from the previous iteration, for delta tracking."
    )
    score_delta: Optional[float] = Field(
        default=None, description="Change in aggregated score vs previous iteration."
    )
    critical_findings: list[EvaluationFinding] = Field(default_factory=list)
    high_priority_findings: list[EvaluationFinding] = Field(default_factory=list)
    all_findings: list[EvaluationFinding] = Field(default_factory=list)
    stop_reason: Optional[str] = Field(
        default=None,
        description="Why the improvement loop stopped, if known.",
    )
    iteration: int = 0
    max_iterations: int = 2

    @property
    def has_critical(self) -> bool:
        return len(self.critical_findings) > 0

    @property
    def has_actionable_findings(self) -> bool:
        return len(self.high_priority_findings) > 0

    @property
    def score_improved(self) -> bool:
        if self.score_delta is None:
            return False
        return self.score_delta > 0


class ImprovementLoopConfig(BaseModel):
    """Configuration for the bounded resume improvement loop."""

    model_config = ConfigDict(extra="allow")

    max_iterations: int = Field(default=2, description="Maximum revision iterations.")
    score_improvement_threshold: float = Field(
        default=2.0,
        description="Minimum score improvement to continue iterating.",
    )
    min_aggregate_score: float = Field(
        default=70.0,
        description="Target aggregate score; loop stops when reached.",
    )
    critical_severity_blocks: bool = Field(
        default=True,
        description="If True, critical findings block progress until resolved.",
    )
    deduplicate_feedback: bool = Field(
        default=True,
        description="Suppress duplicate findings across iterations.",
    )