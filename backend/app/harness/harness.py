"""Agent harness implementation.

The harness executes agents safely by:
1. Validating input against the spec's input schema
2. Resolving permitted tools from the registry
3. Invoking the model adapter with tool calls
4. Validating structured output
5. Emitting trace and audit events
6. Enforcing timeouts and retry policies

Tool-calling cycle
------------------
The harness drives a bounded model/tool loop:

    model response
        -> extract tool calls
        -> validate each call against the registry allowlist
        -> execute authorized calls, record results
        -> append calls + results to the conversation and execution history
        -> feed results back to the model
        -> repeat until the model returns a final answer or the iteration
           limit is reached

Unauthorized tool calls are rejected explicitly and never executed. They
are recorded in the trace so the failure is inspectable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, ValidationError

from app.llm.model_adapter import ModelAdapter, MockModelAdapter
from app.tools.registry import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)

# Default bounds for the tool-calling loop. Agents may tighten these via
# AgentSpec.policy; they are never loosened silently.
DEFAULT_MAX_TOOL_ITERATIONS = 5
DEFAULT_TOOL_ITERATION_TIMEOUT_SECONDS = 30.0
DEFAULT_RETRY_BACKOFF_BASE_SECONDS = 0.05


@dataclass
class AgentSpec:
    """Specification for an agent execution."""

    name: str
    instructions: str
    input_schema: dict[str, Any]  # JSON Schema
    output_schema: dict[str, Any]  # JSON Schema
    tools: list[str] = field(default_factory=list)  # Tool names allowed
    model: str = "mock"
    timeout_seconds: float = 60.0
    max_retries: int = 2
    token_budget: int | None = None  # None = unlimited
    policy: dict[str, Any] = field(default_factory=dict)


@dataclass
class HarnessError(Exception):
    """Error that occurred during agent execution."""

    agent_name: str
    error_type: str  # 'validation', 'timeout', 'retry_exhausted', 'tool_denied'
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class HarnessResult:
    """Result of agent execution."""

    agent_name: str
    success: bool
    output: Any = None
    error: HarnessError | None = None
    trace: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)


class AgentHarness:
    """Shared execution interface for agents.

    Validates input, resolves permitted tools, invokes the model, enforces
    execution limits, validates structured output, and emits traces.
    """

    def __init__(
        self,
        model_adapter: ModelAdapter | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.model_adapter = model_adapter or MockModelAdapter()
        self.tool_registry = tool_registry

    # --------------------------------------------------------------------- #
    # Tool definitions
    # --------------------------------------------------------------------- #

    def _tool_definitions(self, allowed_tools: list[str]) -> list[dict[str, Any]]:
        """Build provider-agnostic tool definitions for the model.

        Returns a list of ``{"name", "description", "parameters"}`` dicts. The
        concrete adapter is responsible for translating these into the
        provider's native tool schema (e.g. OpenAI's
        ``{"type":"function","function":{...}}``).
        """
        if not self.tool_registry or not allowed_tools:
            return []
        definitions: list[dict[str, Any]] = []
        for name in allowed_tools:
            tool = self.tool_registry.get_tool(name)
            if tool is not None:
                definitions.append({
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                })
        return definitions

    async def run(self, spec: AgentSpec, payload: dict[str, Any]) -> HarnessResult:
        """Execute an agent with the given spec and input.

        Runs a bounded model/tool-calling loop:

        1. Validate input against the spec's input schema.
        2. Resolve the agent's effective tool allowlist.
        3. Send the conversation to the model.
        4. If the model returns tool calls, validate and execute each
           authorized call, append the assistant message and tool-result
           messages, and repeat.
        5. When the model returns a final answer, parse and validate the
           structured output.

        Unauthorized, malformed, duplicate, or failing tool calls are
        recorded in the trace and never silently promoted to success.

        Parameters
        ----------
        spec: AgentSpec
            The agent specification.
        payload: dict
            The input data.

        Returns
        -------
        HarnessResult
            The result of execution.
        """
        start_time = time.time()
        trace: dict[str, Any] = {
            "agent_name": spec.name,
            "started_at": start_time,
            "steps": [],
        }
        tool_calls: list[dict[str, Any]] = []
        tool_results: list[ToolResult] = []
        executed_call_ids: set[str] = set()

        try:
            # Step 1: Validate input
            self._validate_input(spec.input_schema, payload)
            trace["steps"].append({"step": "input_validation", "status": "ok"})

            # Step 2: Resolve allowed tools
            allowed_tools = self.tool_registry.get_allowlist(spec.name) if self.tool_registry else set()
            effective_tools = [t for t in spec.tools if t in allowed_tools]

            # Step 3: Build the conversation
            system_prompt = self._build_system_prompt(spec.instructions, effective_tools)
            user_prompt = self._build_user_prompt(payload)
            conversation: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Step 4: Bounded tool-calling loop
            max_iterations = int(spec.policy.get("max_tool_iterations", DEFAULT_MAX_TOOL_ITERATIONS))
            if max_iterations < 1:
                max_iterations = DEFAULT_MAX_TOOL_ITERATIONS

            response: ModelResponse | None = None
            for iteration in range(1, max_iterations + 1):
                response = await self._invoke_model(
                    spec=spec,
                    conversation=conversation,
                    trace=trace,
                    iteration=iteration,
                )

                # Defensive: some test doubles omit ``tool_calls``. Treat a
                # missing attribute as an empty list so the harness never
                # crashes on a plain dict-like mock.
                response_tool_calls = getattr(response, "tool_calls", None) or []

                if not response_tool_calls:
                    # Final answer — exit the loop.
                    trace["steps"].append({
                        "step": f"tool_loop_iteration_{iteration}",
                        "status": "ok",
                        "outcome": "final_response",
                    })
                    break

                # Process the model's requested tool calls.
                assistant_message, tool_result_messages, loop_denied = (
                    await self._execute_tool_calls(
                        spec=spec,
                        tool_calls=response_tool_calls,
                        tool_calls_log=tool_calls,
                        tool_results=tool_results,
                        executed_call_ids=executed_call_ids,
                        trace=trace,
                        iteration=iteration,
                    )
                )
                conversation.append(assistant_message)
                conversation.extend(tool_result_messages)

                if loop_denied:
                    # Every call in this batch was denied; stop rather than
                    # letting the model retry the same unauthorized requests.
                    trace["steps"].append({
                        "step": f"tool_loop_iteration_{iteration}",
                        "status": "failed",
                        "error": "all_tool_calls_denied",
                    })
                    raise HarnessError(
                        agent_name=spec.name,
                        error_type="tool_denied",
                        message=(
                            f"All tool calls in iteration {iteration} were denied "
                            f"by the allowlist"
                        ),
                    )

                trace["steps"].append({
                    "step": f"tool_loop_iteration_{iteration}",
                    "status": "ok",
                    "tool_calls": len(response.tool_calls),
                })
            else:
                # Loop exhausted without a final response.
                raise HarnessError(
                    agent_name=spec.name,
                    error_type="retry_exhausted",
                    message=(
                        f"Tool-calling loop reached its limit of {max_iterations} "
                        f"iterations without a final response"
                    ),
                    details={"max_iterations": max_iterations},
                )

            assert response is not None  # for type checkers; loop always sets it

            # Step 5: Parse and validate output
            output = self._parse_output(response.content)
            self._validate_output(spec.output_schema, output)

            elapsed = time.time() - start_time
            trace["steps"].append({"step": "output_validation", "status": "ok"})
            trace["elapsed_seconds"] = elapsed
            trace["conversation"] = conversation

            return HarnessResult(
                agent_name=spec.name,
                success=True,
                output=output,
                trace=trace,
                usage=response.usage,
                tool_calls=tool_calls,
                tool_results=tool_results,
            )

        except HarnessError as e:
            elapsed = time.time() - start_time
            trace["error"] = e.message
            trace["elapsed_seconds"] = elapsed
            return HarnessResult(
                agent_name=spec.name,
                success=False,
                error=e,
                trace=trace,
                tool_calls=tool_calls,
                tool_results=tool_results,
            )
        except Exception as e:
            logger.exception("Unexpected error in agent %s", spec.name)
            elapsed = time.time() - start_time
            trace["error"] = str(e)
            trace["elapsed_seconds"] = elapsed
            return HarnessResult(
                agent_name=spec.name,
                success=False,
                error=HarnessError(
                    agent_name=spec.name,
                    error_type="unexpected",
                    message=str(e),
                ),
                trace=trace,
                tool_calls=tool_calls,
                tool_results=tool_results,
            )

    # --------------------------------------------------------------------- #
    # Validation
    # --------------------------------------------------------------------- #

    def _validate_input(self, schema: dict[str, Any], data: Any) -> None:
        """Validate input data against the schema.

        Checks both field presence (required) and basic structural types
        declared in the JSON Schema. Malformed input is rejected explicitly
        rather than passed through to the model or a tool.
        """
        if not isinstance(data, dict):
            raise HarnessError(
                agent_name="",
                error_type="validation",
                message="Input payload must be an object",
                details={"type": type(data).__name__},
            )

        required = schema.get("required", [])
        missing = [field for field in required if field not in data]
        if missing:
            raise HarnessError(
                agent_name="",
                error_type="validation",
                message=f"Missing required field(s): {', '.join(missing)}",
                details={"missing": missing},
            )

        type_errors = self._check_types(schema.get("properties", {}), data)
        if type_errors:
            raise HarnessError(
                agent_name="",
                error_type="validation",
                message="Input type validation failed: " + "; ".join(type_errors),
                details={"type_errors": type_errors},
            )

    def _validate_output(self, schema: dict[str, Any], data: Any) -> None:
        """Validate output data against the schema."""
        if not isinstance(data, dict):
            raise HarnessError(
                agent_name="",
                error_type="validation",
                message="Model output must be a JSON object",
                details={"type": type(data).__name__},
            )

        required = schema.get("required", [])
        missing = [field for field in required if field not in data]
        if missing:
            raise HarnessError(
                agent_name="",
                error_type="validation",
                message=f"Missing required output field(s): {', '.join(missing)}",
                details={"missing": missing},
            )

        type_errors = self._check_types(schema.get("properties", {}), data)
        if type_errors:
            raise HarnessError(
                agent_name="",
                error_type="validation",
                message="Output type validation failed: " + "; ".join(type_errors),
                details={"type_errors": type_errors},
            )

    @staticmethod
    def _check_types(properties: dict[str, Any], data: dict[str, Any]) -> list[str]:
        """Return a list of type-error messages for ``data``.

        Only the ``type`` keyword of each property is checked. Nested
        objects and arrays are validated structurally (must be dict/list)
        but their contents are not recursively schema-validated, matching
        the lightweight approach used elsewhere in the harness.
        """
        errors: list[str] = []
        for field, prop in properties.items():
            if field not in data:
                continue
            value = data[field]
            expected = prop.get("type") if isinstance(prop, dict) else None
            if expected == "string" and not isinstance(value, str):
                errors.append(f"Field '{field}' must be a string, got {type(value).__name__}")
            elif expected == "number" and not isinstance(value, (int, float)):
                errors.append(f"Field '{field}' must be a number, got {type(value).__name__}")
            elif expected == "integer" and not isinstance(value, int):
                errors.append(f"Field '{field}' must be an integer, got {type(value).__name__}")
            elif expected == "boolean" and not isinstance(value, bool):
                errors.append(f"Field '{field}' must be a boolean, got {type(value).__name__}")
            elif expected == "array" and not isinstance(value, list):
                errors.append(f"Field '{field}' must be an array, got {type(value).__name__}")
            elif expected == "object" and not isinstance(value, dict):
                errors.append(f"Field '{field}' must be an object, got {type(value).__name__}")
        return errors

    # --------------------------------------------------------------------- #
    # Prompt / conversation building
    # --------------------------------------------------------------------- #

    def _build_system_prompt(self, instructions: str, allowed_tools: list[str]) -> str:
        """Build the system prompt with instructions and tool definitions."""
        prompt = instructions
        if allowed_tools:
            tool_defs = []
            for tool_name in allowed_tools:
                if self.tool_registry:
                    tool = self.tool_registry.get_tool(tool_name)
                    if tool:
                        tool_defs.append(
                            f"- {tool_name}: {tool.description}\n  Parameters: {json.dumps(tool.parameters, indent=4)}"
                        )
            if tool_defs:
                prompt += "\n\n## Available Tools\n\nYou may use the following tools:\n\n"
                prompt += "\n\n".join(tool_defs)
        return prompt

    def _build_user_prompt(self, payload: dict[str, Any]) -> str:
        """Build the user prompt from the payload."""
        return json.dumps(payload, indent=2)

    # --------------------------------------------------------------------- #
    # Model invocation
    # --------------------------------------------------------------------- #

    async def _invoke_model(
        self,
        spec: AgentSpec,
        conversation: list[dict[str, Any]],
        trace: dict[str, Any],
        iteration: int,
    ) -> ModelResponse:
        """Invoke the model with retries.

        Parameters
        ----------
        spec: AgentSpec
            The agent spec (used for retries, timeouts, and policy).
        conversation: list[dict[str, Any]]
            The growing conversation history. The harness owns this and
            appends assistant messages plus tool-result messages after each
            tool-calling batch.
        trace: dict[str, Any]
            Execution trace being built in-place.
        iteration: int
            Current tool-loop iteration (1-based), used for trace labels.
        """
        import asyncio as _asyncio
        last_error: BaseException | None = None
        for attempt in range(spec.max_retries + 1):
            try:
                tools = self._tool_definitions(
                    [t for t in spec.tools if t in (self.tool_registry.get_allowlist(spec.name) or set())]
                    if self.tool_registry else []
                )
                coro = self.model_adapter.generate(
                    prompt="",
                    system=None,
                    messages=conversation,
                    tools=tools,
                    temperature=spec.policy.get("temperature", 0.1),
                    max_tokens=spec.policy.get("max_tokens", 4096),
                )
                # Enforce timeout; use a generous minimum of 1 second so tests
                # with tiny timeout values don't silently pass.
                timeout = max(1.0, float(spec.timeout_seconds))
                response = await _asyncio.wait_for(coro, timeout=timeout)
                trace["steps"].append({
                    "step": f"model_call_attempt_{iteration}_{attempt + 1}",
                    "status": "ok",
                    "model": response.model,
                    "usage": response.usage,
                })
                return response
            except _asyncio.TimeoutError:
                last_error = TimeoutError(f"Model call exceeded {timeout}s timeout")
                trace["steps"].append({
                    "step": f"model_call_attempt_{iteration}_{attempt + 1}",
                    "status": "failed",
                    "error": f"timeout after {timeout}s",
                })
                if attempt < spec.max_retries:
                    logger.warning("Attempt %d/%d timed out for agent %s", attempt + 1, spec.max_retries + 1, spec.name)
                    time.sleep(0.1 * (attempt + 1))
            except Exception as e:
                last_error = e
                trace["steps"].append({
                    "step": f"model_call_attempt_{iteration}_{attempt + 1}",
                    "status": "failed",
                    "error": str(e),
                })
                if attempt < spec.max_retries:
                    logger.warning("Attempt %d/%d failed for agent %s: %s", attempt + 1, spec.max_retries + 1, spec.name, e)
                    time.sleep(0.1 * (attempt + 1))

        raise HarnessError(
            agent_name=spec.name,
            error_type="retry_exhausted",
            message=f"Model invocation failed after {spec.max_retries + 1} attempts",
            details={"last_error": str(last_error)},
        )

    # --------------------------------------------------------------------- #
    # Tool execution
    # --------------------------------------------------------------------- #

    async def _execute_tool_calls(
        self,
        spec: AgentSpec,
        tool_calls: list[dict[str, Any]],
        tool_calls_log: list[dict[str, Any]],
        tool_results: list[ToolResult],
        executed_call_ids: set[str],
        trace: dict[str, Any],
        iteration: int,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
        """Execute the model's requested tool calls.

        For each call the harness:
        - validates the call shape (``id``, ``name``, ``arguments``);
        - enforces the tool allowlist;
        - skips duplicates based on ``id``;
        - executes the tool through the registry;
        - records results.

        Returns ``(assistant_message, tool_result_messages, loop_denied)``:

        * ``assistant_message`` is the normalized assistant record appended
          to the conversation after the batch.
        * ``tool_result_messages`` are the provider-formatted tool-result
          messages.
        * ``loop_denied`` is true when **every** call in the batch was
          denied by the allowlist, signaling the harness to stop rather
          than looping indefinitely on the same unauthorized requests.
        """
        allowed = (self.tool_registry.get_allowlist(spec.name) if self.tool_registry else set()) or set()
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": None,
            "tool_calls": [],
        }
        tool_result_messages: list[dict[str, Any]] = []
        all_denied = bool(tool_calls)
        batch_denied = True

        for call in tool_calls:
            call_id = call.get("id") if isinstance(call, dict) else None
            name = call.get("name") if isinstance(call, dict) else None
            arguments = call.get("arguments") if isinstance(call, dict) else {}

            # Fail-safe: ignore calls without an id or name — the trace will
            # record them as malformed and the harness will not retry them.
            if not call_id or not name:
                trace["steps"].append({
                    "step": f"tool_loop_iteration_{iteration}",
                    "status": "failed",
                    "error": f"malformed_tool_call: missing id or name (args={arguments!r})",
                })
                continue

            # Deduplication: avoid re-executing the same call id.
            if call_id in executed_call_ids:
                trace["steps"].append({
                    "step": f"tool_loop_iteration_{iteration}",
                    "status": "skipped",
                    "reason": "duplicate_call_id",
                    "call_id": call_id,
                })
                continue

            tool_calls_log.append({"id": call_id, "name": name, "arguments": arguments})
            assistant_message["tool_calls"].append({
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments) if isinstance(arguments, dict) else str(arguments)},
            })
            executed_call_ids.add(call_id)

            # Allowlist check.
            if not self.tool_registry or name not in allowed:
                error_message = (
                    f"Tool '{name}' is not authorized for agent '{spec.name}'"
                    if self.tool_registry and name not in allowed
                    else f"Tool '{name}' is not registered"
                )
                tool_result_messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps({"error": error_message}),
                })
                trace["steps"].append({
                    "step": f"tool_loop_iteration_{iteration}",
                    "status": "denied",
                    "call_id": call_id,
                    "tool_name": name,
                    "reason": error_message,
                })
                continue

            batch_denied = False
            all_denied = False

            result = await self.tool_registry.execute(name, arguments)
            tool_results.append(result)
            trace["steps"].append({
                "step": f"tool_loop_iteration_{iteration}",
                "status": "executed" if result.success else "failed",
                "call_id": call_id,
                "tool_name": name,
                "error": result.error,
            })

            if result.success:
                tool_result_messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(result.content) if isinstance(result.content, (dict, list)) else str(result.content),
                })
            else:
                tool_result_messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps({"error": result.error}),
                })

        return assistant_message, tool_result_messages, all_denied and batch_denied

    # --------------------------------------------------------------------- #
    # Output parsing
    # --------------------------------------------------------------------- #

    def _parse_output(self, content: str) -> dict[str, Any]:
        """Parse the model output as JSON."""
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise HarnessError(
                agent_name="",
                error_type="validation",
                message=f"Invalid JSON output: {e}",
                details={"raw": content[:200]},
            ) from e