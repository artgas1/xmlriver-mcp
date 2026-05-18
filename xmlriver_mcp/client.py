"""HTTP client for XMLRiver API.

XMLRiver uses HTTP (not HTTPS — service constraint, key passed in query string).
Auth via `user=<id>&key=<hex>` query params on every request.
Documentation: https://xmlriver.com/apidoc/
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

API_BASE = os.environ.get("XMLRIVER_BASE_URL", "http://xmlriver.com")
USER = os.environ.get("XMLRIVER_USER")
KEY = os.environ.get("XMLRIVER_KEY")

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Lazy-init shared httpx client. Validates credentials."""
    global _client
    if _client is None:
        if not USER or not KEY:
            raise RuntimeError(
                "XMLRIVER_USER and XMLRIVER_KEY env vars required. "
                "Get them at https://xmlriver.com after registration and balance top-up."
            )
        _client = httpx.AsyncClient(
            base_url=API_BASE,
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=True,
        )
    return _client


def _auth_params() -> dict[str, str]:
    """Auth params injected into every request."""
    return {"user": str(USER), "key": str(KEY)}


def format_error(code: str, text: str) -> dict[str, Any]:
    """Structured error dict — returned, not raised."""
    return {
        "isError": True,
        "errorCode": code,
        "content": [{"type": "text", "text": text[:500]}],
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    reraise=True,
)
async def fetch_xml(path: str, **params: Any) -> str | dict[str, Any]:
    """GET request returning XML text body (or structured error dict).

    Args:
        path: URL path relative to API_BASE (e.g. ``/search/xml``)
        **params: Additional query parameters (merged with auth)

    Returns:
        XML response body as str, or structured error dict on HTTP failure.
    """
    client = _get_client()
    merged_params: dict[str, Any] = {**_auth_params(), **params}
    try:
        response = await client.get(path, params=merged_params)
    except httpx.HTTPError as e:
        return format_error("NETWORK", f"{type(e).__name__}: {e}")

    if response.status_code >= 400:
        return format_error(f"HTTP_{response.status_code}", response.text)

    return response.text


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    reraise=True,
)
async def fetch_text(path: str, **params: Any) -> str | dict[str, Any]:
    """GET request returning plain text (used for /api/get_balance, get_cost, etc).

    Returns plain text body or structured error dict.
    """
    client = _get_client()
    merged_params: dict[str, Any] = {**_auth_params(), **params}
    try:
        response = await client.get(path, params=merged_params)
    except httpx.HTTPError as e:
        return format_error("NETWORK", f"{type(e).__name__}: {e}")

    if response.status_code >= 400:
        return format_error(f"HTTP_{response.status_code}", response.text)

    return response.text.strip()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    reraise=True,
)
async def fetch_json(path: str, **params: Any) -> dict[str, Any]:
    """GET request returning JSON (used for Wordstat New endpoint).

    Returns parsed JSON dict or structured error dict.

    XMLRiver JSON endpoints may return HTTP 200 with `{"code": ..., "error": ...}`
    body on logical errors — we detect this and convert to structured error.
    """
    client = _get_client()
    # Drop None values so callers can pass optional params idiomatically
    merged_params: dict[str, Any] = {
        **_auth_params(),
        **{k: v for k, v in params.items() if v is not None},
    }
    try:
        response = await client.get(path, params=merged_params)
    except httpx.HTTPError as e:
        return format_error("NETWORK", f"{type(e).__name__}: {e}")

    if response.status_code >= 400:
        return format_error(f"HTTP_{response.status_code}", response.text)

    try:
        body = response.json()
    except ValueError:
        return format_error("INVALID_JSON", response.text)

    # XMLRiver-level error masquerading as HTTP 200
    if isinstance(body, dict) and "error" in body and "code" in body:
        return format_error(f"XMLRIVER_{body['code']}", str(body.get("error", "")))

    return body


async def close_client() -> None:
    """Close shared client. For testing / shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
