from app.github_research.comparison import compare_repository_scorecards, comparison_to_evidence_text
from app.github_research.models import RepositoryScoreDimension, RepositoryScorecard


def _scorecard(full_name: str, scores: dict[str, int]) -> RepositoryScorecard:
    return RepositoryScorecard(
        full_name=full_name,
        dimensions=[
            RepositoryScoreDimension(
                name=name,
                score=score,
                rationale=f"{name} rationale",
                evidence_refs=[f"https://example.com/{full_name}/{name}"],
            )
            for name, score in scores.items()
        ],
    )


def test_compare_repository_scorecards_ranks_for_resume_reproduction():
    stronger = _scorecard("acme/strong", {
        "reproducibility": 9,
        "project_depth": 8,
        "stack_breadth": 7,
        "extensibility": 9,
        "engineering_quality": 8,
        "risk_control": 8,
    })
    weaker = _scorecard("acme/weak", {
        "reproducibility": 4,
        "project_depth": 7,
        "stack_breadth": 9,
        "extensibility": 4,
        "engineering_quality": 5,
        "risk_control": 6,
    })

    comparison = compare_repository_scorecards([weaker, stronger])

    assert comparison.recommended_repository == "acme/strong"
    assert comparison.ranking[0].rank == 1
    assert comparison.ranking[0].full_name == "acme/strong"
    assert comparison.ranking[0].weighted_score > comparison.ranking[1].weighted_score
    assert comparison.ranking[0].recommendation == "优先推荐复刻/改造"
    assert comparison.evidence_refs


def test_comparison_to_evidence_text_includes_ranking_table():
    comparison = compare_repository_scorecards([
        _scorecard("acme/a", {
            "reproducibility": 8,
            "project_depth": 8,
            "stack_breadth": 8,
            "extensibility": 8,
            "engineering_quality": 8,
            "risk_control": 8,
        }),
        _scorecard("acme/b", {
            "reproducibility": 6,
            "project_depth": 6,
            "stack_breadth": 6,
            "extensibility": 6,
            "engineering_quality": 6,
            "risk_control": 6,
        }),
    ])

    text = comparison_to_evidence_text(comparison)

    assert "Recommended repository: acme/a" in text
    assert "| Rank | Repository | Weighted |" in text
    assert "| 1 | acme/a |" in text
