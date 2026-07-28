# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.9] — 2026-07-29

### Fixed

- `wordstat_query` history mode never worked. The tool sent `history=month`, but the
  XMLRiver endpoint expects `pagetype=history` together with `period`. An unknown
  parameter is silently ignored upstream, so the call returned a normal words-mode
  response with HTTP 200 — the documented `history` field simply never appeared, and
  nothing surfaced the failure. The response parser had the mirror-image bug: it read
  only `popular`/`associations` and keyed on `result["history"]`, which no XMLRiver
  response contains in any mode.

### Added

- `start` / `end` parameters (ISO `YYYY-MM-DD`) for the history window. They are
  required in practice: without an explicit window the endpoint returns a stale range
  that stops several months short of the available data.
- Automatic window alignment per period — month snaps to 1st/last day, week to
  Monday/Sunday, and the current incomplete period is never requested. Windows shorter
  than the upstream three-period minimum are widened backwards instead of failing with
  `{"code": "400"}`.
- `daily` history period, alongside the existing `monthly` / `weekly`.
- `share_of_all_queries` on each history point (the phrase's share of all Yandex
  queries) — useful for seasonality work, since it controls for total search growth.
- `window` in the response, echoing the range actually requested upstream.
- `tests/unit/test_wordstat.py` — the module had no test coverage at all.

### Changed

- History and words are now explicitly documented as **mutually exclusive** modes: a
  `pagetype=history` response carries no phrases, so `history_period != "none"` returns
  `total_shows` (from `totalValue`) plus `history`, and no `containing_phrases` /
  `similar_queries`.
- History point dates are normalized to one shape. Upstream labels them three different
  ways — `{year, month}` with a 0-based month for months, `x` for weeks, `day` for days.

### Removed

- `device_breakdown` from the documented response. It keyed on a `device` field that
  XMLRiver does not return, so it was never populated — same defect class as `history`.

## [0.1.8] — 2026-05-18

### Added

- `assets/demo-wordstat.png` — static demo screenshot showing a real Wordstat query in Claude (user prompt → `wordstat_query` tool call → JSON output with real frequency data → SEO insight). Placed at top of README, between tagline and Quickstart.

## [0.1.7] — 2026-05-18

### Fixed

- `server.json` `icons[].sizes` schema — was string, must be array of strings per Official MCP Registry validation. v0.1.6 failed registry publish with `cannot unmarshal string into Go struct field Icon.icons.sizes of type []string`.

## [0.1.6] — 2026-05-18

### Added

- **Icon assets** (`assets/icon-192.png`, `icon-48.png`, `icon.svg`) — minimalist "X" mark on blue gradient. Wired into `server.json` `icons[]` array per SEP-2127 Server Cards spec — appears in Smithery/Glama/Claude Desktop/Cursor catalogs.
- **Install-action badges** in README header — "Add to Cursor", "Add to VS Code", "Add to Claude Desktop" with deeplink configs.
- **Downloads badge** (PePy) for at-a-glance adoption signal.

## [0.1.5] — 2026-05-18

Initial public release.

### Tools

- `google_search` — Google SERP with country, language, device, page, date filter, additional blocks (ads, FAQ, knowledge graph, AI Overview)
- `yandex_search` — Yandex SERP with region, domain, language, device, page, date filter
- `yandex_search_api_v2` — official Yandex Search API v2 proxy (cleaner JSON)
- `wordstat_query` — Yandex Wordstat keyword frequency, similar/containing phrases, history
- `check_url_indexed` — index check in Google and Yandex
- `get_balance`, `get_tariff`, `get_tariff_expire`, `get_cost` — account ops

### Infrastructure

- FastMCP 3.x stdio server, Python 3.10+
- HTTPX client with tenacity retry + structured error returns
- 19 unit tests (XML parser, client, account tools) + 4 integration tests against live XMLRiver API
- CI: Python 3.10-3.13 matrix
- Publish-and-fan-out workflow on tag `v*`:
  - PyPI release via `UV_PUBLISH_TOKEN`
  - Official MCP Registry via `mcp-publisher` CLI + GitHub OIDC
  - Glama crawler topics (`mcp`, `model-context-protocol`)
  - awesome-mcp-servers PR via `scripts/insert_awesome_mcp_entry.py` (idempotent)

[Unreleased]: https://github.com/artgas1/xmlriver-mcp/compare/v0.1.8...HEAD
[0.1.8]: https://github.com/artgas1/xmlriver-mcp/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/artgas1/xmlriver-mcp/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/artgas1/xmlriver-mcp/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/artgas1/xmlriver-mcp/releases/tag/v0.1.5
