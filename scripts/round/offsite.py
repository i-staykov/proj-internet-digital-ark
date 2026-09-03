"""Copy off-site what nothing else could bring back, and check it without downloading.

The payload is not everything on disk. It is the entries of `docs/retention.md` that
are neither regenerable by a recipe nor refetchable from somebody else:

  * `keep_journal`, our own collectors' output, which nobody else holds;
  * `reference` that arrived by mail as a reviewer release, the archived releases
    of `data/archive/` among them, or whose refetch cell names nobody, which is
    every frozen `submissions/phase-*`;
  * `live_input` whose refetch cell is `unknown`, so a `just reproduce` stage reads
    bytes we could not fetch twice;
  * `keep_until_priced`, held until somebody prices it, EXCEPT `usenet_bulk` and
    `usenet_new`: archive.org serves those two again and their sha1 per zip is
    already recorded in `data/raw/usenet_catalog.json`.

Everything else stays local only: a recipe rebuilds it, or a URL in its row fetches
it. `private/` has no row and so can never appear (C-62).

    uv run python scripts/round/offsite.py --manifest        # price the payload
    uv run python scripts/round/offsite.py --upload          # print the commands
    uv run python scripts/round/offsite.py --upload --yes    # run them
    uv run python scripts/round/offsite.py --verify          # remote against manifest

`--manifest` writes `data/offsite-manifest.tsv` (untracked, like the `SHA256SUMS`
files it reads) and refuses any entry whose row carries no checksum record: an
uploaded copy nobody can check is not a backup.

`--verify` downloads nothing. Google Drive returns md5, sha1 AND sha256 per object,
measured 2026-09-03 with `rclone lsjson --hash` over a .jsonl, a .gz and a .zip
uploaded for the purpose: all three hashes came back populated and the sha256
matched the local file, so each file is compared with the hash its own local
manifest holds (sha256, or IA's sha1 for the Usenet zips in `SHA1SUMS`).

Deleting the local bytes afterwards is a separate ticket. This script never deletes
anything, locally or on the remote.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REMOTE = "gdrive:ark-offsite"
MANIFEST = "data/offsite-manifest.tsv"
LOGS = "data/logs"
COLUMNS = ("entry", "class", "bytes", "files", "digest", "reason")

# The two corpora archive.org can serve again, by name, so the rule that holds every
# other `keep_until_priced` entry does not drag 110 GB of refetchable zips off-site.
REFETCHABLE = {"data/raw/usenet_bulk", "data/raw/usenet_new"}

# Written beside the data by verify_raw.py, so not part of any entry's own manifest.
SIDECARS = ("SHA256SUMS", "SHA1SUMS", "SHA256SUMS.stat")


def _load(name: str):
    """A sibling script as a module. `scripts/` is not a package."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # the dataclasses read their own module back
    spec.loader.exec_module(mod)
    return mod


prune = _load("prune")
verify_raw = _load("verify_raw")


def reason(entry) -> str | None:
    """Why this entry must go off-site, or None when something else can bring it back."""
    if Path(entry.key).name == ".DS_Store":
        return None
    if entry.cls == "keep_journal":
        return "our own collector wrote it, nobody else holds it"
    if entry.cls == "reference":
        if entry.refetch == "reviewer_release":
            return "reviewer release, arrived by mail"
        if entry.route == "none":
            return "kept for the record, no refetch route"
    if entry.cls == "live_input" and entry.route == "none":
        return "a reproduce stage reads it, no refetch route"
    if entry.cls == "keep_until_priced" and entry.key not in REFETCHABLE:
        return "unpriced corpus, off-site until somebody prices it"
    return None


def held_because(entry) -> str:
    """Why an entry stays local only. Read only for the summary under the payload."""
    if Path(entry.key).name == ".DS_Store":
        return "Finder metadata, not data"
    if entry.key in REFETCHABLE:
        return "archive.org refetch, sha1 per zip in data/raw/usenet_catalog.json"
    if entry.cls == "regenerable":
        return "a recipe rebuilds it"
    return f"{entry.cls}, refetch recorded"


@dataclass(frozen=True)
class Row:
    """One manifest line: an entry that must be copied, and what it should hold."""

    entry: str
    cls: str
    size: int
    files: int
    digest: str
    why: str

    def local(self, root: Path) -> Path:
        return root / self.entry

    def is_file(self, root: Path) -> bool:
        """A loose file entry, like `data/raw/checksums.sha256`, rather than a tree."""
        local = self.local(root)
        return local.is_file() if local.exists() else bool(Path(self.entry).suffix)

    def dest(self, root: Path, remote: str) -> str:
        """Where rclone puts it: a tree keeps its path, a loose file lands in its parent."""
        where = Path(self.entry).parent if self.is_file(root) else Path(self.entry)
        return f"{remote.rstrip('/')}/{where.as_posix()}"


def payload(entries: list) -> tuple[list[Row], list[tuple[str, str]], list[str]]:
    """Rows to copy, entries refused for want of a checksum, and empty entries skipped."""
    rows, refused, empty = [], [], []
    for e in entries:
        why = reason(e)
        if why is None:
            continue
        if not (e.size or 0) and not (e.files or 0):
            empty.append(e.key)
            continue
        if not e.checksummed:
            refused.append((e.key, why))
            continue
        rows.append(Row(e.key, e.cls, e.size or 0, e.files or 0, e.digest, why))
    return rows, refused, empty


def render(rows: list[Row]) -> str:
    out = [
        "# Off-site payload: the entries of docs/retention.md that are neither",
        "# regenerable nor refetchable. Written by scripts/round/offsite.py --manifest.",
        "\t".join(COLUMNS),
    ]
    for r in rows:
        out.append("\t".join((r.entry, r.cls, str(r.size), str(r.files), r.digest, r.why)))
    return "\n".join(out) + "\n"


def read_manifest(path: Path) -> list[Row]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        cells = line.split("\t")
        if cells == list(COLUMNS):
            continue
        if len(cells) != len(COLUMNS):
            raise ValueError(f"{path}: expected {len(COLUMNS)} columns: {line}")
        entry, cls, size, files, digest, why = cells
        rows.append(Row(entry, cls, int(size), int(files), digest, why))
    if not rows:
        raise ValueError(f"{path}: no rows")
    return rows


def expected_files(root: Path, entry: str) -> dict[str, tuple[str, str]]:
    """`rel -> (hash kind, hex)` for the files one entry owns, from the manifests on disk.

    The kind is what verify_raw.py recorded: `sha256`, or `sha1` where IA's own sha1
    for a Usenet zip stood in for a rehash.
    """
    local = root / entry
    manifest = verify_raw.Manifest.read(verify_raw.home(root, entry))
    out: dict[str, tuple[str, str]] = {}
    for kind, table in (("sha256", manifest.sums), ("sha1", manifest.sha1s)):
        for rel, hexdigest in table.items():
            inside = verify_raw.within(local, manifest.where, rel)
            if inside is not None:
                out[inside] = (kind, hexdigest)
    return out


def rclone(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["rclone", *args], capture_output=True, text=True, check=check)


def copy_command(row: Row, root: Path, remote: str, log: Path) -> list[str]:
    """The exact `rclone copy` for one entry. Resumable, and it never deletes."""
    cmd = ["rclone", "copy", "--checksum", "--transfers", "4"]
    if not row.is_file(root):
        # verify_raw.py writes these beside the data and no entry's manifest lists
        # itself, so leaving them behind keeps the remote exactly the manifest.
        cmd += [flag for name in SIDECARS for flag in ("--exclude", f"/{name}")]
    cmd += ["--log-level", "INFO", "--log-file", str(log)]
    return cmd + [str(row.local(root)), row.dest(root, remote)]


def upload(rows: list[Row], root: Path, remote: str, run: bool) -> list[str]:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    logs = root / LOGS
    out = [
        f"{len(rows)} entries, {sum(r.size for r in rows):,} B "
        f"({prune.human(sum(r.size for r in rows))}) to {remote}.",
        "A copy adds and overwrites only: a second run transfers what changed,",
        "and no command below can delete a remote object.",
        "",
    ]
    if run:
        logs.mkdir(parents=True, exist_ok=True)
    failed = []
    for r in rows:
        log = logs / f"offsite-{r.entry.replace('/', '_')}-{stamp}.log"
        cmd = copy_command(r, root, remote, log)
        out.append(" ".join(cmd))
        if not run:
            continue
        if not r.local(root).exists():
            out.append(f"  SKIPPED: {r.local(root)} is not on this disk")
            failed.append(r.entry)
            continue
        done = rclone(cmd[1:], check=False)
        tail = (done.stderr or done.stdout).strip().splitlines()[-1:] or ["ok"]
        out.append(f"  exit {done.returncode}: {tail[0][:120]}")
        if done.returncode:
            failed.append(r.entry)
    if not run:
        out += ["", "Nothing ran: pass --yes to run these commands."]
    elif failed:
        out += ["", f"{len(failed)} entries did not finish: {', '.join(failed)}"]
    else:
        out += ["", "Every entry copied. Run --verify before deleting anything."]
    return out


@dataclass
class Check:
    """What the remote holds for one entry, against what the local manifest says."""

    row: Row
    matched: list[str] = field(default_factory=list)
    differ: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    nohash: list[str] = field(default_factory=list)
    remote_bytes: int = 0
    note: str = ""

    @property
    def verified(self) -> bool:
        """Every file the manifest names is on the remote with the hash it should have."""
        return bool(self.matched) and not (self.differ or self.missing or self.nohash)


def remote_listing(row: Row, root: Path, remote: str) -> tuple[dict[str, dict], str]:
    """`rel -> lsjson object` for one entry, without downloading a byte.

    Drive answers with the hashes it holds, so nothing is read back. A loose file is
    filtered by name: its destination is a parent directory shared with other entries.
    """
    args = ["lsjson", "--hash", "--hash-type", "sha256", "--hash-type", "sha1", "--files-only"]
    wanted = Path(row.entry).name if row.is_file(root) else None
    args += ["--include", f"/{wanted}"] if wanted else ["--recursive"]
    done = rclone([*args, row.dest(root, remote)], check=False)
    if done.returncode:
        last = (done.stderr or "").strip().splitlines()[-1:] or ["rclone failed"]
        if "not found" in (done.stderr or "").lower():
            return {}, "nothing at that remote path"
        return {}, last[0][:120]
    return {obj["Path"]: obj for obj in json.loads(done.stdout or "[]")}, ""


def check_entry(row: Row, root: Path, remote: str) -> Check:
    res = Check(row)
    expect = expected_files(root, row.entry)
    listing, res.note = remote_listing(row, root, remote)
    notes = [res.note]
    if not expect:
        notes.append("no local checksum lines to compare")
    elif len(expect) != row.files:
        # The entry grew or shrank since the manifest was priced, so the row is stale.
        notes.append(
            f"the manifest beside the data names {len(expect)} files, the row says "
            f"{row.files}: rerun `just verify raw` and --manifest"
        )
    res.note = "; ".join(n for n in notes if n)
    for rel, (kind, hexdigest) in sorted(expect.items()):
        obj = listing.get(rel)
        if obj is None:
            res.missing.append(rel)
            continue
        res.remote_bytes += int(obj.get("Size") or 0)
        got = (obj.get("Hashes") or {}).get(kind)
        if not got:
            res.nohash.append(rel)
        elif got.lower() == hexdigest.lower():
            res.matched.append(rel)
        else:
            res.differ.append(rel)
    res.extra = sorted(set(listing) - set(expect))
    return res


def verify_report(checks: list[Check], remote: str) -> list[str]:
    head = (
        f"{'entry':<40} {'files':>6} {'bytes':>9} {'on remote':>10} "
        f"{'matched':>8} {'missing':>8} {'extra':>6}"
    )
    plural = "entry" if len(checks) == 1 else "entries"
    out = [f"{remote}: {len(checks)} manifest {plural}, compared by hash only.", "", head]
    for c in checks:
        out.append(
            f"{c.row.entry:<40} {c.row.files:>6} {prune.human(c.row.size):>9} "
            f"{prune.human(c.remote_bytes):>10} "
            f"{len(c.matched):>8} {len(c.missing):>8} {len(c.extra):>6}"
        )
        for label, names in (("DIFFERENT", c.differ), ("NO HASH", c.nohash)):
            if names:
                out.append(f"    {label}: {len(names)}, first {', '.join(names[:3])}")
        if c.note:
            out.append(f"    {c.note}")
    good = [c for c in checks if c.verified]
    bad = [c for c in checks if not c.verified]
    size = sum(c.row.size for c in good)
    out += [
        "",
        f"verified off-site, safe for the deletion ticket: {len(good)} of {len(checks)} entries, "
        f"{size:,} B ({prune.human(size)}): {', '.join(c.row.entry for c in good) or 'none'}",
    ]
    if bad:
        out.append(f"NOT verified, do not delete: {', '.join(c.row.entry for c in bad)}")
    return out


def manifest_report(
    rows: list[Row],
    refused: list[tuple[str, str]],
    empty: list[str],
    held: list[tuple[str, str, int]],
    path: Path,
) -> list[str]:
    size = sum(r.size for r in rows)
    out = [
        f"{path}: {len(rows)} entries, {size:,} B ({prune.human(size)}) to copy off-site.",
        "",
        f"  {'entry':<40} {'bytes':>9} {'files':>7}  why it must be copied",
    ]
    for r in rows:
        out.append(f"  {r.entry:<40} {prune.human(r.size):>9} {r.files:>7}  {r.why}")
    kept: dict[str, list[int]] = {}
    for _, why, hsize in held:
        tally = kept.setdefault(why, [0, 0])
        tally[0] += 1
        tally[1] += hsize
    total_held = sum(t[1] for t in kept.values())
    out += ["", f"held local only: {len(held)} entries, {prune.human(total_held)}"]
    for why, (count, hsize) in sorted(kept.items(), key=lambda kv: -kv[1][1]):
        out.append(
            f"  {why:<62} {count:>3} {'entry' if count == 1 else 'entries'} {prune.human(hsize):>9}"
        )
    if empty:
        out.append(f"empty, nothing to copy: {', '.join(empty)}")
    if refused:
        out.append("")
        out.append("REFUSED, no checksum record, so a copy could not be checked:")
        out += [f"  {key}  ({why})" for key, why in refused]
        out.append("Run `just verify raw` for these entries, then rerun --manifest.")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--manifest", action="store_true", help="compute the payload and write it")
    mode.add_argument("--upload", action="store_true", help="print the rclone commands")
    mode.add_argument(
        "--verify", action="store_true", help="remote against the manifest, no download"
    )
    ap.add_argument("--yes", action="store_true", help="with --upload, actually run them")
    ap.add_argument("--remote", default=REMOTE, help=f"rclone destination (default {REMOTE})")
    ap.add_argument("--root", type=Path, default=REPO, help="repository root the data sits under")
    ap.add_argument(
        "--table", type=Path, default=None, help="retention table (default under --root)"
    )
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    root: Path = args.root
    manifest = root / MANIFEST

    if args.manifest:
        table = args.table or root / "docs/retention.md"
        entries = prune.read_table(table)
        rows, refused, empty = payload(entries)
        held = [(e.key, held_because(e), e.size or 0) for e in entries if reason(e) is None]
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(render(rows), encoding="utf-8")
        print("\n".join(manifest_report(rows, refused, empty, held, manifest)))
        return 1 if refused else 0

    if not manifest.is_file():
        print(f"{manifest} is missing: run --manifest first.", file=sys.stderr)
        return 2
    rows = read_manifest(manifest)

    if args.upload:
        print("\n".join(upload(rows, root, args.remote, args.yes)))
        return 0

    checks = [check_entry(r, root, args.remote) for r in rows]
    print("\n".join(verify_report(checks, args.remote)))
    return 0 if all(c.verified for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
