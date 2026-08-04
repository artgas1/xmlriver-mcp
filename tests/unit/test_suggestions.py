"""Tests for search-box suggestions.

The value here is in the guards: the endpoint bills per phrase, so a request
that would be rejected must never leave the process, and an API-level error
arriving inside a 200 response must not be mistaken for data.
"""

from __future__ import annotations

import pytest

from xmlriver_mcp.tools.suggestions import MAX_PHRASES, search_suggestions

TOOL = search_suggestions.fn if hasattr(search_suggestions, "fn") else search_suggestions


@pytest.mark.asyncio
async def test_returns_deduplicated_suggestions(monkeypatch):
    captured = {}

    async def fake_post(path, payload, **params):
        captured["path"] = path
        captured["payload"] = payload
        captured["params"] = params
        return {"phrases": ["отчет по практике", "отчет по практике пример", "отчет по практике"]}

    monkeypatch.setattr("xmlriver_mcp.tools.suggestions.post_json", fake_post)
    result = await TOOL(phrases=["отчет по практике"])

    assert captured["path"] == "/search/xml"
    assert captured["params"]["setab"] == "tips"
    assert captured["payload"] == {"phrases": ["отчет по практике"]}
    # дубль схлопнут, порядок сохранён
    assert result["suggestions"] == ["отчет по практике", "отчет по практике пример"]
    assert result["count"] == 2
    assert result["requested"] == 1


@pytest.mark.asyncio
async def test_yandex_uses_its_own_endpoint(monkeypatch):
    captured = {}

    async def fake_post(path, payload, **params):
        captured["path"] = path
        captured["params"] = params
        return {"phrases": ["тест"]}

    monkeypatch.setattr("xmlriver_mcp.tools.suggestions.post_json", fake_post)
    await TOOL(phrases=["тест"], engine="yandex", lr="213", domain="ru")

    assert captured["path"] == "/search_yandex/xml"
    assert captured["params"]["lr"] == "213"
    assert captured["params"]["domain"] == "ru"


@pytest.mark.asyncio
async def test_country_is_never_forwarded(monkeypatch):
    """The tips endpoint rejects `country` with `code 104` — it must not be sent."""
    captured = {}

    async def fake_post(path, payload, **params):
        captured.update(params)
        return {"phrases": []}

    monkeypatch.setattr("xmlriver_mcp.tools.suggestions.post_json", fake_post)
    await TOOL(phrases=["тест"], lr="ru")

    assert "country" not in captured
    assert "loc" not in captured


@pytest.mark.asyncio
async def test_blank_phrases_rejected_without_calling_api(monkeypatch):
    async def fail(*a, **kw):  # pragma: no cover — must not run
        raise AssertionError("API вызван для запроса, который заведомо отклонён")

    monkeypatch.setattr("xmlriver_mcp.tools.suggestions.post_json", fail)
    result = await TOOL(phrases=["   ", ""])

    assert result["isError"] is True
    assert result["errorCode"] == "EMPTY_PHRASES"


@pytest.mark.asyncio
async def test_over_limit_rejected_without_calling_api(monkeypatch):
    """Billing is per phrase — an over-limit batch must not reach the wire."""

    async def fail(*a, **kw):  # pragma: no cover — must not run
        raise AssertionError("API вызван с батчем больше лимита")

    monkeypatch.setattr("xmlriver_mcp.tools.suggestions.post_json", fail)
    result = await TOOL(phrases=[f"фраза {i}" for i in range(MAX_PHRASES + 1)])

    assert result["isError"] is True
    assert result["errorCode"] == "TOO_MANY_PHRASES"


@pytest.mark.asyncio
async def test_api_error_passed_through(monkeypatch):
    async def fake_post(path, payload, **params):
        return {
            "isError": True,
            "errorCode": "104",
            "content": [{"type": "text", "text": "Неверный параметр loc!"}],
        }

    monkeypatch.setattr("xmlriver_mcp.tools.suggestions.post_json", fake_post)
    result = await TOOL(phrases=["тест"])

    assert result["isError"] is True
    assert result["errorCode"] == "104"
    assert "suggestions" not in result


@pytest.mark.asyncio
async def test_post_json_converts_inline_api_error(monkeypatch):
    """XMLRiver reports failures inside HTTP 200 — those must become errors."""
    from xmlriver_mcp import client

    class FakeResponse:
        status_code = 200
        text = '{"code": "104"}'

        def json(self):
            return {"code": "104", "error": "Неверный параметр loc!"}

    class FakeClient:
        async def post(self, path, params=None, json=None):
            return FakeResponse()

    monkeypatch.setattr(client, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(client, "USER", "1")
    monkeypatch.setattr(client, "KEY", "k")

    result = await client.post_json("/search/xml", {"phrases": ["x"]}, setab="tips")
    assert result["isError"] is True
    assert result["errorCode"] == "104"
