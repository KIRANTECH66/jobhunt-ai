"""Quality Reviewer agent.

Evaluates generated application materials against quality criteria defined
in FR-06 of the PRD. The reviewer checks for:

1. Unsupported claims
2. Incorrect dates, employers, or titles
3. Skills not present in the verified profile
4. Misalignment with job requirements
5. Missing or inconsistent information
6. Repeated or irrelevant content
7. Formatting and readability issues
8. Grammar problems
9. Unintentional disclosure of sensitive information

Returns a structured review result with status (passed/needs_revision/blocked),
issues with severity, and recommended corrections.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.schemas.job import JobPosting
from app.schemas.match import MatchResult
from app.schemas.profile import CandidateProfile
from app.harness.harness import AgentHarness, AgentSpec

logger = logging.getLogger(__name__)


class QualityReviewResult:
    """Result of a quality review."""

    def __init__(
        self,
        status: str,
        issues: list[dict[str, Any]],
        summary: str = "",
    ) -> None:
        self.status = status  # 'passed', 'needs_revision', 'blocked'
        self.issues = issues
        self.summary = summary

    @property
    def is_blocked(self) -> bool:
        return any(issue.get("severity") == "critical" for issue in self.issues)

    @property
    def needs_revision(self) -> bool:
        return any(issue.get("severity") in ("warning", "error") for issue in self.issues)


class QualityReviewerAgent:
    """Agent that evaluates application materials for quality.

    Uses both deterministic checks and LLM-assisted review. Returns a
    QualityReviewResult with the overall status and detailed findings.
    """

    def __init__(
        self,
        harness: AgentHarness | None = None,
    ) -> None:
        self.harness = harness or AgentHarness()

    async def review(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        match: MatchResult,
        resume: str,
        cover_letter: str,
    ) -> QualityReviewResult:
        """Run quality review on application materials.

        Performs both deterministic checks and LLM-assisted review, combining
        the results into a single QualityReviewResult.
        """
        # Run deterministic checks
        deterministic_issues = self._deterministic_checks(profile, job, resume, cover_letter)

        # Run LLM-assisted review
        llm_issues = await self._llm_review(profile, job, resume, cover_letter)

        # Combine and deduplicate issues
        all_issues = deterministic_issues + llm_issues
        unique_issues = self._deduplicate_issues(all_issues)

        # Determine overall status
        if any(issue["severity"] == "critical" for issue in unique_issues):
            status = "blocked"
        elif any(issue["severity"] in ("warning", "error") for issue in unique_issues):
            status = "needs_revision"
        else:
            status = "passed"

        return QualityReviewResult(
            status=status,
            issues=unique_issues,
            summary=f"Found {len(unique_issues)} issue(s): {', '.join(set(i['category'] for i in unique_issues))}",
        )

    def _deterministic_checks(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        resume: str,
        cover_letter: str,
    ) -> list[dict[str, Any]]:
        """Run deterministic quality checks."""
        issues = []

        # Check 1: Unsupported claims (skills not in profile)
        profile_skills = {s.name.lower() for s in profile.profile_data.skills}
        resume_skills = self._extract_skills(resume)
        unverified_skills = resume_skills - profile_skills
        for skill in unverified_skills:
            issues.append({
                "category": "unsupported_claim",
                "severity": "critical",
                "message": f"Skill '{skill}' appears in resume but is not in verified profile",
                "location": "resume",
                "recommendation": f"Remove '{skill}' or verify with candidate",
            })

        # Check 2: Missing information
        if not profile.profile_data.work_experience:
            issues.append({
                "category": "missing_info",
                "severity": "warning",
                "message": "No work experience in profile",
                "location": "profile",
                "recommendation": "Ask candidate for work experience details",
            })

        if not profile.profile_data.skills:
            issues.append({
                "category": "missing_info",
                "severity": "warning",
                "message": "No skills in profile",
                "location": "profile",
                "recommendation": "Ask candidate for skills",
            })

        # Check 3: Date format validation
        date_pattern = r'\b(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{4})\b'
        dates_in_resume = re.findall(date_pattern, resume)
        dates_in_cover = re.findall(date_pattern, cover_letter)
        for date_str in dates_in_resume + dates_in_cover:
            if not self._is_valid_date(date_str):
                issues.append({
                    "category": "invalid_date",
                    "severity": "error",
                    "message": f"Invalid date format: {date_str}",
                    "location": "document",
                    "recommendation": "Use YYYY-MM-DD format",
                })

        # Check 4: PII disclosure
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        if re.search(email_pattern, resume):
            issues.append({
                "category": "pii_disclosure",
                "severity": "warning",
                "message": "Email address found in resume",
                "location": "resume",
                "recommendation": "Remove email or ensure it's approved for disclosure",
            })
        if re.search(phone_pattern, resume):
            issues.append({
                "category": "pii_disclosure",
                "severity": "warning",
                "message": "Phone number found in resume",
                "location": "resume",
                "recommendation": "Remove phone or ensure it's approved for disclosure",
            })

        return issues

    async def _llm_review(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        resume: str,
        cover_letter: str,
    ) -> list[dict[str, Any]]:
        """Run LLM-assisted quality review."""
        try:
            prompt = f"""Review these application materials for quality.

CANDIDATE PROFILE:
{profile.profile_data.summary or 'No summary provided'}

JOB DESCRIPTION:
{job.description or 'No description provided'}

RESUME:
{resume[:2000]}

COVER LETTER:
{cover_letter[:2000]}

Return a JSON array of issues found, with each issue having:
- category: 'unsupported_claim', 'incorrect_fact', 'misalignment', 'grammar', 'formatting', 'pii'
- severity: 'critical', 'error', 'warning'
- message: description of the issue
- location: 'resume', 'cover_letter', or 'both'
- recommendation: suggested correction

Return an empty array if no issues found."""

            response = await self.harness.model_adapter.generate(prompt)
            issues_text = response.content
            issues = self._parse_review_issues(issues_text)
            return issues
        except Exception as e:
            logger.warning("LLM quality review failed: %s", e)
            return []

    def _parse_review_issues(self, text: str) -> list[dict[str, Any]]:
        """Parse LLM review output into structured issues."""
        import json
        try:
            # Try to extract JSON from the response
            if "[" in text:
                start = text.index("[")
                end = text.rindex("]") + 1
                issues = json.loads(text[start:end])
                return issues
        except (json.JSONDecodeError, ValueError):
            pass
        return []

    def _extract_skills(self, text: str) -> set[str]:
        """Extract skills mentioned in text."""
        # Simple extraction - in production this would use NLP
        skill_keywords = ["python", "java", "javascript", "react", "sql", "aws", "docker", "kubernetes"]
        text_lower = text.lower()
        return {s for s in skill_keywords if s in text_lower}

    def _is_valid_date(self, date_str: str) -> bool:
        """Check if a date string is in a valid format."""
        # Accept YYYY-MM-DD, MM/DD/YYYY, or 4-digit year
        patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{4}',              # YYYY
        ]
        return any(re.match(p, date_str) for p in patterns)

    def _deduplicate_issues(self, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate issues based on message and location."""
        seen = set()
        unique = []
        for issue in issues:
            key = (issue["message"], issue.get("location", ""))
            if key not in seen:
                seen.add(key)
                unique.append(issue)
        return unique