"""Public GitHub repository evidence collector."""

from __future__ import annotations

import base64
import os
from datetime import datetime
from typing import Any

import httpx

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


README_SECTION_KEYWORDS = {
    "install": ("install", "installation", "setup", "getting started", "安装", "部署"),
    "usage": ("usage", "example", "examples", "quickstart", "使用", "示例"),
    "quickstart": ("quickstart", "quick start", "getting started", "快速开始"),
}

MANIFEST_LANGUAGE_HINTS = {
    "requirements.txt": ("Python", "pip"),
    "pyproject.toml": ("Python", "pip/poetry"),
    "poetry.lock": ("Python", "poetry"),
    "Pipfile": ("Python", "pipenv"),
    "package.json": ("JavaScript/TypeScript", "npm"),
    "package-lock.json": ("JavaScript/TypeScript", "npm"),
    "pnpm-lock.yaml": ("JavaScript/TypeScript", "pnpm"),
    "yarn.lock": ("JavaScript/TypeScript", "yarn"),
    "go.mod": ("Go", "go"),
    "Cargo.toml": ("Rust", "cargo"),
    "pom.xml": ("Java", "maven"),
    "build.gradle": ("Java/Kotlin", "gradle"),
    "composer.json": ("PHP", "composer"),
    "Gemfile": ("Ruby", "bundler"),
    "Dockerfile": ("Container", "docker"),
    "docker-compose.yml": ("Container", "docker compose"),
    "docker-compose.yaml": ("Container", "docker compose"),
}

LOCKFILES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
}


class GitHubRepositoryCollector:
    """Collect structured evidence for public GitHub repositories."""

    def __init__(
        self,
        token: str | None = None,
        timeout: float = 20.0,
        max_tree_files: int = 800,
        readme_max_chars: int = 20000,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN") or ""
        self.timeout = timeout
        self.max_tree_files = max_tree_files
        self.readme_max_chars = readme_max_chars
        self._client = client

    async def collect(self, repository: str) -> GitHubEvidenceBundle:
        """Collect repository metadata, README, file tree, dependency signals and scores."""
        identity = parse_github_repository_url(repository)
        async with self._get_client() as client:
            metadata = await self._collect_metadata(client, identity)
            identity.default_branch = metadata.default_branch
            readme = await self._collect_readme(client, identity, metadata.default_branch)
            file_tree = await self._collect_file_tree(client, identity, metadata.default_branch)
            dependencies = self._collect_dependency_manifests(file_tree)

        bundle = GitHubEvidenceBundle(
            identity=identity,
            metadata=metadata,
            readme=readme,
            file_tree=file_tree,
            dependencies=dependencies,
        )
        bundle.scorecard = score_repository(bundle)
        return bundle

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return _BorrowedAsyncClient(self._client)

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "DeepIntel-GitHub-Research-Agent",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return httpx.AsyncClient(headers=headers, timeout=self.timeout, follow_redirects=True)

    async def _collect_metadata(
        self,
        client: httpx.AsyncClient,
        identity: GitHubRepositoryIdentity,
    ) -> RepositoryMetadataEvidence:
        response = await client.get(identity.api_url)
        response.raise_for_status()
        data = response.json()
        default_branch = data.get("default_branch")
        return RepositoryMetadataEvidence(
            identity=identity.model_copy(update={"default_branch": default_branch}),
            source=EvidenceSource(source_type="github_api", source_url=identity.api_url),
            description=data.get("description"),
            homepage=data.get("homepage"),
            language=data.get("language"),
            topics=list(data.get("topics") or []),
            stars=int(data.get("stargazers_count") or 0),
            forks=int(data.get("forks_count") or 0),
            watchers=int(data.get("watchers_count") or 0),
            open_issues=int(data.get("open_issues_count") or 0),
            license_name=(data.get("license") or {}).get("spdx_id") or (data.get("license") or {}).get("name"),
            archived=bool(data.get("archived")),
            disabled=bool(data.get("disabled")),
            private=bool(data.get("private")),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
            pushed_at=_parse_datetime(data.get("pushed_at")),
            default_branch=default_branch,
        )

    async def _collect_readme(
        self,
        client: httpx.AsyncClient,
        identity: GitHubRepositoryIdentity,
        default_branch: str | None,
    ) -> RepositoryReadmeEvidence | None:
        response = await client.get(f"{identity.api_url}/readme")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        text = _decode_github_content(data)
        truncated = len(text) > self.readme_max_chars
        if truncated:
            text = text[: self.readme_max_chars]

        lower_text = text.lower()
        raw_url = data.get("download_url") or _raw_url(identity, default_branch, data.get("path") or "README.md")
        return RepositoryReadmeEvidence(
            source=EvidenceSource(source_type="github_raw", source_url=raw_url),
            path=data.get("path"),
            text=text,
            truncated=truncated,
            has_install_section=_contains_any(lower_text, README_SECTION_KEYWORDS["install"]),
            has_usage_section=_contains_any(lower_text, README_SECTION_KEYWORDS["usage"]),
            has_quickstart_section=_contains_any(lower_text, README_SECTION_KEYWORDS["quickstart"]),
            has_docker_reference="docker" in lower_text,
            has_env_reference=".env" in lower_text or "environment variable" in lower_text,
        )

    async def _collect_file_tree(
        self,
        client: httpx.AsyncClient,
        identity: GitHubRepositoryIdentity,
        default_branch: str | None,
    ) -> RepositoryFileTreeEvidence | None:
        if not default_branch:
            return None
        tree_url = f"{identity.api_url}/git/trees/{default_branch}?recursive=1"
        response = await client.get(tree_url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        tree = data.get("tree") or []
        paths = [item.get("path", "") for item in tree if item.get("type") == "blob" and item.get("path")]
        directories = sorted({path.split("/", 1)[0] for path in paths if "/" in path})
        sampled_paths = paths[: self.max_tree_files]
        key_files = sorted(path for path in sampled_paths if _is_key_file(path))
        lower_paths = [path.lower() for path in sampled_paths]

        return RepositoryFileTreeEvidence(
            source=EvidenceSource(source_type="github_api", source_url=tree_url),
            default_branch=default_branch,
            files_sampled=len(sampled_paths),
            directories=directories[:100],
            key_files=key_files,
            has_tests=any(_is_test_path(path) for path in lower_paths),
            has_ci=any(path.startswith(".github/workflows/") or path in {".travis.yml", ".circleci/config.yml"} for path in lower_paths),
            has_docker=any(path.endswith("dockerfile") or "docker-compose" in path for path in lower_paths),
            has_docs=any(path.startswith("docs/") or path.startswith("doc/") for path in lower_paths),
            has_examples=any(path.startswith("examples/") or path.startswith("example/") for path in lower_paths),
            has_license_file=any(path.split("/")[-1] in {"license", "license.md", "license.txt"} for path in lower_paths),
            has_contributing=any(path.split("/")[-1] in {"contributing.md", "contributing"} for path in lower_paths),
        )

    def _collect_dependency_manifests(
        self,
        file_tree: RepositoryFileTreeEvidence | None,
    ) -> DependencyManifestEvidence | None:
        if not file_tree:
            return None
        manifest_paths = [path for path in file_tree.key_files if path.split("/")[-1] in MANIFEST_LANGUAGE_HINTS]
        languages: set[str] = set()
        package_managers: set[str] = set()
        frameworks: set[str] = set()
        for path in manifest_paths:
            filename = path.split("/")[-1]
            language, manager = MANIFEST_LANGUAGE_HINTS[filename]
            languages.add(language)
            package_managers.add(manager)
            if filename in {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"}:
                frameworks.add("Docker")
            if filename == "package.json":
                frameworks.add("Node.js")
            if filename in {"requirements.txt", "pyproject.toml"}:
                frameworks.add("Python")

        return DependencyManifestEvidence(
            source=file_tree.source,
            manifests=manifest_paths,
            package_managers=sorted(package_managers),
            languages=sorted(languages),
            frameworks=sorted(frameworks),
            has_lockfile=any(path.split("/")[-1] in LOCKFILES for path in file_tree.key_files),
        )


class _BorrowedAsyncClient:
    """Context manager wrapper that does not close an injected AsyncClient."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self.client

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def _decode_github_content(data: dict[str, Any]) -> str:
    content = data.get("content") or ""
    encoding = data.get("encoding")
    if encoding == "base64":
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return str(content)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _raw_url(identity: GitHubRepositoryIdentity, branch: str | None, path: str) -> str:
    resolved_branch = branch or "main"
    return f"https://raw.githubusercontent.com/{identity.owner}/{identity.repo}/{resolved_branch}/{path}"


def _is_test_path(path: str) -> bool:
    parts = path.split("/")
    filename = parts[-1]
    return (
        "tests" in parts
        or "test" in parts
        or filename.startswith("test_")
        or filename.endswith("_test.py")
        or filename.endswith(".test.ts")
        or filename.endswith(".spec.ts")
        or filename.endswith(".test.js")
        or filename.endswith(".spec.js")
    )


def _is_key_file(path: str) -> bool:
    filename = path.split("/")[-1]
    if filename in MANIFEST_LANGUAGE_HINTS or filename in LOCKFILES:
        return True
    if filename.lower() in {"readme.md", "license", "license.md", "contributing.md"}:
        return True
    return path.startswith(".github/workflows/")
