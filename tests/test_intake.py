"""One command takes a release: verify, extract, measure, and repoint every figure.

The layout is `tests/test_releases.py`'s, because an intake ends in that script and the
two must agree about what a release tree looks like. His calculator is stubbed at two
equivalent-English per line, so the figures the JSON ends up with are checkable by hand.

What the tests pin is the refusal and the repeat, not the happy path alone: a second
zip under one marker stops the run before anything is written, a second run of the same
zip writes nothing, and `--dry-run` leaves the disk byte for byte.
"""

import hashlib
import importlib.util
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

import pytest
from test_releases import LINES, _layout, _tree

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

_SPEC = importlib.util.spec_from_file_location("intake", ROOT / "scripts/round/intake.py")
intake = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(intake)

MARKER = "merged260903"
STAMP = (2026, 9, 3, 10, 31, 0)

# Two EE per line, so 1996 is 6 and 2001 is 2,468 against test_releases' LINES.
CALCULATOR = """
import json, pathlib, sys

lines = [line for line in pathlib.Path(sys.argv[1]).read_text().splitlines() if line.strip()]
out = pathlib.Path(sys.argv[sys.argv.index("--output-dir") + 1])
out.mkdir(parents=True, exist_ok=True)
summary = {"equivalent_english_domains": format(2 * len(lines), ".4f")}
(out / "summary.json").write_text(json.dumps(summary))
"""


def _zip(tmp_path: Path, name: str = "Task_0903.zip", extra: str | None = None) -> Path:
    """His release zip: the tree wrapped in a task directory, stamped by his packer."""
    staged = _tree(tmp_path / "staging" / MARKER)
    if extra is not None:
        (staged / "note.txt").write_text(extra)
    zip_path = tmp_path / "incoming" / name
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in sorted(staged.iterdir()):
            info = zipfile.ZipInfo(f"Domain_Data_Collection_Task/{MARKER}/{f.name}", STAMP)
            zf.writestr(info, f.read_bytes())
    shutil.rmtree(tmp_path / "staging")
    return zip_path


def _bench(tmp_path: Path) -> dict[str, Path]:
    """The tmp copies of every file an intake writes, plus the stubbed calculator."""
    _layout(tmp_path)
    baseline = tmp_path / "baseline.json"
    baseline.write_text((ROOT / "data/baseline.json").read_text(encoding="utf-8"))
    rounds_page = tmp_path / "rounds.md"
    rounds_page.write_text((ROOT / "docs/rounds.md").read_text(encoding="utf-8"))
    calculator = tmp_path / "equivalent_english_domains.py"
    calculator.write_text(CALCULATOR)
    return {
        "zip": _zip(tmp_path),
        "baseline": baseline,
        "page": tmp_path / "releases.md",
        "rounds": rounds_page,
        "calculator": calculator,
    }


def _run(monkeypatch, capsys, tmp_path: Path, bench: dict[str, Path], *flags: str) -> str:
    argv = [
        "intake.py",
        str(bench["zip"]),
        "--feedback",
        str(tmp_path / "feedback"),
        "--archive",
        str(tmp_path / "archive"),
        "--legacy",
        str(tmp_path / "legacy-data"),
        "--baseline-json",
        str(bench["baseline"]),
        "--page",
        str(bench["page"]),
        "--rounds-page",
        str(bench["rounds"]),
        "--calculator",
        str(bench["calculator"]),
        *flags,
    ]
    monkeypatch.setattr(sys, "argv", argv)
    intake.main()
    return capsys.readouterr().out


def _row(page: Path, marker: str) -> dict[str, str]:
    text = page.read_text(encoding="utf-8")
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0].strip("`") == marker:
            return dict(zip(intake.releases.COLUMNS, cells, strict=False))
    raise AssertionError(f"no row for {marker}")


def _snapshot(paths: list[Path]) -> dict[str, str]:
    return {str(p): p.read_text(encoding="utf-8") for p in paths}


def test_a_release_and_a_verdict_go_in_with_one_command(monkeypatch, capsys, tmp_path):
    bench = _bench(tmp_path)
    out = _run(
        monkeypatch,
        capsys,
        tmp_path,
        bench,
        "--mail",
        str(FIXTURES / "verdict_round7.txt"),
        "--round",
        "7",
        "--received",
        "2026-09-02 05:50",
    )

    written = json.loads(bench["baseline"].read_text())
    tracked = json.loads((ROOT / "data/baseline.json").read_text())
    current = written["current"]
    assert current["marker"] == MARKER
    assert current["directory"].endswith(f"Domain_Data_Collection_Task/{MARKER}")
    assert current["released_at"] == "2026-09-03 10:31"
    assert current["reviewer_pairs"] == sum(LINES.values())
    assert current["reviewer_ee_by_year"]["2001"] == "2468.0000"
    assert current["reviewer_ee"] == f"{2 * sum(LINES.values())}.0000"
    # The round fields and the ledger are separate decisions, left where they were.
    assert current["round_label"] == tracked["current"]["round_label"]
    assert current["round_since"] == tracked["current"]["round_since"]
    assert written["rounds"] == tracked["rounds"]
    assert written["original"] == tracked["original"]

    row = _row(bench["page"], MARKER)
    assert row["2001"] == "1,234"
    assert row["sha256"] == hashlib.sha256(bench["zip"].read_bytes()).hexdigest()
    assert row["artifact"] == bench["zip"].name

    round_row = [
        c.strip()
        for line in bench["rounds"].read_text().splitlines()
        if line.startswith("| 7 |")
        for c in line.strip().strip("|").split("|")
    ]
    assert "1,456,458.1029" in round_row

    assert "changed:" in out
    assert "total:" in out
    # Every step says how long it took, which is how a slow intake is diagnosed.
    for label in ("checksum", "extract", "artifact", "line counts", "equivalent English"):
        assert f"{label}:" in out
    assert len(re.findall(r"^ {2}\d+\.\d{2}s$", out, re.MULTILINE)) >= 8


def test_a_second_run_writes_nothing_and_says_so(monkeypatch, capsys, tmp_path):
    bench = _bench(tmp_path)
    _run(monkeypatch, capsys, tmp_path, bench)
    before = _snapshot([bench["baseline"], bench["page"]])
    out = _run(monkeypatch, capsys, tmp_path, bench)
    assert _snapshot([bench["baseline"], bench["page"]]) == before
    assert "already extracted" in out
    assert "unchanged, kept from" in out
    assert "no change: this release was already taken in" in out


def test_a_second_zip_under_one_marker_stops_the_run(monkeypatch, capsys, tmp_path):
    bench = _bench(tmp_path)
    _run(monkeypatch, capsys, tmp_path, bench)
    before = _snapshot([bench["baseline"], bench["page"]])
    bench["zip"] = _zip(tmp_path, name="Task_0903_v2.zip", extra="repacked\n")
    with pytest.raises(SystemExit) as stop:
        _run(monkeypatch, capsys, tmp_path, bench)
    assert "already recorded" in str(stop.value)
    assert _snapshot([bench["baseline"], bench["page"]]) == before


def test_a_stated_sha256_that_disagrees_stops_the_run(monkeypatch, capsys, tmp_path):
    bench = _bench(tmp_path)
    with pytest.raises(SystemExit) as stop:
        _run(monkeypatch, capsys, tmp_path, bench, "--sha256", "0" * 64)
    assert "sha256 is" in str(stop.value)
    assert MARKER not in bench["page"].read_text()


def test_dry_run_writes_nothing(monkeypatch, capsys, tmp_path):
    bench = _bench(tmp_path)
    before = _snapshot([bench["baseline"], bench["page"], bench["rounds"]])
    out = _run(monkeypatch, capsys, tmp_path, bench, "--dry-run")
    assert _snapshot([bench["baseline"], bench["page"], bench["rounds"]]) == before
    assert not list((tmp_path / "feedback").rglob(MARKER))
    assert not (tmp_path / "feedback" / bench["zip"].name).exists()
    assert "would extract" in out
    assert f"would name {MARKER}" in out
    assert "dry run: nothing written" in out


def test_the_release_stamp_falls_back_to_the_marker_date(tmp_path):
    """A zip stamped on another day dates the release only to the day."""
    bench = _bench(tmp_path)
    assert intake.released_at(bench["zip"], MARKER, None) == "2026-09-03 10:31"
    assert intake.released_at(bench["zip"], "merged260830", None) == "2026-08-30 00:00"
    assert intake.released_at(bench["zip"], MARKER, "2026-09-03 09:04") == "2026-09-03 09:04"


def test_the_tracked_json_survives_a_rewrite_unchanged():
    """The writer re-dumps the whole file, so its formatting has to be the file's."""
    text = (ROOT / "data/baseline.json").read_text(encoding="utf-8")
    assert json.dumps(json.loads(text), indent=2, ensure_ascii=False) + "\n" == text


def test_a_zip_holding_no_release_is_refused(tmp_path):
    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w") as zf:
        zf.writestr("readme.txt", "nothing here")
    with pytest.raises(SystemExit):
        intake.marker_of(empty, None)
