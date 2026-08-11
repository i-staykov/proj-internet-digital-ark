"""What is on disk that nothing has read, and what the documented path would miss.

The reviewer's first priority is residual opportunity inside sources already
used: "unprocessed files, failed parses, truncated runs, unqueried candidates,
missing date partitions". This answers the file half of that in one command, with
no network and no write lock, so it can run before every collection decision.

**It exists because the answer was worth 14,956 equivalent-English on 2026-08-10.**
496 per-TLD ISC survey shards had been on disk since 5 August, matched by a glob
`just sources` already documented, and no ingest had ever read them. Nothing here
searched for a new source; it diffed disk against the ingest ledger. Every
measurement the project takes starts from the store, so every one of them was
blind to those files.

Five checks, each of which has caught something real:

`unread`         files a documented ingest glob matches that the ledger has never
                 read, per source. The ISC case, and the first thing to look at.
`glob_too_narrow` files the ledger holds that the documented glob does NOT match.
                 Not lost yield: a reproduction defect, because `just reproduce`
                 rebuilds a store missing them. Found twice on 2026-07-26, where
                 `isc_survey/*.domains.gz` silently missed `wb_nw_9607_org.gz`.
`unreferenced`   directories under data/raw/ that no ingest glob points into at
                 all. These are the "bytes nothing reads" in `docs/sources.md`,
                 and one of them is a National Library of Australia title index.
`usenet`         the corpus has its own `.processed` ledger rather than rows in
                 `ingested_file`, so it needs its own three-way comparison
                 against the catalogue and the disk.
`stale_derived`  derived artifacts older than the baseline release they are
                 supposed to reflect. A queue built before a release is
                 structurally blind to it, which once hid 102,628 targets.

Nothing here is a gate. It reports and exits 0, because "there is unread material
on disk" is a fact about the round rather than a broken invariant, and a check
that fails the build for it would simply be turned off.

    uv run python scripts/audit_residual.py
    uv run python scripts/audit_residual.py --check unread --verbose
"""

import argparse
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from ark.baseline import CURRENT_BASELINE_MARKER  # noqa: E402
from ark.sources import SOURCES  # noqa: E402
from ark.stats import BASELINE_TYPE  # noqa: E402

STORE = ROOT / "data/ark.duckdb"
RAW = ROOT / "data/raw"
JUSTFILE = ROOT / "justfile"

# `ark ingest <key> <path-or-glob>`, ignoring a commented-out line. Two sources
# are deliberately not on any glob: `arquivo_ia`'s 47 GB input was reclaimed once
# its evidence was in the store, and the ingest line is commented out to say so.
INGEST_RE = re.compile(r"^\s*(?!#)\s*uv run ark ingest\s+(\S+)\s+(\S+)")

# Derived artifacts that a new reviewer release invalidates. Each is regenerable,
# so the finding is "rebuild this", never "you have lost something".
DERIVED = (
    # The operative lists since the two-machine split of 2026-08-11: the VPS works
    # bracketed gaps, the local engine works the candidate pool.
    ("data/raw/cdx/queue_gap_vps.txt", "build_query_queue.py --population gap"),
    ("data/raw/cdx/queue_pool_local.txt", "build_query_queue.py --population pool"),
    ("data/raw/rdap/pool_targets_org.txt", "build_rdap_pool_list.py --tlds org"),
    # The mixed queue, kept because a shard of it may still be in flight on a
    # machine that has not been re-pointed yet.
    ("data/raw/cdx/queue_shard0.txt", "just query-queue"),
    ("data/raw/cdx/queue_shard1.txt", "just query-queue"),
    ("data/raw/cdx/queue_manifest.tsv.gz", "just query-queue"),
)

# Directories whose contents are inputs to a collector rather than to an ingest,
# or which are recorded as rejected on measurement. Naming them here keeps the
# `unreferenced` check to material that is genuinely unaccounted for; without it
# the check reports every OCR cache file and reads as noise.
ACCOUNTED = {
    "usenet": "the corpus, tracked in its own .processed ledger",
    "usenet_bulk": "verified byte-identical duplicate of data/raw/usenet",
    "usenet_probe": "spent probe, superseded by the whole-corpus run",
    "usenet_probe4": "spent probe",
    "usenet_probe5": "spent probe, duplicate bytes",
    "rtfm": "extracted FAQ tree, read by scripts/split_rtfm_faqs.py",
    "maillists": "harvested month files, read by scripts/collect_mailing_lists.py",
    "texts": "trade-press OCR cache, read by scripts/reextract_trade_press.py",
    "webbase": "rejected on measurement: 99.99% already held",
    "nypw": "rejected on measurement: 53 net-new domains over 6.28M lines",
    "100hot": "worked in phase 1 to 3,453 hostnames; master-evidence route declined",
    "wwwvl": "page cache for the Virtual Library expansion rounds",
    "lang": "retired English-verification engine, see legacy/README.md",
    "yahoo96": "rejected on measurement: 7.73 EE over 55 requests",
    # read by a script rather than by an ingest glob, so `unreferenced` cannot
    # clear it on its own: seeds candidates, evidences nothing, has no date column
    "pandora-titles": "seed-only, read by scripts/seed_pandora_titles.py",
    "pandora": "byte-identical duplicate of pandora-titles/pandora-titles.csv",
    "gapfill_candidates.txt": "target list",
    "gapfill_sample.txt": "target list",
    "usenet_catalog.json": "the group catalogue, read by the Usenet collectors",
    "checksums.sha256": "the pinned source manifest",
}


def read_only_store(path: Path, patience_s: int = 900) -> duckdb.DuckDBPyConnection:
    """Open for reading, waiting out a writer.

    Patience is 15 minutes, not the 2 minutes this first shipped with. That was
    sized against `just maintain`, which holds the write lock for seconds, and it
    failed the first time it met a real writer: `ark seed` over 29,432 names holds
    the lock for more than twenty minutes, so a read-only audit gave up at
    exactly the moment the audit was worth running. A writer that outlasts even
    this gets a one-line explanation naming its PID, because a traceback out of a
    read-only reporting tool reads as a defect in the tool.
    """
    deadline = time.monotonic() + patience_s
    announced = False
    while True:
        try:
            return duckdb.connect(str(path), read_only=True)
        except duckdb.Error as exc:
            message = str(exc)
            if "Conflicting lock" not in message:
                raise
            if time.monotonic() >= deadline:
                pid = re.search(r"PID (\d+)", message)
                who = f" (PID {pid.group(1)})" if pid else ""
                raise SystemExit(
                    f"the store is being written{who} and still was after "
                    f"{patience_s}s. Nothing is wrong: this reads the store, so it "
                    f"waits for the writer. Re-run when the ingest or seed finishes."
                ) from None
            if not announced:
                print(f"waiting for a writer to release {path.name} ...", flush=True)
                announced = True
            time.sleep(3)


def ingest_globs() -> list[tuple[str, str, str]]:
    """(spec key, source name, glob) for every documented ingest line."""
    out = []
    for line in JUSTFILE.read_text(encoding="utf-8").splitlines():
        match = INGEST_RE.match(line)
        if not match:
            continue
        key, pattern = match.group(1), match.group(2)
        spec = SOURCES.get(key)
        if spec is None:
            # `ingest-legacy` and any journal spec not in SOURCES; the ledger
            # cannot be joined for those, so they are out of scope rather than
            # silently reported as clean.
            continue
        out.append((key, spec.source_name, pattern))
    return out


def check_unread(ledger: dict[str, set[str]], verbose: bool) -> int:
    """Files a documented glob matches that the ledger has never read."""
    print("== unread: a documented ingest glob matches it, no ingest has read it ==")
    total = 0
    for key, source_name, pattern in ingest_globs():
        matched = sorted(ROOT.glob(pattern))
        if not matched:
            continue
        seen = ledger.get(source_name, set())
        missing = [p for p in matched if p.name not in seen]
        if not missing:
            continue
        nbytes = sum(p.stat().st_size for p in missing)
        total += len(missing)
        print(
            f"  {key:24} {len(missing):>6,} of {len(matched):>6,} matched files unread"
            f"  {nbytes:>15,} bytes"
        )
        for path in missing if verbose else missing[:4]:
            print(f"      {path.relative_to(ROOT)}")
        if not verbose and len(missing) > 4:
            print(f"      ... and {len(missing) - 4:,} more, pass --verbose")
    if not total:
        print("  nothing: every file a documented glob matches is in the ledger")
    return total


def check_glob_too_narrow(ledger: dict[str, set[str]], verbose: bool) -> int:
    """Files the ledger holds that the documented glob does not match.

    Not lost yield. It means `just reproduce` rebuilds a store without them, so
    the reproduction path claims more than it delivers.
    """
    print("\n== glob_too_narrow: ingested, but the documented glob would miss it ==")
    by_source: dict[str, set[str]] = defaultdict(set)
    for _key, source_name, pattern in ingest_globs():
        by_source[source_name] |= {p.name for p in ROOT.glob(pattern)}
    total = 0
    for source_name, reachable in sorted(by_source.items()):
        held = ledger.get(source_name, set())
        missed = sorted(held - reachable)
        if not missed:
            continue
        total += len(missed)
        print(f"  {source_name:24} {len(missed):>6,} of {len(held):>6,} ledgered files unreachable")
        for name in missed if verbose else missed[:4]:
            print(f"      {name}")
        if not verbose and len(missed) > 4:
            print(f"      ... and {len(missed) - 4:,} more, pass --verbose")
    if not total:
        print("  nothing: every ledgered file is reachable from a documented glob")
    return total


def check_unreferenced(verbose: bool) -> int:
    """Directories under data/raw/ that no ingest glob points into at all."""
    print("\n== unreferenced: downloaded bytes with no parser and no ingest line ==")
    targeted = set()
    for _key, _source, pattern in ingest_globs():
        # the directory the glob reads, relative to data/raw
        parts = Path(pattern).parts
        if len(parts) > 2 and parts[0] == "data" and parts[1] == "raw":
            targeted.add(parts[2])
    rows = []
    for entry in sorted(RAW.iterdir()):
        name = entry.name
        if name in targeted or name in ACCOUNTED:
            continue
        if entry.is_dir():
            nbytes = sum(p.stat().st_size for p in entry.rglob("*") if p.is_file())
            nfiles = sum(1 for p in entry.rglob("*") if p.is_file())
        else:
            nbytes, nfiles = entry.stat().st_size, 1
        rows.append((nbytes, nfiles, name))
    for nbytes, nfiles, name in sorted(rows, reverse=True):
        print(f"  {name:34} {nfiles:>7,} files  {nbytes:>15,} bytes")
    if not rows:
        print("  nothing unaccounted for under data/raw/")
    if verbose and rows:
        print("\n  accounted for deliberately, with the reason:")
        for name, why in sorted(ACCOUNTED.items()):
            print(f"    {name:28} {why}")
    return len(rows)


def check_usenet() -> int:
    """Catalogue against disk against `.processed`, the corpus's own ledger."""
    print("\n== usenet: catalogue vs disk vs .processed ==")
    import json

    catalogue = RAW / "usenet_catalog.json"
    corpus = RAW / "usenet"
    processed = corpus / ".processed"
    if not catalogue.exists() or not corpus.is_dir():
        print("  skipped: catalogue or corpus directory absent")
        return 0
    cat = json.loads(catalogue.read_text(encoding="utf-8"))
    want = {item["name"]: int(item["size"]) for entries in cat.values() for item in entries}
    on_disk = {p.name: p.stat().st_size for p in corpus.glob("*.mbox.zip")}
    done = (
        {
            line.strip()
            for line in processed.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        if processed.exists()
        else set()
    )
    missing = sorted(set(want) - set(on_disk))
    unread = sorted(set(on_disk) - done)
    wrong_size = sorted(n for n, size in on_disk.items() if n in want and want[n] != size)
    partial = sorted(p.name for p in corpus.glob("*.part")) + sorted(
        p.name for p in corpus.glob("*.tmp")
    )
    print(f"  catalogue {len(want):>7,} groups  {sum(want.values()):>15,} bytes")
    print(f"  on disk   {len(on_disk):>7,} groups  {sum(on_disk.values()):>15,} bytes")
    print(f"  processed {len(done):>7,}")
    print(f"  on disk and unread            : {len(unread):>7,}")
    print(f"  size differs from the catalogue: {len(wrong_size):>7,}")
    print(f"  partial or temporary files     : {len(partial):>7,}")
    if missing:
        print(f"  absent from disk ({len(missing)}): {', '.join(missing[:6])}")
    return len(unread) + len(wrong_size) + len(partial)


def baseline_loaded_at(conn: duckdb.DuckDBPyConnection) -> float | None:
    """Unix time at which the newest `prior_reused` evidence landed.

    Anchored on the evidence rather than on `ingested_file`, because the legacy
    loader does not write a ledger row a file glob can find, and because the
    evidence rows are what actually changed: they are the reason a queue built
    earlier is blind to the release. Read as epoch seconds inside SQL, since
    DuckDB needs `pytz` to hand a TIMESTAMPTZ to Python and it is not a
    dependency here.
    """
    row = conn.execute(
        "SELECT max(epoch(ingested_at)) FROM evidence WHERE evidence_type = ?", [BASELINE_TYPE]
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else None


def check_stale_derived(conn: duckdb.DuckDBPyConnection) -> int:
    """Derived artifacts older than the release they should reflect."""
    print("\n== stale_derived: built before the current baseline landed ==")
    loaded = baseline_loaded_at(conn)
    if loaded is None:
        print("  skipped: no baseline evidence in the store, so nothing to be stale against")
        return 0
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(loaded))
    print(f"  newest {CURRENT_BASELINE_MARKER} evidence landed {stamp}")
    stale = 0
    for rel, rebuild in DERIVED:
        path = ROOT / rel
        if not path.exists():
            continue
        mtime = path.stat().st_mtime
        when = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime))
        if mtime < loaded:
            stale += 1
            print(f"  [STALE] {rel}  {when}  rebuild: {rebuild}")
        else:
            print(f"  [ok]    {rel}  {when}")
    if not stale:
        print("  nothing: every derived artifact postdates the baseline load")
    return stale


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="append",
        choices=["unread", "glob_too_narrow", "unreferenced", "usenet", "stale_derived"],
        help="run only these checks (repeatable). Default: all five.",
    )
    ap.add_argument("--verbose", action="store_true", help="list every file, not the first four")
    args = ap.parse_args()
    wanted = set(
        args.check or ["unread", "glob_too_narrow", "unreferenced", "usenet", "stale_derived"]
    )

    conn = read_only_store(STORE)
    try:
        ledger: dict[str, set[str]] = defaultdict(set)
        for source_name, file_name in conn.execute(
            "SELECT source_name, file_name FROM ingested_file"
        ).fetchall():
            ledger[source_name].add(file_name)
        print(
            f"ingest ledger: {sum(len(v) for v in ledger.values()):,} files "
            f"over {len(ledger):,} sources\n"
        )
        findings = {}
        if "unread" in wanted:
            findings["unread"] = check_unread(ledger, args.verbose)
        if "glob_too_narrow" in wanted:
            findings["glob_too_narrow"] = check_glob_too_narrow(ledger, args.verbose)
        if "unreferenced" in wanted:
            findings["unreferenced"] = check_unreferenced(args.verbose)
        if "usenet" in wanted:
            findings["usenet"] = check_usenet()
        if "stale_derived" in wanted:
            findings["stale_derived"] = check_stale_derived(conn)
    finally:
        conn.close()

    print("\n== summary ==")
    for name, count in findings.items():
        print(f"  {name:18} {count:>7,}")
    print(
        "\nNot a gate: unread material is a fact about the round, not a broken invariant.\n"
        "An `unread` count above zero is the cheapest yield in the project. Price it\n"
        "against the live store before ingesting, per docs/discovery.md."
    )


if __name__ == "__main__":
    main()
