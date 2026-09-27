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


def credited(root, day="2026-09-05", percent="18.769714"):
    """A `data/baseline.json` whose one round is dated `day` and awarded `percent`."""
    rounds = [{"label": "8", "date": day, "awarded_percent": percent}]
    file(root, "data/baseline.json", json.dumps({"rounds": rounds}).encode())


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
@pytest.mark.parametrize("day,percent", [("1970-01-01", "18.769714"), ("2026-09-05", "")])
def test_a_backup_is_held_until_a_credited_round_follows_it(
    tmp_path, monkeypatch, capsys, write, day, percent
):
    backup, _ = stores(tmp_path)
    credited(tmp_path, day, percent)
    calls = []
    monkeypatch.setattr(prune.subprocess, "run", lambda *a, **kw: calls.append(a))
    argv = ["--round", "--root", str(tmp_path)] + ["--write"] * write
    assert prune.main(argv) == 1
    assert "HELD data/ark.duckdb.pre-test.bak" in capsys.readouterr().out
    assert backup.read_bytes() == b"previous" and not calls


@pytest.mark.parametrize("write", [False, True])
def test_a_later_credited_round_releases_the_backup_only_with_write(tmp_path, monkeypatch, write):
    backup, store = stores(tmp_path)
    credited(tmp_path)
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


@pytest.mark.parametrize("failure", ["check", "store-change", "wal", "missing"])
def test_failed_store_check_keeps_backup(tmp_path, monkeypatch, failure):
    backup, store = stores(tmp_path)
    credited(tmp_path)
    if failure == "wal":
        file(tmp_path, "data/ark.duckdb.wal")
    if failure == "missing":
        store.unlink()

    def run(args, **kwargs):
        if failure == "store-change":
            # another store moved into place while the check ran
            file(tmp_path, "data/ark.duckdb.next", b"updated").replace(store)
        return SimpleNamespace(returncode=int(failure == "check"))

    monkeypatch.setattr(prune.subprocess, "run", run)
    assert prune.round_cleanup(tmp_path, write=True)[0] == 1
    assert backup.read_bytes() == b"previous"


def test_backup_changed_during_check_keeps_its_new_bytes(tmp_path, monkeypatch):
    backup, _ = stores(tmp_path)
    credited(tmp_path)

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


# --- --disk ----------------------------------------------------------------------------

OLD_STAGE = "DomainDataCollectionTask_202601010000_IvayloStaykov"
NEW_STAGE = "DomainDataCollectionTask_202601020000_IvayloStaykov"


def sums(folder, files, kind="SHA256SUMS"):
    """The sidecars verify_raw writes: digests and the (size, mtime_ns) each was taken at."""
    hash_of = hashlib.sha1 if kind == "SHA1SUMS" else hashlib.sha256
    digests = {rel: hash_of(Path(folder, rel).read_bytes()).hexdigest() for rel in files}
    file(folder, kind, "".join(f"{d}  ./{r}\n" for r, d in digests.items()).encode())
    stats = [(r, Path(folder, r).stat()) for r in files]
    lines = "".join(f"{st.st_size} {st.st_mtime_ns} ./{r}\n" for r, st in stats)
    file(folder, "SHA256SUMS.stat", lines.encode())
    return digests


def disk_repo(root):
    """One of everything --disk selects, keeps or holds."""
    current = "feedback/Current_Release/merged261231"
    file(
        root,
        "data/baseline.json",
        json.dumps({"current": {"directory": current}, "rounds": []}).encode(),
    )
    file(root, f"{current}/1996.txt", b"current.example\n")
    file(root, "feedback/Current_Release.zip", b"current zip")
    old = root / "feedback/Old_Release/merged260101"
    file(root, f"{old.relative_to(root)}/1996.txt", b"old.example\n")
    with zipfile.ZipFile(root / "feedback/Old_Release.zip", "w") as zf:
        zf.write(old / "1996.txt", "merged260101/1996.txt")
    file(root, "data/archive/merged250101.tar.zst", b"repacked release")
    host = root / "data/raw/host_cdx"
    file(host, "ia600702.hostcdx.gz", b"the node cdx")
    file(host, "bank.log", b"a log with no copy anywhere")
    file(host, "items/hostcdx_ia600702_001_items.jsonl.gz", b"journal")
    sums(host, ["ia600702.hostcdx.gz", "bank.log", "items/hostcdx_ia600702_001_items.jsonl.gz"])
    bulk = root / "data/raw/usenet_bulk"
    file(bulk, "alt.test.mbox.zip", b"a usenet zip")
    sha1 = sums(bulk, ["alt.test.mbox.zip"], "SHA1SUMS")["alt.test.mbox.zip"]
    catalog = {"alt": [{"name": "alt.test.mbox.zip", "sha1": sha1, "size": "12"}]}
    file(root, "data/raw/usenet_catalog.json", json.dumps(catalog).encode())
    hdr2 = root / "data/raw/usenet_hdr2"
    file(hdr2, "demon/demon.test.mbox.zip", b"uncatalogued")
    file(hdr2, "aus_items/shard_000.jsonl.gz", b"journal")
    sums(hdr2, ["demon/demon.test.mbox.zip", "aus_items/shard_000.jsonl.gz"])
    file(root, f"output/{OLD_STAGE}/report.md", b"superseded build")
    file(root, f"output/{OLD_STAGE}/journals/one.jsonl.gz", b"journal")
    file(root, f"output/{OLD_STAGE}/SHA256SUMS", b"sums")
    file(root, f"output/{NEW_STAGE}/report.md", b"the round as sent")
    tarball = file(root, f"submissions/phase-9/{NEW_STAGE}.tar.gz.sha256", b"")
    tarball.write_text(f"{'b' * 64}  {NEW_STAGE}.tar.gz\n")
    for rel in ("personal-context.md", "handoff.md", "mail/verdict.txt", "notes.md", "v3/big.bin"):
        file(root, f"private/{rel}", b"private")
    for name in ("ark.duckdb.pre-stage-a.bak", "ark.duckdb.pre-166.bak"):
        file(root, f"data/{name}", b"store backup")
    return {"old": old, "host": host, "bulk": bulk, "hdr2": hdr2}


def archive_org(monkeypatch, files):
    """archive.org's metadata as a dict of (item, name) -> file record."""

    def ia_file(item, name, cache):
        return files.get((item, name))

    monkeypatch.setattr(prune, "ia_file", ia_file)


def test_disk_dry_run_lists_every_selector_and_touches_nothing(tmp_path, monkeypatch):
    disk_repo(tmp_path)
    offsite = prune.sibling("offsite")
    monkeypatch.setattr(offsite, "rclone", lambda *a, **k: pytest.fail("the dry run went to Drive"))
    monkeypatch.setattr(prune, "ia_file", lambda *a: pytest.fail("the dry run went to archive.org"))
    before = sorted(p for p in tmp_path.rglob("*") if p.is_file())
    code, lines = prune.disk_cleanup(tmp_path)
    text = "\n".join(lines)
    assert code == 1  # the store backups are always held
    for label in ("releases:", "spent raw:", "output stages:", "store backups:"):
        assert label in text
    assert "would remove: data/raw/host_cdx/ia600702.hostcdx.gz" in text
    assert "https://archive.org/download/host_cdx_ia600702/ia600702.hostcdx.gz" in text
    assert "https://archive.org/download/usenet-alt/alt.test.mbox.zip" in text
    assert "kept 1 archives of data/raw/usenet_hdr2" in text
    assert "HELD feedback/Old_Release.zip: no Drive receipt" in text
    assert "Current_Release" not in text and "jsonl.gz" not in text and NEW_STAGE not in text
    assert "\nprivate:" not in text  # the private group only with --private
    assert sorted(p for p in tmp_path.rglob("*") if p.is_file()) == before


def test_disk_write_deletes_only_what_is_proven(tmp_path, monkeypatch):
    parts = disk_repo(tmp_path)
    receipted = [
        parts["old"] / "1996.txt",
        tmp_path / "feedback/Old_Release.zip",
        tmp_path / "data/archive/merged250101.tar.zst",
    ]
    objects, _ = proofs(tmp_path, receipted, monkeypatch)
    objects[f"gdrive:ark-offsite/submissions/phase-9/{NEW_STAGE}.tar.gz"] = {
        "Hashes": {"sha256": "b" * 64}
    }
    bulk_sha1 = hashlib.sha1(b"a usenet zip").hexdigest()
    archive_org(
        monkeypatch,
        {
            ("host_cdx_ia600702", "ia600702.hostcdx.gz"): {"size": "12"},
            ("usenet-alt", "alt.test.mbox.zip"): {"size": "12", "sha1": bulk_sha1},
        },
    )
    code, lines = prune.disk_cleanup(tmp_path, write=True)
    gone = [
        *receipted,
        parts["host"] / "ia600702.hostcdx.gz",
        parts["bulk"] / "alt.test.mbox.zip",
        tmp_path / f"output/{OLD_STAGE}/report.md",
    ]
    assert not any(p.exists() for p in gone), lines
    stays = [
        tmp_path / "feedback/Current_Release.zip",
        parts["host"] / "bank.log",
        parts["host"] / "items/hostcdx_ia600702_001_items.jsonl.gz",
        parts["hdr2"] / "demon/demon.test.mbox.zip",
        parts["hdr2"] / "aus_items/shard_000.jsonl.gz",
        tmp_path / f"output/{OLD_STAGE}/journals/one.jsonl.gz",
        tmp_path / f"output/{OLD_STAGE}/SHA256SUMS",
        tmp_path / f"output/{NEW_STAGE}/report.md",
        tmp_path / "data/ark.duckdb.pre-stage-a.bak",
        tmp_path / "data/ark.duckdb.pre-166.bak",
        tmp_path / "private/notes.md",
    ]
    assert all(p.exists() for p in stays), [p for p in stays if not p.exists()]
    deleted = (parts["host"] / "DELETED.tsv").read_text().splitlines()
    rel, size, digest, url = deleted[1].split("\t")
    assert (rel, size) == ("ia600702.hostcdx.gz", "12")
    assert digest == "sha256:" + hashlib.sha256(b"the node cdx").hexdigest()
    assert url == "https://archive.org/download/host_cdx_ia600702/ia600702.hostcdx.gz"
    assert "sha1:" in (parts["bulk"] / "DELETED.tsv").read_text()
    assert code == 1  # the backups stay held


def test_a_spent_file_stays_when_archive_org_does_not_match_it(tmp_path, monkeypatch):
    parts = disk_repo(tmp_path)
    proofs(tmp_path, [], monkeypatch)
    archive_org(
        monkeypatch,
        {
            ("host_cdx_ia600702", "ia600702.hostcdx.gz"): {"size": "999"},
            ("usenet-alt", "alt.test.mbox.zip"): {"size": "12", "sha1": "0" * 40},
        },
    )
    _, lines = prune.disk_cleanup(tmp_path, write=True)
    text = "\n".join(lines)
    assert (parts["host"] / "ia600702.hostcdx.gz").exists()
    assert (parts["bulk"] / "alt.test.mbox.zip").exists()
    assert "archive.org holds 999 B" in text and "archive.org's sha1 differs" in text
    assert not (parts["host"] / "DELETED.tsv").exists()


def test_a_spent_file_changed_since_its_digest_is_held(tmp_path, monkeypatch):
    parts = disk_repo(tmp_path)
    (parts["host"] / "ia600702.hostcdx.gz").write_bytes(b"rewritten after hashing")
    _, lines = prune.disk_cleanup(tmp_path)
    assert "changed since its digest was recorded" in "\n".join(lines)


def test_an_old_stage_waits_for_the_newest_tarball_on_drive(tmp_path, monkeypatch):
    disk_repo(tmp_path)
    proofs(tmp_path, [], monkeypatch)  # Drive holds no tarball
    archive_org(monkeypatch, {})
    _, lines = prune.disk_cleanup(tmp_path, write=True)
    assert (tmp_path / f"output/{OLD_STAGE}/report.md").exists()
    assert f"HELD output/{OLD_STAGE}/report.md: Drive" in "\n".join(lines)


def test_private_keeps_what_code_reads_and_goes_only_with_the_flag(tmp_path, monkeypatch):
    disk_repo(tmp_path)
    proofs(tmp_path, [], monkeypatch)
    archive_org(monkeypatch, {})
    prune.disk_cleanup(tmp_path, write=True)
    assert (tmp_path / "private/notes.md").exists()
    prune.disk_cleanup(tmp_path, write=True, private=True)
    for kept in ("personal-context.md", "handoff.md", "mail/verdict.txt"):
        assert (tmp_path / "private" / kept).exists()
    assert not (tmp_path / "private/notes.md").exists()
    assert not (tmp_path / "private/v3/big.bin").exists()
    with pytest.raises(SystemExit):
        prune.main(["--private", "--root", str(tmp_path)])


def test_the_never_list(tmp_path):
    disk_repo(tmp_path)
    for rel in (
        "submissions/phase-9/x.tar.gz",
        "data/raw/usenet_hdr2/aus_items/shard_000.jsonl.gz",
        "data/raw/host_cdx/items/hostcdx_ia600702_001_items.jsonl.gz",
        "data/raw/host_cdx/SHA256SUMS",
        "data/raw/host_cdx/DELETED.tsv",
        "data/raw/cdx/collector.txt",  # keep_journal
        "data/raw/afnic/zone.txt",  # live_input
        "data/raw/antispam_media/x.bin",  # keep_until_priced
    ):
        assert prune.never(tmp_path, tmp_path / rel), rel
    assert prune.never(tmp_path, tmp_path / "data/raw/host_cdx/ia600702.hostcdx.gz") == ""


def test_store_backups_are_listed_and_never_deleted(tmp_path, monkeypatch):
    disk_repo(tmp_path)
    proofs(tmp_path, [tmp_path / "data/ark.duckdb.pre-166.bak"], monkeypatch)
    archive_org(monkeypatch, {})
    code, lines = prune.disk_cleanup(tmp_path, write=True)
    text = "\n".join(lines)
    assert (tmp_path / "data/ark.duckdb.pre-stage-a.bak").exists()
    assert (tmp_path / "data/ark.duckdb.pre-166.bak").exists()  # even with a receipt
    assert "pre-stage-a.bak: held until #181's rebuild restores the rows only it holds" in text
    assert "pre-166.bak: a store backup is deleted by the agents that own the store" in text
    assert code == 1
