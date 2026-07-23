"""Registered bulk sources: the parser and evidence semantics of each.

Adding a source means writing a parser that yields BulkRecord rows and
registering a SourceSpec here; the shared loader in bulk.py handles the
rest (canonicalization, staging, evidence routing, audit, metrics).
"""

import gzip
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from ark.bulk import BulkRecord, SourceSpec
from ark.ingest import YEARS

# classic CDX field order: urlkey, timestamp, original url, mimetype, status
_MIN_CDX_FIELDS = 5


def _open_text(path: Path) -> IO[str]:
    """Open a possibly gzip-compressed text file for streaming reads."""
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open(encoding="utf-8", errors="replace")


def parse_early_web_cdx(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per in-window HTTP-200 capture line.

    IA's Early Web files are classic space-delimited CDX: the capture
    timestamp is the evidence, the original URL feeds the canonicalizer.
    """
    with _open_text(path) as fh:
        for line in fh:
            stats["lines"] += 1
            if line.startswith(" CDX") or line.startswith("CDX"):
                stats["header_lines"] += 1
                continue
            parts = line.split()
            if len(parts) < _MIN_CDX_FIELDS or len(parts[1]) != 14 or not parts[1].isdigit():
                stats["malformed"] += 1
                continue
            timestamp, original, status = parts[1], parts[2], parts[4]
            year = int(timestamp[:4])
            if year not in YEARS:
                stats["out_of_window"] += 1
                continue
            if status != "200":
                stats["non_200"] += 1
                continue
            yield BulkRecord(
                raw=original,
                year=year,
                evidence_value=timestamp,
                evidence_url=f"https://web.archive.org/web/{timestamp}/{original}",
            )


SOURCES: dict[str, SourceSpec] = {
    "early_web": SourceSpec(
        key="early_web",
        source_name="early_web_cdx",
        evidence_type="cdx_timestamp",
        acquisition_method="bulk_cdx_file",
        parse=parse_early_web_cdx,
    ),
}
