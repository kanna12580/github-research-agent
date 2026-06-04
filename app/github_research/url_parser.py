"""GitHub repository URL parsing utilities."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.github_research.models import GitHubRepositoryIdentity


_OWNER_REPO_RE = re.compile(r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$")
_GITHUB_URL_RE = re.compile(
    r"https?://(?:www\.)?github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?",
    re.IGNORECASE,
)


def parse_github_repository_url(value: str) -> GitHubRepositoryIdentity:
    """Parse GitHub URL or owner/repo text into canonical repository identity."""
    candidate = value.strip()
    if not candidate:
        raise ValueError("GitHub repository URL is empty")

    owner: str | None = None
    repo: str | None = None

    direct_match = _OWNER_REPO_RE.match(candidate)
    if direct_match and "://" not in candidate:
        owner = direct_match.group("owner")
        repo = direct_match.group("repo")
    else:
        parsed = urlparse(candidate)
        host = parsed.netloc.lower()
        if host in {"github.com", "www.github.com"}:
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1].removesuffix(".git")

    if not owner or not repo:
        raise ValueError(f"Not a supported GitHub repository URL: {value}")

    if owner.lower() in {"settings", "marketplace", "topics", "features"}:
        raise ValueError(f"GitHub URL does not identify a repository: {value}")

    html_url = f"https://github.com/{owner}/{repo}"
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    return GitHubRepositoryIdentity(owner=owner, repo=repo, html_url=html_url, api_url=api_url)


def extract_github_repository_urls(text: str) -> list[GitHubRepositoryIdentity]:
    """Extract unique public GitHub repository identities from free-form text."""
    identities: list[GitHubRepositoryIdentity] = []
    seen: set[str] = set()
    for match in _GITHUB_URL_RE.finditer(text or ""):
        try:
            identity = parse_github_repository_url(match.group(0))
        except ValueError:
            continue
        key = identity.full_name.lower()
        if key in seen:
            continue
        seen.add(key)
        identities.append(identity)
    return identities
