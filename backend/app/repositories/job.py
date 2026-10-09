"""Job repository.

Manages persistence of job postings, source records, and their relationships.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobPosting, JobSourceRecord
from app.schemas.job import JobPosting as JobPostingSchema
from app.schemas.job import JobPostingCreate, JobSourceRecord as JobSourceRecordSchema


class SQLAlchemyJobRepository:
    """Repository for managing job postings and source records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, job_id: str) -> JobPostingSchema | None:
        """Return a job posting by its internal ID."""
        stmt = select(JobPosting).where(JobPosting.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()
        if job is None:
            return None
        return JobPostingSchema(
            id=job.id,
            source=job.source,
            external_id=job.external_id,
            company=job.company,
            title=job.title,
            location=job.location,
            work_arrangement=job.work_arrangement,
            employment_type=job.employment_type,
            description=job.description,
            url=job.url,
            posted_at=job.posted_at.isoformat() if job.posted_at else None,
            first_seen_at=job.first_seen_at.isoformat() if job.first_seen_at else None,
            last_verified_at=job.last_verified_at.isoformat() if job.last_verified_at else None,
            content_hash=job.content_hash,
            status=job.status,
            sources=[
                JobSourceRecordSchema(
                    source=source.source,
                    external_id=source.external_id,
                    url=source.url,
                    posted_at=source.posted_at.isoformat() if source.posted_at else None,
                    retrieved_at=source.retrieved_at.isoformat() if source.retrieved_at else None,
                    raw=source.raw,
                )
                for source in job.sources
            ],
        )

    async def get_by_source_external_id(self, source: str, external_id: str) -> str | None:
        """Return the internal job ID for a given source and external ID.

        Queries JobPosting directly (not via JobSourceRecord) since source
        records may not have been saved yet at ingestion time.
        """
        stmt = select(JobPosting.id).where(
            JobPosting.source == source,
            JobPosting.external_id == external_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> str | None:
        """Return the internal job ID for a given canonical URL."""
        stmt = select(JobPosting.id).where(JobPosting.url == url)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_content_hash(self, content_hash: str) -> str | None:
        """Return the internal job ID for a given content hash."""
        stmt = select(JobPosting.id).where(JobPosting.content_hash == content_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_job_posting(self, posting: JobPostingCreate) -> str:
        """Persist a job posting and return its internal job ID."""
        job_id = str(uuid.uuid4())
        job = JobPosting(
            id=job_id,
            source=posting.source,
            external_id=posting.external_id,
            company=posting.company,
            title=posting.title,
            location=posting.location,
            work_arrangement=posting.work_arrangement.value if posting.work_arrangement else None,
            employment_type=posting.employment_type.value if posting.employment_type else None,
            description=posting.description,
            url=posting.url,
            posted_at=posting.posted_at,
            first_seen_at=datetime.now(timezone.utc),
            last_verified_at=datetime.now(timezone.utc),
            content_hash=self._compute_content_hash(posting),
            status="active",
            is_expired=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job.id

    async def save_job_source_record(self, job_id: str, source_record: JobSourceRecordSchema) -> str:
        """Persist a job source record and return its internal ID."""
        record_id = str(uuid.uuid4())
        record = JobSourceRecord(
            id=record_id,
            job_id=job_id,
            source=source_record.source,
            external_id=source_record.external_id,
            url=source_record.url,
            posted_at=source_record.posted_at,
            retrieved_at=source_record.retrieved_at or datetime.now(timezone.utc),
            raw=source_record.raw,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record.id

    @staticmethod
    def _compute_content_hash(posting: JobPostingCreate) -> str:
        """Compute a SHA256 hash of the normalized content fields.

        Used as a tertiary dedup signal when source IDs and URLs are not
        available or collide. The hash is deterministic and collision-resistant
        for practical purposes.
        """
        # Normalize whitespace and case for better matching
        normalized = f"{posting.title.strip().lower()}|{posting.company.strip().lower()}|{posting.location.strip().lower() if posting.location else ''}|{posting.description.strip().lower() if posting.description else ''}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()