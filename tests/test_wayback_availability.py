"""The two defects the engine exists to survive, and the XIII rule it enforces."""

from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "wayback_availability", REPO / "scripts/engines/wayback_availability.py"
)
engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(engine)


def answer(url: str, stamp: str) -> dict:
    """His body shape: the top level echoes the CALLER's timestamp back."""
    return {
        "url": "example.com",
        "timestamp": "20010701",
        "archived_snapshots": {
            "closest": {"available": True, "url": url, "timestamp": stamp, "status": "200"}
        },
    }


def test_the_echoed_timestamp_is_not_the_answer(monkeypatch) -> None:
    """Reading the last `timestamp` makes every probe report a perfect hit."""
    body = answer("http://example.com/", "19990412235959")
    body["timestamp"] = "20010701"
    monkeypatch.setattr(
        engine,
        "ask",
        lambda d: (
            body["archived_snapshots"]["closest"]["url"],
            body["archived_snapshots"]["closest"]["timestamp"],
            0.0,
        ),
    )
    assert engine.probe("example.com") is None, "a 1999 capture may not date 2001"


def test_a_www_answer_is_not_evidence_for_the_bare_name(monkeypatch) -> None:
    """XIII: a capture of `www.example.com` does not establish `example.com`."""
    monkeypatch.setattr(engine, "ask", lambda d: ("http://www.example.com/", "20010704120000", 0.0))
    found = engine.probe("example.com")
    assert found is not None
    assert found["host"] == "www.example.com" != found["asked"]


def test_an_exact_answer_is_evidence_for_the_name_asked(monkeypatch) -> None:
    monkeypatch.setattr(engine, "ask", lambda d: ("http://example.com:80/", "20010704120000", 0.0))
    found = engine.probe("example.com")
    assert found is not None and found["host"] == "example.com"


def test_the_two_grains_go_to_two_journals(tmp_path, monkeypatch) -> None:
    """A variant never lands in the registrable journal, which is the whole point."""
    replies = {
        "a.com": ("http://a.com/", "20010704120000", 0.0),
        "b.com": ("http://www.b.com/", "20010704120000", 0.0),
        "c.com": (None, None, 0.0),
    }
    monkeypatch.setattr(engine, "ask", lambda d: replies[d])
    monkeypatch.setattr(engine, "WORKERS", 1)
    totals = engine.run(["a.com", "b.com", "c.com"], 1e12, tmp_path / "exact", tmp_path / "host")
    assert totals == {"asked": 3, "exact": 1, "variant": 1, "empty": 1}

    exact = next((tmp_path / "exact").glob("*.jsonl.gz"))
    rows = [json.loads(x) for x in gzip.open(exact, "rt") if x.strip()]
    assert rows == [
        {"domain": "a.com", "status": 200, "years": [2001], "strategy": "wayback_availability"}
    ]

    host = next((tmp_path / "host").glob("*.jsonl.gz"))
    rows = [json.loads(x) for x in gzip.open(host, "rt") if x.strip()]
    assert rows == [{"url": "http://www.b.com/", "timestamp": "20010704120000"}]
