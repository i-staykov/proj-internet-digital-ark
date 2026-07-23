"""Registered bulk sources: the parser and evidence semantics of each.

Adding a source means writing a parser that yields BulkRecord rows and
registering a SourceSpec here; the shared loader in bulk.py handles the
rest (canonicalization, staging, evidence routing, audit, metrics).
"""

import gzip
import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from ark.bulk import BulkRecord, SourceSpec
from ark.ingest import YEARS

# classic CDX field order: urlkey, timestamp, original url, mimetype, status
_MIN_CDX_FIELDS = 5

# the ISC survey date is the YYMM code in the filename (e.g. 9607 = Jul 1996)
_ISC_SURVEY_CODE = re.compile(r"(\d{2})(0[1-9]|1[0-2])")


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


def _isc_survey_date(name: str) -> tuple[int, str] | None:
    """Read (year, 'YYYY-MM') from an ISC survey filename, or None if absent."""
    match = _ISC_SURVEY_CODE.search(name)
    if match is None:
        return None
    yy, mm = match.group(1), match.group(2)
    # ISC domain-list surveys run 1995-1997; the century split is future-proofing
    century = 1900 if int(yy) >= 90 else 2000
    return century + int(yy), f"{century + int(yy)}-{mm}"


def parse_isc_survey(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per domain listed in an ISC Internet Domain Survey file.

    The survey date is encoded in the filename (YYMM). Every line names either
    a domain (the `.domains` lists) or an `IP hostname` pair (the per-TLD host
    lists), so the last whitespace token is the host to canonicalize. Files
    dated outside the 1996-2001 window are skipped whole.
    """
    dated = _isc_survey_date(path.name)
    if dated is None:
        stats["unparsed_filename"] += 1
        return
    year, survey = dated
    if year not in YEARS:
        stats["out_of_window_file"] += 1
        return
    with _open_text(path) as fh:
        for line in fh:
            stats["lines"] += 1
            tokens = line.split()
            if not tokens:
                continue
            yield BulkRecord(raw=tokens[-1], year=year, evidence_value=survey)


SOURCES: dict[str, SourceSpec] = {
    "early_web": SourceSpec(
        key="early_web",
        source_name="early_web_cdx",
        evidence_type="cdx_timestamp",
        acquisition_method="bulk_cdx_file",
        parse=parse_early_web_cdx,
    ),
    "isc_survey": SourceSpec(
        key="isc_survey",
        source_name="isc_survey",
        evidence_type="artifact_listing",
        acquisition_method="isc_domain_survey",
        parse=parse_isc_survey,
    ),
}
