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
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.journal import journal_writer, write_journal_line  # noqa: E402
from ark.usenet import is_moderated_announce, parse_usenet  # noqa: E402

STORE = Path("data/ark.duckdb")
OUT_DIR = Path("data/raw/usenet")
DATED_JOURNAL = OUT_DIR / "usenet_dated.jsonl.gz"
CANDIDATE_JOURNAL = OUT_DIR / "usenet_candidates.jsonl.gz"


def group_of(path: Path) -> str:
    """The newsgroup name, which is the archive's filename without suffixes."""
    return path.name.replace(".mbox.zip", "").replace(".mbox", "")


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
    args = parser.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""
    dated_journal = OUT_DIR / f"usenet_dated{suffix}.jsonl.gz"
    candidate_journal = OUT_DIR / f"usenet_candidates{suffix}.jsonl.gz"

    stats: Counter = Counter()
    # (domain, year) -> (message_id, group), keeping the first post that named it
    seen: dict[tuple[str, int], tuple[str, str]] = {}
    for path in args.archives:
        group = group_of(path)
        moderated = is_moderated_announce(group)
        stats["moderated_groups" if moderated else "other_groups"] += 1
        for record in parse_usenet(path, stats):
            key = (record.raw, record.year)
            if key not in seen:
                seen[key] = (record.evidence_value, group)

    conn = duckdb.connect(str(STORE), read_only=True)
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
