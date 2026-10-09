"""Fixture job source for development and testing.

Reads a static JSON file containing job postings. Intended for local
development and automated tests; never claims to be live data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncIterable

from app.sources.base import JobSource


class FixtureJobSource(JobSource):
    """Loads job postings from a local JSON file."""

    def __init__(self, source_id: str, file_path: str | Path) -> None:
        super().__init__(source_id)
        self.file_path = Path(file_path)

    async def fetch(self) -> AsyncIterable[dict]:
        """Yield each job posting from the fixture file."""
        if not self.file_path.is_file():
            # Return empty iterator if the fixture file is missing.
            return
        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            # Yield nothing; the orchestrator will log the error.
            return

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    yield item
        elif isinstance(data, dict):
            # Single object fixture.
            yield data
        # Any other JSON type is ignored.