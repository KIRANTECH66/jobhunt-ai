"""Application repository.

Manages persistence of applications, documents, and approval requests.
Provides versioned document operations and idempotent writes.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application as ApplicationModel
from app.models.application import ApprovalRequest as ApprovalRequestModel
from app.models.application import Document as DocumentModel
from app.schemas.application import ApplicationStatus

logger = logging.getLogger(__name__)


class SQLAlchemyApplicationRepository:
    """Repository for managing applications, documents, and approvals."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, application_id: str) -> ApplicationModel | None:
        """Return an application by ID."""
        stmt = select(ApplicationModel).where(ApplicationModel.id == application_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_job_and_profile(self, job_id: str, profile_id: str) -> ApplicationModel | None:
        """Return an application for a specific job and profile pair."""
        stmt = (
            select(ApplicationModel)
            .where(ApplicationModel.job_id == job_id)
            .where(ApplicationModel.profile_id == profile_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_or_get(self, profile_id: str, job_id: str, status: str = ApplicationStatus.discovered) -> ApplicationModel:
        """Create or retrieve an application for the given job/profile pair.

        Returns the existing application if one already exists for this pair.
        This ensures idempotent workflow execution.
        """
        existing = await self.get_by_job_and_profile(job_id, profile_id)
        if existing:
            return existing

        application = ApplicationModel(
            id=str(__import__('uuid').uuid4()),
            profile_id=profile_id,
            job_id=job_id,
            status=status,
        )
        self.session.add(application)
        await self.session.flush()
        return application

    async def save_document(self, document: DocumentModel) -> DocumentModel:
        """Save a document version. Creates new version if content differs."""
        # Check if approved document exists with same content
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.application_id == document.application_id)
            .where(DocumentModel.document_type == document.document_type)
            .where(DocumentModel.is_approved == True)
            .where(DocumentModel.content == document.content)
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Content unchanged, return existing
            return existing

        # Get max version for this document type
        if document.application_id:
            stmt = (
                select(DocumentModel)
                .where(DocumentModel.application_id == document.application_id)
                .where(DocumentModel.document_type == document.document_type)
                .order_by(DocumentModel.version.desc())
                .limit(1)
            )
            result = await self.session.execute(stmt)
            latest = result.scalar_one_or_none()
            new_version = (latest.version + 1) if latest else 1
        else:
            new_version = 1

        document.version = new_version
        self.session.add(document)
        await self.session.flush()
        return document

    async def get_latest_document(self, application_id: str, document_type: str) -> DocumentModel | None:
        """Get the latest version of a document."""
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.application_id == application_id)
            .where(DocumentModel.document_type == document_type)
            .order_by(DocumentModel.version.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_documents_by_application(self, application_id: str) -> list[DocumentModel]:
        """Get all documents for an application."""
        stmt = select(DocumentModel).where(DocumentModel.application_id == application_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_approval_request(self, application_id: str, requested_by: str,
                                       document_version: str | None = None,
                                       job_content_hash: str | None = None) -> ApprovalRequestModel:
        """Create an approval request bound to document version and job hash."""
        approval = ApprovalRequestModel(
            id=str(__import__('uuid').uuid4()),
            application_id=application_id,
            action="submit_application",
            status="pending",
            document_version=document_version,
            job_content_hash=job_content_hash,
        )
        self.session.add(approval)
        await self.session.flush()
        return approval

    async def get_pending_approval(self, application_id: str) -> ApprovalRequestModel | None:
        """Get the pending approval for an application."""
        stmt = (
            select(ApprovalRequestModel)
            .where(ApprovalRequestModel.application_id == application_id)
            .where(ApprovalRequestModel.status == "pending")
            .where(ApprovalRequestModel.invalidated == False)
            .order_by(ApprovalRequestModel.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def invalidate_approval(self, approval_id: str) -> bool:
        """Invalidate an approval request."""
        stmt = select(ApprovalRequestModel).where(ApprovalRequestModel.id == approval_id)
        result = await self.session.execute(stmt)
        approval = result.scalar_one_or_none()
        if approval:
            approval.invalidated = True
            approval.status = "superseded"
            await self.session.flush()
            return True
        return False
