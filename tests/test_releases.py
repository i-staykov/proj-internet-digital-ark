"""The release table fills from disk and never forgets what it has measured.

Loaded by path, like the other script tests: `scripts/` is not a package.

Two properties matter. A zip is matched to its marker by member list, because his
zips are named by mail date (`..._0831_UpdateV2.zip` holds `merged260830`). And a
filled cell survives the file behind it leaving the machine, since the hash is what
the off-site copy is later verified against.
"""

import hashlib
import importlib.util
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("releases", ROOT / "scripts/round/releases.py")
releases = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(releases)

YEARS = releases.YEARS
LINES = {1996: 3, 1997: 0, 1998: 5, 1999: 1, 2000: 2, 2001: 1234}


def _tree(where: Path) -> Path:
    where.mkdir(parents=True)
    for y in YEARS:
        (where / f"{y}.txt").write_text("".join(f"site{i}.com\n" for i in range(LINES[y])))
    (where / "candidate_pool.txt").write_text("x.com\n")
    return where


def _blank_page() -> str:
    """The tracked page's prose around a table nobody has filled yet.

    The tracked table is filled from the real feedback/ tree, so a test that started from
    it would read those cells instead of its own layout's.
    """
    head, _, tail = releases.split_page((ROOT / "docs/releases.md").read_text())
    table = releases.render_table([releases.blank_row(m) for m in releases.RELEASES])
    return head + releases.BEGIN + "\n" + table + "\n" + releases.END + tail


def _layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    """One release with his zip beside it, one extracted with the zip gone."""
    feedback = tmp_path / "feedback"
    with_zip = _tree(feedback / "feedback-phase-7/Domain_Data_Collection_Task 3/merged260830")
    zip_path = feedback / "feedback-phase-7/Domain_Data_Collection_Task_0831_UpdateV2.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in sorted(with_zip.iterdir()):
            zf.write(f, f"Domain_Data_Collection_Task 3/merged260830/{f.name}")
    (feedback / "feedback-phase-7/note.docx").write_bytes(b"not a release")
    zipless = _tree(feedback / "feedback-phase-4/merged260810")
    page = tmp_path / "releases.md"
    page.write_text(_blank_page())
    return feedback, zip_path, zipless


def _run(monkeypatch, capsys, tmp_path: Path, *flags: str) -> str:
    argv = [
        "releases.py",
        "--page",
        str(tmp_path / "releases.md"),
        "--feedback",
        str(tmp_path / "feedback"),
        "--archive",
        str(tmp_path / "archive"),
        "--legacy",
        str(tmp_path / "legacy-data"),
        *flags,
    ]
    monkeypatch.setattr(sys, "argv", argv)
    releases.main()
    return capsys.readouterr().out


def _rows(page: Path) -> dict[str, dict[str, str]]:
    _, rows, _ = releases.split_page(page.read_text())
    return {r["marker"]: r for r in rows}


def test_every_release_has_a_row_and_a_date():
    rows = _rows(ROOT / "docs/releases.md")
    assert list(rows) == list(releases.RELEASES)
    for marker, row in rows.items():
        assert row["released"] == releases.release_date(marker)
    for marker, (_, successor) in releases.NOT_RECEIVED.items():
        assert rows[marker]["received"].startswith("not received")
        assert successor in releases.RELEASES
        assert rows[marker]["sha256"] == "none"


def test_release_date_reads_the_marker():
    assert releases.release_date("merged260902-3") == "2026-09-02"
    assert releases.release_date("merged260715-2") == "2026-07-15"
    with pytest.raises(ValueError):
        releases.release_date("legacy-data")


def test_fills_counts_and_shas_from_a_layout(monkeypatch, capsys, tmp_path):
    feedback, zip_path, zipless = _layout(tmp_path)
    out = _run(monkeypatch, capsys, tmp_path)
    rows = _rows(tmp_path / "releases.md")

    with_zip = rows["merged260830"]
    assert [with_zip[str(y)] for y in YEARS] == ["3", "0", "5", "1", "2", "1,234"]
    assert with_zip["artifact"] == zip_path.name
    assert with_zip["sha256"] == hashlib.sha256(zip_path.read_bytes()).hexdigest()

    no_zip = rows["merged260810"]
    assert no_zip["2001"] == "1,234"
    assert no_zip["sha256"] == "pending"
    assert f"tar -C {zipless.parent} -cf - merged260810 | zstd -19" in out
    assert "merged260810.tar.zst" in out

    assert rows["merged260902-3"]["sha256"] == "pending"
    assert rows["merged260817"]["sha256"] == "none"
    assert "wrote" in out


def test_filled_cells_survive_the_zip_leaving(monkeypatch, capsys, tmp_path):
    _, zip_path, _ = _layout(tmp_path)
    _run(monkeypatch, capsys, tmp_path)
    before = _rows(tmp_path / "releases.md")["merged260830"]
    zip_path.unlink()
    out = _run(monkeypatch, capsys, tmp_path)
    after = _rows(tmp_path / "releases.md")["merged260830"]
    assert after == before
    assert "unchanged" in out


def test_absent_directories_print_and_leave_the_page(monkeypatch, capsys, tmp_path):
    page = tmp_path / "releases.md"
    page.write_text(_blank_page())
    stamp = page.stat().st_mtime_ns
    out = _run(monkeypatch, capsys, tmp_path)
    assert "feedback/ not found: would scan" in out
    assert "archive/ not found" in out
    assert page.stat().st_mtime_ns == stamp
    assert _rows(page)["merged260830"]["sha256"] == "pending"


def test_duplicate_extraction_is_reported_and_the_shallow_one_used(monkeypatch, capsys, tmp_path):
    _layout(tmp_path)
    deep = _tree(
        tmp_path / "feedback/feedback-phase-4/Domain_Data_Collection_Task_update/merged260810"
    )
    out = _run(monkeypatch, capsys, tmp_path)
    assert f"duplicate tree {deep}" in out
    assert f"tar -C {tmp_path / 'feedback/feedback-phase-4'} -cf - merged260810" in out


def test_stray_tree_is_reported_not_silently_added(monkeypatch, capsys, tmp_path):
    _layout(tmp_path)
    _tree(tmp_path / "feedback/feedback-phase-9/merged261231")
    out = _run(monkeypatch, capsys, tmp_path)
    assert "on disk but not in RELEASES: merged261231" in out
    assert "merged261231" not in _rows(tmp_path / "releases.md")


@pytest.mark.skipif(shutil.which("zstd") is None, reason="zstd not installed")
def test_zstd_packs_the_zipless_tree_and_hashes_it(monkeypatch, capsys, tmp_path):
    _layout(tmp_path)
    _run(monkeypatch, capsys, tmp_path, "--zstd")
    target = tmp_path / "archive/merged260810.tar.zst"
    assert target.is_file()
    row = _rows(tmp_path / "releases.md")["merged260810"]
    assert row["artifact"] == "merged260810.tar.zst"
    assert row["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    # Only the tree named by the marker went in, rooted at the marker.
    unpacked = subprocess.run(["zstd", "-dc", str(target)], capture_output=True, check=True)
    members = subprocess.run(
        ["tar", "-tf", "-"], input=unpacked.stdout, capture_output=True, check=True
    ).stdout.decode()
    names = {line.strip("/") for line in members.split()}
    assert "merged260810/2001.txt" in names
    assert all(n == "merged260810" or n.startswith("merged260810/") for n in names)
