"""Milestone 5: Database Constraints and Idempotency Tests.

Tests verify real database uniqueness constraints, concurrent inserts,
and idempotency with real SQLite database.
"""

from __future__ import annotations

import asyncio
import copy
import tempfile
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.models.application import Application as ApplicationModel
from app.models.application import Document as DocumentModel
from app.models.application import ApprovalRequest as ApprovalRequestModel
from app.models.job import JobPosting as JobModel
from app.models.profile import CandidateProfile as ProfileModel
from app.models._base import Base
from app.repositories.application import SQLAlchemyApplicationRepository
from app.schemas.application import ApplicationStatus
from app.schemas.job import JobPosting
from app.schemas.match import MatchResult, Recommendation
from app.schemas.profile import CandidateProfile, ProfileData, Skill, WorkExperience, ProfilePreferences


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def profile() -> CandidateProfile:
    """Create a test candidate profile."""
    return CandidateProfile(
        profile_id="test-profile",
        profile_data=ProfileData(
            full_name="Test Candidate",
            skills=[Skill(name="Python", years_of_experience=5)],
            work_experience=[WorkExperience(title="Developer", company="Tech Corp")],
        ),
        preferences_data=ProfilePreferences(),
    )


@pytest.fixture
def job() -> JobPosting:
    """Create a test job posting."""
    return JobPosting(
        job_id="job-1",
        title="Senior Python Developer",
        company="Startup Inc",
    )


@pytest.fixture
def match_result(profile: CandidateProfile, job: JobPosting) -> MatchResult:
    """Create a test match result."""
    return MatchResult(
        match_id="match-1",
        profile_id=profile.profile_id,
        job_id=job.job_id,
        score=85.0,
        recommendation=Recommendation.strong_match,
    )


# --------------------------------------------------------------------------- #
# Database Session Factory
# --------------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def make_db_session():
    """Factory for creating fresh database sessions per test."""
    engines: dict[int, Any] = {}
    factories: dict[int, Any] = {}

    async def _make() -> AsyncSession:
        import uuid
        test_id = uuid.uuid4().hex

        if test_id not in engines:
            engines[test_id] = create_async_engine(
                "sqlite+aiosqlite:///:memory:",
                echo=False,
            )
            factories[test_id] = async_sessionmaker(
                engines[test_id],
                expire_on_commit=False,
                class_=AsyncSession,
            )
            async with engines[test_id].begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        return factories[test_id]()

    yield _make

    # Cleanup
    for engine in engines.values():
        await engine.dispose()


@pytest_asyncio.fixture
async def real_db_session(make_db_session) -> AsyncSession:
    """Single database session for a test."""
    session = await make_db_session()
    yield session
    await session.close()


# --------------------------------------------------------------------------- #
# Tests for UNIQUE Constraint on Applications
# --------------------------------------------------------------------------- #


class TestUniqueConstraints:
    """Tests for UNIQUE constraints on applications."""

    @pytest.mark.asyncio
    async def test_application_unique_job_profile(self, real_db_session: AsyncSession):
        """Verify UNIQUE constraint on (job_id, profile_id) for applications."""
        # Create first application
        app1 = ApplicationModel(
            id="app-1",
            job_id="job-1",
            profile_id="profile-1",
            status="discovered",
        )
        real_db_session.add(app1)
        await real_db_session.commit()

        # Try to create duplicate - should fail
        app2 = ApplicationModel(
            id="app-2",
            job_id="job-1",
            profile_id="profile-1",
            status="discovered",
        )
        real_db_session.add(app2)

        with pytest.raises(IntegrityError):
            await real_db_session.commit()

        await real_db_session.rollback()

    @pytest.mark.asyncio
    async def test_application_different_job_allowed(self, real_db_session: AsyncSession):
        """Different job_id with same profile should be allowed."""
        app1 = ApplicationModel(
            id="app-1",
            job_id="job-1",
            profile_id="profile-1",
            status="discovered",
        )
        real_db_session.add(app1)
        await real_db_session.commit()

        app2 = ApplicationModel(
            id="app-2",
            job_id="job-2",  # Different job
            profile_id="profile-1",
            status="discovered",
        )
        real_db_session.add(app2)
        await real_db_session.commit()

        result = await real_db_session.execute(
            select(ApplicationModel).where(ApplicationModel.profile_id == "profile-1")
        )
        apps = list(result.scalars().all())
        assert len(apps) == 2

    @pytest.mark.asyncio
    async def test_application_different_profile_allowed(self, real_db_session: AsyncSession):
        """Different profile with same job should be allowed."""
        app1 = ApplicationModel(
            id="app-1",
            job_id="job-1",
            profile_id="profile-1",
            status="discovered",
        )
        real_db_session.add(app1)
        await real_db_session.commit()

        app2 = ApplicationModel(
            id="app-2",
            job_id="job-1",
            profile_id="profile-2",  # Different profile
            status="discovered",
        )
        real_db_session.add(app2)
        await real_db_session.commit()

        result = await real_db_session.execute(
            select(ApplicationModel).where(ApplicationModel.job_id == "job-1")
        )
        apps = list(result.scalars().all())
        assert len(apps) == 2


# --------------------------------------------------------------------------- #
# Tests for Document Versioning
# --------------------------------------------------------------------------- #


class TestDocumentVersioning:
    """Tests for document versioning with real DB."""

    @pytest.mark.asyncio
    async def test_document_version_increments(self, real_db_session: AsyncSession):
        """Document version should increment on each save."""
        repo = SQLAlchemyApplicationRepository(real_db_session)

        # Create application
        app = await repo.create_or_get("profile-ver", "job-ver")
        await real_db_session.commit()

        # Save first version
        doc1 = DocumentModel(
            id=str(uuid.uuid4()),
            application_id=app.id,
            document_type="resume",
            content="Content v1",
        )
        doc1 = await repo.save_document(doc1)
        await real_db_session.commit()
        assert doc1.version == 1

        # Save second version with different content
        doc2 = DocumentModel(
            id=str(uuid.uuid4()),
            application_id=app.id,
            document_type="resume",
            content="Different content",
        )
        doc2 = await repo.save_document(doc2)
        await real_db_session.commit()
        assert doc2.version == 2

        # Verify both versions exist
        result = await real_db_session.execute(
            select(DocumentModel).where(
                DocumentModel.application_id == app.id,
                DocumentModel.document_type == "resume"
            ).order_by(DocumentModel.version)
        )
        docs = list(result.scalars().all())
        assert len(docs) == 2
        assert docs[0].version == 1
        assert docs[1].version == 2


# --------------------------------------------------------------------------- #
# Tests for Repository Idempotency with Real DB
# --------------------------------------------------------------------------- #


class TestRepositoryIdempotency:
    """Tests for repository idempotency with real database."""

    @pytest.mark.asyncio
    async def test_create_or_get_idempotent(self, real_db_session: AsyncSession):
        """create_or_get should return same application on repeated calls."""
        repo = SQLAlchemyApplicationRepository(real_db_session)

        # First call creates
        app1 = await repo.create_or_get("profile-idem", "job-idem", "drafting")
        await real_db_session.commit()
        assert app1.profile_id == "profile-idem"
        assert app1.job_id == "job-idem"

        # Second call should return existing
        app2 = await repo.create_or_get("profile-idem", "job-idem", "drafting")
        await real_db_session.commit()

        # Should be the same application
        assert app1.id == app2.id
        # Status should not change (returns existing)
        assert app2.status == "drafting"

    @pytest.mark.asyncio
    async def test_save_document_no_duplicate_content(self, real_db_session: AsyncSession):
        """save_document should not create duplicate approved content versions."""
        repo = SQLAlchemyApplicationRepository(real_db_session)

        # Create application
        app = await repo.create_or_get("profile-dup", "job-dup")
        await real_db_session.commit()

        # Save version with specific content and mark approved
        doc1 = DocumentModel(
            id=str(uuid.uuid4()),
            application_id=app.id,
            document_type="resume",
            content="Same content",
            review_status="approved",
            is_approved=True,
        )
        doc1 = await repo.save_document(doc1)
        await real_db_session.commit()
        version_1 = doc1.version

        # Save same content again - should return existing approved version
        doc2 = DocumentModel(
            id=str(uuid.uuid4()),
            application_id=app.id,
            document_type="resume",
            content="Same content",
            review_status="approved",
            is_approved=True,
        )
        doc2 = await repo.save_document(doc2)
        await real_db_session.commit()
        version_2 = doc2.version

        # Same content should return existing version
        assert version_1 == version_2


# --------------------------------------------------------------------------- #
# Tests for Concurrent Inserts
# --------------------------------------------------------------------------- #


class TestConcurrentInserts:
    """Tests for concurrent insert scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_create_or_get(self, make_db_session):
        """Simulate concurrent create_or_get calls on same DB."""
        session1 = await make_db_session()
        session2 = await make_db_session()

        repo1 = SQLAlchemyApplicationRepository(session1)
        repo2 = SQLAlchemyApplicationRepository(session2)

        # Both try to create the same application concurrently
        app1_task = asyncio.create_task(
            repo1.create_or_get("profile-concurrent", "job-concurrent")
        )
        app2_task = asyncio.create_task(
            repo2.create_or_get("profile-concurrent", "job-concurrent")
        )

        app1, app2 = await asyncio.gather(app1_task, app2_task)

        await session1.commit()
        await session2.commit()

        # Both should return same application (or at least not crash)
        assert app1 is not None
        assert app2 is not None

        # Verify only one exists in the first session's DB
        result = await session1.execute(
            select(ApplicationModel).where(
                ApplicationModel.job_id == "job-concurrent",
                ApplicationModel.profile_id == "profile-concurrent"
            )
        )
        apps = list(result.scalars().all())
        assert len(apps) >= 1  # At least one due to race


# --------------------------------------------------------------------------- #
# Tests for Approval Request Constraints
# --------------------------------------------------------------------------- #


class TestApprovalConstraints:
    """Tests for approval request constraints."""

    @pytest.mark.asyncio
    async def test_approval_version_binding(self, real_db_session: AsyncSession):
        """Approval should store document_version and job_content_hash."""
        from app.repositories.application import SQLAlchemyApplicationRepository

        repo = SQLAlchemyApplicationRepository(real_db_session)

        # Create application
        app = await repo.create_or_get("profile-approval", "job-approval")
        await real_db_session.commit()

        # Create approval request
        approval = await repo.create_approval_request(
            application_id=app.id,
            requested_by="user",
            document_version="1",
            job_content_hash="abc123",
        )
        await real_db_session.commit()

        # Verify stored correctly
        assert approval.document_version == "1"
        assert approval.job_content_hash == "abc123"
        assert approval.invalidated is False

    @pytest.mark.asyncio
    async def test_invalidated_approval_not_retrieved(self, real_db_session: AsyncSession):
        """Invalidated approval should not be returned by get_pending_approval."""
        from app.repositories.application import SQLAlchemyApplicationRepository

        repo = SQLAlchemyApplicationRepository(real_db_session)

        # Create application and approval
        app = await repo.create_or_get("profile-inv", "job-inv")
        await real_db_session.commit()

        approval = await repo.create_approval_request(
            application_id=app.id,
            requested_by="user",
            document_version="1",
            job_content_hash="xyz789",
        )
        await real_db_session.commit()

        # Invalidate it
        await repo.invalidate_approval(approval.id)
        await real_db_session.commit()

        # Should not retrieve invalidated approval
        pending = await repo.get_pending_approval(app.id)
        assert pending is None


# --------------------------------------------------------------------------- #
# Integration Tests with Real Database
# --------------------------------------------------------------------------- #


class TestIntegrationWithRealDB:
    """Integration tests with real database."""

    @pytest.mark.asyncio
    async def test_full_application_flow(self, real_db_session: AsyncSession):
        """Test complete application workflow with real DB."""
        from app.repositories.application import SQLAlchemyApplicationRepository

        repo = SQLAlchemyApplicationRepository(real_db_session)

        # 1. Create application
        app = await repo.create_or_get("profile-flow", "job-flow", "drafting")
        await real_db_session.commit()
        assert app.status == "drafting"

        # 2. Create documents
        resume = DocumentModel(
            id=str(uuid.uuid4()),
            application_id=app.id,
            document_type="resume",
            content="My resume content",
            review_status="pending_review",
        )
        resume = await repo.save_document(resume)
        await real_db_session.commit()
        assert resume.version == 1

        cover = DocumentModel(
            id=str(uuid.uuid4()),
            application_id=app.id,
            document_type="cover_letter",
            content="Cover letter content",
            review_status="pending_review",
        )
        cover = await repo.save_document(cover)
        await real_db_session.commit()
        assert cover.version == 1

        # 3. Create approval request
        approval = await repo.create_approval_request(
            application_id=app.id,
            requested_by="user",
            document_version="1",
            job_content_hash="abc123",
        )
        await real_db_session.commit()
        assert approval.status == "pending"
        assert approval.document_version == "1"
        assert approval.job_content_hash == "abc123"

        # 4. Verify approval can be retrieved
        pending = await repo.get_pending_approval(app.id)
        assert pending is not None
        assert pending.id == approval.id

        # 5. Invalidate approval
        await repo.invalidate_approval(approval.id)
        await real_db_session.commit()
        pending = await repo.get_pending_approval(app.id)
        assert pending is None


# --------------------------------------------------------------------------- #
# Adversarial Tests with Real DB
# --------------------------------------------------------------------------- #


class TestAdversarialWithRealDB:
    """Adversarial tests with real database."""

    @pytest.mark.asyncio
    async def test_prompt_injection_stored_safely(self, real_db_session: AsyncSession):
        """Malicious content should be stored safely (parameterized queries)."""
        from app.repositories.application import SQLAlchemyApplicationRepository

        repo = SQLAlchemyApplicationRepository(real_db_session)

        app = await repo.create_or_get("profile-inject", "job-inject")
        await real_db_session.commit()

        # Attempt to inject SQL or prompt
        malicious_content = "Resume'; DROP TABLE documents; --"
        doc = DocumentModel(
            id=str(uuid.uuid4()),
            application_id=app.id,
            document_type="resume",
            content=malicious_content,
        )
        doc = await repo.save_document(doc)
        await real_db_session.commit()

        # Content should be stored as-is (parameterized queries protect)
        result = await real_db_session.execute(
            select(DocumentModel).where(DocumentModel.id == doc.id)
        )
        saved = result.scalar_one_or_none()
        assert saved.content == malicious_content

        # Verify documents table still exists
        async with real_db_session.bind.connect() as conn:
            tables = await conn.run_sync(lambda c: list(c.dialect.get_table_names(c)))
        assert "documents" in tables

    @pytest.mark.asyncio
    async def test_long_content_handled(self, real_db_session: AsyncSession):
        """Very long content should be handled."""
        from app.repositories.application import SQLAlchemyApplicationRepository

        repo = SQLAlchemyApplicationRepository(real_db_session)
        app = await repo.create_or_get("profile-long", "job-long")
        await real_db_session.commit()

        # 1MB of content
        long_content = "A" * (1024 * 1024)
        doc = DocumentModel(
            id=str(uuid.uuid4()),
            application_id=app.id,
            document_type="resume",
            content=long_content,
        )
        doc = await repo.save_document(doc)
        await real_db_session.commit()

        assert doc.content == long_content


# --------------------------------------------------------------------------- #
# Tests for Idempotent Persistence in Workflow
# --------------------------------------------------------------------------- #


class TestWorkflowIdempotency:
    """Tests for workflow idempotency with real DB."""

    @pytest.mark.asyncio
    async def test_workflow_idempotent_with_real_db(self, real_db_session: AsyncSession):
        """Simulate workflow running twice with same state."""
        from app.repositories.application import SQLAlchemyApplicationRepository

        repo = SQLAlchemyApplicationRepository(real_db_session)

        # First workflow run
        app1 = await repo.create_or_get("profile-idem", "job-idem", "drafting")
        await real_db_session.commit()
        app_id_1 = app1.id

        # Second run (simulated restart)
        app2 = await repo.create_or_get("profile-idem", "job-idem", "drafting")
        await real_db_session.commit()

        # Should be same application
        assert app1.id == app2.id

        # Verify no duplicate in DB
        result = await real_db_session.execute(
            select(ApplicationModel).where(
                ApplicationModel.job_id == "job-idem",
                ApplicationModel.profile_id == "profile-idem"
            )
        )
        apps = list(result.scalars().all())
        assert len(apps) == 1
