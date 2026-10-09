"""Tests for the harness tool-calling cycle.

Verifies that:
- The harness detects tool calls in a model response.
- Tool calls are validated against the allowlist before execution.
- Results are returned to the model and the loop continues.
- Malformed calls, unknown tools, and execution errors are recorded.
- Duplicate call ids are skipped.
- Iteration limits terminate the loop.
- Ordinary model responses (no tool calls) work unchanged.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch

from app.harness.harness import (
    AgentHarness,
    AgentSpec,
    HarnessError,
    DEFAULT_MAX_TOOL_ITERATIONS,
)
from app.llm.model_adapter import MockModelAdapter, ModelResponse
from app.tools.registry import InMemoryToolRegistry, ToolDefinition


# --------------------------------------------------------------------------- #
# Test data
# --------------------------------------------------------------------------- #


def make_tool_call(name: str, args: dict | None = None, call_id: str = "call-1"):
    """Build a normalized tool call dict."""
    return {"id": call_id, "name": name, "arguments": args or {}}


# --------------------------------------------------------------------------- #
# Basic cycles
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_basic_tool_call_cycle() -> None:
    """A single tool call followed by a final answer completes."""
    registry = InMemoryToolRegistry()
    registry.set_allowlist("matcher", ["get_candidate_profile"])
    harness = AgentHarness(tool_registry=registry, model_adapter=MockModelAdapter())

    first = ModelResponse(
        content="",
        model="mock",
        tool_calls=[make_tool_call("get_candidate_profile", {"profile_id": "prof-1"})],
    )
    second = ModelResponse(
        content=json.dumps({"score": 85, "recommendation": "strong_match"}),
        model="mock",
        finish_reason="stop",
    )

    harness.model_adapter.set_response("get_candidate_profile", first)
    harness.model_adapter.set_response(second.content, second)

    spec = AgentSpec(
        name="matcher",
        instructions="Match the job to the profile.",
        input_schema={"type": "object", "required": []},
        output_schema={"type": "object", "required": ["score", "recommendation"]},
        tools=["get_candidate_profile"],
    )

    result = await harness.run(spec, {})
    assert result.success is True
    assert result.output["score"] == 85
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "get_candidate_profile"
    assert result.tool_calls[0]["id"] == "call-1"
    assert len(result.tool_results) == 1
    assert result.tool_results[0].success is True
    assert result.tool_results[0].content["id"] == "prof-1"

    # Trace shows two model calls and the tool call + result messages.
    steps = result.trace["steps"]
    model_calls = [s for s in steps if s.get("step", "").startswith("model_call")]
    assert len(model_calls) == 2

    # Conversation grew with assistant + tool message.
    assert len(result.trace["conversation"]) == 4


@pytest.mark.asyncio
async def test_multi_step_tool_cycle() -> None:
    """Multiple sequential tool calls before the final answer."""
    registry = InMemoryToolRegistry()
    registry.set_allowlist("matcher", ["get_candidate_profile", "get_job_posting"])
    harness = AgentHarness(tool_registry=registry, model_adapter=MockModelAdapter())

    prof_call = ModelResponse(
        content="",
        model="mock",
        tool_calls=[make_tool_call("get_candidate_profile", {"profile_id": "prof-1"})],
    )
    job_call = ModelResponse(
        content="",
        model="mock",
        tool_calls=[make_tool_call("get_job_posting", {"job_id": "job-1"})],
    )
    final = ModelResponse(
        content=json.dumps({"score": 85, "recommendation": "strong_match"}),
        model="mock",
    )

    harness.model_adapter.set_response("get_candidate_profile", prof_call)
    harness.model_adapter.set_response("get_job_posting", job_call)
    harness.model_adapter.set_response(final.content, final)

    spec = AgentSpec(
        name="matcher",
        instructions="Match the job to the profile.",
        input_schema={"type": "object", "required": []},
        output_schema={"type": "object", "required": ["score", "recommendation"]},
        tools=["get_candidate_profile", "get_job_posting"],
    )

    result = await harness.run(spec, {})
    assert result.success is True
    assert len(result.tool_calls) == 2
    names = [tc["name"] for tc in result.tool_calls]
    assert names == ["get_candidate_profile", "get_job_posting"]
    assert len(result.tool_results) == 2
    assert all(r.success for r in result.tool_results)


# --------------------------------------------------------------------------- #
# Allowlist and validation
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_unauthorized_tool_rejected_without_execution() -> None:
    """Tools not in the agent's allowlist are denied, not executed."""
    registry = InMemoryToolRegistry()
    registry.set_allowlist("matcher", ["get_candidate_profile"])
    harness = AgentHarness(tool_registry=registry, model_adapter=MockModelAdapter())

    prof_call = ModelResponse(
        content="",
        model="mock",
        tool_calls=[make_tool_call("get_job_posting", {"job_id": "job-1"})],
    )
    final = ModelResponse(
        content=json.dumps({"score": 85, "recommendation": "strong_match"}),
        model="mock",
    )

    harness.model_adapter.set_response("get_job_posting", prof_call)
    harness.model_adapter.set_response(final.content, final)

    spec = AgentSpec(
        name="matcher",
        instructions="Match the job to the profile.",
        input_schema={"type": "object", "required": []},
        output_schema={"type": "object", "required": ["score", "recommendation"]},
        tools=["get_candidate_profile", "get_job_posting"],
    )

    result = await harness.run(spec, {})
    assert result.success is True
    assert len(result.tool_calls) == 1
    assert len(result.tool_results) == 1
    denied = result.tool_results[0]
    assert denied.success is False
    assert "not authorized" in denied.error

    # The tool function was never invoked (placeholder would return 'job-1').
    assert denied.content.get("id") != "job-1"


@pytest.mark.asyncio
async def test_unknown_tool_is_rejected() -> None:
    """Tool names that do not exist are rejected."""
    registry = InMemoryToolRegistry()
    registry.set_allowlist("matcher", ["get_candidate_profile"])
    harness = AgentHarness(tool_registry=registry, model_adapter=MockModelAdapter())

    prof_call = ModelResponse(
        content="",
        model="mock",
        tool_calls=[make_tool_call("nonexistent_tool", {"foo": "bar"})],
    )
    final = ModelResponse(
        content=json.dumps({"score": 85, "recommendation": "strong_match"}),
        model="mock",
    )

    harness.model_adapter.set_response("nonexistent_tool", prof_call)
    harness.model_adapter.set_response(final.content, final)

    spec = AgentSpec(
        name="matcher",
        instructions="Match the job to the profile.",
        input_schema={"type": "object", "required": []},
        output_schema={"type": "object", "required": ["score", "recommendation"]},
        tools=["get_candidate_profile"],
    )

    result = await harness.run(spec, {})
    assert result.success is True
    assert result.tool_results[0].success is False
    assert "does not exist" in result.tool_results[0].error


@pytest.mark.asyncio
async def test_malformed_arguments_are_reported_not_crashed() -> None:
    """Invalid arguments yield a failed tool result, not an exception."""
    registry = InMemoryToolRegistry()
    registry.set_allowlist("matcher", ["get_candidate_profile"])
    harness = AgentHarness(tool_registry=registry, model_adapter=MockModelAdapter())

    prof_call = ModelResponse(
        content="",
        model="mock",
        tool_calls=[make_tool_call("get_candidate_profile", {"profile_id": 123})],
    )
    final = ModelResponse(
        content=json.dumps({"score": 85, "recommendation": "strong_match"}),
        model="mock",
    )

    harness.model_adapter.set_response("get_candidate_profile", prof_call)
    harness.model_adapter.set_response(final.content, final)

    spec = AgentSpec(
        name="matcher",
        instructions="Match the job to the profile.",
        input_schema={"type": "object", "required": []},
        output_schema={"type": "object", "required": ["score", "recommendation"]},
        tools=["get_candidate_profile"],
    )

    result = await harness.run(spec, {})
    assert result.success is True
    denied = result.tool_results[0]
    assert denied.success is False
    assert "must be a string" in denied.error or "required" in denied.error


@pytest.mark.asyncio
async def test_duplicate_call_id_is_skipped() -> None:
    """The same call id is executed once even if returned repeatedly."""
    registry = InMemoryToolRegistry()
    registry.set_allowlist("matcher", ["get_candidate_profile"])
    harness = AgentHarness(tool_registry=registry, model_adapter=MockModelAdapter())

    call = ModelResponse(
        content="",
        model="mock",
        tool_calls=[make_tool_call("get_candidate_profile", {"profile_id": "prof-1"})],
    )
    final = ModelResponse(
        content=json.dumps({"score": 85, "recommendation": "strong_match"}),
        model="mock",
    )

    harness.model_adapter.set_response("get_candidate_profile", call)
    harness.model_adapter.set_response(final.content, final)

    spec = AgentSpec(
        name="matcher",
        instructions="Match the job to the profile.",
        input_schema={"type": "object", "required": []},
        output_schema={"type": "object", "required": ["score", "recommendation"]},
        tools=["get_candidate_profile"],
    )

    result = await harness.run(spec, {})
    assert result.success is True
    executed_names = [r.tool_name for r in result.tool_results]
    assert executed_names == ["get_candidate_profile"]


@pytest.mark.asyncio
async def test_normal_response_without_tools_unchanged() -> None:
    """Backward compatibility: a response with no tool calls is treated as final."""
    registry = InMemoryToolRegistry()
    harness = AgentHarness(tool_registry=registry, model_adapter=MockModelAdapter())

    final = ModelResponse(
        content=json.dumps({"score": 85, "recommendation": "strong_match"}),
        model="mock",
        finish_reason="stop",
    )
    harness.model_adapter.set_response("score", final)

    spec = AgentSpec(
        name="matcher",
        instructions="Match the job to the profile.",
        input_schema={"type": "object", "required": []},
        output_schema={"type": "object", "required": ["score", "recommendation"]},
    )

    result = await harness.run(spec, {})
    assert result.success is True
    assert result.output["score"] == 85
    assert len(result.tool_calls) == 0
    assert len(result.tool_results) == 0


@pytest.mark.asyncio
async def test_tool_execution_exception_is_recorded() -> None:
    """Tools that raise during execution return a failed result."""
    registry = InMemoryToolRegistry()

    async def failing_tool(**kwargs):
        raise ValueError("boom")

    registry.register(ToolDefinition(
        name="crash_me",
        description="A tool that crashes",
        parameters={"type": "object", "properties": {}, "required": []},
        fn=failing_tool,
    ))
    registry.set_allowlist("matcher", ["crash_me"])
    harness = AgentHarness(tool_registry=registry, model_adapter=MockModelAdapter())

    prof_call = ModelResponse(
        content="",
        model="mock",
        tool_calls=[make_tool_call("crash_me")],
    )
    final = ModelResponse(
        content=json.dumps({"score": 85, "recommendation": "strong_match"}),
        model="mock",
    )

    harness.model_adapter.set_response("crash_me", prof_call)
    harness.model_adapter.set_response(final.content, final)

    spec = AgentSpec(
        name="matcher",
        instructions="Match the job to the profile.",
        input_schema={"type": "object", "required": []},
        output_schema={"type": "object", "required": ["score", "recommendation"]},
        tools=["crash_me"],
    )

    result = await harness.run(spec, {})
    assert result.success is True
    assert result.tool_results[0].success is False
    assert "boom" in result.tool_results[0].error


# --------------------------------------------------------------------------- #
# Failure semantics
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_all_calls_denied_raises() -> None:
    """When every tool call in a batch is denied, the harness stops."""
    registry = InMemoryToolRegistry()
    registry.set_allowlist("matcher", ["get_candidate_profile"])
    harness = AgentHarness(tool_registry=registry, model_adapter=MockModelAdapter())

    call = ModelResponse(
        content="",
        model="mock",
        tool_calls=[make_tool_call("get_job_posting", {"job_id": "job-1"})],
    )
    harness.model_adapter.set_response("get_job_posting", call)

    spec = AgentSpec(
        name="matcher",
        instructions="Match the job to the profile.",
        input_schema={"type": "object", "required": []},
        output_schema={"type": "object", "required": ["score", "recommendation"]},
        tools=["get_candidate_profile", "get_job_posting"],
    )

    result = await harness.run(spec, {})
    assert result.success is False
    assert result.error.error_type == "tool_denied"


@pytest.mark.asyncio
async def test_iteration_limit_raises() -> None:
    """Exhausting the tool-calling loop without a final answer raises."""
    registry = InMemoryToolRegistry()
    registry.set_allowlist("matcher", ["get_candidate_profile"])
    harness = AgentHarness(tool_registry=registry, model_adapter=MockModelAdapter())

    call = ModelResponse(
        content="",
        model="mock",
        tool_calls=[make_tool_call("get_candidate_profile", {"profile_id": "prof-1"})],
    )
    harness.model_adapter.set_response("get_candidate_profile", call)

    spec = AgentSpec(
        name="matcher",
        instructions="Match the job to the profile.",
        input_schema={"type": "object", "required": []},
        output_schema={"type": "object", "required": ["score", "recommendation"]},
        tools=["get_candidate_profile"],
        policy={"max_tool_iterations": 2},
    )

    result = await harness.run(spec, {})
    assert result.success is False
    assert result.error.error_type == "retry_exhausted"
    assert result.error.details.get("max_iterations") == 2

    # The model was called once per iteration (3 total calls), no final answer.
    steps = result.trace["steps"]
    model_calls = [s for s in steps if s.get("step", "").startswith("model_call")]
    assert len(model_calls) == 3


@pytest.mark.asyncio
async def test_missing_call_id_is_logged_as_malformed() -> None:
    """A tool call missing id/name is not executed and is logged."""
    registry = InMemoryToolRegistry()
    registry.set_allowlist("matcher", ["get_candidate_profile"])
    harness = AgentHarness(tool_registry=registry, model_adapter=MockModelAdapter())

    bad_call = ModelResponse(
        content="",
        model="mock",
        tool_calls=[{"name": "get_candidate_profile", "arguments": {"profile_id": "prof-1"}}],
    )
    final = ModelResponse(
        content=json.dumps({"score": 85, "recommendation": "strong_match"}),
        model="mock",
    )

    harness.model_adapter.set_response("get_candidate_profile", bad_call)
    harness.model_adapter.set_response(final.content, final)

    spec = AgentSpec(
        name="matcher",
        instructions="Match the job to the profile.",
        input_schema={"type": "object", "required": []},
        output_schema={"type": "object", "required": ["score", "recommendation"]},
        tools=["get_candidate_profile"],
    )

    result = await harness.run(spec, {})
    assert result.success is True
    assert len(result.tool_calls) == 0
    assert len(result.tool_results) == 0

    steps = result.trace["steps"]
    assert any("malformed_tool_call" in str(s) for s in steps)


@pytest.mark.asyncio
async def test_max_tool_iterations_respected_from_policy() -> None:
    """Custom max_tool_iterations policy is respected."""
    registry = InMemoryToolRegistry()
    registry.set_allowlist("matcher", ["get_candidate_profile"])
    harness = AgentHarness(tool_registry=registry, model_adapter=MockModelAdapter())

    call = ModelResponse(
        content="",
        model="mock",
        tool_calls=[make_tool_call("get_candidate_profile", {"profile_id": "prof-1"})],
    )
    harness.model_adapter.set_response("get_candidate_profile", call)

    spec = AgentSpec(
        name="matcher",
        instructions="Match the job to the profile.",
        input_schema={"type": "object", "required": []},
        output_schema={"type": "object", "required": ["score", "recommendation"]},
        tools=["get_candidate_profile"],
        policy={"max_tool_iterations": 1},
    )

    result = await harness.run(spec, {})
    assert result.success is False
    steps = result.trace["steps"]
    model_calls = [s for s in steps if s.get("step", "").startswith("model_call")]
    # 1 iteration + 1 retry = 2 attempts
    assert len(model_calls) == 2

    # Default is used when policy is absent.
    registry2 = InMemoryToolRegistry()
    harness2 = AgentHarness(tool_registry=registry2, model_adapter=MockModelAdapter())
    harness2.model_adapter.set_response("get_candidate_profile", call)
    spec2 = AgentSpec(
        name="matcher",
        instructions="Match",
        input_schema={"type": "object", "required": []},
        output_schema={"type": "object", "required": ["score"]},
        tools=["get_candidate_profile"],
    )
    result2 = await harness2.run(spec2, {})
    steps2 = result2.trace["steps"]
    model_calls2 = [s for s in steps2 if s.get("step", "").startswith("model_call")]
    assert len(model_calls2) == DEFAULT_MAX_TOOL_ITERATIONS + 1
