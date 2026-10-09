"""Job matcher service.

Combines normalization, deduplication, and scoring to produce match results
for job postings against a candidate profile. This is the core logic that
the Job Matcher agent will use (in Milestone 2) to evaluate jobs.
"""

from __future__ import annotations

import logging
from typing import Protocol

from app.schemas.job import JobPosting, JobPostingCreate, JobSourceRecord
from app.schemas.match import MatchResult
from app.schemas.profile import CandidateProfile
from app.services.dedup import DedupService
from app.services.normalization import NormalizationService
from app.services.scoring import MatchScorer, ScoringConfig

logger = logging.getLogger(__name__)


class JobRepository(Protocol):
    """Protocol defining the repository methods needed by the matcher service."""

    async def get_by_source_external_id(self, source: str, external_id: str) -> str | None:
        """Return the internal job ID for a given source and external ID, or None."""

    async def get_by_url(self, url: str) -> str | None:
        """Return the internal job ID for a given canonical URL, or None."""

    async def get_by_content_hash(
        self, title: str, company: str, location: str | None, description: str
    ) -> str | None:
        """Return the internal job ID for a given content fingerprint, or None."""

    async def save_job_posting(self, posting: JobPostingCreate) -> str:
        """Persist a job posting and return its internal job ID."""

    async def save_job_source_record(
        self, job_id: str, source_record: JobSourceRecord
    ) -> str:
        """Persist a job source record and return its internal ID."""

    async def save_match_result(self, match_result: dict) -> str:
        """Persist a match result and return its internal ID."""


class MatcherService:
    """Match jobs against a candidate profile.

    Orchestrates:
    1. Normalization of raw job postings
    2. Deduplication against existing records
    3. Persistence of new jobs and source records
    4. Scoring against the candidate profile
    5. Persistence of match results
    """

    def __init__(
        self,
        repository: JobRepository,
        dedup_service: DedupService | None = None,
        normalization_service: NormalizationService | None = None,
        scorer: MatchScorer | None = None,
        scoring_config: ScoringConfig | None = None,
    ) -> None:
        self.repository = repository
        self.dedup = dedup_service or DedupService(repository)
        self.normalizer = normalization_service or NormalizationService()
        self.scorer = scorer or MatchScorer(scoring_config)

    async def process_job_posting(
        self, raw_posting: dict, source_id: str
    ) -> tuple[JobPosting, bool, str | None]:
        """Process a raw job posting from a source.

        Returns
        -------
        tuple[JobPosting, bool, str | None]
            (job_posting, is_new, matched_external_id)
            - job_posting: The normalized and validated job posting
            - is_new: True if this created a new job record
            - matched_external_id: The external ID of the matched existing record, if any
        """
        # Normalize the raw posting
        normalized = self.normalizer.normalize_job_posting(raw_posting)

        # Create a validated posting for the dedup service
        posting_create = JobPostingCreate(
            **normalized,
            source=source_id,
        )

        # Check if this is a duplicate
        existing_job_id = await self.dedup.find_existing_job(posting_create)
        is_new = existing_job_id is None

        if is_new:
            # Persist as a new job posting
            job_id = await self.repository.save_job_posting(posting_create)
            logger.info("Created new job posting: %s", job_id)
        else:
            job_id = existing_job_id
            logger.info("Matched existing job posting: %s", job_id)

        # Get the full job posting (we'll need to fetch it from the repository)
        # For now, we'll construct it from what we have
        job_posting = JobPosting(
            id=job_id,
            source=posting_create.source,
            external_id=posting_create.external_id,
            company=posting_create.company,
            title=posting_create.title,
            location=posting_create.location,
            work_arrangement=posting_create.work_arrangement,
            employment_type=posting_create.employment_type,
            description=posting_create.description,
            url=posting_create.url,
            posted_at=posting_create.posted_at,
            status="active",  # Default status
            sources=[],  # Will be populated by the source record below
        )

        # Persist the source record (this creates the link between source and job)
        source_record = JobSourceRecord(
            source=source_id,
            external_id=posting_create.external_id,
            url=posting_create.url,
            posted_at=posting_create.posted_at,
            retrieved_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            raw=raw_posting,
        )
        source_record_id = await self.repository.save_job_source_record(
            job_id, source_record
        )
        logger.debug("Saved source record: %s", source_record_id)

        # Update the job posting with its source records (in a real implementation,
        # we'd fetch this from the repository; for now we'll just add the one we just saved)
        job_posting.sources = [source_record]

        return job_posting, is_new, posting_create.external_id if not is_new else None

    async def score_job(
        self, profile: CandidateProfile, job: JobPosting
    ) -> MatchResult:
        """Score a job posting against a candidate profile.

        Delegates to the deterministic scorer and returns the match result.
        """
        match_result = self.scorer.score_job(profile, job)
        logger.debug(
            "Scored job %s (%s): %.2f (%s)",
            job.id,
            job.title,
            match_result.score,
            match_result.recommendation,
        )
        return match_result

    async def process_and_score(
        self, profile: CandidateProfile, raw_posting: dict, source_id: str
    ) -> tuple[JobPosting, MatchResult, bool]:
        """Process a raw posting and score it against a profile.

        Convenience method that combines processing and scoring.

        Returns
        -------
        tuple[JobPosting, MatchResult, bool]
            (job_posting, match_result, is_new)
        """
        job_posting, is_new, _ = await self.process_job_posting(
            raw_posting, source_id
        )
        match_result = await self.score_job(profile, job_posting)
        return job_posting, match_result, is_new