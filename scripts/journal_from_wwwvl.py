"""Turn the on-disk WWW Virtual Library captures into a standard run journal.

These captures were harvested out of band, during a source survey, rather than by
`ark download`: 2,709 Wayback snapshots of Virtual Library subject pages sit under
`data/raw/wwwvl/` with their year, capture timestamp and original URL recorded in
`l2pages.tsv`. Re-fetching them to get a journal would cost hours and add nothing,
since the bytes are already here and checksummed in `SHA256SUMS`.

So this writes the journal instead of the collector, in exactly the format
`ark download` writes, and everything after that is the normal path:
`ark ingest expansion_directory <journal>` parses it with the same parser, hashes
it into the same file ledger, and applies the same evidence rules. Nothing about
this source gets a private route into the store.

Link extraction uses `ark.expand.outbound_domains`, the same function the live
collector uses, so a domain found here and a domain found by `ark download`
cannot disagree about what a page links to.

Level 2 only, on purpose. The Level 1 pages under `pages.tsv` are mostly the
frozen `info.cern.ch` copy of the 1993 catalogue, whose capture date says when
the Internet Archive fetched an old file, not that the listed sites were live
that year. That is exactly the inference the evidence wall exists to prevent.

Two journals come out, not one, because a listing is a claim by the linking page
and HTML carries typos: this harvest contains `gov.edu` and `gintysuooly.com`,
and a parallel review of the same route measured roughly 40% of never-before-seen
names as transcription errors. So a domain some independent source already
attests is written as curated (its capture date evidences the year under IV.i),
while a name appearing here and nowhere else is written as an ordinary outbound
link, which routes it to the candidate pool to earn its own evidence. The split
is therefore a statement about corroboration, not about the page.

Usage:
    uv run python scripts/journal_from_wwwvl.py            # dry run, prints counts
    uv run python scripts/journal_from_wwwvl.py --write    # write both journals
"""

import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ark.expand import outbound_domains  # noqa: E402
from ark.ingest import YEARS  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402

WWWVL_DIR = Path("data/raw/wwwvl")
INDEX = WWWVL_DIR / "l2pages.tsv"
JOURNAL_DIR = Path("data/raw/expand/wwwvl")
CURATED_JOURNAL = JOURNAL_DIR / "expand_wwwvl_corroborated.jsonl.gz"
UNVERIFIED_JOURNAL = JOURNAL_DIR / "expand_wwwvl_unverified.jsonl.gz"
STORE = Path("data/ark.duckdb")

# the Virtual Library's own infrastructure, not sites it catalogues
SELF_HOSTS = frozenset(
    {"w3.org", "vlib.org", "cern.ch", "archive.org", "openlibrary.org", "savethearchive.com"}
)


def capture_path(year: str, stamp: str, url: str) -> Path:
    digest = hashlib.sha1(url.encode()).hexdigest()[:16]  # noqa: S324 (a filename, not a signature)
    return WWWVL_DIR / "level2" / year / f"{stamp}_{digest}.html"


def is_wayback_error_page(raw: bytes) -> bool:
    """Wayback serves an HTML error page with HTTP 200 when a capture is missing."""
    return b"<title>wayback machine</title>" in raw[:4000].lower()


def build_records(stats: Counter) -> list[dict]:
    records = []
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        year, stamp, _size, url = line.split("\t")
        stats["indexed"] += 1
        if int(year) not in YEARS:
            stats["out_of_window"] += 1
            continue
        path = capture_path(year, stamp, url)
        if not path.exists():
            stats["missing_file"] += 1
            continue
        raw = path.read_bytes()
        if is_wayback_error_page(raw):
            stats["wayback_error_page"] += 1
            continue
        domains = [
            d
            for d in outbound_domains(raw.decode("latin-1", "replace"), url)
            if d not in SELF_HOSTS
        ]
        stats["pages"] += 1
        stats["domains"] += len(domains)
        records.append(
            {
                "domain": url,
                "page_url": url,
                "status": 200,
                "timestamp": stamp,
                "year": int(year),
                "curated": True,
                "domains": domains,
            }
        )
    return records


def known_domains() -> set[str]:
    """Every domain the store already holds from some other source."""
    import duckdb

    conn = duckdb.connect(str(STORE), read_only=True)
    try:
        return {row[0] for row in conn.execute("SELECT domain FROM domain").fetchall()}
    finally:
        conn.close()


def split_by_corroboration(records: list[dict], known: set[str]) -> tuple[list[dict], list[dict]]:
    """Split each page's links into the corroborated half and the rest."""
    curated, unverified = [], []
    for record in records:
        seen = [d for d in record["domains"] if d in known]
        unseen = [d for d in record["domains"] if d not in known]
        if seen:
            curated.append({**record, "domains": seen, "curated": True})
        if unseen:
            unverified.append({**record, "domains": unseen, "curated": False})
    return curated, unverified


def _write(path: Path, records: list[dict]) -> None:
    with journal_writer(path) as fh:
        for record in records:
            write_journal_line(fh, record)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write both journal files.")
    args = parser.parse_args()

    stats: Counter = Counter()
    records = build_records(stats)
    known = known_domains()
    curated, unverified = split_by_corroboration(records, known)
    corroborated = {d for r in curated for d in r["domains"]}
    unseen = {d for r in unverified for d in r["domains"]}
    print(f"{dict(stats)}")
    print(f"corroborated domains: {len(corroborated):,} -> curated, master-eligible")
    print(f"uncorroborated domains: {len(unseen):,} -> candidate pool only")

    if not args.write:
        print(f"dry run; pass --write to create {CURATED_JOURNAL} and {UNVERIFIED_JOURNAL}")
        return
    _write(CURATED_JOURNAL, curated)
    _write(UNVERIFIED_JOURNAL, unverified)
    print(f"wrote {len(curated):,} + {len(unverified):,} records")
    print(
        f"next: uv run ark ingest expansion_directory {CURATED_JOURNAL} --round 3\n"
        f"      uv run ark ingest expansion_links {UNVERIFIED_JOURNAL} --round 3"
    )


if __name__ == "__main__":
    main()
