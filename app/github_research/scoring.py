"""Deterministic scoring for GitHub repository evidence."""

from __future__ import annotations

from app.github_research.models import (
    GitHubEvidenceBundle,
    RepositoryScoreDimension,
    RepositoryScorecard,
)


def score_repository(bundle: GitHubEvidenceBundle) -> RepositoryScorecard:
    """Generate a deterministic scorecard from structured evidence."""
    return RepositoryScorecard(
        full_name=bundle.identity.full_name,
        dimensions=[
            _score_reproducibility(bundle),
            _score_project_depth(bundle),
            _score_stack_breadth(bundle),
            _score_extensibility(bundle),
            _score_engineering_quality(bundle),
            _score_risk(bundle),
        ],
    )


def _score_reproducibility(bundle: GitHubEvidenceBundle) -> RepositoryScoreDimension:
    score = 0
    refs: list[str] = []
    readme = bundle.readme
    deps = bundle.dependencies
    tree = bundle.file_tree
    if readme:
        refs.append(readme.source.source_url)
        score += 2
        if readme.has_install_section:
            score += 2
        if readme.has_usage_section or readme.has_quickstart_section:
            score += 2
        if readme.has_env_reference:
            score += 1
    if deps and deps.manifests:
        refs.append(deps.source.source_url)
        score += 2
        if deps.has_lockfile:
            score += 1
    if tree and tree.has_docker:
        refs.append(tree.source.source_url)
        score += 1
    return RepositoryScoreDimension(
        name="reproducibility",
        score=min(score, 10),
        rationale="README setup guidance, dependency manifests, lockfiles and Docker signals are used as reproducibility evidence.",
        evidence_refs=_unique(refs),
    )


def _score_project_depth(bundle: GitHubEvidenceBundle) -> RepositoryScoreDimension:
    score = 0
    refs = [bundle.metadata.source.source_url]
    tree = bundle.file_tree
    if bundle.metadata.stars >= 1000:
        score += 2
    elif bundle.metadata.stars >= 100:
        score += 1
    if bundle.metadata.forks >= 100:
        score += 1
    if tree:
        refs.append(tree.source.source_url)
        if tree.files_sampled >= 100:
            score += 2
        elif tree.files_sampled >= 30:
            score += 1
        if tree.has_docs:
            score += 2
        if tree.has_examples:
            score += 1
        if len(tree.directories) >= 8:
            score += 2
    return RepositoryScoreDimension(
        name="project_depth",
        score=min(score, 10),
        rationale="Repository size, documentation, examples, directory breadth and adoption signals are used as depth evidence.",
        evidence_refs=_unique(refs),
    )


def _score_stack_breadth(bundle: GitHubEvidenceBundle) -> RepositoryScoreDimension:
    deps = bundle.dependencies
    refs = [deps.source.source_url] if deps else []
    language_count = len(deps.languages) if deps else 0
    manager_count = len(deps.package_managers) if deps else 0
    framework_count = len(deps.frameworks) if deps else 0
    score = min(10, language_count * 2 + manager_count + framework_count)
    return RepositoryScoreDimension(
        name="stack_breadth",
        score=score,
        rationale="Detected languages, package managers and framework/container manifests are used as stack breadth evidence.",
        evidence_refs=_unique(refs),
    )


def _score_extensibility(bundle: GitHubEvidenceBundle) -> RepositoryScoreDimension:
    score = 0
    refs: list[str] = []
    tree = bundle.file_tree
    if tree:
        refs.append(tree.source.source_url)
        if tree.has_docs:
            score += 2
        if tree.has_examples:
            score += 2
        if tree.has_contributing:
            score += 2
        if len(tree.directories) >= 6:
            score += 2
    if bundle.metadata.topics:
        refs.append(bundle.metadata.source.source_url)
        score += 1
    if bundle.metadata.license_name:
        score += 1
    return RepositoryScoreDimension(
        name="extensibility",
        score=min(score, 10),
        rationale="Docs, examples, contribution guidance, modular directory layout, topics and license are used as extensibility evidence.",
        evidence_refs=_unique(refs),
    )


def _score_engineering_quality(bundle: GitHubEvidenceBundle) -> RepositoryScoreDimension:
    score = 0
    refs: list[str] = []
    tree = bundle.file_tree
    if tree:
        refs.append(tree.source.source_url)
        if tree.has_tests:
            score += 3
        if tree.has_ci:
            score += 3
        if tree.has_docker:
            score += 1
        if tree.has_license_file:
            score += 1
    if bundle.metadata.pushed_at:
        refs.append(bundle.metadata.source.source_url)
        score += 1
    if bundle.metadata.open_issues >= 0:
        score += 1
    return RepositoryScoreDimension(
        name="engineering_quality",
        score=min(score, 10),
        rationale="Tests, CI, containerization, license files and activity metadata are used as engineering quality evidence.",
        evidence_refs=_unique(refs),
    )


def _score_risk(bundle: GitHubEvidenceBundle) -> RepositoryScoreDimension:
    score = 10
    refs = [bundle.metadata.source.source_url]
    if bundle.metadata.archived or bundle.metadata.disabled:
        score -= 5
    if not bundle.metadata.license_name:
        score -= 2
    if bundle.metadata.open_issues > max(100, bundle.metadata.stars // 20):
        score -= 1
    if not bundle.readme:
        score -= 2
    if bundle.file_tree and not bundle.file_tree.has_tests:
        refs.append(bundle.file_tree.source.source_url)
        score -= 1
    return RepositoryScoreDimension(
        name="risk_control",
        score=max(score, 0),
        rationale="Archived/disabled status, license availability, issue volume, README and tests are used as risk-control evidence.",
        evidence_refs=_unique(refs),
    )


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
