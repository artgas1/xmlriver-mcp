"""Search-box suggestions (autocomplete) for Google and Yandex.

Docs: https://xmlriver.com/apidoc/api-tips/ (Google)
      https://xmlriver.com/apiydoc/apiy-tips/ (Yandex)

The only endpoints in the API that take a POST body: mode and auth go in the
query string (``setab=tips``), the phrases go in JSON. One request carries 1–50
phrases and **is billed per phrase**, not per request.

Gotcha worth knowing: this endpoint rejects ``country``, which the regular
Google search accepts — it answers ``code 104: Неверный параметр loc!``. Only
``domain`` and ``lr`` are documented as extra parameters here, so nothing else
is forwarded.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from xmlriver_mcp.client import post_json
from xmlriver_mcp.server import mcp

MAX_PHRASES = 50

_PATHS = {"google": "/search/xml", "yandex": "/search_yandex/xml"}


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def search_suggestions(
    phrases: Annotated[
        list[str],
        Field(
            description=(
                "Phrases to autocomplete, 1–50 per call. BILLED PER PHRASE — 50 phrases "
                "in one call costs 50 requests, so batch deliberately rather than maximally."
            ),
            min_length=1,
            max_length=MAX_PHRASES,
        ),
    ],
    engine: Annotated[
        Literal["google", "yandex"],
        Field(description="Which search box to read suggestions from. Default 'google'."),
    ] = "google",
    domain: Annotated[
        str | None,
        Field(
            description=(
                "Search domain. Yandex takes a string ('ru', 'com', 'ua', 'by', 'kz', "
                "'com.tr'); Google takes its numeric domain id as a string. Omit for the default."
            )
        ),
    ] = None,
    lr: Annotated[
        str | None,
        Field(
            description=(
                "Language/region. Google: language code such as 'ru'. Yandex: numeric "
                "region id such as '213' (Moscow). Omit for the default."
            )
        ),
    ] = None,
) -> dict[str, Any]:
    """Collect search-box suggestions (autocomplete) for a batch of phrases.

    Use this for: keyword research beyond Wordstat — suggestions surface live
    long-tail phrasings, including ones with no Wordstat frequency at all; they
    are what people actually type. Pair it with a prefix sweep (append each
    letter of the alphabet to a seed) to pull the tail systematically.

    Do NOT use for: frequency data (suggestions carry no volume — feed them to
    `wordstat_query` afterwards), or for SERP contents (use `google_search` /
    `yandex_search`).

    Returns:
        Dict with:
            - `engine` (echoed), `requested` — number of phrases sent
            - `suggestions` — flat, de-duplicated list of suggestion strings
            - `count` — number of suggestions returned
            - Or `isError: True` on failure (including API-level errors such as
              `code 104` for an unsupported parameter).

    Examples:
        search_suggestions(phrases=["отчет по практике"])
        → {"engine": "google", "suggestions": ["отчет по практике пример", …], "count": 10}

        search_suggestions(phrases=["купить iphone", "купить ipad"], engine="yandex", lr="213")
        → suggestions from the Yandex search box for the Moscow region
    """
    cleaned = [p.strip() for p in phrases if p and p.strip()]
    if not cleaned:
        return {
            "isError": True,
            "errorCode": "EMPTY_PHRASES",
            "content": [
                {"type": "text", "text": "phrases must contain at least one non-empty string"}
            ],
        }
    if len(cleaned) > MAX_PHRASES:
        return {
            "isError": True,
            "errorCode": "TOO_MANY_PHRASES",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"{len(cleaned)} phrases sent, "
                        f"the endpoint accepts at most {MAX_PHRASES}"
                    ),
                }
            ],
        }

    params: dict[str, Any] = {"setab": "tips"}
    if domain is not None:
        params["domain"] = domain
    if lr is not None:
        params["lr"] = lr

    result = await post_json(_PATHS[engine], {"phrases": cleaned}, **params)
    if result.get("isError"):
        return result

    seen: dict[str, None] = {}
    for item in result.get("phrases") or []:
        if isinstance(item, str) and item.strip():
            seen.setdefault(item.strip(), None)

    return {
        "engine": engine,
        "requested": len(cleaned),
        "count": len(seen),
        "suggestions": list(seen),
    }
