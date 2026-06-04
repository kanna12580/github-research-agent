"""Structured evidence models for GitHub repository technical research."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class GitHubRepositoryIdentity(BaseModel):
    """Canonical identity for a public GitHub repository."""

    owner: str
    repo: str
    html_url: str
    api_url: str
    default_branch: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


class EvidenceSource(BaseModel):
    """Source provenance attached to collected GitHub evidence."""

    source_type: Literal["github_api", "github_raw", "github_html"]
    source_url: str
    collected_at: datetime = Field(default_factory=datetime.utcnow)


class RepositoryMetadataEvidence(BaseModel):
    """Repository metadata collected from GitHub REST API."""

    identity: GitHubRepositoryIdentity
    source: EvidenceSource
    description: str | None = None
    homepage: str | None = None
    language: str | None = None
    topics: list[str] = Field(default_factory=list)
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    open_issues: int = 0
    license_name: str | None = None
    archived: bool = False
    disabled: bool = False
    private: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    pushed_at: datetime | None = None
    default_branch: str | None = None


class RepositoryReadmeEvidence(BaseModel):
    """README content and setup hints."""

    source: EvidenceSource
    path: str | None = None
    text: str = ""
    truncated: bool = False
    has_install_section: bool = False
    has_usage_section: bool = False
    has_quickstart_section: bool = False
    has_docker_reference: bool = False
    has_env_reference: bool = False


class RepositoryFileTreeEvidence(BaseModel):
    """Repository file tree and important engineering signals."""

    source: EvidenceSource
    default_branch: str
    files_sampled: int = 0
    directories: list[str] = Field(default_factory=list)
    key_files: list[str] = Field(default_factory=list)
    has_tests: bool = False
    has_ci: bool = False
    has_docker: bool = False
    has_docs: bool = False
    has_examples: bool = False
    has_license_file: bool = False
    has_contributing: bool = False


class DependencyManifestEvidence(BaseModel):
    """Detected dependency manifests and inferred technology stack."""

    source: EvidenceSource
    manifests: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    has_lockfile: bool = False


class RepositoryScoreDimension(BaseModel):
    """Single deterministic score with evidence references."""

    name: str
    score: int = Field(ge=0, le=10)
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)


class RepositoryScorecard(BaseModel):
    """Deterministic technical scorecard derived from structured evidence."""

    full_name: str
    dimensions: list[RepositoryScoreDimension]

    @property
    def total_score(self) -> int:
        return sum(item.score for item in self.dimensions)

    @property
    def average_score(self) -> float:
        if not self.dimensions:
            return 0.0
        return round(self.total_score / len(self.dimensions), 2)


class RankedRepository(BaseModel):
    """Repository ranking result for multi-repository technical comparison."""

    rank: int
    full_name: str
    weighted_score: float = Field(ge=0.0, le=10.0)
    average_score: float = Field(ge=0.0, le=10.0)
    total_score: int = 0
    dimension_scores: dict[str, int] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendation: str = ""


class RepositoryComparison(BaseModel):
    """Deterministic comparison and ranking for multiple GitHub repositories."""

    repositories: list[str] = Field(default_factory=list)
    ranking: list[RankedRepository] = Field(default_factory=list)
    recommended_repository: str | None = None
    summary: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class GitHubEvidenceBundle(BaseModel):
    """Complete GitHub evidence package for one repository."""

    identity: GitHubRepositoryIdentity
    metadata: RepositoryMetadataEvidence
    readme: RepositoryReadmeEvidence | None = None
    file_tree: RepositoryFileTreeEvidence | None = None
    dependencies: DependencyManifestEvidence | None = None
    scorecard: RepositoryScorecard | None = None
    raw_errors: list[str] = Field(default_factory=list)

    def provenance_urls(self) -> list[str]:
        urls: list[str] = [self.metadata.source.source_url]
        for item in (self.readme, self.file_tree, self.dependencies):
            if item and item.source.source_url not in urls:
                urls.append(item.source.source_url)
        return urls

    def as_report_context(self) -> dict[str, Any]:
        """Return compact context suitable for report generation prompts."""
        return self.model_dump(mode="json")
