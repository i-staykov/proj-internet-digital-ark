"""Offsite verification uses temporary fixtures and never invokes a real remote."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("offsite", REPO / "scripts/round/offsite.py")
offsite = importlib.util.module_from_spec(_SPEC)
# Registered before exec: the dataclasses read their own module back for its annotations.
sys.modules["offsite"] = offsite
_SPEC.loader.exec_module(offsite)

HEAD = """# Retention

| entry | class | files | bytes | digest | refetch | record |
|---|---|---|---|---|---|---|
"""

# One file per entry, plus a nested one, so a tree and a loose file both get covered.
FILES = {
    "data/raw/journal/queries.jsonl": "one\n",
    "data/raw/journal/2001/more.jsonl": "two\n",
    "data/raw/priced/corpus.zip": "three\n",
    "data/raw/live/pages.warc": "four\n",
    "data/raw/checksums.sha256": "five\n",
    "data/raw/regen/derived.txt": "six\n",
    "data/raw/nosum/mystery.bin": "seven\n",
    "data/raw/usenet_bulk/alt.config.zip": "eight\n",
}

# entry, class, digest, refetch, record. `priced` records IA's sha1 the way the Usenet
# zips do; `nosum` has no checksum at all and must never reach the manifest.
ROWS = (
    ("data/raw/journal", "keep_journal", "d1", "own_journal", "SHA256SUMS"),
    ("data/raw/priced", "keep_until_priced", "d2", "https://example.org/corpus.zip", "SHA1SUMS"),
    ("data/raw/live", "live_input", "d3", "unknown", "SHA256SUMS"),
    ("data/raw/checksums.sha256", "reference", "d4", "unknown", "line in data/raw/SHA256SUMS"),
    ("data/raw/regen", "regenerable", "d5", "just reproduce", "SHA256SUMS"),
    (
        "data/raw/usenet_bulk",
        "keep_until_priced",
        "d6",
        "https://archive.org/details/x",
        "SHA1SUMS",
    ),
    ("data/raw/nosum", "keep_until_priced", "none", "unknown", "none"),
)

PAYLOAD = ["data/raw/checksums.sha256", "data/raw/journal", "data/raw/live", "data/raw/priced"]


def holder(root: Path, rel: str) -> tuple[Path, str]:
    """Which manifest a file's line sits in, and the name it is keyed by.

    A tree keeps its own manifest at its root; a loose file shares `data/raw/SHA256SUMS`.
    """
    path = root / rel
    raw = root / "data/raw"
    if path.parent == raw:
        return raw, path.name
    entry = raw / Path(rel).relative_to("data/raw").parts[0]
    return entry, path.relative_to(entry).as_posix()


def build(root: Path, rows=ROWS) -> Path:
    """A tree, the manifests verify_raw.py would have written beside it, and a table."""
    for rel, text in FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    lines: dict[Path, list[str]] = {}
    for rel, text in FILES.items():
        where, name = holder(root, rel)
        if where.name == "nosum":  # the entry whose row says no checksum record
            continue
        sha1 = where.name in ("priced", "usenet_bulk")
        kind = "SHA1SUMS" if sha1 else "SHA256SUMS"
        digest = (hashlib.sha1 if sha1 else hashlib.sha256)(text.encode()).hexdigest()
        lines.setdefault(where / kind, []).append(f"{digest}  ./{name}")
    for path, body in lines.items():
        path.write_text("".join(f"{line}\n" for line in sorted(body)), encoding="utf-8")

    body = ""
    for key, cls, digest, refetch, record in rows:
        local = root / key
        files = [p for p in local.rglob("*") if p.is_file()] if local.is_dir() else [local]
        files = [p for p in files if p.name not in offsite.SIDECARS]
        size = sum(p.stat().st_size for p in files)
        body += f"| `{key}` | {cls} | {len(files)} | {size} | `{digest}` | {refetch} | {record} |\n"
    table = root / "docs/registers/retention.md"
    table.parent.mkdir(parents=True, exist_ok=True)
    table.write_text(HEAD + body, encoding="utf-8")
    return table


def run(root: Path, *args: str) -> int:
    return offsite.main(["--root", str(root), *args])


def manifest_rows(root: Path) -> list[offsite.Row]:
    return offsite.read_manifest(root / offsite.MANIFEST)


@pytest.fixture(autouse=True)
def fake_rclone(tmp_path, monkeypatch):
    def invoke(args, check=True):
        target = args[-1]
        if target.startswith(offsite.REMOTE + "/"):
            target = str(tmp_path / "remote" / target.removeprefix(offsite.REMOTE + "/"))
        destination = Path(target)
        assert destination.is_relative_to(tmp_path)
        if args[0] == "copy":
            source = Path(args[-2])
            assert source.is_relative_to(tmp_path)
            files = sorted(source.rglob("*")) if source.is_dir() else [source]
            copied = False
            for path in files:
                if not path.is_file() or path.name in offsite.SIDECARS:
                    continue
                rel = path.relative_to(source) if source.is_dir() else Path(path.name)
                dest = destination / rel
                if not dest.exists() or dest.read_bytes() != path.read_bytes():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, dest)
                    copied = True
            log = Path(args[args.index("--log-file") + 1])
            assert log.is_relative_to(tmp_path)
            with log.open("a") as stream:
                stream.write("Copied\n" if copied else "There was nothing to transfer\n")
            return subprocess.CompletedProcess(args, 0, "", "")
        assert args[0] == "lsjson" and "--hash" in args
        if not destination.exists():
            return subprocess.CompletedProcess(args, 3, "", "not found")
        files = [destination] if "--stat" in args else sorted(destination.rglob("*"))
        objects = []
        for path in files:
            if not path.is_file():
                continue
            rel = path.name if "--stat" in args else path.relative_to(destination).as_posix()
            if "--include" in args and rel != args[args.index("--include") + 1].lstrip("/"):
                continue
            content = path.read_bytes()
            objects.append(
                {
                    "Path": rel,
                    "Size": len(content),
                    "IsDir": False,
                    "Hashes": {
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "sha1": hashlib.sha1(content).hexdigest(),
                    },
                }
            )
        result = objects[0] if "--stat" in args else objects
        return subprocess.CompletedProcess(args, 0, json.dumps(result), "")

    mock = Mock(side_effect=invoke)
    monkeypatch.setattr(offsite, "rclone", mock)
    return mock


@pytest.fixture
def verified_payload(tmp_path, fake_rclone):
    build(tmp_path, [r for r in ROWS if r[0] != "data/raw/nosum"])
    assert run(tmp_path, "--manifest") == 0
    assert run(tmp_path, "--upload", "--yes") == 0
    assert run(tmp_path, "--verify") == 0
    assert offsite.read_receipt(tmp_path)
    fake_rclone.reset_mock()
    return tmp_path


def test_the_payload_is_what_nothing_else_could_bring_back(tmp_path: Path, capsys) -> None:
    build(tmp_path, [r for r in ROWS if r[0] != "data/raw/nosum"])
    assert run(tmp_path, "--manifest") == 0
    out = capsys.readouterr().out
    rows = manifest_rows(tmp_path)
    assert sorted(r.entry for r in rows) == PAYLOAD
    assert {r.entry: r.why for r in rows} == {
        "data/raw/journal": "our own collector wrote it, nobody else holds it",
        "data/raw/priced": "unpriced corpus, off-site until somebody prices it",
        "data/raw/live": "a reproduce stage reads it, no refetch route",
        "data/raw/checksums.sha256": "kept for the record, no refetch route",
    }
    assert "a recipe rebuilds it" in out and "data/raw/regen" not in out.split("held local only")[0]


def test_the_two_usenet_corpora_are_excluded_by_name(tmp_path: Path) -> None:
    build(tmp_path)
    entries = {e.key: e for e in offsite.prune.read_table(tmp_path / "docs/registers/retention.md")}
    assert offsite.reason(entries["data/raw/usenet_bulk"]) is None
    assert "archive.org" in offsite.held_because(entries["data/raw/usenet_bulk"])
    assert offsite.REFETCHABLE == {"data/raw/usenet_bulk", "data/raw/usenet_new"}


def test_an_entry_with_no_checksum_record_is_refused(tmp_path: Path, capsys) -> None:
    build(tmp_path)
    assert run(tmp_path, "--manifest") == 1
    out = capsys.readouterr().out
    assert "REFUSED" in out and "data/raw/nosum" in out
    assert [r.entry for r in manifest_rows(tmp_path) if "nosum" in r.entry] == []


def test_upload_prints_the_commands_and_runs_nothing_without_yes(tmp_path: Path, capsys) -> None:
    build(tmp_path, [r for r in ROWS if r[0] != "data/raw/nosum"])
    remote = tmp_path / "remote"
    assert run(tmp_path, "--manifest") == 0
    capsys.readouterr()
    assert run(tmp_path, "--upload", "--remote", str(remote)) == 0
    out = capsys.readouterr().out
    assert "Nothing ran" in out and not remote.exists()
    lines = [line for line in out.splitlines() if line.startswith("rclone copy --checksum")]
    assert len(lines) == len(PAYLOAD)
    assert all("--checksum" in line for line in lines)
    assert any(line.endswith(f"{remote}/data/raw/journal") for line in lines)  # a tree
    assert any(line.endswith(f"{remote}/data/raw") for line in lines)  # the loose file
    # Nothing here may remove a remote object.
    assert not any(word in out for word in ("--delete", "rclone sync", "rclone move", "purge"))


def test_verify_needs_a_manifest_first(tmp_path: Path, capsys) -> None:
    build(tmp_path)
    assert run(tmp_path, "--verify") == 2
    assert "run --manifest first" in capsys.readouterr().err


def test_verify_a_local_remote_reports_matched_missing_and_changed(tmp_path: Path, capsys) -> None:
    build(tmp_path, [r for r in ROWS if r[0] != "data/raw/nosum"])
    remote = tmp_path / "remote"
    assert run(tmp_path, "--manifest") == 0
    assert run(tmp_path, "--upload", "--yes", "--remote", str(remote)) == 0
    capsys.readouterr()

    assert run(tmp_path, "--verify", "--remote", str(remote)) == 0
    out = capsys.readouterr().out
    assert f"verified off-site, safe for the deletion ticket: {len(PAYLOAD)} of" in out
    assert all(entry in out for entry in PAYLOAD)
    # The manifests stay local: excluded from the copy, so they are not extras either.
    assert not (remote / "data/raw/journal/SHA256SUMS").exists()
    assert "extra" in out and " NO HASH" not in out

    (remote / "data/raw/journal/queries.jsonl").unlink()
    (remote / "data/raw/live/pages.warc").write_text("tampered\n", encoding="utf-8")
    assert run(tmp_path, "--verify", "--remote", str(remote)) == 1
    out = capsys.readouterr().out
    assert "DIFFERENT" in out and "NOT verified, do not delete" in out
    assert "data/raw/journal" in out.split("NOT verified")[1]


def test_verify_reads_metadata_only_and_never_asks_for_bytes(
    tmp_path: Path, capsys, fake_rclone
) -> None:
    build(tmp_path, [r for r in ROWS if r[0] != "data/raw/nosum"])
    remote = tmp_path / "remote"
    assert run(tmp_path, "--manifest") == 0
    assert run(tmp_path, "--upload", "--yes", "--remote", str(remote)) == 0
    fake_rclone.reset_mock()
    assert run(tmp_path, "--verify", "--remote", str(remote)) == 0
    capsys.readouterr()
    calls = [call.args[0] for call in fake_rclone.call_args_list]
    assert calls and all(args[0] == "lsjson" and "--hash" in args for args in calls)


def test_a_stale_file_count_is_flagged_rather_than_passed(tmp_path: Path, capsys) -> None:
    build(tmp_path, [r for r in ROWS if r[0] != "data/raw/nosum"])
    remote = tmp_path / "remote"
    assert run(tmp_path, "--manifest") == 0
    assert run(tmp_path, "--upload", "--yes", "--remote", str(remote)) == 0
    capsys.readouterr()
    new = tmp_path / "data/raw/journal/2002/later.jsonl"
    new.parent.mkdir(parents=True, exist_ok=True)
    new.write_text("nine\n", encoding="utf-8")
    sums = tmp_path / "data/raw/journal/SHA256SUMS"
    digest = hashlib.sha256(b"nine\n").hexdigest()
    sums.write_text(sums.read_text() + f"{digest}  ./2002/later.jsonl\n", encoding="utf-8")

    assert run(tmp_path, "--upload", "--yes", "--remote", str(remote)) == 0
    row = next(r for r in manifest_rows(tmp_path) if r.entry == "data/raw/journal")
    check = offsite.check_entry(row, tmp_path, str(remote))
    assert len(check.matched) == 3 and not (check.missing or check.differ or check.nohash)
    assert not check.verified
    assert run(tmp_path, "--verify", "--remote", str(remote)) == 1
    out = capsys.readouterr().out
    assert "the manifest beside the data names 3 files, the row says 2" in out
    assert "data/raw/journal" in out.split("NOT verified")[1]


def test_a_second_upload_transfers_nothing(tmp_path: Path, capsys) -> None:
    build(tmp_path, [r for r in ROWS if r[0] != "data/raw/nosum"])
    remote = tmp_path / "remote"
    assert run(tmp_path, "--manifest") == 0
    assert run(tmp_path, "--upload", "--yes", "--remote", str(remote)) == 0
    capsys.readouterr()
    assert run(tmp_path, "--upload", "--yes", "--remote", str(remote)) == 0
    assert "Every entry copied" in capsys.readouterr().out
    logs = sorted((tmp_path / offsite.LOGS).glob("offsite-data_raw_journal-*.log"))
    text = "".join(p.read_text(encoding="utf-8") for p in logs)
    assert "Copied" in text  # the first run
    assert "There was nothing to transfer" in text  # the second found the bytes already there


def test_the_table_keeps_regenerable_and_refetchable_bytes_local(tmp_path) -> None:
    table = build(tmp_path, [r for r in ROWS if r[0] != "data/raw/nosum"])
    entries = offsite.prune.read_table(table)
    rows, refused, empty = offsite.payload(entries)
    assert rows and not refused
    picked = {r.entry for r in rows}
    assert picked.isdisjoint(offsite.REFETCHABLE)
    assert not any(r.cls == "regenerable" for r in rows)
    assert all(r.digest not in ("none", "") for r in rows)
    assert all("private/" not in r.entry for r in rows)
    assert not picked.intersection(empty)


@pytest.mark.parametrize("files,note", [(0, ""), (1, ""), (3, ""), (2, "remote failed")])
def test_check_rejects_notes_and_count_mismatches(files, note):
    row = offsite.Row("data/raw/journal", "keep_journal", 8, files, "d1", "own journal")
    assert not offsite.Check(row, matched=["a", "b"], note=note).verified


@pytest.mark.parametrize("field,delta", [("files", -1), ("files", 1), ("size", -1), ("size", 1)])
def test_stale_counts_revoke_receipts_despite_matching_remote_hashes(
    verified_payload, field, delta
):
    root = verified_payload
    rows = manifest_rows(root)
    row = next(r for r in rows if r.entry == "data/raw/journal")
    stale = replace(row, **{field: getattr(row, field) + delta})
    (root / offsite.MANIFEST).write_text(offsite.render([stale if r == row else r for r in rows]))
    check = offsite.check_entry(stale, root, offsite.REMOTE)
    assert len(check.matched) == row.files and not (check.missing or check.differ)
    assert run(root, "--verify") == 1
    assert "data/raw/journal/queries.jsonl" not in offsite.read_receipt(root)


def test_undeclared_local_file_prevents_pinning(verified_payload):
    root = verified_payload
    (root / "data/raw/journal/undeclared.jsonl").write_text("unlisted\n")
    assert run(root, "--verify") == 1
    assert not any(key.startswith("data/raw/journal/") for key in offsite.read_receipt(root))


@pytest.mark.parametrize("rel", ["data/raw/journal/queries.jsonl", "data/raw/priced/corpus.zip"])
def test_same_size_change_with_reset_mtime_revokes_receipt(verified_payload, rel):
    root = verified_payload
    path = root / rel
    before = path.stat()
    path.write_bytes(b"x" * before.st_size)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = path.stat()
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    with pytest.raises(ValueError):
        offsite.deletion_proof(root, path)
    assert run(root, "--verify") == 1
    assert rel not in offsite.read_receipt(root)


@pytest.mark.parametrize("fault", ["missing", "hashless", "different", "failed", "duplicate"])
def test_remote_failure_revokes_old_receipt(verified_payload, fake_rclone, fault):
    root = verified_payload
    row = next(r for r in manifest_rows(root) if r.entry == "data/raw/journal")
    listing, note = offsite.remote_listing(row, root, offsite.REMOTE)
    assert not note
    objects = list(listing.values())
    if fault == "missing":
        objects.pop()
    elif fault == "hashless":
        objects[0]["Hashes"] = {}
    elif fault == "different":
        objects[0]["Hashes"]["sha256"] = "0" * 64
    elif fault == "duplicate":
        objects.append(objects[0])
    fake_rclone.side_effect = None
    fake_rclone.return_value = subprocess.CompletedProcess(
        [], 1 if fault == "failed" else 0, json.dumps(objects), "remote failed"
    )
    assert run(root, "--verify") == 1
    assert not offsite.read_receipt(root)
    with pytest.raises(ValueError):
        offsite.deletion_proof(root, root / "data/raw/journal/queries.jsonl")


@pytest.mark.parametrize("error", [KeyboardInterrupt, OSError, subprocess.SubprocessError])
def test_interrupted_or_failed_verify_revokes_old_receipt(verified_payload, fake_rclone, error):
    root = verified_payload
    fake_rclone.side_effect = error("verification interrupted")
    if error is KeyboardInterrupt:
        with pytest.raises(KeyboardInterrupt):
            run(root, "--verify")
    else:
        assert run(root, "--verify") == 1
    assert not offsite.read_receipt(root)
    fake_rclone.reset_mock()
    with pytest.raises(ValueError):
        offsite.deletion_proof(root, root / "data/raw/journal/queries.jsonl")
    fake_rclone.assert_not_called()


def test_interruption_after_one_match_publishes_no_partial_receipt(verified_payload, fake_rclone):
    root = verified_payload
    invoke = fake_rclone.side_effect

    def interrupt(args, check=True):
        if fake_rclone.call_count == 2:
            raise KeyboardInterrupt
        return invoke(args, check=check)

    fake_rclone.side_effect = interrupt
    with pytest.raises(KeyboardInterrupt):
        run(root, "--verify")
    assert fake_rclone.call_count == 2
    assert not offsite.read_receipt(root)


@pytest.mark.parametrize("missing", [False, True])
def test_manifest_failure_revokes_old_receipt(verified_payload, fake_rclone, missing):
    root = verified_payload
    manifest = root / offsite.MANIFEST
    if missing:
        manifest.unlink()
        assert run(root, "--verify") == 2
    else:
        manifest.write_text("invalid row\n")
        with pytest.raises(ValueError):
            run(root, "--verify")
    assert not offsite.read_receipt(root)
    fake_rclone.assert_not_called()


@pytest.mark.parametrize("fault", ["stale", "future", "wrong-root", "wrong-remote", "missing"])
def test_invalid_receipt_cannot_prove_deletion(verified_payload, fake_rclone, monkeypatch, fault):
    root = verified_payload
    receipt = root / offsite.RECEIPT
    saved = json.loads(receipt.read_text())
    now = saved["verified_at"]
    monkeypatch.setattr(offsite.time, "time", lambda: now)
    if fault == "stale":
        saved["verified_at"] = now - offsite.MAX_AGE - 1
    elif fault == "future":
        saved["verified_at"] = now + 1
    elif fault == "wrong-root":
        saved["root"] = str(root / "another-root")
    elif fault == "wrong-remote":
        saved["remote"] = str(root / "remote")
    if fault == "missing":
        receipt.unlink()
    else:
        receipt.write_text(json.dumps(saved))
    with pytest.raises(ValueError):
        offsite.deletion_proof(root, root / "data/raw/journal/queries.jsonl")
    fake_rclone.assert_not_called()


@pytest.mark.parametrize(
    "rel,kind",
    [("data/raw/journal/queries.jsonl", "sha256"), ("data/raw/priced/corpus.zip", "sha1")],
)
def test_receipt_pins_current_hash_and_live_exact_remote_object(
    verified_payload, fake_rclone, rel, kind
):
    root = verified_payload
    path = root / rel
    signature = offsite.signature(root, path)
    saved = json.loads((root / offsite.RECEIPT).read_text())
    assert saved["root"] == str(root.resolve()) and saved["remote"] == offsite.REMOTE
    assert 0 <= offsite.time.time() - saved["verified_at"] <= offsite.MAX_AGE
    assert saved["files"][rel] == {
        "stat": signature,
        "kind": kind,
        "digest": hashlib.new(kind, path.read_bytes()).hexdigest(),
    }
    assert offsite.deletion_proof(root, path) == signature
    fake_rclone.assert_called_once_with(
        ["lsjson", "--stat", "--hash", "--hash-type", kind, f"{offsite.REMOTE}/{rel}"],
        check=False,
    )


@pytest.mark.parametrize("fault", ["missing", "hashless", "changed", "size", "directory", "failed"])
def test_fresh_receipt_still_requires_live_remote_match(verified_payload, fake_rclone, fault):
    root = verified_payload
    path = root / "data/raw/journal/queries.jsonl"
    obj = {
        "Size": path.stat().st_size,
        "Hashes": {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
    }
    if fault == "missing":
        obj = {}
    elif fault == "hashless":
        obj["Hashes"] = {}
    elif fault == "changed":
        obj["Hashes"]["sha256"] = "0" * 64
    elif fault == "size":
        obj["Size"] += 1
    elif fault == "directory":
        obj["IsDir"] = True
    fake_rclone.side_effect = None
    fake_rclone.return_value = subprocess.CompletedProcess(
        [], 1 if fault == "failed" else 0, json.dumps(obj), "remote failed"
    )
    with pytest.raises(ValueError):
        offsite.deletion_proof(root, path)
    fake_rclone.assert_called_once()
