"""Split the Tucows catalogue into a dated-evidence half and a candidate half.

Tucows is a better-behaved source than Usenet: the vendor URL is a single
structured metadata field rather than free text typed into a message, so it does
not carry the same transcription risk, and its dating validates well. Measured
against evidence the store already holds, the Tucows release year is exactly
right 78.7% of the time and within one year 95.4%, against 51.1% and 88.7% for
the Usenet post date.

It is still split, and the reason is worth stating because the temptation not to
was real. The catalogue was donated in 2004, so a `creator` URL may record where
a vendor lived then rather than at release. The 78.7% agreement is measured only
on domains the store already knows, which are the long-lived, well-covered ones.
Drift would show precisely in the names never seen before, which are exactly
the 775 that would otherwise become net-new domains on this source's word alone.

So the same rule as Usenet: a domain another source already places in an annual
file carries the release date as `dated_directory`; a name appearing only here
goes to the candidate pool and earns its year from a capture.

    uv run python scripts/split_tucows.py --write
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.canonical import to_registrable  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402

STORE = Path("data/ark.duckdb")
SOURCE = Path("data/raw/tucows/tucows_1996_2001.json")
OUT_DIR = Path("data/raw/tucows")
YEARS = range(1996, 2002)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    items = json.loads(SOURCE.read_text(encoding="utf-8"))
    # (domain, year) -> identifier, keeping the first release that named it
    seen: dict[tuple[str, int], str] = {}
    for item in items:
        creator = item.get("creator")
        if not creator:
            continue
        if isinstance(creator, list):
            creator = creator[0] if creator else ""
        year_text = (item.get("date") or "")[:4]
        if not year_text.isdigit() or int(year_text) not in YEARS:
            continue
        domain = to_registrable(str(creator))
        if not domain:
            continue
        seen.setdefault((domain, int(year_text)), item.get("identifier", ""))

    conn = duckdb.connect(str(STORE), read_only=True)
    try:
        attested = {
            r[0] for r in conn.execute("SELECT DISTINCT domain FROM domain_year").fetchall()
        }
    finally:
        conn.close()

    dated, candidates = [], []
    for (domain, year), identifier in sorted(seen.items()):
        record = {
            "domain": domain,
            "year": year,
            "message_id": identifier,
            "group": "tucows",
        }
        (dated if domain in attested else candidates).append(record)

    print(f"in-window pairs: {len(seen):,}")
    print(f"  corroborated (another source places the domain in an annual file): {len(dated):,}")
    print(
        f"  uncorroborated (candidate pool only)                             : {len(candidates):,}"
    )
    if not args.write:
        print("dry run; pass --write to create both journals")
        return

    for path, batch in (
        (OUT_DIR / "tucows_dated.jsonl.gz", dated),
        (OUT_DIR / "tucows_candidates.jsonl.gz", candidates),
    ):
        with journal_writer(path) as fh:
            for record in batch:
                write_journal_line(fh, record)
        print(f"wrote {path} ({len(batch):,} records)")


if __name__ == "__main__":
    main()
