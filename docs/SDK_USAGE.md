# DeepIntel 本地启动与 SDK 调用文档

## 1. 适用范围

本文档面向本地开发、复现验收和后续二次开发，说明如何：

- 启动 DeepIntel 全栈服务
- 配置 DashScope / Qwen OpenAI 兼容接口
- 验证容器内真实 Qwen 调用
- 通过 HTTP API 创建研究任务
- 通过 SSE 接收 Agent 执行事件
- 使用 PowerShell、Python 和 Node.js 编写最小 SDK 调用

当前默认模型：

```text
qwen3.5-flash
```

当前默认 DashScope Base URL：

```text
https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

## 2. 本地启动

### 2.1 准备 `.env`

从模板复制：

```powershell
Copy-Item .env.example .env
```

至少配置：

```env
LLM_PROVIDER=qwen
LLM_MODEL=qwen3.5-flash
LLM_API_KEY=你的 DashScope API Key
LLM_API_BASE=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

如果 Docker 容器需要通过宿主机 FlClash 访问外网：

```env
DOCKER_HTTP_PROXY=http://host.docker.internal:7890
DOCKER_HTTPS_PROXY=http://host.docker.internal:7890
DOCKER_NO_PROXY=db,redis,localhost,127.0.0.1
```

如果要使用 GitHub Repository Evidence API，建议配置一个 GitHub Personal
Access Token 以提升公共 API 额度：

```env
GITHUB_TOKEN=你的 GitHub Token
```

注意：

- `.env` 不要提交到 Git。
- 本项目通过 OpenAI SDK 调用 DashScope，因此使用 `/compatible-mode/v1`
  这类 OpenAI 兼容地址，不使用 DashScope 原生
  `/api/v1/services/aigc/...` 地址。
- `GITHUB_TOKEN` 只用于 GitHub REST API 采集公开仓库 evidence，不要提交。

### 2.2 启动服务

```powershell
docker compose up -d --build
```

查看状态：

```powershell
docker compose ps
```

期望看到：

- `deepintel-db`：healthy
- `deepintel-redis`：running
- `deepintel-api`：healthy
- `deepintel-frontend`：running

### 2.3 访问入口

前端：

```text
http://localhost:5173
```

后端：

```text
http://localhost:8000
```

前端 Nginx 会代理 `/api` 到后端，因此 SDK 调用建议统一走：

```text
http://localhost:5173/api/v1
```

## 3. 健康检查

PowerShell：

```powershell
Invoke-RestMethod http://localhost:5173/api/v1/health
Invoke-RestMethod http://localhost:5173/api/v1/ready
```

curl：

```powershell
curl.exe http://localhost:5173/api/v1/health
curl.exe http://localhost:5173/api/v1/ready
```

期望：

- `/health` 返回 `healthy`
- `/ready` 返回 `ready`

## 4. DashScope / Qwen 连通性验证

### 4.1 TLS 层验证

```powershell
docker compose exec -T api sh -lc "curl -v --proxy http://host.docker.internal:7890 https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models"
```

不带 Key 时，如果看到 HTTP `401`，说明网络、代理、TLS 都已经打通。

### 4.2 OpenAI SDK 最小验证

```powershell
docker compose exec -T api python -c "import os; from openai import OpenAI; c=OpenAI(api_key=os.environ['LLM_API_KEY'], base_url=os.environ['LLM_API_BASE']); r=c.chat.completions.create(model=os.getenv('LLM_MODEL','qwen3.5-flash'), messages=[{'role':'user','content':'只返回 OK'}], max_tokens=8); print(r.choices[0].message.content)"
```

期望输出：

```text
OK
```

如果这里成功，说明后端容器具备真实 Qwen 调用能力。

## 5. Research API

### 5.1 创建研究任务

Endpoint：

```http
POST /api/v1/research
```

请求体：

```json
{
  "query": "Analyze https://github.com/langchain-ai/langgraph and summarize its purpose with citations.",
  "output_length": "short",
  "max_revision": 1,
  "allow_web_after_rag_hit": true,
  "rag_group": null
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `query` | string | 研究问题，长度 5 到 2000 |
| `session_id` | string 或 null | 可选，指定会话 ID |
| `max_revision` | int | 最大反思修订轮数，1 到 5 |
| `user_confirmed` | bool | 高风险任务确认标记 |
| `allow_web_after_rag_hit` | bool | 内部 RAG 命中后是否仍联网 |
| `rag_group` | string 或 null | 内部知识库分组过滤 |
| `output_length` | string | `short`、`medium`、`long` |

响应示例：

```json
{
  "session_id": "c36ba8f7-c5ec-4844-9242-603ac2e4c5ec",
  "status": "running",
  "message": "Research task started. Connect to /api/v1/research/stream/{session_id} for updates.",
  "requires_confirmation": false,
  "output_length": "short",
  "budget": {
    "max_report_chars": 4000
  }
}
```

### 5.2 查询状态

```http
GET /api/v1/research/status/{session_id}
```

### 5.3 查询结果

```http
GET /api/v1/research/{session_id}
```

返回内容包括：

- `status`
- `report`
- `citations`
- `agent_trace`
- `created_at`
- `completed_at`

### 5.4 订阅 SSE 事件

```http
GET /api/v1/research/stream/{session_id}
```

常见事件：

| 事件 | 说明 |
| --- | --- |
| `connected` | SSE 连接成功 |
| `workflow_start` | 工作流开始 |
| `agent_start` | 某个 Agent 开始执行 |
| `tool_start` | 工具调用开始 |
| `tool_complete` | 工具调用完成 |
| `agent_complete` | Agent 执行完成 |
| `state_update` | 状态更新 |
| `report_citation` | 报告引用生成 |
| `report_chunk` | 报告正文分片 |
| `done` | 任务完成 |
| `workflow_error` | 工作流错误 |

## 6. PowerShell SDK 示例

### 6.1 创建任务并轮询结果

```powershell
$base = "http://localhost:5173/api/v1"

$body = @{
  query = "Analyze https://github.com/langchain-ai/langgraph and summarize its purpose with citations."
  output_length = "short"
  max_revision = 1
  allow_web_after_rag_hit = $true
} | ConvertTo-Json -Compress

$created = Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Uri "$base/research" `
  -Body $body

$sessionId = $created.session_id

do {
  Start-Sleep -Seconds 5
  $result = Invoke-RestMethod "$base/research/$sessionId"
  Write-Host "status=$($result.status)"
} while ($result.status -eq "running")

$result.report
$result.citations
```

### 6.2 监听 SSE

```powershell
curl.exe -sN "http://localhost:5173/api/v1/research/stream/$sessionId"
```

## 7. Python SDK 示例

依赖：

```powershell
pip install requests sseclient-py
```

同步创建任务并轮询：

```python
import time
import requests

BASE = "http://localhost:5173/api/v1"

payload = {
    "query": "Analyze https://github.com/langchain-ai/langgraph and summarize its purpose with citations.",
    "output_length": "short",
    "max_revision": 1,
    "allow_web_after_rag_hit": True,
}

created = requests.post(f"{BASE}/research", json=payload, timeout=30).json()
session_id = created["session_id"]
print("session_id =", session_id)

while True:
    result = requests.get(f"{BASE}/research/{session_id}", timeout=30).json()
    print("status =", result["status"])
    if result["status"] != "running":
        break
    time.sleep(5)

print(result["report"])
print(result["citations"])
```

SSE 监听：

```python
import json
import requests

BASE = "http://localhost:5173/api/v1"
session_id = "替换为你的 session_id"

with requests.get(f"{BASE}/research/stream/{session_id}", stream=True, timeout=None) as resp:
    for line in resp.iter_lines(decode_unicode=True):
        if line:
            print(line)
```

## 8. Node.js SDK 示例

Node 18+ 已内置 `fetch`。

创建任务并轮询：

```js
const BASE = "http://localhost:5173/api/v1";

const created = await fetch(`${BASE}/research`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: "Analyze https://github.com/langchain-ai/langgraph and summarize its purpose with citations.",
    output_length: "short",
    max_revision: 1,
    allow_web_after_rag_hit: true,
  }),
}).then((res) => res.json());

const sessionId = created.session_id;
console.log("session_id =", sessionId);

while (true) {
  const result = await fetch(`${BASE}/research/${sessionId}`).then((res) => res.json());
  console.log("status =", result.status);
  if (result.status !== "running") {
    console.log(result.report);
    console.log(result.citations);
    break;
  }
  await new Promise((resolve) => setTimeout(resolve, 5000));
}
```

SSE 监听可以使用浏览器原生 `EventSource`：

```js
const sessionId = "替换为你的 session_id";
const events = new EventSource(`/api/v1/research/stream/${sessionId}`);

events.addEventListener("agent_start", (event) => {
  console.log("agent_start", event.data);
});

events.addEventListener("report_chunk", (event) => {
  console.log("report_chunk", event.data);
});

events.addEventListener("done", (event) => {
  console.log("done", event.data);
  events.close();
});
```

## 9. LLM 配置 API

### 9.1 查看当前配置

```http
GET /api/v1/config/llm
```

PowerShell：

```powershell
Invoke-RestMethod http://localhost:5173/api/v1/config/llm
```

返回的 API Key 会被脱敏。

### 9.2 更新运行时配置

```http
POST /api/v1/config/llm
```

请求体：

```json
{
  "provider": "qwen",
  "model": "qwen3.5-flash",
  "api_key": "你的 DashScope API Key",
  "api_base": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
  "temperature": 0.7,
  "max_tokens": 8192,
  "fallback_provider": null,
  "fallback_model": null,
  "fallback_api_key": null
}
```

注意：这个接口会把配置保存到数据库，并覆盖环境变量配置。不要把真实 Key
写入文档、提交记录或截图。

## 10. GitHub Repository Evidence API

这个 API 是 GitHub 技术调研 Agent 的第一层能力：输入一个 GitHub 仓库
URL，返回结构化 evidence 和 deterministic scorecard。

Endpoint：

```http
POST /api/v1/github/repositories/analyze
```

请求体：

```json
{
  "repository_url": "https://github.com/langchain-ai/langgraph"
}
```

PowerShell：

```powershell
$body = @{
  repository_url = "https://github.com/langchain-ai/langgraph"
} | ConvertTo-Json -Compress

Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Uri "http://localhost:5173/api/v1/github/repositories/analyze" `
  -Body $body
```

返回内容包括：

- `identity`：规范化后的 `owner/repo`
- `metadata`：stars、forks、license、topics、默认分支等
- `readme`：README 内容和安装/使用/Docker/.env 信号
- `file_tree`：测试、CI、Docker、docs、examples、license 等文件树信号
- `dependencies`：依赖清单、包管理器、语言和框架信号
- `scorecard`：可复现性、项目深度、技术栈广度、可扩展性、工程质量、风险控制评分

如果返回 HTTP `403`：

```text
GitHub API rate limit or permission error.
```

通常是当前出口 IP 的 GitHub 匿名 API 额度不足。请在 `.env` 中配置
`GITHUB_TOKEN`，然后重建 API 容器：

```powershell
docker compose up -d --build api
```

## 11. 本次真实端到端验收记录

验收时间：2026-06-03

真实 Qwen SDK 最小调用：

```text
OK
```

端到端任务：

```text
Analyze the LangGraph repository at https://github.com/langchain-ai/langgraph.
Explain its core purpose, agent workflow value, and reproducibility signals
using source citations.
```

结果：

| 检查项 | 结果 |
| --- | --- |
| Session ID | `c36ba8f7-c5ec-4844-9242-603ac2e4c5ec` |
| 最终状态 | `completed` |
| 报告长度 | 4548 字符 |
| 引用数量 | 15 条 |
| 网络状态 | DashScope TLS 正常，OpenAI SDK 调用成功 |

## 12. 常见问题

### 12.1 curl 返回 401 是否失败？

不是。未带 Authorization Header 时返回 `401`，说明网络、代理、TLS 已经
打通。真实 SDK 调用会带 `LLM_API_KEY`。

### 12.2 仍然出现 TLS EOF 怎么办？

优先确认 FlClash 当前节点是否可访问 DashScope：

```powershell
docker compose exec -T api sh -lc "curl -v --proxy http://host.docker.internal:7890 https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models"
```

如果 CONNECT 成功但 TLS EOF，通常是当前节点出口对 DashScope 不可用。
切换 FlClash 节点后重试。

### 12.3 SSE queue full 是否影响最终结果？

如果客户端长时间不读取 SSE，后端可能打印：

```text
SSE queue full ... dropping event
```

这表示部分实时事件被丢弃，不代表任务失败。最终报告和引用仍会写入数据库。

### 12.4 为什么报告里出现英文？

当前 baseline 的报告 Agent prompt 更偏英文技术报告风格。后续改造成
GitHub 技术调研 Agent 时，可以把报告模板改为中文、结构化评分和证据表。
