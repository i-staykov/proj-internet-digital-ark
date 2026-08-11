"""Price any dated corpus against the live store, without writing a line of it.

**The bottleneck this removes.** Every source assessed here has needed a bespoke
script, and almost all of that code was the same code: extract hostnames, collapse
to registrable domains, difference against the store, apply the corroboration
split, weigh the result, and try not to fool yourself with the projection. Only
the first step, turning a source into dated items, is genuinely source-specific.
So this owns everything after that, and a new hypothesis costs a fetch loop rather
than a program.

**The boundary is deliberate.** Input is a normalised JSON Lines stream, one object
per item:

    {"item": "<an id a reviewer can look up>", "year": 1998, "text": "..."}

`date` is accepted instead of `year` and the first in-window year in it is used.
Fetching, unpacking and date-parsing stay with the caller because they cannot be
generalised; nothing downstream of them can be got wrong twice.

**What it refuses to let you get wrong**, each because the project has paid for it:

- **It quotes the post-split figure.** A raw recovered set of 2,440,926 pairs
  admitted 107,304, so the raw number overstated that source 24-fold. Both are
  printed and the raw one is labelled do-not-quote.
- **It measures against the LIVE store**, not an export. A header projection said
  ~10,889 equivalent-English and delivered 1,038.4 because it was measured against
  an export three hours old while another ingest wrote 102,577 overlapping pairs.
- **It fits saturation as well as a line, and reports the lower.** A 120-archive
  pilot projected 1.9M equivalent-English against a true 62,821. Both fits come
  from `project_usenet_bare.py` rather than a second implementation.
- **It counts domains and pairs separately.** Conflating them once reported
  1,161,961 domains against a true 463,566.
- **It bounds the typo rate** by checking how many never-before-seen names are one
  edit from a name already held, which is the honest upper bound on OCR and
  transcription junk.
- **It never writes.** Pricing decides whether to build a collector; it is not one.

    uv run python scripts/price_items.py --items items.jsonl.gz
    uv run python scripts/price_items.py --items sample.jsonl --sample-of 19233
"""

import argparse
import gzip
import importlib.util
import json
import re
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import duckdb  # noqa: E402
from probe_texts_corpus import domains_in  # noqa: E402

from ark.english_share import english_weights  # noqa: E402

# The two fits live in the script that first needed them; importing rather than
# reimplementing is the point, since a second saturation curve would eventually
# disagree with the first.
_SPEC = importlib.util.spec_from_file_location(
    "project_usenet_bare", ROOT / "scripts" / "project_usenet_bare.py"
)
_projection = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_projection)

STORE = ROOT / "data/ark.duckdb"
YEARS = range(1996, 2002)
YEAR_RE = re.compile(r"(199[6-9]|200[01])")
ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789-."


def read_only_store(patience_s: int = 900) -> duckdb.DuckDBPyConnection:
    deadline = time.monotonic() + patience_s
    while True:
        try:
            return duckdb.connect(str(STORE), read_only=True)
        except duckdb.Error as exc:
            if "Conflicting lock" not in str(exc):
                raise
            if time.monotonic() >= deadline:
                raise SystemExit(
                    f"the store was still being written after {patience_s}s; "
                    "pricing reads it, so re-run when the ingest finishes"
                ) from None
            time.sleep(3)


def opener(path: Path):
    return (
        gzip.open(path, "rt", encoding="utf-8", errors="replace")
        if path.suffix == ".gz"
        else path.open(encoding="utf-8", errors="replace")
    )


def year_of(record: dict) -> int | None:
    """An explicit in-window `year`, or the first in-window year inside `date`."""
    raw = record.get("year")
    if isinstance(raw, int) and raw in YEARS:
        return raw
    if isinstance(raw, str) and raw.isdigit() and int(raw) in YEARS:
        return int(raw)
    found = YEAR_RE.search(str(record.get("date", "")))
    return int(found.group(1)) if found else None


def within_one_edit(name: str, held: set[str]) -> bool:
    """Whether one edit of `name` is a name the store already holds.

    Generates the neighbourhood rather than scanning `held`, so it is a few
    hundred set lookups instead of millions of comparisons.
    """
    for i in range(len(name)):
        if name[:i] + name[i + 1 :] in held:
            return True
        for ch in ALPHABET:
            if ch != name[i] and name[:i] + ch + name[i + 1 :] in held:
                return True
    for i in range(len(name) + 1):
        for ch in ALPHABET:
            if name[:i] + ch + name[i:] in held:
                return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--items", type=Path, required=True, help="JSONL(.gz): item, year|date, text")
    ap.add_argument(
        "--sample-of",
        type=int,
        default=None,
        help="items in the whole corpus, if this is a sample. Turns on the projections.",
    )
    ap.add_argument("--label", default="", help="name for the report line")
    args = ap.parse_args()

    weights = english_weights()
    conn = read_only_store()
    try:
        held_pairs = {
            (d, y)
            for d, y in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
        known = {r[0] for r in conn.execute("SELECT domain FROM domain").fetchall()}
    finally:
        conn.close()
    attested = {d for d, _ in held_pairs}

    stats = Counter()
    pairs: set[tuple[str, int]] = set()
    # cumulative net-new equivalent-English against item count, for the fits
    curve: list[tuple[int, float]] = []
    running = Decimal(0)
    with opener(args.items) as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            stats["items"] += 1
            record = json.loads(line)
            year = year_of(record)
            if year is None:
                stats["undated_or_out_of_window"] += 1
                continue
            stats["in_window"] += 1
            for name in domains_in(record.get("text") or ""):
                key = (name, year)
                if key in pairs:
                    continue
                pairs.add(key)
                if key not in held_pairs:
                    running += weights.get(name.rsplit(".", 1)[-1], Decimal(0))
            if stats["items"] % 25 == 0:
                curve.append((stats["items"], float(running)))
    curve.append((stats["items"], float(running)))

    def ee(rows) -> Decimal:
        return sum((weights.get(d.rsplit(".", 1)[-1], Decimal(0)) for d, _ in rows), Decimal(0))

    netnew = pairs - held_pairs
    corroborated = {(d, y) for d, y in netnew if d in attested}
    pooled = netnew - corroborated
    label = f" [{args.label}]" if args.label else ""

    print(f"== priced against the live store{label} ==")
    print(f"items read                 : {stats['items']:,}")
    print(f"  in window 1996-2001      : {stats['in_window']:,}")
    print(f"  undated or out of window : {stats['undated_or_out_of_window']:,}")
    print(
        f"distinct (domain, year)    : {len(pairs):,} over {len({d for d, _ in pairs}):,} domains"
    )
    print(f"already held by the store  : {len(pairs) - len(netnew):,}")
    print()
    print(
        f"net-new BEFORE the split   : {len(netnew):,} pairs, {ee(netnew):,.1f} EE  <- DO NOT QUOTE"
    )
    print(f"net-new AFTER the split    : {len(corroborated):,} pairs, {ee(corroborated):,.1f} EE")
    mean = ee(corroborated) / len(corroborated) if corroborated else Decimal(0)
    print(f"  net-new domains          : {len({d for d, _ in corroborated}):,}")
    print(f"  mean weight of net-new   : {mean:.4f}")
    print(
        f"to the candidate pool      : {len(pooled):,} pairs, "
        f"{len({d for d, _ in pooled} - known):,} names new to the pool"
    )
    if netnew:
        print(
            "  the raw figure overstates this source "
            f"{ee(netnew) / max(ee(corroborated), Decimal('0.0001')):.1f}x"
        )

    if corroborated:
        by_year = Counter(y for _d, y in corroborated)
        by_tld = Counter(d.rsplit(".", 1)[-1] for d, _ in corroborated)
        print(f"  by year                  : {dict(sorted(by_year.items()))}")
        print(f"  by tld                   : {dict(by_tld.most_common(6))}")

    sample_names = sorted({d for d, _ in netnew})[:1500]
    if sample_names:
        near = sum(1 for d in sample_names if within_one_edit(d, known))
        print(
            f"  typo upper bound         : {near:,} of {len(sample_names):,} sampled net-new names "
            f"({near / len(sample_names) * 100:.1f}%) are one edit from a name already held"
        )

    if args.sample_of and stats["items"]:
        share = stats["items"] / args.sample_of
        linear = float(ee(corroborated)) / share
        fitted, half = _projection.saturation(curve, args.sample_of)
        power, exponent = _projection.power_law(curve, args.sample_of)
        print()
        print(
            f"== PROJECTIONS, not measurements. Sample is {share:.2%} "
            f"of {args.sample_of:,} items =="
        )
        print(f"  linear      : {linear:,.0f} EE   <- the one that has been wrong before")
        print(f"  saturation  : {fitted:,.0f} EE   (half-yield at {half:,.0f} items)")
        print(
            f"  power law   : {power:,.0f} EE   (exponent {exponent:.2f}, 1.00 = no saturation yet)"
        )
        print(f"  QUOTE THE LOWEST: {min(linear, fitted, power):,.0f} EE")

    print()
    bar_pairs = len(corroborated) if not args.sample_of else None
    print("== against the bar in docs/discovery.md ==")
    if bar_pairs is not None:
        verdict = "clears it" if bar_pairs >= 5000 else "below the ~5,000 net-new pair bar"
        print(f"  volume      : {bar_pairs:,} net-new pairs, {verdict}")
    else:
        print("  volume      : sample only, project before judging")
    if corroborated:
        if mean >= Decimal("0.6"):
            print(f"  mean weight : {mean:.4f}, good")
        elif mean >= Decimal("0.4"):
            print(f"  mean weight : {mean:.4f}, volume has to justify itself")
        else:
            print(f"  mean weight : {mean:.4f}, below the 0.4 floor")
    print("  nothing was written. This decides whether to build a collector.")


if __name__ == "__main__":
    main()
