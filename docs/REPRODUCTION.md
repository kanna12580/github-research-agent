# DeepIntel Baseline Reproduction Notes

## Scope

This branch reproduces the public DeepIntel baseline before adapting it into a
GitHub repository technical research agent.

- Upstream repository: `https://github.com/wblxr408/DeepIntel`
- Imported upstream commit: `815383e`
- Working branch: `baseline/deepintel-import`
- Local model target: `qwen3.5-flash` through the DashScope
  OpenAI-compatible endpoint

## Environment

The baseline is run through Docker Compose so that the backend uses the
project-defined Python 3.11 image instead of relying on host Python packages.

Validated services on 2026-05-25:

| Component | Verification |
| --- | --- |
| PostgreSQL with pgvector | Container healthy; `pg_isready` accepted connections |
| Redis | Container running; `redis-cli ping` returned `PONG` |
| FastAPI backend | `GET /api/v1/health` returned `healthy` |
| Readiness dependencies | `GET /api/v1/ready` returned `ready` |
| React frontend build/proxy | Frontend container built; `/` returned HTTP 200 and `/api/v1/health` proxied successfully |

The local `.env` file maps the user's DashScope key to `LLM_API_KEY` and is
gitignored. No key value is stored in source control.

## Baseline Fixes Required To Run

The following narrow fixes were required while reproducing the imported
baseline:

1. The default model configuration and UI option were aligned to
   `qwen3.5-flash`.
2. A reflection-triggered replan previously left completed tool nodes marked
   `done`, which ended the graph before report generation. Replanning now
   clears tool execution state and performs the next evidence pass.
3. The browser graph node validated natural-language input as a URL before the
   Browser Agent could resolve it. It now validates the resolved target and
   extracts an embedded public URL such as a GitHub repository URL.
4. SSE connections previously stayed open after `done` or `workflow_error`.
   Terminal events now close the event stream.

## Verification Evidence

Automated verification:

```powershell
docker compose run --rm --no-deps `
  -v 'E:\PycharmProjects\agent_wsl\tests:/app/tests' `
  -v 'E:\PycharmProjects\agent_wsl\metrics:/app/metrics' `
  api pytest -q tests/graph/test_graph.py tests/agents/test_agents.py tests/integration/test_workflow.py
```

Result: `69 passed`, with one upstream LangGraph deprecation warning about
importing `Send` from `langgraph.constants`.

End-to-end verification task:

```text
Analyze the LangGraph repository documentation at
https://github.com/langchain-ai/langgraph and summarize its core purpose with
citations.
```

Observed result:

| Check | Result |
| --- | --- |
| Session ID | `18c37059-bb4d-45d0-8eff-a48f7ceb6952` |
| Final status | `completed` |
| SSE events | Included `tool_complete`, `report_citation`, `report_chunk`, and `done` |
| Generated report | 1440 characters |
| Stored citations | 2 GitHub-page citations |

## Current Limitations

This is a runnable baseline with a working fallback report path, but it is not
yet a full LLM-backed acceptance run:

- Calls from this environment to the official DashScope Beijing, Singapore,
  and US endpoints fail during TLS negotiation before authentication. Official
  Alibaba Cloud documentation confirms that `qwen3.5-flash` and the configured
  Beijing endpoint are supported, so this is recorded as a network blocker.
- The configured RAG embedding model
  `BAAI/bge-zh-qwen2-int8` cannot currently be downloaded from HuggingFace in
  this environment.
- DuckDuckGo search returned intermittent HTTP `202`; the successful evidence
  run used a directly accessible GitHub repository page through the Browser
  Agent.
- Replanning can collect the same page in more than one pass, producing
  duplicate stored citations. Deduplication should be added before using the
  system for comparative reports.
- Browser-plugin UI automation could not be completed in this Codex session
  because the installed plugin directory did not contain its required
  `scripts/browser-client.mjs` runtime file. Frontend build and HTTP/API proxy
  checks succeeded independently.

## Baseline Status

The application stack is runnable and the Agent/SSE/report persistence chain is
demonstrated with public-source evidence. Milestone 1 remains partially open
until a real `qwen3.5-flash` response can be obtained and the frontend
submission flow can be visually exercised in a functioning browser runtime.
