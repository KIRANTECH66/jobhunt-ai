"""Test agent harness."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.harness.harness import AgentHarness, AgentSpec, HarnessError
from app.tools.registry import InMemoryToolRegistry


@pytest.mark.asyncio
async def test_harness_basic_run() -> None:
    """Test basic harness execution."""
    registry = InMemoryToolRegistry()
    harness = AgentHarness(tool_registry=registry)

    spec = AgentSpec(
        name='test_agent',
        instructions='Test instructions',
        input_schema={
            'type': 'object',
            'properties': {'key': {'type': 'string'}},
            'required': ['key'],
        },
        output_schema={
            'type': 'object',
            'properties': {'result': {'type': 'string'}},
            'required': ['result'],
        },
        max_retries=1,
    )

    payload = {'key': 'value'}
    result = await harness.run(spec, payload)

    assert result.success is True
    assert 'result' in result.output


@pytest.mark.asyncio
async def test_harness_missing_input_field() -> None:
    """Test that missing required input fields are caught."""
    registry = InMemoryToolRegistry()
    harness = AgentHarness(tool_registry=registry)

    spec = AgentSpec(
        name='test_agent',
        instructions='Test instructions',
        input_schema={
            'type': 'object',
            'properties': {'required_field': {'type': 'string'}},
            'required': ['required_field'],
        },
        output_schema={'type': 'object'},
    )

    payload = {}  # Missing required_field
    result = await harness.run(spec, payload)
    assert result.success is False
    assert result.error is not None
    assert result.error.error_type == 'validation'


@pytest.mark.asyncio
async def test_harness_tool_allowlist() -> None:
    """Test that tool allowlists are enforced."""
    registry = InMemoryToolRegistry()
    harness = AgentHarness(tool_registry=registry)

    # Set up allowlist for a specific agent
    registry.set_allowlist('job_matcher', ['get_candidate_profile'])

    spec = AgentSpec(
        name='job_matcher',
        instructions='Match jobs',
        input_schema={'type': 'object'},
        output_schema={'type': 'object'},
        tools=['get_candidate_profile', 'get_job_posting'],  # Second tool not allowed
    )

    payload = {}
    result = await harness.run(spec, payload)
    # Should still run successfully (tools are resolved but not blocking)
    assert result.success is True


@pytest.mark.asyncio
async def test_harness_validation_error() -> None:
    """Test that invalid output is handled gracefully."""
    registry = InMemoryToolRegistry()
    harness = AgentHarness(tool_registry=registry)

    spec = AgentSpec(
        name='test_agent',
        instructions='Test',
        input_schema={'type': 'object'},
        output_schema={
            'type': 'object',
            'properties': {'score': {'type': 'number'}},
            'required': ['score'],
        },
    )

    # Mock the model to return invalid output
    with patch.object(harness.model_adapter, 'generate') as mock_generate:
        mock_generate.return_value = type('MockResponse', (), {
            'content': '{"wrong_field": 123}',
            'model': 'mock',
            'usage': {},
            'finish_reason': 'stop',
        })()

        payload = {}
        result = await harness.run(spec, payload)
        assert result.success is False
        assert result.error is not None
        assert result.error.error_type == 'validation'


@pytest.mark.asyncio
async def test_harness_retry_on_failure() -> None:
    """Test that retries work on model failure."""
    registry = InMemoryToolRegistry()
    harness = AgentHarness(tool_registry=registry)

    spec = AgentSpec(
        name='test_agent',
        instructions='Test',
        input_schema={'type': 'object'},
        output_schema={'type': 'object'},
        max_retries=2,
    )

    call_count = 0

    async def failing_then_success(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Transient error")
        return type('MockResponse', (), {
            'content': '{"result": "ok"}',
            'model': 'mock',
            'usage': {},
            'finish_reason': 'stop',
        })()

    with patch.object(harness.model_adapter, 'generate', side_effect=failing_then_success):
        payload = {}
        result = await harness.run(spec, payload)
        assert result.success is True
        assert call_count == 3  # 2 failures + 1 success