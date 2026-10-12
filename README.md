jobhuntai — Full Multi-Agent Implementation Requirements

Implement the complete specialist-agent architecture below in the existing repository using its existing LangGraph workflow, Harness, Loop, schemas, models, and persistence layer.

Do not rebuild the project from scratch. Inspect the implementation plan and current code before making changes.

A. Implement all 8 primary specialist agents
1. Profile Agent

Responsibilities:

Parse the candidate's resume and user-provided information.
Extract skills, experience, education, achievements, certifications, preferences, target roles, salary expectations, location, work arrangement, and work authorization where provided.
Distinguish verified facts, user preferences, and unknown information.
Never infer work authorization, sponsorship eligibility, salary expectations, or qualifications without evidence.
Maintain a structured, versioned candidate profile.
2. Job Discovery Agent

Responsibilities:

Discover jobs through available authorized job-board APIs, company career pages, and supported ATS integrations.
Normalize job title, company, location, job description, salary, employment type, posting date, source, and application URL.
Deduplicate listings using stable identifiers and normalized URLs.
Track source, retrieval time, and verification status.
Respect source terms, rate limits, and access restrictions.
Do not fabricate job listings or claim live discovery when no live connector exists.
3. Job Matching Agent

Responsibilities:

Match each job against the candidate's verified profile and stated preferences.
Produce a configurable 0–100 fit score with component scores and explanations.
Assess skills, experience, seniority, location, work arrangement, compensation when available, and explicit eligibility constraints.
Separate hard eligibility constraints from preference-based ranking.
Identify missing evidence and skill gaps.
Never use protected characteristics to rank candidates or infer suitability.
4. Resume Agent

Responsibilities:

Tailor a resume for one specific job description.
Preserve factual accuracy, dates, titles, qualifications, and employment history.
Use only verified candidate evidence.
Never invent achievements, metrics, tools, certifications, or experience.
Maintain traceability between generated resume claims and source-profile evidence.
Support configurable resume templates and versioned outputs.
Produce a job-specific resume and change summary.
B. Implement all 3 resume evaluators

All three evaluators must assess the same specific job description and the same current resume version. Each evaluator returns structured findings, evidence, severity, and recommended changes.

4a. Senior Technical Recruiter Evaluator

Evaluate:

Recruiter-level relevance and clarity.
Required versus preferred qualifications.
Career narrative and credibility.
Seniority alignment and unsupported claims.
Resume readability and relevance to the target role.
4b. Hiring Manager Persona Evaluator

Support configurable hiring-manager personas appropriate to the target job family and seniority.

Evaluate:

Demonstrated technical or functional depth.
Evidence of impact and ownership.
Relevant projects, outcomes, and problem-solving.
Role-specific competency gaps.
Whether the resume provides evidence for the responsibilities in the JD.

Do not create arbitrary personas for every job. Select and document appropriate personas from a configurable set.

4c. ATS Evaluator

Evaluate:

Required and preferred keyword coverage.
Evidence-backed alignment with the JD.
Section structure, readability, and parseability.
Formatting risks, missing standard sections, and ambiguous terminology.

Clearly distinguish a local heuristic ATS score from a real vendor ATS score. Do not claim to predict an employer's proprietary ranking system.

C. Resume evaluation and improvement loop

Implement this sequence:

Resume Agent generates a job-specific draft.
Run the Senior Technical Recruiter, Hiring Manager Persona, and ATS Evaluators.
Aggregate their findings into a structured improvement report.
Prioritize high-severity, evidence-supported changes.
Ask the Resume Agent to revise the draft.
Re-run the evaluators against the same JD and new resume version.
Stop when configurable quality criteria are met, the score improvement plateaus, no valid changes remain, or the maximum iteration count is reached.
Save all resume versions, evaluation results, and the stop reason.

Use bounded retries, explicit thresholds, deterministic checks where possible, and duplicate-feedback suppression. Never increase a score by adding unsupported claims or keyword stuffing.

D. Implement the remaining 4 primary agents
5. Application Agent
Use supported and authorized browser automation or ATS integrations.
Map verified candidate facts to application fields.
Detect unknown, sensitive, or ambiguous questions.
Save progress where supported.
Do not bypass CAPTCHAs, access controls, or platform restrictions.
Do not submit applications without explicit user approval.
6. Question Agent
Draft answers using the verified candidate profile, resume, and job context.
Identify questions that require candidate input.
Never fabricate personal history, work authorization, sponsorship answers, demographic answers, or other declarations.
Mark uncertain answers for clarification.
7. Approval Agent
Present the employer, job URL, final resume, cover letter, application answers, and relevant declarations for review.
Require explicit, job-specific user approval before submission.
Bind approval to the exact application version and content.
Invalidate approval if application content changes.
Keep approval state persistent and auditable.
8. Tracking Agent
Track discovered, matched, shortlisted, draft-ready, pending-approval, submitted, interview, rejected, offer, and withdrawn states as appropriate.
Record timestamps, application identifiers, resume versions, and source references.
Mark a submission as confirmed only when a trusted integration reports success.
Support follow-up reminders, status updates, and pipeline summaries.
Prevent duplicate application records.
E. Harness, LangGraph, and Loop architecture
Reuse the current LangGraph and orchestration implementation.
Use typed state schemas and clear node input/output contracts.
Organize phases into maintainable nodes or subgraphs.
Run independent tasks in parallel where safe.
Define conditional edges, retries, timeouts, error recovery, and loop termination.
Persist workflow checkpoints and application state using the existing persistence layer.
Make external side effects idempotent where possible.
Add structured logging, tracing, and error reporting without exposing secrets or sensitive candidate data.
Ensure application submission cannot be triggered by an uncontrolled loop.
F. Docker and configuration
Preserve existing Docker and Docker Compose infrastructure where possible.
Add required configuration, migrations, dependencies, and health checks.
Use environment variables or secret management for credentials.
Do not put API keys or personal candidate data into images or source control.
Document required integrations and their configuration.
Do not use mock job data in production paths.
G. Testing and delivery

Add tests for:

Every primary agent and all three evaluators.
Shared schemas, state transitions, and evidence traceability.
Resume factual consistency.
Evaluator aggregation and bounded improvement loops.
Loop termination, retries, duplicate detection, and checkpoint recovery.
Application approval, approval invalidation, and submission failure handling.
Tracking status correctness.
Docker startup and an end-to-end workflow with external integrations mocked.

Before implementation:

Map all 11 agent roles to existing code and proposed LangGraph nodes.
Identify reusable components and missing integrations.
Present the proposed state schema and graph design.

Then implement incrementally, run the relevant tests and Docker checks, and report actual results. Clearly identify which integrations are functional, which require credentials, and which remain unimplemented.

Do not silently replace existing infrastructure, invent successful test results, or claim an integration works without verification.




[ Phase 1: Sourcing & Filtering ] 
  Profile Agent (1) ──► Job Discovery Agent (2) ──► Job Matching Agent (3)
                                                              │
[ Phase 2: Tailoring & Evaluation Loop ]                      ▼
  Resume Agent (4) ◄───────────────────────── [ Evaluation Gate ]
        │                                      ├─ 4a. Tech Recruiter
        ├──────────────────────────────────────┼─ 4b. Hiring Manager
        ▼                                      └─ 4c. ATS Scorer
  (Iterate until score >= threshold)
        │
[ Phase 3: Execution & Approval ]                     ▼
  Question Agent (6) ──► Application Agent (5) ──► Approval Agent (7) (Human-in-the-Loop)
                                                              │
[ Phase 4: Lifecycle Management ]                             ▼
  Tracking Agent (8) ◄────────────────────────────────────────┘