"""Test ModelAdapter contract.

All tests use MockModelAdapter — no real LLM provider is called.
"""

from __future__ import annotations

import asyncio
import json
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.llm.model_adapter import ModelAdapter, ModelResponse, MockModelAdapter, OpenAIModelAdapter


class TestMockModelAdapter:
    """Tests for MockModelAdapter."""

    def test_generates_match_score_response(self) -> None:
        """Test that match_score pattern returns the canned response."""
        adapter = MockModelAdapter()
        response = asyncio.run(adapter.generate("match_score for this candidate"))
        assert response.model == "mock"
        data = json.loads(response.content)
        assert data["score"] == 85
        assert "Python experience" in data["strengths"]

    def test_generates_no_match_response(self) -> None:
        """Test that no_match/unqualified patterns return the canned response."""
        adapter = MockModelAdapter()
        response = asyncio.run(adapter.generate("no match - candidate is unqualified"))
        assert response.model == "mock"
        data = json.loads(response.content)
        assert data["score"] == 10
        assert data["strengths"] == []

    def test_generates_generic_response(self) -> None:
        """Test that unknown patterns return a generic response."""
        adapter = MockModelAdapter()
        response = asyncio.run(adapter.generate("some random prompt"))
        assert response.model == "mock"
        data = json.loads(response.content)
        assert data["result"] == "ok"

    def test_returns_model_response_with_usage(self) -> None:
        """Test that ModelResponse carries usage metadata."""
        adapter = MockModelAdapter()
        response = asyncio.run(adapter.generate("match_score"))
        assert response.usage == {"prompt_tokens": 12, "completion_tokens": 45, "total_tokens": 57}
        assert response.finish_reason == "stop"


class TestOpenAIModelAdapterContract:
    """Tests for OpenAIModelAdapter contract (using mocked SDK)."""

    @pytest.fixture
    def adapter(self) -> OpenAIModelAdapter:
        """Create an OpenAIModelAdapter with a mocked client."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            adapter = OpenAIModelAdapter()
            adapter.client = MagicMock()
            return adapter

    @pytest.mark.asyncio
    async def test_generate_calls_model_api(self, adapter) -> None:
        """Test that OpenAIModelAdapter calls the model API."""
        # The model adapter calls dict(response.usage), so we need a mock that works with dict()
        usage_mock = MagicMock()
        usage_mock.__iter__ = MagicMock(return_value=iter([("prompt_tokens", 10), ("completion_tokens", 20)]))
        usage_mock.__getitem__ = MagicMock(side_effect=lambda k: {"prompt_tokens": 10, "completion_tokens": 20}[k])
        usage_mock.keys = MagicMock(return_value=["prompt_tokens", "completion_tokens"])
        adapter.client.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"score": 50}'))],
            usage=usage_mock,
        ))

        response = await adapter.generate("test prompt", system="system prompt")
        assert response.model == "gpt-4o"
        assert response.content == '{"score": 50}'
        assert response.usage == {"prompt_tokens": 10, "completion_tokens": 20}

    @pytest.mark.asyncio
    async def test_generate_handles_api_error(self, adapter) -> None:
        """Test that OpenAIModelAdapter handles API errors."""
        from openai import APIError
        import httpx
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        adapter.client.chat.completions.create = AsyncMock(
            side_effect=APIError("test message", request=request, body={"message": "error"})
        )

        with pytest.raises(RuntimeError, match="OpenAI API error"):
            await adapter.generate("test prompt")

    @pytest.mark.asyncio
    async def test_generate_with_none_content(self, adapter) -> None:
        """Test that OpenAIModelAdapter handles None content."""
        adapter.client.chat.completions.create = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content=None))],
            usage=None,
        ))

        response = await adapter.generate("test prompt")
        assert response.content == ""

    @pytest.mark.asyncio
    async def test_never_calls_real_api_in_tests(self, adapter) -> None:
        """Verify that OpenAIModelAdapter can be fully mocked."""
        # The client is already mocked by the fixture
        assert adapter.client is not None

        # Patch the client to prevent any real calls
        with patch.object(adapter, 'client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Should not call real API"))
            # This should fail because we patched it
            with pytest.raises(Exception, match="Should not call real API"):
                await adapter.generate("test")
