"""What is on disk that nothing has read, and what the documented path would miss.

The reviewer's first priority is residual opportunity inside sources already
used: "unprocessed files, failed parses, truncated runs, unqueried candidates,
missing date partitions". This answers the file half of that in one command, with
no network and no write lock, so it can run before every collection decision.

**Every measurement starts from the store, so a file no ingest has read is invisible
to all of them.** This searches for no new source; it diffs disk against the ingest
ledger.

Four checks, each of which has caught something real:

`unread`         files a documented ingest glob matches that the ledger has never
                 read, per source. The ISC case, and the first thing to look at.
`glob_too_narrow` files the ledger holds that the documented glob does NOT match.
                 Not lost yield: a reproduction defect, because `just reproduce`
                 rebuilds a store missing them: `isc_survey/*.domains.gz`
                 silently misses `wb_nw_9607_org.gz`.
`unreferenced`   directories under data/raw/ that no ingest glob points into at
                 all. These are the "bytes nothing reads" in `docs/registers/sources.md`,
                 and one of them is a National Library of Australia title index.
`usenet`         the corpus has its own `.processed` ledger rather than rows in
                 `ingested_file`, so it needs its own three-way comparison
                 against the catalogue and the disk.

Nothing here is a gate. It reports and exits 0, because "there is unread material
on disk" is a fact about the round rather than a broken invariant, and a check
that fails the build for it would simply be turned off.

    uv run python scripts/harness/audit_residual.py
    uv run python scripts/harness/audit_residual.py --check unread --verbose
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from ark.db import connect_read_only_patiently  # noqa: E402
from ark.sources import SOURCES  # noqa: E402

STORE = ROOT / "data/ark.duckdb"
RAW = ROOT / "data/raw"
JUSTFILE = ROOT / "justfile"

# `ark ingest <key> <path-or-glob>`, ignoring a commented-out line.
INGEST_RE = re.compile(r"^\s*(?!#)\s*uv run ark ingest\s+(\S+)\s+(\S+)")

# Directories whose contents are inputs to a collector rather than to an ingest,
# or which are recorded as rejected on measurement. Naming them here keeps the
# `unreferenced` check to material that is genuinely unaccounted for; without it
# the check reports every OCR cache file and reads as noise.
ACCOUNTED = {
    "usenet": "the corpus, tracked in its own .processed ledger",
    "usenet_bulk": "deleted; DELETED.tsv lists the archives and their URLs",
    "usenet_probe": "spent probe, superseded by the whole-corpus run",
    "usenet_probe5": "spent probe, duplicate bytes",
    "rtfm": "extracted FAQ tree, read by scripts/sources/usenet/split_rtfm_faqs.py",
    "maillists": "harvested month files, read by "
    "scripts/sources/mail_corpora/collect_mailing_lists.py",
    "texts": "trade-press OCR cache, read by scripts/sources/trade_press/reextract_trade_press.py",
    "webbase": "rejected on measurement: 99.99% already held",
    # The largest block on disk, and INPUT: `ark ingest-hostnames` reads these capture rows
    # and `cdx_suffix_convert.py` turns their exact-host registrables into `cdx_snapshot`
    # journals under `data/raw/cdx/`. `unreferenced` cannot tell "raw input" from "bytes
    # nothing reads", which is why this needs saying here rather than being rediscovered.
    "cdx_suffix": "raw sweep input; converted incrementally, state in "
    "data/raw/cdx/cdx_suffix_convert.state.tsv",
    # Deliberately unreachable, and it must stay that way until the owner rules. Nominet's
    # RDAP terms prohibit "extracting, copying and/or using or re-using ... all or part
    # ... of the contents of the RDAP database", which reaches USE and not only
    # collection, so these three journals are held where no ingest or bank glob matches
    # them.
    "rdap_hold_uk": "quarantined pending the Nominet extraction-clause decision",
    # 511 MB that is three byte-for-byte duplicates: all three
    # names exist in `data/raw/usenet_new/` at identical sizes and all three are in
    # that pool's `.processed` ledger, so the announce, address, header and bare
    # extractors have each already read them.
    "usenet_msft": "3 byte-identical duplicates of processed data/raw/usenet_new files",
    "nypw": "rejected on measurement: 53 net-new domains over 6.28M lines",
    "100hot": "worked in phase 1 to 3,453 hostnames; master-evidence route declined",
    "wwwvl": "page cache for the Virtual Library expansion rounds",
    "lang": "retired English-verification engine, removed 2026-08-23",
    "yahoo96": "rejected on measurement: 7.73 EE over 55 requests",
    # read by a script rather than by an ingest glob, so `unreferenced` cannot
    # clear it on its own: seeds candidates, evidences nothing, has no date column
    "pandora-titles": "seed-only, read by scripts/sources/directories/seed_pandora_titles.py",
    "pandora": "byte-identical duplicate of pandora-titles/pandora-titles.csv",
    # 982 MB that looks like the largest opportunity on disk and is not one:
    # `enron.tar.gz` is the input
    # scripts/sources/mail_corpora/collect_enron.py
    # names directly, `mlists` and `attrition` fed ingested sources, and
    # `hathitrust_ef` is the HathiTrust route already closed on measurement inside the
    # printed-directory verdict. Measured at 74 net-new pairs and 49.4 EE after the
    # split, under the bar.
    "source_probe_260806": "collector inputs (enron, mlists, attrition) plus the "
    "hathitrust_ef route closed on measurement, see docs/registers/sources.md",
    "probes": "cached pages and journals from scripts/pricing/probe_source.py, read by "
    "scripts/pricing/price_items.py; a probe has no ingest spec by design",
    "udrp": "the dockets collector's own input and journal, ingested as "
    "udrp_proceedings; udrp_hosts.txt is the seed list built beside it",
    "gapfill_candidates.txt": "target list",
    "gapfill_sample.txt": "target list",
    "usenet_catalog.json": "the group catalogue, read by the Usenet collectors",
    "checksums.sha256": "the pinned source manifest",
}


def read_only_store(path: Path, patience_s: int = 900) -> duckdb.DuckDBPyConnection:
    """Open for reading through `ark.db`, which caps memory and waits out a writer.

    Patience is 15 minutes because `ark seed` over tens of thousands of names holds the
    lock for more than twenty. A writer that outlasts even this gets a one-line
    explanation naming its PID, because a traceback out of a read-only reporting tool
    reads as a defect in the tool.
    """
    try:
        return connect_read_only_patiently(path, patience_s=patience_s)
    except duckdb.Error as exc:
        message = str(exc)
        if "Conflicting lock" not in message:
            raise
        pid = re.search(r"PID (\d+)", message)
        who = f" (PID {pid.group(1)})" if pid else ""
        raise SystemExit(
            f"the store is being written{who} and still was after "
            f"{patience_s}s. Nothing is wrong: this reads the store, so it "
            f"waits for the writer. Re-run when the ingest or seed finishes."
        ) from None


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
            # A journal spec not in SOURCES: the ledger cannot be joined for it,
            # so it is out of scope rather than silently reported as clean.
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
    """Ledgered files the reproduction path cannot reach, and why.

    Not lost yield. It means `just reproduce` rebuilds a store without them, so
    the reproduction path claims more than it delivers.

    **The two causes need separating, because they have different fixes and the
    lumped total misleads.** As one number it conflates two real things of very
    different size. Widening a glob fixes one of them; nothing fixes the other, and
    saying so is the honest claim.

    `narrow`  the file is on disk and no documented glob matches its name.
    `absent`  the file is not on disk at all, so no glob can reach it and the
              replay has to come from whatever the journal was derived from.
    """
    print("\n== glob_too_narrow: ingested, but the reproduction path cannot reach it ==")
    by_source: dict[str, set[str]] = defaultdict(set)
    for _key, source_name, pattern in ingest_globs():
        by_source[source_name] |= {p.name for p in ROOT.glob(pattern)}
    # `data/raw` is not the only place a journal lands: the promotion tranches are
    # written under `data/staging/`, and scanning only RAW reported all 41 of them as
    # "absent from disk" when every one was present. An audit that mislabels its own
    # finding is worse than one that misses it.
    on_disk = {p.name for p in RAW.rglob("*") if p.is_file()}
    staging = ROOT / "data/staging"
    if staging.is_dir():
        on_disk |= {p.name for p in staging.rglob("*") if p.is_file()}
    total, narrow_total, absent_total = 0, 0, 0
    for source_name, reachable in sorted(by_source.items()):
        held = ledger.get(source_name, set())
        missed = sorted(held - reachable)
        if not missed:
            continue
        narrow = [n for n in missed if n in on_disk]
        absent = [n for n in missed if n not in on_disk]
        total += len(missed)
        narrow_total += len(narrow)
        absent_total += len(absent)
        print(
            f"  {source_name:24} {len(missed):>6,} of {len(held):>6,} unreachable"
            f"   narrow {len(narrow):>5,}  absent from disk {len(absent):>5,}"
        )
        for label, names in (("narrow", narrow), ("absent", absent)):
            shown = names if verbose else names[:2]
            for name in shown:
                print(f"      {label}: {name}")
            if not verbose and len(names) > 2:
                print(f"      {label}: ... and {len(names) - 2:,} more, pass --verbose")
    if not total:
        print("  nothing: every ledgered file is reachable from a documented glob")
    else:
        print(
            f"  {narrow_total:,} fixable by widening a glob; {absent_total:,} are gone from disk "
            f"and can only be replayed from what produced them"
        )
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
            # `is_file()` follows a symlink, and the batch runners stage each batch as
            # a directory of links into the pools so no bytes move. Counted naively,
            # `usenet_bare_probe` read as 3,668,938,578 bytes of "downloaded bytes with
            # no parser" while holding 400 links and no bytes. Skip links.
            real = [p for p in entry.rglob("*") if p.is_file() and not p.is_symlink()]
            nbytes = sum(p.stat().st_size for p in real)
            nfiles = len(real)
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="append",
        choices=["unread", "glob_too_narrow", "unreferenced", "usenet"],
        help="run only these checks (repeatable). Default: all four.",
    )
    ap.add_argument("--verbose", action="store_true", help="list every file, not the first four")
    args = ap.parse_args()
    wanted = set(args.check or ["unread", "glob_too_narrow", "unreferenced", "usenet"])

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
    finally:
        conn.close()

    print("\n== summary ==")
    for name, count in findings.items():
        print(f"  {name:18} {count:>7,}")
    print(
        "\nNot a gate: unread material is a fact about the round, not a broken invariant.\n"
        "An `unread` count above zero is the cheapest yield in the project. Price it\n"
        "against the live store before ingesting."
    )


if __name__ == "__main__":
    main()
