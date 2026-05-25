# Project Instructions: GitHub Repository Research Agent

## Project Goal

This workspace is used to learn from and reproduce the DeepIntel project, then
evolve it into a GitHub open-source project technical research agent for resume
and interview demonstration.

The development path has two explicit phases:

1. Reproduce and validate the original DeepIntel end-to-end workflow.
2. Refactor and extend the system for GitHub repository analysis and comparison.

Do not skip the reproduction phase by prematurely replacing core workflow
components. Record fixes required to make the baseline runnable before beginning
the domain-specific redesign.

## Product Direction

The target product accepts one or more public GitHub repository URLs and
generates an evidence-backed technical selection report. It should evaluate:

- reproducibility and setup quality
- architecture and Agent workflow depth
- technology stack breadth
- extensibility
- engineering quality and project risks

The intended workflow is:

`Repository Input -> Planning -> Evidence Collection -> Analysis -> Verification -> Report`

Evidence collection should eventually include repository metadata, README and
documentation, dependency manifests, directory structure, tests, CI and
container configuration.

## Baseline Architecture To Preserve Initially

During reproduction, retain the original architectural responsibilities:

- LangGraph for workflow orchestration
- FastAPI for backend APIs
- SSE for real-time execution updates
- React and TypeScript for the research console
- PostgreSQL and pgvector for persistent retrieval data
- Redis where required by the baseline application
- browser or search tools used by the existing workflow
- report citations and reflection or verification steps

Only simplify a baseline component when it blocks execution and the reason is
documented.

## Implementation Principles

- Keep changes small, testable, and attributable to a specific milestone.
- Prefer structured evidence models over asking an LLM to freely judge raw text.
- Preserve provenance for report conclusions: scores and conclusions should
  point to collected repository evidence.
- Treat generated reports, runtime data, logs, model caches, secrets, and local
  databases as non-source artifacts.
- Never commit API keys, `.env` contents, access tokens, credentials, or local
  model files.
- Maintain a runnable baseline before starting broad feature changes.
- Add tests for routing, evidence extraction, scoring logic, API contracts, and
  report verification as those features are introduced.

## Planned Milestones

### Milestone 1: Baseline Reproduction

- Import the DeepIntel baseline source.
- Configure environment templates without storing secrets.
- Start backing services and application components.
- Run automated tests and capture any required fixes.
- Produce one successful end-to-end research report with observable Agent trace.

### Milestone 2: Evidence Model

- Define structured GitHub repository evidence schemas.
- Add repository metadata, file tree, README and dependency collectors.
- Store evidence and references independently from final prose reports.

### Milestone 3: GitHub Research Workflow

- Adapt planning for single-repository and multi-repository comparison tasks.
- Implement scoring for reproducibility, depth, stack breadth, extensibility
  and engineering quality.
- Adapt verification to ensure each important conclusion is evidence-backed.

### Milestone 4: Demonstration And Evaluation

- Build a repeatable evaluation set of public repository comparison tasks.
- Measure citation coverage, score consistency, latency and model/token cost.
- Prepare screenshots, architecture documentation and interview-ready examples.

## Version Control Rules

- Use `main` as the stable integration branch.
- Create focused feature branches for non-trivial changes after baseline import.
- Commit source, configuration templates, documentation and tests.
- Exclude secrets, local databases, logs, model downloads, caches, build output
  and generated reports unless a small sanitized example is intentionally added.
- Keep upstream attribution and reproduction notes in project documentation when
  the DeepIntel baseline is imported.

## Completion Criteria For The Baseline

The reproduction phase is complete only when:

- the backend health endpoint responds successfully
- the frontend can submit a research task
- Agent execution updates are visible through SSE or the UI
- a report with source citations is successfully generated
- test/build status and any remaining limitations are documented
