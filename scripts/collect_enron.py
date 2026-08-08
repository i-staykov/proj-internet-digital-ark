"""Dated domain mentions in the Enron email corpus.

The FERC-released Enron corpus is roughly 517,000 messages from 1999-2002, each
carrying a `Date:` header. A message dated 2000 naming `foo.com` attests `foo.com`
for 2000 in exactly the sense a dated Usenet post does: the date is intrinsic to
the artifact rather than recovered from a crawl.

Its population is the useful part and also its limit. These are one company's
business counterparties, so the domains skew large and American and are
disproportionately names the baseline already holds. Measured on the first 80,000
messages: 71,024 in window, 10,671 distinct (domain, year), 3,367 net-new, of
which 1,412 corroborated and worth 892.3 equivalent-English.

Lineage is its own: corporate email is independent of every crawl, of Usenet and
of the registries, so a pair it confirms alongside one of those is genuine
cross-lineage corroboration.

Takes the corroboration split like every free-text source: the addresses and URLs
here were typed by people. Reads a local tarball, no network.

    uv run python scripts/collect_enron.py --write
"""

import argparse
import re
import sys
import tarfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from ark.canonical import to_registrable  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402
from ark.usenet import INFRASTRUCTURE, message_year  # noqa: E402

SOURCE = ROOT / "data/raw/source_probe_260806/enron.tar.gz"
OUT_DIR = ROOT / "data/raw/enron"
YEARS = range(1996, 2002)

_DATE = re.compile(r"(?mi)^Date:[ \t]*(.+)")
# Anchored the same way as the Usenet address work: a local part, an `@`, and a
# host ending in a TLD the metric rewards. A generic dot rule over mail bodies
# fabricates domains out of sentence punctuation.
_ADDR = re.compile(
    r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.(?:com|net|org|edu|gov|uk|au|ca|de|fr|nl|jp))\b",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://([A-Za-z0-9.-]+)", re.IGNORECASE)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    stats: Counter = Counter()
    pairs: dict[tuple[str, int], str] = {}
    started = time.time()
    with tarfile.open(SOURCE, "r:gz") as tf:
        for member in tf:
            if not member.isfile():
                continue
            stats["files"] += 1
            if args.limit and stats["files"] > args.limit:
                break
            try:
                body = tf.extractfile(member).read().decode("latin-1", "replace")
            except Exception:  # noqa: BLE001
                stats["unreadable"] += 1
                continue
            header = _DATE.search(body[:2000])
            if not header:
                stats["undated"] += 1
                continue
            year = message_year(header.group(1).strip())
            if year not in YEARS:
                stats["out_of_window"] += 1
                continue
            stats["in_window"] += 1
            for pattern in (_ADDR, _URL):
                for host in pattern.findall(body):
                    domain = to_registrable(host)
                    if domain and domain not in INFRASTRUCTURE:
                        pairs.setdefault((domain, year), member.name)

    print(f"read {stats['files']:,} messages in {time.time() - started:.0f}s: {dict(stats)}")
    print(f"distinct in-window (domain, year): {len(pairs):,}")

    conn = duckdb.connect(str(ROOT / "data/ark.duckdb"), read_only=True)
    try:
        attested = {
            r[0] for r in conn.execute("SELECT DISTINCT domain FROM domain_year").fetchall()
        }
        held = {
            (r[0], r[1])
            for r in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
    finally:
        conn.close()

    dated, candidates = [], []
    fresh = 0
    for (domain, year), origin in sorted(pairs.items()):
        record = {
            "domain": domain,
            "year": year,
            "message_id": origin,
            "group": "enron",
            "url": "https://www.cs.cmu.edu/~enron/",
        }
        if domain in attested:
            dated.append(record)
            fresh += (domain, year) not in held
        else:
            candidates.append(record)
    print(f"  corroborated -> dated_directory : {len(dated):,}, of which {fresh:,} net-new")
    print(f"  seen only here -> candidates    : {len(candidates):,}")
    if not args.write:
        print("\ndry run; pass --write to create both journals")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, batch in (("enron_dated", dated), ("enron_candidates", candidates)):
        path = OUT_DIR / f"{name}.jsonl.gz"
        with journal_writer(path) as fh:
            for record in batch:
                write_journal_line(fh, record)
        print(f"wrote {path} ({len(batch):,} records)")


if __name__ == "__main__":
    main()
