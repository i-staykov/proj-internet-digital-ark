"""Run journals: the artifact a network collector writes, and evidence reads.

Network collectors do not write evidence. They append one JSON object per
queried domain to an immutable per-run journal, and a bulk parser turns that
journal into evidence through the audited loader, which hashes it into the file
ledger. Three properties follow, and each one was paid for the hard way:

- the evidence replays from bytes on disk instead of from a live service whose
  answers change;
- a change of evidence standard is a re-parse, not a database migration;
- collection never opens the store, so a long run cannot hold the single-writer
  lock against everything else.

One file per run, never appended to after the run ends, because the loader keys
its ledger on (source name, file name) and refuses a file whose hash changed.

That ledger rule is also why a run writes to `<name>.part` and renames only when
it stops. The documented ingest commands glob `*.jsonl.gz`, and a collector is
often still running when one is issued; ingesting a half-written journal would
ledger the hash of its first N lines, and every later ingest of the finished file
would then fail the hash check with its tail unreachable. The `.part` name keeps
an unfinished run out of that glob while `queried_domains` still reads it, so a
killed run's answers are not re-queried.
"""

import gzip
import json
import os
import signal
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

# marks a journal whose run has not stopped yet: readable, not yet ingestable
IN_FLIGHT_SUFFIX = ".part"


def journal_path(directory: Path, prefix: str, now: datetime | None = None) -> Path:
    """Path for a new run journal, stamped so runs never collide."""
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return directory / f"{prefix}_{stamp}.jsonl.gz"


def in_flight_path(path: Path) -> Path:
    """The name a journal carries while its run is still writing to it."""
    return path.with_name(path.name + IN_FLIGHT_SUFFIX)


def _is_compressed(path: Path) -> bool:
    """Whether a journal is gzipped, looking past a trailing `.part`."""
    return ".gz" in path.suffixes


def open_journal(path: Path) -> IO[str]:
    """Open a journal for reading, gzipped or plain."""
    if _is_compressed(path):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open(encoding="utf-8", errors="replace")


def open_journal_for_write(path: Path) -> IO[str]:
    """Open a journal for writing, gzipped unless the path says otherwise."""
    if _is_compressed(path):
        return gzip.open(path, "wt", encoding="utf-8")
    return path.open("w", encoding="utf-8")


@contextmanager
def _sigterm_raises() -> Iterator[None]:
    """Turn SIGTERM into SystemExit, so `finally` blocks still run.

    The supervisor script stops a collector with `pkill`, and Python's default
    SIGTERM handling exits without unwinding, which would leave the journal
    stranded under its `.part` name. Only the main thread can install a handler,
    and only the main thread ever runs this, but a worker thread asking for one
    should be a no-op rather than a crash.
    """

    def raise_system_exit(_signum: int, _frame: object) -> None:
        raise SystemExit(128 + signal.SIGTERM)

    try:
        previous = signal.signal(signal.SIGTERM, raise_system_exit)
    except ValueError:
        yield
        return
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


@contextmanager
def journal_writer(path: Path) -> Iterator[IO[str]]:
    """Write a run journal, publishing it under its real name only at the end.

    The rename happens however the run ends, including on Ctrl-C, an exception,
    or SIGTERM: at that point nothing is writing the file any more, so what it
    holds is a complete record of a shorter run and is safe to ingest.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = in_flight_path(path)
    handle = open_journal_for_write(partial)
    try:
        with _sigterm_raises():
            yield handle
    finally:
        handle.close()
        os.replace(partial, path)


def write_journal_line(fh: IO[str], record: dict) -> None:
    fh.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")


def queried_domains(
    directory: Path,
    prefix: str,
    answered: Callable[[dict], bool] | None = None,
) -> set[str]:
    """Domains a run journal already ANSWERED, so runs never repeat settled work.

    `answered` decides what counts as settled. This matters: a transport failure
    is not an answer, and journalling it as one would permanently drop the domain
    from every later run. Pass a predicate for sources where some outcomes are
    failures rather than findings; the default treats any record as settled,
    which is right where the service either answers or says "not found".

    Truncation is tolerated: an interrupted run leaves a journal readable up to
    its last flush, and whatever it lost is simply queried again next time.
    """
    seen: set[str] = set()
    if not directory.is_dir():
        return seen
    for path in sorted(directory.glob(f"{prefix}_*.jsonl*")):
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
                    domain = record.get("domain")
                    if domain and (answered is None or answered(record)):
                        seen.add(domain)
        except (EOFError, OSError):
            continue
    return seen
