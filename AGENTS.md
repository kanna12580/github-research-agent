# Project Instructions: GitHub Repository Research Agent

## Project Goal

This workspace is used to learn from and reproduce the DeepIntel project, then
evolve it into a GitHub open-source project technical research agent for resume
and interview demonstration.

The development path has two explicit phases:

1. Reproduce and validate the original DeepIntel end-to-end workflow.
2. Refactor and extend the system for GitHub repository analysis and comparison.

The reproduction phase is complete. Keep the runnable baseline intact while
building the GitHub-domain layer incrementally. Do not replace the core
LangGraph/FastAPI/SSE/report flow until the new GitHub evidence path has its
own tests and a minimal working API surface.

Current phase: Milestone 4, Demonstration and evaluation loop.

## Product Direction

The target product accepts one or more public GitHub repository URLs and
generates an evidence-backed technical selection report. It should evaluate:

- reproducibility and setup quality
- architecture and Agent workflow depth
- technology stack breadth
- extensibility
- engineering quality and project risks

The target workflow is:

`Repository Input -> GitHub Evidence Collection -> Scoring -> Verification -> Report`

Evidence collection should include repository metadata, README and
documentation, dependency manifests, directory structure, tests, CI,
container configuration, license, release signals and activity signals.

Important scoring dimensions:

- reproducibility and setup quality
- architecture and Agent workflow depth
- technology stack breadth
- extensibility
- engineering quality
- maintenance activity and project risks

## Baseline Architecture To Preserve

Retain the original architectural responsibilities while adding GitHub-domain
capabilities:

- LangGraph for workflow orchestration
- FastAPI for backend APIs
- SSE for real-time execution updates
- React and TypeScript for the research console
- PostgreSQL and pgvector for persistent retrieval data
- Redis where required by the baseline application
- browser or search tools used by the existing workflow
- report citations and reflection or verification steps

Do not remove or heavily rewrite baseline components while implementing the
GitHub research workflow. Prefer additive modules first, then integrate them
into the existing workflow once they are independently tested.

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
- Keep GitHub evidence structured before it is turned into prose.
- Prefer deterministic collectors and scoring heuristics for facts that can be
  computed from repository files or metadata. Use LLMs for synthesis after the
  evidence object exists.
- Treat GitHub API tokens as optional. Public repository collection must work
  without a token when rate limits allow it.

## Planned Milestones

### Milestone 1: Baseline Reproduction

- Import the DeepIntel baseline source.
- Configure environment templates without storing secrets.
- Start backing services and application components.
- Run automated tests and capture any required fixes.
- Produce one successful end-to-end research report with observable Agent trace.

Status: complete. The baseline runs through Docker Compose, uses
`qwen3.5-flash` through DashScope OpenAI-compatible API, exposes frontend SSE
progress, and has produced a real cited end-to-end report.

### Milestone 2: Evidence Model

- Define structured GitHub repository evidence schemas.
- Add repository metadata, file tree, README and dependency collectors.
- Store evidence and references independently from final prose reports.

Current implementation order:

1. Parse and normalize public GitHub repository URLs.
2. Define Pydantic evidence schemas for repository identity, metadata, files,
   dependency manifests, CI/container signals and documentation signals.
3. Add a public GitHub collector that works through GitHub REST/raw endpoints.
4. Add deterministic scoring inputs for reproducibility, depth, stack breadth,
   extensibility, engineering quality and risk.
5. Expose a narrow API or workflow adapter only after the collector and scoring
   tests pass.

Status: complete. The project now includes GitHub URL parsing, structured
repository evidence schemas, public GitHub REST collection, deterministic
scorecards, an analysis API, tests, and Chinese SDK usage documentation.

### Milestone 3: GitHub Research Workflow

- Adapt planning for single-repository and multi-repository comparison tasks.
- Implement scoring for reproducibility, depth, stack breadth, extensibility
  and engineering quality.
- Adapt verification to ensure each important conclusion is evidence-backed.

Current implementation order:

1. Detect GitHub repository URLs in ordinary research prompts.
2. Insert `github` collection nodes into the LangGraph DAG before search, RAG,
   browser, analyst and report stages.
3. Convert structured GitHub evidence bundles into standard report evidence
   with provenance URLs.
4. Preserve GitHub repositories, evidence bundles and scorecards in workflow
   state for future comparison UI and verification work.
5. Template GitHub technical research reports so repository tasks no longer use
   the generic business research report structure.
6. Add deterministic multi-repository comparison and ranking before frontend
   visualization work.
7. Add single-repository and multi-repository workflow tests before expanding
   evaluation tasks.

Current technical additions:

- `github` tool node in the LangGraph workflow
- deterministic GitHub scorecard evidence injected into the existing analyst
  and report path
- GitHub repository state fields: repositories, evidence bundles and scorecards
- guardrail registration for read-only GitHub repository collection
- Chinese GitHub technical report template with sections for reproducibility,
  architecture and Agent workflow depth, stack breadth, extensibility,
  engineering quality, risks and interview presentation advice
- deterministic GitHub fallback report skeleton for offline or failed LLM runs
- deterministic multi-repository comparison using scorecard weights tuned for
  resume/interview reproduction suitability
- GitHub comparison state and ranking evidence injected into the existing
  analyst/report path

Do not build a separate report pipeline yet. The existing research task
entrypoint should reliably produce a cited GitHub technical research report
from one public repository URL, and then extend toward multi-repository
comparison.

For multi-repository comparison, prefer deterministic ranking from structured
scorecards over free-form LLM judgment. LLM synthesis may explain the ranking,
but it must not invent scores or reorder repositories without evidence.

### Milestone 4: Demonstration And Evaluation

- Build a repeatable evaluation set of public repository comparison tasks.
- Measure citation coverage, score consistency, latency and model/token cost.
- Prepare screenshots, architecture documentation and interview-ready examples.

Current implementation order:

1. Maintain one fixed GitHub Agent project comparison demo.
2. Provide a deterministic compare API for quick scoring, ranking and
   evaluation checks without invoking the LLM report path.
3. Document frontend demo steps, API smoke evaluation and interview talking
   points.
4. Expand screenshots and additional evaluation cases only after this first
   demo remains stable.

Current frontend demonstration direction:

- Provide a GitHub repository input area that can turn one or more public
  repository URLs into a research prompt.
- Show a GitHub technical research dashboard with detected repositories,
  GitHub tool activity, recommended repository and ranking table.
- Keep the existing SSE agent trace, tool trace, report preview and citation
  panels visible during GitHub research runs.
- Favor interview-demo clarity over adding a separate complex frontend route
  until the core workflow is stable.

The first fixed demo task compares:

- `wblxr408/DeepIntel`
- `PavithraNagineni/multi-agent-research-system`
- `tarun7r/deep-research-agent`

The demo/evaluation assets live in `docs/DEMO_EVALUATION.md` and
`docs/demo/github_agent_comparison_demo.json`.

Status: first demo loop complete. A real end-to-end GitHub comparison research
task has been run with `GITHUB_TOKEN` configured and saved as:

- `docs/demo/sample_report.md`
- `docs/demo/sample_result_summary.json`
- `docs/demo/sample_citations.json`
- `docs/demo/sample_report_preview.html`
- `docs/demo/screenshots/01_frontend_home.png`
- `docs/demo/screenshots/02_sample_report_preview.png`

Keep these sample artifacts sanitized and small. They are intentionally committed
as interview-ready examples; do not commit arbitrary generated reports or local
runtime output.

Final polish status: complete on the feature branch. The project now includes
interview presentation material, a cleaner GitHub ranking UI, Demo prompt copy
support, clearer GitHub token/rate-limit failure guidance, highlighted report
score tables, cleaned sample citations and build/smoke verification. The next
project-level step is to merge `codex/github-research-workflow-m3` into `main`
after user confirmation.

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

Status: complete.

## Completion Criteria For The GitHub Evidence Model

Milestone 2 is complete when:

- one public GitHub URL can be parsed into stable `owner/repo` identity
- metadata, README, file tree and key manifest signals can be collected
- evidence objects retain provenance URLs for every important conclusion
- deterministic scores are generated from structured evidence
- tests cover URL parsing, evidence extraction and scoring edge cases
