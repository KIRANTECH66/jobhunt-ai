"""Agent implementations.

Each agent is a thin wrapper around the shared Agent Harness. The harness
handles input validation, tool resolution, model invocation, retries, and
audit emission. The agent defines its spec (instructions, schemas, tools).
"""

from __future__ import annotations

from app.agents.job_matcher import JobMatcherAgent

__all__ = ["JobMatcherAgent"]