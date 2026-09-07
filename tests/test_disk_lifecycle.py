"""Round cleanup must preserve every local-only or unverified artifact."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("disk_prune", ROOT / "scripts/round/prune.py")
prune = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = prune
SPEC.loader.exec_module(prune)


def file(root, rel, content=b"original\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def proofs(root, paths, monkeypatch):
    offsite = prune.sibling("offsite")
    records, objects, calls = {}, {}, []
    for path in paths:
        key = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        records[key] = {"stat": offsite.signature(root, path), "kind": "sha256", "digest": digest}
        objects[f"{offsite.REMOTE}/{key}"] = {
            "Size": path.stat().st_size,
            "Hashes": {"sha256": digest},
        }
    offsite.write_receipt(root, offsite.REMOTE, records)

    def rclone(args, check=True):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=json.dumps(objects.get(args[-1], {})))

    monkeypatch.setattr(offsite, "rclone", rclone)
    return objects, calls


def stores(root):
    backup = file(root, "data/ark.duckdb.pre-test.bak", b"previous")
    os.utime(backup, ns=(1_000_000, 1_000_000))
    store = file(root, "data/ark.duckdb", b"current")
    return backup, store


def release(root, marker="merged261231"):
    tree = root / f"feedback/package/{marker}"
    for year in range(1996, 2002):
        file(root, f"{tree.relative_to(root)}/{year}.txt", b"example.org\n")
    archive = root / "feedback/reviewer.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for child in tree.iterdir():
            zf.write(child, f"package/{marker}/{child.name}")
        zf.writestr("package/brief.txt", b"reviewer brief")
    return archive, tree


def test_no_receipt_preserves_backup_zip_and_graded_submission(tmp_path, monkeypatch):
    backup, store = stores(tmp_path)
    archive, tree = release(tmp_path)
    graded = file(tmp_path, "submissions/phase-8/graded.zip")
    output = file(tmp_path, "output/delivery/unique.txt")
    calls = []
    monkeypatch.setattr(prune.subprocess, "run", lambda *a, **kw: calls.append(a))
    code, lines = prune.round_cleanup(tmp_path, write=True)
    assert code == 1 and "HELD" in "\n".join(lines)
    assert all(p.exists() for p in (backup, store, archive, tree, graded, output))
    assert not calls


@pytest.mark.parametrize("write", [False, True])
def test_checked_remote_backup_is_removed_only_with_write(tmp_path, monkeypatch, write):
    backup, store = stores(tmp_path)
    proofs(tmp_path, [backup], monkeypatch)
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(prune.subprocess, "run", run)
    assert prune.round_cleanup(tmp_path, write=write)[0] == 0
    assert backup.exists() is not write
    assert store.read_bytes() == b"current"
    assert len(calls) == int(write)
    if write:
        assert calls[0][0] == ["uv", "run", "ark", "check"]
        assert calls[0][1]["cwd"] == tmp_path


@pytest.mark.parametrize("failure", ["check", "store-change", "wal", "missing", "remote"])
def test_failed_store_or_remote_check_keeps_backup(tmp_path, monkeypatch, failure):
    backup, store = stores(tmp_path)
    objects, _ = proofs(tmp_path, [backup], monkeypatch)
    if failure == "wal":
        file(tmp_path, "data/ark.duckdb.wal")
    if failure == "missing":
        store.unlink()
    if failure == "remote":
        objects.clear()

    def run(args, **kwargs):
        if failure == "store-change":
            store.write_bytes(b"updated")
        return SimpleNamespace(returncode=int(failure == "check"))

    monkeypatch.setattr(prune.subprocess, "run", run)
    assert prune.round_cleanup(tmp_path, write=True)[0] == 1
    assert backup.read_bytes() == b"previous"


def test_backup_changed_during_check_keeps_its_new_bytes(tmp_path, monkeypatch):
    backup, _ = stores(tmp_path)
    proofs(tmp_path, [backup], monkeypatch)

    def run(args, **kwargs):
        backup.write_bytes(b"new local-only backup")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(prune.subprocess, "run", run)
    assert prune.round_cleanup(tmp_path, write=True)[0] == 1
    assert backup.read_bytes() == b"new local-only backup"


def test_crc_verified_zip_leaves_one_extracted_copy_and_is_idempotent(tmp_path, monkeypatch):
    archive, tree = release(tmp_path)
    proofs(tmp_path, [archive], monkeypatch)
    before = {p.name: p.read_bytes() for p in tree.iterdir()}
    assert prune.round_cleanup(tmp_path)[0] == 0
    assert archive.exists()
    assert prune.round_cleanup(tmp_path, write=True)[0] == 0
    assert not archive.exists()
    assert {p.name: p.read_bytes() for p in tree.iterdir()} == before
    assert prune.round_cleanup(tmp_path, write=True) == (0, ["round duplicates: nothing to prune"])


@pytest.mark.parametrize("failure", ["extra", "missing", "crc", "symlink", "remote", "stale"])
def test_release_refusals_preserve_zip(tmp_path, monkeypatch, failure):
    archive, tree = release(tmp_path)
    objects, _ = proofs(tmp_path, [archive], monkeypatch)
    if failure == "extra":
        (tree / "unique.txt").write_text("local-only")
    elif failure == "missing":
        (tree / "1996.txt").unlink()
    elif failure == "crc":
        (tree / "1996.txt").write_bytes(b"changed.org\n")
    elif failure == "symlink":
        (tree / "unique.txt").symlink_to(tree / "1996.txt")
    elif failure == "remote":
        objects.clear()
    elif failure == "stale":
        with archive.open("ab") as stream:
            stream.write(b"updated")
    assert prune.round_cleanup(tmp_path, write=True)[0] == 1
    assert archive.exists()


def test_two_release_zip_needs_both_extracted_trees(tmp_path, monkeypatch):
    archive, tree = release(tmp_path)
    with zipfile.ZipFile(archive, "a") as zf:
        zf.writestr("another/merged270101/1996.txt", b"another.org")
    proofs(tmp_path, [archive], monkeypatch)
    assert prune.round_cleanup(tmp_path, write=True)[0] == 1
    assert archive.exists() and tree.exists()


def test_scope_never_selects_submissions_output_or_raw(tmp_path, monkeypatch):
    paths = [
        file(tmp_path, "submissions/phase-8/submission.zip"),
        file(tmp_path, "output/delivery.zip"),
        file(tmp_path, "data/raw/unique.jsonl"),
    ]
    proofs(tmp_path, paths, monkeypatch)
    assert prune.round_cleanup(tmp_path, write=True)[0] == 0
    assert all(p.exists() for p in paths)


def test_just_run_refuses_before_export_on_low_space(tmp_path):
    import shutil

    just = shutil.which("just")
    if just is None:
        pytest.skip("just not installed")
    binary = tmp_path / "uv"
    binary.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\n'
        'case "$*" in *bank_hygiene.py*space*) exit 2;; esac\nexit 0\n'
    )
    binary.chmod(0o755)
    calls = tmp_path / "calls"
    done = subprocess.run(
        [just, "--justfile", str(ROOT / "justfile"), "run", "export"],
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "CALLS": str(calls)},
        capture_output=True,
        check=False,
    )
    assert done.returncode != 0
    assert "run ark export" not in calls.read_text()


def test_every_direct_ingest_and_export_has_an_independent_guard():
    lines = (ROOT / "justfile").read_text().splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith(("uv run ark ingest", "uv run ark export")):
            assert "bank_hygiene.py space" in lines[index - 1], line
            assert "|| true" not in lines[index - 1], line
