"""Google Maps places search.

Docs: https://xmlriver.com/apidoc/api-maps/ and the Maps section of
https://xmlriver.com/apidoc/api-about/

Same endpoint as the web search (``/search/xml``), switched by ``setab=maps``;
``zoom`` and ``coords`` are required alongside it (omitting either is documented
to return ``code 108``). Result count comes from ``count`` (5–50, clamped by the
service), not from ``groupby``.

⚠️ **Not confirmed against a live response.** On 2026-08-04 every ``setab=maps``
request returned ``code 500`` ("Выполните перезапрос") — six retries, and also
for a deliberately invalid request without ``zoom``, which should have produced
``code 108``. Failing before parameter validation points at the mode being
unavailable service-side, not at a malformed request: plain Google and Yandex
searches answered normally in the same minutes. The request shape and the
response parsing below follow the documentation; both need a live check once the
mode responds again.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Annotated, Any

from pydantic import Field

from xmlriver_mcp.client import fetch_xml
from xmlriver_mcp.server import mcp
from xmlriver_mcp.xml_parser import parse_search_xml


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def google_maps_search(
    query: Annotated[
        str,
        Field(
            description="What to look for on the map, e.g. 'кофейня' or 'car repair'.",
            min_length=1,
            max_length=400,
        ),
    ],
    coords: Annotated[
        str,
        Field(
            description=(
                "Map centre as 'latitude,longitude' — e.g. '55.75581,37.61764' for Moscow. "
                "Required by the API together with zoom."
            ),
            pattern=r"^-?\d{1,3}(\.\d+)?,-?\d{1,3}(\.\d+)?$",
        ),
    ],
    zoom: Annotated[
        int,
        Field(description="Map zoom, 1–15. Required by the API together with coords.", ge=1, le=15),
    ] = 12,
    count: Annotated[
        int,
        Field(
            description="Places to return, 5–50. The service clamps anything above 50.", ge=5, le=50
        ),
    ] = 20,
    language: Annotated[
        str, Field(description="Interface language code, e.g. 'ru' or 'en'. Default 'ru'.")
    ] = "ru",
) -> dict[str, Any]:
    """Search Google Maps for places around a point.

    Use this for: local competitor mapping, presence checks in a city, pulling a
    list of businesses by category around a coordinate.

    Do NOT use for: organic web results (use `google_search`), or for a place you
    can name exactly — a plain web search answers that in one request.

    Returns:
        Dict with `results`, `total_found`, `query`, `coords`, `zoom`, `count`,
        or `isError: True` on failure (`code 108` means zoom/coords missing).

    Examples:
        google_maps_search(query="кофейня", coords="55.75581,37.61764", zoom=13)
        → places around central Moscow

        google_maps_search(query="barber", coords="41.40338,2.17403", zoom=14, count=50)
        → up to 50 places around Barcelona
    """
    result = await fetch_xml(
        "/search/xml",
        query=query,
        setab="maps",
        coords=coords,
        zoom=zoom,
        count=count,
        lr=language,
    )
    if isinstance(result, dict):  # error
        return result

    places = _parse_maps_xml(result)
    if places is None:
        # Mode answered with an ordinary SERP rather than a <maps> block — report
        # it as such instead of silently passing organic results off as places.
        parsed = parse_search_xml(result)
        parsed.update(
            {
                "query": query,
                "coords": coords,
                "zoom": zoom,
                "count": count,
                "warning": "ответ не содержит блока <maps> — вернулась обычная выдача",
            }
        )
        return parsed

    return {
        "query": query,
        "coords": coords,
        "zoom": zoom,
        "count": count,
        "places": places,
        "places_count": len(places),
    }


def _parse_maps_xml(xml_text: str) -> list[dict[str, Any]] | None:
    """Parse the <maps> block. Returns None when the response has no such block.

    Field set per the docs: title, stars, type, address, url. Anything else the
    service adds is carried through as-is rather than dropped.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    block = root.find(".//maps")
    if block is None:
        return None
    places = []
    for item in block.findall("item"):
        place = {child.tag: (child.text or "").strip() for child in item}
        if place:
            places.append(place)
    return places
