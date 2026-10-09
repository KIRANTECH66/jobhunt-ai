"""In-memory job repository for testing."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.job import JobPostingCreate, JobSourceRecord


class InMemoryJobRepository:
    """In-memory implementation of the job repository for testing."""

    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}
        self.source_records: dict[str, dict] = {}
        self.next_id = 1

    async def get_by_id(self, job_id: str) -> dict | None:
        """Return a job posting by its internal ID."""
        return self.jobs.get(job_id)

    async def get_by_source_external_id(self, source: str, external_id: str) -> str | None:
        """Return the internal job ID for a given source and external ID."""
        for job_id, job in self.jobs.items():
            if job.get("source") == source and job.get("external_id") == external_id:
                return job_id
        return None

    async def get_by_url(self, url: str) -> str | None:
        """Return the internal job ID for a given canonical URL."""
        for job_id, job in self.jobs.items():
            if job.get("url") == url:
                return job_id
        return None

    async def get_by_content_hash(self, content_hash: str) -> str | None:
        """Return the internal job ID for a given content hash."""
        for job_id, job in self.jobs.items():
            if job.get("content_hash") == content_hash:
                return job_id
        return None

    async def save_job_posting(self, posting: JobPostingCreate | dict) -> str:
        """Persist a job posting and return its internal job ID.

        Accepts either a JobPostingCreate model or a plain dict for flexibility
        in tests.
        """
        job_id = str(self.next_id)
        self.next_id += 1

        # Handle both model and dict inputs
        if isinstance(posting, dict):
            job_data = posting.copy()
            job_data["id"] = job_id
        else:
            job_data = {
                "id": job_id,
                "source": posting.source,
                "external_id": posting.external_id,
                "company": posting.company,
                "title": posting.title,
                "location": posting.location,
                "work_arrangement": posting.work_arrangement.value if posting.work_arrangement else None,
                "employment_type": posting.employment_type.value if posting.employment_type else None,
                "description": posting.description,
                "url": posting.url,
                "posted_at": posting.posted_at,
                "content_hash": self._compute_content_hash(posting),
                "status": "active",
                "is_expired": False,
            }

        self.jobs[job_id] = job_data
        return job_id

    async def save_job_source_record(self, job_id: str, source_record: JobSourceRecord | dict) -> str:
        """Persist a job source record and return its internal ID."""
        record_id = str(len(self.source_records) + 1)

        if isinstance(source_record, dict):
            record_data = source_record.copy()
            record_data["id"] = record_id
            record_data.setdefault("job_id", job_id)
        else:
            record_data = {
                "id": record_id,
                "job_id": job_id,
                "source": source_record.source,
                "external_id": source_record.external_id,
                "url": source_record.url,
                "posted_at": source_record.posted_at,
                "retrieved_at": source_record.retrieved_at or datetime.now(timezone.utc),
                "raw": source_record.raw,
            }

        self.source_records[record_id] = record_data
        return record_id

    @staticmethod
    def _compute_content_hash(posting: JobPostingCreate | dict) -> str:
        """Compute a SHA256 hash of the normalized content fields.

        Used as a tertiary dedup signal when source IDs and URLs are not
        available or collide. The hash is deterministic and collision-resistant
        for practical purposes.
        """
        if isinstance(posting, dict):
            title = posting.get("title", "")
            company = posting.get("company", "")
            location = posting.get("location", "")
            description = posting.get("description", "")
        else:
            title = posting.title
            company = posting.company
            location = posting.location or ""
            description = posting.description or ""

        # Normalize whitespace and case for better matching
        normalized = f"{title.strip().lower()}|{company.strip().lower()}|{location.strip().lower()}|{description.strip().lower()}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()