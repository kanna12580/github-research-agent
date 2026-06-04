import pytest

from app.github_research.url_parser import extract_github_repository_urls, parse_github_repository_url


@pytest.mark.parametrize(
    ("value", "owner", "repo"),
    [
        ("https://github.com/langchain-ai/langgraph", "langchain-ai", "langgraph"),
        ("https://github.com/langchain-ai/langgraph/", "langchain-ai", "langgraph"),
        ("https://github.com/langchain-ai/langgraph.git", "langchain-ai", "langgraph"),
        ("https://github.com/langchain-ai/langgraph/tree/main/docs", "langchain-ai", "langgraph"),
        ("langchain-ai/langgraph", "langchain-ai", "langgraph"),
    ],
)
def test_parse_github_repository_url(value, owner, repo):
    identity = parse_github_repository_url(value)

    assert identity.owner == owner
    assert identity.repo == repo
    assert identity.full_name == f"{owner}/{repo}"
    assert identity.html_url == f"https://github.com/{owner}/{repo}"
    assert identity.api_url == f"https://api.github.com/repos/{owner}/{repo}"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "https://example.com/langchain-ai/langgraph",
        "https://github.com/features",
        "not a repo",
    ],
)
def test_parse_github_repository_url_rejects_non_repo_values(value):
    with pytest.raises(ValueError):
        parse_github_repository_url(value)


def test_extract_github_repository_urls_from_free_form_text():
    identities = extract_github_repository_urls(
        "Compare https://github.com/langchain-ai/langgraph and "
        "https://github.com/openai/openai-python/tree/main. "
        "Duplicate: https://github.com/langchain-ai/langgraph"
    )

    assert [identity.full_name for identity in identities] == [
        "langchain-ai/langgraph",
        "openai/openai-python",
    ]
