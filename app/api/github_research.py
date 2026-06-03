"""GitHub repository research API endpoints."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.github_research import GitHubEvidenceBundle, GitHubRepositoryCollector

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/github", tags=["github-research"])


class GitHubRepositoryAnalyzeRequest(BaseModel):
    """Request body for GitHub repository evidence collection."""

    repository_url: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="GitHub repository URL or owner/repo identifier.",
    )


def get_github_collector() -> GitHubRepositoryCollector:
    """Dependency factory for GitHub repository collector."""
    return GitHubRepositoryCollector()


@router.post("/repositories/analyze", response_model=GitHubEvidenceBundle)
async def analyze_github_repository(
    request: GitHubRepositoryAnalyzeRequest,
    collector: GitHubRepositoryCollector = Depends(get_github_collector),
):
    """Collect structured evidence and deterministic scores for one GitHub repo."""
    try:
        return await collector.collect(request.repository_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        detail = f"GitHub API request failed with HTTP {status_code}"
        if status_code == 404:
            detail = "GitHub repository was not found or is not publicly accessible."
        elif status_code == 403:
            detail = "GitHub API rate limit or permission error."
        logger.warning("GitHub API request failed", exc_info=exc)
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        logger.warning("GitHub API network error", exc_info=exc)
        raise HTTPException(status_code=502, detail=f"GitHub API network error: {exc}") from exc
