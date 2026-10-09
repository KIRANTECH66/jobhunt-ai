"""FastAPI API layer.

Defines the HTTP endpoints for the JobHunt AI backend. All endpoints return
Pydantic models and use dependency injection for database sessions and
repositories.
"""

from __future__ import annotations

from app.api.v1 import api_router

__all__ = ["api_router"]