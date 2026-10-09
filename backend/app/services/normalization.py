"""Normalization service.

Turns raw job postings from any source into the common schema used by the
system. Handles URL canonicalization, location formatting, and other
source-independent transformations.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

from app.schemas.job import JobPostingCreate


class NormalizationService:
    """Normalize job postings to the common schema."""

    @staticmethod
    def canonicalize_url(url: str | None) -> str | None:
        """Return a canonical form of a URL for dedup comparison.

        - Lowercases the scheme and host.
        - Removes default ports (80 for http, 443 for https).
        - Strips fragments.
        - Keeps query parameters (order is not normalized here; sources that
          vary only by query order should handle that in their adapter).
        - Returns None if the input is None or empty.
        """
        if not url:
            return None

        try:
            parsed = urlparse(url.strip())
        except ValueError:
            return url.strip()  # best effort

        # Normalize scheme and host
        scheme = parsed.scheme.lower()
        host = parsed.hostname.lower() if parsed.hostname else ""
        port = parsed.port

        # Remove default ports
        if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
            netloc = host
        else:
            netloc = f"{host}:{port}" if port else host

        # Rebuild without fragment
        canonical = urlunparse(
            (scheme, netloc, parsed.path, parsed.params, parsed.query, "")
        )
        return canonical

    @staticmethod
    def normalize_location(location: str | None) -> str | None:
        """Normalize a location string for better dedup matching.

        - Strips whitespace.
        - Returns None if the input is None or empty after stripping.
        - Does NOT change case; locations are stored as-is to preserve
          abbreviations like "CA" and "NY" and avoid mangling proper nouns.
        """
        if not location:
            return None
        location = location.strip()
        if not location:
            return None
        return location

    @staticmethod
    def normalize_job_posting(raw: dict) -> dict:
        """Apply normalization to a raw job posting dict.

        Returns a new dict with normalized fields; does not mutate the input.
        Only the fields that have a known normalization are touched; the rest
        are copied as-is.
        """
        if not isinstance(raw, dict):
            return raw

        normalized = raw.copy()

        # Normalize URL if present
        if "url" in normalized and isinstance(normalized["url"], str):
            normalized["url"] = NormalizationService.canonicalize_url(normalized["url"])

        # Normalize location if present
        if "location" in normalized and isinstance(normalized["location"], str):
            normalized["location"] = NormalizationService.normalize_location(normalized["location"])

        # Ensure description is a string (some sources might give None)
        if "description" in normalized and normalized["description"] is None:
            normalized["description"] = ""

        return normalized