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


# Transport failures worth repeating. A GET is idempotent, so a timeout qualifies
# too; a paid POST (suggestions are billed per phrase) is repeated only when the
# request provably never reached XMLRiver — a read timeout may already be billed.
_GET_RETRY_ERRORS = (httpx.TimeoutException, httpx.ConnectError)
_UNSENT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)
_RETRY_WAIT = wait_exponential(multiplier=1, min=2, max=10)

# The retrying helpers below raise; the public fetch_* catch the final failure and
# return a structured error. A decorator on a function that catches its own
# exceptions never fires — that is how every retry here was dead until 0.2.2.

REREQUEST_MARKER = "Выполните перезапрос"


class _RerequestError(Exception):
    """XMLRiver answered "Выполните перезапрос"; carries the response for the last attempt."""

    def __init__(self, response: httpx.Response) -> None:
        super().__init__(response.status_code)
        self.response = response


def _asks_to_rerequest(response: httpx.Response) -> bool:
    """XMLRiver's transient "no answer from the search engine" error.

    It passes on a repeat 2-3 attempts later. Seen as HTTP 500 and as an <error>
    inside HTTP 200; a real SERP never carries <error>, so a query that merely
    contains the phrase is not mistaken for it.
    """
    body = response.text
    return REREQUEST_MARKER in body and (response.status_code >= 500 or "<error" in body)


@retry(
    stop=stop_after_attempt(4),
    wait=_RETRY_WAIT,
    retry=retry_if_exception_type((_RerequestError, *_GET_RETRY_ERRORS)),
    reraise=True,
)
async def _get_xml(path: str, params: dict[str, Any]) -> httpx.Response:
    response = await _get_client().get(path, params=params)
    if _asks_to_rerequest(response):
        raise _RerequestError(response)
    return response


@retry(
    stop=stop_after_attempt(3),
    wait=_RETRY_WAIT,
    retry=retry_if_exception_type(_GET_RETRY_ERRORS),
    reraise=True,
)
async def _get(path: str, params: dict[str, Any]) -> httpx.Response:
    return await _get_client().get(path, params=params)


@retry(
    stop=stop_after_attempt(3),
    wait=_RETRY_WAIT,
    retry=retry_if_exception_type(_UNSENT_ERRORS),
    reraise=True,
)
async def _post(path: str, params: dict[str, Any], payload: dict[str, Any]) -> httpx.Response:
    return await _get_client().post(path, params=params, json=payload)


async def fetch_xml(path: str, **params: Any) -> str | dict[str, Any]:
    """GET request returning XML text body (or structured error dict).

    "Выполните перезапрос" answers and transport failures are repeated with a
    pause (up to 4 attempts); if the last answer still asks for a re-request, it
    is returned as-is.

    Args:
        path: URL path relative to API_BASE (e.g. ``/search/xml``)
        **params: Additional query parameters (merged with auth)

    Returns:
        XML response body as str, or structured error dict on HTTP failure.
    """
    merged_params: dict[str, Any] = {**_auth_params(), **params}
    try:
        response = await _get_xml(path, merged_params)
    except _RerequestError as e:
        response = e.response
    except httpx.HTTPError as e:
        return format_error("NETWORK", f"{type(e).__name__}: {e}")

    if response.status_code >= 400:
        return format_error(f"HTTP_{response.status_code}", response.text)

    return response.text


async def fetch_text(path: str, **params: Any) -> str | dict[str, Any]:
    """GET request returning plain text (used for /api/get_balance, get_cost, etc).

    Transport failures are repeated with a pause (up to 3 attempts).
    Returns plain text body or structured error dict.
    """
    merged_params: dict[str, Any] = {**_auth_params(), **params}
    try:
        response = await _get(path, merged_params)
    except httpx.HTTPError as e:
        return format_error("NETWORK", f"{type(e).__name__}: {e}")

    if response.status_code >= 400:
        return format_error(f"HTTP_{response.status_code}", response.text)

    return response.text.strip()


async def fetch_json(path: str, **params: Any) -> dict[str, Any]:
    """GET request returning JSON (used for Wordstat New endpoint).

    Transport failures are repeated with a pause (up to 3 attempts).
    Returns parsed JSON dict or structured error dict.

    XMLRiver JSON endpoints may return HTTP 200 with `{"code": ..., "error": ...}`
    body on logical errors — we detect this and convert to structured error.
    """
    # Drop None values so callers can pass optional params idiomatically
    merged_params: dict[str, Any] = {
        **_auth_params(),
        **{k: v for k, v in params.items() if v is not None},
    }
    try:
        response = await _get(path, merged_params)
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


async def post_json(path: str, payload: dict[str, Any], **params: Any) -> dict[str, Any]:
    """POST with a JSON body, returning the parsed JSON response.

    Used by the search-suggestions endpoints (``setab=tips``), the only ones that
    take a body: auth and mode stay in the query string, the phrases go in JSON.
    Billed per phrase, so only a request that never left (refused connection,
    connect or pool timeout) is repeated — never a read timeout.

    XMLRiver reports API-level failures inside a 200 response
    (``{"code": "104", "error": "…"}``), so those are converted into the same
    structured error dict as transport failures instead of being returned as data.
    """
    merged_params: dict[str, Any] = {**_auth_params(), **params}
    try:
        response = await _post(path, merged_params, payload)
    except httpx.HTTPError as e:
        return format_error("NETWORK", f"{type(e).__name__}: {e}")

    if response.status_code >= 400:
        return format_error(f"HTTP_{response.status_code}", response.text)

    try:
        data = response.json()
    except ValueError:
        return format_error("BAD_JSON", response.text)

    if isinstance(data, dict) and data.get("error"):
        return format_error(str(data.get("code", "API")), str(data["error"]))
    return data
