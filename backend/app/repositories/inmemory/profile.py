"""In-memory profile repository for testing."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.profile import (
    CandidateProfile,
    ProfileData,
    ProfilePreferences,
    ProfileUpdate,
)


class InMemoryProfileRepository:
    """In-memory implementation of the profile repository for testing."""

    def __init__(self) -> None:
        self.profiles: dict[str, dict] = {}

    async def get_current(self) -> dict | None:
        """Return the latest version of the candidate profile."""
        if not self.profiles:
            return None
        # Return the profile with the highest version
        latest_profile_id = max(
            self.profiles.keys(), key=lambda pid: self.profiles[pid]["version"]
        )
        return self.profiles[latest_profile_id]

    async def get_by_version(self, version: int) -> dict | None:
        """Return the profile at a specific version."""
        for profile in self.profiles.values():
            if profile["version"] == version:
                return profile
        return None

    async def create(self, profile_data: dict, preferences_data: dict) -> dict:
        """Create a new profile with version 1."""
        profile_id = str(uuid.uuid4())
        profile = {
            "id": profile_id,
            "version": 1,
            "profile_data": profile_data,
            "preferences_data": preferences_data,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        self.profiles[profile_id] = profile
        return profile

    async def update(self, profile_id: str, update: ProfileUpdate) -> dict:
        """Update an existing profile, creating a new version."""
        if profile_id not in self.profiles:
            raise ValueError(f"Profile not found: {profile_id}")

        # Get the current profile to merge with
        existing = self.profiles[profile_id]

        # Merge the updates
        new_profile_data = existing["profile_data"].copy()
        new_preferences_data = existing["preferences_data"].copy()

        if update.profile_data is not None:
            new_profile_data.update(update.profile_data.model_dump(exclude_unset=True))
        if update.preferences_data is not None:
            new_preferences_data.update(update.preferences_data.model_dump(exclude_unset=True))

        # Create a new version
        new_profile = {
            "id": str(uuid.uuid4()),  # New ID for the new version
            "version": existing["version"] + 1,
            "profile_data": new_profile_data,
            "preferences_data": new_preferences_data,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        self.profiles[new_profile["id"]] = new_profile
        return new_profile