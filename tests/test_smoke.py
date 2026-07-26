"""Smoke test: the `ark` package imports and its entry point is callable.

Trivial on purpose: its real job is to prove `uv run pytest` is wired up and green
from day one. Every later module (db, canonicalize, cdx, whois) adds its own tests
alongside this one.
"""

import ark


def test_package_imports() -> None:
    assert ark.__name__ == "ark"


def test_entrypoint_is_callable() -> None:
    assert callable(ark.main)
