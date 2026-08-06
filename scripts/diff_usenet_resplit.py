"""Compare a staged Usenet re-split against the journals already ingested.

The point is to keep the database clean by never handing it a duplicate, rather
than by cleaning up afterwards. `domain_year.evidence_id` is a NOT NULL foreign
key and the evidence-wall check requires every annual assignment to point at a
live evidence row for the same domain and year, so deleting evidence after the
fact orphans assignments. Filtering on disk costs nothing and cannot break that.

Three categories come out, and they are three different decisions:

  NEW         the pair appears in no existing journal. This is what the wider
              regex actually bought: a `www.foo.com` written without a scheme,
              which `_URL` could not see because it requires `https?://`.

  PROMOTED    the pair is already in an existing CANDIDATE journal, and the
              re-split now puts it in the DATED half because some other source
              has attested the domain since. Nothing to do with the new regex:
              it is the store having grown under a rule that was always there.
              Worth its own decision, because ingesting it adds a second
              evidence row for a post that already has one.

  UNCHANGED   everything else. Dropped.

Writes the NEW half as ingestable journals and leaves PROMOTED as a report only,
because the two deserve separate answers.

    uv run python scripts/diff_usenet_resplit.py \
        --staged data/staging/usenet_resplit --tag resplit260806
"""

import argparse
import gzip
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ark.english_share import weight_of  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402

LIVE_DIR = Path("data/raw/usenet")


def pairs_in(path: Path) -> dict[tuple[str, int], dict]:
    out: dict[tuple[str, int], dict] = {}
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                domain, year = record.get("domain"), record.get("year")
                if domain and isinstance(year, int):
                    out[(domain, year)] = record
    except (OSError, EOFError):
        pass
    return out


def ee(pairs) -> Decimal:
    return sum((Decimal(weight_of(d)) for d, _ in pairs), Decimal(0))


def describe(label: str, pairs: set, records: dict) -> None:
    if not pairs:
        print(f"\n{label}: none")
        return
    years = Counter(y for _, y in pairs)
    tlds = Counter(d.rsplit(".", 1)[-1] for d, _ in pairs)
    print(f"\n{label}: {len(pairs):,} pairs, {ee(pairs):,.1f} equivalent-English")
    print(f"   mean weight {ee(pairs) / len(pairs):.4f}")
    print(f"   by year  {dict(sorted(years.items()))}")
    print(f"   top TLDs {tlds.most_common(8)}")
    for key in sorted(pairs)[:5]:
        rec = records.get(key, {})
        print(
            f"     {key[0]:<34} {key[1]}  {rec.get('group', '?')}  {rec.get('message_id', '')[:56]}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--staged", type=Path, default=Path("data/staging/usenet_resplit"))
    ap.add_argument("--tag", default="resplit260806")
    ap.add_argument("--write", action="store_true", help="Write the NEW half as journals.")
    args = ap.parse_args()

    live: dict[tuple[str, int], str] = {}
    live_files = sorted(LIVE_DIR.glob("*.jsonl.gz"))
    for path in live_files:
        half = "dated" if "usenet_dated" in path.name else "candidates"
        for key in pairs_in(path):
            # a pair already dated stays dated for this comparison
            if live.get(key) != "dated":
                live[key] = half
    print(f"existing journals: {len(live_files)}, {len(live):,} distinct (domain, year)")

    staged_dated = pairs_in(args.staged / f"usenet_dated_{args.tag}.jsonl.gz")
    staged_cand = pairs_in(args.staged / f"usenet_candidates_{args.tag}.jsonl.gz")
    print(
        f"staged re-split: {len(staged_dated):,} dated, {len(staged_cand):,} candidates, "
        f"{len(staged_dated) + len(staged_cand):,} total"
    )

    new_dated = {k for k in staged_dated if k not in live}
    new_cand = {k for k in staged_cand if k not in live}
    promoted = {k for k in staged_dated if live.get(k) == "candidates"}

    describe("NEW, corroborated half (would enter annual files)", new_dated, staged_dated)
    describe("NEW, candidate half (goes to the candidate pool)", new_cand, staged_cand)
    describe("PROMOTED (already a candidate, now corroborated)", promoted, staged_dated)

    total_new = new_dated | new_cand
    print(f"\n{'=' * 70}")
    print(f"NEW total          : {len(total_new):,} pairs, {ee(total_new):,.1f} EE")
    print(f"  of which admitted: {len(new_dated):,} pairs, {ee(new_dated):,.1f} EE")
    print(f"  of which candidate: {len(new_cand):,} pairs, {ee(new_cand):,.1f} EE")
    print(
        f"PROMOTED           : {len(promoted):,} pairs, {ee(promoted):,.1f} EE  (separate decision)"
    )
    print(f"{'=' * 70}")

    if not args.write:
        print("\nreport only; pass --write to stage the NEW half as ingestable journals")
        return

    out = args.staged / "filtered"
    out.mkdir(parents=True, exist_ok=True)
    for name, keys, source in (
        (f"usenet_dated_{args.tag}new.jsonl.gz", new_dated, staged_dated),
        (f"usenet_candidates_{args.tag}new.jsonl.gz", new_cand, staged_cand),
    ):
        path = out / name
        with journal_writer(path) as fh:
            for key in sorted(keys):
                write_journal_line(fh, source[key])
        print(f"wrote {path} ({len(keys):,} records)")
    print("\nNOT ingested. To ingest after review:")
    print(f"  uv run ark ingest usenet_dated {out}/usenet_dated_{args.tag}new.jsonl.gz")
    print(f"  uv run ark ingest usenet_candidates {out}/usenet_candidates_{args.tag}new.jsonl.gz")


if __name__ == "__main__":
    main()
