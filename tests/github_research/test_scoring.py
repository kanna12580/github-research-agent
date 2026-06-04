from app.github_research.models import (
    DependencyManifestEvidence,
    EvidenceSource,
    GitHubEvidenceBundle,
    GitHubRepositoryIdentity,
    RepositoryFileTreeEvidence,
    RepositoryMetadataEvidence,
    RepositoryReadmeEvidence,
)
from app.github_research.scoring import score_repository


def test_score_repository_rewards_reproducible_engineering_signals():
    identity = GitHubRepositoryIdentity(
        owner="acme",
        repo="demo",
        html_url="https://github.com/acme/demo",
        api_url="https://api.github.com/repos/acme/demo",
        default_branch="main",
    )
    api_source = EvidenceSource(source_type="github_api", source_url=identity.api_url)
    raw_source = EvidenceSource(
        source_type="github_raw",
        source_url="https://raw.githubusercontent.com/acme/demo/main/README.md",
    )
    metadata = RepositoryMetadataEvidence(
        identity=identity,
        source=api_source,
        stars=500,
        forks=80,
        open_issues=5,
        license_name="MIT",
        default_branch="main",
    )
    readme = RepositoryReadmeEvidence(
        source=raw_source,
        text="install usage docker .env",
        has_install_section=True,
        has_usage_section=True,
        has_docker_reference=True,
        has_env_reference=True,
    )
    file_tree = RepositoryFileTreeEvidence(
        source=api_source,
        default_branch="main",
        files_sampled=120,
        directories=["app", "tests", "docs", "examples", "scripts", ".github"],
        key_files=["requirements.txt", "Dockerfile", ".github/workflows/ci.yml", "LICENSE"],
        has_tests=True,
        has_ci=True,
        has_docker=True,
        has_docs=True,
        has_examples=True,
        has_license_file=True,
        has_contributing=True,
    )
    dependencies = DependencyManifestEvidence(
        source=api_source,
        manifests=["requirements.txt", "Dockerfile"],
        package_managers=["pip", "docker"],
        languages=["Python", "Container"],
        frameworks=["Python", "Docker"],
        has_lockfile=True,
    )
    bundle = GitHubEvidenceBundle(
        identity=identity,
        metadata=metadata,
        readme=readme,
        file_tree=file_tree,
        dependencies=dependencies,
    )

    scorecard = score_repository(bundle)
    scores = {dimension.name: dimension.score for dimension in scorecard.dimensions}

    assert scores["reproducibility"] >= 8
    assert scores["engineering_quality"] >= 8
    assert scores["risk_control"] >= 8
