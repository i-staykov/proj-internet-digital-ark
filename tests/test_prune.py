"""prune on a fixture retention table: the three conditions, and no deletion.

Loaded by path, like the other script tests: `scripts/` is not a package.
"""

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("prune", REPO / "scripts/round/prune.py")
prune = importlib.util.module_from_spec(_SPEC)
# Registered before exec: the dataclasses read their own module back for its annotations.
sys.modules["prune"] = prune
_SPEC.loader.exec_module(prune)

HEAD = """# Retention

| entry | class | files | bytes | digest | refetch | record |
|---|---|---|---|---|---|---|
"""

# One entry of each class, plus one with no refetch route and one with no checksum.
ROWS = [
    ("data/raw/live", "live_input", 2, 100, "aa", "https://example.org/live.gz", "SHA256SUMS"),
    ("data/raw/journal", "keep_journal", 3, 200, "bb", "own_journal", "SHA256SUMS"),
    ("data/raw/priced", "keep_until_priced", 4, 400, "cc", "https://example.org/p.zip", "SHA1SUMS"),
    ("data/raw/ref", "reference", 5, 800, "dd", "reviewer_release", "SHA256SUMS"),
    ("output/build", "regenerable", 6, 1600, "ee", "just ship, or ark export", "SHA256SUMS"),
    ("data/raw/noroute", "keep_until_priced", 7, 3200, "ff", "unknown", "SHA256SUMS"),
    ("data/raw/nosum", "regenerable", 8, 6400, "none", "just reproduce", "none"),
]


def write_table(path: Path, rows=ROWS) -> Path:
    body = "".join(
        f"| `{k}` | {c} | {f} | {b} | `{d}` | {r} | {rec} |\n" for k, c, f, b, d, r, rec in rows
    )
    path.write_text(HEAD + body, encoding="utf-8")
    return path


def groups_of(path: Path) -> dict[str, list[str]]:
    return {g.label: [e.key for e in g.entries] for g in prune.group(prune.read_table(path))}


def test_fixture_table_produces_the_expected_groups(tmp_path: Path) -> None:
    groups = groups_of(write_table(tmp_path / "retention.md"))
    assert groups == {
        "regenerable, recipe route, checksum recorded": ["output/build"],
        "keep_until_priced, url route, checksum recorded": ["data/raw/priced"],
        "no checksum record": ["data/raw/nosum"],
        "no refetch route": ["data/raw/noroute"],
        "class reference is held": ["data/raw/ref"],
        "class keep_journal is held + no refetch route": ["data/raw/journal"],
        "class live_input is held": ["data/raw/live"],
    }


def test_an_entry_without_a_refetch_route_is_never_deletable(tmp_path: Path) -> None:
    rows = [
        (k, c, f, b, d, nobody, rec)
        for nobody in ("unknown", "own_journal", "none")
        for k, c, f, b, d, _, rec in ROWS
    ]
    entries = prune.read_table(write_table(tmp_path / "retention.md", rows))
    assert entries and not any(e.deletable for e in entries)
    assert all("no refetch route" in e.missing for e in entries)


def test_group_totals_sum_to_the_table_total(tmp_path: Path) -> None:
    groups = prune.group(prune.read_table(write_table(tmp_path / "retention.md")))
    assert sum(g.size for g in groups) == sum(row[3] for row in ROWS)
    assert sum(g.size for g in groups if g.deletable) == 1600 + 400


def test_real_table_groups_sum_to_its_bytes_column() -> None:
    page = REPO / "docs/retention.md"
    groups = prune.group(prune.read_table(page))
    total = sum(
        int(line.split("|")[4].strip())
        for line in page.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `")
    )
    assert sum(g.size for g in groups) == total
    assert all(g.entries for g in groups)


def test_json_form_lists_every_entry_with_its_reasons(tmp_path: Path, capsys) -> None:
    table = write_table(tmp_path / "retention.md")
    assert prune.main(["--table", str(table), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["deletes"] is False
    assert out["entries"] == len(ROWS)
    assert out["total_bytes"] == sum(row[3] for row in ROWS)
    assert out["deletable_bytes"] == 2000
    by_key = {e["entry"]: e for g in out["groups"] for e in g["entries"]}
    assert by_key["data/raw/nosum"]["missing"] == ["no checksum record"]
    assert by_key["data/raw/priced"]["missing"] == []


def test_a_delete_flag_is_refused_and_nothing_is_read(tmp_path: Path, capsys) -> None:
    table = write_table(tmp_path / "retention.md")
    for flag in ("--delete", "--force", "--apply=yes"):
        assert prune.main(["--table", str(table), flag]) == 2
        assert "never deletes" in capsys.readouterr().err


def test_the_text_report_deletes_nothing_and_says_so(tmp_path: Path, capsys) -> None:
    table = write_table(tmp_path / "retention.md")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert prune.main(["--table", str(table)]) == 0
    text = capsys.readouterr().out
    assert "Nothing was deleted" in text
    assert "data/raw/noroute" in text and "no refetch route" in text
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
