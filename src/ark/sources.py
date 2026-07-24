"""Registered bulk sources: the parser and evidence semantics of each.

Adding a source means writing a parser that yields BulkRecord rows and
registering a SourceSpec here; the shared loader in bulk.py handles the
rest (canonicalization, staging, evidence routing, audit, metrics).
"""

import csv
import gzip
import json
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


def parse_arquivo_cdxj(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per in-window HTTP-200 capture in an Arquivo.pt CDXJ file.

    Each line is `SURT-key timestamp {json}`; the JSON carries the original url
    and status. The capture timestamp is item-level evidence (a web-archive
    capture, like IA CDX), so no recheck is needed.
    """
    with _open_text(path) as fh:
        for line in fh:
            stats["lines"] += 1
            parts = line.split(" ", 2)
            if len(parts) < 3:
                stats["malformed"] += 1
                continue
            timestamp = parts[1]
            try:
                record = json.loads(parts[2])
            except json.JSONDecodeError:
                stats["malformed"] += 1
                continue
            url = record.get("url")
            if not url or len(timestamp) != 14 or not timestamp.isdigit():
                stats["malformed"] += 1
                continue
            year = int(timestamp[:4])
            if year not in YEARS:
                stats["out_of_window"] += 1
                continue
            if record.get("status") != "200":
                stats["non_200"] += 1
                continue
            yield BulkRecord(
                raw=url,
                year=year,
                evidence_value=timestamp,
                evidence_url=f"https://arquivo.pt/wayback/{timestamp}/{url}",
            )


# the host link graph is sorted by year ascending, so once we pass the window
# nothing in-window remains; this also stops before the truncated 2002+ tail of
# our partial download (Wayback drops the 20.9 GB stream mid-transfer)
_UKWA_LAST_YEAR = max(YEARS)


def parse_ukwa_link_source(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield the SOURCE host of each UKWA host-link-graph row as `link_source`.

    Rows are `year|source_host|target_host<TAB>count`. The source host was
    crawled (HTTP 200) that year to produce the link, so it is direct evidence;
    the target host (a bare inbound link) is candidate-only and handled by a
    separate Phase-3 source. The graph's granularity is the year.
    """
    with _open_text(path) as fh:
        try:
            for line in fh:
                stats["lines"] += 1
                parts = line.rstrip("\n").split("\t", 1)[0].split("|")
                if len(parts) != 3 or not parts[0].isdigit():
                    stats["malformed"] += 1
                    continue
                year = int(parts[0])
                if year > _UKWA_LAST_YEAR:
                    break
                if year not in YEARS:
                    stats["out_of_window"] += 1
                    continue
                yield BulkRecord(raw=parts[1], year=year, evidence_value=f"host_link_graph:{year}")
        except (EOFError, OSError):
            # a truncated gzip tail (the 2002+ region of our partial download);
            # everything in-window was already yielded before this point
            stats["truncated_tail"] += 1


# AFNIC .fr open data: one semicolon-delimited UTF-8 row per current or
# recently-withdrawn .fr domain. Column 1 is the domain, column 11 the creation
# date and column 12 the WHOIS-withdrawal date, both DD-MM-YYYY (12 empty = still
# registered). A .fr creation date resets on re-registration, so the pair
# (creation, withdrawal) documents one CONTINUOUS registration interval: the
# domain was registered every year from creation until withdrawal (or now). Per
# brief III.6 a record demonstrating continued registration in a year is valid
# year evidence, so we emit one record per in-window year the domain was
# registered, not only the creation year. Domains withdrawn before 1996 or
# created after 2001 contribute nothing in window.
_AFNIC_MIN_FIELDS = 12
_AFNIC_NAME_COL = 0
_AFNIC_CREATED_COL = 10
_AFNIC_WITHDRAWN_COL = 11
_AFNIC_DATE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")
_AFNIC_FIRST_YEAR = min(YEARS)
_AFNIC_LAST_YEAR = max(YEARS)


def _afnic_year(token: str) -> int | None:
    """Year from a DD-MM-YYYY AFNIC date cell, or None if blank/malformed."""
    match = _AFNIC_DATE.match(token.strip())
    return int(match.group(3)) if match else None


def parse_afnic_fr(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per in-window year each .fr domain was registered."""
    with _open_text(path) as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader, None)  # header row
        for row in reader:
            stats["lines"] += 1
            if len(row) < _AFNIC_MIN_FIELDS:
                stats["malformed"] += 1
                continue
            created = _afnic_year(row[_AFNIC_CREATED_COL])
            if created is None:
                stats["no_creation_date"] += 1
                continue
            withdrawn_cell = row[_AFNIC_WITHDRAWN_COL].strip()
            withdrawn = _afnic_year(withdrawn_cell) if withdrawn_cell else None
            start = max(created, _AFNIC_FIRST_YEAR)
            end = _AFNIC_LAST_YEAR if withdrawn is None else min(withdrawn, _AFNIC_LAST_YEAR)
            if end < start:
                stats["out_of_window"] += 1
                continue
            # the interval is the auditable basis for every year assigned
            interval = f"registered {row[_AFNIC_CREATED_COL].strip()}..{withdrawn_cell or 'active'}"
            for year in range(start, end + 1):
                yield BulkRecord(
                    raw=row[_AFNIC_NAME_COL],
                    year=year,
                    evidence_value=interval,
                    evidence_url="https://opendata.afnic.fr/",
                )


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
    "arquivo_roteiro": SourceSpec(
        key="arquivo_roteiro",
        source_name="arquivo_roteiro",
        evidence_type="cdx_timestamp",
        acquisition_method="arquivo_cdxj",
        parse=parse_arquivo_cdxj,
    ),
    # the Internet Archive's donated Portuguese-web collection (1996-2007), same
    # CDXJ format as Roteiro but a distinct source so provenance stays separate
    "arquivo_ia": SourceSpec(
        key="arquivo_ia",
        source_name="arquivo_ia",
        evidence_type="cdx_timestamp",
        acquisition_method="arquivo_cdxj",
        parse=parse_arquivo_cdxj,
    ),
    "ukwa_link_source": SourceSpec(
        key="ukwa_link_source",
        source_name="ukwa_link_source",
        evidence_type="link_source",
        acquisition_method="ukwa_host_link_graph",
        parse=parse_ukwa_link_source,
    ),
    # AFNIC .fr open data: registration-interval evidence (whois_creation),
    # one year per in-window year the domain was continuously registered
    "afnic_fr": SourceSpec(
        key="afnic_fr",
        source_name="afnic_fr",
        evidence_type="whois_creation",
        acquisition_method="afnic_open_data",
        parse=parse_afnic_fr,
    ),
}
