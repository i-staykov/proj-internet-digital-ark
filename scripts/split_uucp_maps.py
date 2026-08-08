"""Read the UUCP map postings the Usenet parser skipped, and split them by evidence class.

Three journals rather than two, because this source carries three different
claims and flattening them would either overstate the weak one or discard the
strong ones:

    registry listing  a `.CA` registry dump regenerated at posting time lists the
                      name, so the name existed then          -> artifact_listing
    registry creation the registrar's own `approved:` line     -> whois_creation
    uncorroborated    a hand-maintained map entry whose own last-touch date is
                      typically years older than the posting   -> link_target

See `ark.uucp` for the measurements behind that gate. Read-only against the store.

    uv run python scripts/split_uucp_maps.py --write
"""

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from ark.journal import journal_writer, write_journal_line  # noqa: E402
from ark.uucp import records_in_archive  # noqa: E402

STORE = ROOT / "data/ark.duckdb"
USENET = ROOT / "data/raw/usenet"
OUT_DIR = ROOT / "data/raw/uucp"
ARCHIVES = ("comp.mail.maps.mbox.zip",)


def open_store(attempts: int = 60, pause: float = 15.0) -> duckdb.DuckDBPyConnection:
    for attempt in range(attempts):
        try:
            return duckdb.connect(str(STORE), read_only=True)
        except duckdb.IOException:
            if attempt == attempts - 1:
                raise
            time.sleep(pause)
    raise AssertionError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--archives", nargs="*", default=list(ARCHIVES))
    args = ap.parse_args()

    stats: Counter = Counter()
    by_basis: dict[str, dict[tuple[str, int], str]] = {
        "registry_listing": {},
        "registry_creation": {},
        "uncorroborated": {},
    }
    for name in args.archives:
        path = USENET / name
        if not path.is_file():
            print(f"  missing, skipped: {path}")
            continue
        print(f"reading {path}")
        for record in records_in_archive(path):
            stats[record.basis] += 1
            by_basis[record.basis].setdefault((record.domain, record.year), record.identifier)

    conn = open_store()
    try:
        held = {
            (r[0], r[1])
            for r in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
    finally:
        conn.close()

    print("\nrows read per evidence class:", dict(stats))
    for basis, pairs in by_basis.items():
        fresh = sum(1 for key in pairs if key not in held)
        print(f"  {basis:<18} {len(pairs):>8,} distinct pairs, {fresh:>8,} not yet held")

    if not args.write:
        print("\ndry run; pass --write to create the journals")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for basis, filename in (
        ("registry_listing", "uucp_listing.jsonl.gz"),
        ("registry_creation", "uucp_creation.jsonl.gz"),
        ("uncorroborated", "uucp_mentions.jsonl.gz"),
    ):
        path = OUT_DIR / filename
        with journal_writer(path) as fh:
            for (domain, year), identifier in sorted(by_basis[basis].items()):
                write_journal_line(
                    fh,
                    {
                        "domain": domain,
                        "year": year,
                        "message_id": identifier,
                        "group": "comp.mail.maps",
                        "url": "https://archive.org/details/usenet-comp",
                    },
                )
        print(f"wrote {path} ({len(by_basis[basis]):,} records)")


if __name__ == "__main__":
    main()
