"""Profile repository.

Manages persistence of candidate profiles and their versions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateProfile
from app.schemas.profile import CandidateProfile as ProfileSchema
from app.schemas.profile import ProfileUpdate


class SQLAlchemyProfileRepository:
    """Repository for managing candidate profiles."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_current(self) -> ProfileSchema | None:
        """Return the latest version of the candidate profile.

        If multiple profiles exist (legacy state), returns the one with the
        highest version number. Returns None if no profile exists.
        """
        stmt = select(CandidateProfile).order_by(CandidateProfile.version.desc()).limit(1)
        result = await self.session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None:
            return None
        return ProfileSchema(
            id=profile.id,
            version=profile.version,
            profile_data=profile.profile_data,
            preferences_data=profile.preferences_data,
            created_at=profile.created_at.isoformat() if profile.created_at else None,
            updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
        )

    async def get_by_version(self, version: int) -> ProfileSchema | None:
        """Return the profile at a specific version."""
        stmt = select(CandidateProfile).where(CandidateProfile.version == version)
        result = await self.session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None:
            return None
        return ProfileSchema(
            id=profile.id,
            version=profile.version,
            profile_data=profile.profile_data,
            preferences_data=profile.preferences_data,
            created_at=profile.created_at.isoformat() if profile.created_at else None,
            updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
        )

    async def create(self, profile_data: dict, preferences_data: dict) -> ProfileSchema:
        """Create a new profile with version 1."""
        profile_id = str(uuid.uuid4())
        profile = CandidateProfile(
            id=profile_id,
            version=1,
            profile_data=profile_data,
            preferences_data=preferences_data,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(profile)
        await self.session.commit()
        await self.session.refresh(profile)
        return ProfileSchema(
            id=profile.id,
            version=profile.version,
            profile_data=profile.profile_data,
            preferences_data=profile.preferences_data,
            created_at=profile.created_at.isoformat() if profile.created_at else None,
            updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
        )

    async def update(self, profile_id: str, update: ProfileUpdate) -> ProfileSchema:
        """Update an existing profile, creating a new version.

        Updates merge the new data into the existing profile and bump the
        version number. This preserves historical versions so documents can
        retain their original source context.
        """
        # Get the current version to merge with
        stmt = select(CandidateProfile).where(CandidateProfile.id == profile_id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            raise ValueError(f"Profile not found: {profile_id}")

        # Merge the updates
        new_profile_data = existing.profile_data.copy()
        new_preferences_data = existing.preferences_data.copy()

        if update.profile_data is not None:
            new_profile_data.update(update.profile_data.model_dump(exclude_unset=True))
        if update.preferences_data is not None:
            new_preferences_data.update(update.preferences_data.model_dump(exclude_unset=True))

        # Create a new version
        new_profile = CandidateProfile(
            id=str(uuid.uuid4()),  # New ID for the new version
            version=existing.version + 1,
            profile_data=new_profile_data,
            preferences_data=new_preferences_data,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(new_profile)
        await self.session.commit()
        await self.session.refresh(new_profile)

        return ProfileSchema(
            id=new_profile.id,
            version=new_profile.version,
            profile_data=new_profile.profile_data,
            preferences_data=new_profile.preferences_data,
            created_at=new_profile.created_at.isoformat() if new_profile.created_at else None,
            updated_at=new_profile.updated_at.isoformat() if new_profile.updated_at else None,
        )