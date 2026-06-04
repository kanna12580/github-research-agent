from fastapi.testclient import TestClient

from app.api.github_research import get_github_collector
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
from app.github_research.url_parser import parse_github_repository_url
from app.main import create_app


class StubGitHubCollector:
    async def collect(self, repository: str) -> GitHubEvidenceBundle:
        if repository == "bad-url":
            raise ValueError("Not a supported GitHub repository URL")

        identity = parse_github_repository_url(repository)
        identity.default_branch = "main"
        source = EvidenceSource(source_type="github_api", source_url=identity.api_url)
        readme_source = EvidenceSource(
            source_type="github_raw",
            source_url=f"https://raw.githubusercontent.com/{identity.full_name}/main/README.md",
        )
        is_strong = "strong" in identity.repo or identity.repo == "demo"
        bundle = GitHubEvidenceBundle(
            identity=identity,
            metadata=RepositoryMetadataEvidence(
                identity=identity,
                source=source,
                stars=100 if is_strong else 10,
                forks=20 if is_strong else 2,
                license_name="MIT",
                default_branch="main",
            ),
            readme=RepositoryReadmeEvidence(
                source=readme_source,
                text="install usage",
                has_install_section=True,
                has_usage_section=is_strong,
            ),
            file_tree=RepositoryFileTreeEvidence(
                source=source,
                default_branch="main",
                files_sampled=120 if is_strong else 10,
                directories=["app", "tests", "docs", "examples", "scripts", "api"] if is_strong else ["src"],
                key_files=["README.md", "requirements.txt", "Dockerfile", ".github/workflows/ci.yml"],
                has_tests=is_strong,
                has_ci=is_strong,
                has_docker=is_strong,
                has_docs=is_strong,
                has_examples=is_strong,
                has_license_file=True,
            ),
            dependencies=DependencyManifestEvidence(
                source=source,
                manifests=["requirements.txt"],
                package_managers=["pip"],
                languages=["Python"],
                frameworks=["Python"],
            ),
        )
        bundle.scorecard = score_repository(bundle)
        return bundle


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_github_collector] = lambda: StubGitHubCollector()
    return TestClient(app)


def test_analyze_github_repository_returns_evidence_bundle():
    client = _client()

    response = client.post(
        "/api/v1/github/repositories/analyze",
        json={"repository_url": "https://github.com/acme/demo"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["identity"]["owner"] == "acme"
    assert data["identity"]["repo"] == "demo"
    assert data["metadata"]["stars"] == 100
    assert data["readme"]["has_install_section"] is True
    assert data["dependencies"]["languages"] == ["Python"]


def test_analyze_github_repository_rejects_invalid_url():
    client = _client()

    response = client.post(
        "/api/v1/github/repositories/analyze",
        json={"repository_url": "bad-url"},
    )

    assert response.status_code == 400
    assert "Not a supported GitHub repository URL" in response.json()["detail"]


def test_compare_github_repositories_returns_ranking_and_evaluation():
    client = _client()

    response = client.post(
        "/api/v1/github/repositories/compare",
        json={
            "repository_urls": [
                "https://github.com/acme/weak",
                "https://github.com/acme/strong",
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["repositories"] == ["acme/weak", "acme/strong"]
    assert data["comparison"]["recommended_repository"] == "acme/strong"
    assert data["comparison"]["ranking"][0]["rank"] == 1
    assert data["evaluation"]["checks"]["has_recommendation"] is True
    assert data["evaluation"]["ranking_count"] == 2
