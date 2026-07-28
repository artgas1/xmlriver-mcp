"""Unit tests for version resolution.

`__version__` used to be a hardcoded constant that nobody bumped: the package
shipped 0.1.9 while the module still claimed 0.1.0, and the release smoke test
printed that stale number as its result.
"""

from importlib.metadata import PackageNotFoundError, version

import pytest

import xmlriver_mcp


def test_version_matches_installed_distribution():
    """The regression guard: a hardcoded constant fails this the moment it drifts.

    Deliberately spells the distribution name out instead of reading `DIST_NAME`.
    Referencing the new constant made this test die with `AttributeError` on the old
    code — passing for the wrong reason, and proving nothing about the drift it exists
    to catch. With a literal it fails on the old code exactly as production did.
    """
    assert xmlriver_mcp.__version__ == version("xmlriver-mcp")


def test_version_is_not_the_sentinel_when_installed():
    """Under the test runner the package is installed, so the fallback must not win."""
    assert xmlriver_mcp.__version__ != xmlriver_mcp.UNINSTALLED_VERSION


def test_falls_back_when_distribution_is_absent(monkeypatch):
    """A source checkout without an install must import, not explode."""

    def _missing(name: str) -> str:
        raise PackageNotFoundError(name)

    monkeypatch.setattr(xmlriver_mcp, "version", _missing)
    assert xmlriver_mcp._resolve_version() == xmlriver_mcp.UNINSTALLED_VERSION


def test_resolve_reads_the_declared_distribution_name(monkeypatch):
    """Guards against the lookup name drifting away from the packaged one."""
    seen: list[str] = []

    def _spy(name: str) -> str:
        seen.append(name)
        return "1.2.3"

    monkeypatch.setattr(xmlriver_mcp, "version", _spy)
    assert xmlriver_mcp._resolve_version() == "1.2.3"
    assert seen == ["xmlriver-mcp"]


@pytest.mark.parametrize("attr", ["DIST_NAME", "UNINSTALLED_VERSION", "__version__"])
def test_public_names_present(attr):
    assert getattr(xmlriver_mcp, attr)
