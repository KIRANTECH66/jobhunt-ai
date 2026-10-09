"""Candidate profile schemas (FR-01).

The profile is the single source of truth about the job seeker. Facts are
tagged with a ``FactSource`` so user-confirmed facts can be distinguished
from AI-extracted facts, and substantive career claims carry a source
reference (e.g. a resume passage or an explicit user statement).

The profile is versioned: every substantive edit produces a new
``version`` so existing documents can retain their original source context.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FactSource(str, Enum):
    """Who asserted a fact and how confident we are in its provenance."""

    user_confirmed = "user_confirmed"
    resume_extracted = "resume_extracted"
    user_supplied = "user_supplied"


class ContactInfo(BaseModel):
    """Contact details. Optional by design — only what is needed for the workflow."""

    model_config = ConfigDict(extra="allow")

    email: Optional[str] = Field(default=None, description="Primary email address.")
    phone: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None)
    linkedin_url: Optional[str] = Field(default=None)
    portfolio_url: Optional[str] = Field(default=None)


class Skill(BaseModel):
    name: str
    years_of_experience: Optional[float] = Field(default=None)
    proficiency: Optional[str] = Field(default=None)  # e.g. beginner/intermediate/advanced/expert
    source: FactSource = FactSource.user_supplied
    source_reference: Optional[str] = Field(
        default=None, description="Where this fact came from (resume passage, user statement)."
    )


class WorkExperience(BaseModel):
    company: str
    title: str
    start_date: Optional[str] = Field(default=None, description="Start date, free-form (e.g. '2021-06').")
    end_date: Optional[str] = Field(default=None, description="End date; null means present.")
    description: Optional[str] = Field(default=None)
    achievements: list[str] = Field(default_factory=list)
    source: FactSource = FactSource.user_supplied
    source_reference: Optional[str] = Field(default=None)


class Education(BaseModel):
    institution: str
    degree: Optional[str] = Field(default=None)
    field_of_study: Optional[str] = Field(default=None)
    graduation_year: Optional[int] = Field(default=None)
    source: FactSource = FactSource.user_supplied
    source_reference: Optional[str] = Field(default=None)


class Certification(BaseModel):
    name: str
    issuing_organization: Optional[str] = Field(default=None)
    date_obtained: Optional[str] = Field(default=None)
    expiration_date: Optional[str] = Field(default=None)
    source: FactSource = FactSource.user_supplied
    source_reference: Optional[str] = Field(default=None)


class Project(BaseModel):
    name: str
    description: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)
    technologies: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    source: FactSource = FactSource.user_supplied
    source_reference: Optional[str] = Field(default=None)


class EmploymentType(str, Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"
    temporary = "temporary"


class WorkArrangement(str, Enum):
    onsite = "onsite"
    hybrid = "hybrid"
    remote = "remote"
    flexible = "flexible"


class ProfilePreferences(BaseModel):
    """Search preferences. All optional — the matcher treats missing as unknown."""

    target_titles: list[str] = Field(default_factory=list)
    preferred_industries: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    work_arrangements: list[WorkArrangement] = Field(default_factory=list)
    employment_types: list[EmploymentType] = Field(default_factory=list)
    min_compensation: Optional[float] = Field(default=None)
    compensation_currency: Optional[str] = Field(default=None, description="ISO 4217 code, e.g. USD.")
    work_authorization: Optional[str] = Field(
        default=None,
        description="Voluntarily supplied; only included when needed for the search.",
    )
    additional: dict[str, object] = Field(default_factory=dict)


class ProfileData(BaseModel):
    """The substantive candidate facts."""

    model_config = ConfigDict(extra="allow")

    full_name: Optional[str] = Field(default=None)
    contact: Optional[ContactInfo] = Field(default=None)
    summary: Optional[str] = Field(default=None)
    skills: list[Skill] = Field(default_factory=list)
    work_experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    resume_text: Optional[str] = Field(
        default=None,
        description="Raw resume text, if the user supplied one. Never modified in place.",
    )


class CandidateProfile(BaseModel):
    """A versioned candidate profile.

    ``version`` is incremented on every substantive change so documents
    generated from an older profile retain their source context.
    """

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(default=None)
    version: int = Field(default=1, description="Monotonically increasing profile version.")
    profile_data: ProfileData
    preferences_data: ProfilePreferences
    created_at: Optional[str] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)


class ProfileUpdate(BaseModel):
    """Partial profile update. Missing fields are left unchanged."""

    model_config = ConfigDict(extra="allow")

    profile_data: Optional[ProfileData] = Field(default=None)
    preferences_data: Optional[ProfilePreferences] = Field(default=None)