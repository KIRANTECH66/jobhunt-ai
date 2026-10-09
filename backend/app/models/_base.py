"""Shared declarative base for the ORM models.

``Base`` is the SQLAlchemy declarative base. ``Timestamped`` is a mixin that
adds ``created_at`` / ``updated_at`` columns, populated automatically on
insert and update.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Timestamped:
    """Mixin adding created_at/updated_at audit columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )