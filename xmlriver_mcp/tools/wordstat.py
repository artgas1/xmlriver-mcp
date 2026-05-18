"""Yandex Wordstat — keyword frequency data via XMLRiver Wordstat New API.

Returns JSON (not XML) — separate endpoint.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from xmlriver_mcp.client import fetch_json
from xmlriver_mcp.server import mcp


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def wordstat_query(
    query: Annotated[
        str,
        Field(
            description=(
                "Keyword phrase to check frequency for. "
                "Yandex operators OK: '!' (exact form), '+' (require word), "
                "'\"...\"' (exact phrase), '-' (negative word). "
                "Examples: 'купить iphone', '!купить +iphone', '\"новый год 2026\"'."
            ),
            min_length=1,
            max_length=300,
        ),
    ],
    region: Annotated[
        int | None,
        Field(
            description=(
                "Yandex region ID for geo-targeted frequency. "
                "Default None = all of Russia + neighbors. "
                "213=Moscow, 2=SPb, 65=Novosibirsk, etc."
            ),
        ),
    ] = None,
    device: Annotated[
        Literal["desktop", "phone", "tablet"] | None,
        Field(
            description=(
                "Device type filter. None (default) = all devices combined. "
                "Otherwise: 'desktop', 'phone', or 'tablet'."
            ),
        ),
    ] = None,
    history_period: Annotated[
        Literal["none", "monthly", "weekly"],
        Field(
            description=(
                "Include historical dynamics. 'none' = current frequency only, "
                "'monthly' = last 24 months, 'weekly' = last 12 months by week. Default 'none'."
            ),
        ),
    ] = "none",
) -> dict[str, Any]:
    """Get Yandex Wordstat frequency for a keyword phrase.

    Use this for: keyword research, demand validation, seasonality analysis,
    long-tail discovery. **Russian/Yandex-speaking markets** — this is Yandex's
    equivalent of Google Keyword Planner.

    Do NOT use for: Google volume (Wordstat is Yandex-only — for Google use
    Google Keyword Planner or third-party tools).

    Returns:
        Dict with:
            - `query` (echoed)
            - `total_shows` — total monthly impressions (главное число)
            - `device_breakdown` — {desktop, phone, tablet} if available
            - `similar_queries` — phrases users searched alongside (semantic core seed)
            - `history` — list of {date, count} if history_period != 'none'
            - Or `isError: True` on failure.

    Examples:
        wordstat_query(query="купить iphone")
        → {"total_shows": 187234, "similar_queries": [...]}

        wordstat_query(query="!купить +iphone +pro", region=213, history_period="monthly")
        → exact-form filtered, Moscow-only, 24-month dynamics
    """
    params: dict[str, Any] = {"query": query}
    if device is not None:
        params["device"] = device
    if region is not None:
        params["lr"] = region
    if history_period != "none":
        params["history"] = "month" if history_period == "monthly" else "week"

    result = await fetch_json("/wordstat/new/json", **params)
    if result.get("isError"):
        return result

    # XMLRiver Wordstat New returns:
    # {
    #   "popular": [{"isAssociations": false, "value": "170111", "text": "купить iphone"}, ...],
    #   "associations": [{"isAssociations": true, "value": "34097", "text": "..."}, ...]
    # }
    # "popular" = phrases containing the query (with their counts)
    # "associations" = related phrases users also searched
    # First entry in "popular" is usually the exact query with its main count.

    def _normalize(entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if not entries:
            return []
        out: list[dict[str, Any]] = []
        for e in entries:
            text = e.get("text") or e.get("phrase") or ""
            raw_count = e.get("value") or e.get("count") or "0"
            try:
                count = int(str(raw_count).replace(" ", "").replace("\xa0", ""))
            except (ValueError, AttributeError):
                count = 0
            out.append({"phrase": text, "shows": count})
        return out

    popular = _normalize(result.get("popular"))
    associations = _normalize(result.get("associations"))

    # Try to find exact-match total shows from popular (first entry usually matches query)
    total_shows: int | None = None
    if popular:
        # First entry is typically the exact phrase
        total_shows = popular[0]["shows"]

    out: dict[str, Any] = {"query": query}
    if region is not None:
        out["region"] = region
    if total_shows is not None:
        out["total_shows"] = total_shows
    if popular:
        out["containing_phrases"] = popular  # phrases that contain the query
    if associations:
        out["similar_queries"] = associations  # related phrases (associations)

    # Historical data if requested
    if "history" in result:
        out["history"] = result["history"]
    if "device" in result:
        out["device_breakdown"] = result["device"]

    # Include raw only if no structured fields extracted (debugging fallback)
    if not (popular or associations):
        out["_raw"] = result

    return out
