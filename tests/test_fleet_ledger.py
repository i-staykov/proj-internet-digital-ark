"""The laptop's reads and appends of the fleet ledger, against a stand-in fleet clone.

The quiet failures. An append that builds its own key would book a find twice the moment
the fleet's key changed; a streak that skipped a line with no program figure would hand the
decision to a figure nobody measured.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "fleet_ledger", ROOT / "scripts/harness/fleet_ledger.py"
)
fleet_ledger = importlib.util.module_from_spec(_SPEC)
sys.modules["fleet_ledger"] = fleet_ledger
_SPEC.loader.exec_module(fleet_ledger)

# A stand-in for the fleet's `scripts/ledger.py append`: it keys a line on the fields the
# real one names, keeps one it already holds, and refuses a line missing a key field.
STAND_IN = r"""
import json, sys
from pathlib import Path
KINDS = {"legacy": ("row", "line"), "outcome": ("slug", "decision", "banked")}
args = sys.argv[1:]
kind, root = args[args.index("--kind") + 1], Path(args[args.index("--root") + 1])
path = root / "ledger" / "2026-09.jsonl"
path.parent.mkdir(exist_ok=True)
have = {json.loads(t)["key"] for t in path.read_text().splitlines()} if path.exists() else set()
added = kept = 0
for number, text in enumerate(sys.stdin.read().splitlines(), 1):
    line = json.loads(text)
    if any(line.get(f) in (None, "") for f in KINDS[kind]):
        print(f"ledger: stdin line {number}: a {kind} line needs its key", file=sys.stderr)
        sys.exit(2)
    key = ":".join(str(line[f]) for f in KINDS[kind])
    if key in have:
        kept += 1
        continue
    have.add(key)
    added += 1
    with path.open("a") as fh:
        fh.write(json.dumps({**line, "kind": kind, "key": key}) + "\n")
print(f"ledger: {added} appended, {kept} kept")
"""


def fleet(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/ledger.py").write_text(STAND_IN)
    return tmp_path


def outcome(slug: str, store: float | None, program: float | None, **over) -> dict:
    return {
        "kind": "outcome",
        "slug": slug,
        "store_ee": store,
        "program_ee": program,
        "decision": "master",
        "banked": True,
        **over,
    }


def test_an_append_goes_through_the_fleets_script_and_a_replay_adds_nothing(tmp_path):
    root = fleet(tmp_path)
    rows = [{"row": 1, "line": "a\t1\t2.0"}, {"row": 2, "line": "a\t1\t2.0"}]
    assert fleet_ledger.append(root, "legacy", rows) == (True, "ledger: 2 appended, 0 kept")
    assert fleet_ledger.append(root, "legacy", rows) == (True, "ledger: 0 appended, 2 kept")
    assert [line["row"] for line in fleet_ledger.lines(root, "legacy")] == [1, 2]


def test_a_refused_row_is_reported_with_the_scripts_reason(tmp_path):
    ok, said = fleet_ledger.append(fleet(tmp_path), "outcome", [{"slug": "x", "banked": True}])
    assert not ok
    assert "needs its key" in said


def test_a_clone_without_the_ledger_script_appends_nothing_and_says_so(tmp_path):
    ok, said = fleet_ledger.append(tmp_path, "legacy", [{"row": 1, "line": "x"}])
    assert (ok, "scripts/ledger.py" in said) == (False, True)
    assert not (tmp_path / "ledger").exists()
    assert fleet_ledger.lines(tmp_path, "legacy") == []
    assert fleet_ledger.lines(None, "legacy") == []


def test_lines_are_read_month_by_month_and_skip_what_is_not_a_line(tmp_path):
    (tmp_path / "ledger").mkdir()
    (tmp_path / "ledger/2026-10.jsonl").write_text(json.dumps(outcome("late", 1, 1)) + "\n")
    (tmp_path / "ledger/2026-09.jsonl").write_text(
        json.dumps(outcome("early", 1, 1)) + "\nnot json\n" + json.dumps({"kind": "leg"}) + "\n"
    )
    assert [line["slug"] for line in fleet_ledger.lines(tmp_path, "outcome")] == ["early", "late"]


def test_the_agreement_is_the_program_figure_as_a_share_of_the_stores():
    assert fleet_ledger.agreement_pct(1000.0, 995.0) == 99.5
    assert fleet_ledger.agreement_pct(1000.0, None) is None
    assert fleet_ledger.agreement_pct(0, 5.0) is None
    assert fleet_ledger.agreement_pct(True, 5.0) is None


def test_ten_finds_in_a_row_within_one_percent_make_a_streak():
    agreeing = [outcome(f"s{i}", 1000.0, 1000.0 + i) for i in range(fleet_ledger.STREAK)]
    assert fleet_ledger.streak(agreeing)
    assert not fleet_ledger.streak(agreeing[1:]), "nine finds are not ten"
    assert not fleet_ledger.streak([*agreeing, outcome("off", 1000.0, 1011.0)])


def test_a_find_counts_once_and_a_line_without_a_store_figure_not_at_all():
    agreeing = [outcome(f"s{i}", 1000.0, 1000.0) for i in range(fleet_ledger.STREAK - 1)]
    twice = [outcome("s0", 1000.0, 1000.0, decision="pending", banked=False), *agreeing]
    assert not fleet_ledger.streak(twice), "s0 booked twice is still nine finds"
    unpriced = [*agreeing, outcome("store-failed", None, 1000.0)]
    assert not fleet_ledger.streak(unpriced)
    assert fleet_ledger.streak([*unpriced, outcome("tenth", 50.0, 50.4)])


@pytest.mark.parametrize("program", [None, 0.0], ids=["no-program-figure", "program-zero"])
def test_a_line_with_no_program_figure_breaks_the_streak(program):
    """Skipped, it kept the streak alive and handed every later find to a figure that failed."""
    agreeing = [outcome(f"s{i}", 1000.0, 1000.0) for i in range(fleet_ledger.STREAK)]
    assert fleet_ledger.streak(agreeing)
    assert not fleet_ledger.streak([*agreeing, outcome("snapshot-out", 8000.0, program)])


def test_a_rebooked_find_counts_at_its_latest_line_not_its_first():
    """f0 off, ten agreeing finds, then f0 rebooked off as it is banked: the last ten finds
    hold f0, so there is no streak. Kept at its first place, f0 would fall out of the window
    and the program figure would decide while the latest find is 10% off."""
    agreeing = [outcome(f"f{i}", 1000.0, 1000.0) for i in range(1, fleet_ledger.STREAK + 1)]
    first = outcome("f0", 1000.0, 1100.0, decision="pending", banked=False)
    assert not fleet_ledger.streak([first, *agreeing, outcome("f0", 1000.0, 1100.0)])
    # The other way round: moving f0 to the end pushes the one disagreeing find out.
    lines = [
        outcome("f0", 1000.0, 1000.0, decision="pending", banked=False),
        outcome("f1", 1000.0, 1100.0),
        *[outcome(f"f{i}", 1000.0, 1000.0) for i in range(2, fleet_ledger.STREAK + 1)],
        outcome("f0", 1000.0, 1000.0),
    ]
    assert fleet_ledger.streak(lines)
