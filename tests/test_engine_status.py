"""The collector status line, and the pipefail trap that inverted it.

`engine_status.sh` runs under `set -uo pipefail` and asked whether a collector was up with
`ps -eo etime,command | grep -qE "$LOOPS"`. `grep -q` exits at its first match while `ps` is
still writing, so `ps` dies of SIGPIPE (141) and pipefail reports the whole pipeline failed.
The line therefore printed "no collector loop" precisely WHEN a collector was running, which
is how `data/brief.json` told a session at 04:28Z on 2026-09-10 that the lane was down while
two sweep shards had been up for half an hour.
"""

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/engines/engine_status.sh"


def run(snippet: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", snippet], capture_output=True, text=True, check=False, timeout=60
    )


def test_grep_q_on_a_long_producer_fails_under_pipefail() -> None:
    """The defect itself, so the fix below is read as a fix and not as a style change."""
    done = run(
        "set -uo pipefail\n"
        "if seq 1 200000 | grep -q '^1$'; then echo MATCH; else echo \"NOMATCH rc=$?\"; fi"
    )
    assert done.stdout.strip().startswith("NOMATCH"), done.stdout
    assert "141" in done.stdout, done.stdout


def test_capturing_the_match_first_answers_correctly_under_pipefail() -> None:
    """The shape the script now uses: grep reads its input to the end, so nothing gets SIGPIPE."""
    done = run(
        "set -uo pipefail\n"
        "hits=$(seq 1 200000 | grep -E '^1$' || true)\n"
        'if [ -n "$hits" ]; then echo MATCH; else echo NOMATCH; fi'
    )
    assert done.stdout.strip() == "MATCH", done.stdout


def test_the_status_script_never_asks_a_ps_pipeline_with_grep_q() -> None:
    """Whatever else it grows, the local collector question stays SIGPIPE-safe."""
    text = SCRIPT.read_text()
    assert "set -uo pipefail" in text, "the trap only exists while the script sets pipefail"
    offenders = [
        line.strip()
        for line in text.split("\n")
        if "ps -eo" in line and "grep -q" in line and not line.lstrip().startswith("#")
    ]
    assert offenders == [], offenders


def test_the_local_section_still_has_both_answers() -> None:
    text = SCRIPT.read_text()
    assert 'loops=$(ps -eo etime,command | grep -E "$LOOPS" || true)' in text
    assert "no collector loop" in text
