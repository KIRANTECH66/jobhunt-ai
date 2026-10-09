"""Test normalization service."""

from __future__ import annotations

import pytest

from app.services.normalization import NormalizationService


def test_canonicalize_url_standard() -> None:
    """Test URL canonicalization with standard URLs."""
    assert NormalizationService.canonicalize_url("https://example.com/job/123") == "https://example.com/job/123"
    assert NormalizationService.canonicalize_url("http://EXAMPLE.COM/job/123") == "http://example.com/job/123"
    assert NormalizationService.canonicalize_url("https://example.com:443/job/123") == "https://example.com/job/123"
    assert NormalizationService.canonicalize_url("http://example.com:80/job/123") == "http://example.com/job/123"


def test_canonicalize_url_removes_fragment() -> None:
    """Test that URL fragments are removed during canonicalization."""
    url = "https://example.com/job/123#section"
    assert NormalizationService.canonicalize_url(url) == "https://example.com/job/123"


def test_canonicalize_url_with_query_params() -> None:
    """Test that query parameters are preserved."""
    url = "https://example.com/job/123?ref=google"
    assert NormalizationService.canonicalize_url(url) == "https://example.com/job/123?ref=google"


def test_canonicalize_url_none() -> None:
    """Test that None is handled correctly."""
    assert NormalizationService.canonicalize_url(None) is None


def test_canonicalize_url_empty() -> None:
    """Test that empty string is handled correctly."""
    assert NormalizationService.canonicalize_url("") is None


def test_normalize_location_simple() -> None:
    """Test simple location normalization."""
    assert NormalizationService.normalize_location("New York, NY") == "New York, NY"
    assert NormalizationService.normalize_location("San Francisco, CA") == "San Francisco, CA"


def test_normalize_location_whitespace() -> None:
    """Test that whitespace is stripped."""
    assert NormalizationService.normalize_location("  New York, NY  ") == "New York, NY"


def test_normalize_location_none() -> None:
    """Test that None is handled correctly."""
    assert NormalizationService.normalize_location(None) is None


def test_normalize_location_empty() -> None:
    """Test that empty string is handled correctly."""
    assert NormalizationService.normalize_location("") is None


def test_normalize_job_posting_url() -> None:
    """Test that URL is normalized in a job posting."""
    raw = {
        "company": "Test Corp",
        "title": "Software Engineer",
        "url": "https://EXAMPLE.COM:80/job/123#section",
    }
    normalized = NormalizationService.normalize_job_posting(raw)
    assert normalized["url"] == "https://example.com:80/job/123"


def test_normalize_job_posting_location() -> None:
    """Test that location is normalized in a job posting."""
    raw = {
        "company": "Test Corp",
        "title": "Software Engineer",
        "location": "  New York, NY  ",
    }
    normalized = NormalizationService.normalize_job_posting(raw)
    assert normalized["location"] == "New York, NY"


def test_normalize_job_posting_description() -> None:
    """Test that None description is handled correctly."""
    raw = {
        "company": "Test Corp",
        "title": "Software Engineer",
        "description": None,
    }
    normalized = NormalizationService.normalize_job_posting(raw)
    assert normalized["description"] == ""


def test_normalize_job_posting_non_dict() -> None:
    """Test that non-dict input is returned as-is."""
    raw = "not a dict"
    normalized = NormalizationService.normalize_job_posting(raw)
    assert normalized == "not a dict"