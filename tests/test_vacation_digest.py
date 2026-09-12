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

import pytest

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


# Kept before the autouse stub replaces it, so the probe's own tests can call the real one.
REAL_WAVES = digest.waves


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """The fleet probe asks GitHub. No test here is allowed to, so it answers `unknown`."""
    monkeypatch.setattr(digest, "waves", lambda now, limit=20: None)


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


def test_a_dark_fleet_is_an_alarm_the_title_carries(monkeypatch) -> None:
    """2026-09-11: the plan job died for 36 hours and this page reported green throughout."""
    monkeypatch.setattr(digest, "journal_activity", lambda now, root=None: (41, 0.2))
    monkeypatch.setattr(digest, "clients", lambda: 2)
    monkeypatch.setattr(digest, "waves", lambda now, limit=20: (35.6, 12))
    title, body = digest.compose(snapshot(), now=NOW.timestamp())
    assert title.startswith("STALLED (fleet dark)")
    assert "last good wave 35.6 h ago, 12 failed since" in body


def test_a_working_fleet_is_not_an_alarm(monkeypatch) -> None:
    monkeypatch.setattr(digest, "journal_activity", lambda now, root=None: (41, 0.2))
    monkeypatch.setattr(digest, "clients", lambda: 2)
    monkeypatch.setattr(digest, "waves", lambda now, limit=20: (0.4, 0))
    title, body = digest.compose(snapshot(), now=NOW.timestamp())
    assert not title.startswith("STALLED")
    assert "last good wave 0.4 h ago, nothing failed since" in body


def test_a_fleet_that_cannot_be_asked_is_not_an_alarm(monkeypatch) -> None:
    """A laptop off the network must still post the rest of the page."""
    monkeypatch.setattr(digest, "journal_activity", lambda now, root=None: (41, 0.2))
    monkeypatch.setattr(digest, "clients", lambda: 2)
    title, body = digest.compose(snapshot(), now=NOW.timestamp())
    assert not title.startswith("STALLED")
    assert "could not be asked from here" in body


def test_the_probe_counts_the_failures_newer_than_the_last_good_wave(monkeypatch) -> None:
    rows = [
        {"conclusion": "failure", "createdAt": "2026-09-12T19:16:42Z"},
        {"conclusion": "cancelled", "createdAt": "2026-09-12T18:00:00Z"},
        {"conclusion": "failure", "createdAt": "2026-09-12T17:05:00Z"},
        {"conclusion": "success", "createdAt": "2026-09-12T15:00:00Z"},
        {"conclusion": "failure", "createdAt": "2026-09-12T14:00:00Z"},
    ]
    monkeypatch.setattr(digest, "gh", lambda args: (0, json.dumps(rows)))
    since, failed = REAL_WAVES(NOW.timestamp())
    assert failed == 2, (
        "a cancelled wave is not a failure, and one older than the good one is not counted"
    )
    assert since == pytest.approx(hours(datetime(2026, 9, 12, 15, tzinfo=UTC)), abs=0.01)


def test_a_probe_github_refuses_reads_as_unknown_rather_than_zero(monkeypatch) -> None:
    monkeypatch.setattr(digest, "gh", lambda args: (1, "gh: not authenticated"))
    assert REAL_WAVES(NOW.timestamp()) is None


def hours(when: datetime) -> float:
    return (NOW.timestamp() - when.timestamp()) / 3600.0
