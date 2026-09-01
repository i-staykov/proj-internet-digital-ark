"""Apply the corroboration split to the Jeb Bush gubernatorial mailbox, before any ingest.

**What the artifact is.** The email Jeb Bush released himself in 2015 out of his two terms
as governor of Florida, re-uploaded to archive.org as `JebBushEmails-Text.7z`, 411,928,998
bytes, 626 born-digital text files, 2,400,944 `From:` blocks of which **505,927 are dated
inside 1996-2001** (1996 26, 1997 52, 1998 97, 1999 43,664, 2000 195,313, 2001 266,775).
The other 1.83M messages are 2002-2006 and this reads none of them.

**What dates one item, and it is a stamp a mail client wrote.** The unindented `Sent:` line
of each message block, `Sent:\tMonday, December 4, 2000 12:38 AM` immediately under
`From:\tGloria Rinaman <gloria@rinaman.com>`, written by the sending client into the export
rather than typed by a correspondent. That is the same basis the banked `enron_email`
carries, and the same evidence type.

**Hosts are anchored, never taken from loose prose.** `Candace Rice.To tell the truth`
becomes `rice.to` under any wide hostname pattern, and `.to` carries an English weight, so a
missing space after a full stop forges a scoring domain out of typing. Measured cost of the
wide reading: 200.8 EE and 400 pairs, 5.4%, inflating the high-weight TLDs preferentially.
`scripts/sources/mail_corpora/parse_jeb_mail.py` therefore only takes a host with an `@` in front
  of it, a scheme,
or a `www.` label, and this reads its journal.

**The split applies, and on this corpus it is not a formality.** A person typed most of
these addresses: the typo upper bound over 1,500 sampled net-new names is 56.1%, and
`%20fh@fredomhouse.org` is a real scoring row. So a name another source already dates
carries the message's `Sent:` year as `dated_directory`; a name appearing only here parks in
the candidate pool as `link_target` and earns no year.

**Rule 6: a message evidences the year it was sent and no other.** Each row carries its own
message's year, so a domain seen in 1999 and in 2001 gets both and a domain seen once gets
one.

**What this corpus is NOT worth, measured, because the hypothesis behind it was wrong.** The
claim was that inbound public mail beats outbound official mail, the correspondents being
"citizens, small businesses, schools and local associations". Reversed: `From:` pays 1,235.4
EE against 1,410.3 EE for `To:`/`Cc:`. The mechanism is that the public does not own
domains. Over 480,657 `From:` occurrences the top twelve registrable domains are 62.2% of
the traffic and nine are consumer ISPs, aol.com alone 25.37%. A citizen mailing the governor
contributes a mailbox at AOL, not a host.

Read-only against the store.

    uv run python scripts/sources/mail_corpora/split_jeb_mail.py             # report only
    uv run python scripts/sources/mail_corpora/split_jeb_mail.py --write
"""

import argparse
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ark.canonical import to_registrable  # noqa: E402
from ark.db import DEFAULT_DB_PATH, connect_read_only_patiently  # noqa: E402
from ark.english_share import weight_of  # noqa: E402
from ark.ingest import YEARS  # noqa: E402
from ark.journal import journal_writer, open_journal, write_journal_line  # noqa: E402

IN = ROOT / "data/raw/jeb_bush/jeb_bush_anchored.jsonl.gz"
OUT = ROOT / "data/raw/jeb_bush"
ARTIFACT = "https://archive.org/download/JebBushEmails/JebBushEmails-Text.7z"


def read_journal(path: Path, stats: Counter) -> dict[tuple[str, int], str]:
    """One (domain, sent year) to the locator of the first message carrying it."""
    import json

    pairs: dict[tuple[str, int], str] = {}
    years: Counter = Counter()
    with open_journal(path) as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            stats["journal_lines"] += 1
            try:
                record = json.loads(line)
            except ValueError:
                stats["unparseable_line"] += 1
                continue
            year = record.get("year")
            if year not in YEARS:
                stats["out_of_window"] += 1
                continue
            years[year] += 1
            item = record.get("item", "")
            for raw in record.get("text", "").split():
                stats["host_occurrences"] += 1
                domain = to_registrable(raw)
                if domain is None:
                    stats["uncanonical_host"] += 1
                    continue
                pairs.setdefault((domain, year), item)
    print("in-window messages by sent year:")
    for year in sorted(years):
        print(f"  {year}  {years[year]:>10,}")
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the two lanes")
    args = parser.parse_args()

    if not IN.exists():
        print(
            f"no journal at {IN}; run scripts/sources/mail_corpora/parse_jeb_mail.py "
            "over the extracted files first"
        )
        return 1

    stats: Counter = Counter()
    pairs = read_journal(IN, stats)
    for key, value in sorted(stats.items()):
        print(f"  {key:<24}{value:>12,}")
    domains = {domain for domain, _ in pairs}
    print(f"\n{len(domains):,} distinct registrable domains, {len(pairs):,} (domain, year) rows")

    conn = connect_read_only_patiently(DEFAULT_DB_PATH)
    try:
        attested = {
            row[0] for row in conn.execute("SELECT DISTINCT domain FROM domain_year").fetchall()
        }
        held = {
            (row[0], row[1])
            for row in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
    finally:
        conn.close()

    dated, candidates = [], []
    netnew_ee = Decimal(0)
    netnew_pairs = 0
    by_year: Counter = Counter()
    for (domain, year), item in sorted(pairs.items()):
        row = {
            "domain": domain,
            "year": year,
            "message_id": f"sent {year}, {item}",
            "group": "jeb_bush_email",
            "url": ARTIFACT,
        }
        if domain in attested:
            dated.append(row)
            if (domain, year) not in held:
                netnew_pairs += 1
                netnew_ee += weight_of(domain)
                by_year[year] += 1
        else:
            candidates.append(row)

    corroborated = len({d for d, _ in pairs if d in attested})
    print(f"  corroborated, so datable : {corroborated:,}  ({corroborated / len(domains):.1%})")
    print(f"  novel, so candidate only : {len(domains) - corroborated:,}")
    print(f"\ndated lane rows      : {len(dated):,}")
    print(f"candidate lane rows  : {len(candidates):,}")
    print(f"net-new post-split   : {netnew_pairs:,} pairs, {netnew_ee:,.1f} EE")
    print("net-new pairs by year: " + ", ".join(f"{y} {by_year[y]:,}" for y in sorted(by_year)))
    print("\nEE here is the split's own estimate; the ingest and `ark stats` decide.")

    if not args.write:
        print("\nreport only. Pass --write to emit the two lanes.")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    for name, batch in (("jeb_mail_dated", dated), ("jeb_mail_candidates", candidates)):
        path = OUT / f"{name}.jsonl.gz"
        with journal_writer(path) as handle:
            for row in batch:
                write_journal_line(handle, row)
        print(f"wrote {path} ({len(batch):,} rows)")
    print("\nnext:")
    for key in ("jeb_mail_dated", "jeb_mail_candidates"):
        print(f"  uv run ark ingest {key} data/raw/jeb_bush/{key}.jsonl.gz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
