"""Test deduplication service."""

from __future__ import annotations

import pytest

from app.services.dedup import InMemoryDedupService
from app.services.normalization import NormalizationService
from app.schemas.job import JobPostingCreate


import asyncio


def test_dedup_first_posting() -> None:
    """Test that the first posting has no match."""
    async def run_test() -> None:
        dedup = InMemoryDedupService()
        posting = JobPostingCreate(
            company="Test Corp",
            title="Software Engineer",
            location="New York, NY",
            description="Great job",
            url="https://example.com/job/1",
            source="fixture",
            external_id="EXT-001",
        )

        existing_id = await dedup.find_existing_job(posting)
        assert existing_id is None

    asyncio.run(run_test())


def test_dedup_same_source_external_id() -> None:
    """Test that duplicate (source, external_id) is detected."""
    async def run_test() -> None:
        dedup = InMemoryDedupService()
        posting = JobPostingCreate(
            company="Test Corp",
            title="Software Engineer",
            location="New York, NY",
            description="Great job",
            url="https://example.com/job/1",
            source="fixture",
            external_id="EXT-001",
        )

        dedup.put(posting, "internal-job-123")

        # Same source + external_id should match
        existing_id = await dedup.find_existing_job(posting)
        assert existing_id == "internal-job-123"

    asyncio.run(run_test())


def test_dedup_same_url_different_case() -> None:
    """Test that canonical URL matching works."""
    async def run_test() -> None:
        dedup = InMemoryDedupService()
        posting1 = JobPostingCreate(
            company="Test Corp",
            title="Software Engineer",
            location="New York, NY",
            description="Great job",
            url="https://example.com/job/1",
            source="fixture",
            external_id="EXT-001",
        )

        dedup.put(posting1, "internal-job-123")

        # Same URL with different case (canonicalizes to same URL)
        posting2 = JobPostingCreate(
            company="Test Corp",
            title="Software Engineer",
            location="New York, NY",
            description="Great job",
            url="https://EXAMPLE.COM/job/1",  # Different case
            source="fixture",
            external_id="EXT-002",  # Different external ID
        )

        # The dedup service uses canonical URLs for matching
        canonical = NormalizationService.canonicalize_url("https://EXAMPLE.COM/job/1")
        existing_id = await dedup.get_by_url(canonical)
        assert existing_id == "internal-job-123"

    asyncio.run(run_test())


def test_dedup_same_content_different_url() -> None:
    """Test that content-based matching works."""
    async def run_test() -> None:
        dedup = InMemoryDedupService()
        posting1 = JobPostingCreate(
            company="Test Corp",
            title="Software Engineer",
            location="New York, NY",
            description="Great job",
            url="https://example.com/job/1",
            source="fixture",
            external_id="EXT-001",
        )

        dedup.put(posting1, "internal-job-123")

        # Same content but different URL and external_id
        posting3 = JobPostingCreate(
            company="Test Corp",
            title="Software Engineer",
            location="New York, NY",
            description="Great job",
            url="https://example.com/job/2",  # Different URL
            source="fixture",
            external_id="EXT-003",  # Different external ID
        )

        # Content-based match should find the existing job
        existing_id = await dedup.find_existing_job(posting3)
        assert existing_id == "internal-job-123"

    asyncio.run(run_test())


def test_dedup_different_content() -> None:
    """Test that different content is not matched."""
    async def run_test() -> None:
        dedup = InMemoryDedupService()
        posting1 = JobPostingCreate(
            company="Test Corp",
            title="Software Engineer",
            location="New York, NY",
            description="Great job",
            url="https://example.com/job/1",
            source="fixture",
            external_id="EXT-001",
        )

        dedup.put(posting1, "internal-job-123")

        # Different content
        posting4 = JobPostingCreate(
            company="Different Corp",
            title="Data Scientist",
            location="San Francisco, CA",
            description="Analyze data",
            url="https://example.com/job/3",
            source="fixture",
            external_id="EXT-004",
        )

        existing_id = await dedup.find_existing_job(posting4)
        assert existing_id is None

    asyncio.run(run_test())