"""Integration tests — requires live XMLRiver API credentials.

Run with: pytest tests/integration -v -m integration

Skipped if XMLRIVER_USER/XMLRIVER_KEY env vars not set.
"""

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (os.environ.get("XMLRIVER_USER") and os.environ.get("XMLRIVER_KEY")),
        reason="XMLRIVER_USER/XMLRIVER_KEY env vars not set",
    ),
]


@pytest.fixture(autouse=True)
async def _reset_client():
    """Reset shared httpx client between tests — each test has its own event loop."""
    import xmlriver_mcp.client as client_mod
    client_mod._client = None
    yield
    await client_mod.close_client()


@pytest.mark.asyncio
async def test_get_balance_live():
    """Live balance check — should return positive or zero."""
    from xmlriver_mcp.tools.account import get_balance

    result = await get_balance()
    assert "balance_rub" in result, f"Got error: {result}"
    assert isinstance(result["balance_rub"], (int, float))


@pytest.mark.asyncio
async def test_get_cost_google_live():
    """Live cost check for Google."""
    from xmlriver_mcp.tools.account import get_cost

    result = await get_cost(engine="google")
    assert "cost_per_1k_rub" in result, f"Got error: {result}"
    assert result["cost_per_1k_rub"] > 0
    assert result["cost_per_1k_rub"] < 100  # sanity — won't be >100 ₽/1k


@pytest.mark.asyncio
async def test_google_search_returns_results():
    """Live Google search for common query — should return ≥1 result."""
    from xmlriver_mcp.tools.google import google_search

    result = await google_search(query="google", country=2008, language="ru")
    assert "results" in result, f"Got error: {result}"
    assert result["results_count"] > 0


@pytest.mark.asyncio
async def test_yandex_search_returns_results():
    """Live Yandex search for common query — should return ≥1 result."""
    from xmlriver_mcp.tools.yandex import yandex_search

    result = await yandex_search(query="яндекс", region=213)
    assert "results" in result, f"Got error: {result}"
    assert result["results_count"] > 0
