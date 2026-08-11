"""Is a collector finding anything, as opposed to merely running and writing?

**Presence is not progress, and progress is not yield.** `supervise_cdx_pool.sh`
argues the first at length in its own header: a batch stuck on a socket leaves the
process alive and the journal frozen, so the supervisor watches journal growth
rather than the PID. That closed the gap it was aimed at and left a wider one open,
because **a journal full of misses grows exactly as fast as a journal full of
hits.** Every record is written either way.

That gap cost a measured fortnight of collector time on 2026-08-11. A queue rebuilt
that afternoon put 2,675 `.mil` names in its first 3,000 rows, and the local engine
ran two batches, 1,200 archive queries, and returned **zero** in-window captures. Its
process was alive, its journal was growing, `just cycle` reported every mechanical
check clean, and the only place the truth appeared was a `no_capture: 600` counter in
a log line nothing read. Roughly 25 days of the prioritised discovery half would have
produced nothing.

So this reads the journals and answers the question none of the other checks ask:
**of the domains the archive actually answered, what share held a capture?**

**Only status 200 counts in the denominator**, the same rule `journal_outcomes` uses
and for the same reason: a transport failure says nothing about whether a capture
exists, so counting it as a miss would slander the whole population.

**A collapse is judged against the collector's own history, not against a constant.**
The two populations differ by design, gap answering 96-97.5% and the candidate pool
36.9-90.6% depending on where a name came from, so one hardcoded floor would either
miss a pool collapse or cry wolf at a healthy pool. Comparing a collector against its
own recent past needs no such number, and the absolute-zero case is caught separately
because zero over a real sample is never healthy for either population.
"""

import gzip
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from ark.journal import open_journal

# Below this many answered domains a rate is noise, and an alarm on noise is an
# alarm that gets ignored. One pool batch is 600, so this is well under a batch.
MIN_SAMPLE = 250

# How far a recent rate must fall below the collector's own history to count as a
# collapse rather than a bad patch. A quarter is deliberately generous: the failure
# this exists to catch took the rate to exactly zero from 45.8%.
COLLAPSE_FRACTION = 0.25

# How many of the newest journals form the "recent" window, before falling back to
# whatever reaches MIN_SAMPLE. Three batches is a few hours of work.
RECENT_FILES = 3


@dataclass(frozen=True)
class Yield:
    prefix: str
    recent_answered: int
    recent_hits: int
    history_answered: int
    history_hits: int
    newest: str
    newest_answered: int = 0
    newest_hits: int = 0
    # True when a journal was still being written, so the reading is a prefix of it.
    newest_partial: bool = False

    @property
    def recent_rate(self) -> float | None:
        return self.recent_hits / self.recent_answered if self.recent_answered else None

    @property
    def history_rate(self) -> float | None:
        return self.history_hits / self.history_answered if self.history_answered else None

    @property
    def measurable(self) -> bool:
        return self.recent_answered >= MIN_SAMPLE

    @property
    def collapsed(self) -> bool:
        """Zero over a real sample, or far below this collector's own history.

        Zero is called out on its own because it needs no comparison: a population
        that answers and never holds a capture is not a population worth querying,
        whatever it did last week.
        """
        if not self.measurable or self.recent_rate is None:
            return False
        if self.recent_hits == 0:
            return True
        if self.history_answered < MIN_SAMPLE or self.history_rate is None:
            return False
        return self.recent_rate < self.history_rate * COLLAPSE_FRACTION

    @property
    def newest_rate(self) -> float | None:
        return self.newest_hits / self.newest_answered if self.newest_answered else None

    @property
    def latest(self) -> str:
        """The newest FINISHED batch on its own, which is the recovery signal.

        The windowed rate is the right thing to alarm on and the wrong thing to read
        after a queue is re-ranked: it averages over three batches, so it stays low for
        hours after a fix and cannot say whether the fix worked. This can.

        It reads only a published journal, never a `.part`. Reading an in-flight one is
        how three different rates got quoted off a single batch in one afternoon, 9.5%
        then 14.0% then 27.9%, because a gzip stream still being appended truncates at
        its last complete block and the prefix is not a sample.
        """
        if not self.newest or self.newest_rate is None:
            return "no finished batch yet"
        which = "newest batch SO FAR" if self.newest_partial else "newest finished batch"
        return f"{which} {self.newest_rate:.1%} of {self.newest_answered:,} answered"

    def describe(self) -> str:
        if not self.measurable:
            return (
                f"{self.prefix}: only {self.recent_answered} answered in the newest "
                f"journals, too few to judge"
            )
        recent = f"{self.recent_rate:.1%} of {self.recent_answered:,}"
        if self.history_rate is None or self.history_answered < MIN_SAMPLE:
            return (
                f"{self.prefix}: {recent} answered held a capture, no history to "
                f"compare; {self.latest}"
            )
        return (
            f"{self.prefix}: {recent} answered held a capture, against "
            f"{self.history_rate:.1%} of {self.history_answered:,} before that; {self.latest}"
        )


YEARS = range(1996, 2002)


def cdx_verdict(record: dict) -> tuple[bool, bool]:
    """(answered, held a capture) for a CDX journal record.

    Only status 200 counts as answered, the rule `journal_outcomes` already uses: a
    transport failure says nothing about whether a capture exists, so counting it as a
    miss would slander the whole population.
    """
    if record.get("status") != 200:
        return False, False
    return True, bool(record.get("years"))


def rdap_verdict(record: dict) -> tuple[bool, bool]:
    """(answered, in-window creation year) for an RDAP journal record.

    **A 404 counts as answered here, where its CDX equivalent would not.** The registry
    replying "no such domain" is information, and a real one: 1,107,164 of 1,656,921
    RDAP queries on this project have returned 404, which is the forged half of the
    candidate pool seen from the registry side. A throttle (429), a refusal (403, 426)
    or a transport failure (0) is not an answer and must not enter the denominator, or a
    registry that starts rate-limiting would read as a population that stopped existing.

    The year must be **in window**. A creation year of 2015 is a perfectly good answer
    that pays nothing, and counting it would report a sweep of modern registrations as
    productive: 28.4% of queries return some year against 10.1% returning one that
    counts.
    """
    if record.get("status") not in (200, 404):
        return False, False
    year = record.get("creation_year")
    return True, isinstance(year, int) and year in YEARS


@dataclass(frozen=True)
class Collector:
    """One collector's journals and how to read a record of them."""

    prefix: str
    directory: Path
    verdict: Callable[[dict], tuple[bool, bool]]


def _count(path: Path, verdict: Callable[[dict], tuple[bool, bool]]) -> tuple[int, int, bool]:
    """(answered, hits, truncated) in one journal.

    **A journal still being written raises rather than ending politely**, and the error
    is `EOFError`, not an `OSError`, so an `except OSError` around this crashed the whole
    cycle the first time it met a live RDAP journal. The two collectors differ in a way
    that matters here: the CDX supervisor writes `<name>.part` and renames on exit, so a
    finished file is identifiable and mid-write ones are simply excluded, while the RDAP
    sweep writes its final name from the start and flushes as it goes. For RDAP,
    excluding mid-write files would exclude the newest one always.

    So a truncated read keeps what it could parse and **says that it was truncated**,
    because the alternative is either crashing or quietly trusting a prefix, and quietly
    trusting a prefix is how one batch got reported at four different rates.
    """
    answered = hits = 0
    truncated = False
    try:
        with open_journal(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                was_answered, was_hit = verdict(record)
                if not was_answered:
                    continue
                answered += 1
                hits += was_hit
    except (OSError, EOFError, gzip.BadGzipFile):
        truncated = True
    return answered, hits, truncated


def measure(
    directory: Path,
    prefix: str,
    recent_files: int = RECENT_FILES,
    verdict: Callable[[dict], tuple[bool, bool]] = cdx_verdict,
) -> Yield:
    """Recent yield against earlier yield, for one collector prefix.

    In-flight `.part` files are skipped: a batch two records in is not evidence, and
    including it would make the reading jump around between cycles for no reason. That
    exclusion is load-bearing rather than tidy, and reading one anyway produced 19%,
    9.5%, 14.0% and 27.9% off a batch that finished at 8.2%.
    """
    journals = sorted(
        (p for p in directory.glob(f"{prefix}_*.jsonl*") if not p.name.endswith(".part")),
        reverse=True,
    )
    recent_answered = recent_hits = 0
    used = 0
    truncated = False
    for path in journals:
        if used >= recent_files and recent_answered >= MIN_SAMPLE:
            break
        answered, hits, was_truncated = _count(path, verdict)
        recent_answered += answered
        recent_hits += hits
        truncated = truncated or was_truncated
        used += 1

    history_answered = history_hits = 0
    for path in journals[used:]:
        answered, hits, _t = _count(path, verdict)
        history_answered += answered
        history_hits += hits

    newest_answered, newest_hits, newest_partial = (
        _count(journals[0], verdict) if journals else (0, 0, False)
    )
    return Yield(
        prefix=prefix,
        recent_answered=recent_answered,
        recent_hits=recent_hits,
        history_answered=history_answered,
        history_hits=history_hits,
        newest=journals[0].name if journals else "",
        newest_answered=newest_answered,
        newest_hits=newest_hits,
        newest_partial=newest_partial or truncated,
    )


def measure_all(directory: Path, prefixes: Iterable[str]) -> list[Yield]:
    """Backwards-compatible sweep over CDX prefixes under one directory."""
    return [measure(directory, prefix) for prefix in prefixes]


def measure_collectors(collectors: Iterable[Collector]) -> list[Yield]:
    """Every collector, each read by the verdict its own journal format needs.

    The RDAP sweep is this round's largest single contributor, 81,216 records and 49,012
    equivalent-English, and until now nothing measured whether it was still finding
    anything. Same gap as the CDX one, one collector over.
    """
    return [measure(c.directory, c.prefix, verdict=c.verdict) for c in collectors]
