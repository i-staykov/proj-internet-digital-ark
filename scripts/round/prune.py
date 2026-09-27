"""Report retention eligibility, or prune verified round duplicates with --round --write.

Reads the tracked `docs/registers/retention.md` and nothing else, so the page a human can read
is the single source of truth: the classification tables inside `verify_raw.py` are
not consulted here. An entry with no row is not in the table and so cannot appear.

An entry is deletable only when all three of these hold at once:

  1. its class is `regenerable` (a recipe rebuilds it) or `keep_until_priced` (nobody
     reads it yet, so only the bytes are at stake);
  2. `refetch` names somebody who could serve the bytes again: a URL, a recipe or the
     reviewer release. `own_journal` is our own collector's output and `unknown` is
     nobody, so neither is a route;
  3. `digest` and `record` say a checksum exists, so a refetch can be checked.

Everything else is listed under what it is missing, which makes the second half of the
output the to-do list for the off-site copy: an entry missing only a checksum needs one
before it can be copied and verified.

    uv run python scripts/round/prune.py
    uv run python scripts/round/prune.py --json
    uv run python scripts/round/prune.py --disk [--private [--owner-go]] [--write]

The retention report grants no deletion permission. Round cleanup is limited to
superseded store backups and CRC-matched reviewer zips. A backup BACKUP_HOLDS names stays;
any other is held until `data/baseline.json` lists a credited round dated after it,
because that round's Parquet and our journals rebuild the store, and it then needs a newer
quiescent store and a fresh `ark check`. A zip needs an unchanged local verification
receipt and a current matching remote hash.

**`--disk` deletes only what somebody serves again, each file behind its own proof.** It
lists, and with `--write` deletes:

  * superseded releases: their extracted trees, their zips and `data/archive/*.tar.zst`,
    never the current or a newer release nor the reviewer's documents, file by file
    behind a live Drive receipt, a tree first CRC-checked against its zip when both are here;
  * spent raw: the downloaded archives of the entries in SPENT, file by file once
    archive.org serves it (a file marked private there, or one in a restricted item that
    refuses a ranged GET, stays) at the same size, and the sha1 of our own bytes, hashed
    at `--write`, equals archive.org's; `DELETED.tsv` beside them then records the file,
    its bytes, that sha1 and the URL;
  * `output/DomainDataCollectionTask_*` but the newest, once the newest's tarball is on
    Drive with the checksum git keeps;
  * with `--private`, everything in `private/` but PRIVATE_KEEP, which code reads. Nothing
    there has a copy anywhere, so `--private --write` deletes only with `--owner-go`, which
    no recipe passes: #188's last step passes it on the owner's go. Without it, it lists
    `private/` and deletes nothing at all.

It never touches `submissions/`, a `*_items/` directory, a `*.jsonl.gz`, a checksum
sidecar, or an entry the classification tables call `live_input`, `keep_journal` or
`keep_until_*`. Store backups are listed and never deleted here: their delete is for the
agents that own the store, and `ark.duckdb.pre-stage-a.bak` is held until #181's rebuild
restores the rows only it holds. The dry run makes no network call.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.request
import zipfile
import zlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RETENTION = REPO / "docs/registers/retention.md"

# Classes whose bytes can come back. The others are held whatever else holds:
# `live_input` is read by `just reproduce sources`, `keep_journal` and `keep_authority` are
# ours alone, `reference` is kept for the record.
RECLAIMABLE = ("regenerable", "keep_until_priced")

# `refetch` values naming nobody who could serve the bytes again.
NO_ROUTE = frozenset({"unknown", "own_journal", "none", "?", ""})

# Flags a caller might reach for. None of them exist, and saying why beats a usage error.
DELETE_FLAGS = frozenset({"--delete", "--apply", "--force", "--rm", "--execute", "--yes", "-f"})


@dataclass(frozen=True)
class Entry:
    key: str
    cls: str
    files: int | None
    size: int | None
    digest: str
    refetch: str
    record: str

    @property
    def route(self) -> str:
        """Kind of refetch route, or `none`."""
        if self.refetch in NO_ROUTE:
            return "none"
        if self.refetch.startswith(("http://", "https://", "ftp://")):
            return "url"
        if self.refetch == "reviewer_release":
            return "reviewer_release"
        return "recipe"

    @property
    def checksummed(self) -> bool:
        return self.digest not in ("none", "?", "") and self.record not in ("none", "?", "")

    @property
    def missing(self) -> list[str]:
        """Why this entry is not deletable, in the order the three conditions are stated."""
        out = []
        if self.cls not in RECLAIMABLE:
            out.append(f"class {self.cls} is held")
        if self.route == "none":
            out.append("no refetch route")
        if not self.checksummed:
            out.append("no checksum record")
        return out

    @property
    def deletable(self) -> bool:
        return not self.missing

    @property
    def group(self) -> str:
        if self.deletable:
            return f"{self.cls}, {self.route} route, checksum recorded"
        return " + ".join(self.missing)


@dataclass
class Group:
    label: str
    deletable: bool
    entries: list[Entry]

    @property
    def size(self) -> int:
        return sum(e.size or 0 for e in self.entries)


def _cells(line: str) -> list[str]:
    return [c.strip().strip("`") for c in line.strip().strip("|").split("|")]


def _number(cell: str) -> int | None:
    return None if not cell.isdigit() else int(cell)


def read_table(path: Path) -> list[Entry]:
    """The retention rows, in page order. A row is a line whose first cell is a path."""
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = _cells(line)
        if len(cells) != 7:
            raise ValueError(f"{path}: expected 7 cells, got {len(cells)}: {line}")
        key, cls, files, size, digest, refetch, record = cells
        entries.append(Entry(key, cls, _number(files), _number(size), digest, refetch, record))
    if not entries:
        raise ValueError(f"{path}: no rows")
    return entries


def group(entries: list[Entry]) -> list[Group]:
    """One group per distinct reason, deletable first, then largest first."""
    groups: dict[str, Group] = {}
    for e in entries:
        g = groups.setdefault(e.group, Group(e.group, e.deletable, []))
        g.entries.append(e)
    return sorted(groups.values(), key=lambda g: (not g.deletable, -g.size, g.label))


def human(size: int) -> str:
    for unit, step in (("GB", 10**9), ("MB", 10**6), ("kB", 10**3)):
        if size >= step:
            return f"{size / step:.1f} {unit}"
    return f"{size} B"


def sibling(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def remove_verified(root: Path, path: Path, *, write: bool = False) -> str:
    """Delete one regular file only after checking its recorded and live remote copy."""
    offsite = sibling("offsite")
    stamp = offsite.deletion_proof(root, path)
    if write:
        if offsite.signature(root, path) != stamp:
            raise ValueError(f"changed before deletion: {path.relative_to(root)}")
        path.unlink()
    return f"{'removed' if write else 'would remove'}: {path.relative_to(root)}"


def credited_after(root: Path, mtime_ns: int) -> bool:
    """Whether `data/baseline.json` lists a round with an awarded percent dated after the day
    (UTC) of `mtime_ns`. A round's date is a day, so a round the same day does not count."""
    rounds = json.loads((root / "data/baseline.json").read_text(encoding="utf-8"))["rounds"]
    made = datetime.fromtimestamp(mtime_ns / 1e9, UTC).date()
    return any(
        r.get("awarded_percent") and r.get("date") and date.fromisoformat(r["date"]) > made
        for r in rounds
    )


def round_cleanup(root: Path, *, write: bool = False) -> tuple[int, list[str]]:
    """Keep extracted releases and the current store; never select submissions or output."""
    root = root.resolve()
    offsite, releases = sibling("offsite"), sibling("releases")
    lines, held = [], False
    store = root / "data/ark.duckdb"
    for backup in sorted((root / "data").glob("ark.duckdb.pre-*.bak")):
        if backup.name in BACKUP_HOLDS:
            held = True
            lines.append(f"HELD {backup.relative_to(root)}: {BACKUP_HOLDS[backup.name]}")
            continue
        try:
            backup_stamp = offsite.signature(root, backup)
            if not credited_after(root, backup_stamp[3]):
                raise ValueError("no credited round in data/baseline.json is dated after it")
            before = offsite.signature(root, store)
            if (
                before[2] == 0
                or before[3] <= backup_stamp[3]
                or before[:2] == backup_stamp[:2]
                or store.with_suffix(".duckdb.wal").exists()
            ):
                raise ValueError("store is not a quiescent successor")
            if not write:
                lines.append(f"would check store and remove: {backup.relative_to(root)}")
                continue
            # `ark check` only reads, so the store must come out of it the very same file.
            done = subprocess.run(["uv", "run", "ark", "check"], cwd=root, check=False)
            if (
                done.returncode
                or offsite.signature(root, store) != before
                or store.with_suffix(".duckdb.wal").exists()
            ):
                raise ValueError("ark check failed or store replaced; backup retained")
            if offsite.signature(root, backup) != backup_stamp:
                raise ValueError("backup changed during the check")
            backup.unlink()
            lines.append(f"removed: {backup.relative_to(root)}")
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            held = True
            lines.append(f"HELD {backup.relative_to(root)}: {exc}")

    trees = releases.find_trees(root / "feedback", {})
    zips = releases.find_zips(root / "feedback")
    for archive in sorted({p for paths in zips.values() for p in paths}):
        try:
            archive_stamp = offsite.signature(root, archive)
            offsite.deletion_proof(root, archive)
            inventories = {}
            for marker in sorted(releases.zip_markers(archive)):
                if not trees.get(marker):
                    raise ValueError(f"no extracted tree for {marker}")
                tree = trees[marker][0]
                inventories[tree] = offsite.local_files(root, tree)
                counts, problems = releases.verify_tree(tree, archive, marker)
                if not counts["members"] or problems:
                    raise ValueError(f"CRC verification failed for {marker}: {problems[:3]}")
            if offsite.signature(root, archive) != archive_stamp or any(
                offsite.local_files(root, tree) != before for tree, before in inventories.items()
            ):
                raise ValueError("release changed during CRC verification")
            lines.append(remove_verified(root, archive, write=write))
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            RuntimeError,
            zipfile.BadZipFile,
            zlib.error,
            subprocess.SubprocessError,
        ) as exc:
            held = True
            lines.append(f"HELD {archive.relative_to(root)}: {exc}")
    if not lines:
        lines.append("round duplicates: nothing to prune")
    return (1 if held else 0), lines


# --- --disk -----------------------------------------------------------------------------

DELETED = "DELETED.tsv"
SIDECARS = frozenset({"SHA256SUMS", "SHA1SUMS", "SHA256SUMS.stat", DELETED})
HELD_CLASSES = ("live_input", "keep_journal", "keep_until_priced", "keep_until_decided")
# Read by code: the brief, the mail and the round's own drafts.
PRIVATE_KEEP = frozenset(
    {"personal-context.md", "mail", "emails", "email-draft.md", "email.template.md", "handoff.md"}
)
STAGES = "DomainDataCollectionTask_*_IvayloStaykov"
BACKUP_HOLDS = {
    "ark.duckdb.pre-stage-a.bak": "held until #181's rebuild restores the rows only it holds",
}
IA = "https://archive.org"
# The reviewer's own words, kept wherever they sit, even inside a superseded release tree.
DOCUMENTS = {".md", ".docx", ".doc", ".pdf", ".rtf", ".odt"}
# Files another issue still reads, each with the reason, held until that issue says so.
HOLDS = Path(__file__).with_name("disk_holds.tsv")
USER_AGENT = "ark-prune/1.0 (checks archive.org metadata before a delete)"


def _minus(suffix: str):
    """A rule for an entry whose item is each file's own name less `suffix`."""

    def rule(rel: str, name: str, catalog: dict) -> tuple[str, str] | None:
        return (name[: -len(suffix)], name) if "/" not in rel else None

    return rule


def _catalogued(rel: str, name: str, catalog: dict) -> tuple[str, str] | None:
    """A Usenet zip the IA catalog lists, in `usenet-<hierarchy>`; a subdirectory, as in
    usenet_hdr2, must be that hierarchy."""
    hit = catalog.get(name)
    if hit is None or (rel.count("/") == 1 and rel.split("/")[0] != hit[0]) or rel.count("/") > 1:
        return None
    return f"usenet-{hit[0]}", name


# Each spent entry: which of its files archive.org serves again, as (item, name there).
# Every rule was checked against one real file's name and size in archive.org's metadata.
# A file no rule matches is never selected: logs, derived lists, markers, `.meta` files.
SPENT = {
    "host_cdx": (
        re.compile(r"ia\d+\.hostcdx\.gz"),
        lambda rel, name, catalog: (f"host_cdx_{name.split('.')[0]}", name),
    ),
    "arxiv_src": (re.compile(r"arXiv_src_\d{4}_\d{3}\.tar"), _minus(".tar")),
    "dartmouth_arcs": (
        re.compile(r"DARTMOUTH-NBER-RESEARCH-2017-ARCS-[\d-]+\.cdx\.gz"),
        _minus(".cdx.gz"),
    ),
    "poland_cdx": (re.compile(r"pl-2001-EXTRACTION-[\d-]+-ARC_arc\.cdx\.gz"), _minus(".cdx.gz")),
    "usfedgov": (re.compile(r"USFEDGOV-EXTRACT-\d{4}\.cdx\.gz"), _minus(".cdx.gz")),
    # Saved under a plain name; archive.org keeps the parentheses.
    "netabuse": (
        re.compile(r"news\.admin\.net-abuse\.sightings\.3902507\.mbox\.7z"),
        lambda rel, name, catalog: (
            "FULL-USENET-BACKUP-2020-Oct-news.admin.net-abuse.sightings.3902507.mbox.7z",
            "news.admin.net-abuse.sightings.(3902507).mbox.7z",
        ),
    ),
    "usenet_bulk": (re.compile(r"[^/]+\.mbox\.zip"), _catalogued),
    "usenet_uk": (re.compile(r"[^/]+\.mbox\.zip"), _catalogued),
    "usenet_probe5": (re.compile(r"[^/]+\.mbox\.zip"), _catalogued),
    "usenet_hdr2": (re.compile(r"[^/]+\.mbox\.zip"), _catalogued),
}
# Listed so the list says why they stay: no per-file copy, or none catalogued yet.
UNPROVABLE = {
    "rtfm": "its files are members of one archive.org tar, which has no per-file copy",
    "usenet_new": "its zips are in no archive.org catalog yet",
}


@dataclass
class Candidate:
    selector: str
    path: Path
    size: int
    held: str = ""
    item: str = ""
    remote: str = ""
    digest: str = ""


def _catalog(root: Path) -> dict[str, tuple[str, str, int]]:
    """IA zip name -> (hierarchy, sha1, size), from the catalog verify_raw reads."""
    path = root / "data/raw/usenet_catalog.json"
    if not path.is_file():
        return {}
    out = {}
    for key, items in json.loads(path.read_text()).items():
        for it in items:
            out[it["name"]] = (key, it["sha1"], int(it["size"]))
    return out


def never(root: Path, path: Path) -> str:
    """Why `path` may never be deleted by --disk, or ""."""
    rel = path.relative_to(root)
    if rel.parts[0] == "submissions":
        return "submissions/ is never deleted"
    if any(part.endswith("_items") for part in rel.parts[:-1]):
        return "a *_items/ journal directory"
    if path.name.endswith(".jsonl.gz"):
        return "a journal"
    if path.name in SIDECARS:
        return "a checksum sidecar"
    if rel.parts[:2] == ("data", "raw") and len(rel.parts) > 2:
        cls = sibling("verify_raw").classify(f"data/raw/{rel.parts[2]}")
        if cls and cls[0] in HELD_CLASSES:
            return f"class {cls[0]}"
    return ""


def _files(folder: Path):
    if folder.is_file() and not folder.is_symlink():
        yield folder
        return
    for dirpath, dirnames, names in os.walk(folder):
        dirnames.sort()
        for name in sorted(names):
            path = Path(dirpath) / name
            if not path.is_symlink() and path.is_file():
                yield path


def _receipted(root: Path, path: Path, receipt: dict) -> str:
    """ "" when the local receipt pins this file as it is now, else what is missing."""
    offsite = sibling("offsite")
    pinned = receipt.get(path.relative_to(root).as_posix())
    if not pinned:
        return "no Drive receipt"
    try:
        if pinned.get("stat") != offsite.signature(root, path):
            return "changed since its Drive receipt"
    except ValueError as exc:
        return str(exc)
    return ""


def releases_selected(root: Path, receipt: dict) -> list[Candidate]:
    """Superseded release trees (a `merged*` directory with a year file), the release zips
    holding none but superseded markers, and the repacked `data/archive/*.tar.zst`. The
    reviewer's own documents are never listed, nor is the current release, matched by its
    resolved path, case-folded, or by its marker, nor a newer one. With no marker to go by,
    every release is held."""
    releases = sibling("releases")
    current = json.loads((root / "data/baseline.json").read_text(encoding="utf-8"))["current"]
    here = str((root / current["directory"]).resolve()).casefold()
    # The current release by either name baseline.json gives it: its marker and its folder.
    names = {str(n).casefold() for n in (current.get("marker"), Path(current["directory"]).name)}
    keys = []
    for name in names:
        try:
            keys.append(releases.marker_key(name))
        except ValueError:
            pass
    unknown = "" if keys else "data/baseline.json names no release marker, so none is superseded"

    def kept(found: str) -> bool:
        """The current release, or one newer than it that intake has not recorded yet."""
        if found.casefold() in names:
            return True
        try:
            return bool(keys) and releases.marker_key(found) >= min(keys)
        except ValueError:
            return False

    paths: list[Path] = []
    for found, trees in releases.find_trees(root / "feedback", {}).items():
        for tree in trees:
            if not kept(found) and str(tree.resolve()).casefold() != here:
                paths += [f for f in _files(tree) if f.suffix.lower() not in DOCUMENTS]
    markers_of: dict[Path, set[str]] = {}
    for found, zips in releases.find_zips(root / "feedback").items():
        for z in zips:
            markers_of.setdefault(z, set()).add(found.casefold())
    paths += sorted(z for z, markers in markers_of.items() if not any(map(kept, markers)))
    paths += sorted(
        a for a in (root / "data/archive").glob("*.tar.zst") if not kept(a.name.split(".")[0])
    )
    out = []
    for path in sorted(set(paths)):
        inside = f"{str(path.resolve()).casefold()}/".startswith(f"{here}/")
        if path.name == ".DS_Store" or path.is_symlink() or never(root, path) or inside:
            continue
        held = unknown or _receipted(root, path, receipt)
        out.append(Candidate("releases", path, path.stat().st_size, held))
    return out


def spent_selected(root: Path) -> tuple[list[Candidate], list[str]]:
    catalog = _catalog(root)
    out, notes = [], []
    for name, why in UNPROVABLE.items():
        folder = root / "data/raw" / name
        if folder.is_dir():
            size = sum(p.stat().st_size for p in _files(folder) if not never(root, p))
            notes.append(f"kept data/raw/{name}, {human(size)}: {why}")
    unnamed: dict[str, list[int]] = {}
    for entry, (pattern, rule) in SPENT.items():
        folder = root / "data/raw" / entry
        if not folder.is_dir():
            continue
        manifest = sibling("verify_raw").Manifest.read(folder)
        for path in _files(folder):
            rel = path.relative_to(folder).as_posix()
            if never(root, path) or not pattern.fullmatch(path.name):
                continue
            hit = rule(rel, path.name, catalog)
            if hit is None:
                tally = unnamed.setdefault(entry, [0, 0])
                tally[0] += 1
                tally[1] += path.stat().st_size
                continue
            st = path.stat()
            key = "./" + rel
            digest = (
                f"sha1:{manifest.sha1s[key]}"
                if key in manifest.sha1s
                else f"sha256:{manifest.sums[key]}"
                if key in manifest.sums
                else ""
            )
            held = ""
            listed = catalog.get(path.name) if rule is _catalogued else None
            if not digest:
                held = "no recorded digest"
            elif manifest.stats.get(key) != (st.st_size, st.st_mtime_ns):
                held = "changed since its digest was recorded"
            elif listed and listed[2] != st.st_size:
                held = f"{st.st_size:,} B here, {listed[2]:,} B in the catalog: a partial download"
            out.append(Candidate("spent raw", path, st.st_size, held, hit[0], hit[1], digest))
    for entry, (count, size) in unnamed.items():
        notes.append(f"kept {count} archives of data/raw/{entry}, {human(size)}: in no catalog")
    return out, notes


def stages_selected(root: Path) -> list[Candidate]:
    stages = sorted(p for p in (root / "output").glob(STAGES) if p.is_dir() and not p.is_symlink())
    out = []
    for stage in stages[:-1]:
        for path in _files(stage):
            if path.name == ".DS_Store" or never(root, path):
                continue
            out.append(Candidate("output stages", path, path.stat().st_size))
    return out


def private_selected(root: Path) -> list[Candidate]:
    private = root / "private"
    out = []
    for top in sorted(private.iterdir()) if private.is_dir() else []:
        if top.name in PRIVATE_KEEP or top.is_symlink():
            continue
        for path in _files(top):
            if path.name != ".DS_Store" and not never(root, path):
                out.append(Candidate("private", path, path.stat().st_size))
    return out


def backups_listed(root: Path) -> list[Candidate]:
    out = []
    for backup in sorted((root / "data").glob("ark.duckdb.pre-*.bak")):
        why = BACKUP_HOLDS.get(
            backup.name, "a store backup is deleted by the agents that own the store"
        )
        out.append(Candidate("store backups", backup, backup.stat().st_size, why))
    return out


def holds() -> dict[str, str]:
    """Repository-relative path -> why it is held, from disk_holds.tsv. A path ending in `/`
    holds everything under it; a line with no reason still holds its path."""
    out = {}
    for line in HOLDS.read_text().splitlines() if HOLDS.is_file() else []:
        if line.strip() and not line.startswith("#"):
            rel, _, why = line.partition("\t")
            out[rel.strip()] = why.strip() or "held by disk_holds.tsv"
    return out


def held_by(rel: str, held: dict[str, str]) -> str:
    return held.get(rel) or next(
        (why for key, why in held.items() if key.endswith("/") and rel.startswith(key)), ""
    )


def ia_file(item: str, name: str, cache: dict) -> dict | None:
    """archive.org's metadata for one file of one item, or None when it has no such file."""
    if item not in cache:
        request = urllib.request.Request(
            f"{IA}/metadata/{item}", headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(request, timeout=60) as reply:
            cache[item] = json.load(reply)
    meta = cache[item].get("metadata") or {}
    restricted = cache[item].get("is_dark") or meta.get("access-restricted-item") in (True, "true")
    files = cache[item].get("files") or []
    found = next((f for f in files if f.get("name") == name), None)
    return found and {**found, "restricted": bool(restricted)}


def ia_serves(url: str) -> bool:
    """archive.org answers a one-byte ranged GET for the file, as it does for an open file."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as reply:
            return reply.status in (200, 206)
    except (OSError, http.client.HTTPException):
        return False


def record_deleted(folder: Path, rel: str, size: int, digest: str, url: str) -> None:
    """One line in the entry's DELETED.tsv, written and flushed before the file goes."""
    path = folder / DELETED
    lines = path.read_text().splitlines() if path.is_file() else ["# rel\tbytes\tdigest\turl"]
    if any(line.split("\t", 1)[0] == rel for line in lines[1:]):
        return
    lines.append(f"{rel}\t{size}\t{digest}\t{url}")
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def remove_refetchable(root: Path, cand: Candidate, cache: dict, *, write: bool) -> str:
    """Delete one spent file once archive.org serves it again, recorded in DELETED.tsv."""
    rel_root = cand.path.relative_to(root)
    if not write:
        url = f"{IA}/download/{cand.item}/{cand.remote}"
        return f"would remove: {rel_root}  ({cand.digest[:14]}, {url})"
    offsite = sibling("offsite")
    before = offsite.signature(root, cand.path)
    there = ia_file(cand.item, cand.remote, cache)
    if there is None:
        raise ValueError(f"archive.org has no {cand.item}/{cand.remote}")
    url = f"{IA}/download/{cand.item}/{urllib.request.quote(cand.remote)}"
    # A file archive.org lists is not one it serves: a private file stays, and so does a
    # file in a restricted item that will not answer a ranged GET.
    if str(there.get("private", "")).lower() == "true":
        raise ValueError("archive.org lists the file as private, so it does not serve it")
    if there.get("restricted") and not ia_serves(url):
        raise ValueError(f"archive.org restricts {cand.item} and did not serve the file")
    if int(there.get("size", -1)) != before[2]:
        raise ValueError(f"archive.org holds {there.get('size')} B, not {before[2]}")
    if not there.get("sha1"):
        raise ValueError("archive.org gives no sha1 to compare our bytes with")
    # The sidecar digest of a Usenet zip is archive.org's catalog sha1, copied, so it can
    # only show archive.org has not changed the file. Our bytes are hashed here.
    with cand.path.open("rb") as handle:
        ours = hashlib.file_digest(handle, "sha1").hexdigest()
    if ours != there["sha1"]:
        raise ValueError("the sha1 of our bytes differs from archive.org's")
    folder = root / "data/raw" / rel_root.parts[2]
    digest = f"sha1:{ours}" + (f" {cand.digest}" if cand.digest.startswith("sha256:") else "")
    record_deleted(folder, cand.path.relative_to(folder).as_posix(), before[2], digest, url)
    if offsite.signature(root, cand.path) != before:
        raise ValueError(f"changed before deletion: {rel_root}")
    cand.path.unlink()
    return f"removed: {rel_root}"


def newest_on_drive(root: Path) -> str:
    """ "" when the newest stage's tarball is on Drive with the checksum git keeps."""
    offsite = sibling("offsite")
    stages = sorted(p for p in (root / "output").glob(STAGES) if p.is_dir())
    if not stages:
        return "no stage"
    tarball = f"{stages[-1].name}.tar.gz"
    kept = sorted((root / "submissions").glob(f"*/{tarball}.sha256"))
    if not kept:
        return f"git keeps no checksum for {tarball}"
    digest = kept[0].read_text().split()[0]
    remote = f"{offsite.REMOTE}/{kept[0].parent.relative_to(root).as_posix()}/{tarball}"
    try:
        done = offsite.rclone(
            ["lsjson", "--stat", "--hash", "--hash-type", "sha256", remote], check=False
        )
        there = json.loads(done.stdout) if not done.returncode else None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return f"Drive did not answer for {remote}: {type(exc).__name__}"
    if there is None:
        return f"Drive did not list {remote} (rclone exit {done.returncode})"
    if (there.get("Hashes") or {}).get("sha256") != digest:
        return f"Drive's {tarball} does not match its checksum"
    return ""


def remove_plain(root: Path, path: Path, *, under: str, write: bool) -> str:
    """Delete one regular file whose proof the caller holds for its whole group."""
    rel = path.relative_to(root)
    if rel.parts[0] != under or any(
        (root / Path(*rel.parts[:i])).is_symlink() for i in range(1, len(rel.parts) + 1)
    ):
        raise ValueError(f"refused: {rel}")
    if write:
        path.unlink()
    return f"{'removed' if write else 'would remove'}: {rel}"


def crc_failures(root: Path, cands: list[Candidate]) -> dict[Path, str]:
    """Release trees that fail the CRC check against a zip still here, by tree."""
    releases = sibling("releases")
    trees = releases.find_trees(root / "feedback", {})
    zips = releases.find_zips(root / "feedback")
    listed = {c.path for c in cands}
    failed = {}
    for marker, tree_paths in trees.items():
        for tree in tree_paths:
            if not zips.get(marker) or not any(tree in p.parents for p in listed):
                continue
            # A tree passes against any zip that holds its marker.
            problems: list[str] = []
            for archive in zips[marker]:
                try:
                    counts, problems = releases.verify_tree(tree, archive, marker)
                except (OSError, ValueError, zipfile.BadZipFile, zlib.error, RuntimeError) as exc:
                    # An unsafe or duplicate member holds this tree, not the whole run.
                    counts, problems = {"members": 0}, [str(exc)]
                if counts["members"] and not problems:
                    break
            else:
                failed[tree] = f"CRC check of {marker} against its zip failed: {problems[:2]}"
    return failed


def disk_cleanup(
    root: Path, *, write: bool = False, private: bool = False, owner_go: bool = False
) -> tuple[int, list[str]]:
    """List every --disk candidate by selector with its bytes and proof; with `write`,
    delete each one whose proof holds."""
    root = root.resolve()
    if private and write and not owner_go:
        cands = private_selected(root)
        size = sum(c.size for c in cands)
        return 1, [
            "--disk --private --write without --owner-go: nothing was deleted.",
            f"\nprivate: {len(cands)} files, {size:,} B ({human(size)})",
            *(f"  would remove: {c.path.relative_to(root)}" for c in cands),
        ]
    offsite = sibling("offsite")
    receipt = offsite.read_receipt(root)
    spent, notes = spent_selected(root)
    held_here = holds()
    groups = [
        ("releases", releases_selected(root, receipt)),
        ("spent raw", spent),
        ("output stages", stages_selected(root)),
        ("store backups", backups_listed(root)),
    ]
    if private:
        groups.append(("private", private_selected(root)))
    lines = [f"--disk {'--write' if write else 'dry run'}"]
    held_any, freed, listed = False, 0, 0
    stage_held = newest_on_drive(root) if write and groups[2][1] else ""
    if groups[2][1] and not write:
        notes.append("output stages go at --write only once the newest's tarball is on Drive")
    crc_held = crc_failures(root, groups[0][1]) if write else {}
    cache: dict = {}
    for label, cands in groups:
        size = sum(c.size for c in cands)
        listed += size
        lines.append(f"\n{label}: {len(cands)} files, {size:,} B ({human(size)})")
        for cand in cands:
            rel = cand.path.relative_to(root)
            held = cand.held or held_by(rel.as_posix(), held_here)
            held = held or (stage_held if label == "output stages" else "")
            held = held or next(
                (why for tree, why in crc_held.items() if tree in cand.path.parents), ""
            )
            if held:
                held_any = True
                lines.append(f"  HELD {rel}: {held}")
                continue
            try:
                if label == "releases":
                    line = (
                        remove_verified(root, cand.path, write=write)
                        if write
                        else f"would remove: {rel}"
                    )
                elif label == "spent raw":
                    line = remove_refetchable(root, cand, cache, write=write)
                elif label == "output stages":
                    line = remove_plain(root, cand.path, under="output", write=write)
                else:
                    line = remove_plain(root, cand.path, under="private", write=write)
                freed += cand.size
                lines.append(f"  {line}")
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                subprocess.SubprocessError,
                http.client.HTTPException,
            ) as exc:
                held_any = True
                lines.append(f"  HELD {rel}: {exc}")
            except KeyboardInterrupt:
                lines.append(f"\ninterrupted at {rel}: everything above it ran")
                return 1, lines
    if notes:
        lines += ["", *notes]
    verb = "removed" if write else "would remove"
    lines.append(f"\nlisted {listed:,} B ({human(listed)}); {verb} {freed:,} B ({human(freed)})")
    return (1 if held_any else 0), lines


def report(groups: list[Group], path: Path) -> list[str]:
    total = sum(g.size for g in groups)
    count = sum(len(g.entries) for g in groups)
    free = sum(g.size for g in groups if g.deletable)
    out = [
        f"{path}: {count} entries, {total:,} B ({human(total)}).",
        "Nothing was deleted: retention eligibility is not remote-copy verification.",
    ]
    for heading, deletable in (
        ("ELIGIBLE FOR REVIEW: class, refetch route and checksum record all hold", True),
        ("HELD: what each entry is missing, which is the off-site copy to-do list", False),
    ):
        out += ["", heading]
        for g in (g for g in groups if g.deletable == deletable):
            out.append(f"\n  {g.label}  [{len(g.entries)} entries, {g.size:,} B, {human(g.size)}]")
            for e in g.entries:
                size = "?" if e.size is None else human(e.size)
                out.append(f"    {e.key:<52} {size:>9}  {e.refetch[:60]}")
    out += [
        "",
        f"deletable {free:,} B ({human(free)}), "
        f"held {total - free:,} B ({human(total - free)}), "
        f"groups sum to {total:,} B.",
    ]
    return out


def as_json(groups: list[Group], path: Path) -> dict:
    return {
        "table": str(path),
        "deletes": False,
        "entries": sum(len(g.entries) for g in groups),
        "total_bytes": sum(g.size for g in groups),
        "deletable_bytes": sum(g.size for g in groups if g.deletable),
        "groups": [
            {
                "label": g.label,
                "deletable": g.deletable,
                "bytes": g.size,
                "entries": [
                    {
                        "entry": e.key,
                        "class": e.cls,
                        "files": e.files,
                        "bytes": e.size,
                        "refetch": e.refetch,
                        "route": e.route,
                        "record": e.record,
                        "missing": e.missing,
                    }
                    for e in g.entries
                ],
            }
            for g in groups
        ],
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    refused = [a for a in argv if a.split("=", 1)[0] in DELETE_FLAGS]
    if refused:
        print(
            f"prune.py has no {', '.join(refused)}: the retention report never deletes. "
            "Only --round --write and --disk --write delete, each file behind its proof.",
            file=sys.stderr,
        )
        return 2

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--table", type=Path, default=RETENTION, help="retention table to read")
    ap.add_argument("--json", action="store_true", help="machine-readable form")
    ap.add_argument(
        "--round", action="store_true", help="check superseded backups and release zips"
    )
    ap.add_argument(
        "--disk", action="store_true", help="list what somebody serves again, with its proof"
    )
    ap.add_argument(
        "--private", action="store_true", help="with --disk, private/ off the keep list"
    )
    ap.add_argument(
        "--owner-go",
        action="store_true",
        help="with --disk --private --write, the owner's go to delete private/",
    )
    ap.add_argument(
        "--write", action="store_true", help="with --round or --disk, remove what is proven"
    )
    ap.add_argument("--root", type=Path, default=REPO)
    args = ap.parse_args(argv)

    if args.write and not (args.round or args.disk):
        ap.error("--write requires --round or --disk")
    if args.private and not args.disk:
        ap.error("--private requires --disk")
    if args.owner_go and not (args.private and args.write):
        ap.error("--owner-go goes only with --disk --private --write")
    if args.disk:
        if args.round or args.json:
            ap.error("--disk takes neither --round nor --json")
        code, lines = disk_cleanup(
            args.root, write=args.write, private=args.private, owner_go=args.owner_go
        )
        print("\n".join(lines))
        return code
    if args.round:
        if args.json:
            ap.error("--round does not accept --json")
        code, lines = round_cleanup(args.root, write=args.write)
        print("\n".join(lines))
        return code

    groups = group(read_table(args.table))
    if args.json:
        print(json.dumps(as_json(groups, args.table), indent=2))
    else:
        print("\n".join(report(groups, args.table)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
