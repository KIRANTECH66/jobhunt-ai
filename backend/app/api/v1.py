"""API v1 router.

Contains all the endpoints for Milestone 1:
- Health check
- Profile management
- Job ingestion and retrieval
- Match computation
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.job import JobPosting
from app.repositories.profile import SQLAlchemyProfileRepository
from app.repositories.job import SQLAlchemyJobRepository
from app.repositories.match import SQLAlchemyMatchRepository
from app.schemas.job import JobPostingCreate
from app.schemas.match import MatchResult
from app.schemas.profile import CandidateProfile, ProfileUpdate

api_router = APIRouter()


# --------------------------------------------------------------------------- #
# Health check
# --------------------------------------------------------------------------- #


@api_router.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Return a simple health status."""
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Profile endpoints (FR-01)
# --------------------------------------------------------------------------- #


@api_router.get("/profiles/current", response_model=CandidateProfile, tags=["profiles"])
async def get_current_profile(
    session: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    """Return the latest version of the candidate profile."""
    repo = SQLAlchemyProfileRepository(session)
    profile = await repo.get_current()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found. Create one first.",
        )
    return profile


@api_router.put("/profiles/current", response_model=CandidateProfile, tags=["profiles"])
async def update_profile(
    body: ProfileUpdate,
    session: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    """Create or update the candidate profile (partial update).

    Accepts a single ``ProfileUpdate`` request body. ``profile_data`` and
    ``preferences_data`` are each optional: a field that is omitted or ``null``
    is left unchanged, while a field that is explicitly provided replaces the
    stored value (partial fields within each sub-object are merged, so a
    client can update ``full_name`` alone). If no profile exists, one is
    created with version 1; both sub-objects are required in that case.
    """
    repo = SQLAlchemyProfileRepository(session)
    current = await repo.get_current()
    if current is None:
        # No profile exists; create a new one. Both sub-objects are required
        # for an initial profile — reject rather than silently persisting
        # partial data.
        if body.profile_data is None or body.preferences_data is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Creating a new profile requires both profile_data and "
                    "preferences_data."
                ),
            )
        profile = await repo.create(
            body.profile_data.model_dump(), body.preferences_data.model_dump()
        )
    else:
        # Profile exists; update it (creates a new version). The repository
        # merges unset fields, so omitting a field preserves the stored value.
        profile = await repo.update(current.id, body)
    return profile


# --------------------------------------------------------------------------- #
# Job endpoints (FR-02, FR-03)
# --------------------------------------------------------------------------- #


@api_router.post("/jobs/ingest", tags=["jobs"])
async def ingest_job_posting(
    posting: JobPostingCreate,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str | bool]:
    """Ingest a job posting from a source.

    The endpoint is idempotent: posting the same job twice will not create
    duplicate records. It returns whether the posting was ingested as a new
    job record or matched to an existing one.
    """
    job_repo = SQLAlchemyJobRepository(session)

    # Check if we already have this job from the same source and external ID
    if posting.external_id:
        existing_id = await job_repo.get_by_source_external_id(
            posting.source, posting.external_id
        )
        if existing_id is not None:
            return {
                "job_id": existing_id,
                "is_new": False,
                "message": "Job already exists from this source.",
            }

    # Save the job posting
    job_id = await job_repo.save_job_posting(posting)

    return {
        "job_id": job_id,
        "is_new": True,
        "message": "Job ingested successfully.",
    }


@api_router.get("/jobs", tags=["jobs"])
async def list_jobs(
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List job postings with pagination."""
    from sqlalchemy import select

    result = await session.execute(
        select(JobPosting.id, JobPosting.company, JobPosting.title, JobPosting.location)
        .order_by(JobPosting.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    jobs = []
    for row in result:
        jobs.append(
            {
                "id": row.id,
                "company": row.company,
                "title": row.title,
                "location": row.location,
            }
        )
    return jobs


@api_router.get("/jobs/{job_id}", response_model=dict, tags=["jobs"])
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return a single job posting by its internal ID."""
    job_repo = SQLAlchemyJobRepository(session)
    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )
    # Convert to a dict for simplicity in Milestone 1
    return {
        "id": job.id,
        "source": job.source,
        "external_id": job.external_id,
        "company": job.company,
        "title": job.title,
        "location": job.location,
        "work_arrangement": job.work_arrangement,
        "employment_type": job.employment_type,
        "description": job.description,
        "url": job.url,
        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
        "first_seen_at": job.first_seen_at.isoformat() if job.first_seen_at else None,
        "last_verified_at": job.last_verified_at.isoformat() if job.last_verified_at else None,
        "content_hash": job.content_hash,
        "status": job.status,
        "sources": [
            {
                "source": source.source,
                "external_id": source.external_id,
                "url": source.url,
                "posted_at": source.posted_at.isoformat() if source.posted_at else None,
                "retrieved_at": source.retrieved_at.isoformat() if source.retrieved_at else None,
                "raw": source.raw,
            }
            for source in job.sources
        ],
    }


# --------------------------------------------------------------------------- #
# Match endpoints (FR-04)
# --------------------------------------------------------------------------- #


@api_router.get("/jobs/{job_id}/match", response_model=MatchResult, tags=["matches"])
async def get_job_match(
    job_id: str,
    session: AsyncSession = Depends(get_db),
) -> MatchResult:
    """Return the latest match result for a job.

    If no match exists yet, returns a 404.
    """
    match_repo = SQLAlchemyMatchRepository(session)
    match = await match_repo.get_by_job_id(job_id)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No match found for job {job_id}. Run the matcher first.",
        )
    return match


# --------------------------------------------------------------------------- #
# Workflow endpoints (FR-05, FR-06, FR-07, FR-08)
# --------------------------------------------------------------------------- #


@api_router.post("/workflows", tags=["workflows"])
async def run_workflow(
    job_id: str,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trigger the full application workflow for a job.

    Loads the candidate profile and job posting, runs the matcher agent, then
    drives the LangGraph workflow through draft -> review -> persist ->
    await_approval. Returns the terminal workflow state.

    This endpoint never performs external submission: approval is required
    before any side effect can occur (FR-08).
    """
    from app.agents.supervisor import Supervisor, SupervisorError
    from app.repositories.profile import SQLAlchemyProfileRepository
    from app.repositories.job import SQLAlchemyJobRepository

    profile_repo = SQLAlchemyProfileRepository(session)
    job_repo = SQLAlchemyJobRepository(session)

    profile = await profile_repo.get_current()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found. Create one first.",
        )

    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    supervisor = Supervisor()
    try:
        result = await supervisor.run(profile=profile, job=job)
    except SupervisorError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow failed at phase '{e.phase}': {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow failed: {e}",
        )

    return result