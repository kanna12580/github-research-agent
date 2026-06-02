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

Validated services on 2026-06-02:

| Component | Verification |
| --- | --- |
| PostgreSQL with pgvector | Container healthy; `pg_isready` accepted connections |
| Redis | Container running; `redis-cli ping` returned `PONG` |
| FastAPI backend | `GET /api/v1/health` returned `healthy` |
| Readiness dependencies | `GET /api/v1/ready` returned `ready` |
| React frontend build/proxy | Frontend container built; `/` returned HTTP 200 and `/api/v1/health` proxied successfully |

The local `.env` file maps the user's DashScope key to `LLM_API_KEY` and is
gitignored. No key value is stored in source control.

For this environment, Qwen is configured through the Singapore
OpenAI-compatible DashScope endpoint:

```env
LLM_API_BASE=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

Docker containers can optionally use the host proxy through these gitignored
local `.env` values:

```env
DOCKER_HTTP_PROXY=http://host.docker.internal:7890
DOCKER_HTTPS_PROXY=http://host.docker.internal:7890
DOCKER_NO_PROXY=db,redis,localhost,127.0.0.1
```

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
5. The imported default RAG embedding model did not resolve to a public
   HuggingFace repository. The baseline now defaults to `BAAI/bge-m3`.
6. The RAG agent now checks whether the knowledge base contains documents
   before loading local embedding and reranking models. This keeps a clean
   baseline run from blocking on unnecessary model downloads.

## Verification Evidence

Automated verification:

```powershell
docker compose run --rm --no-deps `
  -v 'E:\PycharmProjects\agent_wsl\tests:/app/tests' `
  -v 'E:\PycharmProjects\agent_wsl\metrics:/app/metrics' `
  api pytest -q tests/graph/test_graph.py tests/agents/test_agents.py tests/integration/test_workflow.py
```

Result: `70 passed`, with one upstream LangGraph deprecation warning about
importing `Send` from `langgraph.constants`.

Updated verification on 2026-06-02:

```powershell
docker compose run --rm --no-deps `
  -v 'E:\PycharmProjects\agent_wsl\tests:/app/tests' `
  -v 'E:\PycharmProjects\agent_wsl\metrics:/app/metrics' `
  api pytest -q tests/agents/test_agents.py tests/graph/test_graph.py `
    tests/integration/test_workflow.py tests/rag/test_rag.py
```

Result: `78 passed`, with the same upstream LangGraph deprecation warning.

End-to-end verification task:

```text
Analyze the LangGraph repository documentation at
https://github.com/langchain-ai/langgraph and summarize its core purpose with
citations.
```

Observed result:

| Check | Result |
| --- | --- |
| Session ID | `c90e88ed-9da6-4347-acbf-9846a1dc01b9` |
| Final status | `completed` |
| SSE events | Included `tool_complete`, `report_citation`, `report_chunk`, and `done` |
| Generated report | 798 characters |
| Stored citations | 1 unique GitHub-page citation |

Follow-up API verification on 2026-06-02 through the frontend proxy:

| Check | Result |
| --- | --- |
| Session ID | `5dae28ad-3fa2-4d41-9471-9600ed406232` |
| Final status | `completed` |
| SSE events | Included `connected`, `workflow_start`, `state_update`, and `agent_start` |
| Generated report | 2067 characters |
| Stored citations | 8 persisted source citations |

This run confirmed that the frontend proxy, backend API, SSE stream, report
persistence, and citation persistence are wired together. Container logs showed
the LLM calls still fell back because DashScope TLS negotiation failed through
the current host proxy, so this is not counted as a real Qwen acceptance run.

Visual frontend verification on 2026-06-02:

| Check | Result |
| --- | --- |
| Home page | Loaded at `http://localhost:5173`; system status showed online |
| Research form | Opened through the `开始研究` action |
| Task submission | Submitted a GitHub repository analysis query from the UI |
| Agent trace | Displayed live RAG, search, browser, analyst, reflection, and report events |
| Final UI state | Completed with 47 visible steps, 24 tool calls, and 6 displayed citations |

This confirms the frontend submission flow and visible SSE execution trace.
The same DashScope TLS blocker applies to the LLM-backed quality of the report.

## Current Limitations

This is a runnable baseline with a working fallback report path, but it is not
yet a full LLM-backed acceptance run:

- Calls from the API container to the official DashScope Beijing and Singapore
  OpenAI-compatible endpoints currently fail during TLS negotiation before
  authentication, both directly and through the host proxy
  `host.docker.internal:7890`. The same container has the expected
  `LLM_API_BASE`, `HTTP_PROXY`, `HTTPS_PROXY`, and `LLM_API_KEY` values, so
  this is recorded as an environment/proxy blocker rather than an application
  configuration bug.
- The imported default RAG embedding model `BAAI/bge-zh-qwen2-int8` did not
  resolve to a public HuggingFace repository. The baseline now uses the public
  1024-dimensional `BAAI/bge-m3` model and skips model loading while the
  knowledge base has no documents.
- DuckDuckGo search returned intermittent HTTP `202`; the successful evidence
  run used a directly accessible GitHub repository page through the Browser
  Agent.
- Replanning can collect the same page in more than one pass; report generation
  now deduplicates evidence by source URL before storing citations.
- Browser-plugin UI automation could not be completed in this Codex session
  because the installed plugin directory did not contain its required
  `scripts/browser-client.mjs` runtime file. Frontend build and HTTP/API proxy
  checks succeeded independently.

## Baseline Status

The application stack is runnable and the Agent/SSE/report persistence chain is
demonstrated with public-source evidence. Automated tests pass, and the frontend
submission flow has been visually exercised. Milestone 1 remains partially open
only for a real `qwen3.5-flash` response from inside the API container.
