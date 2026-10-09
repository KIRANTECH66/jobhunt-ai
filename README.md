## Milestone 2: Harness and Matching (Current)

✅ **Completed** — Agent harness, model adapter, tool registry, and LLM-assisted matching are implemented.

### Agent Architecture

```
Agent Harness
├── Input validation (JSON Schema)
├── Tool resolution (per-agent allowlists)
├── Model invocation (with retries & timeouts)
├── Output validation (JSON Schema)
├── Trace emission (structured execution logs)
└── Error handling (structured errors)

Job Matcher Agent
├── LLM-assisted semantic matching (when available)
└── Deterministic fallback (keyword-based scoring)
```

### New Components

| Component | Description |
|-----------|-------------|
| `app/llm/model_adapter.py` | Abstract model adapter with `MockModelAdapter` + `OpenAIModelAdapter` |
| `app/tools/registry.py` | Tool registry with per-agent allowlists and policy enforcement |
| `app/harness/harness.py` | Shared Agent Harness with validation, retries, tracing |
| `app/agents/job_matcher.py` | LLM-assisted Job Matcher with deterministic fallback |

### Test Results

**53 tests passing:**
- 43 Milestone 1 tests (regression baseline)
- 10 Milestone 2 tests (harness + matcher agent)

### Usage

```python
from app.harness.harness import AgentHarness, AgentSpec
from app.agents.job_matcher import JobMatcherAgent

# Create the harness with mock model
harness = AgentHarness()
matcher = JobMatcherAgent(harness=harness)

# Run the matcher
result = await matcher.match(profile, job)
print(f"Score: {result.score}")
print(f"Recommendation: {result.recommendation}")
```

## Milestone 3: Application Workflow (Next)

- [ ] Implement Application Writer
- [ ] Implement Quality Reviewer
- [ ] Implement document versioning
- [ ] Implement LangGraph workflow
- [ ] Implement checkpoint persistence
- [ ] Implement revision limits and review gates



Open-source tools to use
LangGraph  — orchestrate the agents.

Pydantic AI  — implement agent logic and tools; evaluate its harness capabilities for your coding workflow.

Ollama  — run local language models.

PostgreSQL  — store job listings, resumes, and applications.

Streamlit  — build an initial user interface.

Langfuse  — monitor agent execution.


 Best open-source tools to consider
Qbit Labs | AI-First MVP Studio
1. LangGraph — Best for orchestration

Recommended
Manages multiple agents, workflow steps, shared state, branching, retries, and human approvals.

Best for: Complex workflows with control over how agents communicate.

Language: Python and JavaScript/TypeScript.

Website: 
LangGraph documentation 

Agent Frameworks
2. Pydantic AI + Pydantic AI Harness

A strong choice if you want to build the actual agent runtime, with tools, context management, subagents, and coding-agent capabilities. 

GitHub

Best for: Custom agent harnesses and Python applications.

Website: 
Pydantic AI 

Code: 
GitHub repository 

OpenAI Agents SDK explained with visualizations by Claude | Hai Wang posted on the topic | LinkedIn
3. OpenAI Agents SDK — Simple to start

Provides agent handoffs, tools, guardrails, and tracing. The SDK is open source, although using hosted models may cost money. 

GitHub
+1

Best for: Getting a working multi-agent system running quickly.

Code: 
GitHub repository 

Crew AI Pricing & Reviews 2025 | Techjockey.com
4. CrewAI — Easy role-based teams

Lets you define agents with different roles, tasks, and responsibilities.

Best for: Researcher, developer, reviewer, and tester agent teams.

Website: 
CrewAI 

Code: 
GitHub repository 