"""Measure a bare-host sample against the live store and project the full corpus.

Three things this reports that a raw set difference does not, and each of them has
already cost this project a wrong verdict:

- **the marginal figure.** Most bare hits are domains the corpus already gave up
  through their `www.` or URL form, or through `usenet_address`. The gross count
  is meaningless; what counts is pairs that survive the corroboration split AND
  are not already assigned. This reports how much of the gross each of those two
  filters removed, and names the Usenet sources the overlap belongs to.
- **a live measurement.** On 8 August a header-mode projection of 10,889
  equivalent-English delivered 1,038, because it was measured against a snapshot
  taken before an intervening ingest. This opens the store now, with retries.
- **a saturation fit as well as a linear one.** A linear extrapolation from a
  120-archive Usenet sample overstated one seam 24-fold. The corpus repeats the
  same addresses across groups, so yield per archive falls as it is walked; the
  fit uses the shape the sample itself shows rather than assuming a straight line.

Read-only against the store.

    uv run python scripts/project_usenet_bare.py --journal data/raw/usenet_bare/<file>
"""

import argparse
import gzip
import json
import math
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from ark.english_share import english_weights  # noqa: E402

STORE = ROOT / "data/ark.duckdb"
YEARS = range(1996, 2002)
CORPUS_ARCHIVES = 19231
# the two Usenet sources already reading these messages, which is what the
# marginal figure has to be net of
USENET_SOURCES = ("usenet_announce", "usenet_address")


def open_store(attempts: int = 80, pause: float = 15.0) -> duckdb.DuckDBPyConnection:
    for attempt in range(attempts):
        try:
            return duckdb.connect(str(STORE), read_only=True)
        except duckdb.IOException:
            if attempt == attempts - 1:
                raise
            time.sleep(pause)
    raise AssertionError("unreachable")


def read_journal(path: Path) -> dict[tuple[str, int], int]:
    """(domain, year) -> the archive ordinal that first produced it."""
    seen: dict[tuple[str, int], int] = {}
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            domain, year = record.get("domain"), record.get("year")
            if domain and year in YEARS:
                seen.setdefault((domain, int(year)), int(record.get("n", 0)))
    return seen


def saturation(curve: list[tuple[int, float]], target: int) -> tuple[float, float]:
    """Fit `y = A*a/(a+K)` to (archives, cumulative EE) and evaluate it at `target`.

    A two-parameter Michaelis-Menten shape, chosen because it is the shape a
    repeating corpus actually produces: every archive adds names, and an
    increasing share of them have been seen already. `A` is solved exactly for
    each candidate `K` by least squares, so only `K` is scanned, which keeps this
    to a few lines and needs no solver.

    `K` is scanned on a log grid running far past the corpus, because a linear
    scan with a ceiling reports its own ceiling as the answer and that reads as a
    measurement. A fitted `K` near the top of the range means the sample shows no
    saturation yet, which is information rather than a number to quote.
    """
    best = (float("inf"), 0.0, 1.0)
    for step in range(1, 1201):
        k = 10.0 ** (step / 150.0)
        num = sum(y * (a / (a + k)) for a, y in curve)
        den = sum((a / (a + k)) ** 2 for a in (a for a, _ in curve))
        if den == 0:
            continue
        amp = num / den
        error = sum((y - amp * a / (a + k)) ** 2 for a, y in curve)
        if error < best[0]:
            best = (error, amp, k)
    _, amp, k = best
    return amp * target / (target + k), k


def power_law(curve: list[tuple[int, float]], target: int) -> tuple[float, float]:
    """Fit `y = c*a**b` in log space and evaluate it at `target`, returning (y, b).

    The second reading of the same curve, and the one with a measured precedent.
    The address pass took 14,581 net-new pairs from 120 archives to 102,577 from
    19,231, which is exactly this shape with `b` near 0.38: yield keeps growing,
    sublinearly, because the corpus repeats its addresses across groups. `b = 1`
    would mean no saturation at all, so the exponent is the thing to read.
    """
    points = [(a, y) for a, y in curve if a > 0 and y > 0]
    if len(points) < 2:
        return 0.0, 1.0
    n = len(points)
    xs = [math.log(a) for a, _ in points]
    ys = [math.log(y) for _, y in points]
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    var = sum((x - mean_x) ** 2 for x in xs)
    if var == 0:
        return 0.0, 1.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / var
    intercept = mean_y - slope * mean_x
    return math.exp(intercept) * target**slope, slope


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--journal", type=Path, required=True)
    ap.add_argument("--archives", type=int, required=True, help="archives the journal walked")
    ap.add_argument("--corpus", type=int, default=CORPUS_ARCHIVES)
    args = ap.parse_args()

    seen = read_journal(args.journal)
    print(f"{len(seen):,} distinct (domain, year) in {args.journal.name}")

    conn = open_store()
    try:
        attested = {
            r[0] for r in conn.execute("SELECT DISTINCT domain FROM domain_year").fetchall()
        }
        held = {
            (r[0], r[1])
            for r in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
        placeholders = ", ".join("?" for _ in USENET_SOURCES)
        usenet_pairs = {
            (r[0], r[1])
            for r in conn.execute(
                f"""
                SELECT e.domain, e.evidence_year FROM evidence e
                JOIN source s ON s.source_id = e.source_id
                WHERE s.name IN ({placeholders})
                """,
                list(USENET_SOURCES),
            ).fetchall()
        }
    finally:
        conn.close()

    weights = english_weights()

    def ee(pairs) -> Decimal:
        return sum((weights.get(d.rsplit(".", 1)[-1], Decimal(0)) for d, _ in pairs), Decimal(0))

    corroborated = {p for p in seen if p[0] in attested}
    fresh = {p for p in corroborated if p not in held}
    from_usenet = {p for p in seen if p in usenet_pairs}

    print(f"\n  already asserted by {' or '.join(USENET_SOURCES)} : {len(from_usenet):,}")
    print(f"  already assigned by any source                    : {len(seen.keys() & held):,}")
    uncorroborated = len(seen) - len(corroborated)
    print(f"  uncorroborated, candidate pool only               : {uncorroborated:,}")
    print(f"  corroborated -> dated_directory                   : {len(corroborated):,}")
    print(f"    of those, not yet held: MARGINAL NET-NEW        : {len(fresh):,}")
    print(f"\nmarginal net-new equivalent-English: {ee(fresh):,.2f}")
    print(f"  (gross if the split and the dedupe were ignored: {ee(seen):,.2f})")

    tlds = Counter(d.rsplit(".", 1)[-1] for d, _ in fresh)
    print("  by TLD: " + ", ".join(f"{t} {n:,}" for t, n in tlds.most_common(8)))
    years = Counter(y for _, y in fresh)
    print("  by year: " + ", ".join(f"{y} {years[y]:,}" for y in sorted(years)))

    # cumulative marginal EE against archives walked, which is what the fit needs
    ordered = sorted((seen[p], p) for p in fresh)
    curve: list[tuple[int, float]] = []
    running = Decimal(0)
    index = 0
    for cut in range(max(args.archives // 40, 1), args.archives + 1, max(args.archives // 40, 1)):
        while index < len(ordered) and ordered[index][0] <= cut:
            running += weights.get(ordered[index][1][0].rsplit(".", 1)[-1], Decimal(0))
            index += 1
        curve.append((cut, float(running)))

    linear = float(ee(fresh)) / args.archives * args.corpus
    fitted, half = saturation(curve, args.corpus)
    fitted_power, exponent = power_law(curve, args.corpus)
    print(f"\nprojection to {args.corpus:,} archives")
    print(f"  linear     : {linear:,.0f} EE   (the shape that was wrong by 24x before)")
    print(f"  saturation : {fitted:,.0f} EE   (half-yield at {half:,.0f} archives)")
    print(
        f"  power law  : {fitted_power:,.0f} EE   (exponent {exponent:.2f}, 1.00 = no saturation)"
    )
    quarter, half_way = curve[len(curve) // 4], curve[len(curve) // 2]
    print(
        f"  sample curve: {quarter[0]} archives {quarter[1]:,.0f} EE, "
        f"{half_way[0]} archives {half_way[1]:,.0f} EE, "
        f"{args.archives} archives {float(ee(fresh)):,.0f} EE"
    )


if __name__ == "__main__":
    main()
