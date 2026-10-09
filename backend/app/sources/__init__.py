"""Job source adapters.

The system uses a pluggable interface so new sources can be added without
touching the core logic. Each source must implement the ``JobSource`` ABC and
return ``JobPostingCreate`` objects (or dicts that validate against that
schema). The orchestrator calls ``fetch()``, normalizes the results, and then
deduplicates them against the existing job postings.

A fixture source is provided for development and testing. It reads a static
JSON file and never claims to be live data.
"""

from __future__ import annotations

from app.sources.base import JobSource
from app.sources.fixture import FixtureJobSource

__all__ = ["JobSource", "FixtureJobSource"]