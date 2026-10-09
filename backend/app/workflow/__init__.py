"""LangGraph workflow definitions.

Defines the primary ``job_search_workflow`` using LangGraph's stateful
workflow engine. The workflow orchestrates the complete job search process:
validating search requests, ingesting jobs, deduplicating, matching, drafting
application materials, reviewing quality, and presenting approval-ready drafts.
"""

from __future__ import annotations

from app.workflow.state import WorkflowState
from app.workflow.graph import build_job_search_graph

__all__ = ["WorkflowState", "build_job_search_graph"]