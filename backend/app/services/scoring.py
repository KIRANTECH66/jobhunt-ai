"""Deterministic job matching scorer (FR-04).

Implements the weighted scoring model described in the PRD:
- Relevant skills and experience: 35%
- Role and responsibility alignment: 25%
- Seniority alignment: 15%
- Location and work arrangement: 10%
- Compensation alignment when known: 10%
- Industry or domain preference: 5%

The scorer is deterministic for clearly structured criteria and returns
evidence, gaps, and unknowns for transparency. It never interprets the score
as a probability of receiving an interview.
"""

from __future__ import annotations

import re
from typing import Any

from app.config import settings
from app.schemas.job import JobPosting
from app.schemas.match import MatchEvidence, MatchResult, Recommendation, ScoringConfig
from app.schemas.profile import CandidateProfile, Skill, WorkExperience


class MatchScorer:
    """Deterministic job matcher using weighted criteria."""

    def __init__(self, config: ScoringConfig | None = None) -> None:
        self.config = config or ScoringConfig(
            weight_skills=settings.weight_skills,
            weight_role=settings.weight_role,
            weight_seniority=settings.weight_seniority,
            weight_location=settings.weight_location,
            weight_compensation=settings.weight_compensation,
            weight_industry=settings.weight_industry,
            threshold=settings.job_match_threshold,
        )

    def score_job(
        self, profile: CandidateProfile, job: JobPosting
    ) -> MatchResult:
        """Score a job posting against a candidate profile.

        Returns a MatchResult with the score (0-100), recommendation,
        strengths, gaps, unknowns, and evidence.
        """
        # Initialize accumulators
        score = 0.0
        strengths: list[str] = []
        gaps: list[str] = []
        unknowns: list[str] = []
        evidence: list[MatchEvidence] = []

        # 1. Relevant skills and experience (35%)
        skills_score, skills_strengths, skills_gaps, skills_unknowns, skills_evidence = (
            self._score_skills(profile, job)
        )
        score += skills_score * self.config.weight_skills
        strengths.extend(skills_strengths)
        gaps.extend(skills_gaps)
        unknowns.extend(skills_unknowns)
        evidence.extend(skills_evidence)

        # 2. Role and responsibility alignment (25%)
        role_score, role_strengths, role_gaps, role_unknowns, role_evidence = (
            self._score_role(profile, job)
        )
        score += role_score * self.config.weight_role
        strengths.extend(role_strengths)
        gaps.extend(role_gaps)
        unknowns.extend(role_unknowns)
        evidence.extend(role_evidence)

        # 3. Seniority alignment (15%)
        seniority_score, seniority_strengths, seniority_gaps, seniority_unknowns, seniority_evidence = (
            self._score_seniority(profile, job)
        )
        score += seniority_score * self.config.weight_seniority
        strengths.extend(seniority_strengths)
        gaps.extend(seniority_gaps)
        unknowns.extend(seniority_unknowns)
        evidence.extend(seniority_evidence)

        # 4. Location and work arrangement (10%)
        location_score, location_strengths, location_gaps, location_unknowns, location_evidence = (
            self._score_location(profile, job)
        )
        score += location_score * self.config.weight_location
        strengths.extend(location_strengths)
        gaps.extend(location_gaps)
        unknowns.extend(location_unknowns)
        evidence.extend(location_evidence)

        # 5. Compensation alignment when known (10%)
        compensation_score, compensation_strengths, compensation_gaps, compensation_unknowns, compensation_evidence = (
            self._score_compensation(profile, job)
        )
        score += compensation_score * self.config.weight_compensation
        strengths.extend(compensation_strengths)
        gaps.extend(compensation_gaps)
        unknowns.extend(compensation_unknowns)
        evidence.extend(compensation_evidence)

        # 6. Industry or domain preference (5%)
        industry_score, industry_strengths, industry_gaps, industry_unknowns, industry_evidence = (
            self._score_industry(profile, job)
        )
        score += industry_score * self.config.weight_industry
        strengths.extend(industry_strengths)
        gaps.extend(industry_gaps)
        unknowns.extend(industry_unknowns)
        evidence.extend(industry_evidence)

        # Clamp score to 0-100
        score = max(0.0, min(100.0, score * 100.0))

        # Determine recommendation
        if score >= self.config.threshold:
            recommendation = Recommendation.strong_match
        elif score >= 40.0:  # Possible match threshold
            recommendation = Recommendation.possible_match
        else:
            recommendation = Recommendation.skip

        return MatchResult(
            score=round(score, 2),
            recommendation=recommendation,
            strengths=strengths,
            gaps=gaps,
            unknowns=unknowns,
            evidence=evidence,
            scoring_version="v1-deterministic",
        )

    # --------------------------------------------------------------------- #
    # Individual scoring criteria
    # --------------------------------------------------------------------- #

    def _score_skills(
        self, profile: CandidateProfile, job: JobPosting
    ) -> tuple[float, list[str], list[str], list[str], list[MatchEvidence]]:
        """Score skills match (0-1.0)."""
        if not profile.profile_data.skills:
            return 0.0, [], ["No skills in profile"], [], []

        # Extract skills from job description (simple keyword matching)
        job_text = f"{job.title} {job.description or ''}".lower()
        profile_skills = {s.name.lower(): s for s in profile.profile_data.skills}

        matched_skills = []
        missing_skills = []

        for skill_name, skill_obj in profile_skills.items():
            if skill_name in job_text:
                matched_skills.append(skill_name)
            else:
                missing_skills.append(skill_name)

        # Simple ratio: matched / total profile skills
        score = len(matched_skills) / max(len(profile_skills), 1)
        score = min(1.0, score)  # Cap at 1.0

        strengths = [f"Has {skill}" for skill in matched_skills[:3]]  # Limit evidence
        gaps = [f"Missing {skill}" for skill in missing_skills[:3]]
        unknowns = []  # No unknowns for skills - we know what's in profile
        evidence = [
            MatchEvidence(
                criterion="skills",
                type="strength" if matched_skills else "gap",
                statement=f"Found {len(matched_skills)} matching skills: {', '.join(matched_skills[:3])}{'...' if len(matched_skills) > 3 else ''}",
                source="profile skills vs job description",
            )
            if matched_skills or missing_skills
            else MatchEvidence(
                criterion="skills",
                type="unknown",
                statement="No skills found in profile",
                source="profile",
            )
        ]

        return score, strengths, gaps, unknowns, evidence

    def _score_role(
        self, profile: CandidateProfile, job: JobPosting
    ) -> tuple[float, list[str], list[str], list[str], list[MatchEvidence]]:
        """Score role alignment (0-1.0)."""
        if not profile.preferences_data.target_titles:
            return 0.5, [], ["No target titles specified"], [], []

        job_title_lower = job.title.lower()
        matches = []
        for target in profile.preferences_data.target_titles:
            if target.lower() in job_title_lower or job_title_lower in target.lower():
                matches.append(target)

        score = min(1.0, len(matches) / max(len(profile.preferences_data.target_titles), 1)) if matches else 0.0

        strengths = [f"Role matches target: {job.title}"] if matches else []
        gaps = [f"Role does not match target titles: {', '.join(profile.preferences_data.target_titles[:3])}"] if not matches else []
        unknowns = []
        evidence = [
            MatchEvidence(
                criterion="role",
                type="strength" if matches else "gap",
                statement=f"Job title '{job.title}' vs target titles {profile.preferences_data.target_titles}",
                source="profile preferences vs job title",
            )
        ]

        return score, strengths, gaps, unknowns, evidence

    def _score_seniority(
        self, profile: CandidateProfile, job: JobPosting
    ) -> tuple[float, list[str], list[str], list[str], list[MatchEvidence]]:
        """Score seniority alignment (0-1.0)."""
        # Simple heuristic: count years of experience vs job title indicators
        total_years = sum(
            s.years_of_experience or 0
            for s in profile.profile_data.skills
            if s.years_of_experience is not None
        )
        if not profile.profile_data.work_experience:
            # Fallback to skills-based years
            total_years = sum(
                s.years_of_experience or 0
                for s in profile.profile_data.skills
                if s.years_of_experience is not None
            )

        job_title_lower = job.title.lower()
        seniority_indicators = {
            "entry": 0,
            "junior": 1,
            "associate": 2,
            "mid": 3,
            "intermediate": 3,
            "senior": 5,
            "lead": 5,
            "principal": 7,
            "architect": 7,
            "manager": 5,
            "director": 7,
            "vp": 10,
            "president": 10,
            "chief": 10,
            "head": 5,
        }

        implied_years = 0
        for indicator, years in seniority_indicators.items():
            if indicator in job_title_lower:
                implied_years = max(implied_years, years)

        if implied_years == 0:
            # No seniority indicators found
            score = 0.5
            strengths = []
            gaps = ["No seniority level detected in job title"]
            unknowns = ["Seniority level unclear from job title"]
            evidence = [
                MatchEvidence(
                    criterion="seniority",
                    type="unknown",
                    statement="Could not determine seniority level from job title",
                    source="job title analysis",
                )
            ]
        else:
            # Compare years of experience to implied seniority
            years_diff = abs(total_years - implied_years)
            score = max(0.0, 1.0 - (years_diff / 10.0))  # 10-year tolerance

            if total_years >= implied_years:
                strengths = [f"Experience ({total_years} years) meets seniority level"]
                gaps = []
            else:
                strengths = []
                gaps = [f"Experience ({total_years} years) below implied seniority ({implied_years} years)"]
            unknowns = []
            evidence = [
                MatchEvidence(
                    criterion="seniority",
                    type="strength" if total_years >= implied_years else "gap",
                    statement=f"Profile: {total_years} years experience vs job implied: {implied_years} years",
                    source="profile experience vs job title",
                )
            ]

        return score, strengths, gaps, unknowns, evidence

    def _score_location(
        self, profile: CandidateProfile, job: JobPosting
    ) -> tuple[float, list[str], list[str], list[str], list[MatchEvidence]]:
        """Score location and work arrangement (0-1.0)."""
        if not profile.preferences_data.preferred_locations and not profile.preferences_data.work_arrangements:
            return 0.5, [], ["No location or work arrangement preferences"], [], []

        score = 0.0
        strengths = []
        gaps = []
        unknowns = []

        # Location match
        if profile.preferences_data.preferred_locations and job.location:
            job_loc_lower = job.location.lower()
            loc_matches = []
            for pref_loc in profile.preferences_data.preferred_locations:
                if pref_loc.lower() in job_loc_lower or job_loc_lower in pref_loc.lower():
                    loc_matches.append(pref_loc)
            if loc_matches:
                score += 0.5
                strengths.append(f"Location match: {job.location}")
            else:
                gaps.append(f"Location {job.location} not in preferred locations")
        elif job.location:
            unknowns.append("No preferred locations specified")

        # Work arrangement match
        if profile.preferences_data.work_arrangements and job.work_arrangement:
            if job.work_arrangement in profile.preferences_data.work_arrangements:
                score += 0.5
                strengths.append(f"Work arrangement match: {job.work_arrangement.value}")
            else:
                gaps.append(f"Work arrangement {job.work_arrangement.value} not preferred")
        elif job.work_arrangement:
            unknowns.append("No work arrangement preferences specified")

        # Normalize score to 0-1
        score = min(1.0, score)

        evidence = [
            MatchEvidence(
                criterion="location",
                type="strength" if score >= 0.5 else "gap",
                statement=f"Location: {job.location or 'unspecified'}, Arrangement: {job.work_arrangement.value if job.work_arrangement else 'unspecified'}",
                source="profile preferences vs job location/arrangement",
            )
        ]

        return score, strengths, gaps, unknowns, evidence

    def _score_compensation(
        self, profile: CandidateProfile, job: JobPosting
    ) -> tuple[float, list[str], list[str], list[str], list[MatchEvidence]]:
        """Score compensation alignment (0-1.0)."""
        # This is simplified - we don't have actual salary data in the job posting
        # In a real implementation, we'd parse salary ranges from the description
        if not profile.preferences_data.min_compensation:
            return 0.5, [], ["No minimum compensation specified"], [], []

        # Since we don't have salary data in the fixture, we'll return unknown
        # A real implementation would parse the job description for salary info
        unknowns = ["Compensation information not available in job posting"]
        strengths = []
        gaps = []
        evidence = [
            MatchEvidence(
                criterion="compensation",
                type="unknown",
                statement="Could not determine compensation from job posting",
                source="job description parsing",
            )
        ]

        return 0.0, strengths, gaps, unknowns, evidence

    def _score_industry(
        self, profile: CandidateProfile, job: JobPosting
    ) -> tuple[float, list[str], list[str], list[str], list[MatchEvidence]]:
        """Score industry/domain preference (0-1.0)."""
        if not profile.preferences_data.preferred_industries:
            return 0.5, [], ["No preferred industries specified"], [], []

        # Simple keyword matching in company and description
        job_text = f"{job.company} {job.description or ''}".lower()
        matches = []
        for industry in profile.preferences_data.preferred_industries:
            if industry.lower() in job_text:
                matches.append(industry)

        score = min(1.0, len(matches) / max(len(profile.preferences_data.preferred_industries), 1)) if matches else 0.0

        strengths = [f"Industry match: {matches[0]}" if matches else ""]
        strengths = [s for s in strengths if s]  # Remove empty strings
        gaps = [f"No match for preferred industries: {', '.join(profile.preferences_data.preferred_industries[:3])}"] if not matches else []
        unknowns = []
        evidence = [
            MatchEvidence(
                criterion="industry",
                type="strength" if matches else "gap",
                statement=f"Found industry matches: {', '.join(matches)}" if matches else "No industry preferences matched",
                source="profile preferences vs job company/description",
            )
        ]

        return score, strengths, gaps, unknowns, evidence