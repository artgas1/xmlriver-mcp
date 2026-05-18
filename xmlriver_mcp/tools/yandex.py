"""Yandex SERP parsing via XMLRiver.

Two endpoints:
- `/search_yandex/xml` — direct SERP parsing (with extras: FAQ, knowledge, etc)
- `/yandex/xml` — official Yandex Search API v2 proxy (cleaner JSON, official API contract)
"""

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
async def yandex_search(
    query: Annotated[
        str,
        Field(
            description=(
                "Search query. Plain text or with Yandex operators (site:, inurl:, host:, etc). "
                "Example: 'купить квартиру москва' or 'site:habr.com nextjs'."
            ),
            min_length=1,
            max_length=400,
        ),
    ],
    region: Annotated[
        int,
        Field(
            description=(
                "Yandex region ID (lr param). Default 213 (Moscow). "
                "Common: 213=Moscow, 2=SPb, 65=Novosibirsk, 54=Yekaterinburg, "
                "47=NN, 10174=Samara, 11119=Krasnodar, 39=Rostov, 51=Kazan. "
                "Full list: https://yandex.ru/yandsearch/regions.html"
            ),
        ),
    ] = 213,
    domain: Annotated[
        Literal["ru", "com", "ua", "by", "kz", "com.tr"],
        Field(description="Yandex domain. Default 'ru'."),
    ] = "ru",
    language: Annotated[
        Literal["ru", "uk", "be", "kk", "tr", "en"],
        Field(description="Interface language. Default 'ru'."),
    ] = "ru",
    device: Annotated[
        Literal["desktop", "tablet", "mobile"],
        Field(description="Device emulation. Default 'desktop'."),
    ] = "desktop",
    page: Annotated[
        int,
        Field(description="Page number (0-based for Yandex). Default 0.", ge=0, le=99),
    ] = 0,
    within: Annotated[
        str | None,
        Field(
            description=(
                "Date filter (Yandex `within` param). Values: '77' (24h), '1' (2 weeks), "
                "'2' (1 month), or 'YYYYMMDD..YYYYMMDD' custom range."
            ),
        ),
    ] = None,
    additional_blocks: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated extra blocks: "
                "'topads,bottomads,faqsnippet,rq,rs,knowledge_graph,sitelinks,"
                "extended_snippet,fast_links,related_searches'."
            ),
        ),
    ] = None,
    filter_duplicates: Annotated[
        bool,
        Field(description="Filter near-duplicate results. Default False (Yandex default)."),
    ] = False,
) -> dict[str, Any]:
    """Parse Yandex search results page (SERP) for a given query and region.

    Use this for: Russian SEO research (own/competitor ranking in Yandex),
    regional keyword analysis, SERP feature analysis (FAQ, knowledge graph),
    competitive intel for Russian-speaking markets.

    Do NOT use for: keyword frequency data — use `wordstat_query` instead.
    Do NOT use for: structured JSON output — use `yandex_search_api_v2` instead
    (official Yandex Search API proxy, cleaner JSON).

    Returns:
        Dict with `results` (organic 10 items), `total_found`, `page`, `addresults`
        (related_questions, knowledge_graph, etc), or `isError: True` on failure.

    Examples:
        yandex_search(query="купить iphone", region=213)
        → top 10 organic for Moscow

        yandex_search(query="site:wildberries.ru игрушки", region=2)
        → site-restricted search for St. Petersburg

        yandex_search(query="новости", within="77")
        → last-24-hours filtered
    """
    params: dict[str, Any] = {
        "query": query,
        "lr": region,
        "domain": domain,
        "lang": language,
        "device": device,
        "page": page,
    }
    if within:
        params["within"] = within
    if additional_blocks:
        params["additional"] = additional_blocks
    if filter_duplicates:
        params["filter"] = 1

    result = await fetch_xml("/search_yandex/xml", **params)
    if isinstance(result, dict):
        return result

    parsed = parse_search_xml(result)
    parsed["query"] = query
    parsed["region"] = region
    parsed["domain"] = domain
    parsed["device"] = device
    return parsed


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def yandex_search_api_v2(
    query: Annotated[
        str,
        Field(description="Search query.", min_length=1, max_length=400),
    ],
    region: Annotated[
        int,
        Field(description="Yandex region ID (lr). Default 213 (Moscow)."),
    ] = 213,
    page: Annotated[
        int,
        Field(description="Page number (0-based). Default 0.", ge=0, le=99),
    ] = 0,
    group_count: Annotated[
        int,
        Field(description="Results per page (Yandex Search API). Default 10.", ge=1, le=50),
    ] = 10,
) -> dict[str, Any]:
    """Query Yandex Search API v2 (official) via XMLRiver proxy.

    Use this when you need: cleaner structured output, no SERP-feature parsing overhead,
    documented Yandex Search API semantics. Slightly more expensive than `yandex_search`
    (~24 ₽/1k vs 25 ₽/1k on Basic tariff).

    Do NOT use for: SERP features (knowledge graph, FAQ, related questions) — those
    are not in the official API. Use `yandex_search` instead.

    Returns:
        Parsed search results dict similar to `yandex_search` but without addresults.
    """
    params: dict[str, Any] = {
        "query": query,
        "lr": region,
        "page": page,
        "groupby": f"attr=d.mode=deep.groups-on-page={group_count}.docs-in-group=1",
    }
    result = await fetch_xml("/yandex/xml", **params)
    if isinstance(result, dict):
        return result
    parsed = parse_search_xml(result)
    parsed["query"] = query
    parsed["region"] = region
    return parsed
