"""Yandex Wordstat — keyword frequency and demand dynamics via XMLRiver Wordstat New API.

Returns JSON (not XML) — separate endpoint.

The endpoint has two mutually exclusive modes, selected by `pagetype`:

- ``words``   — phrases containing the query + associations (the default)
- ``history`` — demand dynamics over time + total frequency in ``totalValue``

They cannot be combined in one call: a ``history`` response carries no
``popular``/``associations`` at all, and vice versa.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any, Literal

from pydantic import Field

from xmlriver_mcp.client import fetch_json, format_error
from xmlriver_mcp.server import mcp

# MCP-facing period name -> XMLRiver `period` value
_PERIOD_API: dict[str, str] = {"monthly": "month", "weekly": "week", "daily": "day"}

# XMLRiver rejects windows shorter than three periods with `{"code": "400"}`.
_MIN_POINTS = 3

# Default window sizes when the caller does not pass start/end.
_DEFAULT_POINTS: dict[str, int] = {"month": 24, "week": 12, "day": 30}


def _to_int(raw: Any) -> int:
    """Parse XMLRiver numeric strings ("28 211", "1\xa0234") into int."""
    try:
        return int(str(raw).replace(" ", "").replace("\xa0", ""))
    except (ValueError, TypeError, AttributeError):
        return 0


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def _shift_months(anchor: date, months: int) -> date:
    """Shift a date by whole months, clamping the day to the target month length."""
    total = anchor.year * 12 + (anchor.month - 1) + months
    year, month_index = divmod(total, 12)
    month = month_index + 1
    return date(year, month, min(anchor.day, _days_in_month(year, month)))


def _resolve_window(
    api_period: str,
    start: date | None,
    end: date | None,
    today: date,
) -> tuple[date, date]:
    """Align a requested window to XMLRiver's rules.

    Each period type has its own alignment and its own notion of "last complete
    period"; asking for anything else returns an API error rather than partial
    data. The window is also widened backwards when it is shorter than
    ``_MIN_POINTS``, so a caller asking for one month gets three instead of an error.
    """
    if api_period == "month":
        last_complete = date(today.year, today.month, 1) - timedelta(days=1)
        stop = min(end, last_complete) if end else last_complete
        stop = date(stop.year, stop.month, _days_in_month(stop.year, stop.month))
        stop_first = date(stop.year, stop.month, 1)
        begin = (
            date(start.year, start.month, 1)
            if start
            else _shift_months(stop_first, -(_DEFAULT_POINTS["month"] - 1))
        )
        latest_begin = _shift_months(stop_first, -(_MIN_POINTS - 1))
        return min(begin, latest_begin), stop

    if api_period == "week":
        # Monday is 0 — step back past this week's Monday to land on the last full Sunday.
        last_sunday = today - timedelta(days=today.weekday() + 1)
        stop = min(end, last_sunday) if end else last_sunday
        stop += timedelta(days=6 - stop.weekday())  # forward to that week's Sunday
        stop = min(stop, last_sunday)
        begin = (
            start - timedelta(days=start.weekday())  # back to Monday
            if start
            else stop - timedelta(days=7 * (_DEFAULT_POINTS["week"] - 1) + 6)
        )
        latest_begin = stop - timedelta(days=7 * (_MIN_POINTS - 1) + 6)
        return min(begin, latest_begin), stop

    # day — the API refuses today as `end`; keep a day of slack for late ingestion.
    last_day = today - timedelta(days=2)
    stop = min(end, last_day) if end else last_day
    begin = start or stop - timedelta(days=_DEFAULT_POINTS["day"] - 1)
    latest_begin = stop - timedelta(days=_MIN_POINTS - 1)
    return min(begin, latest_begin), stop


def _point_label(point: dict[str, Any]) -> str | None:
    """Normalize a series point to a date label.

    XMLRiver labels the same field three different ways depending on period:
    ``{year, month}`` (month is 0-based) for months, ``x`` for weeks, ``day`` for days.
    """
    year, month = point.get("year"), point.get("month")
    if year is not None and month is not None:
        return f"{int(year):04d}-{int(month) + 1:02d}"
    for key in ("x", "day", "date"):
        value = point.get(key)
        if value:
            return str(value)
    return None


def _extract_history(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the absolute series (and relative share, when present) out of the graph tab."""
    graph = payload.get("graph") or {}
    images = graph.get("images") or {}
    series = images.get("timeSeries") or graph.get("timeSeries") or {}
    prepared = series.get("preparedValues") or {}
    absolute = prepared.get("absolute") or []
    relative = prepared.get("relative") or []

    history: list[dict[str, Any]] = []
    for index, point in enumerate(absolute):
        label = _point_label(point)
        if label is None:
            continue
        entry: dict[str, Any] = {"date": label, "shows": _to_int(point.get("y"))}
        if index < len(relative):
            share = relative[index].get("y")
            if isinstance(share, (int, float)):
                entry["share_of_all_queries"] = share
        history.append(entry)
    return history


def _normalize_phrases(entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not entries:
        return []
    return [
        {
            "phrase": e.get("text") or e.get("phrase") or "",
            "shows": _to_int(e.get("value") or e.get("count") or 0),
        }
        for e in entries
    ]


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
        Literal["none", "monthly", "weekly", "daily"],
        Field(
            description=(
                "Switch to demand-dynamics mode. 'none' (default) returns frequency "
                "plus related phrases. Any other value returns frequency plus a time "
                "series and NO phrases — the API modes are mutually exclusive. "
                "'monthly' = by month, 'weekly' = by week, 'daily' = by day."
            ),
        ),
    ] = "none",
    start: Annotated[
        str | None,
        Field(
            description=(
                "History mode only. Window start, ISO 'YYYY-MM-DD'. Snapped to the "
                "period boundary (1st of month / Monday). Default: 24 months, "
                "12 weeks or 30 days back depending on history_period."
            ),
        ),
    ] = None,
    end: Annotated[
        str | None,
        Field(
            description=(
                "History mode only. Window end, ISO 'YYYY-MM-DD'. Snapped to the "
                "period boundary and clamped to the last COMPLETE period — the "
                "current month/week and today are never returned."
            ),
        ),
    ] = None,
) -> dict[str, Any]:
    """Get Yandex Wordstat frequency, or demand dynamics over time, for a phrase.

    Use this for: keyword research, demand validation, **seasonality analysis**,
    long-tail discovery. **Russian/Yandex-speaking markets** — this is Yandex's
    equivalent of Google Keyword Planner.

    Do NOT use for: Google volume (Wordstat is Yandex-only — for Google use
    Google Keyword Planner or third-party tools).

    Two mutually exclusive modes, selected by `history_period`:

    - ``none`` (default) — `total_shows`, `containing_phrases`, `similar_queries`
    - anything else — `total_shows` plus `history`; **no phrases**, because the
      upstream API does not return them in this mode

    Returns:
        Dict with:
            - `query` (echoed), `region` (if set)
            - `total_shows` — monthly impressions for the phrase
            - `containing_phrases` / `similar_queries` — words mode only
            - `history` — list of `{date, shows, share_of_all_queries?}`, history mode only.
              `date` is `YYYY-MM` for monthly, `YYYY-MM-DD` for weekly (week start) and daily.
            - `window` — `{start, end, period}` actually requested upstream
            - Or `isError: True` on failure.

    Examples:
        wordstat_query(query="купить iphone")
        → {"total_shows": 187234, "containing_phrases": [...], "similar_queries": [...]}

        wordstat_query(query="реферат", history_period="monthly", start="2024-01-01")
        → {"total_shows": 145052, "history": [{"date": "2024-01", "shows": 2025430}, ...]}
    """
    params: dict[str, Any] = {"query": query}
    if device is not None:
        params["device"] = device
    if region is not None:
        params["lr"] = region

    api_period: str | None = None
    window: dict[str, str] | None = None

    if history_period != "none":
        api_period = _PERIOD_API[history_period]

        parsed: dict[str, date | None] = {"start": None, "end": None}
        for name, raw in (("start", start), ("end", end)):
            if raw is None:
                continue
            try:
                parsed[name] = date.fromisoformat(raw)
            except ValueError:
                return format_error(
                    "INVALID_DATE",
                    f"{name}={raw!r} is not ISO 'YYYY-MM-DD'",
                )

        begin, stop = _resolve_window(api_period, parsed["start"], parsed["end"], date.today())
        params["pagetype"] = "history"
        params["period"] = api_period
        params["start"] = begin.strftime("%d.%m.%Y")
        params["end"] = stop.strftime("%d.%m.%Y")
        window = {
            "start": begin.isoformat(),
            "end": stop.isoformat(),
            "period": history_period,
        }

    result = await fetch_json("/wordstat/new/json", **params)
    if result.get("isError"):
        return result

    out: dict[str, Any] = {"query": query}
    if region is not None:
        out["region"] = region

    if api_period is not None:
        # History mode: frequency lives in `totalValue`, the series in the graph tab.
        out["total_shows"] = _to_int(result.get("totalValue"))
        out["history"] = _extract_history(result)
        if window is not None:
            out["window"] = window
        if not out["history"]:
            out["_raw"] = result
        return out

    popular = _normalize_phrases(result.get("popular"))
    associations = _normalize_phrases(result.get("associations"))
    if popular:
        # First entry is the exact phrase, carrying its own frequency.
        out["total_shows"] = popular[0]["shows"]
        out["containing_phrases"] = popular
    if associations:
        out["similar_queries"] = associations
    if not (popular or associations):
        out["_raw"] = result
    return out
