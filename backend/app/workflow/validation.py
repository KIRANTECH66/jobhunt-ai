"""Workflow validation and approval integrity checks.

Provides functions to validate approval requests against document versions
and job content hashes. Enforces immutability rules for approved documents.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ApprovalValidationError(Exception):
    """Raised when an approval request is invalid."""

    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


def validate_approval_against_state(
    approval: dict[str, Any],
    document: dict[str, Any],
    job_posting: dict[str, Any],
) -> bool:
    """Validate that an approval request is still valid.

    Checks:
    - Document version matches approval's bound version
    - Job content hash matches approval's bound hash
    - Approval hasn't been invalidated
    - Approval status is pending

    Args:
        approval: Approval request data from state
        document: Document data to validate against
        job_posting: Job posting data to compute hash

    Returns:
        True if approval is valid, False otherwise

    Raises:
        ApprovalValidationError: If validation fails with specific reason
    """
    # 1. Check approval status
    if approval.get("status") != "pending":
        raise ApprovalValidationError(
            f"Approval is not pending (status: {approval.get('status')})",
            "invalid_status",
        )

    # 2. Check invalidation flag
    if approval.get("invalidated"):
        raise ApprovalValidationError(
            "Approval has been invalidated",
            "invalidated",
        )

    # 3. Check document version binding
    approval_version = approval.get("document_version")
    document_version = document.get("version")

    if approval_version is not None and str(document_version) != str(approval_version):
        raise ApprovalValidationError(
            f"Document version mismatch: approval bound to v{approval_version}, "
            f"but current is v{document_version}",
            "version_mismatch",
        )

    # 4. Check job content hash binding
    approval_hash = approval.get("job_content_hash")
    current_hash = compute_job_content_hash(job_posting)

    if approval_hash is not None and approval_hash != current_hash:
        raise ApprovalValidationError(
            f"Job content has changed: approval bound to hash {approval_hash}, "
            f"but current hash is {current_hash}",
            "job_content_changed",
        )

    return True


def compute_job_content_hash(job_posting: Any) -> str:
    """Compute canonical hash of job content for binding to approvals.

    Uses job title + company as the canonical fields.
    Accepts either a dict or a JobPosting model.
    """
    if hasattr(job_posting, 'model_dump'):
        # Pydantic model
        data = job_posting.model_dump()
    else:
        data = job_posting

    title = data.get("title", "") or ""
    company = data.get("company", "") or ""
    content = f"{title}:{company}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def validate_document_immutable(approved_doc: dict[str, Any]) -> bool:
    """Check that an approved document cannot be modified.

    Returns True if document is immutable (approved), False otherwise.
    """
    if approved_doc.get("is_approved"):
        return True
    return False


def create_approval_request_data(
    application_id: str,
    document_version: int,
    job_content_hash: str,
) -> dict[str, Any]:
    """Create structured approval request data."""
    return {
        "application_id": application_id,
        "action": "submit_application",
        "status": "pending",
        "document_version": str(document_version),
        "job_content_hash": job_content_hash,
        "invalidated": False,
        "created_at": datetime.utcnow().isoformat(),
    }
