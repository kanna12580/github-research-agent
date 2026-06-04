"""Evaluation helpers for GitHub repository research demos."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.github_research.models import RepositoryComparison


class DemoEvaluationResult(BaseModel):
    """Compact quality metrics for a GitHub comparison demo run."""

    task_name: str
    repositories: list[str] = Field(default_factory=list)
    recommended_repository: str | None = None
    ranking_count: int = 0
    evidence_ref_count: int = 0
    citation_coverage: float = Field(ge=0.0, le=1.0)
    score_gap: float = 0.0
    recommendation_confidence: str = "low"
    checks: dict[str, bool] = Field(default_factory=dict)
    residual_risks: list[str] = Field(default_factory=list)


def evaluate_repository_comparison(
    comparison: RepositoryComparison | dict,
    *,
    task_name: str = "github_repository_comparison_demo",
    minimum_repositories: int = 2,
    refs_per_repository_target: int = 3,
) -> DemoEvaluationResult:
    """Evaluate whether a comparison result is demo-ready."""
    parsed = (
        comparison
        if isinstance(comparison, RepositoryComparison)
        else RepositoryComparison.model_validate(comparison)
    )
    ranking_count = len(parsed.ranking)
    evidence_ref_count = len(parsed.evidence_refs)
    citation_target = max(1, ranking_count * refs_per_repository_target)
    citation_coverage = round(min(1.0, evidence_ref_count / citation_target), 2)
    score_gap = 0.0
    if len(parsed.ranking) >= 2:
        score_gap = round(parsed.ranking[0].weighted_score - parsed.ranking[1].weighted_score, 2)

    checks = {
        "has_minimum_repositories": ranking_count >= minimum_repositories,
        "has_recommendation": bool(parsed.recommended_repository),
        "has_evidence_refs": evidence_ref_count > 0,
        "has_non_tied_leader": score_gap > 0 if ranking_count >= 2 else bool(parsed.recommended_repository),
        "has_citation_coverage": citation_coverage >= 0.5,
    }
    return DemoEvaluationResult(
        task_name=task_name,
        repositories=parsed.repositories,
        recommended_repository=parsed.recommended_repository,
        ranking_count=ranking_count,
        evidence_ref_count=evidence_ref_count,
        citation_coverage=citation_coverage,
        score_gap=score_gap,
        recommendation_confidence=_recommendation_confidence(score_gap, citation_coverage),
        checks=checks,
        residual_risks=_residual_risks(checks, score_gap),
    )


def _recommendation_confidence(score_gap: float, citation_coverage: float) -> str:
    if score_gap >= 1.0 and citation_coverage >= 0.7:
        return "high"
    if score_gap >= 0.4 and citation_coverage >= 0.5:
        return "medium"
    return "low"


def _residual_risks(checks: dict[str, bool], score_gap: float) -> list[str]:
    risks: list[str] = []
    if not checks["has_minimum_repositories"]:
        risks.append("需要至少两个仓库才能形成有效对比。")
    if not checks["has_recommendation"]:
        risks.append("排序结果没有给出推荐仓库。")
    if not checks["has_evidence_refs"]:
        risks.append("评分缺少证据引用，面试展示时说服力不足。")
    if not checks["has_non_tied_leader"] or score_gap < 0.4:
        risks.append("第一名与第二名分差较小，推荐结论需要人工解释。")
    if not checks["has_citation_coverage"]:
        risks.append("引用覆盖率偏低，需要补充 README、文件树、依赖或 CI 证据。")
    return risks
