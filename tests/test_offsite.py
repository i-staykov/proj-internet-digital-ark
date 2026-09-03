"""offsite.py on a fixture tree: the payload rule, the refusal, and verify on a local remote.

Loaded by path, like the other script tests: `scripts/` is not a package. `rclone` takes a
plain path as a remote, so the upload and verify modes are exercised for real against a
directory under tmp_path.
"""

import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("offsite", REPO / "scripts/round/offsite.py")
offsite = importlib.util.module_from_spec(_SPEC)
# Registered before exec: the dataclasses read their own module back for its annotations.
sys.modules["offsite"] = offsite
_SPEC.loader.exec_module(offsite)

needs_rclone = pytest.mark.skipif(shutil.which("rclone") is None, reason="rclone not installed")

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
    table = root / "docs/retention.md"
    table.parent.mkdir(parents=True, exist_ok=True)
    table.write_text(HEAD + body, encoding="utf-8")
    return table


def run(root: Path, *args: str) -> int:
    return offsite.main(["--root", str(root), *args])


def manifest_rows(root: Path) -> list[offsite.Row]:
    return offsite.read_manifest(root / offsite.MANIFEST)


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
    entries = {e.key: e for e in offsite.prune.read_table(tmp_path / "docs/retention.md")}
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


@needs_rclone
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


@needs_rclone
def test_verify_reads_metadata_only_and_never_asks_for_bytes(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    build(tmp_path, [r for r in ROWS if r[0] != "data/raw/nosum"])
    remote = tmp_path / "remote"
    assert run(tmp_path, "--manifest") == 0
    assert run(tmp_path, "--upload", "--yes", "--remote", str(remote)) == 0
    calls: list[list[str]] = []
    real = offsite.rclone

    def spy(args, check=True):
        calls.append(args)
        return real(args, check)

    monkeypatch.setattr(offsite, "rclone", spy)
    assert run(tmp_path, "--verify", "--remote", str(remote)) == 0
    capsys.readouterr()
    assert calls and all(args[0] == "lsjson" and "--hash" in args for args in calls)


@needs_rclone
def test_a_stale_file_count_is_flagged_rather_than_passed(tmp_path: Path, capsys) -> None:
    build(tmp_path, [r for r in ROWS if r[0] != "data/raw/nosum"])
    remote = tmp_path / "remote"
    assert run(tmp_path, "--manifest") == 0
    assert run(tmp_path, "--upload", "--yes", "--remote", str(remote)) == 0
    capsys.readouterr()
    # A collector wrote one more file and verify_raw.py hashed it, but nobody repriced.
    new = tmp_path / "data/raw/journal/2002/later.jsonl"
    new.parent.mkdir(parents=True, exist_ok=True)
    new.write_text("nine\n", encoding="utf-8")
    sums = tmp_path / "data/raw/journal/SHA256SUMS"
    digest = hashlib.sha256(b"nine\n").hexdigest()
    sums.write_text(sums.read_text() + f"{digest}  ./2002/later.jsonl\n", encoding="utf-8")

    assert run(tmp_path, "--verify", "--remote", str(remote)) == 1
    out = capsys.readouterr().out
    assert "the manifest beside the data names 3 files, the row says 2" in out
    assert "data/raw/journal" in out.split("NOT verified")[1]


@needs_rclone
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


def test_the_real_table_keeps_regenerable_and_refetchable_bytes_local() -> None:
    entries = offsite.prune.read_table(REPO / "docs/retention.md")
    rows, refused, empty = offsite.payload(entries)
    assert rows and not refused
    picked = {r.entry for r in rows}
    assert picked.isdisjoint(offsite.REFETCHABLE)
    assert not any(r.cls == "regenerable" for r in rows)
    assert all(r.digest not in ("none", "") for r in rows)
    assert all("private/" not in r.entry for r in rows)
    assert not picked.intersection(empty)
