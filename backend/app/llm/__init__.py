"""LLM provider abstraction.

A single configured LLM provider behind a model adapter. The adapter exposes
a uniform interface so the harness can swap providers without touching agent
code. A ``MockModelAdapter`` is provided for deterministic tests.
"""

from __future__ import annotations

from app.llm.model_adapter import (
    ModelAdapter,
    ModelResponse,
    MockModelAdapter,
    OpenAIModelAdapter,
)

__all__ = ["ModelAdapter", "ModelResponse", "MockModelAdapter", "OpenAIModelAdapter"]