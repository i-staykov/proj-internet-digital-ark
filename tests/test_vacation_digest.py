"""The digest's fleet line: Leg runs that dealt, never the watchdog that only starts slots.

`Leg watchdog` runs three times an hour and succeeds whether or not a slot is alive, so a
digest that counted it would read a dead fleet as green, the failure this line exists for.
"""

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "vacation_digest", Path(__file__).resolve().parents[1] / "scripts/harness/vacation_digest.py"
)
digest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(digest)

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


def _run(title: str, conclusion: str | None, hours_ago: float) -> dict:
    at = (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"displayTitle": title, "conclusion": conclusion, "createdAt": at}


def _gh(monkeypatch, rows: list[dict]) -> list[list[str]]:
    asked = []

    def gh(args):
        asked.append(args)
        return 0, json.dumps(rows)

    monkeypatch.setattr(digest, "gh", gh)
    return asked


def test_the_watchdogs_green_runs_do_not_hide_a_failing_leg(monkeypatch) -> None:
    asked = _gh(
        monkeypatch,
        [
            _run("Leg watchdog", "success", 0.1),
            _run("Leg watchdog", "success", 0.4),
            _run("Leg slot 0", "failure", 1.0),
            _run("Leg slot 0", "success", 5.0),
        ],
    )
    since, failed = digest.waves(NOW.timestamp())
    assert (round(since, 1), failed) == (5.0, 1)
    assert since > digest.FLEET_STALL_HOURS, "a fleet five hours dark must read dark"
    assert asked[0][asked[0].index("--workflow") + 1] == "leg.yaml"


def test_only_watchdog_runs_is_a_fleet_that_dealt_nothing(monkeypatch) -> None:
    """Not "could not be asked": GitHub answered, and no leg worked in what it listed."""
    _gh(monkeypatch, [_run("Leg watchdog", "success", h / 3) for h in range(9)])
    fleet = digest.waves(NOW.timestamp())
    assert fleet == (None, 0)
    assert digest.fleet_line(fleet).startswith("no leg has worked in the last 50 runs")
