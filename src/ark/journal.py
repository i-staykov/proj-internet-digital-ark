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
"""

import gzip
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import IO


def journal_path(directory: Path, prefix: str, now: datetime | None = None) -> Path:
    """Path for a new run journal, stamped so runs never collide."""
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return directory / f"{prefix}_{stamp}.jsonl.gz"


def open_journal(path: Path) -> IO[str]:
    """Open a journal for reading, gzipped or plain."""
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open(encoding="utf-8", errors="replace")


def open_journal_for_write(path: Path) -> IO[str]:
    """Open a journal for writing, gzipped unless the path says otherwise."""
    if path.suffix == ".gz":
        return gzip.open(path, "wt", encoding="utf-8")
    return path.open("w", encoding="utf-8")


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
