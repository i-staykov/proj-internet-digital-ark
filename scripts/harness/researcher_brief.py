"""Write one researcher's brief: several hypotheses, each with its collision report.

**Three problems this fixes, all measured on the loop's own ledger.**

**1. A seventh of the budget was spent rediscovering closed families.** Twelve of 85
runs found mid-flight that their family was already in `docs/sources.md`. The
researcher prompt asked the agent to grep for it, which costs tokens, is skippable,
and only tells the agent what it collided with if it greps the right words. So the
collision report is computed HERE, by `screen_hypothesis.py`, and pasted into the
brief. The agent starts knowing the nearest closed verdict and the screen it was
closed on, and spends its budget arguing with that verdict instead of finding it.

**2. A researcher that kills its hypothesis in five minutes idled for the rest of
the round.** The per-round cap is 2,400 s and a probe often settles a hypothesis in
a tenth of that, so the slot sat finished while its round-mates worked. Each brief
now carries a QUEUE, and the agent is told to work down it until the budget runs
out. The fixed cost of a round, reading CLAUDE.md and orienting, is paid once and
amortised over every hypothesis in the queue rather than over one.

**3. A closure can rest on a screen that has since been retired.** The novelty
screen was retired on 2026-08-25 and the free-hosting family had to be re-tested
because of it; the same happened to Stanford WebBase. So the brief names that
possibility explicitly and tells the agent what to do about it, which is the one
judgement a collision report cannot make for it.

    uv run python scripts/harness/researcher_brief.py --slugs a,b,c --budget 2000 --out FILE
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# Above this many shared terms the collision is worth reading in full; below it the
# screen is mostly matching common words like "index" or "list" and the report is noise.
COLLISION_FLOOR = 2
# Report at most this many collisions per hypothesis. The screen prints every lead it
# matched, and a brief carrying twenty of them costs more than the grep it replaced.
MAX_COLLISIONS = 3


def block_for(doc: str, slug: str) -> str | None:
    for block in re.split(r"\n(?=## )", doc):
        head = re.match(r"##\s+([a-z0-9_-]+)\s*\|", block)
        if head and head.group(1) == slug:
            return block.strip()
    return None


def title_of(block: str) -> str:
    head = re.match(r"##\s+[a-z0-9_-]+\s*\|\s*(.+)", block)
    return head.group(1).strip() if head else ""


def collisions(proposal: str) -> str:
    """Run the closed-register screen and return the collisions worth reading."""
    try:
        done = subprocess.run(
            [sys.executable, str(REPO / "scripts/harness/screen_hypothesis.py"), proposal],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=REPO,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return f"  (the screen could not be run: {exc})"

    kept: list[str] = []
    current: list[str] = []
    shared = 0
    for line in done.stdout.splitlines():
        hit = re.match(r"\s*COLLIDES \((\d+) shared terms?\)", line)
        if hit:
            if current and shared >= COLLISION_FLOOR:
                kept.append("\n".join(current))
            current = [line.strip()]
            shared = int(hit.group(1))
            continue
        if current:
            if line.strip().startswith("== gate"):
                break
            current.append(line.rstrip())
    if current and shared >= COLLISION_FLOOR:
        kept.append("\n".join(current))
    if not kept:
        return "  NOTHING in the closed register matches this. It is genuinely untried."
    return "\n\n".join(kept[:MAX_COLLISIONS])


HEADER = """You are ONE researcher in a parallel fan-out. Budget: about {budget} seconds for
ALL of the hypotheses below. Nobody reads a status update; your output is files.

Read CLAUDE.md first, it is binding. Then work the QUEUE below, in order, and STOP
when your budget is spent. Most hypotheses die on the probe in minutes; a queue means
that when one dies you move to the next instead of finishing early.

**Write one findings file per hypothesis you reach**, at private/findings/<slug>.md.
A hypothesis you never reach gets no file, which is correct and costs nothing.

## How to test one

1. **The collision report is already below. Do not grep docs/sources.md to rediscover
   it.** Read the verdict, then ask the question the report cannot answer for you:
   **what SCREEN was it closed on, and is that screen still current?** This project
   has retired two screens and both retirements reopened a family that had been
   closed on them:
   - the NOVELTY screen ("97.4% already held") was retired on 2026-08-25 and replaced
     by the 2001 screen, which asks the opposite question: held names are GOOD, and
     what matters is whether they lack the artifact's own YEAR.
   - a corpus closed for being crawl-derived was reopened when the 2001-dated edition
     of the same blocklist paid 10,736 EE while the 2000-dated edition paid 18.
   If the verdict's reasoning is "mostly already held" or "not novel", it was closed
   on the retired screen and IS worth re-testing. If it was closed on a measurement
   made with the current screen, it is finished: say so and move to the next one.
2. Read the WHOLE robots.txt of any host before the first request. Honour Retry-After.
   Do NOT touch web.archive.org/cdx: two collectors are metering against it. Other
   archive.org services and other hosts are fine.
3. **PROBE BEFORE YOU COMMIT.** Fetch the SMALLEST representative piece and measure
   three numbers on it: distinct registrable domains, the fraction ALREADY HELD, and
   the fraction held AND MISSING the artifact's own year. That third number is the
   one that decides it. Extrapolate, write the estimate down, then branch:
   - projected under 200 EE: STOP, report CLOSED with the probe numbers, next hypothesis.
   - projected 200 to 1,000 EE: take it only if the rest of the fetch is minutes.
   - projected over 1,000 EE: measure it properly. This is the case that matters.
4. Price with `uv run python scripts/pricing/price_items.py`, against merged260830. Sample
   DISTINCT DOMAINS, never domain_year rows.
5. If the artifact is already on disk under data/raw/, there is no fetch to save and
   no probe budget to protect: read it properly. Those have been the best runs.

## Write each result like this, and nothing else

  # <slug>
  verdict: FIND | CLOSED | BLOCKED
  ee: <net-new post-split EE, a number, 0 if none>
  probe: <the smallest piece measured, its domains, held fraction, held-and-missing-year
         fraction, and the projection to the whole artifact>
  what dates one item: <one line, or "nothing" if it cannot date a year>
  artifact: <URL and byte size, or why unreachable>
  measurement: <the numbers, including what you sampled>
  screen check: <what screen the nearest closed verdict used, and whether it still holds>
  method: <the reusable part, if any>
  next: <what you would do with more time, or "closed">

HARD RULES: do NOT run git. Do NOT edit any file except your own findings files. Do NOT
ingest anything. Do NOT edit docs/. Another process banks your results.
A measured negative is a RESULT: fill the file either way.

# YOUR QUEUE, {count} hypotheses, in order
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hypotheses", type=Path, default=REPO / "private/agent-hypotheses.md")
    parser.add_argument("--slugs", required=True, help="comma-separated, in priority order")
    parser.add_argument("--budget", type=int, default=2000)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    doc = args.hypotheses.read_text(encoding="utf-8")
    slugs = [s.strip() for s in args.slugs.split(",") if s.strip()]

    parts: list[str] = []
    reached = 0
    for position, slug in enumerate(slugs, 1):
        block = block_for(doc, slug)
        if block is None:
            continue
        reached += 1
        parts.append(
            f"\n## {position}. {slug}\n\n{block}\n\n"
            f"### the closed register on this proposal\n\n{collisions(title_of(block))}\n"
        )
    if not reached:
        print("no hypothesis block matched any slug", file=sys.stderr)
        return 1

    args.out.write_text(
        HEADER.format(budget=args.budget, count=reached) + "".join(parts), encoding="utf-8"
    )
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
