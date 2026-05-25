"""
Tests for PostgreSQL text search configuration fallback helpers.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.db.text_search import (
    build_text_search_candidates,
    regconfig_sql_literal,
    resolve_text_search_config,
)


def test_build_text_search_candidates_deduplicates_and_orders() -> None:
    assert build_text_search_candidates("chinese") == ["chinese", "simple", "english"]
    assert build_text_search_candidates("simple") == ["simple", "english"]


def test_regconfig_sql_literal_escapes_quotes() -> None:
    assert regconfig_sql_literal("simple") == "'simple'"
    assert regconfig_sql_literal("foo'bar") == "'foo''bar'"


@pytest.mark.asyncio
async def test_resolve_text_search_config_falls_back_to_simple() -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=[None, "simple"])

    result = await resolve_text_search_config(conn)

    assert result == "simple"
    assert conn.fetchval.await_count == 2


@pytest.mark.asyncio
async def test_resolve_text_search_config_raises_when_none_available() -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=[None, None, None])

    with pytest.raises(RuntimeError, match="No PostgreSQL text search configuration is available"):
        await resolve_text_search_config(conn)
