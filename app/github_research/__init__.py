"""GitHub repository research domain models and collectors."""

from app.github_research.collector import GitHubRepositoryCollector
from app.github_research.comparison import compare_repository_scorecards, comparison_to_evidence_text
from app.github_research.evaluation import DemoEvaluationResult, evaluate_repository_comparison
from app.github_research.models import (
    DependencyManifestEvidence,
    GitHubEvidenceBundle,
    GitHubRepositoryIdentity,
    RepositoryFileTreeEvidence,
    RepositoryMetadataEvidence,
    RepositoryReadmeEvidence,
    RepositoryComparison,
    RepositoryScorecard,
)
from app.github_research.scoring import score_repository
from app.github_research.url_parser import parse_github_repository_url

__all__ = [
    "DependencyManifestEvidence",
    "GitHubEvidenceBundle",
    "GitHubRepositoryCollector",
    "GitHubRepositoryIdentity",
    "DemoEvaluationResult",
    "RepositoryComparison",
    "RepositoryFileTreeEvidence",
    "RepositoryMetadataEvidence",
    "RepositoryReadmeEvidence",
    "RepositoryScorecard",
    "compare_repository_scorecards",
    "comparison_to_evidence_text",
    "evaluate_repository_comparison",
    "parse_github_repository_url",
    "score_repository",
]
