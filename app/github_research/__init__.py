"""GitHub repository research domain models and collectors."""

from app.github_research.collector import GitHubRepositoryCollector
from app.github_research.models import (
    DependencyManifestEvidence,
    GitHubEvidenceBundle,
    GitHubRepositoryIdentity,
    RepositoryFileTreeEvidence,
    RepositoryMetadataEvidence,
    RepositoryReadmeEvidence,
    RepositoryScorecard,
)
from app.github_research.scoring import score_repository
from app.github_research.url_parser import parse_github_repository_url

__all__ = [
    "DependencyManifestEvidence",
    "GitHubEvidenceBundle",
    "GitHubRepositoryCollector",
    "GitHubRepositoryIdentity",
    "RepositoryFileTreeEvidence",
    "RepositoryMetadataEvidence",
    "RepositoryReadmeEvidence",
    "RepositoryScorecard",
    "parse_github_repository_url",
    "score_repository",
]
