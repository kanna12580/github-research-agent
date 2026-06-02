# 本地启动与排查指南

## 目标

本文档用于在 Windows + Docker Desktop 环境中本地启动当前 DeepIntel
复现项目，并排查 DashScope / Qwen API 在容器内访问失败的问题。

当前项目默认使用：

- 后端：FastAPI，容器端口 `8000`
- 前端：React + Nginx，宿主机端口 `5173`
- 数据库：PostgreSQL + pgvector，宿主机端口 `5433`
- 缓存：Redis，宿主机端口 `6379`
- 模型：`qwen3.5-flash`
- DashScope OpenAI 兼容接口：
  `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`

阿里云官方文档说明：千问模型支持 OpenAI 兼容接口，不同地域使用不同
Base URL；新加坡地域对应 `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`。

## 1. 前置条件

请先确认本机已安装：

1. Docker Desktop，并确保 Docker Engine 正在运行。
2. Git。
3. 一个可用的 DashScope API Key。
4. 如果需要代理访问外网，确认代理软件已开启“允许局域网连接”。

在 PowerShell 中确认 Docker：

```powershell
docker version
docker compose version
```

如果 `docker` 命令找不到，但 Docker Desktop 已安装，可临时使用：

```powershell
$dockerBin='C:\Program Files\Docker\Docker\resources\bin'
$env:Path="$dockerBin;$env:Path"
docker version
```

## 2. 配置环境变量

复制环境模板：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少配置以下项：

```env
LLM_PROVIDER=qwen
LLM_MODEL=qwen3.5-flash
LLM_API_KEY=你的 DashScope API Key
LLM_API_BASE=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

如果你的外网必须经过本机代理，并且代理 HTTP/Mixed 端口是 `7890`，
再加入：

```env
DOCKER_HTTP_PROXY=http://host.docker.internal:7890
DOCKER_HTTPS_PROXY=http://host.docker.internal:7890
DOCKER_NO_PROXY=db,redis,localhost,127.0.0.1
```

注意：

- `.env` 已被忽略，不要提交。
- 新加坡地域和北京地域的 API Key 可能不是同一个，请使用与地域匹配的
  Key。
- 本项目使用 OpenAI SDK 的 `chat.completions.create`，所以应配置
  OpenAI 兼容 Base URL，不是 DashScope 原生
  `/api/v1/services/aigc/...` 地址。

## 3. 启动服务

构建并启动完整服务：

```powershell
docker compose up -d --build
```

查看容器状态：

```powershell
docker compose ps
```

期望看到：

- `deepintel-db` 为 healthy
- `deepintel-redis` 为 running
- `deepintel-api` 为 running
- `deepintel-frontend` 为 running

## 4. 基础健康检查

后端健康检查：

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
Invoke-RestMethod http://localhost:8000/api/v1/ready
```

前端代理检查：

```powershell
Invoke-WebRequest http://localhost:5173 -UseBasicParsing
Invoke-RestMethod http://localhost:5173/api/v1/health
```

浏览器打开：

```text
http://localhost:5173
```

## 5. 在容器内检查关键环境变量

不要打印 API Key 明文。只检查是否存在：

```powershell
docker compose exec -T api python -c "import os; print('LLM_API_BASE=' + str(os.getenv('LLM_API_BASE'))); print('MODEL=' + str(os.getenv('LLM_MODEL'))); print('KEY_SET=' + str(bool(os.getenv('LLM_API_KEY')))); print('HTTP_PROXY=' + str(os.getenv('HTTP_PROXY'))); print('HTTPS_PROXY=' + str(os.getenv('HTTPS_PROXY'))); print('NO_PROXY=' + str(os.getenv('NO_PROXY')))"
```

如果 `HTTP_PROXY` 或 `HTTPS_PROXY` 为空，说明 `.env` 中的
`DOCKER_HTTP_PROXY` / `DOCKER_HTTPS_PROXY` 没有传入容器。

修改 `.env` 后需要重建或重启 API 容器：

```powershell
docker compose up -d --build api
```

## 6. 测试 DashScope 连通性

### 6.1 宿主机测试

先在宿主机上测试代理端口是否监听：

```powershell
netstat -ano | Select-String ':7890'
```

测试宿主机是否能访问 DashScope：

```powershell
curl.exe -sS -o NUL -w "direct:%{http_code} err=%{errormsg}`n" `
  https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models
```

如果需要代理：

```powershell
curl.exe -sS --proxy http://127.0.0.1:7890 -o NUL `
  -w "proxy:%{http_code} err=%{errormsg}`n" `
  https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models
```

未带认证时返回 `401` 通常是好信号，表示网络已经打通，只是没有传 Key。
如果返回 `000`、TLS 错误、连接超时，则是网络或代理问题。

### 6.2 容器内测试

测试容器直接访问：

```powershell
docker compose exec -T api python -c "import httpx; print(httpx.get('https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models', timeout=20).status_code)"
```

测试容器通过宿主机代理访问：

```powershell
docker compose exec -T api python -c "import httpx; proxy='http://host.docker.internal:7890'; url='https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models'; print(httpx.Client(proxy=proxy, timeout=20).get(url).status_code)"
```

测试真实 OpenAI 兼容调用：

```powershell
docker compose exec -T api python -c "import os; from openai import OpenAI; c=OpenAI(api_key=os.environ['LLM_API_KEY'], base_url=os.environ['LLM_API_BASE']); r=c.chat.completions.create(model=os.getenv('LLM_MODEL','qwen3.5-flash'), messages=[{'role':'user','content':'只返回 OK'}], max_tokens=8); print(r.choices[0].message.content)"
```

如果这一步成功，后端工作流就具备真实 Qwen 调用条件。

## 7. TLS EOF 的可能原因

当前观察到的错误是：

```text
SSL: UNEXPECTED_EOF_WHILE_READING
openai.APIConnectionError: Connection error.
```

它发生在认证之前的 TLS 握手阶段，通常不是 API Key 错误。API Key 错误
更常见的是 HTTP `401` 或 `403`。

常见原因：

1. 容器没有真正走到可用代理出口。
   - 现象：容器直连和代理都失败。
   - 检查：容器内 `HTTP_PROXY` / `HTTPS_PROXY` 是否存在。

2. 代理开启了本机监听，但没有允许 Docker 容器访问。
   - Docker 访问宿主机应使用 `host.docker.internal`，不是 `127.0.0.1`。
   - 代理软件需要开启“允许局域网连接”。

3. 代理端口类型不匹配。
   - 有些客户端的 `7890` 是 mixed 端口，有些只支持 HTTP 或 SOCKS。
   - OpenAI SDK / httpx 默认支持 HTTP 代理；SOCKS 代理需要额外依赖。

4. 代理出口节点对 DashScope 域名的 TLS 连接被中断。
   - 现象：TCP 能连上代理，但 HTTPS 握手 EOF。
   - 可尝试切换代理节点，或在代理规则中把
     `dashscope-intl.aliyuncs.com` 显式走代理。

5. 代理软件对 Docker 流量、SNI 或证书链处理异常。
   - 可尝试关闭 HTTPS 解密、MITM、证书注入等功能。
   - 如果宿主机代理 curl 也失败，优先排查代理客户端，而不是项目代码。

6. 地域与 Key 不匹配。
   - 新加坡 Base URL 应配新加坡地域可用的 Key。
   - 这种情况通常表现为认证错误，不太像 TLS EOF，但仍应确认。

## 8. 运行测试

```powershell
docker compose run --rm --no-deps `
  -v 'E:\PycharmProjects\agent_wsl\tests:/app/tests' `
  -v 'E:\PycharmProjects\agent_wsl\metrics:/app/metrics' `
  api pytest -q tests/agents/test_agents.py tests/graph/test_graph.py `
    tests/integration/test_workflow.py tests/rag/test_rag.py
```

当前预期结果：

```text
78 passed, 1 warning
```

这个 warning 是 LangGraph 上游弃用提示，不影响当前复现。

## 9. 提交一次研究任务

通过 API：

```powershell
$body = @{
  query = 'Analyze https://github.com/langchain-ai/langgraph and summarize its purpose with citations.'
  output_length = 'short'
  max_revision = 1
  allow_web_after_rag_hit = $true
} | ConvertTo-Json -Compress

$created = Invoke-RestMethod -Method Post `
  -ContentType 'application/json' `
  -Uri 'http://localhost:5173/api/v1/research' `
  -Body $body

$created.session_id
```

监听 SSE：

```powershell
curl.exe -sN "http://localhost:5173/api/v1/research/stream/$($created.session_id)"
```

查看最终结果：

```powershell
Invoke-RestMethod "http://localhost:5173/api/v1/research/$($created.session_id)"
```

## 10. 查看日志

```powershell
docker compose logs --tail 200 api
```

重点关注：

- `Connection error`：LLM API 连接失败。
- `SSL: UNEXPECTED_EOF_WHILE_READING`：TLS 握手被提前断开。
- `Report generated`：报告生成完成。
- `knowledge base is empty; skipping embedding model initialization`：
  空知识库时已跳过本地 embedding 模型加载。

## 11. 停止服务

停止容器但保留数据卷：

```powershell
docker compose down
```

如果要清理数据库和缓存卷：

```powershell
docker compose down -v
```

清理数据卷会删除本地数据库数据，请谨慎使用。
