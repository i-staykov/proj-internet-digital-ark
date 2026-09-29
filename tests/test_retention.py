"""Retention: what goes off-site, what a deletion needs, and what nothing may delete.

Temporary trees only: Drive is the folder tmp_path/remote, archive.org a dict.
"""

import hashlib
import http.client
import json
import os
import shutil
import subprocess
import sys
import zipfile
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import script

ROOT = Path(__file__).resolve().parents[1]
prune = sys.modules.get("prune") or script("round/prune.py", "prune")
offsite, vr = prune.sibling("offsite"), prune.sibling("verify_raw")
RETENTION, JOURNAL = "docs/registers/retention.md", "data/raw/journal/a"
HASHES = ("sha256", "sha1")
ROWS = {  # entry: class, refetch; the two output/ rows are verify_raw's own
    "data/raw/journal": ("keep_journal", "own_journal"),
    "data/raw/priced": ("keep_until_priced", "https://x"),
    "data/raw/live": ("live_input", "unknown"),
    "data/raw/checksums.sha256": ("reference", "none"),  # `none` is no route: off-site
    "data/raw/regen": ("regenerable", "just reproduce"),
    "data/raw/usenet_bulk": ("keep_until_priced", "https://y"),
    "output/provenance": vr.classify("output/provenance"),
    "output/netnew": vr.classify("output/netnew"),
    "data/raw/nosum": ("keep_until_priced", "unknown"),  # and no checksum record at all
}
PAYLOAD = ["data/raw/checksums.sha256", "data/raw/journal", "data/raw/live", "data/raw/priced"]
PAYLOAD += ["output/provenance"]
REMOTE_FAULTS = {
    "missing": lambda objects: objects.pop(),
    "hashless": lambda objects: objects[0].update(Hashes={}),
    "different": lambda objects: objects[0]["Hashes"].update(sha256="0" * 64),
    "duplicate": lambda objects: objects.append(objects[0]),
    "failed": lambda objects: None,
}
STALE = ("files-1", "files+1", "size-1", "size+1", "undeclared", "same-size-edit")
OTHER = ("rclone-error", "interrupt-after-one", "no-manifest", "bad-manifest")
RECEIPT_FAULTS = ("stale", "future", "wrong-root", "wrong-remote", "no-receipt")
OBJECT_FAULTS = {"missing": None, "hashless": {"Hashes": {}}, "size": {"Size": 1}}
OBJECT_FAULTS |= {"changed": {"Hashes": {"sha256": "0" * 64}}, "dir": {"IsDir": True}, "failed": {}}
BACKUP = ("released", "dry-run", "same-day", "uncredited", "check", "wal")
BACKUP += ("missing-store", "store-replaced", "backup-changed")
ZIP_FAULTS = {
    "no-receipt": lambda tree, archive: (tree.parents[2] / offsite.RECEIPT).unlink(),
    "remote": lambda tree, archive: shutil.rmtree(tree.parents[2] / "remote"),
    "extra": lambda tree, archive: (tree / "unique.txt").write_text("local-only"),
    "missing": lambda tree, archive: (tree / "1996.txt").unlink(),
    "crc": lambda tree, archive: (tree / "1996.txt").write_bytes(OLD.upper().encode()),
    "symlink": lambda tree, archive: (tree / "unique.txt").symlink_to(tree / "1996.txt"),
    "stale": lambda tree, archive: archive.write_bytes(archive.read_bytes() + b"updated"),
}
OLD_STAGE, NEW_STAGE = (f"DomainDataCollectionTask_2026010{d}0000_IvayloStaykov" for d in (1, 2))
CURRENT, OLD = "feedback/Current_Release/merged261231", "feedback/Old_Release/merged260101"
CDX, ZIP, TARBALL = b"the node cdx", b"a usenet zip", b"the round as sent"
HOST, SPENT = ("host_cdx_ia600702", "ia600702.hostcdx.gz"), "data/raw/host_cdx/ia600702.hostcdx.gz"
UNLISTED = ("Current_Release", "Newer_Release", "merged270101", "Both.zip", "jsonl.gz")
UNLISTED += (NEW_STAGE, "feedback-phase-9", "README.md", "\nprivate:")
# PRIVATE_KEEP, and a journal, which never() keeps even in private/
KEPT_PRIVATE = ("personal-context.md", "handoff.md", "mail/verdict.txt", "emails/a.eml")
KEPT_PRIVATE += ("email-draft.md", "email.template.md", "work/x.jsonl.gz")
HELD = f"HELD {SPENT}: "
SPENT_CASES = {
    "restricted-served": ({"restricted": True}, f"removed: {SPENT}"),
    "private": ({"private": "true"}, HELD + "archive.org lists the file as private"),
    "restricted-unserved": ({"restricted": True}, HELD + "archive.org restricts"),
    "size": ({"size": "999"}, HELD + "archive.org holds 999 B"),
    "sha1": ({"sha1": "0" * 40}, HELD + "the sha1 of our bytes differs"),
    "no-sha1": ({"sha1": ""}, HELD + "archive.org gives no sha1"),
    "absent": (None, HELD + "archive.org has no host_cdx_ia600702"),
    "changed": ({}, HELD + "changed since its digest was recorded"),
    "changed-at-delete": ({}, HELD + "changed before deletion"),
    "incomplete-read": (http.client.IncompleteRead(b""), HELD + "IncompleteRead"),
    "interrupt": (KeyboardInterrupt(), f"interrupted at {SPENT}"),
}
NEVER = ("submissions/phase-9/x.tar.gz", "data/raw/usenet_hdr2/aus_items/s.jsonl.gz")
NEVER += ("data/raw/host_cdx/items/x.jsonl.gz", "data/raw/ietf_header_items/x.jsonl")
NEVER += ("data/raw/host_cdx/SHA256SUMS", "data/raw/host_cdx/DELETED.tsv")
NEVER += ("data/raw/cdx/c", "data/raw/afnic/z", "data/raw/antispam_media/x")  # held classes


def sha(data: bytes, kind: str = "sha256") -> str:
    return hashlib.new(kind, data).hexdigest()


def file(root: Path, rel: str, content: bytes = b"original\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def files_under(root: Path) -> set[Path]:
    return {p for p in root.rglob("*") if p.is_file()}


@pytest.fixture(autouse=True)
def fake_rclone(tmp_path, monkeypatch):
    def lsjson(args, check=True):
        assert args[0] == "lsjson" and "--hash" in args
        dest = Path(args[-1].replace(offsite.REMOTE, str(tmp_path / "remote"), 1))
        assert dest.is_relative_to(tmp_path)
        if not dest.exists():
            return subprocess.CompletedProcess(args, 3, "", "not found")
        found = [dest] if dest.is_file() else sorted(files_under(dest))
        objects = [
            {"Path": p.name if p == dest else p.relative_to(dest).as_posix(), "IsDir": False}
            | {"Size": p.stat().st_size, "Hashes": {k: sha(p.read_bytes(), k) for k in HASHES}}
            for p in found
        ]
        out = objects[0] if "--stat" in args else objects
        return subprocess.CompletedProcess(args, 0, json.dumps(out), "")

    monkeypatch.setattr(offsite, "rclone", mock := Mock(side_effect=lsjson))
    return mock


def build(root: Path, drop: str | None = "data/raw/nosum") -> None:
    for key in ROWS:
        file(root, key if key.endswith(".sha256") else f"{key}/a", key.encode())
    file(root, "data/raw/journal/2001/b")
    scanned, body = {r.key: r for r in vr.run(root).rows}, ""
    unlisted = {(r.cls, r.refetch) for r in scanned.values() if not r.known}
    assert unlisted == {("reference", vr.UNKNOWN)}  # an unlisted entry goes off-site
    for key, (cls, refetch) in ROWS.items():
        record = "none" if key.endswith("nosum") else "SHA256SUMS"
        cells = (f"`{key}`", cls, scanned[key].files, scanned[key].size, record, refetch, record)
        body += f"| {' | '.join(map(str, cells))} |\n" if key != drop else ""
    file(root, RETENTION, body.encode())


def run(root: Path, *args: str) -> int:
    return offsite.main(["--root", str(root), *args])


@pytest.fixture
def verified(tmp_path, fake_rclone):
    build(tmp_path)
    for path in sorted(files_under(tmp_path / "data/raw") | files_under(tmp_path / "output")):
        if path.name not in offsite.SIDECARS:  # what `--upload --yes` leaves on Drive
            shutil.copyfile(path, file(tmp_path, f"remote/{path.relative_to(tmp_path)}"))
    assert run(tmp_path, "--manifest") == run(tmp_path, "--verify") == 0
    fake_rclone.reset_mock()
    return tmp_path


def test_the_payload_is_what_nothing_else_brings_back_and_no_report_deletes(tmp_path, capsys):
    build(tmp_path, drop=None)
    assert vr.classify("output/provenance") == ("keep_authority", vr.OWN)
    assert run(tmp_path, "--manifest") == 1
    assert "data/raw/nosum" in capsys.readouterr().out.split("REFUSED")[1]
    assert sorted(r.entry for r in offsite.read_manifest(tmp_path / offsite.MANIFEST)) == PAYLOAD
    backup = prune.Entry("data/ark.duckdb.pre-stage-a.bak", "regenerable", 1, 8, "d", "x", "row")
    assert offsite.payload([backup]) == ([], [], [])  # a store backup never goes off-site
    entries = {e.key: e for e in prune.read_table(tmp_path / RETENTION)}
    freed = ["data/raw/priced", "data/raw/regen", "data/raw/usenet_bulk", "output/netnew"]
    assert sorted(k for k, e in entries.items() if e.deletable) == freed
    assert entries["data/raw/nosum"].missing == ["no refetch route", "no checksum record"]
    before = {p: p.read_bytes() for p in files_under(tmp_path)}
    flags = (["--delete"], ["--force"], ["--apply=yes"], ["--json"])
    assert [prune.main(["--table", str(tmp_path / RETENTION), *f]) for f in flags] == [2, 2, 2, 0]
    assert run(tmp_path, "--upload") == 0
    out, err = capsys.readouterr()
    assert err.count("never deletes") == 3 and '"deletes": false' in out and "Nothing ran" in out
    assert out.count("rclone copy --checksum") == len(PAYLOAD)
    assert not any(word in out for word in ("--delete", "rclone sync", "rclone move", "purge"))
    assert {p: p.read_bytes() for p in files_under(tmp_path)} == before


@pytest.mark.parametrize("fault", [*REMOTE_FAULTS, *STALE, *OTHER])
def test_a_verify_that_cannot_vouch_for_the_bytes_revokes_them(verified, fake_rclone, fault):
    rows = offsite.read_manifest(manifest := verified / offsite.MANIFEST)
    row = next(r for r in rows if r.entry == "data/raw/journal")
    objects = list(offsite.remote_listing(row, verified, offsite.REMOTE)[0].values())
    fake_rclone.reset_mock()
    if fault in REMOTE_FAULTS:
        REMOTE_FAULTS[fault](objects)
        done = subprocess.CompletedProcess([], int(fault == "failed"), json.dumps(objects), "no")
        fake_rclone.side_effect, fake_rclone.return_value = None, done
    elif fault in STALE[:4]:  # every remote hash matches, yet the row no longer fits
        stale = replace(row, **{fault[:-2]: getattr(row, fault[:-2]) + int(fault[-2:])})
        manifest.write_text(offsite.render([stale if r == row else r for r in rows]))
        assert len(offsite.check_entry(stale, verified, offsite.REMOTE).matched) == row.files
    elif fault == "undeclared":
        file(verified, "data/raw/journal/undeclared.jsonl")
    elif fault == "same-size-edit":  # the same size, and the old mtime put back
        before = (verified / JOURNAL).stat()
        file(verified, JOURNAL, b"x" * before.st_size)
        os.utime(verified / JOURNAL, ns=(before.st_atime_ns, before.st_mtime_ns))
        pytest.raises(ValueError, offsite.deletion_proof, verified, verified / JOURNAL)
    elif fault == "rclone-error":
        fake_rclone.side_effect = subprocess.SubprocessError("x")
    elif fault == "interrupt-after-one":  # one entry matched, then the run stopped
        first = fake_rclone.side_effect(["lsjson", "--hash", f"{offsite.REMOTE}/{row.entry}"])
        fake_rclone.side_effect = [first, KeyboardInterrupt()]
    elif fault == "no-manifest":
        manifest.unlink()
    else:
        manifest.write_text("invalid row\n")
    if raised := {"interrupt-after-one": KeyboardInterrupt, "bad-manifest": ValueError}.get(fault):
        pytest.raises(raised, run, verified, "--verify")
    else:
        assert run(verified, "--verify") == (2 if fault == "no-manifest" else 1)
    receipt = offsite.read_receipt(verified)
    assert JOURNAL not in receipt and (not receipt or fault in STALE)
    assert fake_rclone.called is ("manifest" not in fault)
    pytest.raises(ValueError, offsite.deletion_proof, verified, verified / JOURNAL)


@pytest.mark.parametrize("fault", [*RECEIPT_FAULTS, *OBJECT_FAULTS])
def test_a_proof_needs_a_fresh_receipt_and_a_live_match(verified, fake_rclone, monkeypatch, fault):
    path, receipt = verified / JOURNAL, verified / offsite.RECEIPT
    now = (saved := json.loads(receipt.read_text()))["verified_at"]
    monkeypatch.setattr(offsite.time, "time", lambda: now)
    edits = {"stale": {"verified_at": now - offsite.MAX_AGE - 1}, "wrong-remote": {"remote": "x:"}}
    edits |= {"future": {"verified_at": now + 1}, "wrong-root": {"root": str(verified / "x")}}
    if fault in OBJECT_FAULTS:
        good = {"Size": path.stat().st_size, "Hashes": {"sha256": sha(path.read_bytes())}}
        obj = {} if fault == "missing" else good | OBJECT_FAULTS[fault]
        done = subprocess.CompletedProcess([], int(fault == "failed"), json.dumps(obj), "")
        fake_rclone.side_effect, fake_rclone.return_value = None, done
    elif fault in edits:
        receipt.write_text(json.dumps(saved | edits[fault]))
    else:
        receipt.unlink()
    pytest.raises(ValueError, offsite.deletion_proof, verified, path)
    assert fake_rclone.call_count == int(fault in OBJECT_FAULTS)


def test_a_check_verifies_every_named_file_matched_and_nothing_noted():
    row = offsite.Row("j", "c", 8, 2, "d", "w")
    cases = ((2, ""), (0, ""), (1, ""), (3, ""), (2, "x"))
    checks = [offsite.Check(replace(row, files=f), matched=["a", "b"], note=n) for f, n in cases]
    assert [c.verified for c in checks] == [True, False, False, False, False]


def proofs(root: Path, paths: list[Path]) -> None:
    records = {}
    for path in paths:
        key = path.relative_to(root).as_posix()
        shutil.copyfile(path, file(root, f"remote/{key}"))
        stat = offsite.signature(root, path)
        records[key] = {"stat": stat, "kind": "sha256", "digest": sha(path.read_bytes())}
    offsite.write_receipt(root, offsite.REMOTE, records)


@pytest.mark.parametrize("case", BACKUP)
def test_a_backup_goes_after_a_later_credited_round_and_a_clean_check(tmp_path, monkeypatch, case):
    backup = file(tmp_path, "data/ark.duckdb.pre-test.bak", b"previous")
    os.utime(backup, ns=(1_000_000, 1_000_000))
    store = file(tmp_path, "data/ark.duckdb", b"current")
    day = "1970-01-01" if case == "same-day" else "2026-09-05"
    rounds = [{"date": day, "awarded_percent": "" if case == "uncredited" else "18.7"}]
    file(tmp_path, "data/baseline.json", json.dumps({"rounds": rounds}).encode())
    if case == "wal":
        file(tmp_path, "data/ark.duckdb.wal")
    if case == "missing-store":
        store.unlink()
    calls = []

    def ark_check(args, **kwargs):
        calls.append((args, kwargs))
        if case == "store-replaced":  # another store moved into place while the check ran
            file(tmp_path, "data/ark.duckdb.next", b"updated").replace(store)
        if case == "backup-changed":
            backup.write_bytes(b"new local-only backup")
        return SimpleNamespace(returncode=int(case == "check"))

    monkeypatch.setattr(prune.subprocess, "run", ark_check)
    code, lines = prune.round_cleanup(tmp_path, write=case != "dry-run")
    released = case in ("released", "dry-run")
    assert code == int(not released) and backup.exists() is (case != "released")
    checked = case in ("released", "check", "store-replaced", "backup-changed")
    assert calls == [(["uv", "run", "ark", "check"], {"cwd": tmp_path, "check": False})] * checked
    assert released or "HELD data/ark.duckdb.pre-test.bak" in "\n".join(lines)
    kept = b"new local-only backup" if case == "backup-changed" else b"previous"
    assert case == "released" or backup.read_bytes() == kept


@pytest.mark.parametrize("fault", ["ok", "dry-run", "second-release", *ZIP_FAULTS])
def test_a_release_zip_goes_only_when_every_tree_it_holds_matches_it(tmp_path, fault):
    """Receipted files under submissions/, output/ and data/raw are never in scope."""
    tree, archive = disk_repo(tmp_path)["old"], tmp_path / "feedback/Old_Release.zip"
    if fault == "second-release":
        with zipfile.ZipFile(archive, "a") as zf:
            zf.writestr("another/merged250505/1996.txt", b"another.org")
    scoped = [tmp_path / SPENT, tmp_path / f"output/{NEW_STAGE}/report.md"]
    scoped += [tmp_path / f"submissions/phase-9/{NEW_STAGE}.tar.gz.sha256"]
    proofs(tmp_path, [archive, *scoped])
    before = {p.name: p.read_bytes() for p in tree.iterdir()}
    ZIP_FAULTS.get(fault, lambda *a: None)(tree, archive)
    lines = prune.round_cleanup(tmp_path, write=fault != "dry-run")[1]
    assert ("removed: feedback/Old_Release.zip" in lines) is (fault == "ok")
    assert archive.exists() is (fault != "ok") and all(p.exists() for p in scoped)
    assert fault != "ok" or {p.name: p.read_bytes() for p in tree.iterdir()} == before


def test_every_ingest_and_export_has_an_independent_space_guard():
    lines = (ROOT / "justfile").read_text().splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith(("uv run ark ingest", "uv run ark export")):
            assert "bank_hygiene.py space" in lines[i - 1] and "|| true" not in lines[i - 1], line
    run = [line.strip() for line in lines[lines.index("run *args:") :]]  # `just run export`
    assert run[run.index("ingest*|export)") + 1].endswith("bank_hygiene.py space")


def sums(folder: Path, files: list[str], kind: str = "SHA256SUMS") -> None:
    """The sidecars verify_raw writes: digests, and the (size, mtime_ns) each was taken at."""
    lines = [f"{sha((folder / r).read_bytes(), kind[:-4].lower())}  ./{r}\n" for r in files]
    file(folder, kind, "".join(lines).encode())
    stats = [(folder / r).stat() for r in files]
    lines = [f"{st.st_size} {st.st_mtime_ns} ./{r}\n" for r, st in zip(files, stats, strict=True)]
    file(folder, "SHA256SUMS.stat", "".join(lines).encode())


def disk_repo(root: Path) -> dict[str, Path]:
    (root / "feedback").mkdir()
    file(root, "data/baseline.json", json.dumps({"current": {"directory": CURRENT}}).encode())
    trees = {CURRENT: ["1996.txt"], "feedback/Newer_Release/merged270101": ["1996.txt"]}
    for tree, names in (trees | {OLD: ["1996.txt", "README.md"]}).items():
        with zipfile.ZipFile(root / f"{Path(tree).parent}.zip", "w") as zf:
            for name in names:
                zf.write(file(root, f"{tree}/{name}", tree.encode()), f"{Path(tree).name}/{name}")
    with zipfile.ZipFile(root / "feedback/Both.zip", "w") as zf:  # an old release and the current
        for tree in (OLD, CURRENT):
            zf.write(root / tree / "1996.txt", f"{Path(tree).name}/1996.txt")
    kept = [f"output/{OLD_STAGE}/{r}" for r in ("report.md", "journals/one.jsonl.gz", "SHA256SUMS")]
    kept += [f"feedback/feedback-phase-9/{r}" for r in ("Round_9.docx", "round-9.md", "notes.txt")]
    kept += [f"private/{r}" for r in ("notes.md", "v3/big.bin", *KEPT_PRIVATE)]
    kept += [f"data/archive/merged{m}.tar.zst" for m in (250101, 270101)]
    kept += ["feedback/partial.zip", f"output/{NEW_STAGE}/report.md", "data/raw/host_cdx/bank.log"]
    for rel in [*kept, "data/ark.duckdb.pre-166.bak"]:
        file(root, rel)
    sidecar = f"{sha(TARBALL)}  {NEW_STAGE}.tar.gz\n".encode()
    file(root, f"submissions/phase-9/{NEW_STAGE}.tar.gz.sha256", sidecar)
    host, bulk, hdr2 = (root / f"data/raw/{n}" for n in ("host_cdx", "usenet_bulk", "usenet_hdr2"))
    file(host, "ia600702.hostcdx.gz", CDX), file(host, "items/x.jsonl.gz")
    sums(host, ["ia600702.hostcdx.gz", "bank.log", "items/x.jsonl.gz"])
    file(bulk, "alt.test.mbox.zip", ZIP)
    sums(bulk, ["alt.test.mbox.zip"], "SHA1SUMS")
    file(bulk, "alt.cut.mbox.zip", b"partial")
    sums(bulk, ["alt.test.mbox.zip", "alt.cut.mbox.zip"])  # SHA1SUMS stays, stats for both
    catalog = [("alt.test.mbox.zip", sha(ZIP, "sha1"), "12"), ("alt.cut.mbox.zip", "c" * 40, "999")]
    catalog = {"alt": [{"name": n, "sha1": s, "size": size} for n, s, size in catalog]}
    file(root, "data/raw/usenet_catalog.json", json.dumps(catalog).encode())
    file(hdr2, "demon/demon.test.mbox.zip", b"uncatalogued"), file(hdr2, "aus_items/s.jsonl.gz")
    sums(hdr2, ["demon/demon.test.mbox.zip", "aus_items/s.jsonl.gz"])
    return {"old": root / OLD, "host": host, "bulk": bulk}


def cleanup(root: Path, **flags) -> str:
    return "\n".join(prune.disk_cleanup(root, write=True, **flags)[1])


def test_disk_takes_exactly_what_is_proven(tmp_path, monkeypatch, capsys, fake_rclone):
    """A dry run touches nothing; a write takes what is proven; private/ needs --owner-go."""
    parts = disk_repo(tmp_path)
    for rel in ("notes/deep/a.md", "notes/.DS_Store", "mixed/go.md", "mixed/keep.jsonl.gz"):
        file(tmp_path, f"private/{rel}")
    (tmp_path / "private/empty").mkdir()  # empty before the run, so not this run's to remove
    monkeypatch.setattr(offsite, "rclone", lambda *a, **k: pytest.fail("the dry run went to Drive"))
    monkeypatch.setattr(prune, "ia_file", lambda *a: pytest.fail("the dry run went to archive.org"))
    before = files_under(tmp_path)
    code, lines = prune.disk_cleanup(tmp_path)
    text = "\n".join(lines)
    assert code == 1 and files_under(tmp_path) == before  # the store backups are always held
    assert f"would remove: {SPENT}" in text and "HELD feedback/Old_Release.zip: no Drive" in text
    assert "HELD data/raw/usenet_bulk/alt.cut.mbox.zip: 7 B here, 999 B in the catalog" in text
    assert [never for never in UNLISTED if never in text] == []  # private/ only with --private
    out, err = capsys.readouterr()
    assert "skip feedback/partial.zip: not a zip" in err
    assert str(tmp_path) not in text + out + err  # the list goes on a public issue
    receipted = [parts["old"] / "1996.txt", tmp_path / "feedback/Old_Release.zip"]
    receipted += [tmp_path / "data/archive/merged250101.tar.zst"]
    proofs(tmp_path, [*receipted, tmp_path / "data/ark.duckdb.pre-166.bak"])
    file(tmp_path, f"remote/submissions/phase-9/{NEW_STAGE}.tar.gz", TARBALL)
    monkeypatch.setattr(offsite, "rclone", fake_rclone)
    ia = {HOST: {"size": "12", "sha1": sha(CDX, "sha1")}}
    ia[("usenet-alt", "alt.test.mbox.zip")] = {"size": "12", "sha1": sha(ZIP, "sha1")}
    monkeypatch.setattr(prune, "ia_file", lambda item, name, cache: ia.get((item, name)))
    unlink = Path.unlink

    def recorded_first(path, *a, **k):
        if "data/raw" in path.as_posix():
            assert path.name in (path.parent / "DELETED.tsv").read_text()
        unlink(path, *a, **k)

    monkeypatch.setattr(Path, "unlink", recorded_first)
    before = files_under(tmp_path)
    code, lines = prune.disk_cleanup(tmp_path, write=True)
    gone = [tmp_path / SPENT, parts["bulk"] / "alt.test.mbox.zip"]
    gone += [*receipted, tmp_path / f"output/{OLD_STAGE}/report.md"]
    assert before - files_under(tmp_path) == set(gone), lines
    rel, size, digest, url = (parts["host"] / "DELETED.tsv").read_text().splitlines()[1].split("\t")
    assert (rel, size, url) == (HOST[1], "12", f"{prune.IA}/download/{HOST[0]}/{HOST[1]}")
    assert digest == f"sha1:{sha(CDX, 'sha1')} sha256:{sha(CDX)}"
    assert f"sha1:{sha(ZIP, 'sha1')}\t" in (parts["bulk"] / "DELETED.tsv").read_text()
    text = "\n".join(lines)
    assert code == 1 and "pre-166.bak: a store backup is deleted by the agents" in text  # receipted
    before = files_under(tmp_path)
    code, lines = prune.disk_cleanup(tmp_path, write=True, private=True)
    assert code == 1 and "without --owner-go: nothing was deleted" in lines[0]
    assert "  would remove: private/notes.md" in lines and files_under(tmp_path) == before
    for argv in (["--private"], ["--disk", "--owner-go"], ["--disk", "--private", "--owner-go"]):
        pytest.raises(SystemExit, prune.main, [*argv, "--root", str(tmp_path)])
    text = cleanup(tmp_path, private=True, owner_go=True)
    assert all(f"  removed folder: private/{f}" in text for f in ("notes/deep", "notes", "v3"))
    for gone in ("notes", "v3", "notes.md", "mixed/go.md"):
        assert not (tmp_path / "private" / gone).exists(), gone
    for kept in ("empty", "mixed/keep.jsonl.gz", *KEPT_PRIVATE):
        assert (tmp_path / "private" / kept).exists(), kept


@pytest.mark.parametrize("case", SPENT_CASES)
def test_a_spent_file_goes_only_when_archive_org_serves_our_bytes(tmp_path, monkeypatch, case):
    disk_repo(tmp_path)
    spent, (record, line) = tmp_path / SPENT, SPENT_CASES[case]
    if isinstance(record, BaseException):
        monkeypatch.setattr(prune, "ia_file", Mock(side_effect=record))
    else:
        ia = None if record is None else {"size": "12", "sha1": sha(CDX, "sha1")} | record
        monkeypatch.setattr(prune, "ia_file", lambda *a: {HOST: ia}.get(a[:2]))
    monkeypatch.setattr(prune, "ia_serves", lambda url: case != "restricted-unserved")
    if case == "sha1":  # the sidecar sha1 agrees with archive.org; our bytes do not
        file(spent.parent, "SHA1SUMS", f"{'0' * 40}  ./{HOST[1]}\n".encode())
    if case == "changed":
        spent.write_bytes(b"rewritten after hashing")
    if case == "changed-at-delete":  # moved after its DELETED.tsv line, before the unlink
        written = prune.record_deleted
        monkeypatch.setattr(prune, "record_deleted", lambda *a: written(*a) or os.utime(spent))
    assert line in cleanup(tmp_path)
    assert spent.exists() is (case != "restricted-served")
    wrote = case in ("restricted-served", "changed-at-delete")
    assert (spent.parent / "DELETED.tsv").exists() is wrote


def test_usenet_new_goes_where_its_saved_ia_metadata_routes_it(tmp_path, monkeypatch):
    """A zip goes at its route once our bytes hash to IA's sha1: each item asked once, through
    fetch.py, and nothing asked after a failed ask."""
    new = tmp_path / "data/raw/usenet_new"
    theirs = {"bit": {"bit.c.mbox.zip": b"same", "free.c.mbox.zip": b"off its route"}}
    theirs["free"] = {"free.a.mbox.zip": b"same", "free.b.mbox.zip": b"IA's", "free.d.txt": b"x"}
    theirs["free"]["free.e.mbox.zip"] = b"md5!"
    ours = theirs["bit"] | theirs["free"] | {"free.b.mbox.zip": b"ours"}
    meta = {}
    for h, got in theirs.items():
        files = [{"name": n, "size": str(len(b)), "sha1": sha(b, "sha1")} for n, b in got.items()]
        meta[f"usenet-{h}"] = {"metadata": {"identifier": f"usenet-{h}"}, "files": files}
    meta["usenet-free"]["files"][-1] |= {"sha1": "", "md5": sha(b"md5!", "md5")}  # no sha1
    others = ["usenet_dated_new1.jsonl.gz", ".banked/free.a.mbox.zip.ok"]
    for name, data in (ours | dict.fromkeys(others, b"x")).items():
        file(new, name, data)
    sums(new, [*ours, *others])
    for item, answer in meta.items():
        file(new, f".meta-{item[7:]}.json", json.dumps(answer).encode())
    file(new, ".meta-gov.json", b"<html>500</html>")  # an error page saved as the metadata
    stale = f"free.a.mbox.zip\t4\tsha1:{'0' * 40}\tx"  # a copy deleted before, other bytes
    file(new, "DELETED.tsv", f"# rel\tbytes\tdigest\turl\n{stale}\n".encode())
    file(tmp_path, "data/baseline.json", json.dumps({"current": {"directory": CURRENT}}).encode())
    asked, exit_code = [], [7]

    def fetch(command, **kwargs):
        assert command[1] == str(ROOT / "scripts/harness/fetch.py")
        assert command[3:5] == ["--to", "-"]
        asked.append(command[2].rsplit("/", 1)[1])
        answer = json.dumps(meta[asked[-1]]).encode()
        return subprocess.CompletedProcess(command, exit_code[0], answer)

    monkeypatch.setattr(prune.subprocess, "run", fetch)
    before, text = files_under(new), cleanup(tmp_path)
    assert f"free.b.mbox.zip: {prune.IA}/metadata/usenet-bit: fetch.py exit 7" in text
    assert asked == ["usenet-bit"] and files_under(new) == before
    asked[:], exit_code[0] = [], 0
    text = cleanup(tmp_path)
    assert asked == ["usenet-bit", "usenet-free"]
    assert "HELD data/raw/usenet_new/free.b.mbox.zip: the sha1 of our bytes differs" in text
    assert "kept 2 archives of data/raw/usenet_new, 17 B: no catalog lists them" in text
    assert before - files_under(new) == {new / "bit.c.mbox.zip", new / "free.a.mbox.zip"}
    assert f"free.a.mbox.zip\t4\tsha1:{sha(b'same', 'sha1')} " in (new / "DELETED.tsv").read_text()


def test_an_old_stage_waits_for_the_newest_tarball_on_drive(tmp_path, monkeypatch):
    disk_repo(tmp_path)
    monkeypatch.setattr(prune, "ia_file", lambda *a: None)
    held = f"HELD output/{OLD_STAGE}/report.md: Drive"
    assert f"{held} did not list" in cleanup(tmp_path)
    file(tmp_path, f"remote/submissions/phase-9/{NEW_STAGE}.tar.gz", b"another tarball")
    assert f"{held}'s {NEW_STAGE}.tar.gz does not match its checksum" in cleanup(tmp_path)
    monkeypatch.setattr(offsite, "rclone", Mock(side_effect=FileNotFoundError("rclone")))
    assert f"{held} did not answer" in cleanup(tmp_path)
    assert (tmp_path / f"output/{OLD_STAGE}/report.md").exists()


def test_archive_org_restricts_a_dark_or_restricted_item_and_asks_for_one_byte(monkeypatch):
    items = {"dark": {"is_dark": True}, "open": {}}
    items["walled"] = {"metadata": {"access-restricted-item": "true"}}
    cache = {item: meta | {"files": [{"name": "f"}]} for item, meta in items.items()}
    assert [prune.ia_file(item, "f", cache)["restricted"] for item in items] == [True, False, True]
    urlopen = Mock(side_effect=[nullcontext(SimpleNamespace(status=206)), OSError("401")])
    monkeypatch.setattr(prune.urllib.request, "urlopen", urlopen)
    assert prune.ia_serves(f"{prune.IA}/open/f") and not prune.ia_serves(f"{prune.IA}/walled/f")
    assert [c.args[0].get_header("Range") for c in urlopen.call_args_list] == ["bytes=0-0"] * 2


@pytest.mark.parametrize("rel", NEVER)
def test_the_never_list(tmp_path, rel):
    assert prune.never(tmp_path, tmp_path / rel) and prune.never(tmp_path, tmp_path / SPENT) == ""


@pytest.mark.parametrize("fault", ["edited", "duplicate-member", "no-marker"])
def test_a_release_tree_is_held_without_a_crc_match_or_a_marker(tmp_path, monkeypatch, fault):
    parts = disk_repo(tmp_path)
    tree_file, archive = parts["old"] / "1996.txt", tmp_path / "feedback/Old_Release.zip"
    if fault == "edited":
        tree_file.write_bytes(b"edited after zipping\n")
    elif fault == "no-marker":  # baseline.json names no marker, so every release is held
        file(tmp_path, "data/baseline.json", b'{"current": {"directory": "x"}}')
    else:
        with pytest.warns(UserWarning), zipfile.ZipFile(archive, "w") as zf:
            for _ in range(2):
                zf.write(tree_file, "merged260101/1996.txt")
    proofs(tmp_path, [tree_file, archive])
    monkeypatch.setattr(prune, "ia_file", lambda *a: None)
    text = cleanup(tmp_path)
    why = "data/baseline.json names no release marker" if fault == "no-marker" else "CRC check"
    assert tree_file.exists() and f"HELD {OLD}/1996.txt: {why}" in text
    assert fault != "duplicate-member" or "unsafe or duplicate zip member" in text


def test_a_frozen_submission_gets_no_sidecar_of_its_own(tmp_path):
    phase, names = tmp_path / "submissions/phase-4", ("ark.tar.gz", "report.md")
    for name in names:
        file(phase, name, name.encode())
    frozen = next(r for r in vr.run(tmp_path).rows if r.key == "submissions/phase-4")
    assert sorted(p.name for p in phase.iterdir()) == list(names)
    shared = (tmp_path / "submissions/SHA256SUMS").read_text().splitlines()
    assert shared == sorted(f"{sha(n.encode())}  ./phase-4/{n}" for n in names)
    assert vr.within(phase, tmp_path / "submissions", "./phase-40/report.md") is None
    assert (frozen.cls, frozen.files) == ("reference", 2) and frozen.record.startswith("lines in")


def test_a_worktree_reads_the_checkouts_data_and_writes_its_own_table(tmp_path):
    checkout, table = tmp_path / "checkout", tmp_path / "worktree" / RETENTION
    file(checkout / "data/raw/live", "a", b"a")
    vr.main(["--root", str(checkout), "--table", str(table)])
    assert "`data/raw/live`" in table.read_text() and not (checkout / RETENTION).exists()
