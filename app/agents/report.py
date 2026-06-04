"""
Report Generator Agent: produces the final Markdown report with citations.

Generates a structured, well-formatted research report with source attribution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from app.config import get_settings
from app.guardrails import build_guardrail_decision, build_prompt_profile_message, get_research_budget
from app.graph.state import Citation, Evidence

if TYPE_CHECKING:
    from openai import OpenAI

logger = logging.getLogger(__name__)


class ReportAgent:
    """
    Converts the analysis and evidence into a polished Markdown research report.

    The report follows a standard business research format with:
    - Executive summary
    - Structured findings
    - Data analysis
    - Expert perspectives
    - Conclusions
    - References
    """

    SYSTEM_PROMPT = """You are an expert research report writer. Your job is to produce a polished, well-structured Markdown research report.

## Report Structure

```
# {Research Topic}

> Generated: {timestamp} | Research Depth: Comprehensive

## Executive Summary
{2-3 sentence core conclusion}

## 1. Background and Context
{Research background and scope}

## 2. Key Findings
### 2.1 [Finding Category 1]
{Detailed finding with evidence}

### 2.2 [Finding Category 2]
{Detailed finding with evidence}

## 3. Data and Statistics
{Key data points with sources}

## 4. Expert Perspectives
{Expert opinions and analyses}

## 5. Conclusions and Recommendations
{Actionable conclusions}

## References
{citation list}
```

## Formatting Rules

1. Use [citation:N] format for every factual claim
2. Use **bold** for key terms and important numbers
3. Use tables for data comparisons
4. Use blockquotes for expert quotes
5. Keep paragraphs focused (3-5 sentences max)
6. Use ## for main sections, ### for subsections

## Quality Standards

- Every factual claim must be cited
- Distinguish between facts (verified) and opinions (analyst interpretation)
- Include confidence levels for uncertain claims
- Provide actionable, specific conclusions
"""

    GITHUB_TECHNICAL_REPORT_PROMPT = """You are a senior software architect writing a Chinese technical research report for public GitHub repositories.

The report must be written in Chinese and must follow this exact Markdown structure:

```
# GitHub 开源项目技术调研报告：{repository_names}

## 1. 结论摘要
{Give a direct recommendation and 2-3 key reasons.}

## 2. 评分总览
| 仓库 | 可复现性 | 项目深度 | 技术栈广度 | 可扩展性 | 工程质量 | 风险控制 | 综合判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |

## 3. 可复现性与启动成本
{Discuss README setup quality, dependency manifests, lockfiles, Docker/env hints.}

## 4. 架构与 Agent 工作流深度
{Discuss whether the repository shows workflow orchestration, modular design, agent/tool roles, and reasoning depth.}

## 5. 技术栈广度
{Discuss languages, frameworks, package managers, containers, CI and integration breadth.}

## 6. 可扩展性
{Discuss docs, examples, contribution guide, modular directory layout, topics, license.}

## 7. 工程质量
{Discuss tests, CI, Docker, license files, activity metadata and maintainability.}

## 8. 风险点与补救建议
{List risks and concrete reproduction or extension actions.}

## 9. 面试展示建议
{Explain how to present this project on a resume/interview demo.}

## References
{citation list}
```

Rules:

1. Every factual statement must use [citation:N].
2. Scores must be grounded in the deterministic scorecard evidence.
3. Separate observed facts from your engineering judgment.
4. If evidence is missing, say what is missing instead of inventing it.
5. For multi-repository tasks, compare repositories explicitly in the table and final recommendation.
"""

    def __init__(self):
        settings = get_settings()
        self.model = settings.llm.model
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            from openai import OpenAI
            settings = get_settings()
            self._client = OpenAI(
                api_key=settings.llm.api_key,
                base_url=settings.llm.api_base or "https://api.openai.com/v1",
            )
        return self._client

    def generate(
        self,
        user_query: str,
        analysis: str,
        evidence_list: list[Evidence],
        reflection: dict | None,
    ) -> tuple[str, list[Citation]]:
        """Generate the final report without streaming callbacks."""
        return self.generate_stream(
            user_query=user_query,
            analysis=analysis,
            evidence_list=evidence_list,
            reflection=reflection,
        )

    def generate_stream(
        self,
        user_query: str,
        analysis: str,
        evidence_list: list[Evidence],
        reflection: dict | None,
        output_length: str | None = None,
        on_chunk: Callable[[str], None] | None = None,
        on_citation: Callable[[Citation], None] | None = None,
    ) -> tuple[str, list[Citation]]:
        """
        Generate the final research report.

        Args:
            user_query: Original research question
            analysis: Analyst's synthesized analysis
            evidence_list: All collected evidence
            reflection: Reflection quality result (optional)

        Returns:
            Tuple of (report_markdown, citations_list)
        """
        logger.info(f"Report: generating report for query: {user_query[:80]}")
        evidence_list = self._deduplicate_evidence(evidence_list)
        is_github_report = self._is_github_report(evidence_list)
        decision = build_guardrail_decision(user_query)
        budget = get_research_budget(output_length)
        repository_names = ", ".join(self._github_repository_names(evidence_list)) or user_query
        report_prompt = (
            self.GITHUB_TECHNICAL_REPORT_PROMPT.replace("{repository_names}", repository_names)
            if is_github_report
            else self.SYSTEM_PROMPT
        )
        system_prompt = f"{build_prompt_profile_message(decision, user_query)}\n\n{report_prompt}"
        system_prompt += (
            f"\n\n输出长度要求：{output_length or 'medium'}。"
            f"请优先控制在约 {budget['report_max_tokens']} tokens 内。"
            f"引用数量上限约 {budget['citation_max']} 条。"
        )
        if not evidence_list and not decision.reject_if_no_evidence:
            system_prompt += (
                "\n\n当前没有外部证据。允许回答简单事实问题，但必须明确说明“未检索验证”。"
                "不要生成虚假的 [citation:N]，不要声称已检索来源。"
            )

        citations = self._build_citations(evidence_list)
        for citation in citations:
            if on_citation:
                on_citation(citation)

        # Build reference list
        ref_list = self._build_reference_list(citations)

        # Format evidence for prompt
        formatted_evidence = (
            self._format_github_evidence(evidence_list, citations)
            if is_github_report
            else self._format_evidence(evidence_list, citations)
        )

        # Confidence note if reflection is available
        confidence_note = ""
        if reflection:
            conf = reflection.get("overall_confidence", 0.5)
            if conf < 0.7:
                confidence_note = f"\n\n**Quality Note**: This report has moderate confidence ({conf:.0%}). Some claims may need verification."

        # Generate citation range note
        citation_note = self._citation_range_note(len(citations))

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""Research Topic: {user_query}

Analyst's Analysis:
{analysis}

Evidence Sources:
{formatted_evidence}

{citation_note}

{confidence_note}

Generate the complete research report in Markdown format. Include all sections specified in the system prompt.
Make sure every factual claim has a [citation:N] reference."""
            },
        ]

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=budget["report_max_tokens"],
                stream=True,
            )
            chunks: list[str] = []
            for event in stream:
                if not event.choices:
                    continue
                delta = event.choices[0].delta.content or ""
                if not delta:
                    continue
                chunks.append(delta)
                if on_chunk:
                    on_chunk(delta)

            content = "".join(chunks).strip()
            if not content:
                content = self._fallback_report(user_query, evidence_list, citations)
                self._emit_fallback_chunks(content, on_chunk)

            # Append references section if not present
            if "## References" not in content and "## 参考" not in content:
                references_block = f"\n\n---\n\n## References\n\n{ref_list}"
                content += references_block
                if on_chunk:
                    on_chunk(references_block)

            logger.info(f"Report: generated {len(content)} chars, {len(citations)} citations")
            return content, citations

        except Exception as e:
            logger.error(f"Report generation error: {e}")
            fallback = self._fallback_report(user_query, evidence_list, citations)
            self._emit_fallback_chunks(fallback, on_chunk)
            return fallback, citations

    def _deduplicate_evidence(self, evidence_list: list[Evidence]) -> list[Evidence]:
        """Keep one evidence item per source URL across revision passes."""
        unique: list[Evidence] = []
        seen_keys: set[tuple[str, str, str]] = set()
        for evidence in evidence_list:
            source_url = (evidence.source_url or "").strip()
            url_key = source_url.casefold()
            title_key = (evidence.source_title or "").strip().casefold()
            source_type_key = evidence.source_type
            dedupe_key = (url_key, title_key, source_type_key)
            if url_key and dedupe_key in seen_keys:
                continue
            if url_key:
                seen_keys.add(dedupe_key)
            unique.append(evidence)
        return unique

    def _is_github_report(self, evidence_list: list[Evidence]) -> bool:
        """Return True when the evidence set contains GitHub repository evidence."""
        return any(ev.source_type == "github_repository" or ev.agent_type.value == "github" for ev in evidence_list)

    def _github_repository_names(self, evidence_list: list[Evidence]) -> list[str]:
        """Infer repository names from GitHub evidence titles/content."""
        names: list[str] = []
        seen: set[str] = set()
        markers = (
            " repository metadata",
            " deterministic scorecard",
            " README",
            " file tree",
            " dependency manifests",
        )
        for ev in evidence_list:
            if ev.source_type != "github_repository":
                continue
            candidate = ev.source_title or ""
            for marker in markers:
                if marker in candidate:
                    candidate = candidate.split(marker, 1)[0]
                    break
            if "/" not in candidate and " for " in ev.content:
                candidate = ev.content.split(" for ", 1)[1].split(":", 1)[0].strip()
            if "/" in candidate and candidate not in seen:
                seen.add(candidate)
                names.append(candidate)
        return names

    def _format_github_evidence(self, evidence_list: list[Evidence], citations: list[Citation]) -> str:
        """Format GitHub evidence with an explicit technical report lens."""
        lines = [
            "GitHub repository technical evidence. Use these items to fill the Chinese technical research template.",
            "",
        ]
        for i, (ev, citation) in enumerate(zip(evidence_list[:30], citations[:30]), 1):
            source = f"{ev.source_title or 'Unknown'} - {ev.source_url}" if ev.source_url else (ev.source_title or "Unknown")
            dimension_hint = self._github_dimension_hint(ev)
            lines.append(
                f"[{i}] {source}\n"
                f"Type: {ev.source_type} | Dimension hint: {dimension_hint}\n"
                f"{ev.content[:1200]}"
            )
        return "\n\n".join(lines)

    def _github_dimension_hint(self, evidence: Evidence) -> str:
        title = (evidence.source_title or "").lower()
        content = evidence.content.lower()
        if "comparison ranking" in title or "comparison ranking" in content:
            return "多仓库排序、推荐选择、优先级判断"
        if "scorecard" in title or "scorecard" in content:
            return "评分总览、风险控制、综合判断"
        if "readme" in title:
            return "可复现性、启动成本、使用说明"
        if "file tree" in title:
            return "架构深度、工程质量、可扩展性"
        if "dependency" in title:
            return "技术栈广度、依赖与包管理"
        if "metadata" in title:
            return "项目成熟度、维护活跃度、风险"
        return "通用仓库证据"

    def _build_citations(self, evidence_list: list[Evidence]) -> list[Citation]:
        """Build a stable citation list from collected evidence."""
        citations: list[Citation] = []
        for i, ev in enumerate(evidence_list[:30], 1):
            citation_text = getattr(ev, "citation", None)
            citations.append(Citation(
                citation_id=f"citation:{i}",
                source_url=ev.source_url or "",
                source_title=ev.source_title or f"Source {i}",
                source_type=ev.source_type,
                extracted_evidence=(citation_text[:300] if citation_text else ev.content[:300]),
                relevance_score=0.5,
            ))
        return citations

    def _emit_fallback_chunks(
        self,
        content: str,
        on_chunk: Callable[[str], None] | None,
        chunk_size: int = 800,
    ) -> None:
        """Emit chunk events for fallback/non-streamed content."""
        if not on_chunk:
            return
        for start in range(0, len(content), chunk_size):
            on_chunk(content[start:start + chunk_size])

    def _format_evidence(self, evidence_list: list[Evidence], citations: list[Citation]) -> str:
        """Format evidence with citation numbers."""
        lines = []
        for i, (ev, citation) in enumerate(zip(evidence_list[:20], citations[:20]), 1):
            source = f"{ev.source_title or 'Unknown'} - {ev.source_url}" if ev.source_url else (ev.source_title or "Unknown")
            lines.append(f"[{i}] {source}\nType: {ev.source_type}\n{ev.content[:300]}")
        return "\n\n".join(lines)

    def _build_reference_list(self, citations: list[Citation]) -> str:
        """Build the references section."""
        if not citations:
            return "No citations available."

        refs = []
        for i, c in enumerate(citations, 1):
            title = c.source_title or "Untitled"
            url = c.source_url or ""
            ref_str = f"[{i}] **{title}**"
            if url:
                ref_str += f" - {url}"
            refs.append(ref_str)

        return "\n".join(refs)

    def _citation_range_note(self, n: int) -> str:
        """Generate a note about available citations."""
        if n == 0:
            return "No evidence sources available."
        return f"Available citations: {n} sources (use [citation:1] through [citation:{n}] to reference them)"

    def _fallback_report(
        self,
        user_query: str,
        evidence_list: list[Evidence],
        citations: list[Citation],
    ) -> str:
        """Generate a minimal fallback report when LLM fails."""
        if self._is_github_report(evidence_list):
            return self._github_fallback_report(user_query, evidence_list, citations)

        lines = [f"# {user_query}", "", "## 摘要", ""]
        for i, ev in enumerate(evidence_list[:10], 1):
            lines.append(f"### 来源 {i}")
            lines.append(ev.content[:500])
            lines.append("")
        if citations:
            lines.append("## 参考资料")
            for i, c in enumerate(citations[:10], 1):
                title = c.source_title or "Untitled"
                url = c.source_url or ""
                lines.append(f"[{i}] {title} - {url}")
        return "\n".join(lines)

    def _github_fallback_report(
        self,
        user_query: str,
        evidence_list: list[Evidence],
        citations: list[Citation],
    ) -> str:
        """Generate a deterministic GitHub technical research report skeleton."""
        repo_names = self._github_repository_names(evidence_list)
        title_target = ", ".join(repo_names) if repo_names else user_query
        scorecard_items = [
            (idx, ev)
            for idx, ev in enumerate(evidence_list[:30], 1)
            if "scorecard" in (ev.source_title or "").lower() or "repository scorecard" in ev.content.lower()
        ]
        readme_items = [
            (idx, ev)
            for idx, ev in enumerate(evidence_list[:30], 1)
            if "readme" in (ev.source_title or "").lower()
        ]
        file_tree_items = [
            (idx, ev)
            for idx, ev in enumerate(evidence_list[:30], 1)
            if "file tree" in (ev.source_title or "").lower()
        ]
        dependency_items = [
            (idx, ev)
            for idx, ev in enumerate(evidence_list[:30], 1)
            if "dependency" in (ev.source_title or "").lower()
        ]
        metadata_items = [
            (idx, ev)
            for idx, ev in enumerate(evidence_list[:30], 1)
            if "metadata" in (ev.source_title or "").lower()
        ]

        lines = [
            f"# GitHub 开源项目技术调研报告：{title_target}",
            "",
            "## 1. 结论摘要",
            "",
            self._github_section_summary(scorecard_items or metadata_items, "当前结论主要依据仓库元数据、README、文件树、依赖清单和确定性评分卡。"),
            "",
            "## 2. 评分总览",
            "",
            "| 仓库 | 可复现性 | 项目深度 | 技术栈广度 | 可扩展性 | 工程质量 | 风险控制 | 综合判断 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
            *self._github_score_table_rows(scorecard_items, repo_names),
            "",
            "## 3. 可复现性与启动成本",
            "",
            self._github_section_summary(readme_items + dependency_items, "需要重点检查 README 安装说明、使用示例、环境变量、依赖清单、锁文件和 Docker 信号。"),
            "",
            "## 4. 架构与 Agent 工作流深度",
            "",
            self._github_section_summary(file_tree_items, "需要结合目录结构、核心模块、测试目录和文档目录判断项目是否具备可解释的 Agent 工作流深度。"),
            "",
            "## 5. 技术栈广度",
            "",
            self._github_section_summary(dependency_items, "技术栈广度主要由语言、包管理器、框架、容器和 CI 线索支撑。"),
            "",
            "## 6. 可扩展性",
            "",
            self._github_section_summary(file_tree_items + metadata_items, "扩展性应关注文档、示例、贡献指南、许可证、主题标签和模块化目录。"),
            "",
            "## 7. 工程质量",
            "",
            self._github_section_summary(file_tree_items + metadata_items, "工程质量应关注测试、CI、Docker、许可证文件、最近活跃度和 issue 风险。"),
            "",
            "## 8. 风险点与补救建议",
            "",
            "- 若 README 缺少完整启动步骤，应补充本地启动、Docker 启动和 API Key 配置说明。",
            "- 若缺少测试或 CI，应优先补充核心评分逻辑、API 合约和端到端任务测试。",
            "- 若依赖锁文件或容器配置不足，应补充可复现环境，降低面试演示时的环境风险。",
            "",
            "## 9. 面试展示建议",
            "",
            "- 展示从 GitHub URL 输入、结构化证据采集、确定性评分、引用校验到报告生成的完整链路。",
            "- 强调评分不是直接让 LLM 主观判断，而是先采集可追溯证据，再由 LLM 负责归纳表达。",
            "- 准备一个单仓库调研和一个多仓库对比案例，体现产品化和工程化扩展能力。",
        ]

        if citations:
            lines.extend(["", "---", "", "## References", "", self._build_reference_list(citations)])

        return "\n".join(lines)

    def _github_section_summary(self, indexed_items: list[tuple[int, Evidence]], default_text: str) -> str:
        if not indexed_items:
            return f"{default_text} 当前证据不足，需要后续采集补齐。"
        bullets = []
        for citation_index, evidence in indexed_items[:4]:
            bullets.append(f"- {evidence.content[:350]} [citation:{citation_index}]")
        return "\n".join(bullets)

    def _github_score_table_rows(
        self,
        scorecard_items: list[tuple[int, Evidence]],
        repo_names: list[str],
    ) -> list[str]:
        if not scorecard_items:
            target = repo_names[0] if repo_names else "待识别仓库"
            return [f"| {target} | 待评分 | 待评分 | 待评分 | 待评分 | 待评分 | 待评分 | 需要补充 scorecard 证据 |"]

        rows = []
        for citation_index, evidence in scorecard_items:
            repo_name = self._github_repository_names([evidence])
            scores = self._extract_scorecard_scores(evidence.content)
            rows.append(
                "| {repo} | {repro} | {depth} | {stack} | {ext} | {quality} | {risk} | 基于确定性评分卡，需结合 README 和工程证据解释 [citation:{citation}] |".format(
                    repo=repo_name[0] if repo_name else evidence.source_title or "GitHub repository",
                    repro=scores.get("reproducibility", "待评分"),
                    depth=scores.get("project_depth", "待评分"),
                    stack=scores.get("stack_breadth", "待评分"),
                    ext=scores.get("extensibility", "待评分"),
                    quality=scores.get("engineering_quality", "待评分"),
                    risk=scores.get("risk_control", "待评分"),
                    citation=citation_index,
                )
            )
        return rows

    def _extract_scorecard_scores(self, content: str) -> dict[str, str]:
        scores: dict[str, str] = {}
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped.startswith("- ") or ":" not in stripped:
                continue
            name, rest = stripped[2:].split(":", 1)
            score = rest.strip().split(".", 1)[0].strip()
            if "/10" in score:
                scores[name.strip()] = score
        return scores
