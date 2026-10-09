"""Agent Harness.

A shared Python execution interface responsible for:
- Input validation
- Agent configuration (model, tools, timeouts, retries)
- Model adapter invocation
- Tool allowlist enforcement
- Structured output validation
- Timeout and retry policy
- Trace and audit emission
- Policy enforcement
"""

from __future__ import annotations

from app.harness.harness import AgentHarness, AgentSpec, HarnessError, HarnessResult

__all__ = [
    "AgentHarness",
    "AgentSpec",
    "HarnessError",
    "HarnessResult",
]