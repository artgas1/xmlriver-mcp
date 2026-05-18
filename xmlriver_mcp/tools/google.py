"""Google SERP parsing via XMLRiver."""

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
        "openWorldHint": True,  # calls external API
    }
)
async def google_search(
    query: Annotated[
        str,
        Field(
            description=(
                "Search query. Plain text or with Google operators (site:, inurl:, etc). "
                "Example: 'купить iphone 15' or 'site:wikipedia.org openai'."
            ),
            min_length=1,
            max_length=500,
        ),
    ],
    country: Annotated[
        int,
        Field(
            description=(
                "Country ID for Google location. Default 2008 (Russia). "
                "Common values: 2008=RU, 2840=US, 2826=UK, 2276=DE, 2250=FR, 2724=ES, 2484=MX. "
                "Full list: https://xmlriver.com/apidoc/country/"
            ),
        ),
    ] = 2008,
    domain: Annotated[
        int,
        Field(
            description=(
                "Google domain ID. Default 10 (google.com). "
                "Common: 10=google.com, 11=google.co.uk, 53=google.com.tr, 84=google.ru. "
                "Full list: https://xmlriver.com/apidoc/domain/"
            ),
        ),
    ] = 10,
    language: Annotated[
        str,
        Field(
            description=(
                "Interface language code (Google `lr` param). "
                "Examples: 'ru' (Russian), 'en' (English), 'de' (German), 'es' (Spanish). "
                "Default 'ru'."
            ),
        ),
    ] = "ru",
    device: Annotated[
        Literal["desktop", "tablet", "mobile"],
        Field(description="Device emulation. Default 'desktop'."),
    ] = "desktop",
    page: Annotated[
        int,
        Field(description="Page number (1-based). Default 1.", ge=1, le=100),
    ] = 1,
    location: Annotated[
        int | None,
        Field(
            description=(
                "Optional precise location ID (Google `loc` param). "
                "Overrides country/region with city-level precision. "
                "Full list: https://xmlriver.com/apidoc/loc/"
            ),
        ),
    ] = None,
    date_filter: Annotated[
        str | None,
        Field(
            description=(
                "Date filter (Google `tbs` param). "
                "Examples: 'qdr:h' (last hour), 'qdr:d' (24h), 'qdr:w' (week), "
                "'qdr:m' (month), 'qdr:y' (year), "
                "or custom 'cdr:1,cd_min:1/1/2024,cd_max:6/1/2024'."
            ),
        ),
    ] = None,
    additional_blocks: Annotated[
        str | None,
        Field(
            description=(
                "Comma-separated extra blocks to parse: "
                "'topads,bottomads,faqsnippet,rq,rs,knowledge_graph,sitelinks,"
                "g_news,g_videos,g_inlineshopping,searchsters,scroller,extended_snippet'. "
                "Each adds parsing cost on XMLRiver side but no extra charge."
            ),
        ),
    ] = None,
    ai_overview: Annotated[
        bool,
        Field(
            description=(
                "Parse Google's AI Overview block (slower, costs extra). Default False."
            ),
        ),
    ] = False,
) -> dict[str, Any]:
    """Parse Google search results page (SERP) for a given query and locale.

    Use this for: SEO research (own/competitor ranking), keyword discovery,
    SERP feature analysis (featured snippets, knowledge graph, FAQ), competitive intel.

    Do NOT use for: live page content fetching (use a dedicated scraper for that),
    Google Ads keyword planner data (use Yandex Wordstat via `wordstat_query` for RU).

    Returns:
        Dict with:
            - `query` (echoed)
            - `total_found` — Google's reported result count
            - `page` — page number
            - `results` — list of organic results with `position`, `url`, `title`, `snippet`
            - `addresults` — featured_snippet, related_questions, related_searches,
              knowledge_graph (if present and requested via `additional_blocks`)
            - Or `isError: True` on XMLRiver error (15 = no results, 110 = rate limit, etc).

    Examples:
        google_search(query="python tutorial", country=2008, language="ru")
        → {"results": [...10 organic results...], "total_found": 12300, "page": 1}

        google_search(query="site:wikipedia.org python", country=2840, language="en")
        → results restricted to wikipedia.org domain
    """
    params: dict[str, Any] = {
        "query": query,
        "country": country,
        "domain": domain,
        "lr": language,
        "device": device,
        "page": page,
    }
    if location is not None:
        params["loc"] = location
    if date_filter:
        params["tbs"] = date_filter
    if additional_blocks:
        params["additional"] = additional_blocks
    if ai_overview:
        params["ai"] = 1

    result = await fetch_xml("/search/xml", **params)
    if isinstance(result, dict):  # error
        return result

    parsed = parse_search_xml(result)
    parsed["query"] = query
    parsed["country"] = country
    parsed["language"] = language
    parsed["device"] = device
    return parsed
