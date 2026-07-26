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
from ark.cdx import evidence_years as cdx_evidence_years
from ark.ingest import YEARS
from ark.journal import open_journal
from ark.rdap import RDAP_REDIRECTOR, attested_years

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


# the host link graph is sorted by year ascending, so once the scan passes the window
# nothing in-window remains; this also stops before the truncated 2002+ tail of
# the partial download (Wayback drops the 20.9 GB stream mid-transfer)
_UKWA_LAST_YEAR = max(YEARS)


_UKWA_SOURCE_COL = 1
_UKWA_TARGET_COL = 2


def _parse_ukwa(path: Path, stats: Counter, host_column: int) -> Iterator[BulkRecord]:
    """Yield one host per in-window host-link-graph row, from the chosen column.

    Rows are `year|source_host|target_host<TAB>count`, sorted by year ascending,
    so the scan stops once it passes the window. That also stops before the
    truncated 2002+ tail of the partial download.
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
                yield BulkRecord(
                    raw=parts[host_column], year=year, evidence_value=f"host_link_graph:{year}"
                )
        except (EOFError, OSError):
            # a truncated gzip tail (the 2002+ region of the partial download);
            # everything in-window was already yielded before this point
            stats["truncated_tail"] += 1


def parse_ukwa_link_source(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield the SOURCE host of each row as `link_source`, which is direct evidence.

    The source host was crawled with HTTP 200 in that year to produce the link, so
    its existence that year is attested.
    """
    yield from _parse_ukwa(path, stats, _UKWA_SOURCE_COL)


def parse_ukwa_link_target(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield the TARGET host of each row as `link_target`, which is candidate-only.

    Being linked to proves nothing about the target: dead links, typographical
    errors and names registered only later are all common in a link graph. The row
    is kept for provenance and to prioritise verification, and can never assign a
    year on its own. Targets are worldwide, unlike the `.uk`-biased source hosts,
    which is why they are worth holding as candidates at all.
    """
    yield from _parse_ukwa(path, stats, _UKWA_TARGET_COL)


# AFNIC .fr open data: one semicolon-delimited UTF-8 row per current or
# recently-withdrawn .fr domain. Column 1 is the domain, column 11 the creation
# date and column 12 the WHOIS-withdrawal date, both DD-MM-YYYY (12 empty = still
# registered). A .fr creation date resets on re-registration, so the pair
# (creation, withdrawal) documents one CONTINUOUS registration interval: the
# domain was registered every year from creation until withdrawal (or now). Per
# brief III.6 a record demonstrating continued registration in a year is valid
# year evidence, so one record is emitted per in-window year the domain was
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


# Internet Scout Report archive (OAI-PMH harvest, oai_dc). Each <record> is an
# editorial review of a live site; <dc:date> is the Scout Report publication year
# (the archive spans 1994-2007, matching the Report's lifespan; a handful of
# pre-1994 dc:date anomalies fall outside the window and drop out). The
# publication date attests the site was live that year -> dated_directory (the
# 2026-07-24: dated directory/index sources are direct). Site URLs are in
# <dc:identifier>; the <header><identifier> is the auditable OAI record id.
_SCOUT_RECORD = re.compile(r"<record>.*?</record>", re.S)
_SCOUT_OAI_ID = re.compile(r"<identifier>([^<]+)</identifier>")
_SCOUT_DATE = re.compile(r"<dc:date>(\d{4})</dc:date>")
_SCOUT_URL = re.compile(r"<dc:identifier>(https?://[^<]+)</dc:identifier>")


def parse_internet_scout(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per reviewed site per in-window Scout Report year."""
    with _open_text(path) as fh:
        text = fh.read()
    for match in _SCOUT_RECORD.finditer(text):
        block = match.group(0)
        stats["scout_records"] += 1  # own key: "records" is the loader's yielded-count
        year_match = _SCOUT_DATE.search(block)
        if year_match is None:
            stats["no_date"] += 1
            continue
        year = int(year_match.group(1))
        if year not in YEARS:
            stats["out_of_window"] += 1
            continue
        oai = _SCOUT_OAI_ID.search(block)
        record_id = oai.group(1) if oai else "scout"
        urls = _SCOUT_URL.findall(block)
        if not urls:
            stats["no_url"] += 1
            continue
        for url in urls:
            yield BulkRecord(raw=url, year=year, evidence_value=record_id)


# ODP (Open Directory / DMOZ) RDF content dump: a dated data file, so
# artifact_listing evidence: a dated index file is direct evidence. The
# `<!-- Generated at YYYY-MM-DD ... -->` stamp fixes the year for the whole dump;
# each cataloged site is an external URL in a `link r:resource="..."` or an
# `ExternalPage about="..."`. The RDF is malformed pseudo-XML, so URLs are pulled
# by regex, not an XML parser. Some dumps are truncated downloads (gzip EOF
# mid-stream); tolerate that like UKWA, keeping everything decoded so far.
_ODP_GENERATED = re.compile(r"Generated at (\d{4})-(\d{2})-(\d{2})")
_ODP_URL = re.compile(r'(?:r:resource|about)="(https?://[^"]+)"')
_ODP_NAME_YEAR = re.compile(r"(?:19|20)\d{2}")


def _odp_fallback_year(name: str) -> int | None:
    """Year from the dump filename (e.g. c2000, kt200106), a fallback if the
    Generated-at stamp is missing."""
    match = _ODP_NAME_YEAR.search(name)
    return int(match.group(0)) if match else None


def parse_odp(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per cataloged external site in a dated ODP RDF dump."""
    year = _odp_fallback_year(path.name)
    dump_date = None
    try:
        with _open_text(path) as fh:
            for line in fh:
                stats["lines"] += 1
                if dump_date is None:
                    stamp = _ODP_GENERATED.search(line)
                    if stamp:
                        dump_date = f"{stamp[1]}-{stamp[2]}-{stamp[3]}"
                        year = int(stamp[1])
                for url in _ODP_URL.findall(line):
                    if year is None:
                        stats["no_year"] += 1
                        continue
                    yield BulkRecord(
                        raw=url,
                        year=year,
                        evidence_value=f"odp {dump_date or path.stem}",
                    )
    except (EOFError, OSError):
        # truncated download (e.g. the c2000 prefix); everything before the
        # truncation was already yielded
        stats["truncated_tail"] += 1


# An `ark rdap` run journal: one JSON object per line, format documented in
# ark.rdap. The journal is the artifact, so this evidence replays from a hashed
# file like every other source. Only the creation year is attested (III.6), so a
# domain yields at most one record; the rule itself lives in rdap.attested_years.
def parse_rdap_snapshot(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per journalled domain whose creation year is in window."""
    try:
        with open_journal(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                stats["journal_lines"] += 1
                try:
                    record = json.loads(line)
                except ValueError:
                    stats["unparseable_line"] += 1
                    continue
                domain = record.get("domain")
                if not domain:
                    stats["no_domain"] += 1
                    continue
                year = record.get("creation_year")
                if not isinstance(year, int):
                    # journalled as undatable: no RDAP, 404, or transport failure
                    stats["not_dated"] += 1
                    continue
                years = attested_years(year)
                if not years:
                    stats["outside_window"] += 1
                    continue
                for target_year in years:
                    yield BulkRecord(
                        raw=domain,
                        year=target_year,
                        evidence_value=f"rdap creation {year}",
                        evidence_url=f"{RDAP_REDIRECTOR}{domain}",
                    )
    except (EOFError, OSError):
        # journal from an interrupted run; everything before the last flush was
        # already yielded, and the missing tail is re-queried on the next run
        stats["truncated_tail"] += 1


# An `ark cdx` run journal: one JSON object per queried domain, format documented
# in ark.cdx. A returned in-window capture year is evidence for that year and no
# other, so there is no inference to make here (III.7).
def parse_cdx_snapshot(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per in-window year a CDX query returned for a domain."""
    try:
        with open_journal(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                stats["journal_lines"] += 1
                try:
                    record = json.loads(line)
                except ValueError:
                    stats["unparseable_line"] += 1
                    continue
                domain = record.get("domain")
                if not domain:
                    stats["no_domain"] += 1
                    continue
                if record.get("status") != 200:
                    stats["query_failed"] += 1
                    continue
                if record.get("truncated"):
                    stats["truncated_response"] += 1
                years = list(cdx_evidence_years(record, min(YEARS), max(YEARS)))
                if not years:
                    stats["no_capture_in_window"] += 1
                    continue
                for year in years:
                    yield BulkRecord(
                        raw=domain,
                        year=year,
                        evidence_value=f"cdx capture {year}",
                        evidence_url=f"https://web.archive.org/web/{year}/{domain}",
                    )
    except (EOFError, OSError):
        # journal from an interrupted run; the missing tail is re-queried next run
        stats["truncated_tail"] += 1


# An `ark download` journal: one JSON object per fetched page capture, format
# documented in ark.expand. The same journal is read by two sources, each taking
# the half it is entitled to, because a link's worth depends on whether the page
# carrying it is a curated catalogue.
def _parse_expansion(path: Path, stats: Counter, curated: bool) -> Iterator[BulkRecord]:
    try:
        with open_journal(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    stats["unparseable_line"] += 1
                    continue
                if record.get("status") != 200:
                    stats["fetch_failed"] += 1
                    continue
                if bool(record.get("curated")) is not curated:
                    stats["other_half"] += 1
                    continue
                year = record.get("year")
                page = record.get("page_url") or "page"
                stamp = record.get("timestamp") or ""
                if not isinstance(year, int) or year not in YEARS:
                    stats["out_of_window"] += 1
                    continue
                domains = record.get("domains") or []
                if not domains:
                    stats["no_outbound_links"] += 1
                    continue
                stats["pages"] += 1
                for domain in domains:
                    yield BulkRecord(
                        raw=domain,
                        year=year,
                        evidence_value=f"linked from {page} captured {stamp}",
                        evidence_url=f"https://web.archive.org/web/{stamp}/{page}"
                        if stamp
                        else None,
                    )
    except (EOFError, OSError):
        stats["truncated_tail"] += 1


def parse_expansion_links(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Hosts linked from an ordinary archived page: candidate-only.

    The page's author linked to them, which is not evidence the host existed:
    that is what verification is for.
    """
    yield from _parse_expansion(path, stats, curated=False)


def parse_expansion_directory(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Entries listed on an archived page asserted to be a curated directory.

    Section IV.i grants that the capture date of such a page is item-level
    evidence for every domain listed on it, needing no further verification. The
    assertion that a page IS a curated directory is made per seed, on the record.
    """
    yield from _parse_expansion(path, stats, curated=True)


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
    # Internet Scout Report archive: editorial directory entries, each dated by
    # its Scout Report publication year (dated_directory)
    "internet_scout": SourceSpec(
        key="internet_scout",
        source_name="internet_scout",
        evidence_type="dated_directory",
        acquisition_method="scout_report_oai",
        parse=parse_internet_scout,
    ),
    # ODP / DMOZ RDF content dump: dated data file -> artifact_listing; the
    # dump's generation stamp fixes the year (c2000 = 2000, kt2001xx = 2001)
    "odp": SourceSpec(
        key="odp",
        source_name="odp",
        evidence_type="artifact_listing",
        acquisition_method="odp_rdf_dump",
        parse=parse_odp,
    ),
    # kept distinct from the legacy `rdap` source, whose rows predate the
    # journal and so cannot be replayed from a file (see notes.md 2026-07-25)
    "rdap_snapshot": SourceSpec(
        key="rdap_snapshot",
        source_name="rdap_snapshot",
        evidence_type="whois_creation",
        acquisition_method="rdap_journal_file",
        parse=parse_rdap_snapshot,
    ),
    # the target side of the same file: candidate-only, so the loader records the
    # evidence and enqueues the host but never assigns a year
    "ukwa_link_target": SourceSpec(
        key="ukwa_link_target",
        source_name="ukwa_link_target",
        evidence_type="link_target",
        acquisition_method="ukwa_host_link_graph",
        parse=parse_ukwa_link_target,
    ),
    "expansion_links": SourceSpec(
        key="expansion_links",
        source_name="page_expansion",
        evidence_type="link_target",
        acquisition_method="archived_page_outbound_link",
        parse=parse_expansion_links,
    ),
    "expansion_directory": SourceSpec(
        key="expansion_directory",
        source_name="page_directory",
        evidence_type="dated_directory",
        acquisition_method="archived_directory_page",
        parse=parse_expansion_directory,
    ),
    "cdx_snapshot": SourceSpec(
        key="cdx_snapshot",
        source_name="ia_cdx_bulk",
        evidence_type="cdx_timestamp",
        acquisition_method="ia_cdx_collapsed_query",
        parse=parse_cdx_snapshot,
    ),
}
