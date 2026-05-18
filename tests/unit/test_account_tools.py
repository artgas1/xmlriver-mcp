"""Unit tests for account tools — mocked client."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _set_creds(monkeypatch):
    monkeypatch.setenv("XMLRIVER_USER", "12345")
    monkeypatch.setenv("XMLRIVER_KEY", "fakekey123")
    import xmlriver_mcp.client as client_mod
    client_mod._client = None
    client_mod.USER = "12345"
    client_mod.KEY = "fakekey123"


@pytest.mark.asyncio
async def test_get_balance_returns_float():
    from xmlriver_mcp.tools.account import get_balance

    with patch("xmlriver_mcp.tools.account.fetch_text", AsyncMock(return_value="1234.56")):
        result = await get_balance()
        assert result == {"balance_rub": 1234.56}


@pytest.mark.asyncio
async def test_get_balance_handles_invalid_response():
    from xmlriver_mcp.tools.account import get_balance

    with patch("xmlriver_mcp.tools.account.fetch_text", AsyncMock(return_value="not a number")):
        result = await get_balance()
        assert result["isError"] is True
        assert result["errorCode"] == "INVALID_RESPONSE"


@pytest.mark.asyncio
async def test_get_tariff_returns_string():
    from xmlriver_mcp.tools.account import get_tariff

    with patch("xmlriver_mcp.tools.account.fetch_text", AsyncMock(return_value="Basic")):
        result = await get_tariff()
        assert result == {"tariff": "Basic"}


@pytest.mark.asyncio
async def test_get_cost_returns_float():
    from xmlriver_mcp.tools.account import get_cost

    with patch("xmlriver_mcp.tools.account.fetch_text", AsyncMock(return_value="25.0")):
        result = await get_cost(engine="google")
        assert result == {"engine": "google", "cost_per_1k_rub": 25.0}


@pytest.mark.asyncio
async def test_get_balance_propagates_error():
    """If client returns error dict, tool propagates it."""
    from xmlriver_mcp.tools.account import get_balance

    error_dict = {
        "isError": True,
        "errorCode": "HTTP_500",
        "content": [{"type": "text", "text": "server error"}],
    }
    with patch("xmlriver_mcp.tools.account.fetch_text", AsyncMock(return_value=error_dict)):
        result = await get_balance()
        assert result == error_dict
