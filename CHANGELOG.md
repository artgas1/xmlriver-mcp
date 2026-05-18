# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.4] — 2026-05-18

### Changed

- Cleaned README and example queries — removed unrelated org references that crept in during initial release. Previous versions 0.1.0–0.1.3 yanked from PyPI.

## [0.1.3] — 2026-05-18

### Added

- **awesome-mcp PR automation in workflow** — `scripts/insert_awesome_mcp_entry.py` (standalone, testable, idempotent) + new `awesome-mcp-pr` job in publish.yml. Re-runs skip if PR already opened (via `gh pr list` check). Future MCPs published from this skill template get auto-submission.

### Fixed

- `pyproject.toml` ruff config: added `RUF002` and `RUF003` to ignore (Cyrillic in docstrings/comments OK for Russian SEO MCP)

## [0.1.2] — 2026-05-18

### Added

- `mcp-name: io.github.artgas1/xmlriver-mcp` marker в README — required by Official MCP Registry для ownership validation. Registry проверяет marker присутствие в PyPI README перед accepting submission.

### Note

This is a re-publish only to satisfy registry validation — no functional changes from 0.1.1.

## [0.1.1] — 2026-05-18

### Added

- `server.json` manifest (Official MCP Registry schema) — declares package on registry.modelcontextprotocol.io
- `glama.json` ownership claim for Glama.ai indexing
- `.mcp-submit-state.json` for tracking fan-out submissions across registries
- Real CI workflows — previous v0.1.0 had empty workflow files; replaced with working test + publish-and-fan-out

### Changed

- `.github/workflows/publish.yml` rebuilt as **publish-and-fan-out** workflow:
  - Builds + publishes to PyPI (token-based via `PYPI_API_TOKEN`)
  - Publishes to Official MCP Registry via `mcp-publisher` CLI + GitHub OIDC
  - Auto-adds `mcp` and `model-context-protocol` topics for Glama crawler
  - Opens PR to `punkpeye/awesome-mcp-servers` (first-time only, idempotent via state file)
  - Verifies clean install from PyPI

## [0.1.0] — 2026-05-18

### Added

- Initial release.
- **Google SERP** parsing: `google_search` tool with country, language, device, page, date filter, additional blocks (ads, FAQ, knowledge graph, AI Overview).
- **Yandex SERP** parsing: `yandex_search` tool with region, domain, language, device, page, date filter.
- **Yandex Search API v2** proxy: `yandex_search_api_v2` for clean structured output.
- **Wordstat**: `wordstat_query` for keyword frequency, device breakdown, history, similar queries.
- **Indexing**: `check_url_indexed` for Google and Yandex.
- **Account ops**: `get_balance`, `get_tariff`, `get_tariff_expire`, `get_cost`.
- Unit tests (XML parser, client, account tools) and integration tests (live API).
- CI workflow (test on Python 3.10-3.13 + MCP Inspector smoke).
- PyPI publish workflow with trusted publishing.

[Unreleased]: https://github.com/artgas1/xmlriver-mcp/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/artgas1/xmlriver-mcp/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/artgas1/xmlriver-mcp/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/artgas1/xmlriver-mcp/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/artgas1/xmlriver-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/artgas1/xmlriver-mcp/releases/tag/v0.1.0
