"""Split Usenet archives into a dated-evidence half and a candidate half.

The post date is good year evidence and the URL beside it is human-typed. Those
two facts pull in opposite directions, and averaging them would be the worst of
both: either invented domains reach an annual file, or a large body of genuine
dated evidence is thrown away.

So the same split `expand.py` applies to archived directory pages applies here.
A domain **another source already places in an annual file** is real, and the
only open question is the year, which the post answers with an auditable
Message-ID. That half is written as `dated_directory`. A name appearing only in
Usenet has neither its existence nor its year independently attested, and 35.4%
of such names in this corpus are within a single edit of a name the store
already holds, so that half is written as `link_target` and routed to the
candidate pool to earn its own evidence.

The test is deliberately "appears in `domain_year`", not "appears in `domain`".
The latter includes the candidate pool, so a typo that some earlier round also
recorded as a candidate would corroborate itself.

    uv run python scripts/split_usenet.py data/raw/usenet/*.zip --write
"""

import argparse
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.journal import journal_writer, write_journal_line  # noqa: E402
from ark.usenet import is_moderated_announce, parse_usenet  # noqa: E402

STORE = Path("data/ark.duckdb")
OUT_DIR = Path("data/raw/usenet")
DATED_JOURNAL = OUT_DIR / "usenet_dated.jsonl.gz"
CANDIDATE_JOURNAL = OUT_DIR / "usenet_candidates.jsonl.gz"


def _open_store(attempts: int = 60, pause: float = 15.0) -> duckdb.DuckDBPyConnection:
    """Open the store read-only, waiting out a writer rather than dying on one.

    The store query happens AFTER every archive has been parsed, which over the
    full corpus is hours of work, and `maintain.sh` holds a write lock
    whenever it is mid-ingest. Failing here throws all of that away, which has
    already happened once tonight to a measurement script.
    """
    for attempt in range(attempts):
        try:
            return duckdb.connect(str(STORE), read_only=True)
        except duckdb.IOException:
            if attempt == attempts - 1:
                raise
            print(f"store is locked, waiting ({attempt + 1}/{attempts})", flush=True)
            time.sleep(pause)
    raise RuntimeError("unreachable")


def group_of(path: Path) -> str:
    """The newsgroup name, which is the archive's filename without suffixes."""
    return path.name.replace(".mbox.zip", "").replace(".mbox", "")


def parse_one(path: Path) -> tuple[str, bool, list[tuple[str, int, str]], dict]:
    """Parse a single archive. Module-level and picklable so it can run in a pool.

    Returns the records in the order the archive yielded them, which is what lets
    the parent merge results in path order and reproduce the serial result exactly.

    **One archive may not take the batch down with it.** A batch is split in a
    single call and its archives are only marked processed if that call succeeds,
    so an exception here unmarks every archive in the batch and the maintain loop
    then re-offers exactly the same batch on its next pass. On 6 August one message
    with an RFC 2047 encoded Date header did that 145 times between 23:47 and 05:50
    and the night's second half produced nothing. The parser bug was one line; the
    all-or-nothing shape was the expensive part, so failure is now per archive and
    is counted rather than raised.
    """
    stats: Counter = Counter()
    group = group_of(path)
    try:
        records = [(r.raw, r.year, r.evidence_value) for r in parse_usenet(path, stats)]
    except Exception as exc:  # noqa: BLE001 - one bad archive must not end the batch
        stats["archives_failed"] += 1
        print(f"  skip {path.name}: {type(exc).__name__}: {exc}", flush=True)
        return group, is_moderated_announce(group), [], dict(stats)
    return group, is_moderated_announce(group), records, dict(stats)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--write", action="store_true", help="Write both journals.")
    parser.add_argument(
        "--tag",
        default="",
        help="Suffix for the journal names. Needed for a later batch: the file ledger keys on "
        "content, so rewriting a journal that is already ingested is refused as a hash mismatch.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR,
        help="Where to write the journals. Point this at a staging folder when the output is "
        "meant to be filtered before it is ingested: `maintain.sh` globs "
        "`data/raw/usenet/usenet_{dated,candidates}_*.jsonl.gz` every cycle and ingests what "
        "it finds, so a journal written there is in the store within minutes whether or not "
        "anyone has looked at it.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parse this many archives at once. Parsing is CPU-bound regex over message "
        "bodies and the machine has 14 cores, so a bulk run is many times faster in a "
        "pool. Results are merged in archive order, so the output is identical to a "
        "serial run whatever this is set to.",
    )
    args = parser.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    dated_journal = out_dir / f"usenet_dated{suffix}.jsonl.gz"
    candidate_journal = out_dir / f"usenet_candidates{suffix}.jsonl.gz"

    stats: Counter = Counter()
    # (domain, year) -> (message_id, group), keeping the first post that named it
    seen: dict[tuple[str, int], tuple[str, str]] = {}
    total = len(args.archives)
    started = time.monotonic()

    def absorb(index: int, group: str, moderated: bool, records: list, got: dict) -> None:
        stats["moderated_groups" if moderated else "other_groups"] += 1
        for key, value in got.items():
            stats[key] += value
        for raw, year, evidence_value in records:
            key = (raw, year)
            if key not in seen:
                seen[key] = (evidence_value, group)
        # a full-corpus split is hours of work; silence for that long is
        # indistinguishable from a hang
        if total > 50 and (index % 100 == 0 or index == total):
            elapsed = time.monotonic() - started
            rate = index / elapsed if elapsed else 0
            left = (total - index) / rate / 60 if rate else 0
            print(
                f"  {index:,}/{total:,} archives, {len(seen):,} pairs, "
                f"{elapsed / 60:.0f} min elapsed, ~{left:.0f} min left",
                flush=True,
            )

    if args.workers > 1:
        # chunksize 1 keeps a single huge archive from stalling a whole chunk while
        # other workers idle; the archives differ in size by four orders of magnitude
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for index, (group, moderated, records, got) in enumerate(
                pool.map(parse_one, args.archives, chunksize=1), 1
            ):
                absorb(index, group, moderated, records, got)
    else:
        for index, path in enumerate(args.archives, 1):
            absorb(index, *parse_one(path))

    conn = _open_store()
    try:
        attested = {
            r[0] for r in conn.execute("SELECT DISTINCT domain FROM domain_year").fetchall()
        }
    finally:
        conn.close()

    dated, candidates = [], []
    from_moderated = 0
    for (domain, year), (message_id, group) in sorted(seen.items()):
        record = {
            "domain": domain,
            "year": year,
            "message_id": message_id,
            "group": group,
        }
        if domain in attested:
            dated.append(record)
            if is_moderated_announce(group):
                from_moderated += 1
        else:
            candidates.append(record)

    print(f"parse stats: {dict(stats)}")
    print(f"extracted pairs: {len(seen):,}")
    print(f"  corroborated (another source places the domain in an annual file): {len(dated):,}")
    print(
        f"  uncorroborated (candidate pool only)                             : {len(candidates):,}"
    )
    # Reported, not enforced: admission is decided by corroboration alone. A
    # reviewer who wants only moderated announcements can filter on the group
    # name, which every evidence row carries.
    other = len(dated) - from_moderated
    print(
        f"  of the corroborated half, {from_moderated:,} come from moderated announcement "
        f"groups and {other:,} from other groups"
    )
    if not args.write:
        print("dry run; pass --write to create both journals")
        return

    for path, batch in ((dated_journal, dated), (candidate_journal, candidates)):
        with journal_writer(path) as fh:
            for record in batch:
                write_journal_line(fh, record)
        print(f"wrote {path} ({len(batch):,} records)")
    print(
        f"next: uv run ark ingest usenet_dated {dated_journal}\n"
        f"      uv run ark ingest usenet_candidates {candidate_journal}"
    )


if __name__ == "__main__":
    main()
