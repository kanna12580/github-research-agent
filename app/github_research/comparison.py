"""Deterministic comparison and ranking for GitHub repository scorecards."""

from __future__ import annotations

from app.github_research.models import RankedRepository, RepositoryComparison, RepositoryScorecard


RESUME_PROJECT_WEIGHTS: dict[str, float] = {
    "reproducibility": 0.25,
    "project_depth": 0.20,
    "extensibility": 0.20,
    "engineering_quality": 0.15,
    "stack_breadth": 0.15,
    "risk_control": 0.05,
}


DIMENSION_LABELS: dict[str, str] = {
    "reproducibility": "可复现性",
    "project_depth": "项目深度",
    "stack_breadth": "技术栈广度",
    "extensibility": "可扩展性",
    "engineering_quality": "工程质量",
    "risk_control": "风险控制",
}


def compare_repository_scorecards(scorecards: list[RepositoryScorecard | dict]) -> RepositoryComparison:
    """Rank repositories for resume/interview reproduction suitability."""
    parsed = [
        item if isinstance(item, RepositoryScorecard) else RepositoryScorecard.model_validate(item)
        for item in scorecards
    ]
    ranked = [_rank_candidate(scorecard) for scorecard in parsed]
    ranked.sort(key=lambda item: (item.weighted_score, item.average_score, item.total_score), reverse=True)

    final_ranking: list[RankedRepository] = []
    for index, item in enumerate(ranked, start=1):
        final_ranking.append(item.model_copy(update={
            "rank": index,
            "recommendation": _recommendation(index, item),
        }))

    recommended = final_ranking[0].full_name if final_ranking else None
    return RepositoryComparison(
        repositories=[scorecard.full_name for scorecard in parsed],
        ranking=final_ranking,
        recommended_repository=recommended,
        summary=_comparison_summary(final_ranking),
        evidence_refs=_scorecard_refs(parsed),
    )


def comparison_to_evidence_text(comparison: RepositoryComparison) -> str:
    """Render comparison as compact evidence text for downstream report generation."""
    if not comparison.ranking:
        return "No repository comparison ranking was generated."

    lines = [
        "GitHub repository comparison ranking for resume/interview reproduction suitability.",
        f"Recommended repository: {comparison.recommended_repository or 'N/A'}.",
        comparison.summary,
        "",
        "| Rank | Repository | Weighted | Average | Reproducibility | Depth | Stack | Extensibility | Quality | Risk | Recommendation |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in comparison.ranking:
        scores = item.dimension_scores
        lines.append(
            "| {rank} | {repo} | {weighted:.2f} | {average:.2f} | {repro} | {depth} | {stack} | {ext} | {quality} | {risk} | {rec} |".format(
                rank=item.rank,
                repo=item.full_name,
                weighted=item.weighted_score,
                average=item.average_score,
                repro=scores.get("reproducibility", 0),
                depth=scores.get("project_depth", 0),
                stack=scores.get("stack_breadth", 0),
                ext=scores.get("extensibility", 0),
                quality=scores.get("engineering_quality", 0),
                risk=scores.get("risk_control", 0),
                rec=item.recommendation,
            )
        )
        if item.strengths:
            lines.append(f"Strengths for {item.full_name}: {', '.join(item.strengths)}.")
        if item.weaknesses:
            lines.append(f"Weaknesses for {item.full_name}: {', '.join(item.weaknesses)}.")
    if comparison.evidence_refs:
        lines.extend(["", "Evidence references:", *comparison.evidence_refs[:12]])
    return "\n".join(lines)


def _rank_candidate(scorecard: RepositoryScorecard) -> RankedRepository:
    scores = {dimension.name: dimension.score for dimension in scorecard.dimensions}
    weighted_score = round(sum(
        scores.get(name, 0) * weight
        for name, weight in RESUME_PROJECT_WEIGHTS.items()
    ), 2)
    return RankedRepository(
        rank=0,
        full_name=scorecard.full_name,
        weighted_score=weighted_score,
        average_score=scorecard.average_score,
        total_score=scorecard.total_score,
        dimension_scores=scores,
        strengths=_dimension_names(scores, minimum=8, reverse=True)[:3],
        weaknesses=_dimension_names(scores, maximum=5)[:3],
    )


def _dimension_names(
    scores: dict[str, int],
    *,
    minimum: int | None = None,
    maximum: int | None = None,
    reverse: bool = False,
) -> list[str]:
    items = sorted(scores.items(), key=lambda item: item[1], reverse=reverse)
    result: list[str] = []
    for name, score in items:
        if minimum is not None and score < minimum:
            continue
        if maximum is not None and score > maximum:
            continue
        result.append(f"{DIMENSION_LABELS.get(name, name)}({score}/10)")
    return result


def _recommendation(rank: int, item: RankedRepository) -> str:
    if rank == 1:
        return "优先推荐复刻/改造"
    if item.weighted_score >= 7:
        return "可作为备选或对比样例"
    if item.weighted_score >= 5:
        return "适合作为风险对照样例"
    return "不建议作为主复刻项目"


def _comparison_summary(ranking: list[RankedRepository]) -> str:
    if not ranking:
        return "No repositories were available for comparison."
    leader = ranking[0]
    if len(ranking) == 1:
        return f"{leader.full_name} is the only repository available for ranking."
    runner_up = ranking[1]
    return (
        f"{leader.full_name} ranks first with weighted score {leader.weighted_score:.2f}/10, "
        f"ahead of {runner_up.full_name} at {runner_up.weighted_score:.2f}/10. "
        "The ranking emphasizes reproducibility, project depth and extensibility for interview-ready reproduction."
    )


def _scorecard_refs(scorecards: list[RepositoryScorecard]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for scorecard in scorecards:
        for dimension in scorecard.dimensions:
            for ref in dimension.evidence_refs:
                if ref and ref not in seen:
                    seen.add(ref)
                    refs.append(ref)
    return refs
