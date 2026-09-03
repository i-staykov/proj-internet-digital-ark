"""`just brief` reads a snapshot and nothing else.

It is injected at session start, so the two things that matter are that it fits
in thirty lines and that it can never block: no store, no ssh, no `duckdb`
import. The snapshot side is tested too, because a field the writer drops is a
line the reader loses.
"""

import importlib.util
import json
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIEF_PY = ROOT / "scripts/agents/brief.py"
FIXTURE = ROOT / "tests/fixtures/brief.json"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


brief = _load("brief", BRIEF_PY)
build_round_state = _load("build_round_state", ROOT / "scripts/round/build_round_state.py")

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def fresh_snapshot(**overrides) -> dict:
    snapshot = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snapshot["written_at"] = (NOW - timedelta(hours=2)).isoformat(timespec="seconds")
    snapshot.update(overrides)
    return snapshot


def test_fresh_brief_leads_with_its_age_and_fits_thirty_lines():
    handoff = ("\n".join(f"handoff line {i}" for i in range(60)), NOW - timedelta(hours=1))
    out = brief.render(fresh_snapshot(), handoff, NOW).splitlines()
    assert len(out) <= brief.MAX_LINES
    assert out[0].startswith("brief written 2.0 h ago")
    assert "round 7 against merged260830" in out[1]
    assert "312,456 net-new pairs" in out[1] and "1.2527%" in out[1]
    assert "544,538 EE short of 5%" in out[1]
    assert "collector local: up 2-03:14:22" in "\n".join(out)
    assert "collector vps: NOT RUNNING" in out
    assert "2 approvals pending, 3 open decisions" in "\n".join(out)
    assert any("Hostnames are retained" in ln for ln in out)
    assert "-- private/handoff.md, 1.0 h old --" in out
    assert out[-1].endswith("more lines in private/handoff.md)")


def test_past_the_gate_reads_as_past_not_short():
    out = brief.render(fresh_snapshot(distance_to_gate_ee=-1200.5), None, NOW)
    assert "1,200 EE past 5%" in out


def test_missing_snapshot_is_one_line():
    out = brief.render(None, None, NOW)
    assert out == "no brief: data/brief.json is missing, run `just state`"


def test_stale_snapshot_is_one_line_and_still_shows_the_handoff():
    stale = fresh_snapshot(written_at=(NOW - timedelta(days=3)).isoformat())
    assert brief.render(stale, None, NOW) == (
        "brief is 3.0 days old (2026-08-30T12:00:00+00:00): run `just state`"
    )
    out = brief.render(stale, ("continue with E5.3", NOW), NOW).splitlines()
    assert out[0].startswith("brief is 3.0 days old")
    assert out[-1] == "continue with E5.3"


def test_load_reads_the_files_it_is_pointed_at(tmp_path):
    snap = tmp_path / "brief.json"
    snap.write_text(json.dumps(fresh_snapshot(written_at=datetime.now(UTC).isoformat())))
    handoff = tmp_path / "handoff.md"
    handoff.write_text("last prompt: finish the brief\n")
    out = brief.load(snap, handoff).splitlines()
    assert out[0].startswith("brief written 0.0 h ago")
    assert out[-1] == "last prompt: finish the brief"
    assert brief.load(tmp_path / "absent.json", handoff).splitlines()[0].startswith("no brief")


def test_brief_never_imports_duckdb_and_runs_under_a_second(tmp_path):
    """Run in a fresh interpreter so the assertion is about this script's imports
    and not about whatever the test session already loaded."""
    assert "duckdb" not in BRIEF_PY.read_text(encoding="utf-8")
    snap = tmp_path / "brief.json"
    snap.write_text(json.dumps(fresh_snapshot(written_at=datetime.now(UTC).isoformat())))
    probe = (
        "import importlib.util, sys; from pathlib import Path\n"
        f"spec = importlib.util.spec_from_file_location('brief', {str(BRIEF_PY)!r})\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        f"print(m.load(Path({str(snap)!r}), Path({str(tmp_path / 'none.md')!r})))\n"
        "assert 'duckdb' not in sys.modules and 'ark' not in sys.modules, 'heavy import'\n"
    )
    started = time.monotonic()
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    elapsed = time.monotonic() - started
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("brief written 0.0 h ago")
    assert elapsed < 1.0, f"brief.py took {elapsed:.2f}s"


def test_collector_lines_take_the_first_line_per_machine_and_drop_the_address():
    engines = (
        "\n== clocks (both machines) ==\n   local 2026-09-02 10:00:00 UTC   |   10:00:00Z\n"
        "\n== local ==\n   up 03:12:33 bash scripts/engines/supervise_cdx_pool.sh 1 2 3\n"
        "   journal cdx_q0_20260902T0900Z.jsonl.gz.part\n"
        "\n== VPS (ark@203.0.113.7) ==\n   NOT RUNNING\n   last finished batch:\n"
        "\n== journals on the VPS not yet copied here ==\n"
        "   UNKNOWN: could not reach ark@203.0.113.7\n"
    )
    lines = build_round_state.collector_lines(engines)
    assert lines == {
        "local": "up 03:12:33 bash scripts/engines/supervise_cdx_pool.sh 1 2 3",
        "vps": "NOT RUNNING",
    }
    assert "203.0.113.7" not in json.dumps(lines)
    assert build_round_state.collector_lines("(timed out after 120s: bash x.sh)") == {
        "local": "UNKNOWN",
        "vps": "UNKNOWN",
    }


def test_the_status_probe_fragment_never_reaches_the_printed_line():
    """The VPS section is produced by `bash -c '... pgrep -f supervise_cdx_pool.sh
    ...'` over ssh, so the remote `ps` matches the question and the snapshot stores
    its shell text. The fixture is that output; none of it may be printed."""
    engines = (ROOT / "tests/fixtures/engine_status_probe.txt").read_text(encoding="utf-8")
    collectors = build_round_state.collector_lines(engines)
    assert "pgrep" in collectors["vps"], "fixture no longer holds the shell fragment"
    out = brief.render(fresh_snapshot(collectors=collectors), None, NOW)
    for fragment in ("pgrep", "bash -c", "/projects", "||", "/dev/null"):
        assert fragment not in out, f"{fragment!r} reached the brief"
    assert "collector vps: unclear: the status probe matched itself" in out
    assert "collector local: NOT RUNNING" in out


def test_collector_state_keeps_the_status_and_drops_the_command():
    assert brief.collector_state("NOT RUNNING") == "NOT RUNNING"
    assert brief.collector_state("unreachable (VPN down?)") == "unreachable"
    assert brief.collector_state("") == "UNKNOWN"
    assert (
        brief.collector_state("up 2-03:14:22 bash scripts/engines/supervise_cdx_pool.sh 1 2 900")
        == "up 2-03:14:22 supervise_cdx_pool.sh"
    )
    assert brief.collector_state("up 04:11 python3 something_else.py") == "up 04:11"


def test_pending_amendments_are_the_rows_with_a_pending_cell(tmp_path):
    ledger = tmp_path / "brief_amendments.md"
    ledger.write_text(
        "| Round | His document | Where it is on disk |\n"
        "|---|---|---|\n"
        "| after phase-1 | feedback, 2026-07-27 | `feedback-phase-1/` |\n"
        "\n"
        '| 2026-09-01 | "Hostnames are retained." | unclassified | pending | pending |\n'
        '| 2026-08-20 | "S_i = k * p_i / t_i" | scoring | figures.py | rules.md |\n',
        encoding="utf-8",
    )
    assert build_round_state.pending_amendments(ledger) == [
        {"date": "2026-09-01", "text": '"Hostnames are retained."'}
    ]
    assert build_round_state.pending_amendments(tmp_path / "absent.md") == []
    # the live ledger parses, whatever it currently holds
    assert isinstance(build_round_state.pending_amendments(), list)


def test_brief_snapshot_carries_what_the_reader_prints():
    head = {
        "pairs": 312456,
        "domains": 98765,
        "ee": "182034.5678",
        "evidence": 1,
        "_stats": {
            "ee_netnew": Decimal("182034.5678"),
            "ee_netnew_growth_pct": Decimal("1.2527"),
        },
    }
    snapshot = build_round_state.brief(head, "== local ==\n   NOT RUNNING\n", 2, 3)
    assert set(snapshot) == set(json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert snapshot["netnew_ee"] == 182034.5678 and snapshot["percent"] == 1.2527
    assert snapshot["round"] == build_round_state.CURRENT_ROUND_LABEL
    gate = build_round_state.REVIEWER_BASELINE_EE * 5 / 100 - Decimal("182034.5678")
    assert snapshot["distance_to_gate_ee"] == round(float(gate), 4)
    assert snapshot["collectors"] == {"local": "NOT RUNNING", "vps": "UNKNOWN"}
    assert snapshot["waiting_on_human"] == {"approvals": 2, "open_decisions": 3}
    # the reader takes the writer's output as it is
    brief.parse_stamp(snapshot["written_at"])
    assert brief.render(snapshot, None, datetime.now(UTC)).startswith("brief written 0.0 h")
    assert json.dumps(snapshot)
