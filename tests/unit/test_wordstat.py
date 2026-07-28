"""Unit tests for the Wordstat tool — mocked client.

Focus: the history mode, which was silently broken (wrong upstream parameter name
plus a parser that dropped the series). See `test_history_mode_*` below.
"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _set_creds(monkeypatch):
    monkeypatch.setenv("XMLRIVER_USER", "12345")
    monkeypatch.setenv("XMLRIVER_KEY", "fakekey123")
    import xmlriver_mcp.client as client_mod

    client_mod._client = None
    client_mod.USER = "12345"
    client_mod.KEY = "fakekey123"


def _history_payload(points, total="145052"):
    return {
        "graph": {
            "images": {"timeSeries": {"preparedValues": {"absolute": points}}},
            "noData": False,
        },
        "map": {},
        "table": {},
        "totalValue": total,
    }


WORDS_PAYLOAD = {
    "popular": [
        {"isAssociations": False, "value": "145052", "text": "реферат"},
        {"isAssociations": False, "value": "12 345", "text": "реферат по истории"},
    ],
    "associations": [{"isAssociations": True, "value": "553797", "text": "доклад на тему"}],
}


# --- regression: the bug this module was fixed for ------------------------------------


@pytest.mark.asyncio
async def test_history_mode_sends_pagetype_not_history_param():
    """The upstream parameter is `pagetype=history`; `history=` is silently ignored.

    Sending the wrong name returned a valid words-mode response, so the failure was
    invisible from the status code — this asserts on the request we actually make.
    """
    from xmlriver_mcp.tools.wordstat import wordstat_query

    mock = AsyncMock(return_value=_history_payload([{"year": 2026, "month": 0, "y": 1019109}]))
    with patch("xmlriver_mcp.tools.wordstat.fetch_json", mock):
        await wordstat_query(query="реферат", history_period="monthly")

    sent = mock.call_args.kwargs
    assert sent.get("pagetype") == "history"
    assert sent.get("period") == "month"
    assert "history" not in sent, "the API has no `history` parameter — it is ignored"
    # An implicit window is stale upstream (it stops months short), so both bounds are sent.
    assert "start" in sent
    assert "end" in sent


@pytest.mark.asyncio
async def test_history_mode_returns_series():
    """`history` must actually reach the caller — the old parser dropped it."""
    from xmlriver_mcp.tools.wordstat import wordstat_query

    points = [
        {"year": 2026, "month": 0, "y": 1019109},
        {"year": 2026, "month": 1, "y": 1123456},
    ]
    mock = AsyncMock(return_value=_history_payload(points))
    with patch("xmlriver_mcp.tools.wordstat.fetch_json", mock):
        result = await wordstat_query(query="реферат", history_period="monthly")

    assert result.get("history") == [
        {"date": "2026-01", "shows": 1019109},
        {"date": "2026-02", "shows": 1123456},
    ]
    assert result.get("total_shows") == 145052, "frequency comes from totalValue in history mode"
    assert result.get("window", {}).get("period") == "monthly"


# --- point shapes differ per period ---------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("period", "point", "expected"),
    [
        ("monthly", {"year": 2024, "month": 11, "y": 100}, "2024-12"),
        ("weekly", {"month": None, "x": "2026-07-06", "y": 28211}, "2026-07-06"),
        ("daily", {"month": None, "day": "2026-07-24", "y": 2296}, "2026-07-24"),
    ],
)
async def test_point_label_per_period(period, point, expected):
    """XMLRiver names the date field three different ways depending on the period."""
    from xmlriver_mcp.tools.wordstat import wordstat_query

    mock = AsyncMock(return_value=_history_payload([point]))
    with patch("xmlriver_mcp.tools.wordstat.fetch_json", mock):
        result = await wordstat_query(query="реферат", history_period=period)

    assert result["history"] == [{"date": expected, "shows": point["y"]}]


@pytest.mark.asyncio
async def test_relative_share_included_when_present():
    from xmlriver_mcp.tools.wordstat import wordstat_query

    payload = _history_payload([{"year": 2026, "month": 0, "y": 1019109}])
    payload["graph"]["images"]["timeSeries"]["preparedValues"]["relative"] = [
        {"year": 2026, "month": 0, "y": 0.00113}
    ]
    with patch("xmlriver_mcp.tools.wordstat.fetch_json", AsyncMock(return_value=payload)):
        result = await wordstat_query(query="реферат", history_period="monthly")

    assert result["history"][0]["share_of_all_queries"] == 0.00113


# --- window alignment -----------------------------------------------------------------


def test_month_window_snaps_to_month_boundaries():
    from xmlriver_mcp.tools.wordstat import _resolve_window

    begin, stop = _resolve_window(
        "month", date(2024, 3, 17), date(2026, 6, 10), today=date(2026, 7, 29)
    )
    assert begin == date(2024, 3, 1)
    assert stop == date(2026, 6, 30)


def test_month_window_never_includes_current_month():
    from xmlriver_mcp.tools.wordstat import _resolve_window

    _, stop = _resolve_window("month", None, date(2026, 7, 29), today=date(2026, 7, 29))
    assert stop == date(2026, 6, 30), "the running month is incomplete and is rejected upstream"


def test_short_window_is_widened_instead_of_failing():
    """One month violates the 3-period minimum — the API answers `{"code": "400"}`."""
    from xmlriver_mcp.tools.wordstat import _resolve_window

    begin, stop = _resolve_window(
        "month", date(2026, 6, 1), date(2026, 6, 30), today=date(2026, 7, 29)
    )
    assert stop == date(2026, 6, 30)
    assert begin == date(2026, 4, 1), "widened backwards to three months"


def test_week_window_snaps_monday_to_sunday():
    from xmlriver_mcp.tools.wordstat import _resolve_window

    # 2026-07-29 is a Wednesday; the last complete week ends Sunday 2026-07-26.
    begin, stop = _resolve_window(
        "week", date(2026, 7, 8), date(2026, 7, 26), today=date(2026, 7, 29)
    )
    assert begin.weekday() == 0, "start must be a Monday"
    assert stop.weekday() == 6, "end must be a Sunday"
    assert stop == date(2026, 7, 26)


def test_day_window_excludes_today():
    from xmlriver_mcp.tools.wordstat import _resolve_window

    _, stop = _resolve_window("day", None, date(2026, 7, 29), today=date(2026, 7, 29))
    assert stop < date(2026, 7, 29), "upstream rejects today as `end`"


# --- errors and backward compatibility -------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_date_returns_structured_error():
    from xmlriver_mcp.tools.wordstat import wordstat_query

    mock = AsyncMock()
    with patch("xmlriver_mcp.tools.wordstat.fetch_json", mock):
        result = await wordstat_query(query="реферат", history_period="monthly", start="01.01.2024")

    assert result["isError"] is True
    assert result["errorCode"] == "INVALID_DATE"
    # A malformed request must not cost an API unit.
    mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_words_mode_unchanged():
    """Default mode keeps its old shape — history support must not disturb it."""
    from xmlriver_mcp.tools.wordstat import wordstat_query

    mock = AsyncMock(return_value=WORDS_PAYLOAD)
    with patch("xmlriver_mcp.tools.wordstat.fetch_json", mock):
        result = await wordstat_query(query="реферат")

    assert result["total_shows"] == 145052
    assert result["containing_phrases"][1] == {"phrase": "реферат по истории", "shows": 12345}
    assert result["similar_queries"] == [{"phrase": "доклад на тему", "shows": 553797}]
    assert "history" not in result
    assert "pagetype" not in mock.call_args.kwargs


@pytest.mark.asyncio
async def test_upstream_error_is_passed_through():
    from xmlriver_mcp.tools.wordstat import wordstat_query

    error = {"isError": True, "errorCode": "XMLRIVER_400", "content": []}
    with patch("xmlriver_mcp.tools.wordstat.fetch_json", AsyncMock(return_value=error)):
        result = await wordstat_query(query="реферат", history_period="monthly")

    assert result == error
