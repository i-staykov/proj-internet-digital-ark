"""What has actually paid, per shape, and why that turns out not to be a floor.

**The gap this fills is his XI's last sentence**: "Feed both positive yield and negative results
into the next automated discovery hypotheses." The generator already gets the negative half, 493
closed leads from `screen_hypothesis.py --list-closed`. It gets nothing about the positive half,
and the cost of that is measurable: the `usenet_alt_remainder` hypothesis put its own floor at
130,000 EE gross and the lane paid 1,929, a 67x overestimate, because nothing told it what a GB of
`alt` had actually been worth. In the other direction `usenet_probe` recommended closing the whole
Usenet hostname lane on one group, and the pools then paid 119,640.

So this reads the register's measured figures and groups them by the SHAPE of the artifact.

**And the first run refuted the reason it was written.** The intent was a per-shape floor. The
distribution says no such floor exists: every shape's median is three figures or less while its
best is six or seven, a spread of four to six orders of magnitude WITHIN a shape. A median-based
floor would have killed the 818,952 EE ISC census and the 6,371,375 EE remainder, and a best-based
floor admits everything. **Shape does not predict what a lead is worth.**

What separates the outliers from the medians is visible in the register rows themselves and is one
thing: the six- and seven-figure entries are whole-corpus reads, and the medians are samples,
single artifacts and single groups. That is the same finding as the day's other two, from opposite
directions: reading eleven Usenet hierarchies whole paid 119,640 EE while one `comp` group paid
480, and the sweep pays 193,000 EE per client-hour while the per-domain query pays 255.

**So the prior a hypothesis should carry is not the shape's median but whether the artifact can be
read WHOLE**, and the table below is printed to show the spread rather than to supply a threshold.

    uv run python scripts/harness/yield_priors.py [--top N]
"""

from __future__ import annotations

import argparse
import re
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTERS = (REPO / "docs/sources.md", REPO / "docs/sources-closed.md")

# `<number> EE`, the figure every register row carries in its net-new column.
_EE = re.compile(r"([\d,]+(?:\.\d+)?)\s*EE")

# The shapes a hypothesis is actually written in, matched against the slug and the row's prose.
# Deliberately coarse: a shape with two members is a coincidence, not a prior.
SHAPES: dict[str, tuple[str, ...]] = {
    "capture index at hostname grain": ("hostgrain", "hostname_grain", "cdx", "timemap"),
    "usenet or mail bodies": ("usenet", "maillist", "mail_", "pipermail", "enron", "listserv"),
    "dns survey or zone": ("isc_survey", "zone", "nserver", "inaddr", "in-addr", "dns"),
    "registry or registrar data": ("rdap", "whois", "registry", "register", "afnic", "iedr"),
    "blocklist or filter list": ("blocklist", "squidguard", "chastity", "junkfilter", "spam"),
    "directory or portal listing": ("directory", "portal", "odp", "yellow", "webring", "ring"),
    "link graph or link list": ("link_", "linkgraph", "host_link", "ukwa"),
    "prose or document corpus": ("rfc", "eric", "hansard", "magazine", "press", "faq", "rtfm"),
}


def shape_of(text: str) -> str | None:
    low = text.lower()
    for shape, needles in SHAPES.items():
        if any(needle in low for needle in needles):
            return shape
    return None


def measured() -> dict[str, list[float]]:
    """Every EE figure in the registers, grouped by artifact shape."""
    out: dict[str, list[float]] = {}
    for path in REGISTERS:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.startswith("| "):
                continue
            match = _EE.search(line)
            shape = shape_of(line.split("|")[1] if "|" in line else line)
            if match is None or shape is None:
                continue
            try:
                value = float(match.group(1).replace(",", ""))
            except ValueError:
                continue
            out.setdefault(shape, []).append(value)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=12, help="shapes to print")
    args = ap.parse_args()
    rows = measured()
    if not rows:
        print("no measured figures found in the registers")
        return 0
    print("What each SHAPE of artifact has actually paid, from the register's own figures.")
    print("Read the SPREAD, not the median. Every shape's median is three figures or less and")
    print("its best is six or seven, so shape does not predict what a lead is worth and no")
    print("per-shape floor is honest. What separates them is whether the artifact was read")
    print("WHOLE: the outliers are whole-corpus reads, the medians are samples and single")
    print("artifacts. Price a lead on how much of it you can read, not on its family.\n")
    print(f"{'shape':34} {'n':>4} {'median EE':>12} {'best EE':>14} {'spread':>8}")
    ranked = sorted(rows.items(), key=lambda kv: -max(kv[1]))
    for shape, values in ranked[: args.top]:
        if len(values) < 2:
            continue
        median = statistics.median(values) or 0.1
        print(
            f"{shape:34} {len(values):>4} {statistics.median(values):>12,.1f} "
            f"{max(values):>14,.1f} {max(values) / median:>7,.0f}x"
        )
    print("\nThe rates that decide where an HOUR goes are in docs/laws.md, measured:")
    print("  a domain-wide hostname sweep over names already held : ~193,000 EE per client-hour")
    print("  a per-domain gap query                               :      255 EE per hour")
    print("  so ask how many records ONE answer can carry, not how fast we may ask")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
