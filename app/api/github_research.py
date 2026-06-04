"""GitHub repository research API endpoints."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.github_research import (
    DemoEvaluationResult,
    GitHubEvidenceBundle,
    GitHubRepositoryCollector,
    RepositoryComparison,
    RepositoryScorecard,
    compare_repository_scorecards,
    evaluate_repository_comparison,
    score_repository,
)

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


class GitHubRepositoryCompareRequest(BaseModel):
    """Request body for deterministic GitHub repository comparison."""

    repository_urls: list[str] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="Two to five public GitHub repository URLs or owner/repo identifiers.",
    )


class GitHubRepositoryCompareResponse(BaseModel):
    """Structured comparison response for demo and evaluation use."""

    repositories: list[str]
    scorecards: list[RepositoryScorecard]
    comparison: RepositoryComparison
    evaluation: DemoEvaluationResult


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


@router.post("/repositories/compare", response_model=GitHubRepositoryCompareResponse)
async def compare_github_repositories(
    request: GitHubRepositoryCompareRequest,
    collector: GitHubRepositoryCollector = Depends(get_github_collector),
):
    """Collect evidence, rank repositories and return demo evaluation metrics."""
    bundles: list[GitHubEvidenceBundle] = []
    try:
        for repository in request.repository_urls:
            bundle = await collector.collect(repository)
            if bundle.scorecard is None:
                bundle.scorecard = score_repository(bundle)
            bundles.append(bundle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        detail = f"GitHub API request failed with HTTP {status_code}"
        if status_code == 404:
            detail = "At least one GitHub repository was not found or is not publicly accessible."
        elif status_code == 403:
            detail = "GitHub API rate limit or permission error."
        logger.warning("GitHub comparison API request failed", exc_info=exc)
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        logger.warning("GitHub comparison API network error", exc_info=exc)
        raise HTTPException(status_code=502, detail=f"GitHub API network error: {exc}") from exc

    scorecards = [bundle.scorecard for bundle in bundles if bundle.scorecard is not None]
    comparison = compare_repository_scorecards(scorecards)
    evaluation = evaluate_repository_comparison(comparison)
    return GitHubRepositoryCompareResponse(
        repositories=[bundle.identity.full_name for bundle in bundles],
        scorecards=scorecards,
        comparison=comparison,
        evaluation=evaluation,
    )
