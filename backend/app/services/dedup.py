"""Deduplication service.

Resolves whether a newly fetched job posting is a duplicate of an existing
record. Uses a three-tiered approach:

1. Primary key: (source, external_id) when an external ID exists.
2. Secondary key: canonical URL (when available and same scheme/host).
3. Tertiary key: content fingerprint (hash of normalized title+company+location+description).

The service does not merge records automatically; it returns the existing
internal job ID when a duplicate is detected so the orchestrator can attach
the new source record to the existing job.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Protocol

from app.schemas.job import JobPostingCreate, JobSourceRecord
from app.services.normalization import NormalizationService


class JobRepository(Protocol):
    """Protocol defining the repository methods needed by the dedup service."""

    async def get_by_source_external_id(self, source: str, external_id: str) -> str | None:
        """Return the internal job ID for a given source and external ID, or None."""

    async def get_by_url(self, url: str) -> str | None:
        """Return the internal job ID for a given canonical URL, or None."""

    async def get_by_content_hash(
        self, title: str, company: str, location: str | None, description: str
    ) -> str | None:
        """Return the internal job ID for a given content fingerprint, or None."""


class DedupService:
    """Deduplicate job postings against existing records.

    Accepts any repository implementing the ``JobRepository`` protocol.
    The repository is consulted (via ``await``) to look up existing job IDs.
    """

    def __init__(self, repository: JobRepository) -> None:
        self.repository = repository

    @staticmethod
    def _compute_content_hash(
        *, title: str, company: str, location: str, description: str
    ) -> str:
        """Compute a SHA256 hash of the normalized content fields.

        Used as a tertiary dedup signal when source IDs and URLs are not
        available or collide. The hash is deterministic and collision-resistant
        for practical purposes.
        """
        # Normalize whitespace and case for better matching
        normalized = f"{title.strip().lower()}|{company.strip().lower()}|{location.strip().lower()}|{description.strip().lower()}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def find_existing_job(self, posting: JobPostingCreate) -> str | None:
        """Return the internal job ID of an existing record, or None if new.

        Order of precedence:
        1. (source, external_id) when external_id is present.
        2. Canonical URL (when available).
        3. Content fingerprint (title, company, location, description).

        Returns None when no match is found, indicating the posting should be
        inserted as a new job record.
        """
        # 1. Source + external_id (highest confidence)
        if posting.external_id:
            existing_id = await self.repository.get_by_source_external_id(
                posting.source, posting.external_id
            )
            if existing_id:
                return existing_id

        # 2. Canonical URL (when available)
        if posting.url:
            canonical_url = NormalizationService.canonicalize_url(posting.url)
            if canonical_url:
                existing_id = await self.repository.get_by_url(canonical_url)
                if existing_id:
                    return existing_id

        # 3. Content fingerprint
        # Compute the hash and pass it to the repository's content_hash lookup.
        content_hash = self._compute_content_hash(
            title=posting.title,
            company=posting.company,
            location=posting.location or "",
            description=posting.description or "",
        )
        existing_id = await self.repository.get_by_content_hash(
            title=posting.title,
            company=posting.company,
            location=posting.location or "",
            description=posting.description or "",
        )
        return existing_id


class InMemoryDedupService(DedupService):
    """Simple in-memory implementation for testing and demos.

    Not suitable for production use; intended only for unit tests and local
    development when no persistence layer is configured. This implementation
    does not need a repository: it holds its own indices.
    """

    def __init__(self) -> None:
        self._source_external_to_id: dict[tuple[str, str], str] = {}
        self._url_to_id: dict[str, str] = {}
        self._content_hash_to_id: dict[str, str] = {}

    async def get_by_source_external_id(self, source: str, external_id: str) -> str | None:
        return self._source_external_to_id.get((source, external_id))

    async def get_by_url(self, url: str) -> str | None:
        return self._url_to_id.get(url)

    async def get_by_content_hash(
        self, title: str, company: str, location: str | None, description: str
    ) -> str | None:
        content_hash = self._compute_content_hash(
            title=title, company=company, location=location or "", description=description
        )
        return self._content_hash_to_id.get(content_hash)

    def put(self, posting: JobPostingCreate, internal_id: str) -> None:
        """Register a new job posting in the dedup indices.

        Called by the orchestrator after persisting a new job record.
        """
        if posting.external_id:
            self._source_external_to_id[(posting.source, posting.external_id)] = internal_id
        if posting.url:
            canonical_url = NormalizationService.canonicalize_url(posting.url)
            if canonical_url:
                self._url_to_id[canonical_url] = internal_id
        content_hash = self._compute_content_hash(
            title=posting.title,
            company=posting.company,
            location=posting.location or "",
            description=posting.description or "",
        )
        self._content_hash_to_id[content_hash] = internal_id

    async def find_existing_job(self, posting: JobPostingCreate) -> str | None:
        """Override the base implementation since we hold our own indices.

        The base class expects a ``self.repository`` attribute, which we don't
        have. Instead we look up directly in our in-memory indices.
        """
        # 1. Source + external_id (highest confidence)
        if posting.external_id:
            existing_id = self._source_external_to_id.get((posting.source, posting.external_id))
            if existing_id:
                return existing_id

        # 2. Canonical URL (when available)
        if posting.url:
            canonical_url = NormalizationService.canonicalize_url(posting.url)
            if canonical_url:
                existing_id = self._url_to_id.get(canonical_url)
                if existing_id:
                    return existing_id

        # 3. Content fingerprint
        content_hash = self._compute_content_hash(
            title=posting.title,
            company=posting.company,
            location=posting.location or "",
            description=posting.description or "",
        )
        existing_id = self._content_hash_to_id.get(content_hash)
        return existing_id