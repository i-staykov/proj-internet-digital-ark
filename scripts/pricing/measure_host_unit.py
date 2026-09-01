"""Measure how much of a domain list is a hostname rather than a registered domain.

**Why this exists.** Rule 8 of the brief says the annual files should use registered
domains as the output unit, "rather than `www.example.com`, `foo.example.com`, or
specific user paths on platforms such as GeoCities or Tripod". This project has
followed that literally: `to_registrable` is the single funnel every name passes
through before it reaches the store, so a third-level host is collapsed to its
registrable parent and then discarded as already held.

The reviewer's own benchmark does not follow it, and neither does his calculator,
whose counting unit is "one unique normalized domain record in the supplied list".
So the same population is worth zero to us and full weight to him. This script
measures the size of that disagreement, on his files, with his weights, so the
question can be put to him as arithmetic rather than as an impression.

    uv run python scripts/pricing/measure_host_unit.py <dir-or-file> [more...]

Prints, per file: total records, how many are NOT their own registrable domain,
and what those are worth under the bundled CC-MAIN-2024-10 English shares.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark.canonical import to_registrable  # noqa: E402

# His calculator ships the weights next to itself in every task package. Read them
# from his file rather than from ours, so a disagreement in the weights cannot be
# mistaken for a disagreement in the unit.
DEFAULT_MODEL = (
    REPO
    / "feedback/feedback-phase-7/Domain_Data_Collection_Task 3"
    / "equivalent_english_domain_calculator/q2_tld_top_langs.json"
)
YEARS = tuple(f"{y}.txt" for y in range(1996, 2002))


def load_weights(path: Path) -> dict[str, Decimal]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(tld).lower(): Decimal(str(pct)) / Decimal("100")
        for tld, lang, pct in zip(raw["tld"], raw["lang"], raw["perc_of_tld"], strict=True)
        if tld and lang == "eng"
    }


def survey(path: Path, weights: dict[str, Decimal]) -> tuple[int, int, Decimal, int]:
    """Return (records, sub-registrable records, their equivalent-English, unparsed)."""
    total = subs = unparsed = 0
    ee = Decimal(0)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            host = line.strip().lower()
            if not host:
                continue
            total += 1
            registrable = to_registrable(host)
            if registrable is None:
                unparsed += 1
            elif registrable != host:
                subs += 1
                ee += weights.get(host.rsplit(".", 1)[-1], Decimal(0))
    return total, subs, ee, unparsed


def targets(given: list[Path]) -> list[Path]:
    out: list[Path] = []
    for path in given:
        if path.is_dir():
            out.extend(path / name for name in YEARS if (path / name).is_file())
        elif path.is_file():
            out.append(path)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    args = parser.parse_args()

    weights = load_weights(args.model)
    grand_total = grand_subs = 0
    grand_ee = Decimal(0)
    print(f"{'file':<44} {'records':>11} {'sub-registrable':>16} {'share':>8} {'EE':>14}")
    for path in targets(args.paths):
        total, subs, ee, _ = survey(path, weights)
        share = f"{100 * subs / total:.2f}%" if total else "n/a"
        label = str(path)[-44:]
        print(f"{label:<44} {total:>11,} {subs:>16,} {share:>8} {ee:>14,.2f}")
        grand_total += total
        grand_subs += subs
        grand_ee += ee
    if grand_total:
        share = 100 * grand_subs / grand_total
        print(
            f"{'TOTAL':<44} {grand_total:>11,} {grand_subs:>16,} {share:>7.2f}% {grand_ee:>14,.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
