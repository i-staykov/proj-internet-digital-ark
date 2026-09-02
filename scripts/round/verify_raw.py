"""Checksum every local data entry and rewrite the tracked retention table.

Nothing under `data/raw/` may be deleted until every file has a checksum line and
the entry has a tracked row saying what it is. This script writes both.

`SHA256SUMS` sits beside the data, one per entry (`data/raw/<entry>/SHA256SUMS`, the
shape `wwwvl` and `ncsa-whats-new` already used), `sha256sum -c` compatible. A
`SHA256SUMS.stat` sidecar records size and mtime, so the next run hashes only what
moved. A Usenet zip that `data/raw/usenet_catalog.json` names at the same size takes
IA's sha1 into `SHA1SUMS` instead of a rehash; that covers the 9,266 zips of
`usenet_bulk`. Loose files at a root (`data/raw/checksums.sha256`, `data/*.bak`)
share the root's manifest. The manifests stay untracked: 89k lines that move with
every collector run do not belong in a public repo.

`docs/retention.md` is tracked, one row per entry: the children of `data/raw/`,
`output/` and `feedback/`, and every `data/*.bak`. The class comes from the tables
below; an entry they do not name defaults to `reference` and is flagged. A path with
no row is not deletable, and `just prune` reads this table before touching anything.

    uv run python scripts/round/verify_raw.py             # everything
    uv run python scripts/round/verify_raw.py --dry-run   # what a run would hash and write
    uv run python scripts/round/verify_raw.py --entry wwwvl

Reads the data and writes only the manifests and the table, so it is safe to run
beside a working collector.
"""

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RETENTION = "docs/retention.md"
CATALOG = "data/raw/usenet_catalog.json"
SUMS, SHA1S, STAT = "SHA256SUMS", "SHA1SUMS", "SHA256SUMS.stat"
MANIFESTS = frozenset({SUMS, SHA1S, STAT})

# Every child of a root is an entry; with a glob, only the matching loose files are
# (the store backups, never the store itself).
ROOTS: tuple[tuple[str, str | None], ...] = (
    ("data/raw", None),
    ("output", None),
    ("feedback", None),
    ("data", "*.bak"),
)

OWN = "own_journal"
UNKNOWN = "unknown"
IA_USENET = "https://archive.org/download/usenet-<hierarchy>/<group>.mbox.zip"

# The 26 entries the retention audit of 2026-09-02 left unpriced at hostname grain,
# with the URL it recorded. `None` is honest: nobody has found where the bytes came from.
KEEP_UNTIL_PRICED: dict[str, str | None] = {
    "antispam_media": None,
    "arquivo": "https://arquivo.pt/datasets/cdxj/Roteiro.cdxj",
    "attrition": "https://raw.githubusercontent.com/attrition-org/web-hack-mirror/main/mirror/",
    "can_domain": "https://archive.org/download/usenet-can/can.domain.mbox.zip",
    "dartmouth_bfs": "https://archive.org/details/Dartmouth_10KwebURLs_GWB-20180911224740_BFS_4-lvls",
    "freebsd_ports": "ftp://ftp-archive.freebsd.org/pub/FreeBSD-Archive/old-releases/i386/",
    "internic_zones": "https://web.archive.org/web/19970420113748id_/http://nic.mil/oroot.html/",
    "jeb_bush": "https://archive.org/download/JebBushEmails/JebBushEmails-Text.7z",
    "maillists": "https://mail.python.org/pipermail/ and https://mail.gnome.org/archives/",
    "ncsa-whats-new": "https://web.archive.org/cdx/search/cdx?url=ncsa.uiuc.edu/SDG/Software/Mosaic/Docs/whats-new*&from=1996&to=1996",
    "nypw": "https://archive.org/details/nypw_urls_CDXfirstentry",
    "odp": "https://web.archive.org/cdx/search/cdx?url=dmoz.org/rdf/*&from=2000&to=2001",
    "probes": None,
    "rtfm": "https://archive.org/download/ftp_rtfm.mit.edu_2014.07/2014.07.rtfm.mit.edu.tar",
    "scout": "https://archives.internetscout.org/OAI?verb=ListRecords&metadataPrefix=oai_dc",
    "source_probe_260806": "https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz",
    "squidguard_contrib_2001": "https://web.archive.org/web/20010710215730id_/http://ftp.ost.eltele.no/pub/www/proxy/squidGuard/contrib/blacklists.tar.gz",
    "texts": "https://archive.org/download/<identifier>/<identifier>_djvu.txt",
    "tucows": "https://archive.org/advancedsearch.php?q=collection:tucows+AND+year:[1996+TO+2001]",
    "ukwa": "https://web.archive.org/web/2019id_/https://www.webarchive.org.uk/datasets/ukwa.ds.2/linkage/host-linkage.tsv.gz",
    "usenet_bulk": "https://archive.org/details/usenet-alt",
    "usenet_msft": "https://archive.org/details/usenet-alt",
    "usenet_new": IA_USENET,
    "usenet_probe": "https://archive.org/download/usenet-comp/comp.infosystems.www.misc.mbox.zip",
    "usenet_probe5": IA_USENET,
    "wwwvl": "http://vlib.org/",
}

# Third-party bytes read by `just sources`, `candidates`, `seeds` or `pandora-seed`:
# the offline rebuild breaks without them. `None` means docs/sources.md has the URL
# and this table does not carry it yet.
LIVE_INPUT: dict[str, str | None] = {
    "afnic": None,
    "cctld": None,
    "cctld_capture": None,
    "chastity": None,
    "coza": None,
    "dartmouth_nber": None,
    "domain_creation": None,
    "early_web": None,
    "edelman": None,
    "fac": "https://www.fac.gov/data/download/historic/",
    "granitecanyon": None,
    "iedr": None,
    "isc_survey": None,
    "junkfilter": None,
    "mynic": None,
    "namewinner": None,
    "nypw_timemaps": None,
    "pandora-titles": None,
    "ripe_funet": None,
    "ripe_funet_split": None,
    "squidguard": None,
    "udrp": "https://www.icann.org/udrp/proceedings-list.htm",
    "urlmerchant": None,
    "us_domain": None,
    "webbase": None,
}

# Our own collectors' journals, replayed by `just sources` or `just journals`, or
# a hostname-grain journal a later ingest reads.
KEEP_JOURNAL = frozenset(
    {
        "cdx",
        "cdx_suffix",
        "early_web_hostgrain",
        "enron",
        "expand",
        "rdap",
        "rdap_gen",
        "tradepress",
        "usenet",
        "usenet_addr",
        "usenet_bare",
        "usenet_de",
        "usenet_hdr",
        "usenet_whois",
        "usfedgov_hostgrain",
        "uucp",
        "yahoo96",
    }
)

# Kept for the record: measured negatives whose verdict is in docs/sources.md, spent
# probes, quarantined journals, and the older checksum records.
REFERENCE: dict[str, str] = {
    "100hot": UNKNOWN,
    "alexa": UNKNOWN,
    "bl": UNKNOWN,
    "ccgraph": UNKNOWN,
    "checksums.sha256": UNKNOWN,
    "dedup_pool": UNKNOWN,
    "edgar": UNKNOWN,
    "ffiec": UNKNOWN,
    "jpnic_tomocha": UNKNOWN,
    "lang": UNKNOWN,
    "pandora": UNKNOWN,
    "rdap_hold_uk": OWN,
    "rdap_probe_gen": OWN,
    "seeds": UNKNOWN,
    "squidguard2001": UNKNOWN,
    "usenet_catalog.json": "https://archive.org/metadata/usenet-<hierarchy>",
    "usenet_probe2": UNKNOWN,
    "usenet_probe3": UNKNOWN,
    "usenet_probe4": UNKNOWN,
    "usfedgov": "https://archive.org/download/USFEDGOV-EXTRACT-<year>/USFEDGOV-EXTRACT-<year>.cdx.gz",
}

# Rebuilt by a script or recipe, so the bytes are the cheapest thing on the disk.
REGENERABLE: dict[str, str] = {
    "early_web_hostgrain.log": "scripts/sources/early_web/early_web_hostgrain.py",
    "gapfill_candidates.txt": "derived list, no reader",
    "gapfill_sample.txt": "derived list, no reader",
    "isc_survey_hostgrain.log": "just sources",
    "nypw_hostgrain": "regenerable from nypw_timemaps",
}


def classify(key: str) -> tuple[str, str] | None:
    """Class and refetch for an entry key like `data/raw/wwwvl`, or None when unlisted."""
    root, _, name = key.rpartition("/")
    if root == "data/raw":
        if name in KEEP_UNTIL_PRICED:
            return "keep_until_priced", KEEP_UNTIL_PRICED[name] or UNKNOWN
        if name in LIVE_INPUT:
            return "live_input", LIVE_INPUT[name] or UNKNOWN
        if name in KEEP_JOURNAL:
            return "keep_journal", OWN
        if name in REFERENCE:
            return "reference", REFERENCE[name]
        if name in REGENERABLE:
            return "regenerable", REGENERABLE[name]
        return None
    if root == "output":
        return "regenerable", "just ship, or ark export"
    if root == "feedback":
        return "reference", "reviewer_release"
    if root == "data" and name.endswith(".bak"):
        return "regenerable", "just reproduce"
    return None


@dataclass
class Row:
    key: str
    cls: str
    known: bool
    refetch: str
    files: int | None = None
    size: int | None = None
    digest: str = "none"
    record: str = "none"


@dataclass
class Manifest:
    """What one manifest location holds, keyed by the `./rel` path each line names."""

    where: Path
    sums: dict[str, str] = field(default_factory=dict)
    sha1s: dict[str, str] = field(default_factory=dict)
    stats: dict[str, tuple[int, int]] = field(default_factory=dict)
    todo: list[str] = field(default_factory=list)

    @classmethod
    def read(cls, where: Path) -> "Manifest":
        m = cls(where)
        for rel, value in _read_hashes(where / SUMS):
            m.sums[rel] = value
        for rel, value in _read_hashes(where / SHA1S):
            m.sha1s[rel] = value
        for line in _read_lines(where / STAT):
            size, mtime, rel = line.split(" ", 2)
            m.stats[rel] = (int(size), int(mtime))
        return m

    def lines(self, kind: str) -> list[str]:
        if kind == STAT:
            return sorted(f"{s} {m} {rel}" for rel, (s, m) in self.stats.items())
        table = self.sums if kind == SUMS else self.sha1s
        return sorted(f"{digest}  {rel}" for rel, digest in table.items())


@dataclass
class Report:
    hashed: int = 0
    hashed_bytes: int = 0
    written: list[Path] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)


def _read_lines(path: Path) -> list[str]:
    return path.read_text().splitlines() if path.is_file() else []


def _read_hashes(path: Path) -> list[tuple[str, str]]:
    """`<hex>  ./rel` lines as (rel, hex); a line without the `./` prefix is not ours."""
    out = []
    for line in _read_lines(path):
        digest, sep, rel = line.partition("  ")
        if sep and rel.startswith("./"):
            out.append((rel, digest))
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def digest_of(sums: list[str], sha1s: list[str]) -> str:
    """sha256 over the sorted SHA256SUMS lines, then the sorted SHA1SUMS lines.

    With no SHA1SUMS beside it, `sha256sum SHA256SUMS` reproduces the figure.
    """
    if not sums and not sha1s:
        return "none"
    text = "".join(f"{line}\n" for line in sorted(sums) + sorted(sha1s))
    return hashlib.sha256(text.encode()).hexdigest()


def load_catalog(root: Path) -> dict[str, tuple[str, int]]:
    """IA zip name -> (sha1, size) from usenet_catalog.json, empty when absent."""
    path = root / CATALOG
    if not path.is_file():
        return {}
    out: dict[str, tuple[str, int]] = {}
    for items in json.loads(path.read_text()).values():
        for it in items:
            out[it["name"]] = (it["sha1"], int(it["size"]))
    return out


def list_files(entry: Path) -> list[tuple[str, os.stat_result]]:
    """`(./rel, stat)` for every regular file, the entry's own manifests excluded, sorted."""
    if entry.is_file():
        return [("./" + entry.name, entry.stat())]
    found = []
    for dirpath, dirnames, filenames in os.walk(entry):
        dirnames.sort()
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink() or not path.is_file():
                continue
            if path.parent == entry and name in MANIFESTS:
                continue
            found.append(("./" + path.relative_to(entry).as_posix(), path.stat()))
    return sorted(found)


def owns(entry: Path, rel: str) -> bool:
    """A directory owns its whole manifest; a loose file owns its one line at the root."""
    return entry.is_dir() or rel == "./" + entry.name


def plan_entry(
    key: str,
    entry: Path,
    old: Manifest,
    new: Manifest,
    catalog: dict[str, tuple[str, int]],
    report: Report,
) -> tuple[int, int]:
    """Reuse what has not moved, copy catalog sha1s, queue the rest. Returns (files, bytes)."""
    files = size = 0
    seen = set()
    for rel, st in list_files(entry):
        files += 1
        size += st.st_size
        seen.add(rel)
        stat = (st.st_size, st.st_mtime_ns)
        new.stats[rel] = stat
        name = rel.rsplit("/", 1)[-1]
        if name.endswith(".zip") and name in catalog:
            sha1, cat_size = catalog[name]
            if cat_size == st.st_size:
                new.sha1s[rel] = sha1
                continue
            report.flags.append(
                f"{key}: {rel} is {st.st_size} bytes, catalog says {cat_size}; hashed"
            )
        if old.stats.get(rel) == stat and rel in old.sums:
            new.sums[rel] = old.sums[rel]
        else:
            new.todo.append(rel)
    gone = [rel for rel in old.stats if owns(entry, rel) and rel not in seen]
    if gone:
        report.flags.append(f"{key}: {len(gone)} files in the last {SUMS} are gone")
    return files, size


def carry_over(new: Manifest, old: Manifest) -> None:
    """Keep a shared root manifest's lines for the loose files this run did not select."""
    for rel, stat in old.stats.items():
        path = new.where / rel
        if rel in new.stats or rel[2:] in MANIFESTS or not path.is_file():
            continue
        new.stats[rel] = stat
        if rel in old.sums:
            new.sums[rel] = old.sums[rel]
        if rel in old.sha1s:
            new.sha1s[rel] = old.sha1s[rel]


def write_if_changed(path: Path, text: str, dry_run: bool, report: Report) -> None:
    """Write only on a difference, so an unchanged tree leaves every mtime alone."""
    if path.is_file():
        if path.read_text() == text:
            return
    elif not text:
        return
    report.written.append(path)
    if dry_run:
        return
    if text:
        path.write_text(text)
    else:
        path.unlink()


def fill_row(row: Row, entry: Path, m: Manifest, root: Path) -> None:
    sums = [f"{h}  {rel}" for rel, h in m.sums.items() if owns(entry, rel)]
    sha1s = [f"{h}  {rel}" for rel, h in m.sha1s.items() if owns(entry, rel)]
    row.digest = digest_of(sums, sha1s)
    kinds = [kind for kind, lines in ((SUMS, sums), (SHA1S, sha1s)) if lines]
    if not kinds:
        row.record = "none"
    elif entry.is_dir():
        row.record = ", ".join(kinds)
    else:
        where = m.where.relative_to(root).as_posix()
        row.record = "line in " + ", ".join(f"{where}/{kind}" for kind in kinds)


def new_row(key: str, report: Report) -> Row:
    known = classify(key)
    if known is None:
        report.flags.append(f"{key}: not in the classification tables, defaulted to reference")
    cls, refetch = known or ("reference", UNKNOWN)
    return Row(key, cls, known is not None, refetch)


def row_from_disk(key: str, entry: Path, root: Path, report: Report) -> Row:
    """A row for an entry this run did not scan, read off the manifests it already has."""
    row = new_row(key, report)
    m = Manifest.read(entry if entry.is_dir() else entry.parent)
    stats = [stat for rel, stat in m.stats.items() if owns(entry, rel)]
    if stats:
        row.files = len(stats)
        row.size = sum(size for size, _ in stats)
    fill_row(row, entry, m, root)
    return row


def entries_of(root: Path, sub: str, glob: str | None) -> list[Path]:
    base = root / sub
    if not base.is_dir():
        return []
    if glob:
        return sorted(p for p in base.glob(glob) if p.is_file())
    return sorted(p for p in base.iterdir() if p.name not in MANIFESTS and not p.is_symlink())


def selected(key: str, only: str | None) -> bool:
    return only is None or key == only or key == f"data/raw/{only}"


def run(root: Path, dry_run: bool = False, only: str | None = None) -> Report:
    report = Report()
    catalog = load_catalog(root)
    olds: dict[Path, Manifest] = {}
    news: dict[Path, Manifest] = {}
    scanned: list[tuple[Row, Path, Manifest]] = []
    for sub, glob in ROOTS:
        for entry in entries_of(root, sub, glob):
            key = f"{sub}/{entry.name}"
            if not selected(key, only):
                report.rows.append(row_from_disk(key, entry, root, report))
                continue
            where = entry if entry.is_dir() else entry.parent
            old = olds.setdefault(where, Manifest.read(where))
            new = news.setdefault(where, Manifest(where))
            row = new_row(key, report)
            row.files, row.size = plan_entry(key, entry, old, new, catalog, report)
            scanned.append((row, entry, new))
            report.rows.append(row)
    if only is not None and not scanned:
        raise SystemExit(f"no entry matches --entry {only}")

    shared = {root / sub for sub, _ in ROOTS}
    for where, new in news.items():
        if only is not None and where in shared:
            carry_over(new, olds[where])
        for rel in new.todo:
            report.hashed += 1
            report.hashed_bytes += new.stats[rel][0]
            # a dry run stands a placeholder in, so the manifest it would write is listed
            new.sums[rel] = "?" * 64 if dry_run else sha256_file(where / rel)
        for kind in (SUMS, STAT, SHA1S):
            text = "".join(f"{line}\n" for line in new.lines(kind))
            write_if_changed(where / kind, text, dry_run, report)

    for row, entry, new in scanned:
        fill_row(row, entry, new, root)
    write_if_changed(root / RETENTION, render(report.rows), dry_run, report)
    return report


HEADER = "\n".join(
    [
        "# Retention",
        "Generated by `scripts/round/verify_raw.py` (`just verify-raw`) from the classification "
        "tables in the script; change those, never a row.",
        "",
        "One row per local data entry: the children of `data/raw/`, `output/` and `feedback/`, "
        "and every `data/*.bak`. A path with no row is not deletable. `files` and `bytes` are "
        "what the entry held at the last run. `digest` is the sha256 of the entry's sorted "
        "`SHA256SUMS` lines, followed by its `SHA1SUMS` lines where IA's own sha1 from "
        "`data/raw/usenet_catalog.json` stands in for a rehash of a Usenet zip; the manifests "
        "sit untracked beside the data and `record` names them. `refetch` is a URL, "
        "`own_journal` for what our own collectors wrote, the recipe that rebuilds the entry, "
        "`reviewer_release` for what arrived by mail, or `unknown`.",
        "",
        "Classes: `live_input` is third-party bytes read by `just sources`, `candidates`, "
        "`seeds` or `pandora-seed`; `keep_journal` is a journal of our own that a recipe "
        "replays; `keep_until_priced` waits for its pricing at hostname grain; `reference` is "
        "kept for the record; `regenerable` is rebuilt by a recipe.",
        "",
        "| entry | class | files | bytes | digest | refetch | record |",
        "|---|---|---|---|---|---|---|",
        "",
    ]
)


def render(rows: list[Row]) -> str:
    def cell(value: int | None) -> str:
        return "?" if value is None else str(value)

    out = [HEADER]
    for r in rows:
        out.append(
            f"| `{r.key}` | {r.cls} | {cell(r.files)} | {cell(r.size)} | `{r.digest}` "
            f"| {r.refetch} | {r.record} |\n"
        )
    unknown = [r.key for r in rows if not r.known]
    if unknown:
        out.append(
            "\nNot in the classification tables, so defaulted to `reference` until someone adds "
            "them to the script: " + ", ".join(f"`{k}`" for k in unknown) + ".\n"
        )
    return "".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this one)")
    ap.add_argument(
        "--dry-run", action="store_true", help="hash and write nothing, say what would be"
    )
    ap.add_argument("--entry", help="one entry only: `wwwvl`, `data/raw/wwwvl`, `output/<dir>`")
    args = ap.parse_args(argv)
    report = run(args.root.resolve(), dry_run=args.dry_run, only=args.entry)
    for row in report.rows:
        if row.files is not None:
            print(f"{row.key:<56} {row.cls:<18} {row.files:>7} {row.size:>14}  {row.record}")
    verb, wrote = ("would hash", "would write") if args.dry_run else ("hashed", "wrote")
    print(
        f"{verb} {report.hashed} files, {report.hashed_bytes} bytes; {wrote} {len(report.written)}"
    )
    for path in report.written:
        print(f"  {path}")
    for flag in report.flags:
        print(f"flag: {flag}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
