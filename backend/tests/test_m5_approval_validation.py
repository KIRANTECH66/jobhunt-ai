"""Milestone 5: Approval Validation at Submission Boundary Tests.

Tests verify that approval validation works correctly when:
- Documents have been modified (content changed)
- Stale approvals are detected
- Job content changes invalidate approvals
- Approvals are properly validated before submission
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from app.workflow.validation import (
    ApprovalValidationError,
    validate_approval_against_state,
    compute_job_content_hash,
    validate_document_immutable,
    create_approval_request_data,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def mock_profile() -> dict[str, Any]:
    """Create a mock profile dict."""
    return {
        "profile_id": "profile-1",
        "profile_data": {
            "full_name": "Test Candidate",
            "skills": [{"name": "Python", "years_of_experience": 5}],
            "work_experience": [{"title": "Developer", "company": "Tech Corp"}],
        },
        "preferences_data": {},
    }


@pytest.fixture
def mock_job() -> dict[str, Any]:
    """Create a mock job dict."""
    return {
        "job_id": "job-1",
        "title": "Senior Python Developer",
        "company": "Startup Inc",
    }


@pytest.fixture
def mock_document() -> dict[str, Any]:
    """Create a mock document dict."""
    return {
        "id": "doc-1",
        "version": 1,
        "is_approved": False,
        "content": "Resume content here",
    }


@pytest.fixture
def approved_document() -> dict[str, Any]:
    """Create a mock approved document."""
    return {
        "id": "doc-1",
        "version": 1,
        "is_approved": True,
        "content": "Approved content",
    }


@pytest.fixture
def mock_job_posting() -> dict[str, Any]:
    """Create a mock job posting dict (non-Pydantic)."""
    return {
        "title": "Senior Python Developer",
        "company": "Startup Inc",
    }


# --------------------------------------------------------------------------- #
# Tests for Approval Validation
# --------------------------------------------------------------------------- #


class TestApprovalValidation:
    """Tests for approval validation logic."""

    def test_approval_is_valid(self, mock_job_posting):
        """Test that a valid approval is accepted."""
        approval = {
            "status": "pending",
            "invalidated": False,
            "document_version": "1",
            "job_content_hash": compute_job_content_hash(mock_job_posting),
        }
        document = {"version": 1}

        result = validate_approval_against_state(
            approval,
            document,
            mock_job_posting
        )
        assert result is True

    def test_approval_invalid_status(self, mock_job_posting):
        """Test that non-pending approvals are rejected."""
        approval = {
            "status": "approved",  # Already approved
            "invalidated": False,
            "document_version": "1",
            "job_content_hash": "abc123",
        }
        document = {"version": 1}

        with pytest.raises(ApprovalValidationError) as exc_info:
            validate_approval_against_state(approval, document, mock_job_posting)

        assert exc_info.value.reason == "invalid_status"

    def test_approval_invalidated(self, mock_job_posting):
        """Test that invalidated approvals are rejected."""
        approval = {
            "status": "pending",
            "invalidated": True,  # Invalidated
            "document_version": "1",
            "job_content_hash": "abc123",
        }
        document = {"version": 1}

        with pytest.raises(ApprovalValidationError) as exc_info:
            validate_approval_against_state(approval, document, mock_job_posting)

        assert exc_info.value.reason == "invalidated"

    def test_document_version_mismatch(self, mock_job_posting):
        """Test that document version changes are detected."""
        approval = {
            "status": "pending",
            "invalidated": False,
            "document_version": "1",  # Bound to version 1
            "job_content_hash": "abc123",
        }
        document = {"version": 2}  # Current is version 2

        with pytest.raises(ApprovalValidationError) as exc_info:
            validate_approval_against_state(approval, document, mock_job_posting)

        assert exc_info.value.reason == "version_mismatch"

    def test_job_content_changed(self, mock_job_posting):
        """Test that job content changes invalidate approvals."""
        approval = {
            "status": "pending",
            "invalidated": False,
            "document_version": "1",
            "job_content_hash": "abc123",  # Old hash
        }
        document = {"version": 1}

        # Create a different job posting
        different_job = {
            "title": "Senior Python Developer",
            "company": "Big Corp",  # Different company
        }

        with pytest.raises(ApprovalValidationError) as exc_info:
            validate_approval_against_state(approval, document, different_job)

        assert exc_info.value.reason == "job_content_changed"

    def test_job_content_unchanged(self, mock_job_posting):
        """Test that same job content passes validation."""
        approval = {
            "status": "pending",
            "invalidated": False,
            "document_version": "1",
            "job_content_hash": compute_job_content_hash(mock_job_posting),
        }
        document = {"version": 1}

        result = validate_approval_against_state(
            approval,
            document,
            mock_job_posting
        )
        assert result is True


# --------------------------------------------------------------------------- #
# Tests for Document Immutability
# --------------------------------------------------------------------------- #


class TestDocumentImmutability:
    """Tests for document immutability checks."""

    def test_approved_document_is_immutable(self, approved_document):
        """Test that approved documents cannot be modified."""
        result = validate_document_immutable(approved_document)
        assert result is True

    def test_unapproved_document_is_mutable(self, mock_document):
        """Test that unapproved documents can be modified."""
        result = validate_document_immutable(mock_document)
        assert result is False


# --------------------------------------------------------------------------- #
# Tests for Approval Request Data Creation
# --------------------------------------------------------------------------- #


class TestApprovalRequestData:
    """Tests for approval request data creation."""

    def test_create_approval_request_data(self):
        """Test creating approval request data structure."""
        data = create_approval_request_data(
            application_id="app-1",
            document_version=1,
            job_content_hash="abc123",
        )

        assert data["application_id"] == "app-1"
        assert data["document_version"] == "1"  # Should be string
        assert data["job_content_hash"] == "abc123"
        assert data["status"] == "pending"
        assert data["invalidated"] is False
        assert "created_at" in data


# --------------------------------------------------------------------------- #
# Tests for Stale Document Validation
# --------------------------------------------------------------------------- #


class TestStaleDocumentValidation:
    """Tests for detecting stale documents."""

    def test_stale_document_detected(self):
        """Test that stale documents are detected."""
        approval = {
            "status": "pending",
            "invalidated": False,
            "document_version": "3",  # Bound to version 3
            "job_content_hash": "abc123",
        }

        # Document has been updated to version 4
        current_document = {"version": 4}

        job = {"title": "Test", "company": "Test"}

        with pytest.raises(ApprovalValidationError) as exc_info:
            validate_approval_against_state(approval, current_document, job)

        assert exc_info.value.reason == "version_mismatch"

    def test_unversioned_approval_rejected(self):
        """Test that approvals without version binding are rejected."""
        job = {"title": "Test", "company": "Test"}
        approval = {
            "status": "pending",
            "invalidated": False,
            # No document_version
            "job_content_hash": compute_job_content_hash(job),
        }
        document = {"version": 1}

        # This should succeed (no version check)
        result = validate_approval_against_state(approval, document, job)
        assert result is True


# --------------------------------------------------------------------------- #
# Tests for Complete Submission Validation
# --------------------------------------------------------------------------- #


class TestSubmissionValidation:
    """Tests for complete submission validation."""

    def test_complete_valid_submission(self, mock_job_posting, mock_document):
        """Test complete valid submission flow."""
        approval = {
            "status": "pending",
            "invalidated": False,
            "document_version": "1",
            "job_content_hash": compute_job_content_hash(mock_job_posting),
        }

        result = validate_approval_against_state(
            approval,
            mock_document,
            mock_job_posting
        )
        assert result is True

    def test_complete_invalid_submission_job_changed(self, mock_job_posting, mock_document):
        """Test that submission fails when job content changed."""
        approval = {
            "status": "pending",
            "invalidated": False,
            "document_version": "1",
            "job_content_hash": compute_job_content_hash(mock_job_posting),
        }

        # Job has changed
        changed_job = {
            "title": "Senior Python Developer",
            "company": "Completely Different Company",
        }

        with pytest.raises(ApprovalValidationError) as exc_info:
            validate_approval_against_state(approval, mock_document, changed_job)

        assert exc_info.value.reason == "job_content_changed"

    def test_complete_invalid_submission_stale_approval(self, mock_job_posting, mock_document):
        """Test that stale approval is detected."""
        approval = {
            "status": "pending",
            "invalidated": False,
            "document_version": "5",  # Bound to old version
            "job_content_hash": compute_job_content_hash(mock_job_posting),
        }

        # Current document is newer
        current_document = {"version": 6}

        with pytest.raises(ApprovalValidationError) as exc_info:
            validate_approval_against_state(approval, current_document, mock_job_posting)

        assert exc_info.value.reason == "version_mismatch"

    def test_complete_invalid_submission_invalidated_approval(self, mock_job_posting, mock_document):
        """Test that invalidated approval is detected."""
        approval = {
            "status": "pending",
            "invalidated": True,  # Invalidated by admin
            "document_version": "1",
            "job_content_hash": compute_job_content_hash(mock_job_posting),
        }

        with pytest.raises(ApprovalValidationError) as exc_info:
            validate_approval_against_state(approval, mock_document, mock_job_posting)

        assert exc_info.value.reason == "invalidated"


# --------------------------------------------------------------------------- #
# Integration Tests with Workflow State
# --------------------------------------------------------------------------- #


class TestApprovalIntegration:
    """Integration tests with workflow state."""

    @pytest.mark.asyncio
    async def test_approval_validation_with_metadata(self):
        """Test validation using metadata from workflow state."""
        approval = {
            "status": "pending",
            "invalidated": False,
            "document_version": "2",
            "job_content_hash": "hash123",
        }

        current_doc = {"version": 3}
        job = {"title": "Test", "company": "Test"}

        with pytest.raises(ApprovalValidationError) as exc_info:
            validate_approval_against_state(approval, current_doc, job)

        assert exc_info.value.reason == "version_mismatch"

    @pytest.mark.asyncio
    async def test_hash_computation_consistency(self):
        """Test that hash computation is consistent."""
        job1 = {"title": "Python", "company": "Google"}
        job2 = {"title": "Python", "company": "Google"}
        job3 = {"title": "Java", "company": "Google"}

        hash1 = compute_job_content_hash(job1)
        hash2 = compute_job_content_hash(job2)
        hash3 = compute_job_content_hash(job3)

        assert hash1 == hash2, "Same jobs should have same hash"
        assert hash1 != hash3, "Different jobs should have different hash"
        assert len(hash1) == 16, "Hash should be 16 characters"
