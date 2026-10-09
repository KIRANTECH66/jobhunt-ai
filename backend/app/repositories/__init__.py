"""Repository layer.

Translates between the service layer's abstract repository interface and
the SQLAlchemy ORM. Provides async CRUD operations for all entities.
"""

from __future__ import annotations

from app.repositories.job import SQLAlchemyJobRepository
from app.repositories.match import SQLAlchemyMatchRepository
from app.repositories.profile import SQLAlchemyProfileRepository
from app.repositories.audit import SQLAlchemyAuditRepository

__all__ = [
    "JobRepository",
    "SQLAlchemyJobRepository",
    "SQLAlchemyMatchRepository",
    "SQLAlchemyProfileRepository",
    "AuditRepository",
    "SQLAlchemyAuditRepository",
]