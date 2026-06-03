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
from app.main import create_app


class StubGitHubCollector:
    async def collect(self, repository: str) -> GitHubEvidenceBundle:
        if repository == "bad-url":
            raise ValueError("Not a supported GitHub repository URL")

        identity = GitHubRepositoryIdentity(
            owner="acme",
            repo="demo",
            html_url="https://github.com/acme/demo",
            api_url="https://api.github.com/repos/acme/demo",
            default_branch="main",
        )
        source = EvidenceSource(source_type="github_api", source_url=identity.api_url)
        readme_source = EvidenceSource(
            source_type="github_raw",
            source_url="https://raw.githubusercontent.com/acme/demo/main/README.md",
        )
        bundle = GitHubEvidenceBundle(
            identity=identity,
            metadata=RepositoryMetadataEvidence(
                identity=identity,
                source=source,
                stars=10,
                license_name="MIT",
                default_branch="main",
            ),
            readme=RepositoryReadmeEvidence(
                source=readme_source,
                text="install usage",
                has_install_section=True,
                has_usage_section=True,
            ),
            file_tree=RepositoryFileTreeEvidence(
                source=source,
                default_branch="main",
                files_sampled=4,
                key_files=["README.md", "requirements.txt"],
                has_tests=True,
            ),
            dependencies=DependencyManifestEvidence(
                source=source,
                manifests=["requirements.txt"],
                package_managers=["pip"],
                languages=["Python"],
            ),
        )
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
    assert data["metadata"]["stars"] == 10
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
