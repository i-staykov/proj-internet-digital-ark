"""Measure the CDX campaign from its own journals, for the report section that requires it.

The reviewer's 2026-08-15 brief adds a mandatory section: which CDX tools were used,
which seeds were retrieved, how requests were batched, the success rate, how failures
were handled, and how many unique domains were ultimately added. He also says plainly
that 504s and rate limits "do not justify declaring this approach infeasible", so the
section has to show adaptation rather than assert difficulty.

Every figure here is read from the journals on disk rather than from memory, because
the journals are the only record that cannot drift. Two properties of this data have
each produced a wrong answer before and are handled explicitly:

  **Never enumerate the prefixes.** This file used to be told there were two, then six;
  there are seven today (`cdx_disc` is the newest) and the VPS has always written its
  own. A hardcoded list read clean for 31 hours while a collector wrote 3,219 answered
  queries and zero captures. So the prefixes are discovered from the directory.

  **A journal full of misses grows exactly as fast as one full of hits.** Presence is
  not progress and progress is not yield, so the success rate is reported next to the
  in-window hit rate and never instead of it.

Read-only, no network, no database write lock.

    uv run python scripts/cdx_execution_notes.py
    uv run python scripts/cdx_execution_notes.py --markdown
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

CDX_DIR = Path("data/raw/cdx")
STAMPED = re.compile(r"^(?P<prefix>.+?)_(?P<stamp>\d{8}T\d{6}Z)\.jsonl")

# The window the whole project is scored on. A capture outside it answers the query
# and is still worth nothing, which is the distinction the yield line exists to make.
WINDOW = range(1996, 2002)


# `ark cdx` records transport failures as sentinel statuses rather than HTTP codes,
# and the distinction turned out to carry the whole story. Measured 2026-08-16 over
# 283,968 queries: HTTP-level errors are 0.96% of the campaign, while these two are
# 12.3%. A report that quoted only 429s and 504s would describe a different campaign
# from the one we ran.
REFUSED = 0
TIMED_OUT = -1


@dataclass
class Tally:
    """One collector prefix, which in practice means one machine and one population."""

    queries: int = 0
    answered: int = 0
    failed: int = 0
    throttled: int = 0
    server_error: int = 0
    forbidden: int = 0
    refused: int = 0
    timed_out: int = 0
    other_failure: int = 0
    truncated: int = 0
    with_any_year: int = 0
    with_window_year: int = 0
    window_pairs: int = 0
    domains: set[str] = field(default_factory=set)
    hit_domains: set[str] = field(default_factory=set)
    statuses: collections.Counter = field(default_factory=collections.Counter)
    first_stamp: str = ""
    last_stamp: str = ""
    files: int = 0

    @property
    def success_rate(self) -> float:
        return 100.0 * self.answered / self.queries if self.queries else 0.0

    @property
    def hit_rate(self) -> float:
        """In-window hit rate over ANSWERED queries, which is the honest denominator.

        Over all queries it would blend two different failures, a domain with no
        capture and a request the archive refused, and only the first is a fact
        about the domain.
        """
        return 100.0 * self.with_window_year / self.answered if self.answered else 0.0


def scan(directory: Path) -> dict[str, Tally]:
    tallies: dict[str, Tally] = collections.defaultdict(Tally)
    for path in sorted(directory.glob("*.jsonl*")):
        if path.name.endswith(".part"):
            continue
        match = STAMPED.match(path.name)
        if match is None:
            continue
        prefix, stamp = match.group("prefix"), match.group("stamp")
        tally = tallies[prefix]
        tally.files += 1
        tally.first_stamp = min(tally.first_stamp or stamp, stamp)
        tally.last_stamp = max(tally.last_stamp, stamp)

        opener = gzip.open if path.suffix == ".gz" else open
        try:
            with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    _count(tally, record)
        except (OSError, EOFError):
            # A journal still being written is normal, not an error worth stopping for.
            continue
    return dict(tallies)


def _count(tally: Tally, record: dict) -> None:
    tally.queries += 1
    domain = record.get("domain", "")
    if domain:
        tally.domains.add(domain)

    status = record.get("status")
    if isinstance(status, int):
        tally.statuses[status] += 1
        if status == 200:
            tally.answered += 1
        else:
            tally.failed += 1
            if status == 429:
                tally.throttled += 1
            elif status in (500, 502, 503, 504):
                tally.server_error += 1
            elif status == 403:
                tally.forbidden += 1
            elif status == REFUSED:
                tally.refused += 1
            elif status == TIMED_OUT:
                tally.timed_out += 1
            else:
                tally.other_failure += 1

    if record.get("truncated"):
        tally.truncated += 1

    years = record.get("years") or []
    if years:
        tally.with_any_year += 1
    in_window = [y for y in years if isinstance(y, int) and y in WINDOW]
    if in_window:
        tally.with_window_year += 1
        tally.window_pairs += len(in_window)
        if domain:
            tally.hit_domains.add(domain)


def render(tallies: dict[str, Tally], markdown: bool) -> str:
    order = sorted(tallies, key=lambda p: tallies[p].queries, reverse=True)
    out: list[str] = []

    if markdown:
        out.append(
            "| Collector prefix | Journals | Queries | Answered | Success | "
            "In-window hit rate | Distinct domains | In-window pairs |"
        )
        out.append("|---|--:|--:|--:|--:|--:|--:|--:|")
        for prefix in order:
            t = tallies[prefix]
            out.append(
                f"| `{prefix}` | {t.files:,} | {t.queries:,} | {t.answered:,} | "
                f"{t.success_rate:.1f}% | {t.hit_rate:.1f}% | {len(t.domains):,} | "
                f"{t.window_pairs:,} |"
            )
        total = _total(tallies)
        out.append(
            f"| **All** | **{total.files:,}** | **{total.queries:,}** | "
            f"**{total.answered:,}** | **{total.success_rate:.1f}%** | "
            f"**{total.hit_rate:.1f}%** | **{len(total.domains):,}** | "
            f"**{total.window_pairs:,}** |"
        )
        out.append("")
        out.append(_failure_paragraph(total))
        return "\n".join(out)

    for prefix in order:
        t = tallies[prefix]
        out.append(f"== {prefix} ==")
        out.append(f"  journals            {t.files:,}   {t.first_stamp} .. {t.last_stamp}")
        out.append(f"  queries             {t.queries:,}")
        out.append(f"  answered (200)      {t.answered:,}  ({t.success_rate:.1f}%)")
        out.append(
            f"  failed              {t.failed:,}   "
            f"429 {t.throttled:,}  5xx {t.server_error:,}  403 {t.forbidden:,}  "
            f"refused {t.refused:,}  timeout {t.timed_out:,}  other {t.other_failure:,}"
        )
        out.append(f"  truncated           {t.truncated:,}")
        out.append(f"  any capture         {t.with_any_year:,}")
        out.append(f"  in-window capture   {t.with_window_year:,}  ({t.hit_rate:.1f}% of answered)")
        out.append(f"  in-window pairs     {t.window_pairs:,}")
        out.append(f"  distinct domains    {len(t.domains):,}  of which hit {len(t.hit_domains):,}")
        out.append("")

    total = _total(tallies)
    out.append("== all collectors ==")
    out.append(f"  queries             {total.queries:,}")
    out.append(f"  answered            {total.answered:,}  ({total.success_rate:.1f}%)")
    out.append(
        f"  failed              {total.failed:,}   "
        f"429 {total.throttled:,}  5xx {total.server_error:,}  403 {total.forbidden:,}  "
        f"refused {total.refused:,}  timeout {total.timed_out:,}  other {total.other_failure:,}"
    )
    out.append(f"  in-window pairs     {total.window_pairs:,}")
    out.append(f"  distinct domains    {len(total.domains):,}")
    out.append("")
    out.append(_failure_paragraph(total))
    return "\n".join(out)


def _total(tallies: dict[str, Tally]) -> Tally:
    total = Tally()
    for t in tallies.values():
        total.files += t.files
        total.queries += t.queries
        total.answered += t.answered
        total.failed += t.failed
        total.throttled += t.throttled
        total.server_error += t.server_error
        total.forbidden += t.forbidden
        total.refused += t.refused
        total.timed_out += t.timed_out
        total.other_failure += t.other_failure
        total.truncated += t.truncated
        total.with_any_year += t.with_any_year
        total.with_window_year += t.with_window_year
        total.window_pairs += t.window_pairs
        total.domains |= t.domains
        total.hit_domains |= t.hit_domains
        total.statuses.update(t.statuses)
    return total


def _failure_paragraph(total: Tally) -> str:
    """The failure mix, since the reviewer asks how errors were handled.

    Written to make one point that the obvious framing hides. The brief asks about
    504s and rate limits, and against this campaign those are a rounding error: the
    load is carried by transport-level refusals, which is the same throttling seen
    from the other side of the socket. Any account built on HTTP status codes alone
    would describe 1% of our failures and miss 12%.
    """
    if not total.queries:
        return "No CDX journals found."
    http_level = total.throttled + total.server_error + total.forbidden
    transport = total.refused + total.timed_out
    pct = lambda n: 100.0 * n / total.queries  # noqa: E731
    return (
        f"Of {total.queries:,} queries, {total.answered:,} were answered "
        f"({total.success_rate:.1f}%). The {total.failed:,} that were not divide into two kinds, "
        f"and the smaller kind is the one usually discussed. **HTTP-level errors are "
        f"{http_level:,} ({pct(http_level):.2f}%)**: {total.throttled:,} rate limits (429), "
        f"{total.server_error:,} server errors (500, 502, 503, 504) and {total.forbidden:,} "
        f"refusals (403). **Transport-level failures are {transport:,} ({pct(transport):.2f}%)**: "
        f"{total.refused:,} connections refused or reset and {total.timed_out:,} timed out. "
        f"So the binding constraint is not a status code we could read and obey, it is the "
        f"connection being dropped before a status exists. Rate limits and server errors are "
        f"retried with exponential backoff honouring `Retry-After`; refusals and timeouts are "
        f"retried with a widening delay and then requeued, so no domain is lost by one failure; "
        f"a 403 is treated as a permanent answer for that host and is not retried."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=CDX_DIR)
    parser.add_argument("--markdown", action="store_true", help="Emit a table for the report.")
    args = parser.parse_args()

    tallies = scan(args.dir)
    if not tallies:
        print(f"No stamped journals under {args.dir}")
        return
    print(render(tallies, args.markdown))


if __name__ == "__main__":
    main()
