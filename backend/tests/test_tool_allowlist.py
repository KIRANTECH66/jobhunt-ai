"""Test tool allowlist enforcement."""

from __future__ import annotations

import pytest
from app.tools.registry import InMemoryToolRegistry, ToolDefinition


class TestToolAllowlistEnforcement:
    """Test that tool allowlists are enforced correctly."""

    def test_empty_allowlist_allows_all_tools(self) -> None:
        """Test that an empty allowlist allows all registered tools."""
        registry = InMemoryToolRegistry()
        allowed, reason = registry.validate_tool_call("unknown_agent", "get_candidate_profile")
        assert allowed is True
        assert reason == "ok"

    def test_specific_allowlist_rejects_unlisted_tools(self) -> None:
        """Test that a specific allowlist rejects unlisted tools."""
        registry = InMemoryToolRegistry()
        registry.set_allowlist("job_matcher", ["get_candidate_profile"])

        allowed, reason = registry.validate_tool_call("job_matcher", "get_candidate_profile")
        assert allowed is True

        allowed, reason = registry.validate_tool_call("job_matcher", "get_job_posting")
        assert allowed is False
        assert "not allowed" in reason.lower()

    def test_nonexistent_tool_is_rejected(self) -> None:
        """Test that non-existent tools are rejected."""
        registry = InMemoryToolRegistry()
        allowed, reason = registry.validate_tool_call("any_agent", "nonexistent_tool")
        assert allowed is False
        assert "does not exist" in reason.lower()

    def test_allowlist_is_per_agent(self) -> None:
        """Test that allowlists are per-agent, not global."""
        registry = InMemoryToolRegistry()
        registry.set_allowlist("agent_a", ["get_candidate_profile"])
        registry.set_allowlist("agent_b", ["get_job_posting"])

        allowed_a, _ = registry.validate_tool_call("agent_a", "get_candidate_profile")
        allowed_b, _ = registry.validate_tool_call("agent_b", "get_job_posting")
        assert allowed_a is True
        assert allowed_b is True

        # Cross-agent access should be denied
        allowed_a_bad, _ = registry.validate_tool_call("agent_a", "get_job_posting")
        assert allowed_a_bad is False

    @pytest.mark.asyncio
    async def test_invalid_arguments_are_handled(self) -> None:
        """Test that invalid arguments are handled gracefully."""
        registry = InMemoryToolRegistry()
        result = await registry.execute("get_candidate_profile", {})  # Missing required argument
        # Should return a failure result (tool validates args)
        assert result is not None
        assert result.success is False
        assert "missing" in result.error.lower() or "required" in result.error.lower()


class TestToolExecution:
    """Test tool execution with the registry."""

    @pytest.mark.asyncio
    async def test_execute_registered_tool(self) -> None:
        """Test executing a registered tool."""
        registry = InMemoryToolRegistry()
        result = await registry.execute("get_candidate_profile", {"profile_id": "test-123"})
        assert result.success is True
        assert result.tool_name == "get_candidate_profile"
        assert result.content["id"] == "test-123"

    @pytest.mark.asyncio
    async def test_execute_unregistered_tool(self) -> None:
        """Test executing an unregistered tool."""
        registry = InMemoryToolRegistry()
        result = await registry.execute("nonexistent_tool", {})
        assert result.success is False
        assert "does not exist" in result.error.lower()

    @pytest.mark.asyncio
    async def test_tool_with_approval_required(self) -> None:
        """Test that tools with requires_approval=True are flagged."""
        registry = InMemoryToolRegistry()
        result = await registry.execute("save_match_result", {"job_id": "job-1", "match_result": {}})
        assert result.metadata.get("requires_approval") is True
