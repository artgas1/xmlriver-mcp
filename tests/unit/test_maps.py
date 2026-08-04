"""Tests for Google Maps places search.

The live mode was unavailable while this was written (see the module docstring
in tools/maps.py), so these lock the request shape and the documented response
parsing — and specifically that organic results are never passed off as places.
"""

from __future__ import annotations

import pytest

from xmlriver_mcp.tools.maps import _parse_maps_xml, google_maps_search

TOOL = google_maps_search.fn if hasattr(google_maps_search, "fn") else google_maps_search

MAPS_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<yandexsearch version="1.0"><response>
  <maps>
    <item><title>PERK Cafe</title><stars>4,7</stars><type>Кафе</type>
          <address>ул. Вольская, 63/69</address><url>https://example.com</url></item>
    <item><title>Двор</title><stars>4,5</stars><type>Кофейня</type>
          <address>ул. Мира, 1</address><url></url></item>
  </maps>
</response></yandexsearch>"""

ORGANIC_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<yandexsearch version="1.0"><response><found priority="all">100</found>
  <results><grouping><group><doc><url>https://example.com</url>
  <title>Кофейня</title></doc></group></grouping></results>
</response></yandexsearch>"""


@pytest.mark.asyncio
async def test_sends_setab_maps_and_required_params(monkeypatch):
    captured = {}

    async def fake_fetch(path, **params):
        captured["path"] = path
        captured.update(params)
        return MAPS_XML

    monkeypatch.setattr("xmlriver_mcp.tools.maps.fetch_xml", fake_fetch)
    result = await TOOL(query="кофейня", coords="55.75581,37.61764", zoom=13, count=5)

    assert captured["path"] == "/search/xml"
    assert captured["setab"] == "maps"  # без него сервис отдаёт обычную выдачу
    assert captured["coords"] == "55.75581,37.61764"
    assert captured["zoom"] == 13
    assert result["places_count"] == 2
    assert result["places"][0]["title"] == "PERK Cafe"
    assert result["places"][0]["stars"] == "4,7"


@pytest.mark.asyncio
async def test_organic_response_is_flagged_not_passed_as_places(monkeypatch):
    """Без блока <maps> органику нельзя выдавать за заведения — только с предупреждением."""

    async def fake_fetch(path, **params):
        return ORGANIC_XML

    monkeypatch.setattr("xmlriver_mcp.tools.maps.fetch_xml", fake_fetch)
    result = await TOOL(query="кофейня", coords="55.75581,37.61764")

    assert "places" not in result
    assert "warning" in result


@pytest.mark.asyncio
async def test_transport_error_passed_through(monkeypatch):
    async def fake_fetch(path, **params):
        return {
            "isError": True,
            "errorCode": "XMLRIVER_500",
            "content": [{"type": "text", "text": "…"}],
        }

    monkeypatch.setattr("xmlriver_mcp.tools.maps.fetch_xml", fake_fetch)
    result = await TOOL(query="кофейня", coords="55.75581,37.61764")

    assert result["isError"] is True
    assert result["errorCode"] == "XMLRIVER_500"


def test_parser_returns_none_without_maps_block():
    assert _parse_maps_xml(ORGANIC_XML) is None
    assert _parse_maps_xml("не xml вовсе") is None
    assert len(_parse_maps_xml(MAPS_XML)) == 2
