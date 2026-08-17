"""Re-file mentions the corroboration split now admits, as dated journals.

**Nothing here is a new rule.** A domain typed in a dated message is admitted for
that year only if some other source already places that domain in an annual file.
Names that failed that test when they were first read have since been dated by the
CDX and RDAP engines, so the same unchanged rule, applied to a store that has grown,
admits them now. `diff_usenet_resplit.py` has called this category `PROMOTED` since
2026-08-06, when it was 4,154 pairs.

**It is a re-file rather than a re-parse.** Each mention source has a dated sibling
that shares the *same parser and the same journal format*, differing only in the
`SourceSpec` it is ingested under: `usenet_announce` / `dated_directory`, which is
master and already approved, against `usenet_mention` / `link_target`, which is
candidate-only. So the 411 GB is never touched. Every field of the journal line is
reconstructed from the evidence row, since the loader stores `evidence_value` as
`"{group} {message_id}"` and keeps the URL beside it.

**Three filters, and the last two are the ones that matter.**

  corroborated  the domain is placed in an annual file by a source that is neither
                the Usenet corpus itself, nor the baseline. Without that exclusion
                the corpus corroborates itself.

  not already   the pair is not in `domain_year` and carries no baseline evidence,
                so nothing here can inflate the net-new figure with rows we hold.

  not contra-   the registry does not say the domain was created AFTER the year the
  dicted        message claims. Measured 2026-08-15: 35.0% of the raw promotion set
                fails this against 16.5% of the Usenet pairs the store has already
                accepted, so the promotion population was twice as contradicted as
                the accepted one until this filter was added. Registry dates read
                late for a re-registered name, which inflates both figures; the
                comparison is what justifies the filter, not the absolute level.

**What is deliberately NOT promotable, because it was nearly promoted by mistake.**
`ukwa_link_target` has no dated sibling of this shape. Its only relative is
`ukwa_link_source`, which is `link_source` and dates the page *doing* the linking,
never the page linked *to*. Promoting a link-graph edge onto its target is precisely
what the `link_target` class exists to forbid, and corroboration cannot rescue it:
the split answers "is this domain real" and never "does this edge date its target".
`uucp_map_mention` and `page_expansion` fail for the same reason. Counting them
overstated the tranche by 3,805 pairs.

Read-only. Writes journals and never ingests, because whether to bank this is a
judgement about the corpus rather than a mechanical step, and the ingest command is
printed rather than run.

    uv run python scripts/build_promotion_journals.py --tag 20260816
    uv run python scripts/build_promotion_journals.py --tag 20260816 --write
"""

import argparse
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ark.db import connect_read_only_patiently  # noqa: E402
from ark.english_share import weight_of  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402
from ark.stats import BASELINE_TYPE  # noqa: E402

STORE = Path("data/ark.duckdb")
OUT_DIR = Path("data/staging/promotion")

# mention source -> the `ark ingest` key that files the same lines as master.
# Verified against `ark.sources.SOURCES` rather than assumed: both members of each
# pair use `_parse_usenet_journal`, so the journal format is identical and only the
# source name and evidence type differ.
PROMOTION = {
    "usenet_mention": "usenet_dated",
    "usenet_address_mention": "usenet_addr_dated",
    "usenet_bare_mention": "usenet_bare_dated",
    "enron_email_mention": "enron_dated",
    "maillist_archive_mention": "maillist_dated",
    "rtfm_faq_mention": "rtfm_dated",
    "trade_press_mention": "tradepress_dated",
    "tucows_mention": "tucows_dated",
}

_SELECT = """
WITH mention AS (
  SELECT e.domain, e.evidence_year AS y, e.evidence_value AS val, e.evidence_url AS url
  FROM evidence e JOIN source s ON s.source_id = e.source_id
  WHERE e.evidence_type = 'link_target'
    AND e.evidence_year BETWEEN 1996 AND 2001
    AND s.name = ?
),
corroborated AS (
  SELECT DISTINCT dy.domain FROM domain_year dy
  JOIN evidence e2 ON e2.evidence_id = dy.evidence_id
  JOIN source s2 ON s2.source_id = e2.source_id
  WHERE e2.evidence_type NOT IN ('link_target', '{baseline}')
    AND s2.name NOT LIKE 'usenet%' AND s2.name <> 'prior_task'
),
created AS (
  SELECT domain, min(evidence_year) AS first_year FROM evidence
  WHERE evidence_type = 'whois_creation' AND evidence_year IS NOT NULL GROUP BY 1
)
SELECT DISTINCT m.domain, m.y, m.val, m.url
FROM mention m LEFT JOIN created c ON c.domain = m.domain
WHERE m.domain IN (SELECT domain FROM corroborated)
  AND NOT EXISTS (
    SELECT 1 FROM domain_year dy WHERE dy.domain = m.domain AND dy.assigned_year = m.y)
  AND NOT EXISTS (
    SELECT 1 FROM evidence b WHERE b.domain = m.domain AND b.evidence_year = m.y
      AND b.evidence_type = '{baseline}')
  AND (c.first_year IS NULL OR m.y >= c.first_year)
"""


def journal_line(domain: str, year: int, value: str, url: str | None) -> dict:
    """Rebuild the journal record the loader originally read.

    `evidence_value` was written as `"{group} {message_id}"`, so the group is
    everything up to the first space. A value with no space has no group, and the
    parser's own default of `usenet` is left to apply rather than inventing one.
    """
    group, _, message_id = value.partition(" ")
    record: dict = {"domain": domain, "year": int(year)}
    if message_id:
        record["group"] = group
        record["message_id"] = message_id
    else:
        record["message_id"] = group
    if url:
        record["url"] = url
    return record


def select(conn, mention_source: str) -> list[tuple]:
    return conn.execute(_SELECT.format(baseline=BASELINE_TYPE), [mention_source]).fetchall()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="Suffix for the journal names, e.g. 20260816.")
    parser.add_argument("--write", action="store_true", help="Write the journals.")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    conn = connect_read_only_patiently(STORE, patience_s=900)
    try:
        seen: set[tuple[str, int]] = set()
        total_pairs = 0
        commands: list[str] = []
        for mention_source, ingest_key in PROMOTION.items():
            rows = select(conn, mention_source)
            weighed = sum(
                (weight_of(domain.rsplit(".", 1)[-1]) for domain, _y, _v, _u in rows),
                Decimal(0),
            )
            print(f"  {mention_source:<26} {len(rows):>8,} pairs  {float(weighed):>11,.1f} EE")
            total_pairs += len(rows)
            seen.update((domain, year) for domain, year, _v, _u in rows)
            if not args.write or not rows:
                continue
            path = args.out / f"{ingest_key}_promoted_{args.tag}.jsonl.gz"
            with journal_writer(path) as fh:
                for domain, year, value, url in rows:
                    write_journal_line(fh, journal_line(domain, year, value, url))
            commands.append(f"uv run ark ingest {ingest_key} {path}")

        tlds = Counter(domain.rsplit(".", 1)[-1] for domain, _year in seen)
        ee = sum((weight_of(tld) * n for tld, n in tlds.items()), Decimal(0))
        print(f"\n  per-source total, shared pairs counted twice: {total_pairs:,}")
        print(f"  DEDUPLICATED: {len(seen):,} pairs, {float(ee):,.1f} equivalent-English")
        if args.write:
            print("\n  Written. Nothing is ingested; run these only on a decision:")
            for command in commands:
                print(f"    {command}")
        else:
            print("\n  Dry run. Pass --write to emit the journals.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
