"""Account management tools — balance, tariff, cost per 1k requests."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from xmlriver_mcp.client import fetch_text
from xmlriver_mcp.server import mcp


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,  # account info, not external user-data
    }
)
async def get_balance() -> dict[str, Any]:
    """Get current XMLRiver account balance in rubles (₽).

    Use this to check funds before bulk operations or to monitor spending.

    Returns:
        Dict with `balance_rub` (float) or `isError` on failure.

    Examples:
        get_balance()
        → {"balance_rub": 1234.56}
    """
    result = await fetch_text("/api/get_balance/")
    if isinstance(result, dict):  # error
        return result
    try:
        return {"balance_rub": float(result)}
    except ValueError:
        return {
            "isError": True,
            "errorCode": "INVALID_RESPONSE",
            "content": [{"type": "text", "text": f"Cannot parse balance: {result[:200]}"}],
        }


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def get_tariff() -> dict[str, Any]:
    """Get current XMLRiver tariff name.

    Tariffs:
    - 'Basic' — pay-as-you-go, no prepay, 25 ₽ per 1k requests
    - 'Pro' — 5000 ₽/mo prepay, 20 ₽ per 1k
    - 'Mega' — 15000 ₽/mo prepay, 15 ₽ per 1k
    - 'Giga' — 50000 ₽/mo prepay, 12 ₽ per 1k

    Returns:
        Dict with `tariff` (str) or `isError`.
    """
    result = await fetch_text("/api/get_tarif/")
    if isinstance(result, dict):
        return result
    return {"tariff": result}


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def get_tariff_expire() -> dict[str, Any]:
    """Get expiration date for prepay tariff (Pro/Mega/Giga).

    Returns 'never' or date for Basic tariff (no expiry).

    Returns:
        Dict with `expires_at` (str) or `isError`.
    """
    result = await fetch_text("/api/get_tarif_expire/")
    if isinstance(result, dict):
        return result
    return {"expires_at": result}


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def get_cost(
    engine: Annotated[
        Literal["google", "yandex", "yaxml", "wordstat"],
        Field(
            description=(
                "Engine to check cost for. "
                "'google' = Google SERP parsing, "
                "'yandex' = Yandex SERP (direct), "
                "'yaxml' = Yandex Search API v2 (slightly pricier), "
                "'wordstat' = Wordstat New API."
            ),
        ),
    ],
) -> dict[str, Any]:
    """Get cost per 1000 requests for a given engine, in rubles (₽).

    Use this to estimate spend for a planned bulk operation. Cost depends on
    current tariff — see `get_tariff` for the tariff name.

    Returns:
        Dict with `engine`, `cost_per_1k_rub` or `isError`.

    Examples:
        get_cost(engine="google")
        → {"engine": "google", "cost_per_1k_rub": 25.0}
    """
    result = await fetch_text(f"/api/get_cost/{engine}/")
    if isinstance(result, dict):
        return result
    try:
        return {"engine": engine, "cost_per_1k_rub": float(result)}
    except ValueError:
        return {
            "isError": True,
            "errorCode": "INVALID_RESPONSE",
            "content": [{"type": "text", "text": f"Cannot parse cost: {result[:200]}"}],
        }
