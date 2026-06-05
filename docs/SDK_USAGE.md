# 本地启动与 SDK 调用文档

本文档面向本地开发、复现实验、Demo 演示和后续二次开发，说明如何启动服务、配置模型与 GitHub Token，并通过 API/SSE 调用 GitHub Repository Research Agent。

## 1. 环境准备

已验证环境：

- Python 3.11
- Docker Desktop
- Node.js/npm
- PowerShell
- DashScope/Qwen OpenAI-compatible API

默认模型配置：

```text
LLM_PROVIDER=qwen
LLM_MODEL=qwen3.5-flash
LLM_API_BASE=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

如果容器内访问 DashScope 需要代理，请确认本机代理允许局域网连接，并在 `.env` 中配置：

```env
HTTP_PROXY=http://host.docker.internal:7890
HTTPS_PROXY=http://host.docker.internal:7890
NO_PROXY=db,redis,localhost,127.0.0.1
```

## 2. 配置 `.env`

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

建议配置 GitHub Token，用于提高公开仓库采集的 rate limit：

```env
GITHUB_TOKEN=你的 GitHub Personal Access Token
```

注意：

- 不要提交 `.env`。
- GitHub Token 对公开仓库采集是可选项，但真实 Demo 推荐配置。
- 修改 `.env` 后，已有容器不会自动读取新变量，需要重建或重启容器。

## 3. 启动服务

首次或修改镜像后：

```powershell
docker compose build api
docker compose up -d
```

只修改 `.env` 后，推荐重建 API 容器：

```powershell
docker compose up -d --force-recreate api
```

访问地址：

```text
后端 API: http://localhost:8000
前端 UI:  http://localhost:5173
```

## 4. 网络连通性验证

验证后端健康：

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
```

验证 DashScope 代理链路：

```powershell
docker compose exec -T api sh -lc "curl -v --proxy http://host.docker.internal:7890 https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models"
```

如果返回 `401` 且提示缺少 API Key，说明 TLS、代理和服务端连接已经打通；这是未带 Authorization Header 的正常结果。

## 5. 快速 GitHub 对比 API

该接口走确定性采集、评分、排序和评测，不调用 LLM，适合快速回归：

```powershell
$body = @{
  repository_urls = @(
    "https://github.com/wblxr408/DeepIntel",
    "https://github.com/PavithraNagineni/multi-agent-research-system",
    "https://github.com/tarun7r/deep-research-agent"
  )
} | ConvertTo-Json

$result = Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/github/repositories/compare" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body

$result.comparison.recommended_repository
$result.evaluation
```

预期重点：

- `comparison.recommended_repository` 不为空
- `comparison.ranking` 包含 3 个仓库
- `evaluation.citation_coverage` 大于 0
- `evaluation.recommendation_confidence` 为 `medium` 或 `high`

## 6. 创建真实研究任务

通过后端创建一次完整 Agent 研究任务：

```powershell
$prompt = "Compare these GitHub repositories for resume/interview reproduction suitability and generate a Chinese technical research report with ranking, evidence-backed scores, risks, and interview demo advice: https://github.com/wblxr408/DeepIntel https://github.com/PavithraNagineni/multi-agent-research-system https://github.com/tarun7r/deep-research-agent"

$body = @{
  query = $prompt
  output_length = "medium"
  allow_web_after_rag_hit = $false
  rag_group = $null
} | ConvertTo-Json

$taskResponse = Invoke-WebRequest `
  -UseBasicParsing `
  -Uri "http://localhost:8000/api/v1/research" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))

$task = [System.Text.Encoding]::UTF8.GetString($taskResponse.RawContentStream.ToArray()) | ConvertFrom-Json

$task.session_id
```

轮询结果：

```powershell
$sid = "替换为上一步 session_id"

do {
  Start-Sleep -Seconds 10
  $resultResponse = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:8000/api/v1/research/$sid" -Method Get
  $result = [System.Text.Encoding]::UTF8.GetString($resultResponse.RawContentStream.ToArray()) | ConvertFrom-Json
  "status=$($result.status), citations=$($result.citations.Count)"
} while ($result.status -eq "running")

$result.report
```

保存报告：

```powershell
Set-Content -Path "docs/demo/sample_report.md" -Value $result.report -Encoding UTF8
$result.citations | ConvertTo-Json -Depth 12 | Set-Content -Path "docs/demo/sample_citations.json" -Encoding UTF8
```

如果使用 Windows PowerShell 5，优先使用上面的 `Invoke-WebRequest + UTF8.GetString(...)` 写法；不要直接用 `Invoke-RestMethod` 保存中文报告，否则在缺少 charset 的旧响应或代理场景下可能把 UTF-8 内容误解码成本地 ANSI，导致样例文件乱码。PowerShell 7 对 UTF-8 的默认处理更稳定。

## 7. 查询历史研究任务

列出最近研究任务：

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/research/sessions?limit=20" -Method Get
```

返回字段：

- `session_id`：研究任务 ID
- `query`：用户输入
- `status`：`running`、`completed`、`failed` 等状态
- `created_at` / `updated_at` / `completed_at`：时间信息
- `citation_count`：引用数量
- `report_preview`：报告预览片段

恢复某个报告：

```powershell
$sid = "替换为历史中的 session_id"
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/research/$sid" -Method Get
```

前端“最近研究”面板优先使用后端历史接口；如果后端暂时不可用，会使用浏览器 `localStorage` 中的本地历史作为演示兜底。

## 8. SSE 事件流

前端使用 SSE 展示 Agent 实时进度。也可以用 PowerShell 观察事件流：

```powershell
$sid = "替换为真实 session_id"
curl.exe -N "http://localhost:8000/api/v1/research/$sid/stream"
```

可以关注的事件：

- 任务状态变化
- GitHub 仓库识别
- GitHub 工具采集
- scorecard 与 ranking
- report 生成完成

## 9. 前端演示

打开：

```text
http://localhost:5173
```

推荐演示流程：

1. 点击“使用三项目对比示例”。
2. 点击“生成 GitHub 调研任务”。
3. 点击“研究”。
4. 展示 Agent trace、GitHub ranking、推荐仓库和最终报告。
5. 刷新页面后，在“最近研究”面板点击历史记录，验证报告恢复能力。
6. 打开 [Demo 样例与评测闭环](DEMO_EVALUATION.md) 中保存的样例报告与截图。

## 10. 常见问题

### 修改 `.env` 后 Token 没生效

使用：

```powershell
docker compose up -d --force-recreate api
```

如果只是 `docker compose restart api`，容器通常不会重新读取新的环境变量。

### DashScope TLS EOF

优先检查：

- 代理软件是否允许局域网连接
- 容器是否使用 `host.docker.internal:7890`
- `HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY` 是否正确
- DashScope base URL 是否使用国际站地址

能通过代理访问 `/compatible-mode/v1/models` 并拿到 `401`，通常说明网络链路已经通。

### 报告出现乱码

尽量使用 ASCII prompt 或确保终端使用 UTF-8。PowerShell 中中文字面量在某些环境下可能被错误编码。真实报告如出现 UTF-8/Latin-1 mojibake，可以重新请求或做编码修复后保存。
