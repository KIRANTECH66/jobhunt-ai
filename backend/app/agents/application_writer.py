"""Application Writer agent.

Generates job-specific application materials (resume and cover letter) from
the verified candidate profile, job posting, and match result. The agent:

1. Reads the verified profile data (user-confirmed facts only)
2. Tailors the resume to highlight relevant experience and skills
3. Generates a cover letter addressing the specific job requirements
4. Preserves factual details without inventing qualifications
5. Identifies missing information rather than filling it with guesses
6. Returns structured output with claim provenance where possible
"""

from __future__ import annotations

import logging
from typing import Any

from app.schemas.job import JobPosting
from app.schemas.match import MatchResult
from app.schemas.profile import CandidateProfile
from app.harness.harness import AgentHarness, AgentSpec

logger = logging.getLogger(__name__)


class ApplicationWriterAgent:
    """Agent that generates tailored application materials.

    Uses the shared Agent Harness for safe execution. Falls back to
    template-based generation if the LLM is unavailable or returns invalid
    output.
    """

    def __init__(
        self,
        harness: AgentHarness | None = None,
    ) -> None:
        self.harness = harness or AgentHarness()

    @property
    def spec(self) -> AgentSpec:
        """Return the agent specification."""
        return AgentSpec(
            name="application_writer",
            instructions=(
                "You are an application writer. Generate tailored resume and "
                "cover letter drafts for a job application.\n\n"
                "Rules:\n"
                "- Use ONLY verified candidate facts from the profile\n"
                "- Do NOT invent qualifications, employers, dates, or skills\n"
                "- Tailor emphasis to the job requirements\n"
                "- Preserve factual details exactly as provided\n"
                "- Identify missing information rather than guessing\n"
                "- Keep the original resume unchanged\n"
                "- Return structured JSON with resume and cover_letter sections"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "profile": {"type": "object"},
                    "job_posting": {"type": "object"},
                    "match_result": {"type": "object"},
                },
                "required": ["profile", "job_posting", "match_result"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "resume": {"type": "string"},
                    "cover_letter": {"type": "string"},
                    "missing_info": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["resume", "cover_letter"],
            },
            tools=[],
            max_retries=1,
        )

    async def write(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        match: MatchResult,
    ) -> dict[str, str | list[str]]:
        """Generate application materials for a job.

        Returns a dict with 'resume', 'cover_letter', and optionally
        'missing_info' keys. Falls back to template generation if the LLM
        is unavailable or returns invalid output.
        """
        # Try the LLM-assisted path first
        try:
            result = await self._llm_write(profile, job, match)
            if result:
                return result
        except Exception as e:
            logger.warning("LLM application writing failed, falling back to templates: %s", e)

        # Fall back to template-based generation
        return self._template_write(profile, job, match)

    async def _llm_write(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        match: MatchResult,
    ) -> dict[str, str | list[str]] | None:
        """Use the harness + model adapter for application writing."""
        spec = self.spec
        payload = {
            "profile": profile.model_dump(),
            "job_posting": job.model_dump(),
            "match_result": match.model_dump(),
        }

        result = await self.harness.run(spec, payload)
        if not result.success:
            logger.warning("Application writing failed: %s", result.error)
            return None

        output = result.output
        try:
            # Validate required fields
            if "resume" not in output or "cover_letter" not in output:
                raise ValueError("Missing required fields: resume, cover_letter")

            missing_info = list(output.get("missing_info", []))
            return {
                "resume": output["resume"],
                "cover_letter": output["cover_letter"],
                "missing_info": missing_info,
            }
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("Invalid LLM output for application writing: %s", e)
            return None

    def _template_write(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        match: MatchResult,
    ) -> dict[str, str | list[str]]:
        """Generate application materials using templates."""
        # Build resume from profile data
        resume_lines = [
            f"# {profile.profile_data.full_name or 'Candidate'}",
            "",
            "## Professional Summary",
            profile.profile_data.summary or "Experienced professional seeking opportunities in target field.",
            "",
            "## Work Experience",
        ]

        for exp in profile.profile_data.work_experience:
            resume_lines.append(f"- **{exp.title}** at {exp.company} ({exp.start_date or 'Present'})")
            if exp.description:
                resume_lines.append(f"  {exp.description}")
            for achievement in exp.achievements:
                resume_lines.append(f"  - {achievement}")

        resume_lines.extend([
            "",
            "## Skills",
        ])
        for skill in profile.profile_data.skills:
            years = f" ({skill.years_of_experience} years)" if skill.years_of_experience else ""
            resume_lines.append(f"- {skill.name}{years}")

        resume = "\n".join(resume_lines)

        # Build cover letter
        cover_letter_lines = [
            f"Dear Hiring Manager,",
            "",
            f"I am writing to express my interest in the {job.title} position at {job.company}.",
            "",
            "With my experience in",
            ", ".join(s.name for s in profile.profile_data.skills[:3]),
            ", I believe I would be a strong fit for this role.",
            "",
            "I look forward to discussing how my skills and experience align with your needs.",
            "",
            "Sincerely,",
            profile.profile_data.full_name or "Candidate",
        ]
        cover_letter = "\n".join(cover_letter_lines)

        return {
            "resume": resume,
            "cover_letter": cover_letter,
            "missing_info": [],
        }