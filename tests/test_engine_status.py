"""The collector status line, and the pipefail trap that inverted it.

`engine_status.sh` runs under `set -uo pipefail` and asked whether a collector was up with
`ps -eo etime,command | grep -qE "$LOOPS"`. `grep -q` exits at its first match while `ps` is
still writing, so `ps` dies of SIGPIPE and pipefail reports the pipeline failed: the line
printed "no collector loop" precisely WHEN a collector was running.
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


def _lanes_pipeline() -> str:
    """The counter as the script itself spells it, so a copy pasted here cannot drift out
    of agreement with the thing under test and keep passing."""
    line = next(ln for ln in SCRIPT.read_text().splitlines() if "cdx_suffix_sweep[.]py" in ln)
    return line.strip().lstrip("| ")


LANES = _lanes_pipeline()

TWO_LANES = (
    "uv run python scripts/engines/cdx_suffix_sweep.py ricoh.com --deadline 1789855690\n"
    "/repo/.venv/bin/python3 scripts/engines/cdx_suffix_sweep.py ricoh.com --deadline 1789855690\n"
    "uv run python scripts/engines/cdx_suffix_sweep.py sont-ici.org --deadline 1789855690\n"
    "/repo/.venv/bin/python3 scripts/engines/cdx_suffix_sweep.py sont-ici.org --deadline 178\n"
)


def count_lanes(ps_output: str) -> str:
    """The counter fed a fixed `ps` listing. A quoted heredoc, because the fixture contains
    the backslash of a sed backreference and `printf %b` would eat it."""
    return run(f"cat <<'PS_EOF' | {LANES}\n{ps_output}PS_EOF\n").stdout.strip()


def test_a_lane_is_its_parent_not_its_two_processes() -> None:
    """One lane is a `uv run` wrapper plus its python child, so counting processes doubles
    it and counting parents does not. Four processes, two lanes."""
    assert count_lanes(TWO_LANES) == "2"


def test_the_counter_leaves_its_own_pipeline_out_of_the_answer() -> None:
    """`ps -eo command` lists this sed too. Unbracketed it matches itself, and every status
    line then reads one client too many, which is the same lie in the other direction."""
    assert count_lanes(TWO_LANES + LANES + "\n") == "2"


def test_a_flag_is_not_a_parent() -> None:
    """A sweep invoked with no parent must not have `--deadline` counted as one."""
    assert count_lanes("uv run python scripts/engines/cdx_suffix_sweep.py --deadline 178\n") == "0"


def test_the_printed_count_is_the_larger_of_journals_and_lanes() -> None:
    """Measured 2026-09-19: two sweeps were live, one was between parents holding no journal,
    and the line read "1 (the rule allows 2)". That is an invitation to start a third client
    and breach C-77, from the one script whose job is to stop exactly that. `local_clients()`
    in collectors.sh takes the larger of the two, and this has to agree with the function the
    header cites. The VPS block still counts journals alone, which is right: under C-88 that
    machine runs no lane, so it has nothing else to count.
    """
    text = SCRIPT.read_text()
    assert "sweep_lanes()" in text, "the second half of the question is not asked"
    assert '[ "$held" -gt "$clients" ] && clients=$held' in text
    local = text[text.index("open_now=$(sweep_clients)") : text.index("in-flight .part")]
    assert "holding a journal open" not in local, "the local count still names only journals"
