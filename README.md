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

Your agent list is a good starting point. I'd make one important adjustment: the Senior Technical Recruiter, Hiring Manager, and ATS evaluators should be separate evaluation personas within a coordinated resume-evaluation stage, rather than three independent agents that each reinvent the entire workflow.

1. Your proposed JobHunt AI agent team
Minimalist line vector of a resume or CV document with a profile picture. Ideal for job applications, recruitment, human resources, and career-related concepts. Editable stroke.
1. Profile Agent
Candidate context
Extracts verified skills, experience, education, salary preferences, location, work authorization, and career goals. Flags missing or conflicting information.

Jobbo - Job Finder Platform by Farhan Bagas for Hatypo Studio on Dribbble
2. Job Discovery Agent
Finds jobs through permitted job-board APIs, company career pages, and supported ATS integrations. Normalizes listings and avoids duplicates.

Careerflow Premium – Full AI Career Toolkit | Get Hired Faster
3. Job Matching Agent
Scores job fit using your existing deterministic matcher, with LLM assistance for semantic interpretation. Explains evidence, gaps, and unknowns.

How to prepare resume in word document
4. Resume Agent
Tailors the résumé to a specific job while preserving factual accuracy. Creates a new document version rather than overwriting an approved one.

5. Resume Evaluation Team
Three distinct perspectives working on the same resume and job description.

Где можно найти IT-рекрутера?
Senior Technical Recruiter persona

Evaluates role alignment, relevant experience, qualifications, career progression, and recruiter readability.

Interview Questions to Hire Java Software Engineer - TapTalent
Hiring Manager persona

Evaluates technical depth, project evidence, engineering impact, ownership, and whether the résumé supports the role's requirements.

AI resume parser | Recruit CRM
ATS Evaluation Agent

Checks parsing-friendly structure, section headings, relevant terminology, dates, formatting risks, and keyword coverage.

Online Job Application Form on Laptop Screen with Apply Now Button and Pencil for Digital Recruitment, Career Search and Employment Concept
6. Application Agent
Populates supported application forms, maps verified profile fields, and identifies fields requiring manual input. Does not submit without authorization.

Why your job applications keep getting ghosted: Top tech executive reveals red flags young candidates ignore - The Economic Times
7. Question Agent
Answers application questions using verified candidate evidence. Flags sensitive, ambiguous, or unsupported questions for the user.

The Job Application Checklist That Gets 3x More Callbacks
8. Approval Agent
Presents the final application, documents, and answers for review. Records explicit approval bound to the exact application version.

Job Application Dashboard | Track Interviews & Offers | Interactive Job Search Tracker | Hired OS | Digital Download - Etsy
9. Tracking Agent
Tracks application status, interviews, rejections, follow-ups, and offers. Uses authorized integrations and user-provided updates.

That gives you nine logical agents, counting the three resume evaluators separately.

2. How LangGraph should orchestrate these agents
I would not run all nine agents for every request. Use different workflows depending on what the candidate wants to accomplish.

Candidate request

Find jobs · Tailor résumé · Prepare application · Track progress

LangGraph workflow router

Job discovery workflow

Profile → Discovery → Matching → Save shortlist

Resume optimization workflow

Resume → Recruiter + Hiring Manager + ATS evaluations → Revise → Re-evaluate

Application workflow

Populate form → Answer questions → Validate → User approval → Submit if authorized

Tracking workflow

Record updates → Schedule reminders → Track interviews and offers

Shared Agent Harness

Model access · Schemas · Tool allowlists · Policies · Timeouts · Retries · Tracing · Error handling

LangGraph handles the state transitions, conditional paths, checkpoints, and approval pauses. The harness executes each agent consistently and enforces its permitted tools and output contract.

3. How the three resume evaluators should work together
This is one of the most valuable parts of your design.

Each evaluator should receive the same immutable inputs:

Candidate profile and verified experience.

Job description and its content hash.

Current résumé version.

A defined evaluation rubric.

Each returns structured findings rather than simply a score.

Evaluator

Main question

Example output

Recruiter

Does this résumé make the candidate's fit clear?

Relevant experience is buried; qualifications need clearer presentation.

Hiring Manager

Does the résumé demonstrate the technical abilities required?

The role requires distributed systems experience, but the evidence is unclear.

ATS Evaluator

Can the résumé be parsed and does it accurately represent relevant job terminology?

A multi-column layout may parse poorly; a required skill is not evidenced.

Then an evaluation aggregator combines the findings and determines whether revision is needed.

A practical workflow is:

Run all three evaluators in parallel when their inputs are ready.

Aggregate their findings into one structured review.

Prioritize factual errors and missing qualifications over stylistic preferences.

Ask the Resume Agent to revise the document without inventing evidence.

Re-run the relevant evaluations.

Stop after a bounded number of automatic revisions and ask the user to intervene if important issues remain.

Important: An ATS evaluator is an approximation, not access to an employer's actual screening algorithm. Present its result as a heuristic assessment, not a guarantee that the résumé will pass an ATS.

4. How Claude Code fits into this architecture
Claude Code is the development tool you use to implement and maintain JobHunt AI. It is not automatically one of the nine runtime agents.

Your application can use a model provider through the existing ModelAdapter interface. If you want Claude models to power one or more runtime agents, implement the appropriate provider adapter and configure it through the harness.

This separation means:

You can use Claude Code to write and test all nine agents.

Your runtime agents can use different model providers if needed.

Mock adapters can test workflows without API costs.

LangGraph can orchestrate the workflows regardless of the underlying model provider.

5. Recommended implementation order
Given the milestones you've described, I would build in this order:

Foundation and harness — profile data, job ingestion, deterministic matching, model adapters, schemas, and tool permissions.

Resume optimization team — Resume Agent, recruiter evaluator, hiring manager evaluator, and ATS evaluator.

Reliable orchestration — LangGraph checkpoint persistence, recovery, idempotency, versioned documents, and approval integrity.

Application preparation — Application Agent, Question Agent, explicit user approval, and carefully controlled submission capabilities.

Discovery and tracking expansion — Additional job sources, application status updates, reminders, interview tracking, and offers.

You do not need nine independent model calls for every workflow. Some agents can initially be simple, deterministic services; others can be model-backed. Keep the logical responsibilities separate even when they share an implementation.

6. The architectural decision I would make now
Define a standard contract for every agent before asking Claude Code to implement more agents. For example:

python
class AgentResult:
    status: str
    data: dict
    evidence: list
    warnings: list
    errors: list
    trace_id: str
This is illustrative; use Pydantic models rather than a bare dictionary in the actual implementation. Each agent should also declare its input schema, output schema, allowed tools, timeout, retry policy, and risk level.

That gives you a consistent interface for LangGraph and makes testing, tracing, and replacing models much easier.