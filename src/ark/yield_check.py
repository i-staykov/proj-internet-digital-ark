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

import json
from collections.abc import Iterable
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

    def describe(self) -> str:
        if not self.measurable:
            return (
                f"{self.prefix}: only {self.recent_answered} answered in the newest "
                f"journals, too few to judge"
            )
        recent = f"{self.recent_rate:.1%} of {self.recent_answered:,}"
        if self.history_rate is None or self.history_answered < MIN_SAMPLE:
            return f"{self.prefix}: {recent} answered held a capture, no history to compare"
        return (
            f"{self.prefix}: {recent} answered held a capture, against "
            f"{self.history_rate:.1%} of {self.history_answered:,} before that"
        )


def _count(path: Path) -> tuple[int, int]:
    """(answered, hits) in one journal. A file mid-write is simply short."""
    answered = hits = 0
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
                if record.get("status") != 200:
                    continue
                answered += 1
                if record.get("years"):
                    hits += 1
    except OSError:
        return 0, 0
    return answered, hits


def measure(directory: Path, prefix: str, recent_files: int = RECENT_FILES) -> Yield:
    """Recent yield against earlier yield, for one collector prefix.

    In-flight `.part` files are skipped: a batch two records in is not evidence, and
    including it would make the reading jump around between cycles for no reason.
    """
    journals = sorted(
        (p for p in directory.glob(f"{prefix}_*.jsonl*") if not p.name.endswith(".part")),
        reverse=True,
    )
    recent_answered = recent_hits = 0
    used = 0
    for path in journals:
        if used >= recent_files and recent_answered >= MIN_SAMPLE:
            break
        answered, hits = _count(path)
        recent_answered += answered
        recent_hits += hits
        used += 1

    history_answered = history_hits = 0
    for path in journals[used:]:
        answered, hits = _count(path)
        history_answered += answered
        history_hits += hits

    return Yield(
        prefix=prefix,
        recent_answered=recent_answered,
        recent_hits=recent_hits,
        history_answered=history_answered,
        history_hits=history_hits,
        newest=journals[0].name if journals else "",
    )


def measure_all(directory: Path, prefixes: Iterable[str]) -> list[Yield]:
    return [measure(directory, prefix) for prefix in prefixes]
