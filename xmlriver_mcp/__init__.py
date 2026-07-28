"""xmlriver-mcp — MCP server for XMLRiver Google/Yandex/Wordstat API."""

from importlib.metadata import PackageNotFoundError, version

DIST_NAME = "xmlriver-mcp"

# Sentinel for source checkouts that were never installed. Deliberately not a
# release-shaped number: a hardcoded one drifts from pyproject.toml the moment
# someone forgets to bump it, which is exactly the bug this module used to have.
UNINSTALLED_VERSION = "0.0.0.dev0"


def _resolve_version() -> str:
    """Read the version from installed distribution metadata.

    `pyproject.toml` is the single source of truth. Keeping a second copy here
    let it drift nine releases behind — the package shipped 0.1.9 while this
    module still claimed 0.1.0.
    """
    try:
        return version(DIST_NAME)
    except PackageNotFoundError:
        return UNINSTALLED_VERSION


__version__ = _resolve_version()
