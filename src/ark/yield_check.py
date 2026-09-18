"""Is a collector finding anything, as opposed to merely running and writing?

**Presence is not progress, and progress is not yield.** A supervisor watching journal
growth catches a stuck socket but not a stuck population, because **a journal full of
misses grows exactly as fast as a journal full of hits.** That gap cost a measured
fortnight: a queue whose first 3,000 rows were 2,675 `.mil` names ran 1,200 archive
queries for ZERO in-window captures while every mechanical check reported clean.

So this reads the journals and asks what none of the other checks do: **of the domains
the archive actually answered, what share held a capture?**

**Only status 200 counts in the denominator**, the rule `journal_outcomes` uses: a
transport failure says nothing about whether a capture exists, so counting it as a miss
would slander the whole population.

**A collapse is judged against the collector's own history, never against a constant.**
The populations differ by design, gap answering 96-97.5% and the candidate pool 36.9-90.6%
depending on where a name came from, so one floor would either miss a pool collapse or cry
wolf at a healthy pool. Absolute zero is caught separately, since zero over a real sample
is never healthy for either.
"""

import gzip
import json
import re
import time
import zlib
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

        Zero needs no comparison: a population that answers and never holds a capture is
        not worth querying, whatever it did last week.
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

        The windowed rate is what to alarm on and the wrong thing to read after a queue
        is re-ranked: averaging three batches, it stays low for hours after a fix. This
        reads only a published journal, never a `.part`, because a gzip stream still
        being appended truncates at its last complete block and a prefix is not a sample.
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

    **A 404 counts as answered here, where its CDX equivalent would not**: the registry
    saying "no such domain" is information, and 1,107,164 of 1,656,921 RDAP queries here
    returned one, the forged half of the candidate pool seen from the registry side. A
    throttle (429), refusal (403, 426) or transport failure (0) is not an answer and must
    stay out of the denominator, or rate-limiting reads as a vanished population.

    The year must be **in window**: 28.4% of queries return some year against 10.1%
    returning one that counts, so counting any year reports a sweep of modern
    registrations as productive.
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

    **A journal still being written raises `EOFError`, not `OSError`**, so catch both or
    a live RDAP journal takes the whole cycle down. Both collectors write `<name>.part`
    and rename on exit, but a killed batch can still publish a partial under the final
    name, and a live RDAP batch runs over an hour, so the read stays truncation-tolerant
    rather than trusting the suffix.

    A truncated read keeps what parsed and **says it was truncated**. Quietly trusting a
    prefix is how one batch got reported at four different rates.
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
    except (OSError, EOFError, gzip.BadGzipFile, zlib.error):
        # zlib.error is the CORRUPT case rather than the truncated one, and it subclasses
        # none of the others, so leaving it out takes the whole health cycle down on a
        # journal a killed collector left mid-write. Same treatment as truncation.
        #
        # Not UnicodeDecodeError: `open_journal` opens with errors="replace", so inflated
        # garbage is substituted. An ad-hoc reader on strict decoding DOES die that way.
        truncated = True
    return answered, hits, truncated


def measure(
    directory: Path,
    prefix: str,
    recent_files: int = RECENT_FILES,
    verdict: Callable[[dict], tuple[bool, bool]] = cdx_verdict,
) -> Yield:
    """Recent yield against earlier yield, for one collector prefix.

    In-flight `.part` files are skipped, and that exclusion is load-bearing: reading one
    produced 19%, 9.5%, 14.0% and 27.9% off a batch that finished at 8.2%.

    **Files are selected and ordered on the timestamp in the name, never on the raw
    filename**, because `data/raw/rdap/` also holds hand-named probe files from one-off
    experiments and `rdap_probe_...` sorts ahead of every `rdap_pool_<stamp>...`. That
    reports a static probe as the newest finished batch, and **a yield check reading the
    wrong file cannot fail loudly**.
    """
    stamped = []
    for path in directory.glob(f"{prefix}_*.jsonl*"):
        if path.name.endswith(".part"):
            continue
        match = _STAMPED.match(path.name)
        if match is None:
            continue
        stamped.append((match.group("stamp"), path))
    journals = [path for _stamp, path in sorted(stamped, key=lambda pair: pair[0], reverse=True)]
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


# A collector counts as live if it has written within this long. Journals arrive every
# 50 to 80 minutes per engine, and the VPS ones arrive in an rsync burst, so a day is
# comfortably clear of both while still excluding a prefix that stopped last week.
ACTIVE_WITHIN_S = 24 * 3600

_STAMPED = re.compile(r"^(?P<prefix>.+?)_(?P<stamp>\d{8}T\d{6}Z)\.jsonl")


def active_cdx_collectors(
    directory: Path, within_s: int = ACTIVE_WITHIN_S, now: float | None = None
) -> list[Collector]:
    """Every CDX prefix that has written here recently, discovered rather than listed.

    **Never a hardcoded list.** A supervisor header describes intent; the directory holds
    the facts, and it has held six prefixes where the header named two. An unplanned
    prefix ran 31 hours against an exhausted shard, 3,219 answered queries for ZERO
    captures, invisible because nothing was looking for it. Asking the directory is the
    only version of this check a collector under a new name cannot defeat.

    Activity is judged on the newest file INCLUDING a `.part`, since that is usually what
    a live collector is writing; the measurement still ignores `.part` files.
    """
    moment = time.time() if now is None else now
    newest: dict[str, float] = {}
    for path in directory.glob("cdx*_*.jsonl*"):
        match = _STAMPED.match(path.name)
        if not match:
            continue
        try:
            stamp = path.stat().st_mtime
        except OSError:
            continue
        prefix = match.group("prefix")
        newest[prefix] = max(newest.get(prefix, 0.0), stamp)
    live = [p for p, stamp in newest.items() if moment - stamp <= within_s]
    return [Collector(prefix, directory, cdx_verdict) for prefix in sorted(live)]


def measure_collectors(collectors: Iterable[Collector]) -> list[Yield]:
    """Every collector, each read by the verdict its own journal format needs."""
    return [measure(c.directory, c.prefix, verdict=c.verdict) for c in collectors]
