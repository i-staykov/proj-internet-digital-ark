"""The tick's and the bank's fleet steps, read off the justfile and run where they can be.

The drain runs under `set -euo pipefail`, so one workflow GitHub cannot find would stop the
whole tick; the bank's outcome lines say `banked` only once its commit has landed.
"""

import os
import subprocess
import textwrap
from pathlib import Path

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


def _bash(script: str, tmp_path: Path, **env) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + script],
        cwd=tmp_path,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=30,
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
    """An outcome line's key carries `banked`, so a `banked: true` written before the commit
    reached `live` would stand even when the push failed."""
    order = [
        'git commit -q -m "Sync fleet findings $LABEL"',
        "git push -q origin live",
        'if [ "$COMMITTED" = yes ]; then BANKED=--banked; else BANKED=""; fi',
        'fleet_findings.py outcome "$IN" --fleet "$FLEET" $BANKED',
        "fleet_leads.py",
        "push_fleet.sh",
    ]
    at = [BANK.index(text) for text in order]
    assert at == sorted(at), order
    assert BANK.count("--banked") == 1
