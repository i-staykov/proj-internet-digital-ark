"""`intake.py` takes a release in one command; `releases.py` fills its table from disk, keeps
every cell it measured and byte-verifies each tree against its zip. His calculator is stubbed
at two equivalent-English per line, so the figures check by hand."""

import contextlib
import hashlib
import importlib.util
import json
import re
import shutil
import stat
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

_SPEC = importlib.util.spec_from_file_location("intake", ROOT / "scripts/round/intake.py")
intake = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(intake)
releases = intake.releases
YEARS = releases.YEARS
LINES = {1996: 3, 1997: 0, 1998: 5, 1999: 1, 2000: 2, 2001: 1234}
ZITE = "".join(f"zite{i}.com\n" for i in range(3))  # 1996.txt's length, other bytes
MARKER = "merged261231"  # a date no real release uses, so no assertion reads a real row
STAMP = (2026, 12, 31, 10, 31, 0)
PHASE7 = "feedback-phase-7/Domain_Data_Collection_Task 3/merged260830"
ZIP7 = "feedback-phase-7/Domain_Data_Collection_Task_0831_UpdateV2.zip"
VERIFIED = "byte-verified against their zips, deletable once the off-site copy exists: "
PATHS = {"page": "releases.md", "feedback": "feedback", "archive": "archive", "legacy": "legacy"}
BENCH = {"baseline-json": "baseline.json", "rounds-page": "rounds.md", "calculator": "ee.py"}
TABLE = releases.render_table([releases.blank_row(m) for m in releases.RELEASES])
BLANK = f"{releases.BEGIN}\n{TABLE}\n{releases.END}\n"
CALCULATOR = """import json, sys
n = sum(1 for line in open(sys.argv[1]) if line.strip())
out = open(sys.argv[sys.argv.index("--output-dir") + 1] + "/summary.json", "w")
out.write(json.dumps({"equivalent_english_domains": f"{2 * n:.4f}"}))
"""
UNSAFE = {
    "dotdot": "merged260830/../escape.txt",
    "dot": "merged260830/./stray.txt",
    "empty-part": "merged260830//stray.txt",
    "backslash": "merged260830/sub\\stray.txt",
    "above": "../merged260830/stray.txt",
    "absolute": "/merged260830/stray.txt",
    "symlink": "merged260830/link",
    "same-name": "merged260830/1996.txt",
    "wrapped": "wrapper/merged260830/1996.txt",
}


def _tree(where: Path) -> Path:
    where.mkdir(parents=True)
    for y in YEARS:
        (where / f"{y}.txt").write_text("".join(f"site{i}.com\n" for i in range(LINES[y])))
    (where / "candidate_pool.txt").write_text("x.com\n")
    return where


def _zip(tree: Path, path: Path, wrap: str = "", method: int = zipfile.ZIP_STORED) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        for f in sorted(tree.iterdir()):
            info = zipfile.ZipInfo(f"{wrap}{tree.name}/{f.name}", STAMP)
            zf.writestr(info, f.read_bytes(), method)
    return path


def _his_zip(tmp_path: Path, name: str = "Task_0903.zip", note: str | None = None) -> Path:
    staged = _tree(tmp_path / "staging" / name / MARKER)
    if note is not None:
        (staged / "note.txt").write_text(note)
    return _zip(staged, tmp_path / "incoming" / name, "Domain_Data_Collection_Task/")


def _bench(tmp_path: Path) -> Path:
    """A release beside his zip, one without, a blank page, round 7 unwritten; his zip."""
    feedback = tmp_path / "feedback"
    _zip(_tree(feedback / PHASE7), feedback / ZIP7, "Domain_Data_Collection_Task 3/")
    (feedback / "feedback-phase-7/note.docx").write_bytes(b"not a release")
    _tree(feedback / "feedback-phase-4/merged260810")
    (tmp_path / "releases.md").write_text(BLANK)
    for copy, tracked in (("baseline.json", "data"), ("rounds.md", "docs/registers")):
        lines = (ROOT / tracked / copy).read_text(encoding="utf-8").splitlines(keepends=True)
        (tmp_path / copy).write_text("".join(x for x in lines if not x.startswith("| 7 |")))
    (tmp_path / "ee.py").write_text(CALCULATOR)
    return _his_zip(tmp_path)


@pytest.fixture
def run(monkeypatch, capsys, tmp_path):
    """A script's main() over the tmp layout, printing; `stops` matches the exit it must raise."""

    def run(script, *flags: str, stops: str | None = None) -> str:
        paths = PATHS | (BENCH if script is intake else {})
        argv = [f"--{flag}={tmp_path / name}" for flag, name in paths.items()]
        monkeypatch.setattr(sys, "argv", [script.__name__, *argv, *flags])
        with pytest.raises(SystemExit, match=stops) if stops else contextlib.nullcontext():
            script.main()
        return capsys.readouterr().out

    return run


def _rows(tmp_path: Path) -> dict[str, dict[str, str]]:
    return {r["marker"]: r for r in releases.split_page((tmp_path / "releases.md").read_text())[1]}


def _snapshot(tmp_path: Path) -> list[str]:
    return [(tmp_path / name).read_text() for name in ("baseline.json", "releases.md", "rounds.md")]


def _refused(capsys, tree: Path, archive: Path) -> str:
    assert releases.verify_trees({tree.name: [tree]}, {tree.name: [archive]}) is False
    assert (out := capsys.readouterr().out).splitlines()[-1] == VERIFIED + "none"
    return out


def test_the_table_fills_from_disk_verifies_and_forgets_nothing(run, tmp_path):
    """A zip is matched by member list, a tree verified by CRC-32; a cell outlives its zip."""
    assert releases.release_date("merged260902-3") == "2026-09-02"
    assert releases.release_date("merged260715-2") == "2026-07-15"
    with pytest.raises(ValueError):
        releases.release_date("legacy-data")
    (page := tmp_path / "releases.md").write_text(BLANK)
    stamp = page.stat().st_mtime_ns
    out = run(releases)
    assert "feedback/ not found: would scan" in out and "archive/ not found" in out
    assert page.stat().st_mtime_ns == stamp
    assert _rows(tmp_path)["merged260830"]["sha256"] == "pending"
    _bench(tmp_path)
    feedback = tmp_path / "feedback"
    deep = _tree(feedback / "feedback-phase-4/Domain_Data_Collection_Task_update/merged260810")
    _tree(feedback / "feedback-phase-9/merged261231")
    out = run(releases)
    rows, his, tree = _rows(tmp_path), feedback / ZIP7, feedback / PHASE7
    assert [rows["merged260830"][str(y)] for y in YEARS] == ["3", "0", "5", "1", "2", "1,234"]
    assert rows["merged260830"]["artifact"] == his.name
    assert rows["merged260830"]["sha256"] == hashlib.sha256(his.read_bytes()).hexdigest()
    assert rows["merged260810"]["2001"] == "1,234" and rows["merged260810"]["sha256"] == "pending"
    assert f"tar -C {feedback / 'feedback-phase-4'} -cf - merged260810 | zstd -19" in out
    assert "merged260810.tar.zst" in out and f"duplicate tree {deep}" in out
    assert "on disk but not in RELEASES: merged261231" in out and list(rows) == [*releases.RELEASES]
    assert rows["merged260902-3"]["sha256"] == "pending" and "wrote" in out
    for marker, row in rows.items():
        assert row["released"] == releases.release_date(marker)
    for marker, (_, successor) in releases.NOT_RECEIVED.items():
        assert rows[marker]["received"].startswith("not received") and successor in rows
        assert rows[marker]["sha256"] == "none"

    # Verifying writes nothing, and the zip-less tree has nothing to compare, so is not claimed.
    before = page.read_bytes(), page.stat().st_mtime_ns
    out = run(releases, "--verify-trees")
    assert "7 members, 7 matched, 0 mismatched, 0 missing on disk, 0 extra on disk" in out
    assert out.splitlines()[-1] == VERIFIED + str(tree)
    (tree / "stray.txt").write_text("extra\n")
    out = run(releases, "--verify-trees", stops="^1$")
    assert "7 members, 7 matched, 0 mismatched, 0 missing on disk, 1 extra on disk" in out
    assert "extra on disk: stray.txt" in out and out.splitlines()[-1] == VERIFIED + "none"
    (tree / "1996.txt").write_text(ZITE)
    (tree / "1998.txt").unlink()
    out = run(releases, "--verify-trees", stops="^1$")
    assert "7 members, 5 matched, 1 mismatched, 1 missing on disk, 1 extra on disk" in out
    for problem in ("crc differs: 1996.txt", "missing on disk: 1998.txt", "extra on disk: stray"):
        assert problem in out
    assert out.splitlines()[-1] == VERIFIED + "none"
    assert (page.read_bytes(), page.stat().st_mtime_ns) == before

    his.unlink()
    assert "unchanged" in run(releases)
    assert _rows(tmp_path)["merged260830"] == rows["merged260830"]


@pytest.mark.filterwarnings("ignore:Duplicate name")
@pytest.mark.parametrize("case", [*UNSAFE, "file", "tree", "parent", "extra-directory", "payload"])
def test_verify_trees_refuses_an_unsafe_member_a_symlink_or_a_bad_payload(tmp_path, capsys, case):
    """No tree verifies against a member read as another path, a symlink or a corrupt stream."""
    parent = tmp_path / "extracted"
    tree = _tree(parent / "merged260830")
    archive = _zip(tree, tmp_path / "release.zip", method=zipfile.ZIP_DEFLATED)
    target = tmp_path / "elsewhere"
    if member := UNSAFE.get(case):
        info, twin = zipfile.ZipInfo(member, STAMP), member.endswith("1996.txt")
        if case == "symlink":
            info.create_system, info.external_attr = 3, (stat.S_IFLNK | 0o644) << 16
        if not twin:  # the member's bytes sit on disk too, so only its path can refuse it
            (tree / ("link" if case == "symlink" else "stray.txt")).write_bytes(b"extra\n")
        with zipfile.ZipFile(archive, "a") as zf:
            zf.writestr(info, (tree / "1996.txt").read_bytes() if twin else b"extra\n")
    elif case == "payload":  # same size and CRC-32, so only reading the stream catches it
        with zipfile.ZipFile(archive) as zf:
            info = zf.getinfo(f"{tree.name}/1996.txt")
        assert info.CRC == releases.crc32(tree / "1996.txt")
        payload = bytearray(archive.read_bytes())
        sizes = struct.unpack_from("<HH", payload, info.header_offset + 26)
        payload[info.header_offset + 30 + sum(sizes)] |= 0b110
        archive.write_bytes(payload)
    elif case == "extra-directory":
        target.mkdir()
        (tree / "extra").symlink_to(target, target_is_directory=True)
    else:
        source = {"file": tree / "1996.txt", "tree": tree, "parent": parent}[case]
        source.rename(target)
        source.symlink_to(target, target_is_directory=case != "file")
    said = "duplicate zip member" if member and twin else "unsafe"
    assert said in _refused(capsys, tree, archive) or not member


def test_verify_trees_checks_future_markers_and_every_duplicate(tmp_path, capsys):
    """A marker newer than RELEASES is still verified, and so is every copy of a tree."""
    feedback = tmp_path / "feedback"
    future, shallow = _tree(feedback / "merged270101"), _tree(feedback / "merged260830")
    deep = _tree(feedback / "duplicate/nested/merged260830")
    assert future.name not in releases.RELEASES
    _zip(future, feedback / "future.zip")
    _zip(shallow, feedback / "release.zip")
    trees = releases.find_trees(feedback, {})
    assert trees[shallow.name] == [shallow, deep]
    for modified in (None, deep / "candidate_pool.txt", future / "1996.txt"):
        if modified:
            modified.write_text(ZITE)
        assert releases.verify_trees(trees, releases.find_zips(feedback)) is (modified is None)
        last = (out := capsys.readouterr().out).splitlines()[-1]
        assert future.name in out and f"{deep} against release.zip" in out and str(shallow) in last
        assert (str(deep) in last) is (modified is None)
        assert (str(future) in last) is (modified != future / "1996.txt")


@pytest.mark.skipif(shutil.which("zstd") is None, reason="zstd not installed")
def test_zstd_packs_the_zipless_tree_and_hashes_it(run, tmp_path):
    """Only the tree named by the marker goes in, rooted at the marker."""
    _bench(tmp_path)
    run(releases, "--zstd")
    target = tmp_path / "archive/merged260810.tar.zst"
    row = _rows(tmp_path)["merged260810"]
    assert row["artifact"] == target.name
    assert row["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    tar = subprocess.run(["zstd", "-dc", str(target)], capture_output=True, check=True).stdout
    listed = subprocess.run(["tar", "-tf", "-"], input=tar, capture_output=True, check=True)
    names = {line.strip("/") for line in listed.stdout.decode().split()}
    assert "merged260810/2001.txt" in names
    assert all(n == "merged260810" or n.startswith("merged260810/") for n in names)


def test_a_release_and_a_verdict_go_in_once_with_one_command(run, tmp_path):
    """A dry run or a wrong sha256 writes nothing; a repeat changes no byte; a second zip stops."""
    his = _bench(tmp_path)
    # His packer's stamp dates a release when it falls on the marker's day; else only the day does.
    assert intake.released_at(his, MARKER, None) == "2026-12-31 10:31"
    assert intake.released_at(his, "merged260830", None) == "2026-08-30 00:00"
    assert intake.released_at(his, MARKER, "2026-12-31 09:04") == "2026-12-31 09:04"
    with zipfile.ZipFile(empty := tmp_path / "empty.zip", "w") as zf:
        zf.writestr("readme.txt", "nothing here")
    with pytest.raises(SystemExit):
        intake.marker_of(empty, None)
    before = _snapshot(tmp_path)
    out = run(intake, str(his), "--dry-run")
    for said in ("would extract", f"would name {MARKER}", "dry run: nothing written"):
        assert said in out
    run(intake, str(his), "--sha256", "0" * 64, stops="sha256 is")
    assert _snapshot(tmp_path) == before
    assert not list((tmp_path / "feedback").rglob(MARKER))
    assert not (tmp_path / "feedback" / his.name).exists()

    mail = ["--mail", str(FIXTURES / "verdict_round7.txt"), "--round", "7"]
    out = run(intake, str(his), *mail, "--received=2026-09-02 05:50")
    written = json.loads((tmp_path / "baseline.json").read_text())
    tracked = json.loads((ROOT / "data/baseline.json").read_text())
    current = written["current"]
    assert (current["marker"], current["released_at"]) == (MARKER, "2026-12-31 10:31")
    assert current["directory"].endswith(f"Domain_Data_Collection_Task/{MARKER}")
    assert current["reviewer_pairs"] == sum(LINES.values())
    assert current["reviewer_ee_by_year"]["2001"] == "2468.0000"
    assert current["reviewer_ee"] == f"{2 * sum(LINES.values())}.0000"
    # The round fields and the ledger are separate decisions, left where they were.
    assert all(current[k] == tracked["current"][k] for k in ("round_label", "round_since"))
    assert (written["rounds"], written["original"]) == (tracked["rounds"], tracked["original"])
    row = _rows(tmp_path)[MARKER]
    assert row["2001"] == "1,234" and row["artifact"] == his.name
    assert row["sha256"] == hashlib.sha256(his.read_bytes()).hexdigest()
    round7 = [x for x in (tmp_path / "rounds.md").read_text().splitlines() if x.startswith("| 7 |")]
    assert any("1,456,458.1029" in map(str.strip, line.split("|")) for line in round7)
    assert "changed:" in out and "total:" in out
    # Every step says how long it took, which is how a slow intake is diagnosed.
    for label in ("checksum", "extract", "artifact", "line counts", "equivalent English"):
        assert f"{label}:" in out
    assert len(re.findall(r"^ {2}\d+\.\d{2}s$", out, re.MULTILINE)) >= 8

    before = _snapshot(tmp_path)
    out = run(intake, str(his))
    assert _snapshot(tmp_path) == before
    assert "already extracted" in out and "unchanged, kept from" in out
    assert "no change: this release was already taken in" in out
    run(intake, str(_his_zip(tmp_path, "Task_0903_v2.zip", "repacked\n")), stops="already recorded")
    assert _snapshot(tmp_path) == before
