"""Abstract base class for job sources.

Each source must implement ``fetch()`` which returns an iterable of raw
postings. The orchestrator will normalize each raw posting using the
``normalize`` hook (default implementation does nothing; sources can override
it to map their fields to the common schema) and then validate the result
against the ``JobPostingCreate`` Pydantic model.

Sources are responsible for honoring rate limits and handling errors; the
orchestrator applies a bounded retry policy and surfaces failures as audit
events.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterable, Any

from pydantic import ValidationError

from app.schemas.job import JobPostingCreate


class JobSource(ABC):
    """Pluggable job source interface."""

    def __init__(self, source_id: str) -> None:
        self.source_id = source_id

    @abstractmethod
    async def fetch(self) -> AsyncIterable[dict]:
        """Yield raw job postings from the source.

        Each yielded item is a dict that the orchestrator will pass to
        ``normalize`` and then validate against ``JobPostingCreate``.
        """
        raise NotImplementedError

    async def normalize(self, raw: dict) -> dict:
        """Map a raw posting to the common schema.

        The default implementation returns the raw dict unchanged. Sources
        should override this method to perform field mapping, data cleaning,
        and any source-specific normalization.

        Parameters
        ----------
        raw: dict
            The raw posting as yielded by ``fetch``.

        Returns
        -------
        dict
            A dict that validates against ``JobPostingCreate``.
        """
        return raw

    async def validate_and_create(self, raw: dict) -> JobPostingCreate:
        """Normalize and validate a raw posting.

        Convenience method that calls ``normalize`` and then validates the
        result against the ``JobPostingCreate`` schema. Validation errors are
        logged and re-raised so the orchestrator can surface them as audit
        events.

        Parameters
        ----------
        raw: dict
            The raw posting as yielded by ``fetch``.

        Returns
        -------
        JobPostingCreate
            A validated job posting ready for persistence.
        """
        normalized = await self.normalize(raw)
        try:
            return JobPostingCreate(**normalized, source=self.source_id)
        except ValidationError as exc:
            # Re-raise with context; the orchestrator will catch and log.
            raise ValueError(f"Invalid job posting from source {self.source_id!r}: {exc}") from exc