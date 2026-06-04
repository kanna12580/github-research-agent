# Demo 样例与评测闭环

本文档固定一组 GitHub 开源 Agent 项目对比任务，用于面试演示、功能回归和质量评测。

## Demo 任务

任务名称：Agent 开源项目复刻优先级对比

仓库：

- https://github.com/wblxr408/DeepIntel
- https://github.com/PavithraNagineni/multi-agent-research-system
- https://github.com/tarun7r/deep-research-agent

研究 Prompt：

```text
请对以下 GitHub 开源项目做技术调研、对比排序，并推荐最适合作为简历/面试复刻项目的仓库：https://github.com/wblxr408/DeepIntel https://github.com/PavithraNagineni/multi-agent-research-system https://github.com/tarun7r/deep-research-agent
```

任务配置文件：[github_agent_comparison_demo.json](demo/github_agent_comparison_demo.json)

## 前端演示步骤

1. 启动项目：

```powershell
docker compose up -d
```

2. 打开前端：

```text
http://localhost:5173
```

3. 在首页的「GitHub 开源项目调研」面板点击「使用三项目对比示例」。

4. 点击「生成 GitHub 调研任务」，确认主输入框已生成对比排序 prompt。

5. 点击「研究」开始任务。

6. 观察演示点：

- Agent trace 出现 `GitHub` 和 `排序` 阶段。
- Tool trace 出现 `github_repository_collect`。
- GitHub 技术调研看板显示识别仓库数、GitHub 工具事件数、推荐仓库和 ranking 表。
- 最终报告包含评分总览、可复现性、架构深度、技术栈、风险和面试展示建议。
- 报告中的事实性结论带有 `[citation:N]`。

## API 快速评测

这个接口不调用 LLM，适合快速验证 GitHub 证据采集、确定性评分、排序和评测指标：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/github/repositories/compare `
  -H "Content-Type: application/json" `
  -d "{\"repository_urls\":[\"https://github.com/wblxr408/DeepIntel\",\"https://github.com/PavithraNagineni/multi-agent-research-system\",\"https://github.com/tarun7r/deep-research-agent\"]}"
```

返回结果重点看：

- `comparison.recommended_repository`
- `comparison.ranking`
- `evaluation.citation_coverage`
- `evaluation.recommendation_confidence`
- `evaluation.checks`
- `evaluation.residual_risks`

## 评测指标

当前闭环使用轻量确定性评测，不依赖 LLM 主观判断：

| 指标 | 目的 | 通过信号 |
| --- | --- | --- |
| `ranking_count` | 是否完成多仓库排序 | 至少 2，Demo 任务应为 3 |
| `recommended_repository` | 是否给出推荐仓库 | 非空 |
| `citation_coverage` | 评分证据覆盖度 | 建议不低于 0.5 |
| `score_gap` | 第一名与第二名差距 | 差距越大，推荐越稳定 |
| `recommendation_confidence` | 推荐置信度 | medium 或 high 更适合演示 |
| `residual_risks` | 剩余风险提示 | 越少越好 |

## 面试讲解要点

- 这个 Demo 不是让 LLM 直接判断哪个项目好，而是先采集 GitHub 元数据、README、文件树、依赖、CI/Docker/测试等结构化证据。
- 排序由确定性 scorecard 和加权规则完成，权重面向“适合简历/面试复刻项目”。
- LLM 的职责是把证据和排序解释成可读报告，不负责凭空改分或改排序。
- 前端实时展示 Agent trace、工具调用、GitHub ranking 和最终报告，能说明系统具备可观测性。

## 已知限制

- GitHub 未配置 `GITHUB_TOKEN` 时可能触发公开 API 限流。
- 仓库 README 或文件树缺失时，评分会更保守。
- 当前 Demo 只固定一组样例；后续可以扩展成小型评测集，比较多组任务的一致性、耗时和 token 成本。
