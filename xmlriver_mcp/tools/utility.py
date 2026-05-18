"""Utility tools — URL indexing checks, etc."""

from __future__ import annotations

from typing import Annotated, Any, Literal

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
async def check_url_indexed(
    url: Annotated[
        str,
        Field(
            description=(
                "URL to check indexing for. Full URL with scheme. "
                "Example: 'https://example.com/page-slug'."
            ),
            min_length=10,
        ),
    ],
    search_engine: Annotated[
        Literal["google", "yandex"],
        Field(description="Which engine to check. Default 'google'."),
    ] = "google",
    country: Annotated[
        int,
        Field(
            description=(
                "For Google: country ID (default 2008=Russia). "
                "For Yandex: region ID (default 213=Moscow)."
            ),
        ),
    ] = 2008,
) -> dict[str, Any]:
    """Check if a URL is indexed in Google or Yandex.

    Internally uses `url:<URL>` operator with `inindex=1` flag to xmlriver
    (forces fresh index check, not cache).

    Use this for: SEO audits, indexation monitoring, "did Google find my new page?".

    Returns:
        Dict with:
            - `url` — checked URL
            - `search_engine`
            - `indexed` — bool
            - `details` — full search results if indexed (with title, snippet, position)
    """
    if search_engine == "google":
        path = "/search/xml"
        params: dict[str, Any] = {
            "query": url,
            "country": country if country >= 2000 else 2008,
            "inindex": 1,
        }
    else:  # yandex
        path = "/search_yandex/xml"
        params = {
            "query": url,
            "lr": country if country < 2000 else 213,
            "inindex": 1,
        }

    result = await fetch_xml(path, **params)
    if isinstance(result, dict):
        return result

    parsed = parse_search_xml(result)
    if parsed.get("isError"):
        # Error code 15 = no results = not indexed
        if parsed.get("errorCode") == "XMLRIVER_15":
            return {
                "url": url,
                "search_engine": search_engine,
                "indexed": False,
            }
        return parsed

    indexed = bool(parsed.get("results"))
    out: dict[str, Any] = {
        "url": url,
        "search_engine": search_engine,
        "indexed": indexed,
    }
    if indexed and parsed.get("results"):
        # Include the first match details
        out["details"] = parsed["results"][0]
    return out
