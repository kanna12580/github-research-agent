# DeepIntel 基线复现记录

## 范围

当前分支用于先复现公开的 DeepIntel 基线项目，再逐步改造成
GitHub 开源项目技术调研 Agent。

- 上游仓库：`https://github.com/wblxr408/DeepIntel`
- 导入的上游提交：`815383e`
- 当前工作分支：`baseline/deepintel-import`
- 本地目标模型：通过 DashScope OpenAI 兼容接口调用 `qwen3.5-flash`

## 环境

基线项目通过 Docker Compose 运行，后端使用项目定义的 Python 3.11
镜像，不依赖宿主机 Python 包。

2026-06-02 已验证的服务：

| 组件 | 验证结果 |
| --- | --- |
| PostgreSQL + pgvector | 容器健康，`pg_isready` 可连接 |
| Redis | 容器运行中，`redis-cli ping` 返回 `PONG` |
| FastAPI 后端 | `GET /api/v1/health` 返回 `healthy` |
| 依赖就绪检查 | `GET /api/v1/ready` 返回 `ready` |
| React 前端构建与代理 | 前端容器构建成功，`/` 返回 HTTP 200，`/api/v1/health` 可代理到后端 |

本地 `.env` 会把用户的 DashScope Key 映射到 `LLM_API_KEY`，该文件已被
`.gitignore` 忽略。源码中不保存任何密钥值。

当前环境使用 DashScope 新加坡地域的 OpenAI 兼容接口：

```env
LLM_API_BASE=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

如果 Docker 容器需要通过宿主机代理访问外网，可在本地 `.env` 中配置：

```env
DOCKER_HTTP_PROXY=http://host.docker.internal:7890
DOCKER_HTTPS_PROXY=http://host.docker.internal:7890
DOCKER_NO_PROXY=db,redis,localhost,127.0.0.1
```

## 为跑通基线所做的修复

复现导入后的基线项目时，做了以下小范围修复：

1. 将默认模型配置和前端模型选项对齐到 `qwen3.5-flash`。
2. 反思节点触发重新规划时，原逻辑会保留已完成工具节点的 `done`
   状态，导致图流程提前结束而不生成报告；现在重新规划会清理工具
   执行状态，并执行下一轮证据采集。
3. Browser 图节点原先在 Browser Agent 解析前就把自然语言输入当作 URL
   校验；现在改为校验解析后的目标，并能从输入中提取 GitHub 仓库等
   公开 URL。
4. SSE 连接在 `done` 或 `workflow_error` 后曾经不会主动关闭；现在终止
   事件会关闭事件流。
5. 导入项目默认的 RAG embedding 模型无法解析到公开 HuggingFace 仓库；
   当前默认改为公开可用的 `BAAI/bge-m3`。
6. RAG Agent 在加载本地 embedding 和 reranker 前，会先检查知识库是否
   存在文档。知识库为空时直接跳过本地模型初始化，避免干净基线启动
   被不必要的模型下载阻塞。

## 验证记录

自动化测试：

```powershell
docker compose run --rm --no-deps `
  -v 'E:\PycharmProjects\agent_wsl\tests:/app/tests' `
  -v 'E:\PycharmProjects\agent_wsl\metrics:/app/metrics' `
  api pytest -q tests/graph/test_graph.py tests/agents/test_agents.py tests/integration/test_workflow.py
```

结果：`70 passed`，只有一个 LangGraph 上游弃用警告：
`Send` 未来应从 `langgraph.types` 导入。

2026-06-02 更新后的验证：

```powershell
docker compose run --rm --no-deps `
  -v 'E:\PycharmProjects\agent_wsl\tests:/app/tests' `
  -v 'E:\PycharmProjects\agent_wsl\metrics:/app/metrics' `
  api pytest -q tests/agents/test_agents.py tests/graph/test_graph.py `
    tests/integration/test_workflow.py tests/rag/test_rag.py
```

结果：`78 passed`，仍只有同一个 LangGraph 上游弃用警告。

端到端验证任务：

```text
Analyze the LangGraph repository documentation at
https://github.com/langchain-ai/langgraph and summarize its core purpose with
citations.
```

观察结果：

| 检查项 | 结果 |
| --- | --- |
| Session ID | `c90e88ed-9da6-4347-acbf-9846a1dc01b9` |
| 最终状态 | `completed` |
| SSE 事件 | 包含 `tool_complete`、`report_citation`、`report_chunk`、`done` |
| 生成报告 | 798 个字符 |
| 持久化引用 | 1 条唯一 GitHub 页面引用 |

2026-06-02 通过前端代理进行的 API 验证：

| 检查项 | 结果 |
| --- | --- |
| Session ID | `5dae28ad-3fa2-4d41-9471-9600ed406232` |
| 最终状态 | `completed` |
| SSE 事件 | 包含 `connected`、`workflow_start`、`state_update`、`agent_start` |
| 生成报告 | 2067 个字符 |
| 持久化引用 | 8 条来源引用 |

该验证确认：前端代理、后端 API、SSE 流、报告持久化和引用持久化已经串通。
但容器日志显示 LLM 调用仍因 DashScope TLS 握手失败走了 fallback 路径，
所以这一次不算真实 Qwen 验收。

2026-06-02 前端可视化验证：

| 检查项 | 结果 |
| --- | --- |
| 首页 | `http://localhost:5173` 可打开，系统状态显示在线 |
| 研究表单 | 点击 `开始研究` 后可打开 |
| 任务提交 | 可从 UI 提交 GitHub 仓库分析查询 |
| Agent 轨迹 | 可实时显示 RAG、搜索、浏览器、分析师、反思、报告事件 |
| 最终 UI 状态 | 任务完成，页面显示 47 个步骤、24 次工具调用、6 条引用 |

该验证确认：前端提交流程和可见 SSE 执行轨迹可用。报告质量仍受当前
DashScope TLS 连通性问题影响。

## 当前限制

这是一个可运行的基线栈，fallback 报告路径可以工作，但还不是完整的
真实 LLM 验收：

- API 容器访问 DashScope 北京和新加坡 OpenAI 兼容接口时，在认证前的
  TLS 握手阶段失败。无论直连还是通过宿主机代理
  `host.docker.internal:7890`，都出现
  `SSL: UNEXPECTED_EOF_WHILE_READING`。容器内已经能看到正确的
  `LLM_API_BASE`、`HTTP_PROXY`、`HTTPS_PROXY` 和 `LLM_API_KEY`，因此目前
  记录为环境或代理出口问题，而不是应用配置错误。
- 导入项目默认的 RAG embedding 模型 `BAAI/bge-zh-qwen2-int8` 无法解析到
  公开 HuggingFace 仓库。当前改用公开的 1024 维 `BAAI/bge-m3`，并在
  知识库为空时跳过本地模型加载。
- DuckDuckGo 搜索偶发返回 HTTP `202`；成功的证据采集使用了 Browser
  Agent 直接访问 GitHub 仓库页面。
- 重新规划会在多轮采集中重复收集同一页面；报告生成阶段已按来源 URL
  去重后再存储引用。

## 基线状态

应用栈可运行，Agent / SSE / 报告持久化链路已经用公开来源证据验证。
自动化测试通过，前端提交流程也已经可视化验证。Milestone 1 目前只剩
API 容器内真实调用 `qwen3.5-flash` 这一项受本地网络或代理出口阻塞。
