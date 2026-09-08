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
import stat
import struct
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
    head, _, tail = releases.split_page((ROOT / "docs/registers/releases.md").read_text())
    table = releases.render_table([releases.blank_row(m) for m in releases.RELEASES])
    return head + releases.BEGIN + "\n" + table + "\n" + releases.END + tail


def _zip_tree(tree: Path, zip_path: Path, compression=zipfile.ZIP_STORED) -> Path:
    with zipfile.ZipFile(zip_path, "w", compression=compression) as zf:
        for path in sorted(tree.iterdir()):
            zf.write(path, f"{tree.name}/{path.name}")
    return zip_path


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
    rows = _rows(ROOT / "docs/registers/releases.md")
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


def test_verify_trees_passes_a_matching_tree(monkeypatch, capsys, tmp_path):
    _layout(tmp_path)
    page = tmp_path / "releases.md"
    stamp = page.stat().st_mtime_ns
    out = _run(monkeypatch, capsys, tmp_path, "--verify-trees")
    assert "7 members, 7 matched, 0 mismatched, 0 missing on disk, 0 extra on disk" in out
    assert "deletable once the off-site copy exists: " in out
    assert "merged260830" in out.splitlines()[-1]
    # The zip-less tree has nothing to compare against, so it is not claimed.
    assert "merged260810" not in out.splitlines()[-1]
    assert page.stat().st_mtime_ns == stamp


def test_verify_trees_catches_a_modified_and_a_missing_file(monkeypatch, capsys, tmp_path):
    feedback, _, _ = _layout(tmp_path)
    tree = feedback / "feedback-phase-7/Domain_Data_Collection_Task 3/merged260830"
    # Same length as what the zip holds, so only the checksum can catch it.
    (tree / "1996.txt").write_text("".join(f"zite{i}.com\n" for i in range(LINES[1996])))
    (tree / "1998.txt").unlink()
    (tree / "stray.txt").write_text("later\n")
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, capsys, tmp_path, "--verify-trees")
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "7 members, 5 matched, 1 mismatched, 1 missing on disk, 1 extra on disk" in out
    assert "crc differs: 1996.txt" in out
    assert "missing on disk: 1998.txt" in out
    assert "extra on disk: stray.txt" in out
    assert out.splitlines()[-1].endswith("exists: none")


def test_verify_trees_rejects_an_extra_file_only(monkeypatch, capsys, tmp_path):
    feedback, _, _ = _layout(tmp_path)
    tree = feedback / "feedback-phase-7/Domain_Data_Collection_Task 3/merged260830"
    (tree / "stray.txt").write_text("extra\n")
    page = tmp_path / "releases.md"
    before = page.read_bytes(), page.stat().st_mtime_ns
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, capsys, tmp_path, "--verify-trees")
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "7 matched, 0 mismatched, 0 missing on disk, 1 extra on disk" in out
    assert out.splitlines()[-1].endswith("exists: none")
    assert (page.read_bytes(), page.stat().st_mtime_ns) == before


@pytest.mark.parametrize(
    "member",
    [
        "merged260830/../escape.txt",
        "merged260830/./stray.txt",
        "merged260830//stray.txt",
        "merged260830/sub\\stray.txt",
        "../merged260830/stray.txt",
        "/merged260830/stray.txt",
    ],
)
def test_verify_trees_rejects_unsafe_zip_paths(tmp_path, capsys, member):
    tree = _tree(tmp_path / "merged260830")
    archive = _zip_tree(tree, tmp_path / "release.zip")
    with zipfile.ZipFile(archive, "a") as zf:
        zf.writestr(member, "extra\n")
    (tree / "stray.txt").write_text("extra\n")
    assert releases.verify_trees({tree.name: [tree]}, {tree.name: [archive]}) is False
    out = capsys.readouterr().out
    assert "unsafe" in out and out.splitlines()[-1].endswith("exists: none")


@pytest.mark.parametrize("same_name", [True, False])
def test_verify_trees_rejects_duplicate_zip_members(tmp_path, capsys, same_name):
    tree = _tree(tmp_path / "merged260830")
    archive = _zip_tree(tree, tmp_path / "release.zip")
    name = f"{tree.name}/1996.txt"
    with zipfile.ZipFile(archive, "a") as zf:
        if same_name:
            with pytest.warns(UserWarning, match="Duplicate name"):
                zf.writestr(name, (tree / "1996.txt").read_bytes())
        else:
            zf.writestr(f"wrapper/{name}", (tree / "1996.txt").read_bytes())
    assert releases.verify_trees({tree.name: [tree]}, {tree.name: [archive]}) is False
    out = capsys.readouterr().out
    assert "duplicate zip member" in out
    assert out.splitlines()[-1].endswith("exists: none")


@pytest.mark.parametrize("location", ["file", "tree", "parent", "extra-directory"])
def test_verify_trees_rejects_symlinks_on_disk(tmp_path, capsys, location):
    parent = tmp_path / "extracted"
    tree = _tree(parent / "merged260830")
    archive = _zip_tree(tree, tmp_path / "release.zip")
    if location == "extra-directory":
        target = tmp_path / "empty"
        target.mkdir()
        (tree / "extra").symlink_to(target, target_is_directory=True)
    else:
        source = {"file": tree / "1996.txt", "tree": tree, "parent": parent}[location]
        target = tmp_path / "original"
        source.rename(target)
        source.symlink_to(target, target_is_directory=location != "file")
    assert releases.verify_trees({tree.name: [tree]}, {tree.name: [archive]}) is False
    assert capsys.readouterr().out.splitlines()[-1].endswith("exists: none")


def test_verify_trees_rejects_symlink_zip_member(tmp_path, capsys):
    tree = _tree(tmp_path / "merged260830")
    (tree / "link").write_text("1996.txt")
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in sorted(tree.iterdir()):
            info = zipfile.ZipInfo(f"{tree.name}/{path.name}")
            info.create_system = 3
            info.external_attr = (
                (stat.S_IFLNK if path.name == "link" else stat.S_IFREG) | 0o644
            ) << 16
            zf.writestr(info, path.read_bytes())
    assert releases.verify_trees({tree.name: [tree]}, {tree.name: [archive]}) is False
    out = capsys.readouterr().out
    assert "unsafe" in out and out.splitlines()[-1].endswith("exists: none")


def test_verify_trees_rejects_corrupt_compressed_payload(tmp_path, capsys):
    tree = _tree(tmp_path / "merged260830")
    archive = _zip_tree(tree, tmp_path / "release.zip", zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(archive) as zf:
        info = zf.getinfo(f"{tree.name}/1996.txt")
    assert info.CRC == releases.crc32(tree / "1996.txt")
    payload = bytearray(archive.read_bytes())
    name_size, extra_size = struct.unpack_from("<HH", payload, info.header_offset + 26)
    offset = info.header_offset + 30 + name_size + extra_size
    payload[offset] |= 0b110
    archive.write_bytes(payload)
    assert releases.verify_trees({tree.name: [tree]}, {tree.name: [archive]}) is False
    assert capsys.readouterr().out.splitlines()[-1].endswith("exists: none")


@pytest.mark.parametrize("modified", [False, True])
def test_verify_trees_checks_future_markers(tmp_path, capsys, modified):
    feedback = tmp_path / "feedback"
    tree = _tree(feedback / "merged270101")
    assert tree.name not in releases.RELEASES
    _zip_tree(tree, feedback / "release.zip")
    if modified:
        (tree / "1996.txt").write_text("".join(f"zite{i}.com\n" for i in range(LINES[1996])))
    assert releases.verify_trees(
        releases.find_trees(feedback, {}), releases.find_zips(feedback)
    ) is (not modified)
    out = capsys.readouterr().out
    assert tree.name in out
    assert (str(tree) in out.splitlines()[-1]) is (not modified)


@pytest.mark.parametrize("modified", [False, True])
def test_verify_trees_checks_every_duplicate_tree(tmp_path, capsys, modified):
    feedback = tmp_path / "feedback"
    shallow = _tree(feedback / "merged260830")
    deep = _tree(feedback / "duplicate/nested/merged260830")
    _zip_tree(shallow, feedback / "release.zip")
    if modified:
        (deep / "candidate_pool.txt").write_text("z.com\n")
    trees = releases.find_trees(feedback, {})
    assert trees[shallow.name] == [shallow, deep]
    assert releases.verify_trees(trees, releases.find_zips(feedback)) is (not modified)
    out = capsys.readouterr().out
    assert f"{deep} against release.zip" in out
    assert str(shallow) in out.splitlines()[-1]
    assert (str(deep) in out.splitlines()[-1]) is (not modified)


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
