JobHunt AI Architecture Repair Plan

Status: Verified — implementation authorized
Scope: Harness, workflow loops, multi-agent orchestration
Constraint: Planning only. No implementation changes are authorized.

Verification date: 2026-10-09
Verified against: repository at commit 4e2c29c (main, clean working tree, up to date with origin/main)

1. Objective

Repair the integration between the existing Agent Harness, LangGraph workflow, and multi-agent execution. Preserve useful existing functionality and mock-based testing while ensuring runtime behavior matches documented contracts.

The implementation must not begin until this plan and the repository's current state have been reviewed and approved.

2. Current Architecture

Based on the completed investigation reported by Claude Code:

The harness provides state handling, retry behavior, model adapter integration, and a tool registry.
The workflow is represented as a compiled six-node LangGraph graph.
Worker agents include job matching, application writing, and quality review.
Workflow state is represented using a WorkflowState TypedDict.
Tests cover harness behavior, checkpoint recovery, and workflow execution.
The intended product design includes recruiter, hiring-manager, and ATS evaluations.

These are reported findings and must be checked against the current repository before implementation.

3. Reported Root Causes
3.1 Harness
No effective model tool-calling loop: tool calls and tool results are declared but reportedly never populated or executed.
Unauthorized tools are reportedly filtered from the model prompt rather than rejected by explicit validation.
An empty allowlist may accidentally permit all tools in the registry.
Execution traces are constructed locally but are reportedly not persisted.
Input/output validation checks field presence without adequately validating types and structures.
Retry handling reportedly uses blocking sleep in asynchronous code.
Some agents instantiate a default mock harness instead of using configured model settings.
The quality reviewer reportedly bypasses the harness and can turn exceptions into an empty result.
3.2 Workflow Loop
The configured SQLite checkpoint import reportedly fails with the installed LangGraph version.
The revision decision reportedly has no edge back to the drafting node.
Exceptions are reportedly swallowed, allowing failed workflows to reach an approval state.
The approval-validation node is reportedly defined but not registered in the graph.
Persistence reportedly references a nonexistent profile field.
3.3 Multi-Agent Orchestration
JobMatcherAgent reportedly is not called by the application workflow.
Downstream state expects matching results that may never be produced.
The intended recruiter, hiring-manager, and ATS evaluators reportedly have not been implemented as independent evaluators.
No dedicated supervisor class reportedly coordinates planning, dependencies, retries, and completion.
The workflow may not be connected to an API endpoint that initiates execution.
4. Prioritized Implementation Phases
Phase 0 — Protect repository integrity
Inspect the current Git working tree and preserve unrelated changes.
Review the diffs for README.md and docs/MILESTONE_5_ACCEPTANCE.md.
Recover overwritten documentation only after determining the intended content.
Establish a baseline test result using the project's virtual environment.
Confirm installed dependency versions.

Acceptance criteria:

Existing user changes are preserved.
Documentation recovery is verified.
Baseline test results are recorded.
No source files are modified during this planning phase.
Phase 1 — Correct execution and failure semantics
Reject unauthorized tool calls explicitly.
Ensure invalid tool requests do not appear successful.
Propagate task and workflow failures through explicit statuses or exceptions.
Prevent invalid model output from silently becoming a valid domain result.
Fix persistence and approval-path errors identified in the investigation.

Acceptance criteria:

Unauthorized tool calls are rejected.
Invalid outputs fail validation.
Failed workflow nodes cannot produce a false successful terminal state.
Approval requires valid persisted artifacts.
Tests assert meaningful success and failure conditions.
Phase 2 — Implement the harness tool-calling cycle
Use the configured model adapter to obtain model responses.
Validate every requested tool against the registered tools and effective allowlist.
Execute authorized tools through the harness.
Append tool calls and results to execution history.
Return tool results to the model until it produces a final response or a defined limit is reached.
Enforce bounded iterations and execution timeouts.
Use nonblocking asynchronous retry delays where appropriate.
Persist execution traces and error information.
Ensure mock mode is explicit and configurable.

Acceptance criteria:

A test demonstrates a real tool-call cycle with a tool result returned to the model.
Unauthorized calls never execute.
Tool execution and model failures are reported correctly.
Iteration limits prevent unbounded execution.
Trace records contain the expected execution history.
Mock tests remain deterministic and do not masquerade as live execution.
Phase 3 — Repair persistence and workflow loops
Use a checkpoint implementation compatible with the project's pinned LangGraph version.
Install and declare the required checkpoint dependency if confirmed necessary.
Repair the invalid profile field access.
Connect the revision decision to drafting when revision is permitted.
Enforce revision limits.
Define terminal outcomes for validation failure, exhausted revision attempts, cancellation, and infrastructure failure.
Ensure checkpoints restore sufficient state to resume interrupted execution.

Acceptance criteria:

Checkpoint save, load, and recovery tests pass against the supported implementation.
An interrupted run resumes from persisted state.
A revision decision demonstrably returns to drafting.
Revision limits are respected.
Workflow failure states are distinguishable from successful completion.
Persistence and approval behavior are verified end to end.
Phase 4 — Complete multi-agent integration
Wire JobMatcherAgent into the workflow before downstream nodes consume its results.
Validate matching outputs and store them in workflow state.
Establish explicit task dependencies and result contracts.
Implement a supervisor/coordinator or equivalent graph-based coordination logic.
Add recruiter, hiring-manager, and ATS evaluators if they remain approved product requirements.
Run independent evaluators concurrently when dependencies permit.
Aggregate evaluator outputs into a validated result.
Keep worker responsibilities bounded and prevent unnecessary duplicate work.

Acceptance criteria:

The matching agent is invoked through the real workflow.
Downstream agents receive validated matching results.
Dependencies determine execution order.
Required evaluators execute and their results are aggregated.
Worker failure and partial completion are represented accurately.
The orchestration can terminate successfully or fail explicitly.
Phase 5 — API integration and end-to-end verification
Connect the workflow to the correct API or application entry point.
Verify request validation and profile loading.
Exercise the complete path from request through matching, drafting, evaluation, revision, persistence, and approval.
Verify cancellation and recovery behavior.
Confirm that external application submission or messaging requires appropriate authorization.

Acceptance criteria:

A supported API request can trigger the workflow.
A successful run produces valid, persisted artifacts.
Failure scenarios produce explicit and inspectable errors.
Recovery works after interruption.
Unauthorized external actions cannot occur.
The complete test suite passes without weakening meaningful assertions.
5. Expected Files to Review

The following paths were referenced in the investigation. Confirm their existence and current contents before changing them.

harness.py
registry.py
job_matcher.py
application_writer.py
quality_reviewer.py
checkpointer.py
graph.py
state.py
api/v1.py
app/repositories/audit.py
README.md
docs/MILESTONE_5_ACCEPTANCE.md
Relevant dependency manifests and lockfiles
Harness, checkpoint, workflow, agent, and API tests

The actual repository may use different relative paths. Determine exact paths before implementation.

6. Testing Strategy

Use layered tests:

Unit tests for tool authorization, input/output validation, retries, and error classification.
Harness integration tests that verify model tool calls, execution, and returned tool results.
Checkpoint tests for persistence, recovery, and interruption.
Graph tests for dependency ordering, revision back-edges, and terminal states.
Multi-agent tests for matching, evaluation, aggregation, and failure propagation.
API tests for the supported workflow entry point.
End-to-end tests for successful execution, partial failure, recovery, and cancellation.

Keep deterministic mock-based tests, but add tests that prove each integration actually works. Do not weaken tests merely to make the suite pass.

7. Risks and Assumptions
The investigation findings have not been independently revalidated during preparation of this document.
Dependency compatibility must be confirmed against the project's actual environment and lockfiles.
Restoring tracked documentation can destroy legitimate user changes if performed without reviewing diffs.
A real tool-calling loop introduces limits, timeout, authorization, and duplicate-execution concerns.
Checkpoint recovery may require stable run identifiers and serializable workflow state.
Additional evaluators increase cost and latency; implement them only if they remain required.
Existing tests may encode incorrect behavior and should be corrected with clear rationale.
External side effects require explicit authorization and appropriate idempotency protections.
8. Approval Gate

No implementation is authorized by this document.

Before implementation, present:

The verified repository paths and line references.
The reviewed documentation diffs and recovery status.
The dependency versions and baseline test result.
The exact files expected to change in Phase 1.
The tests and acceptance criteria for that phase.

Wait for explicit approval before making any repair changes.

8.1 Approval Status

Implementation is authorized as of 2026-10-09.

Verified findings (Section 3) are unchanged and remain the basis for all
implementation work. The authorization covers Phases 1-5 in the order
listed, with each phase gated on its own acceptance criteria.

Repository integrity constraints that remain in force:
- Preserve unrelated user changes.
- Do not rewrite README.md or docs/MILESTONE_5_ACCEPTANCE.md.
- Do not weaken existing tests to make the suite pass.
- Keep mock-based tests deterministic; do not let them masquerade as live
  execution.
