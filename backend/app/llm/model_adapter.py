"""Model adapter abstraction.

Provides a uniform interface for the harness to invoke the LLM, with a
deterministic mock adapter for tests and an OpenAI-compatible real adapter.

The adapter is intentionally simple — it sends a structured request and
returns a structured response. It does not handle tool execution, state, or
orchestration; those are the harness's responsibility.
"""

from __future__ import annotations

import json
import time
from typing import Any

from openai import APIError, AsyncOpenAI

from app.config import settings


class ModelResponse:
    """Returned by the model adapter."""

    def __init__(
        self,
        content: str,
        model: str,
        usage: dict[str, int] | None = None,
        finish_reason: str | None = None,
        raw: dict | None = None,
    ) -> None:
        self.content = content
        self.model = model
        self.usage = usage or {}
        self.finish_reason = finish_reason
        self.raw = raw or {}


class ModelAdapter:
    """Abstract interface for an LLM model adapter."""

    async def generate(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> ModelResponse:
        """Generate text from the model.

        Parameters
        ----------
        prompt: str
            The user prompt.
        system: str | None
            Optional system prompt.
        **kwargs: Any
            Provider-specific options (temperature, max_tokens, etc.).

        Returns
        -------
        ModelResponse
            The model's output.
        """
        raise NotImplementedError


class MockModelAdapter(ModelAdapter):
    """Deterministic mock adapter for tests and offline development.

    Returns canned responses based on simple pattern matching. Never calls
    an external API. All responses are reproducible and reproducible.
    """

    # Canned responses keyed by prompt pattern
    _responses: dict[str, ModelResponse] = {}

    def __init__(self) -> None:
        super().__init__()
        # Default responses for common matcher prompts
        if not self._responses:
            self._responses = {
                "match_score": ModelResponse(
                    content='{"score": 85, "strengths": ["Python experience"], "gaps": ["No PostgreSQL"], "unknowns": ["Compensation"]}',
                    model="mock",
                    usage={"prompt_tokens": 12, "completion_tokens": 45, "total_tokens": 57},
                    finish_reason="stop",
                ),
                "no_match": ModelResponse(
                    content='{"score": 10, "strengths": [], "gaps": ["No relevant qualifications"], "unknowns": ["All fields"]}',
                    model="mock",
                    usage={"prompt_tokens": 12, "completion_tokens": 30, "total_tokens": 42},
                    finish_reason="stop",
                ),
            }

    async def generate(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> ModelResponse:
        # Simple pattern matching for testability
        if "match_score" in prompt.lower():
            return self._responses["match_score"]
        elif "no match" in prompt.lower() or "unqualified" in prompt.lower():
            return self._responses["no_match"]
        else:
            # Return a generic response that includes common fields
            return ModelResponse(
                content='{"result": "ok"}',
                model="mock",
                usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                finish_reason="stop",
            )


class OpenAIModelAdapter(ModelAdapter):
    """OpenAI-compatible model adapter.

    Wraps the OpenAI Python SDK to provide a uniform ``ModelAdapter`` interface.
    The adapter reads its configuration from ``app.config.settings``.

    If ``model_api_key`` is not set, the adapter is created with an empty key
    (tests can mock the client). Pass ``api_key`` to override.

    Example::

        adapter = OpenAIModelAdapter()
        response = await adapter.generate(
            "Does this candidate match this job?",
            system="You are a job matcher.",
        )
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        super().__init__()
        # Use provided key or fall back to settings; empty key for testing
        key = api_key or settings.model_api_key or "no-key-needed-for-mocks"
        url = base_url or settings.model_base_url or None
        self.client = AsyncOpenAI(api_key=key, base_url=url)

    async def generate(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> ModelResponse:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                messages=messages,
                model=settings.model_name or "gpt-4o",
                **kwargs,
            )
            content = response.choices[0].message.content or ""
            usage = dict(response.usage) if response.usage else {}
            return ModelResponse(
                content=content,
                model=settings.model_name or "gpt-4o",
                usage=usage,
                finish_reason=response.choices[0].finish_reason,
                raw=response.model_dump(),
            )
        except APIError as e:
            # Re-raise as a RuntimeError with context
            raise RuntimeError(f"OpenAI API error: {e}") from e