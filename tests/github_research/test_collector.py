import base64

import httpx
import pytest

from app.github_research.collector import GitHubRepositoryCollector


def _json_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=data)


@pytest.mark.asyncio
async def test_collector_builds_structured_evidence_bundle():
    readme = """# Demo

## Installation
Use Docker and copy `.env.example`.

## Usage
Run the quickstart command.
"""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://api.github.com/repos/acme/demo":
            return _json_response(
                {
                    "description": "Demo agent project",
                    "homepage": "https://example.com",
                    "language": "Python",
                    "topics": ["agents", "research"],
                    "stargazers_count": 1200,
                    "forks_count": 150,
                    "watchers_count": 1200,
                    "open_issues_count": 12,
                    "license": {"spdx_id": "MIT"},
                    "archived": False,
                    "disabled": False,
                    "private": False,
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2026-06-01T00:00:00Z",
                    "pushed_at": "2026-06-01T00:00:00Z",
                    "default_branch": "main",
                }
            )
        if url == "https://api.github.com/repos/acme/demo/readme":
            return _json_response(
                {
                    "path": "README.md",
                    "encoding": "base64",
                    "content": base64.b64encode(readme.encode()).decode(),
                    "download_url": "https://raw.githubusercontent.com/acme/demo/main/README.md",
                }
            )
        if url == "https://api.github.com/repos/acme/demo/git/trees/main?recursive=1":
            return _json_response(
                {
                    "tree": [
                        {"type": "blob", "path": "README.md"},
                        {"type": "blob", "path": "requirements.txt"},
                        {"type": "blob", "path": "pyproject.toml"},
                        {"type": "blob", "path": "Dockerfile"},
                        {"type": "blob", "path": ".github/workflows/ci.yml"},
                        {"type": "blob", "path": "tests/test_app.py"},
                        {"type": "blob", "path": "docs/architecture.md"},
                        {"type": "blob", "path": "examples/basic.py"},
                        {"type": "blob", "path": "LICENSE"},
                        {"type": "blob", "path": "CONTRIBUTING.md"},
                    ]
                }
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        collector = GitHubRepositoryCollector(client=client)
        bundle = await collector.collect("https://github.com/acme/demo")

    assert bundle.identity.full_name == "acme/demo"
    assert bundle.metadata.stars == 1200
    assert bundle.metadata.license_name == "MIT"
    assert bundle.readme is not None
    assert bundle.readme.has_install_section is True
    assert bundle.readme.has_usage_section is True
    assert bundle.readme.has_docker_reference is True
    assert bundle.readme.has_env_reference is True
    assert bundle.file_tree is not None
    assert bundle.file_tree.has_tests is True
    assert bundle.file_tree.has_ci is True
    assert bundle.file_tree.has_docker is True
    assert bundle.file_tree.has_docs is True
    assert bundle.file_tree.has_examples is True
    assert bundle.dependencies is not None
    assert "requirements.txt" in bundle.dependencies.manifests
    assert "Python" in bundle.dependencies.languages
    assert "docker" in bundle.dependencies.package_managers
    assert bundle.scorecard is not None
    assert bundle.scorecard.full_name == "acme/demo"
    assert bundle.scorecard.average_score > 0


@pytest.mark.asyncio
async def test_collector_allows_missing_readme_and_tree():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://api.github.com/repos/acme/minimal":
            return _json_response(
                {
                    "description": None,
                    "language": None,
                    "topics": [],
                    "stargazers_count": 0,
                    "forks_count": 0,
                    "watchers_count": 0,
                    "open_issues_count": 0,
                    "license": None,
                    "archived": False,
                    "disabled": False,
                    "private": False,
                    "default_branch": "main",
                }
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        collector = GitHubRepositoryCollector(client=client)
        bundle = await collector.collect("acme/minimal")

    assert bundle.readme is None
    assert bundle.file_tree is None
    assert bundle.dependencies is None
    assert bundle.scorecard is not None
    assert bundle.scorecard.average_score >= 0
