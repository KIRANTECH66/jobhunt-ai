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
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        self.content = content
        self.model = model
        self.usage = usage or {}
        self.finish_reason = finish_reason
        self.raw = raw or {}
        # tool_calls: list of {"id": str, "name": str, "arguments": dict}
        self.tool_calls = tool_calls or []

    # Compatibility: some tests construct MockResponse-like objects without
    # going through ModelResponse. Provide a property getter that returns
    # empty list when the attribute is missing.
    @property
    def tool_calls(self) -> list[dict[str, Any]]:
        return getattr(self, "_tool_calls", [])

    @tool_calls.setter
    def tool_calls(self, value: list[dict[str, Any]] | None) -> None:
        self._tool_calls = value or []


class ModelAdapter:
    """Abstract interface for an LLM model adapter."""

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate text from the model.

        Parameters
        ----------
        prompt: str
            The user prompt.
        system: str | None
            Optional system prompt.
        messages: list[dict[str, Any]] | None
            Optional prior conversation messages. When provided, takes
            precedence over ``prompt``/``system`` for multi-turn loops.
        tools: list[dict[str, Any]] | None
            Optional tool definitions (JSON Schema fragments) the model may
            invoke. Provider-specific formatting is handled inside the
            concrete adapter.
        **kwargs: Any
            Provider-specific options (temperature, max_tokens, etc.).

        Returns
        -------
        ModelResponse
            The model's output. ``tool_calls`` is a list of
            ``{"id": str, "name": str, "arguments": dict}`` dicts, or an
            empty list when the model did not request any tools.
        """
        raise NotImplementedError


class MockModelAdapter(ModelAdapter):
    """Deterministic mock adapter for tests and offline development.

    Returns canned responses based on simple pattern matching. Never calls
    an external API. All responses are reproducible and reproducible.

    The mock supports the full tool-calling contract: it accepts a
    ``messages`` conversation and optional ``tools`` list, and may return
    ``tool_calls`` in the normalized ``{"id", "name", "arguments"}`` shape.
    Tests can script multi-turn cycles via :meth:`set_response` or
    :meth:`set_sequence`.
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
        # Per-instance scripted responses for tool-calling cycles. Keys are
        # matched against any message content in the conversation.
        self._scripted: dict[str, ModelResponse] = {}
        # Optional scripted sequence: responses are consumed in order.
        self._sequence: list[ModelResponse] = []
        self._sequence_index = 0

    def set_response(self, key: str, response: ModelResponse) -> None:
        """Script a canned response keyed by substring match in any message content."""
        self._scripted[key] = response

    def set_sequence(self, responses: list[ModelResponse]) -> None:
        """Script a sequence of responses consumed in order.

        Each call to :meth:`generate` returns the next response in the
        sequence. This is the primary mechanism for multi-turn tool-calling
        tests where the model must return a tool call, then a final answer.
        """
        self._sequence = list(responses)
        self._sequence_index = 0

    def clear_scripted(self) -> None:
        """Clear all scripted responses and sequences."""
        self._scripted.clear()
        self._sequence = []
        self._sequence_index = 0

    @staticmethod
    def _message_contains_key(messages: list[dict[str, Any]] | None, key: str) -> bool:
        """Return True if ``key`` appears as a substring in any message content."""
        if not messages:
            return False
        for message in messages:
            content = message.get("content")
            if isinstance(content, str) and key in content:
                return True
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        if key in part.get("text", ""):
                            return True
        return False

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        # 1. Scripted sequence takes precedence.
        if self._sequence:
            response = self._sequence[self._sequence_index]
            self._sequence_index += 1
            if self._sequence_index >= len(self._sequence):
                self._sequence = []
                self._sequence_index = 0
            return response

        # 2. When the conversation already contains a tool-result message,
        #    look for a scripted response keyed by the *last* tool result's
        #    content. This lets tests script the final answer after a tool
        #    call by passing a key that appears in the tool result (e.g. a
        #    JSON fragment or a unique ID).
        if messages:
            last_tool_content: str | None = None
            for message in reversed(messages):
                if message.get("role") == "tool":
                    content = message.get("content")
                    if isinstance(content, str):
                        last_tool_content = content
                    elif content is not None:
                        last_tool_content = str(content)
                    break

            if last_tool_content is not None:
                for scripted_key, scripted_response in self._scripted.items():
                    if scripted_key in last_tool_content:
                        return scripted_response
                # No match in tool result — fall through to generic fallback
                # (do NOT match against system prompt to avoid re-triggering
                # the same tool call).
            else:
                # No tool result yet: first call or a plain response.
                # Match against any message content (e.g. tool name in system prompt).
                for scripted_key, scripted_response in self._scripted.items():
                    if self._message_contains_key(messages, scripted_key):
                        return scripted_response
        else:
            # No messages provided: fall back to checking the prompt for
            # backward compatibility with existing tests.
            lowered_prompt = prompt.lower()
            for scripted_key, scripted_response in self._scripted.items():
                if scripted_key.lower() in lowered_prompt:
                    return scripted_response

        # 3. Check the built-in canned responses (backward compatibility).
        if not messages:
            lowered = prompt.lower()
            if "match_score" in lowered:
                return self._responses["match_score"]
            elif "no match" in lowered or "unqualified" in lowered:
                return self._responses["no_match"]

        # 4. Generic fallback.
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

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Invoke the OpenAI-compatible chat completions endpoint.

        ``messages`` (a prior conversation) takes precedence over the
        ``prompt``/``system`` pair. ``tools`` are passed through as OpenAI
        tool definitions; the response's ``tool_calls`` are normalized into
        ``{"id", "name", "arguments"}`` dicts.
        """
        if messages is not None:
            request_messages = list(messages)
        else:
            request_messages = []
            if system:
                request_messages.append({"role": "system", "content": system})
            request_messages.append({"role": "user", "content": prompt})

        request_kwargs: dict[str, Any] = {
            "messages": request_messages,
            "model": settings.model_name or "gpt-4o",
        }
        if tools:
            # Accept either {"type":"function","function":{...}} shapes or
            # bare JSON Schema fragments; normalize to the OpenAI shape.
            normalized: list[dict[str, Any]] = []
            for tool in tools:
                if isinstance(tool, dict) and tool.get("type") == "function":
                    normalized.append(tool)
                else:
                    normalized.append({
                        "type": "function",
                        "function": {
                            "name": tool.get("name", "tool"),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("parameters", tool.get("parameters_schema", {"type": "object"})),
                        },
                    })
            request_kwargs["tools"] = normalized

        request_kwargs.update(kwargs)

        try:
            response = await self.client.chat.completions.create(**request_kwargs)
            choice = response.choices[0]
            message = choice.message
            content = message.content or ""
            tool_calls = self._normalize_tool_calls(getattr(message, "tool_calls", None))
            usage = dict(response.usage) if response.usage else {}
            return ModelResponse(
                content=content,
                model=settings.model_name or "gpt-4o",
                usage=usage,
                finish_reason=choice.finish_reason,
                raw=response.model_dump(),
                tool_calls=tool_calls,
            )
        except APIError as e:
            # Re-raise as a RuntimeError with context
            raise RuntimeError(f"OpenAI API error: {e}") from e

    @staticmethod
    def _normalize_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
        """Normalize provider tool calls into ``{"id","name","arguments"}``.

        OpenAI returns ``tool_calls`` as objects with ``id``, ``function.name``,
        and ``function.arguments`` (a JSON string). Arguments are parsed into a
        dict; malformed JSON is preserved as a raw string so the harness can
        report the failure rather than silently dropping the call.
        """
        if not tool_calls:
            return []
        normalized: list[dict[str, Any]] = []
        for call in tool_calls:
            call_id = getattr(call, "id", None)
            function = getattr(call, "function", None)
            name = getattr(function, "name", None) if function is not None else None
            raw_args = getattr(function, "arguments", None) if function is not None else None
            if name is None and isinstance(call, dict):
                function = call.get("function", {})
                name = function.get("name")
                raw_args = function.get("arguments")
                call_id = call.get("id", call_id)
            if not call_id or not name:
                # Skip calls missing an id or name — the harness records them
                # as malformed rather than executing them.
                continue
            arguments: Any
            if isinstance(raw_args, dict):
                arguments = raw_args
            elif isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args) if raw_args else {}
                except json.JSONDecodeError:
                    arguments = raw_args
            else:
                arguments = {}
            normalized.append({"id": call_id, "name": name, "arguments": arguments})
        return normalized