"""The digest is the only thing that reaches a phone, so it has to be readable and safe.

Two properties are worth a test. **Nothing shaped like an address may leave the machine**,
because the issue is on the public repository and the collector host is deliberately not in
it. And **the alarm has to be in the title**, since a phone shows a title and a timestamp
and nothing else until somebody taps it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/harness"))

_spec = importlib.util.spec_from_file_location(
    "vacation_digest", ROOT / "scripts/harness/vacation_digest.py"
)
digest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(digest)

NOW = datetime(2026, 9, 14, 6, 0, tzinfo=UTC)


def snapshot(**overrides) -> dict:
    base = {
        "written_at": (NOW - timedelta(minutes=20)).isoformat(timespec="seconds"),
        "baseline": "merged260908",
        "round": "10",
        "round_since": "2026-09-10 13:24:00+00",
        "round_pairs": 412003,
        "round_ee": 233981.4412,
        "round_distance_to_gate_ee": 1510373.35,
        "netnew_pairs": 3811565,
        "netnew_ee": 2109254.77,
        "percent": 6.046,
        "gate_pct": 5.0,
        "distance_to_gate_ee": -364899.98,
        "collectors": {"local": "up 05:00:00 sweep", "vps": "no collector loop"},
        "waiting_on_human": {"approvals": 0, "open_decisions": 5},
        "pending_amendments": [],
    }
    base.update(overrides)
    return base


def test_the_share_of_the_gate_is_the_headline(monkeypatch) -> None:
    monkeypatch.setattr(digest, "journal_activity", lambda now, root=None: (41, 0.2))
    monkeypatch.setattr(digest, "clients", lambda: 2)
    title, body = digest.compose(snapshot(), now=NOW.timestamp())
    assert title.startswith("round 10 at 13.4% of the gate")
    assert "1,510,373 EE short" in body
    assert "412,003 records" in body


def test_a_quiet_collector_puts_the_word_stalled_in_the_title(monkeypatch) -> None:
    """A phone shows the title. An alarm anywhere else is an alarm nobody sees."""
    monkeypatch.setattr(digest, "journal_activity", lambda now, root=None: (3, 9.5))
    monkeypatch.setattr(digest, "clients", lambda: 0)
    title, _ = digest.compose(snapshot(), now=NOW.timestamp())
    assert title.startswith("STALLED (collectors quiet)")


def test_a_quiet_bank_is_an_alarm_too(monkeypatch) -> None:
    monkeypatch.setattr(digest, "journal_activity", lambda now, root=None: (41, 0.2))
    monkeypatch.setattr(digest, "clients", lambda: 2)
    stale = snapshot(written_at=(NOW - timedelta(hours=7)).isoformat(timespec="seconds"))
    title, _ = digest.compose(stale, now=NOW.timestamp())
    assert "sync quiet" in title


def test_nothing_shaped_like_an_address_reaches_the_body(monkeypatch) -> None:
    """The repository is public. The host is not in it and must not arrive by this road."""
    monkeypatch.setattr(digest, "journal_activity", lambda now, root=None: (41, 0.2))
    monkeypatch.setattr(digest, "clients", lambda: 2)
    monkeypatch.setattr(
        digest, "triage_top", lambda *a, **kw: (2, [(90, "host at 10.1.0.6 / typed")])
    )
    _, body = digest.compose(snapshot(), now=NOW.timestamp())
    assert "10.1.0.6" not in body
    assert "sources found and not priced" in body


def test_a_brief_without_the_window_still_composes(monkeypatch) -> None:
    """The digest may run against a snapshot written before the window figures existed."""
    monkeypatch.setattr(digest, "journal_activity", lambda now, root=None: (41, 0.2))
    monkeypatch.setattr(digest, "clients", lambda: 2)
    old = snapshot()
    for key in ("round_ee", "round_pairs", "round_since", "round_distance_to_gate_ee"):
        del old[key]
    title, body = digest.compose(old, now=NOW.timestamp())
    assert "round 10" in title
    assert "364,900 EE past" in body


def test_the_shipped_brief_can_be_composed() -> None:
    """Whatever the last bank wrote must render, or the digest is a daily crash."""
    brief = ROOT / "data/brief.json"
    if not brief.is_file():
        return
    title, body = digest.compose(json.loads(brief.read_text(encoding="utf-8")))
    assert title and "Round" in body
