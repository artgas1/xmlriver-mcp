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


@pytest.fixture
def no_retry_wait(monkeypatch):
    """Keep the real retry policy but drop the pauses between attempts."""
    from tenacity import wait_none

    import xmlriver_mcp.client as client_mod

    for fn in (client_mod._get_xml, client_mod._get, client_mod._post):
        monkeypatch.setattr(fn.retry, "wait", wait_none())


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


REREQUEST_XML = (
    '<?xml version="1.0" encoding="utf-8"?><yandexsearch version="1.0"><response>'
    '<error code="500">Выполните перезапрос. Ответ от поисковой системы не получен.</error>'
    "</response></yandexsearch>"
)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 500])
@pytest.mark.usefixtures("no_retry_wait")
async def test_fetch_xml_repeats_rerequest_answer(status):
    """The transient «Выполните перезапрос» answer is repeated until the SERP arrives."""
    import xmlriver_mcp.client as client_mod

    with respx.mock(base_url="http://xmlriver.com") as mock:
        route = mock.get("/search_yandex/xml").mock(
            side_effect=[
                httpx.Response(status, text=REREQUEST_XML),
                httpx.Response(status, text=REREQUEST_XML),
                httpx.Response(200, text="<xml>serp</xml>"),
            ]
        )
        result = await client_mod.fetch_xml("/search_yandex/xml", query="test")

    assert result == "<xml>serp</xml>"
    assert route.call_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fetch_name", "path", "ok_response", "expected"),
    [
        ("fetch_xml", "/search/xml", httpx.Response(200, text="<xml>ok</xml>"), "<xml>ok</xml>"),
        ("fetch_text", "/api/get_balance/", httpx.Response(200, text="12.5\n"), "12.5"),
        ("fetch_json", "/wordstat/new/json", httpx.Response(200, json={"shows": 1}), {"shows": 1}),
    ],
)
@pytest.mark.usefixtures("no_retry_wait")
async def test_get_fetchers_repeat_transport_failure(fetch_name, path, ok_response, expected):
    """A dropped connection or a read timeout on a GET is repeated, not returned as NETWORK."""
    import xmlriver_mcp.client as client_mod

    with respx.mock(base_url="http://xmlriver.com") as mock:
        route = mock.get(path).mock(
            side_effect=[httpx.ConnectError("reset"), httpx.ReadTimeout("slow"), ok_response]
        )
        result = await getattr(client_mod, fetch_name)(path, query="test")

    assert result == expected
    assert route.call_count == 3


@pytest.mark.asyncio
@pytest.mark.usefixtures("no_retry_wait")
async def test_post_json_repeats_only_unsent_request():
    """Suggestions are billed per phrase: repeat a refused connection, never a read timeout."""
    from xmlriver_mcp.client import post_json

    ok = httpx.Response(200, json={"tips": []})
    with respx.mock(base_url="http://xmlriver.com") as mock:
        route = mock.post("/search/xml").mock(side_effect=[httpx.ConnectError("refused"), ok])
        assert await post_json("/search/xml", {"query": ["a"]}, setab="tips") == {"tips": []}
        assert route.call_count == 2

    with respx.mock(base_url="http://xmlriver.com") as mock:
        route = mock.post("/search/xml").mock(side_effect=[httpx.ReadTimeout("slow"), ok])
        result = await post_json("/search/xml", {"query": ["a"]}, setab="tips")
        assert result["errorCode"] == "NETWORK"
        assert route.call_count == 1


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
