from app.github_research.comparison import compare_repository_scorecards
from app.github_research.evaluation import evaluate_repository_comparison
from app.github_research.models import RepositoryScoreDimension, RepositoryScorecard


def _scorecard(full_name: str, reproducibility: int) -> RepositoryScorecard:
    return RepositoryScorecard(
        full_name=full_name,
        dimensions=[
            RepositoryScoreDimension(
                name="reproducibility",
                score=reproducibility,
                rationale="setup evidence",
                evidence_refs=[f"https://example.com/{full_name}/readme"],
            ),
            RepositoryScoreDimension(
                name="project_depth",
                score=8,
                rationale="depth evidence",
                evidence_refs=[f"https://example.com/{full_name}/tree"],
            ),
            RepositoryScoreDimension(
                name="extensibility",
                score=8,
                rationale="extension evidence",
                evidence_refs=[f"https://example.com/{full_name}/docs"],
            ),
            RepositoryScoreDimension(name="engineering_quality", score=7, rationale="quality", evidence_refs=[]),
            RepositoryScoreDimension(name="stack_breadth", score=7, rationale="stack", evidence_refs=[]),
            RepositoryScoreDimension(name="risk_control", score=8, rationale="risk", evidence_refs=[]),
        ],
    )


def test_evaluate_repository_comparison_returns_demo_metrics():
    comparison = compare_repository_scorecards([
        _scorecard("acme/strong", 9),
        _scorecard("acme/weak", 5),
    ])

    result = evaluate_repository_comparison(comparison)

    assert result.ranking_count == 2
    assert result.recommended_repository == "acme/strong"
    assert result.citation_coverage >= 0.5
    assert result.checks["has_recommendation"] is True
    assert result.checks["has_minimum_repositories"] is True
    assert result.recommendation_confidence in {"medium", "high"}
