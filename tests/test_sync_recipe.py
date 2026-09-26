"""The tick's and the bank's fleet steps, read off the justfile and run where they can be.

The drain runs under `set -euo pipefail`, so one workflow GitHub cannot find would stop the
whole tick, and a run that falls out of the listing before a tick downloads it is lost. The
bank books the outcome of every drain it ever banked, so a find approved or ingested later
still gains its banked line, and a drain leaves `incoming/` only once its lines landed.
"""

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from test_fleet_findings import confirmed, store
from test_fleet_leads import LEAD, with_contract
from test_fleet_ledger import STAND_IN, fleet_ledger

ROOT = Path(__file__).resolve().parents[1]
RECIPE = (ROOT / "justfile").read_text(encoding="utf-8")
TICK = RECIPE[RECIPE.index("\nsync fleet=") : RECIPE.index("\nbank ")]
BANK = RECIPE[RECIPE.index("\nbank ") :]
BANK = BANK[: BANK.index("\n\n")]


def _block(recipe: str, first: str, last: str) -> str:
    """The lines from the one starting `first` to the next one that is `last`, dedented."""
    lines = recipe.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(first))
    stop = next(i for i in range(start, len(lines)) if lines[i].rstrip() == last)
    return textwrap.dedent("\n".join(lines[start : stop + 1]))


def _bash(script: str, tmp_path: Path, timeout: int = 30, **env) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + script],
        cwd=tmp_path,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_the_drain_takes_leg_and_read_runs_and_a_404_skips_only_that_workflow(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "gh.log"
    (bin_dir / "gh").write_text(
        f'#!/bin/sh\necho "$*" >> "{log}"\n'
        'case "$*" in\n'
        '*"--workflow leg.yaml"*) echo "HTTP 404: workflow leg.yaml not found" >&2; exit 1 ;;\n'
        '*"--workflow read.yaml"*) printf \'7\\tcompleted\\n8\\tcompleted\\n'
        "9\\tin_progress\\n' ;;\n"
        "esac\n"
    )
    (bin_dir / "gh").chmod(0o755)
    processed = tmp_path / "processed_runs.txt"
    processed.write_text("7\n")
    drain = _block(TICK, "    for WF in leg.yaml read.yaml; do", "    done")
    done = _bash(
        drain,
        tmp_path,
        PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        IN=str(tmp_path / "incoming"),
        PROCESSED=str(processed),
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "gh could not list leg.yaml" in done.stdout
    downloads = [
        ln.split()[2] for ln in log.read_text().splitlines() if ln.startswith("run download")
    ]
    assert downloads == ["8", "9"], "run 7 was processed; 8 and 9 are new"
    assert processed.read_text().split() == ["7", "8"], "an unfinished run is taken again"


# A `gh` that lists runs the way GitHub does: newest first, filtered by `--event`, cut at
# `--limit` (GitHub's own default is 20), and that logs every download.
FAKE_GH = r"""
import json, os, sys
args = sys.argv[1:]
def flag(name, default=None):
    return args[args.index(name) + 1] if name in args else default
if args[:2] == ["run", "list"]:
    runs = json.load(open(os.environ["FAKE_RUNS"]))[flag("--workflow")]
    event = flag("--event")
    runs = [run for run in runs if event in (None, run["event"])]
    for run in runs[: int(flag("--limit", "20"))]:
        print(f"{run['id']}\t{run['status']}")
elif args[:2] == ["run", "download"]:
    with open(os.environ["FAKE_LOG"], "a") as fh:
        fh.write(f"{flag('--repo')} {args[2]}\n")
"""


def test_a_run_a_day_old_is_still_downloaded_and_a_watchdog_run_never_is(tmp_path):
    """Two idle slots and the watchdog start about 330 runs a day. The run whose download a
    sleeping laptop missed is the oldest of them, and the watchdog's runs carry nothing."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(f"#!{sys.executable}\n{FAKE_GH}")
    (bin_dir / "gh").chmod(0o755)
    day = [
        {
            "id": rid,
            "status": "completed",
            "event": "schedule" if rid % 5 == 0 else "workflow_dispatch",
        }
        for rid in range(2330, 2000, -1)
    ]
    reads = [{"id": 3001, "status": "completed", "event": "workflow_dispatch"}]
    runs = tmp_path / "runs.json"
    runs.write_text(json.dumps({"leg.yaml": day, "read.yaml": reads}), encoding="utf-8")
    processed = tmp_path / "processed_runs.txt"
    missed = {2001, 2330}  # the leg run a sleeping laptop missed, and a watchdog run
    processed.write_text("".join(f"{run['id']}\n" for run in day if run["id"] not in missed))
    log = tmp_path / "gh.log"
    drain = _block(TICK, "    for WF in leg.yaml read.yaml; do", "    done")
    done = _bash(
        drain,
        tmp_path,
        timeout=120,
        PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        IN=str(tmp_path / "incoming"),
        PROCESSED=str(processed),
        FAKE_RUNS=str(runs),
        FAKE_LOG=str(log),
    )
    assert done.returncode == 0, done.stdout + done.stderr
    downloads = [ln.split()[1] for ln in log.read_text().splitlines()]
    assert downloads == ["2001", "3001"]
    assert {"2001", "3001"} <= set(processed.read_text().split())


def test_a_drain_of_closed_scout_leads_alone_reaches_the_scribe(tmp_path):
    gate = _block(
        TICK, "    if ! compgen -G", '        && ! compgen -G "$IN/*/scout.md" >/dev/null; then'
    )
    script = gate + " echo nothing; else echo book; fi"
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    assert _bash(script, tmp_path, IN=str(incoming)).stdout.strip() == "nothing"
    (incoming / "some-lead").mkdir()
    (incoming / "some-lead" / "scout.md").write_text("# some-lead\n")
    assert _bash(script, tmp_path, IN=str(incoming)).stdout.strip() == "book"


def test_every_fleet_step_names_the_fleet_and_no_cache_is_read():
    steps = {
        TICK: ("fleet_findings.py drain", "discover_cycle.py"),
        BANK: ("fleet_request.py", "standing_rule.py"),
    }
    for recipe, names in steps.items():
        for name in names:
            line = next(ln for ln in recipe.splitlines() if f"scripts/harness/{name}" in ln)
            assert '--fleet "$FLEET"' in line, name
    queue = [ln for ln in RECIPE.splitlines() if "scripts/round/lead_queue.py" in ln]
    assert queue and not any("--cached" in ln for ln in queue), queue
    assert "wave.yaml" not in RECIPE


def test_the_bank_books_outcomes_after_its_commit_landed_and_before_the_fleet_push():
    """The outcome lines follow the register commit onto `live`, on every bank, and no flag
    from the bank says banked: the store's ingested files do."""
    order = [
        'git commit -q -m "Sync fleet findings $LABEL"',
        "git push -q origin live",
        'fleet_findings.py outcome "$IN" data/fleet_findings/banked/*/',
        "fleet_leads.py",
        "push_fleet.sh",
        "A drain leaves `incoming/` only once its rows are committed.",
    ]
    at = [BANK.index(text) for text in order]
    assert at == sorted(at), order
    assert "--banked" not in BANK


# --- the bank's step d, run in a checkout of its own ------------------------------


def _checkout(tmp_path: Path, fleet_ledger_script: bool = True) -> tuple[Path, Path, dict]:
    """A checkout step d can run in, and the fleet clone it writes to.

    The harness is copied, so its register and its store are this checkout's and never the
    live ones; `uv run python` is this interpreter, and `push_fleet.sh` pushes nothing.
    """
    repo = tmp_path / "repo"
    harness = repo / "scripts/harness"
    harness.mkdir(parents=True)
    for path in (ROOT / "scripts/harness").glob("*.py"):
        shutil.copy(path, harness / path.name)
    (harness / "push_fleet.sh").write_text('echo "push_fleet: pushed"\n', encoding="utf-8")
    (repo / "src").symlink_to(ROOT / "src")
    (repo / "docs/registers").mkdir(parents=True)
    (repo / "data/fleet_findings/banked").mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "uv").write_text(
        '#!/bin/sh\n[ "$1" = run ] && shift\n[ "$1" = python ] && shift\n'
        f'exec "{sys.executable}" "$@"\n'
    )
    (bin_dir / "uv").chmod(0o755)
    fleet = with_contract(tmp_path / "fleet")
    (fleet / "leads").mkdir()
    (fleet / "leads/foo-bar.json").write_text(json.dumps(dict(LEAD, slug="foo-bar")), "utf-8")
    if fleet_ledger_script:
        (fleet / "scripts/ledger.py").write_text(STAND_IN, encoding="utf-8")
    incoming = repo / "data/fleet_findings/incoming"
    confirmed(incoming, "foo-bar", {"status": "priced", "ee": 12000.0})
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "IN": "data/fleet_findings/incoming",
        "FLEET": str(fleet),
        "NEW_ROWS": "",
    }
    return repo, fleet, env


def _decide(repo: Path, decision: str) -> None:
    (repo / "docs/registers/approved-sources-list.md").write_text(
        f"## Pending requests\n\n### foo_bar / artifact_listing\nDecision: {decision}\n",
        encoding="utf-8",
    )


def _bank(repo: Path, env: dict, label: str, ran_a: str, committed: str = "no"):
    step_d = _block(BANK, "    # Every bank books the outcome of every drain", "    fi")
    return _bash(step_d, repo, timeout=180, LABEL=label, RAN_A=ran_a, COMMITTED=committed, **env)


def _keys(fleet: Path) -> list[str]:
    return [line["key"] for line in fleet_ledger.lines(fleet, "outcome")]


def test_a_find_approved_in_a_later_bank_gains_its_banked_line_and_lead(tmp_path):
    """Booked pending in the bank that drained it, then approved by the owner and ingested in
    later banks that hold no find at all: the store's rows, not the drain, bank it."""
    repo, fleet, env = _checkout(tmp_path)
    lead = fleet / "leads/foo-bar.json"
    _decide(repo, "pending")
    done = _bank(repo, env, "20260926T0100Z", ran_a="yes", committed="yes")
    assert done.returncode == 0, done.stdout + done.stderr
    assert _keys(fleet) == ["foo-bar:pending:False"]
    assert (repo / "data/fleet_findings/banked/20260926T0100Z/foo-bar").is_dir()
    assert not any((repo / "data/fleet_findings/incoming").iterdir())
    # The owner merges the approval; the ingest has not run yet.
    _decide(repo, "master")
    store(repo / "data/ark.duckdb", "some_other_source")
    done = _bank(repo, env, "20260926T0200Z", ran_a="no")
    assert done.returncode == 0, done.stdout + done.stderr
    assert _keys(fleet)[-1] == "foo-bar:master:False"
    assert json.loads(lead.read_text())["status"] == "verified"
    # The ingest lands.
    (repo / "data/ark.duckdb").unlink()
    store(repo / "data/ark.duckdb", "foo_bar")
    done = _bank(repo, env, "20260926T0300Z", ran_a="no")
    assert done.returncode == 0, done.stdout + done.stderr
    assert _keys(fleet)[-1] == "foo-bar:master:True"
    assert json.loads(lead.read_text())["status"] == "banked"
    assert _bank(repo, env, "20260926T0400Z", ran_a="no").returncode == 0
    assert len(_keys(fleet)) == 3, "a later bank adds nothing"


def test_outcome_lines_that_did_not_land_leave_the_tick_alive_and_a_later_bank_books_them(tmp_path):
    """A clone without the ledger script books nothing and the drain still moves: every bank
    books the drains under `banked/` too, so the line lands once the clone has the script."""
    repo, fleet, env = _checkout(tmp_path, fleet_ledger_script=False)
    _decide(repo, "pending")
    done = _bank(repo, env, "20260926T0100Z", ran_a="yes", committed="yes")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "the outcome lines did not land" in done.stdout
    assert (repo / "data/fleet_findings/banked/20260926T0100Z/foo-bar/finding.json").is_file()
    assert _keys(fleet) == []
    (fleet / "scripts/ledger.py").write_text(STAND_IN, encoding="utf-8")
    done = _bank(repo, env, "20260926T0200Z", ran_a="no")
    assert done.returncode == 0, done.stdout + done.stderr
    assert _keys(fleet) == ["foo-bar:pending:False"]
