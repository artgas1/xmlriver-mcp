"""Unit tests for HTTP client — uses respx to mock httpx."""


import httpx
import pytest
import respx


@pytest.fixture(autouse=True)
def _set_creds(monkeypatch):
    """Set fake credentials for tests."""
    monkeypatch.setenv("XMLRIVER_USER", "12345")
    monkeypatch.setenv("XMLRIVER_KEY", "fakekey123")
    # Reset module-level _client since env vars matter
    import xmlriver_mcp.client as client_mod
    client_mod._client = None
    client_mod.USER = "12345"
    client_mod.KEY = "fakekey123"


@pytest.mark.asyncio
async def test_fetch_xml_includes_auth_params():
    """fetch_xml includes user+key in query string."""
    from xmlriver_mcp.client import fetch_xml

    with respx.mock(base_url="http://xmlriver.com") as mock:
        mock.get("/search/xml").mock(
            return_value=httpx.Response(200, text="<xml>ok</xml>")
        )
        result = await fetch_xml("/search/xml", query="test")
        assert result == "<xml>ok</xml>"
        # Verify auth params present
        request = mock.calls.last.request
        assert "user=12345" in str(request.url)
        assert "key=fakekey123" in str(request.url)
        assert "query=test" in str(request.url)


@pytest.mark.asyncio
async def test_fetch_xml_returns_error_on_http_error():
    """HTTP 4xx/5xx returns structured error dict."""
    from xmlriver_mcp.client import fetch_xml

    with respx.mock(base_url="http://xmlriver.com") as mock:
        mock.get("/search/xml").mock(return_value=httpx.Response(403, text="forbidden"))
        result = await fetch_xml("/search/xml", query="test")
        assert isinstance(result, dict)
        assert result["isError"] is True
        assert result["errorCode"] == "HTTP_403"


@pytest.mark.asyncio
async def test_fetch_text_parses_balance():
    """fetch_text returns plain string for account endpoints."""
    from xmlriver_mcp.client import fetch_text

    with respx.mock(base_url="http://xmlriver.com") as mock:
        mock.get("/api/get_balance/").mock(
            return_value=httpx.Response(200, text="1234.56\n")
        )
        result = await fetch_text("/api/get_balance/")
        assert result == "1234.56"


@pytest.mark.asyncio
async def test_fetch_json_parses_wordstat():
    """fetch_json parses JSON response."""
    from xmlriver_mcp.client import fetch_json

    with respx.mock(base_url="http://xmlriver.com") as mock:
        mock.get("/wordstat/new/json").mock(
            return_value=httpx.Response(200, json={"shows": 12345})
        )
        result = await fetch_json("/wordstat/new/json", query="test")
        assert result == {"shows": 12345}


@pytest.mark.asyncio
async def test_missing_credentials_raises():
    """Missing XMLRIVER_USER/KEY raises clear error."""
    import xmlriver_mcp.client as client_mod
    client_mod.USER = None
    client_mod.KEY = None
    client_mod._client = None

    from xmlriver_mcp.client import fetch_xml
    with pytest.raises(RuntimeError, match="XMLRIVER_USER"):
        await fetch_xml("/search/xml", query="test")
