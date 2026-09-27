"""Registered bulk sources: the parser and evidence semantics of each.

Adding a source means writing a parser that yields BulkRecord rows and
registering a SourceSpec here; the shared loader in bulk.py handles the
rest (canonicalization, staging, evidence routing, audit, metrics).
"""

import csv
import gzip
import json
import re
import zipfile
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from ark.bulk import BulkRecord, SourceSpec
from ark.canonical import to_registrable
from ark.cdx import evidence_years as cdx_evidence_years
from ark.ingest import YEARS
from ark.journal import open_journal

# The evidence URL every UDRP row falls back to: the consolidated list itself, so a
# reviewer can find any proceeding by its number.
UDRP_LIST_URL = "https://www.icann.org/udrp/proceedings-list.htm"

# Where an RDAP query went before direct registry routing was added, so it
# rebuilds the record URL of a journal written without one. The client that wrote those
# journals is gone: the registries' terms forbid bulk RDAP.
RDAP_REDIRECTOR = "https://rdap.org/domain/"

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


# The Internet Archive's "Not Your Parents' Web" rows, eight space-delimited fields:
#   queried-url  SURT  timestamp  original-url  mime  status  digest  length
# Two sources share the layout. The first-capture index holds each URL's EARLIEST
# capture only; a TimeMap holds every capture of one URL, one per line. Either way
# field 3 is the crawler's own 14-digit stamp and a row evidences exactly the year it
# names and no other (IV.7).
_NYPW_FIELDS = 6


def _parse_nypw(path: Path, stats: Counter, label: str) -> Iterator[BulkRecord]:
    """Yield one record per in-window HTTP-200 capture row."""
    with _open_text(path) as fh:
        for line in fh:
            stats["lines"] += 1
            parts = line.split()
            if len(parts) < _NYPW_FIELDS:
                stats["malformed"] += 1
                continue
            timestamp, original, status = parts[2], parts[3], parts[5]
            if len(timestamp) != 14 or not timestamp.isdigit():
                stats["malformed"] += 1
                continue
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
                evidence_value=f"{label} {timestamp}",
                evidence_url=f"https://web.archive.org/web/{timestamp}/{original}",
            )


def parse_nypw_firstcdx(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per in-window HTTP-200 first capture."""
    yield from _parse_nypw(path, stats, "nypw first capture")


def parse_nypw_timemap(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per in-window HTTP-200 capture listed in a TimeMap.

    Same rows as the first-capture index, except a URL appears once per capture rather
    than once in total, so it can carry a year for a domain the store already holds.
    """
    yield from _parse_nypw(path, stats, "nypw timemap capture")


def parse_nypw_timemap_nonok(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per in-window capture whose stored status is NOT 200.

    The lane `_parse_nypw` throws away. A 302, 404 or 500 row says a server accepted the
    connection and answered at the stamped instant, which needs the name delegated
    exactly as a 200 does: the status describes the resource, not the registration, so
    this is the same evidence class on the same bytes. A separate spec rather than a
    relaxation of the parser above, so the 200 lane stays the control group.
    """
    with _open_text(path) as fh:
        for line in fh:
            stats["lines"] += 1
            parts = line.split()
            if len(parts) < _NYPW_FIELDS:
                stats["malformed"] += 1
                continue
            timestamp, original, status = parts[2], parts[3], parts[5]
            if len(timestamp) != 14 or not timestamp.isdigit():
                stats["malformed"] += 1
                continue
            year = int(timestamp[:4])
            if year not in YEARS:
                stats["out_of_window"] += 1
                continue
            # a status that is not a three-digit HTTP code is not a server
            # answering, so it evidences nothing; none appear in the corpus as
            # ingested, and the guard keeps a future partition honest
            if len(status) != 3 or not status.isdigit():
                stats["no_response"] += 1
                continue
            if status == "200":
                stats["ok_lane"] += 1
                continue
            yield BulkRecord(
                raw=original,
                year=year,
                evidence_value=f"nypw timemap capture status {status} {timestamp}",
                evidence_url=f"https://web.archive.org/web/{timestamp}/{original}",
            )


# A `split_usenet.py` journal: one JSON object per (domain, year), carrying the
# Message-ID of the post that dated it. Two specs read the same format because
# the split has already decided which half is which; the evidence type is the
# whole difference between them.
def _parse_usenet_journal(path: Path, stats: Counter) -> Iterator[BulkRecord]:
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
            domain, year = record.get("domain"), record.get("year")
            if not domain or year not in YEARS:
                stats["malformed"] += 1
                continue
            group = record.get("group", "usenet")
            # A journal carrying its own evidence URL is believed. The fallback below
            # composes an archive.org Usenet item name out of the hierarchy, which is
            # right for Usenet and a dead link for anything else reusing this parser,
            # and item-level traceability makes a dead link a defect.
            url = record.get("url") or (f"https://archive.org/details/usenet-{group.split('.')[0]}")
            yield BulkRecord(
                raw=domain,
                year=year,
                # the Message-ID is the auditable identifier: globally unique by
                # design, so a reviewer can name the exact post behind a year
                evidence_value=f"{group} {record.get('message_id', '')}".strip(),
                evidence_url=url,
            )


# A `collect_usenet_whois.py` journal, after the corroboration split: one JSON object per
# (domain, creation year), carrying the registry date string that dated it and the
# Message-ID of the post it was pasted into.
#
# **Does not reuse `_parse_usenet_journal`** despite the same shape:
# `evidence_year_matches_its_value` reads the first four-digit run out of the value, and a
# Usenet value `"<group> <message_id>"` carries incidental digits, so
# `microsoft.public.win2000.dns` reads as 2000 on every row. The registry's own date goes
# first so the check tests what it means to.
def _parse_usenet_whois_journal(path: Path, stats: Counter) -> Iterator[BulkRecord]:
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
            domain, year = record.get("domain"), record.get("year")
            if not domain or year not in YEARS:
                stats["malformed"] += 1
                continue
            created = record.get("created") or f"{year}"
            if not created.startswith(str(year)):
                # the stamp and the filed year must agree, or the row is not
                # evidence of anything the check could verify
                stats["created_year_mismatch"] += 1
                continue
            group = record.get("group", "usenet")
            yield BulkRecord(
                raw=domain,
                year=year,
                evidence_value=(
                    f"record created {created} pasted in {group} {record.get('message_id', '')}"
                ).strip(),
                evidence_url=record.get("url")
                or f"https://archive.org/details/usenet-{group.split('.')[0]}",
            )


# The consolidated ICANN list of UDRP proceedings: one dispute per row, an explicit
# commencement date, the disputed name in its own column, all five providers that heard
# cases in the window. `artifact_listing`, no corroboration split.
#
# The year is the COMMENCEMENT date, never the decision date: a case commenced in late
# 2000 may be decided in 2001, and the domain existed when the complaint was filed.
_REGISTRY_STAMP = re.compile(r"\b((?:199[6-9]|200[01])\d{4})\b")


def parse_registry_items(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """A fleet price leg's items for a registry list: `{host, year, text}` per line.

    `text` is the registry's own stamp, quoted by the extractor (`DK Zonen header
    20011217`), and it must carry the date whose year the row is filed under: the integrity
    gate reads the year out of the value, so a stamp naming another year is refused here
    rather than failing there. `host` is the registered name; a hostname beneath it is not
    what a zone list asserts, so the record is filed at the name as listed.
    """
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
            host, year, text = record.get("host"), record.get("year"), str(record.get("text") or "")
            if not host or year not in YEARS:
                stats["malformed"] += 1
                continue
            stamp = _REGISTRY_STAMP.search(text)
            if not stamp or not stamp.group(1).startswith(str(year)):
                stats["stamp_does_not_name_the_year"] += 1
                continue
            yield BulkRecord(
                raw=str(host).lower(),
                year=int(year),
                evidence_value=f"{stamp.group(1)}: {text.strip()}",
                evidence_url=record.get("url"),
            )


def parse_udrp_proceedings(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """A `collect_udrp_proceedings.py` journal: one JSON object per (domain, year)."""
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
            domain, year = record.get("domain"), record.get("year")
            if not domain or year not in YEARS:
                stats["malformed"] += 1
                continue
            proceeding = record.get("proceeding", "").strip()
            commenced = record.get("commenced", "").strip()
            if not proceeding or not commenced.startswith(str(year)):
                # The value must name the year it is filed under, which the integrity
                # gate checks, and the proceeding number is what makes a row auditable.
                stats["missing_identifier"] += 1
                continue
            yield BulkRecord(
                raw=domain,
                year=year,
                # The commencement date leads, so the FIRST four-digit run in the value
                # is the filed year, which is what `evidence_year_matches_its_value`
                # reads. The proceeding number first fails it twice over: NAF's
                # `FA0092016` offers `0092`, and `D2000-` commenced in January 2001
                # offers 2000 against an assigned 2001.
                evidence_value=f"commenced {commenced} UDRP {proceeding}",
                evidence_url=record.get("url") or UDRP_LIST_URL,
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


# The SOA serial of an InterNIC zone, `YYYYMMDDNN`, which is the artifact's own statement
# of when it was generated. Read from inside the file rather than from its name or its
# capture, because a date that would change if the artifact were re-published tomorrow dates
# nothing: this one would not.
_ZONE_SERIAL = re.compile(r"\b(19[89]\d)(?:0[1-9]|1[0-2])(?:[0-2]\d|3[01])\d\d\b")


def _internic_zone_header(path: Path) -> tuple[str, int] | None:
    """The zone's apex and year, both taken from its own SOA record.

    The SOA spans several lines: the owner name is the first token of the first, and the
    serial sits on the line commented `;serial`. Neither the filename nor the Wayback
    capture is consulted, so a file renamed on the way here still dates itself correctly.
    """
    apex = None
    with _open_text(path) as fh:
        for index, line in enumerate(fh):
            tokens = line.split()
            if apex is None and "SOA" in tokens[1:4]:
                apex = tokens[0].rstrip(".").upper()
                continue
            if apex is not None and ";serial" in line:
                match = _ZONE_SERIAL.search(line)
                if match is None:
                    return None
                return apex, int(match.group(1))
            if index > 40:
                break
    return None


def parse_internic_zone(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per domain delegated in an InterNIC top-level zone file.

    **The owner of an NS record is the delegation; the target is a nameserver.** That one
    distinction is the whole parser: getting it backwards measured 2,018 claimed net-new
    pairs against 336 real, 99.8% of the right-hand sides being nameserver names. Only the
    owner counts, and only exactly one label under the apex.

    `artifact_listing`, self-dating, no corroboration split, no later year emitted. Deeper
    owners are SKIPPED, never truncated: `sub.foo.org` as `foo.org` is a second claim.
    """
    header = _internic_zone_header(path)
    if header is None:
        stats["no_soa_serial"] += 1
        return
    apex, year = header
    if year not in YEARS:
        stats["out_of_window_file"] += 1
        return
    suffix = "." + apex
    with _open_text(path) as fh:
        for line in fh:
            tokens = line.split()
            if len(tokens) < 3 or "NS" not in tokens[1:4]:
                continue
            stats["ns_records"] += 1
            owner = tokens[0].rstrip(".").upper()
            if owner == apex:
                stats["apex_delegation"] += 1
                continue
            if not owner.endswith(suffix):
                # Either a continuation line, whose first token is the TTL, or glue for a
                # nameserver in another zone. Both are counted so a silent drop cannot hide.
                stats["owner_outside_zone"] += 1
                continue
            if "." in owner[: -len(suffix)]:
                stats["deeper_than_one_label"] += 1
                continue
            yield BulkRecord(
                raw=owner.lower(),
                year=year,
                evidence_value=f"internic {apex.lower()} zone serial {_serial_of(path)}",
            )


# IEDR (`.ie`) regenerated its WHOLE register as static A-Z pages, captured by Wayback.
# Two editions, two wordings: `/statistics/` writes "updated automatically at 14:51 GMT on
# Friday, 21 December 2001", the earlier `/lists/` tree "Last updated 27 Nov 1999".
#
# JPNIC's register of every `.jp` name, frozen on a personal mirror at 1999-04-30. Lines 3
# to 10 carry JPNIC's open-document notice: free reprint with the copyright notice.
#
# **Three traps, each of which produced a wrong number.**
#
# 1. **Shift-JIS, split on CRLF and never by `splitlines()`.** Japanese organisation names
#    contain bytes Python treats as line breaks (NEL, 0x85), shattering comments into
#    phantom entries.
# 2. **A label is not a domain.** The suffix comes from the section header: `AAA` under
#    `------ AD domains:` is `aaa.ad.jp`. Geographic labels contain dots of their own
#    (`CITY.CHITOSE`), so a dot-free label pattern reads 65 Hokkaido entries as 1.
# 3. **45,662 reserved and 923 abolished entries were never registrations.** Counting the
#    municipal and school names JPNIC held back inflates the source 4.4x.
#
# Checked against the file's own arithmetic: each section declares its size, 62 of 63
# reconcile exactly, total 72,770 against a declared 72,769.
_JPNIC_SECTION = re.compile(r"^-{3,}\s*(\S+)\s+domains:\s*([\d,]+)\s*\(([\d,]+)\)")
_JPNIC_ENTRY = re.compile(r"^\(?\s*([A-Za-z0-9][A-Za-z0-9\-.]*)\s+#")
_JPNIC_STAMP = re.compile(r"Registered Domains in JP \(([A-Za-z]{3} \d{1,2} (\d{4}))\)")
_JPNIC_RESERVED = "\u4e88\u7d04\u30c9\u30e1\u30a4\u30f3\u540d"  # reserved domain name
_JPNIC_ABOLISHED = "\u5ec3\u6b62"  # abolished


def parse_jpnic_register(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per registered `.jp` name, dated by the file's own stamp."""
    text = path.read_bytes().decode("shift_jis", errors="replace")
    lines = text.split("\r\n")

    stamp = _JPNIC_STAMP.search(text)
    if not stamp:
        stats["no_header_stamp"] += 1
        return
    year = int(stamp.group(2))
    if year not in YEARS:
        stats["out_of_window_edition"] += 1
        return

    suffix: str | None = None
    for line in lines:
        section = _JPNIC_SECTION.match(line)
        if section:
            tag = section.group(1).lower()
            suffix = "jp" if tag == "jp" else f"{tag}.jp"
            continue
        if suffix is None:
            continue
        entry = _JPNIC_ENTRY.match(line)
        if not entry:
            continue
        if _JPNIC_RESERVED in line:
            stats["reserved_never_registered"] += 1
            continue
        if _JPNIC_ABOLISHED in line:
            stats["abolished"] += 1
            continue
        name = to_registrable(f"{entry.group(1).lower()}.{suffix}")
        if not name:
            stats["not_registrable"] += 1
            continue
        yield BulkRecord(
            raw=name,
            year=year,
            evidence_value=f"jpnic register listing {stamp.group(1)}",
        )


_IEDR_FOOTER = re.compile(
    r"(?:updated\s+automatically\s+at|last\s+updated)\s+.{0,80}?((?:19|20)\d\d)",
    re.I | re.S,
)
# Only a letter page is a register listing. `stalled.html` is PENDING APPLICATIONS, which
# are names nobody had registered yet, and reading it would manufacture registrations that
# never happened. `weekly.html` and `dom-list.html` are the registry writing about itself.
# `*ch: someone@example.com 19980315`. The date is the LAST 8-digit token on the line
# and the capture group is deliberately narrow: the address before it must never be read.
_RIPE_CHANGED = re.compile(r"^\*ch:.*?(\d{8})\s*$")
# The same attribute spelled in full. FUNET's whole-database file uses the abbreviated
# keys, its `split/` files use the long ones, so both spellings are needed to read the
# same audit trail out of two editions of one database.
_RIPE_CHANGED_LONG = re.compile(r"^changed:.*?(\d{8})\s*$")


def parse_ripe_dbase_changed(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per dated `changed:` transaction on a RIPE domain object.

    You cannot modify a registry object that does not exist, so `19980315` records that the
    registration existed then. Each `changed:` line is its own record for its own year,
    which rule 6 asks for and a creation date cannot give: the audit trail under the 1999
    snapshot reaches 1996, 1997 and 1998 that the snapshot's own date cannot.

    **Personal data must never leave this function, and the regexp is the guard.** A
    `changed:` line is `address SPACE date`, so an address is on all 2,045,382 lines this
    touches. The pattern captures only the trailing 8-digit group and the record carries
    only the date. `tests/test_sources.py` fails on a leak: that is the promise to RIPE NCC.

    **Scope.** `.arpa` reverse zones are skipped; a date outside 1996-2001 is counted and
    dropped; only the leading four digits are read, so a malformed day cannot move the year.
    """
    yield from _ripe_changed_records(path, stats, "*dn:", _RIPE_CHANGED)


def _ripe_changed_records(
    path: Path, stats: Counter, name_key: str, changed: re.Pattern[str]
) -> Iterator[BulkRecord]:
    """The reading itself, over whichever spelling of the two keys an edition uses."""
    year_of: dict[str, int] = {}
    current: str | None = None
    with _open_text(path) as fh:
        for line in fh:
            stats["lines"] += 1
            if line.startswith(name_key):
                value = line[len(name_key) :].strip()
                current = None if value.upper().endswith((".ARPA", ".ARPA.")) else value
                if current is None:
                    stats["reverse_zone_skipped"] += 1
                continue
            if current is None:
                continue
            found = changed.match(line.rstrip("\n"))
            if found is None:
                continue
            stats["changed_lines"] += 1
            year = int(found.group(1)[:4])
            if year not in YEARS:
                stats["changed_out_of_window"] += 1
                continue
            stats["changed_in_window"] += 1
            # One record per (object, year); a second update in the same year adds nothing.
            key = f"{current}\t{year}"
            if key in year_of:
                stats["same_year_repeat"] += 1
                continue
            year_of[key] = year
            yield BulkRecord(
                raw=current,
                year=year,
                evidence_value=f"ripe_changed:{found.group(1)}",
            )


def parse_ripe_dbase_split_2004(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """The same `changed:` audit trail, read out of FUNET's 2004-11-09 `split/` edition.

    Not a duplicate of the 1999 edition: a file frozen 1999-08-03 cannot carry a later
    transaction, so the 2000 and 2001 `changed:` lines (16,536 and 21,507) exist only here.
    Small because it is 96.2% reverse DNS, 6,160 forward names of 162,408 objects. The
    claim, the personal-data guard and the rule 6 reading are `parse_ripe_dbase_changed`'s;
    only the two key spellings differ.
    """
    yield from _ripe_changed_records(path, stats, "domain:", _RIPE_CHANGED_LONG)


# Edelman's whois transcriptions. A record begins at a BOLD subject and runs to the
# next one; the creation date sits inside it as `Registered on: Jun 28, 2001`.
_ED_SUBJECT = re.compile(r"<b>\s*(?:<a[^>]*>)?\s*([A-Za-z0-9][A-Za-z0-9.\-]*\.[A-Za-z]{2,})", re.I)
_ED_REGISTERED = re.compile(
    r"Registered on:\s*</i>\s*</font>\s*([A-Za-z]{3})[a-z]*\s+(\d{1,2}),\s*(\d{4})", re.I
)
# The typo-domain pages use a THIRD format and print three dates on one line:
# `Dates of creation / last modification / expiration:</span> 25-May-2001 / 18-Jun-2002
# / 25-May-2003`. Only the FIRST is the creation date. Anchored so the second and third
# cannot match: taking the wrong one would date a domain to its expiry.
_ED_CREATION_TRIPLE = re.compile(
    r"Dates of creation[^<]*</span>\s*(\d{1,2})-([A-Za-z]{3})-(\d{4})", re.I
)
_ED_MONTHS = {
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
}


def parse_edelman_whois(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per domain whose OWN whois creation date Edelman transcribed.

    **The record is delimited by its bold subject, and only that subject takes the date.**
    Pairing a domain with the nearest date overstates the source by a measured 47%: a block
    also names the registrar, `google.com`, `web.archive.org` and, on typo pages, the
    redirect target and the correctly-spelled original.

        <B><a href="http://A1-DESIGNS.COM">A1-DESIGNS.COM</a></b>
        <BR>Registered on: Jun 28, 2001  by registrar: BULKREGISTER.COM, INC.

    Everything else is counted as `other_domain_ignored`, the number to watch on re-verify.

    **Three formats, and the third is the trap.** `nicgod` pages print `Registered on:`.
    `renewals` pages carry 2002 dates and fall out of window by themselves. `typo-domains`
    pages print THREE dates on one line, `Dates of creation / last modification /
    expiration: ...`, and only the FIRST is the creation date, so the pattern is anchored
    on the label.

    `whois_creation`, rule 6: the year of the transcribed date, no other. No `Registered
    on:` line means skip, which is common. A human transcription of a registry record is
    the weakest dating provenance here, which is why the subject-binding must be exact.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    marks = list(_ED_SUBJECT.finditer(text))
    stats["subject_blocks"] += len(marks)
    for index, mark in enumerate(marks):
        stop = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        block = text[mark.start() : stop]
        registered = _ED_REGISTERED.search(block)
        if registered is not None:
            month, year_text = registered.group(1), registered.group(3)
            stats["dated_by_registered_on"] += 1
        else:
            triple = _ED_CREATION_TRIPLE.search(block)
            if triple is None:
                stats["no_creation_date"] += 1
                continue
            month, year_text = triple.group(2), triple.group(3)
            stats["dated_by_creation_triple"] += 1
        if month.lower() not in _ED_MONTHS:
            stats["unparseable_month"] += 1
            continue
        year = int(year_text)
        if year not in YEARS:
            stats["created_out_of_window"] += 1
            continue
        # Everything in the block that is NOT the subject is deliberately dropped.
        others = len(re.findall(r"[a-z0-9][a-z0-9\-]*\.(?:com|net|org)\b", block, re.I)) - 1
        stats["other_domain_ignored"] += max(0, others)
        stats["records"] += 1
        yield BulkRecord(
            raw=mark.group(1),
            year=year,
            evidence_value=f"edelman_whois_created:{year}",
        )


# `junkfilter-(dated|cand).<YYYYMMDD>.txt`, written by `split_junkfilter.py`. One
# canonical domain per line; the lane is in the name and so is the edition date.
_JF_FILE = re.compile(r"^junkfilter-(dated|cand)\.(\d{4})(\d{2})(\d{2})\.txt$")


def parse_junkfilter_split(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per name in one lane of one junkfilter edition.

    **What dates an edition: three machine-written stamps agreeing.** The HTTP
    `last-modified` header, the release directory's ISO name, and the in-body
    `$Id: junkfilter,v 2.36 2001/05/28 20:00:08 gsutter Exp $`. All thirteen in-window
    editions verified header-to-directory at collection, headers in
    `data/raw/junkfilter/last-modified.txt`.

    **`dated_directory` for the corroborated lane, `link_target` for the other**, the list
    being hand-maintained: the date is a machine's and the name is a person's.
    `split_junkfilter.py` decides before ingest; this parser reads the lane it is given.
    An edition evidences its own date and nothing else, and an entry means the maintainer
    received mail from that host, which is not a resolution.
    """
    match = _JF_FILE.match(path.name)
    if match is None:
        stats["not_a_junkfilter_lane"] += 1
        return
    year = int(match.group(2))
    if year not in YEARS:
        stats["edition_out_of_window"] += 1
        return
    stamp = "".join(match.groups()[1:])
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        name = line.strip()
        if not name:
            continue
        stats["names"] += 1
        yield BulkRecord(raw=name, year=year, evidence_value=f"junkfilter:{stamp}")


# `chastity-(dated|cand).<YYYYMMDD>.txt`, written by `split_chastity.py`. One
# canonical domain per line; the lane is in the name and so is the edition date.
_CHASTITY_FILE = re.compile(r"^chastity-(dated|cand)\.(\d{4})(\d{2})(\d{2})\.txt$")


def parse_chastity_split(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per name in one lane of the chastity-list edition.

    **What dates the edition, and a program wrote it.** The tar member header `Dec 14 2001`
    on all 258 members of `chastity-list_0.5.orig.tar.gz`, corroborated from inside by 209
    per-date diff filenames, `domains.20010813.diff` to `domains.20011201.diff`, in window
    and monotone.

    **`dated_directory` for the corroborated lane, `link_target` for the other**, the list
    being hand-maintained. `split_chastity.py` decides before ingest. 94.0% is corroborated.

    **The edition evidences 2001 and nothing else**: all three releases are December 2001.
    Pricing it at 1999 or 2000 overstates the headroom 141x and 39x, a blacklist's
    population having been registered in the years just before its compile.
    """
    match = _CHASTITY_FILE.match(path.name)
    if match is None:
        stats["not_a_chastity_lane"] += 1
        return
    year = int(match.group(2))
    if year not in YEARS:
        stats["edition_out_of_window"] += 1
        return
    stamp = "".join(match.groups()[1:])
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        name = line.strip()
        if not name:
            continue
        stats["names"] += 1
        yield BulkRecord(raw=name, year=year, evidence_value=f"chastity-list:{stamp}")


# `granitecanyon-(dated|cand).<YYYYMMDD>.txt`, written by `split_granitecanyon.py`.
# One canonical zone name per line; the lane is in the name and so is the edition.
_GC_FILE = re.compile(r"^granitecanyon-(dated|cand)\.(\d{4})(\d{2})(\d{2})\.txt$")


def parse_granitecanyon_split(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per zone in one lane of one Granite Canyon edition.

    **What dates one item: a stamp the operator's own program wrote.** Each reject edition
    prints its generation instant, `Rejected Zone List: 7-May-2001 22:11 GMT`, and the
    Wayback capture fixes when the file existed. All six in-window editions agree with
    their capture stamps; the 1999 prune list is dated by `status.shtml` and its filename.
    A row is Granite Canyon's nameserver holding that zone in BIND at that instant.

    **`artifact_listing` for the corroborated lane, `link_target` for the other**, the zone
    name having been typed into a submission form. `split_granitecanyon.py` decides.

    An unusual population worth having: 60.4% and 46.8% held, against 87-99% for authority
    corpora and 98.4-99.6% for visitor logs. A zone is not a page, so no crawler reaches it
    through a link and the artifact is not head-selected.
    """
    match = _GC_FILE.match(path.name)
    if match is None:
        stats["not_a_granitecanyon_lane"] += 1
        return
    year = int(match.group(2))
    if year not in YEARS:
        stats["edition_out_of_window"] += 1
        return
    stamp = "".join(match.groups()[1:])
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        name = line.strip()
        if not name:
            continue
        stats["zones"] += 1
        yield BulkRecord(raw=name, year=year, evidence_value=f"granitecanyon:{stamp}")


# `cctldcap-(dated|cand).<slug>.<YYYY>.txt`, written by `split_cctld_capture.py`.
# One canonical domain per line; the lane is in the name and so is the year.
_CCTLDCAP_FILE = re.compile(r"^cctldcap-(dated|cand)\.([a-z0-9]+)\.(\d{4})\.txt$")


def parse_cctld_capture_split(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per name in one lane of one capture-dated ccTLD register listing.

    **Four artifacts, two kinds of thing, so the split differs per artifact and
    `split_cctld_capture.py` decides it, never this parser.** A registry printing its own
    register takes no split; a third party's hand-kept directory takes it like any list.

    **What dates one item, per artifact.** SaudiNIC's `AllSA`, generated by `indexing.cgi`
    out of the register, carries no in-body date and is fixed by its Wayback capture at
    2001-04-14 (`cdx_timestamp`). NU Domain's `notRenewed.cfm` carries a machine-written
    `Expired` date per ROW, so the year comes from the row. ISOC-IL's `domains.html`
    self-stamps `Document Modified: 3-1-98`, capture 1998-01-20.

    **NIC Malta is carried at 1.8 EE and only for the record**, its own text refusing the
    liveness claim: "some of the links below may still be unreachable", "This directory is
    not updated regularly". Kept so the negative is measured against the 1,470.5 EE the
    source register once priced it at.

    A name on an expiry list was registered UP TO that date and implies nothing about
    another year: `.nu`'s one row expiring in 2003 is dropped, not read as 2001.
    """
    match = _CCTLDCAP_FILE.match(path.name)
    if match is None:
        stats["not_a_cctld_capture_lane"] += 1
        return
    slug, year = match.group(2), int(match.group(3))
    if year not in YEARS:
        stats["edition_out_of_window"] += 1
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        name = line.strip()
        if not name:
            continue
        stats["names"] += 1
        yield BulkRecord(raw=name, year=year, evidence_value=f"cctld_capture:{slug}:{year}")


# MYNIC's fortnightly `Domain Name Listing`, one page per half-month, as fetched.
# A day heading, then tab-separated `New` or `Delete` rows under it.
_MYNIC_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
    "|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)
_MYNIC_DAY = re.compile(rf"(\d{{1,2}})\s+({_MYNIC_MONTHS})\s+(\d{{4}})", re.I)
_MYNIC_ROW = re.compile(r"^(New|Delete)\t+([a-z0-9][a-z0-9.\-]*\.my)\s*$", re.I | re.M)


def parse_mynic_listing(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per `New` or `Delete` row of one MYNIC listing page.

    **What dates one item**: the per-day heading above the row, `15 March 2001`, carried
    forward from the most recent heading, which is why the file is walked in order rather
    than scanned for names. Both actions date that year only: a name deleted on 15 March
    2001 was in the register until that day.

    **No corroboration split, settled on a test.** MYNIC's own monthly statistics table
    gives March 2001 as New 850 / Delete 166 against New 850 / Delete 165 parsed from the
    listing halves; a hand-compiled list cannot reproduce a registry's counts 850/850.
    Alphabetical ordering is NOT the argument: sorting holds in 75.2% of 472 groups only.

    Only the `-1` and `-2` half-month pages carry names; the bare-month pages are the
    statistics tables and are counted and skipped.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    if "domain name listing" not in raw.lower():
        stats["not_a_listing_page"] += 1
        return
    headings = [(m.start(), int(m.group(3))) for m in _MYNIC_DAY.finditer(raw)]
    for row in _MYNIC_ROW.finditer(raw):
        year = None
        for position, heading_year in headings:
            if position < row.start():
                year = heading_year
            else:
                break
        if year is None:
            stats["row_before_any_day_heading"] += 1
            continue
        if year not in YEARS:
            stats["row_out_of_window"] += 1
            continue
        stats[row.group(1).lower()] += 1
        yield BulkRecord(raw=row.group(2).lower(), year=year, evidence_value=f"mynic:{path.stem}")


# `<host>-<warnsh|todelsh>-<YYYYMMDDHHMMSS>.html`, written by the CO.ZA collector.
_COZA_FILE = re.compile(r"^([a-z_]+)-(warnsh|todelsh)-(\d{4})\d{10}\.html$")
# The registry's CGI links each label to its own whois lookup.
_COZA_LABEL = re.compile(r'<A HREF="[^"]*Domain=([^"&]+)"', re.I)
# The label is truncated to the column width, so anything this long may be a fragment.
COZA_TRUNCATION_WIDTH = 16


def parse_coza_queue(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per label in one capture of a CO.ZA suspension or deletion queue.

    **What dates one item**: the Wayback capture stamp in the filename, neither page
    carrying an in-body date. `todel.sh` is the deletion shortlist, `warn.sh` the suspension
    queue; either way the registry asserts the name is in its register at that instant.
    **No corroboration split**: these are shell CGI reading the register.

    **640 labels are dropped, and the defect is in the artifact.** The CGI prints bare
    labels in fixed 16-character columns and truncates to fit **in the `href` as well as the
    anchor text**, so `sahomeimprovement` is served as `sahomeimprovemen`: 303 labels of 15
    characters against a spike of 640 at exactly 16. A truncated label mints a well-formed
    domain that never existed, which no `ark check` invariant could catch, so every label of
    exactly the column width is refused.
    """
    match = _COZA_FILE.match(path.name)
    if match is None:
        stats["not_a_coza_capture"] += 1
        return
    year = int(match.group(3))
    if year not in YEARS:
        stats["capture_out_of_window"] += 1
        return
    raw = path.read_text(encoding="utf-8", errors="replace")
    if "shortlisted for" not in raw.lower():
        stats["not_a_queue_page"] += 1
        return
    for found in _COZA_LABEL.finditer(raw):
        label = found.group(1).strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", label):
            stats["label_malformed"] += 1
            continue
        if len(label) >= COZA_TRUNCATION_WIDTH:
            stats["label_possibly_truncated"] += 1
            continue
        stats["labels"] += 1
        yield BulkRecord(
            raw=f"{label}.co.za",
            year=year,
            evidence_value=f"coza:{match.group(2)}:{path.stem.rsplit('-', 1)[1]}",
        )


# `fac-(dated|cand).<YYYY>.tsv`, written by `split_fac.py`. `<domain>\t<year>` per line,
# where the year is the filing's own signature date and NOT its `AUDITYEAR`.
_FAC_FILE = re.compile(r"^fac-(dated|cand)\.(\d{4})\.tsv$")


def parse_fac_filings(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per (domain, signature year) in one lane of one FAC filing year.

    **What dates one item.** The signature date on that row, `AUDITEEDATESIGNED` or
    `CPADATESIGNED`, both `mm/dd/yyyy` in GSA's historic data dictionary. The address beside
    it is the auditee's or the audit firm's own.

    **The file's own `AUDITYEAR` is a trap and must not be used.** 1998 filings are
    routinely signed in 1999 and FY2001 audits in 2002; screening on the signature date
    drops 18,979 of 75,311 e-mail fields, 25.2%, all of which `AUDITYEAR` imports silently.

    **The corroboration split applies, because a person typed the address into a form**:
    `campell.edu`, `clakamas.or.us`, `kl2.ca.us` with `l` for `1`, and a further 18.0% are a
    character prepended to a name the store already dates. The typo upper bound is 69.7%,
    the highest in the register, so the uncorroborated lane parks as `link_target`.

    **Provenance.** `app.fac.gov` serves `Disallow: /`, so the ZIPs were downloaded by hand
    and all four SHA1s verified against GSA's published `.sha1` files. Terms are the landing
    page's "provided as-is for historical research" and US federal public domain.
    """
    match = _FAC_FILE.match(path.name)
    if match is None:
        stats["not_a_fac_lane"] += 1
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        domain, _, year_text = line.partition("\t")
        if not domain or not year_text:
            continue
        year = int(year_text)
        if year not in YEARS:
            stats["signature_out_of_window"] += 1
            continue
        stats["filings"] += 1
        yield BulkRecord(raw=domain, year=year, evidence_value=f"fac_signature:{year}")


# `cctld-<registry>-<tld>-<YYYYMMDD>.html`, written by the ccTLD collector. The
# trailing date is the artifact's own stamp: TWNIC prints `更新時間: 2001/8/27 20:0:31`
# on the page, IDNIC's rows carry a due date each.
_CCTLD_FILE = re.compile(r"^cctld-([a-z0-9]+)-([a-z]{2,3})-(\d{4})(\d{2})(\d{2})\.html?$", re.I)
# A name paired with a `DD-MON-YYYY` date in the same row, which is how IDNIC's
# unpaid-fees table is laid out once the tags are collapsed.
_CCTLD_ROW_DATE = re.compile(
    r"\|([a-z0-9][a-z0-9.\-]*\.%s)\|+\s*\|*\s*(\d{2})-([A-Za-z]{3})-(\d{4})", re.I
)
# Indonesian and English month abbreviations. Only the year is used, so the map
# exists to prove the field is a date rather than to compute anything.
_CCTLD_MONTHS = {
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
    "mei",
    "agu",
    "okt",
    "des",
    "ags",
    "peb",
    "nop",
}


def parse_cctld_register_inbody(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per name on a ccTLD register listing that dates itself.

    A registry that wrote its register to a static page carrying its own machine-written
    timestamp, so no corroboration split.

    **Two dating routes, and the ROW wins when it has one.** TWNIC's frozen-domain list
    stamps the page, `更新時間: 2001/8/27 20:0:31`, dating every name on it. IDNIC's
    unpaid-fees table prints a `Jatuh Tempo` due date per row, the boundary of that
    registration's paid period, so the row's year wins over the file's.

    Only names under the registry's own namespace are read: the filename declares the TLD,
    so an ad or a mailto on the page cannot become evidence.

    **The collector must pin the capture and record the size**: the CDX `length` column is
    the compressed WARC record size and a big uniform table compresses hardest, TWNIC 77,565
    in the index against 624,921 on the wire, IDNIC 23,977 against 251,567. Ranking
    candidate pages by CDX length under-ranks exactly the pages worth having.
    """
    match = _CCTLD_FILE.match(path.name)
    if match is None:
        stats["not_a_cctld_listing"] += 1
        return
    registry, tld, file_year = match.group(1), match.group(2).lower(), int(match.group(3))
    if file_year not in YEARS:
        stats["file_stamp_out_of_window"] += 1
        return

    raw = path.read_bytes().decode("latin-1", errors="replace")
    flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", raw))

    dated: dict[str, int] = {}
    for row in re.finditer(_CCTLD_ROW_DATE.pattern % re.escape(tld), flat, re.I):
        if row.group(3).lower() not in _CCTLD_MONTHS:
            continue
        year = int(row.group(4))
        if year in YEARS:
            dated[row.group(1).lower()] = year

    names = set(re.findall(rf"[a-z0-9][a-z0-9.\-]*\.{re.escape(tld)}\b", flat, re.I))
    stats["names_on_page"] += len(names)
    stats["rows_with_own_date"] += len(dated)
    page_stamp = f"{match.group(3)}{match.group(4)}{match.group(5)}"
    for name in sorted(n.lower() for n in names):
        row_year = dated.get(name)
        year = row_year if row_year is not None else file_year
        # **The evidence value must carry the date that justifies THIS year, not the
        # page's.** `evidence_year_matches_its_value` compares the year inside the value
        # against the year the row is filed under, and a row-dated name filed under 1998
        # beside a value reading `@20010415` fails it. That is the invariant doing its job:
        # citing the page stamp for a year the page stamp does not support would be a
        # provenance lie even though the year itself is right.
        stamp = str(row_year) if row_year is not None else page_stamp
        stats["dated_from_row" if row_year is not None else "dated_from_page"] += 1
        yield BulkRecord(
            raw=name,
            year=year,
            evidence_value=f"cctld_register:{registry}.{tld}@{stamp}",
        )


# The CA Domain Registry's approval notices. Records are blocks of aligned
# `Field:  value` lines, so both patterns are anchored to the line start.
_CA_SUBDOMAIN = re.compile(r"^Subdomain:\s*(\S+)\s*$", re.M)
_CA_APPROVED = re.compile(r"^Date-Approved:\s*(\d{4})/(\d{2})/(\d{2})\s*$", re.M)


def parse_can_domain_registry_notices(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per `.ca` subdomain the registry approved in window.

    The CA Domain Registry ran approvals in public, posting a structured record to
    `can.domain` for each. 37,782 survive, carrying 37,578 `Date-Approved:` fields:

        Subdomain:      privacy.ca
        Date-Received:  1999/06/23
        Date-Approved:  1999/06/30
        Date-Modified:  2000/08/23

    The approval is the registry's own machine-formatted act, so `whois_creation`, and rule
    6 costs most of the file: an approval date evidences its own year only. 1996: 7,766 /
    1997: 9,520 / 1998: 15,133 / 1999: 4,473 / 2000: 0 / 2001: 0, posting having stopped.

    **`Date-Modified:` is deliberately not read**: nine records, 0.0 equivalent-English.
    **A block is bounded by the next `Subdomain:` line**, so a neighbour's approval date
    can never attach to this one.
    """
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if not names:
                stats["empty_archive"] += 1
                return
            text = archive.read(names[0]).decode("utf-8", errors="replace")
    else:
        text = path.read_text(encoding="utf-8", errors="replace")

    marks = list(_CA_SUBDOMAIN.finditer(text))
    stats["subdomain_records"] = len(marks)
    for index, mark in enumerate(marks):
        stop = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        block = text[mark.start() : stop]
        approved = _CA_APPROVED.search(block)
        if approved is None:
            stats["no_approval_date"] += 1
            continue
        year = int(approved.group(1))
        if year not in YEARS:
            stats["approved_out_of_window"] += 1
            continue
        stats["approved_in_window"] += 1
        yield BulkRecord(
            raw=mark.group(1),
            year=year,
            evidence_value=(
                f"ca_date_approved:{approved.group(1)}{approved.group(2)}{approved.group(3)}"
            ),
        )


# `NAME<TAB>25-OCT-01`. Oracle-style two-digit year, so the century is inferred: a
# `01` is 2001, not 1901. The month name is parsed only to prove the field is a date
# and not something else that happens to have two hyphens.
_NW_ROW = re.compile(r"^(\S+)\t(\d{1,2})-([A-Z]{3})-(\d{2})\s*$")
_NW_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def parse_namewinner_expiring(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per name on a namewinner expiring-domain list.

    Dotster's `rule_book.php` calls this "our list of soon to be expiring domain names", so
    a name on it is registered at that moment: `artifact_listing`, not a directory. **No
    corroboration split**, being registered being the only way onto a dump out of a
    registrar's own system, so it dates novel names too.

    **The date is read PER ROW, not from the file.** Every row of the 2001-10-26 capture
    carries `25-OCT-01`, 20,945 occurrences with no other date of that shape. Reading each
    row's own date refuses the 2002-04 capture of the same page automatically, which is what
    rule 6 requires. Two-digit years expand on a 30-year pivot, so `01` is 2001.
    """
    with _open_text(path) as fh:
        for line in fh:
            stats["lines"] += 1
            row = _NW_ROW.match(line.rstrip("\n"))
            if row is None:
                stats["not_a_data_row"] += 1
                continue
            if row.group(3) not in _NW_MONTHS:
                stats["unparseable_month"] += 1
                continue
            two = int(row.group(4))
            year = 2000 + two if two <= 30 else 1900 + two
            if year not in YEARS:
                stats["row_out_of_window"] += 1
                continue
            stats["rows"] += 1
            yield BulkRecord(
                raw=row.group(1),
                year=year,
                evidence_value=f"namewinner_expiring:{row.group(2)}-{row.group(3)}-{row.group(4)}",
            )


# The 1999 RIPE database snapshot. **Read the docstring before touching this.**
# Line 2 of the payload is the file's own stamp, `# 990804 00:07:01`. Two-digit year,
# so 99 is 1999; anything below 90 would be 20xx, which this file is not.
_RIPE_STAMP = re.compile(r"^#\s*(\d{2})(\d{2})(\d{2})\s+\d{2}:\d{2}:\d{2}\s*$")
# The ONLY attribute this parser is permitted to read. Deliberately anchored and
# deliberately not a general `\*(\w\w):` pattern, so widening it takes a code change
# and a review rather than a config tweak.
_RIPE_DOMAIN = re.compile(r"^\*dn:\s*(\S+)\s*$")


def parse_ripe_dbase_1999(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per `domain:` object in the 1999-08-04 RIPE database snapshot.

    **Used under written permission, and the permission constrains the CODE, so it lives
    here.** The promise to RIPE NCC: read the domain objects, derive `(domain name, 1999)`
    pairs, publish NO personal data at all.

    **The contact data is inline.** There are no `person:` objects, which invites the WRONG
    conclusion that the file holds no personal data:

        *dn: TuKKK.FI
        *de: Rehtorinpellonkatu 3, SF-20500 TURKU, Finland   <- postal address
        *ac: +358 21 6383105                                 <- phone number
        *ac: mniemi@abo.fi                                   <- e-mail
        *ch: ripe-dbm@ripe.net 19920825                      <- e-mail

    So `_RIPE_DOMAIN` matches `*dn:` and nothing else. **Do not widen it.** `*de`, `*ac`,
    `*tc`, `*zc` and `*ch` break the promise, and three of the five do not look personal.

    **What dates it.** Line 2 of the payload, `# 990804 00:07:01`, so rule 6 gives 1999 and
    no other year. The stamp is read rather than assumed and a file without one is refused.
    Reverse zones (20,974 of 1,256,414) are dropped here as well as by the store.
    """
    year = None
    with _open_text(path) as fh:
        for line in fh:
            stats["lines"] += 1

            if year is None:
                stamp = _RIPE_STAMP.match(line.rstrip("\n"))
                if stamp is not None:
                    two = int(stamp.group(1))
                    year = (1900 + two) if two >= 90 else (2000 + two)
                    stats["header_year"] = year
                    if year not in YEARS:
                        stats["stamp_out_of_window"] += 1
                        return
                    continue
                if stats["lines"] > 40:
                    # The stamp is on line 2. If forty lines in it is still absent,
                    # this is not the file we think it is, and guessing a year for a
                    # 20-million-line dump is the worst possible failure mode.
                    stats["no_header_stamp"] += 1
                    return
                continue

            found = _RIPE_DOMAIN.match(line.rstrip("\n"))
            if found is None:
                stats["attribute_discarded"] += 1
                continue
            value = found.group(1)
            if value.upper().endswith((".ARPA", ".ARPA.")):
                stats["reverse_zone_skipped"] += 1
                continue
            stats["domain_objects"] += 1
            yield BulkRecord(
                raw=value,
                year=year,
                evidence_value="ripe_dbase:19990804",
            )


# `squidguard-<category>-<basename>`, written by `collect_squidguard_2001.py`. The
# category is kept only for the evidence value; the date is what matters.
_SG_FILE = re.compile(r"^squidguard-([a-z0-9-]+)-(domains|urls)(?:\.(\d{4})(\d{2})(\d{2})\.diff)?$")
# The robot's own stamp inside a base list: "compiled in 19:44:45 on 2001.12.15 19:56:41."
_SG_STAMP = re.compile(r"compiled in [\d:]+ on (\d{4})\.(\d{2})\.(\d{2})")


def parse_squidguard_blacklist(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per host in one squidGuard blacklist file.

    The header asserts liveness rather than listing, `compiled from 2402 link sources and
    654820 links, of which 510389 tested successfully`, so the robot fetched the host and it
    answered. Nobody typed the list, so no corroboration split.

    **Two date routes, and neither is the tar's.** A base `domains` or `urls` file carries
    its own compile stamp; a diff carries the date in its filename. A file with neither is
    skipped rather than dated from the archive around it.

    **A diff's `-` lines are dropped, the one judgement in here.** `+host` is the robot
    adding a host it tested successfully; `-host` is evidence it STOPPED answering. 104,242
    added against 23,267 removed, so keeping removals inflates the count by a fifth on
    exactly the wrong inference.

    `urls` lines carry a path the canonicaliser strips. IP-address lines appear in the diffs
    and are rejected there, not here.
    """
    match = _SG_FILE.match(path.name)
    if match is None:
        stats["not_a_blacklist_file"] += 1
        return
    category, kind = match.group(1), match.group(2)
    is_diff = match.group(3) is not None

    text = path.read_text(encoding="utf-8", errors="replace")
    if is_diff:
        year = int(match.group(3))
        stamp = f"{match.group(3)}{match.group(4)}{match.group(5)}"
    else:
        found = _SG_STAMP.search(text)
        if found is None:
            stats["no_compile_stamp"] += 1
            return
        year = int(found.group(1))
        stamp = f"{found.group(1)}{found.group(2)}{found.group(3)}"
    if year not in YEARS:
        stats["out_of_window_edition"] += 1
        return

    for line in text.splitlines():
        stats["lines"] += 1
        entry = line.strip()
        if not entry or entry.startswith("#"):
            stats["comment_or_blank"] += 1
            continue
        if is_diff:
            if entry.startswith("-"):
                stats["diff_removal_skipped"] += 1
                continue
            if entry.startswith("+"):
                entry = entry[1:].strip()
            else:
                stats["diff_context_line"] += 1
                continue
        if not entry:
            continue
        stats["hosts"] += 1
        yield BulkRecord(
            raw=entry,
            year=year,
            evidence_value=f"squidguard:{category}/{kind}@{stamp}",
        )


# The US Domain Registry's delegated-zone list. The artifact carries NO in-body date,
# so the edition date lives in the filename and the collector is what puts it there:
# `us-domain-delegated.YYYYMMDD.txt`, taken from the tar-preserved mtime for the
# 1996 and 1999 editions and from the Wayback capture stamp for the 2000 and 2001 ones.
_USD_EDITION = re.compile(r"us-domain-delegated\.(\d{4})(\d{2})(\d{2})\.txt$", re.I)
# `AK    K12.AK.US.        postmaster@ns.alaska.edu`. Column 2 only: the contact in
# column 3 is a mail domain somebody else operates, and this file says nothing about
# when THAT was registered. Taking it would be reading a `link_target` as a listing.
_USD_ROW = re.compile(r"^([A-Z]{2})\s+([A-Za-z0-9][A-Za-z0-9.\-]*?\.[Uu][Ss])\.?\s", re.M)


def parse_us_domain_delegated(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per delegated `.us` zone in one edition of the ISI list.

    The registry stating which zones it had delegated at an instant, the same instrument as
    a zone file: no corroboration split, and nothing about any other year.

    **The date is in the filename because the artifact has none inside it**, this source's
    one weakness, so the collector records where each date came from. Two independent
    mechanisms agree: the 1996 and 1999 editions carry tar-preserved mtimes whose rotation
    chain is monotone in date and size, continuing monotone into the Wayback captures; the
    2000 and 2001 editions carry their own capture stamps. An edition whose filename has no
    date is skipped rather than guessed at.

    **Column 2 only.** Every row also carries a contact address, and those mail domains are
    not delegated `.us` zones: 56 pairs of 13,816 when the whole line was scanned. The `k12`
    and locality zones are left to the PSL, so this parser does not filter by shape.
    """
    edition = _USD_EDITION.search(path.name)
    if edition is None:
        stats["no_edition_date_in_filename"] += 1
        return
    year = int(edition.group(1))
    stamp = "".join(edition.groups())
    if year not in YEARS:
        stats["edition_out_of_window"] += 1
        return

    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        stats["lines"] += 1
        row = _USD_ROW.match(line + " ")
        if row is None:
            stats["not_a_zone_row"] += 1
            continue
        stats["zone_rows"] += 1
        yield BulkRecord(
            raw=row.group(2),
            year=year,
            evidence_value=f"us_domain_delegated:{stamp}",
        )


_IEDR_PAGE = re.compile(r"(?:^|_)(?:0-9|[a-z])-doms\.html$", re.I)
_IEDR_NAME = re.compile(r"\b([a-z0-9][a-z0-9\-]{0,60}(?:\.[a-z0-9\-]{1,60})*\.ie)\b")
_IEDR_SELF = ("domainregistry.ie", "iedr.ie")


def parse_iedr_register(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per `.ie` name printed on an archived IEDR register page.

    **The date is inside the artifact and the whole page stands or falls on it**: `updated
    automatically at 14:51 GMT on Friday, 21 December 2001`, the Wayback capture only
    corroborating. A page whose own line falls outside the window is dropped ENTIRELY: of 27
    letter pages, `l-doms.html` reads 28 March 2002, and its capture date would import 931
    names into 2001 that the artifact places in 2002.

    **Read the date with the tags stripped**: the footer spans an anchor in some editions,
    so a regex over raw HTML matches most pages and silently misses others.

    **Only a letter page is a register.** The same trees publish `stalled.html`, PENDING
    APPLICATIONS nobody had registered, so the filename is checked before the date.

    `artifact_listing`, no corroboration split, nothing about any other year.
    """
    if _IEDR_PAGE.search(path.name) is None:
        stats["not_a_register_page"] += 1
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    flat = re.sub(r"<[^>]+>", " ", text)
    found = _IEDR_FOOTER.search(flat)
    if found is None:
        stats["no_footer_date"] += 1
        return
    year = int(found.group(1))
    if year not in YEARS:
        stats["out_of_window_page"] += 1
        return
    body = flat[flat.find("[") :] if "[" in flat else flat
    seen: set[str] = set()
    for raw in _IEDR_NAME.findall(body.lower()):
        if raw.endswith(_IEDR_SELF):
            stats["registry_own_host"] += 1
            continue
        name = to_registrable(raw)
        if name is None or not name.endswith(".ie"):
            stats["not_registrable"] += 1
            continue
        if name in seen:
            continue
        seen.add(name)
        yield BulkRecord(
            raw=name,
            year=year,
            evidence_value=f"iedr register listing {found.group(0).strip()}",
        )


def _serial_of(path: Path) -> str:
    """The full `YYYYMMDDNN` serial, cached per path, for the evidence value."""
    cached = _SERIAL_CACHE.get(path)
    if cached is None:
        with _open_text(path) as fh:
            for index, line in enumerate(fh):
                if ";serial" in line:
                    cached = line.split()[0]
                    break
                if index > 40:
                    cached = "unknown"
                    break
        _SERIAL_CACHE[path] = cached or "unknown"
    return _SERIAL_CACHE[path]


_SERIAL_CACHE: dict[Path, str] = {}


def parse_domain_creation_csv(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per domain whose registry creation date falls in the window.

    Rows are semicolon-separated with a header:
    `domain;tld;dnssec;registrar;created_at;records_ns;records_ds;records_dnskey;analyzed_at`
    and `created_at` is the registry's own creation date for that exact domain, parsed by
    the publisher out of a port-43 WHOIS answer.

    **One year per domain, deliberately**: a creation date says nothing about any later
    year, and inferring one is what the brief forbids. The direction of error is LOSS, which
    is safe: WHOIS reports the current registration, so a name created in 1998, dropped and
    re-registered in 2015 reads 2015 and falls out of window. The reverse cannot happen.
    """
    with _open_text(path) as fh:
        for line in fh:
            stats["lines"] += 1
            parts = line.rstrip("\n").split(";")
            if len(parts) < 5:
                stats["malformed"] += 1
                continue
            created = parts[4].strip()
            if len(created) < 4 or not created[:4].isdigit():
                stats["no_creation_date"] += 1
                continue
            year = int(created[:4])
            if year not in YEARS:
                stats["out_of_window"] += 1
                continue
            domain = parts[0].strip()
            # An internationalised TLD cannot be in window: every `xn--` TLD was delegated
            # in 2010 or later. This file carries 17 names under `.xn--fiqs8s` and
            # `.xn--fiqz9s` with 2000 and 2001 creation dates, CNNIC having run
            # Chinese-character domains before ICANN delegated the TLD. The registry date
            # is not a fabrication; the DNS name still did not exist. His validator
            # requires a letters-only TLD, so these score zero for him and full weight for
            # us, and `round_figures.py --verify` refuses the round over the discrepancy.
            if domain.rsplit(".", 1)[-1].lower().startswith("xn--"):
                stats["idn_tld_out_of_window"] += 1
                continue
            yield BulkRecord(
                raw=domain,
                year=year,
                evidence_value=f"registry created {created}",
                # ICANN's own lookup rather than a registry-specific RDAP endpoint,
                # because it resolves for every TLD and shows the creation date a
                # reviewer is being asked to check. Without a link the approval
                # request prints an empty column, and the request exists precisely
                # so a human checks the registry instead of reading our prose.
                evidence_url=f"https://lookup.icann.org/en/lookup?q={domain}",
            )


def parse_domain_year_captures(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per in-window (domain, year) row of an IA capture census.

    Rows are `host<TAB>year<TAB>capture_count`. The claim each row makes is the
    same one `ia_cdx_bulk` makes from a CDX line, that the Internet Archive holds
    a capture of this host in this year; it arrives pre-aggregated to the year
    instead of carrying each timestamp. So the year is per-record and intrinsic,
    not a property of the file.

    The count is kept in the evidence value rather than discarded. It is not used
    to date anything, but a reader checking a row wants to know whether it rests
    on one capture or on two hundred.
    """
    with _open_text(path) as fh:
        for line in fh:
            stats["lines"] += 1
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3 or not parts[1].isdigit():
                stats["malformed"] += 1
                continue
            year = int(parts[1])
            if year not in YEARS:
                stats["out_of_window"] += 1
                continue
            captures = parts[2] if parts[2].isdigit() else "?"
            yield BulkRecord(
                raw=parts[0],
                year=year,
                evidence_value=f"ia_captures:{year}:{captures}",
                # The Wayback calendar for that host in that year, which is the row's
                # own claim rendered as something a reviewer can open. Without this the
                # approval request prints an empty link column, and the request exists
                # precisely so a human checks external evidence instead of our prose.
                evidence_url=f"https://web.archive.org/web/{year}*/http://{parts[0]}/",
            )


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


# **The host link graph is NOT one file sorted by year**, and believing it costs 93% of the
# source. Over all 168,942,882 lines the year column decreases 14 times, so it is 15
# concatenated shards each sorted internally: an early exit at the first row past 2001 stops
# at line 166,895 and reads 166,890 in-window rows of 2,468,674. A tail showing 2004 proves
# only what the LAST shard ends on, so run the cheap positive control, does the year ever go
# backwards. There is deliberately no last-year constant here.


_UKWA_SOURCE_COL = 1
_UKWA_TARGET_COL = 2


def _parse_ukwa(path: Path, stats: Counter, host_column: int) -> Iterator[BulkRecord]:
    """Yield one host per in-window host-link-graph row, from the chosen column.

    Rows are `year|source_host|target_host<TAB>count`. The file is 15 internally
    sorted shards, so an out-of-window year means only that this shard has passed
    the window and the next one may not have. The whole file is therefore read.
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
    """Yield the TARGET host of each row as `link_target`, candidate-only.

    The loader collapses the host to its registrable and the value keeps only the year, so a
    `www.` or deeper target, 77% of them, would date a name the record does not identify.
    `parse_ukwa_link_target_bare` is the annual half. Targets are worldwide, unlike the
    `.uk`-biased source hosts.
    """
    yield from _parse_ukwa(path, stats, _UKWA_TARGET_COL)


def parse_ukwa_link_target_bare(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield the TARGET of each row that names a registrable itself, as `artifact_listing`.

    The brief: "UK Web Archive host/link graph records may serve as direct annual evidence when
    their year association is explicit and documented", and XIII admits "a dated web link-graph
    record that identifies the target hostname". A registrable is identified only when the
    target IS it: a `www.` or deeper target dates that host, never the name beneath it (his
    ruling of 2026-09-06). The host stays in the value.
    """
    for record in _parse_ukwa(path, stats, _UKWA_TARGET_COL):
        host = record.raw.strip().lower()
        registrable = to_registrable(host)
        if registrable is None or host.startswith("www."):
            stats["target_unparseable_or_www"] += 1
            continue
        if registrable != host:
            stats["target_below_its_registrable"] += 1
            continue
        yield BulkRecord(
            raw=host, year=record.year, evidence_value=f"{record.evidence_value} {host}"
        )


# The British Library geoindex of the JISC UK Web Domain Dataset: every `.uk` resource IA
# held for 1996-2013, one row per capture, `<14-digit timestamp>/<url><TAB><postcode>`.
#
# **The timestamp is the capture's own, so `cdx_timestamp`, self-dating**, and no
# corroboration split where the link graph's source side takes one. A bulk projection of IA
# holdings, the documented exception to "an IA-derived source cannot be net-new against an
# IA-derived baseline": 79,253 net-new pairs, 77,749.1 EE.
#
# **Junk stamps exist and the window filter is what rejects them**: some rows carry
# `19800101000000` or 1994-1995 dates, so nothing trusts the first row or the ordering.
def parse_ukwa_geoindex(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per in-window capture row of the BL geoindex extract.

    Input is the filtered output of `scripts/sources/ukwa/ukwa_geoindex_pull.sh`, not the
    11.2 GB original: extraction streams 9 GB over HTTP and counts shard boundaries, which
    is not repeated per ingest.
    """
    with _open_text(path) as fh:
        for line in fh:
            stats["lines"] += 1
            stamp, _, rest = line.partition("/")
            if len(stamp) != 14 or not stamp.isdigit():
                stats["malformed"] += 1
                continue
            url = rest.split("\t", 1)[0].strip()
            if not url:
                stats["malformed"] += 1
                continue
            year = int(stamp[:4])
            if year not in YEARS:
                stats["out_of_window"] += 1
                continue
            yield BulkRecord(
                raw=url,
                year=year,
                evidence_value=stamp,
                evidence_url=f"https://web.archive.org/web/{stamp}/{url}",
            )


# AFNIC .fr open data: one semicolon-delimited UTF-8 row per current or recently-withdrawn
# .fr domain. Column 1 the domain, 11 the creation date, 12 the WHOIS-withdrawal date, both
# DD-MM-YYYY (12 empty = still registered). A .fr creation date resets on re-registration,
# so (creation, withdrawal) documents one CONTINUOUS interval and brief IV.6 makes every
# in-window year inside it valid evidence, not only the creation year.
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


# Internet Scout Report archive (OAI-PMH harvest, oai_dc). Each <record> is an editorial
# review of a live site and <dc:date> is the Report's publication year, so the date attests
# the site was live: `dated_directory`. Site URLs are in <dc:identifier>; the
# <header><identifier> is the auditable OAI record id.
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


# ODP (Open Directory / DMOZ) RDF content dump, `artifact_listing`: the
# `<!-- Generated at YYYY-MM-DD ... -->` stamp fixes the year for the whole dump, and each
# catalogued site is an external URL in `link r:resource="..."` or `ExternalPage about=...`.
# The RDF is malformed pseudo-XML, so URLs come out by regex. Truncated downloads (gzip EOF
# mid-stream) are tolerated like UKWA's, keeping everything decoded so far.
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


def attested_years(creation: int, first: int = 1996, last: int = 2001) -> tuple[int, ...]:
    """The in-window years an RDAP creation year can attest on its own.

    The creation year itself when it is inside the window, nothing otherwise. A domain
    created before `first` gets no attested year: RDAP shows it existed by then and exists
    now, but nothing about any year in between, so it stays a candidate (brief IV.6).
    """
    return (creation,) if first <= creation <= last else ()


# An RDAP run journal: one gzipped JSON object per line, with keys `domain`,
# `queried_at`, `status`, `creation_year`, `response` and `url` (absent before
# direct routing). The journal is the artifact, so this evidence replays from a
# hashed file like every other source. Only the creation year is attested
# (IV.6), so a domain yields at most one record.
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
                # journals written before direct routing carry no `url`, so the
                # redirector stays the fallback: it is where those queries went
                url = record.get("url") or f"{RDAP_REDIRECTOR}{domain}"
                for target_year in years:
                    yield BulkRecord(
                        raw=domain,
                        year=target_year,
                        evidence_value=f"rdap creation {year}",
                        evidence_url=url,
                    )
    except (EOFError, OSError):
        # journal from an interrupted run; everything before the last flush was
        # already yielded, and the missing tail is re-queried on the next run
        stats["truncated_tail"] += 1


# An `ark cdx` run journal: one JSON object per queried domain, format documented
# in ark.cdx. A returned in-window capture year is evidence for that year and no
# other, so there is no inference to make here (IV.7).
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


def parse_ncsa_whats_new(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per site announced in NCSA's "What's New" pages.

    The era's announcement list for newly launched sites, dated by the issue that carried
    them. On disk it is one `domain<TAB>date` row per entry, extracted from the archived
    issues in `issues-1996/` and checksummed alongside them. Entries only: navigation and
    masthead links are not announcements, and that distinction is what earns
    `dated_directory` rather than candidate grade.
    """
    with _open_text(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw, _, date = line.partition("\t")
            if len(date) < 4 or not date[:4].isdigit():
                stats["no_date"] += 1
                continue
            yield BulkRecord(
                raw=raw,
                year=int(date[:4]),
                evidence_value=f"ncsa whats-new entry {date}",
            )


def parse_expansion_links(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Hosts linked from an ordinary archived page: candidate-only.

    The page's author linked to them, which is not evidence the host existed:
    that is what verification is for.
    """
    yield from _parse_expansion(path, stats, curated=False)


def parse_expansion_directory(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Entries listed on an archived page asserted to be a curated directory.

    The brief grants that the capture date of such a page is item-level
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
    # The seed layer of IA's breadth-first expansion of URLs from SEC 10-K filings. Same
    # classic CDX shape as Early Web, so it reuses that parser; a separate spec only so
    # provenance and lineage name it separately. Not the closed
    # DARTMOUTH-NBER-RESEARCH-ARCS family, which measured exactly zero net-new.
    #
    # **Only BFS level 0 is worth reading**: levels 2 and 3 are 92 of the 102 ARC items and
    # measured 0.00, 0.00 and 0.59 EE per MB against level 0's 104.7. The WARC half of the
    # collection is 2012-2019, zero in-window rows.
    # JPNIC's register at 1999-04-30, frozen on a personal mirror. Permissive licence,
    # unusually: JPNIC's open-document notice grants free redistribution.
    "jpnic_register": SourceSpec(
        key="jpnic_register",
        source_name="jpnic_register",
        evidence_type="artifact_listing",
        acquisition_method="registry_register_listing",
        parse=parse_jpnic_register,
    ),
    "dartmouth_bfs_seed": SourceSpec(
        key="dartmouth_bfs_seed",
        source_name="dartmouth_bfs_seed",
        evidence_type="cdx_timestamp",
        acquisition_method="bulk_cdx_file",
        parse=parse_early_web_cdx,
    ),
    # The Defense Data Network NIC mirrored InterNIC's zone distribution over HTTP and
    # Wayback captured it, which is how a family closed twice for "no in-window zone file
    # survives" turned out to have one. Self-dating on the SOA serial inside each file.
    "internic_zone": SourceSpec(
        key="internic_zone",
        source_name="internic_zone",
        evidence_type="artifact_listing",
        acquisition_method="internic_zone_distribution",
        parse=parse_internic_zone,
    ),
    # The IE Domain Registry regenerated its whole register as static A-Z pages and
    # Wayback took them. Self-dating on the page's own "updated automatically at ..."
    # line, which is why a 2002-footered page is dropped rather than read as 2001.
    "iedr_register": SourceSpec(
        key="iedr_register",
        source_name="iedr_register",
        evidence_type="artifact_listing",
        acquisition_method="registry_register_listing",
        parse=parse_iedr_register,
    ),
    # The US Domain Registry's delegated-zone list, ISI, 1996-2001. Master-eligible on the
    # zone-file argument: a delegation is the registry serving the name, not a description.
    # Edelman's 2002 whois transcriptions. `whois_creation`, so rule 6 gives the
    # transcribed creation year and no other.
    "early_bulk_whois_snapshot": SourceSpec(
        key="early_bulk_whois_snapshot",
        source_name="early_bulk_whois_snapshot",
        evidence_type="whois_creation",
        acquisition_method="transcribed_whois_record",
        parse=parse_edelman_whois,
    ),
    # junkfilter's hand-maintained spam-origin blocklist, thirteen in-window editions.
    # Two lanes: the corroborated half dates a year, the rest parks as candidates.
    "junkfilter_dated": SourceSpec(
        key="junkfilter_dated",
        source_name="junkfilter_dated_blocklist",
        evidence_type="dated_directory",
        acquisition_method="dated_blocklist_release",
        parse=parse_junkfilter_split,
    ),
    "junkfilter_candidates": SourceSpec(
        key="junkfilter_candidates",
        source_name="junkfilter_mention",
        evidence_type="link_target",
        acquisition_method="dated_blocklist_release",
        parse=parse_junkfilter_split,
    ),
    # chastity-list, a hand-maintained squidGuard blacklist, one December 2001 edition.
    # Two lanes: the corroborated 94.0% dates 2001, the rest parks as candidates.
    "chastity_dated": SourceSpec(
        key="chastity_dated",
        source_name="chastity_list_blacklist",
        evidence_type="dated_directory",
        acquisition_method="dated_blocklist_release",
        parse=parse_chastity_split,
    ),
    "chastity_candidates": SourceSpec(
        key="chastity_candidates",
        source_name="chastity_list_mention",
        evidence_type="link_target",
        acquisition_method="dated_blocklist_release",
        parse=parse_chastity_split,
    ),
    # Granite Canyon's free-secondary-DNS reject and prune lists, seven editions. Two
    # lanes: the corroborated half dates the edition's own stamped year, the rest parks
    # as candidates.
    "granitecanyon_dated": SourceSpec(
        key="granitecanyon_dated",
        source_name="granitecanyon_zone_rejects",
        evidence_type="artifact_listing",
        acquisition_method="hosted_zone_inventory",
        parse=parse_granitecanyon_split,
    ),
    "granitecanyon_candidates": SourceSpec(
        key="granitecanyon_candidates",
        source_name="granitecanyon_zone_mention",
        evidence_type="link_target",
        acquisition_method="hosted_zone_inventory",
        parse=parse_granitecanyon_split,
    ),
    # The capture-dated sibling of `cctld_register_listing_inbody`: four register
    # listings with no in-body stamp of their own.
    "cctld_capture_dated": SourceSpec(
        key="cctld_capture_dated",
        source_name="cctld_register_listing_capture",
        evidence_type="cdx_timestamp",
        acquisition_method="registry_listing_capture",
        parse=parse_cctld_capture_split,
    ),
    "cctld_capture_candidates": SourceSpec(
        key="cctld_capture_candidates",
        source_name="cctld_register_listing_mention",
        evidence_type="link_target",
        acquisition_method="registry_listing_capture",
        parse=parse_cctld_capture_split,
    ),
    # MYNIC's fortnightly register change report. No split: the listing reproduces the
    # registry's own published per-day counts.
    "mynic_change_report": SourceSpec(
        key="mynic_change_report",
        source_name="mynic_my_change_report",
        evidence_type="artifact_listing",
        acquisition_method="registry_change_report",
        parse=parse_mynic_listing,
    ),
    # The CO.ZA registry's own suspension and deletion queues, 22 captures over two
    # hostnames. No split: shell CGI reading the register.
    "coza_deletion_queue": SourceSpec(
        key="coza_deletion_queue",
        source_name="coza_deletion_listing",
        evidence_type="cdx_timestamp",
        acquisition_method="registry_listing_capture",
        parse=parse_coza_queue,
    ),
    # Federal Audit Clearinghouse Single Audit filings 1998-2001, dated by each row's own
    # signature date. Two lanes: the corroborated half dates a year, the rest parks.
    # Bytes downloaded by hand by Ivo 2026-08-31, since app.fac.gov is Disallow: /.
    "fac_dated": SourceSpec(
        key="fac_dated",
        source_name="fac_single_audit",
        evidence_type="dated_directory",
        acquisition_method="federal_filing_dataset",
        parse=parse_fac_filings,
    ),
    "fac_candidates": SourceSpec(
        key="fac_candidates",
        source_name="fac_single_audit_mention",
        evidence_type="link_target",
        acquisition_method="federal_filing_dataset",
        parse=parse_fac_filings,
    ),
    # ccTLD register listings that carry their own machine-written timestamp.
    # `artifact_listing`: the registry stating its register's contents at that instant.
    "cctld_register_listing_inbody": SourceSpec(
        key="cctld_register_listing_inbody",
        source_name="cctld_register_listing_inbody",
        evidence_type="artifact_listing",
        acquisition_method="registry_register_listing",
        parse=parse_cctld_register_inbody,
    ),
    # The CA Domain Registry's public approval notices. `whois_creation`: the registry
    # stating when it created the registration, so rule 6 gives that year and no other.
    "can_domain_registry_notices": SourceSpec(
        key="can_domain_registry_notices",
        source_name="can_domain_registry_notices",
        evidence_type="whois_creation",
        acquisition_method="registry_approval_notice",
        parse=parse_can_domain_registry_notices,
    ),
    # Dotster's expiring-domain auction list, 2001-10-26. `artifact_listing`: a registrar
    # stating which names are registered and about to expire. Per-row dates, so an
    # out-of-window edition is refused row by row.
    "namewinner_expiring": SourceSpec(
        key="namewinner_expiring",
        source_name="namewinner_expiring",
        evidence_type="artifact_listing",
        acquisition_method="registrar_expiring_listing",
        parse=parse_namewinner_expiring,
    ),
    # The audit trail INSIDE the 1999 RIPE snapshot: one record per dated `changed:`
    # transaction, which reaches 1996-1998 where the snapshot's own date cannot.
    # `artifact_listing`: the file records a dated transaction on that object.
    "ripe_dbase_changed": SourceSpec(
        key="ripe_dbase_changed",
        source_name="ripe_dbase_changed",
        evidence_type="artifact_listing",
        acquisition_method="registry_database_audit_trail",
        parse=parse_ripe_dbase_changed,
    ),
    # The same audit trail in FUNET's 2004-11-09 `split/` edition, the only reachable RIPE
    # file carrying 2000 and 2001 `changed:` lines. Same class, reading and permission.
    "ripe_dbase_split_2004": SourceSpec(
        key="ripe_dbase_split_2004",
        source_name="ripe_dbase_split_2004",
        evidence_type="artifact_listing",
        acquisition_method="registry_database_audit_trail",
        parse=parse_ripe_dbase_split_2004,
    ),
    # The 1999 RIPE database snapshot, used under written permission from RIPE NCC.
    # `artifact_listing`: the file states its own generation instant and a `domain:` object
    # in it is the registry's database contents then. Evidences 1999 only, per rule 6.
    "ripe_dbase_1999": SourceSpec(
        key="ripe_dbase_1999",
        source_name="ripe_dbase_1999",
        evidence_type="artifact_listing",
        acquisition_method="registry_database_snapshot",
        parse=parse_ripe_dbase_1999,
    ),
    # squidGuard's robot-compiled blacklists, 2001-12 edition. Master-eligible: the header
    # asserts successful fetches, and nobody typed the list. GPL v2, so licence-clear.
    "squidguard_2001_blacklist": SourceSpec(
        key="squidguard_2001_blacklist",
        source_name="squidguard_2001_blacklist",
        evidence_type="artifact_listing",
        acquisition_method="robot_compiled_blocklist",
        parse=parse_squidguard_blacklist,
    ),
    "us_domain_delegated": SourceSpec(
        key="us_domain_delegated",
        source_name="us_domain_delegated",
        evidence_type="artifact_listing",
        acquisition_method="registry_delegation_listing",
        parse=parse_us_domain_delegated,
    ),
    "isc_survey": SourceSpec(
        key="isc_survey",
        source_name="isc_survey",
        evidence_type="artifact_listing",
        acquisition_method="isc_domain_survey",
        parse=parse_isc_survey,
    ),
    # A per-year capture census IA itself computed over the Dartmouth/NBER
    # corporate-websites crawl. A bulk index OF the archive rather than a corpus derived
    # from it, the documented exception to "IA-derived cannot be net-new": it converts our
    # binding constraint, request throughput, into a file download. Its own source name so
    # provenance never merges with `ia_cdx_bulk`.
    # A published bulk of registry creation dates, CC BY 4.0, covering 171M domains.
    # Same claim and same authority as `rdap_snapshot`, arriving as a file instead of
    # 171 million queries we could never afford to make. Its own source name so
    # provenance stays separable from our live RDAP sweeps.
    "domain_creation_bulk": SourceSpec(
        key="domain_creation_bulk",
        source_name="domain_creation_bulk",
        evidence_type="whois_creation",
        acquisition_method="published_registry_creation_dates",
        parse=parse_domain_creation_csv,
    ),
    "dartmouth_nber_captures": SourceSpec(
        key="dartmouth_nber_captures",
        source_name="dartmouth_nber_captures",
        evidence_type="cdx_timestamp",
        acquisition_method="ia_domain_year_census",
        parse=parse_domain_year_captures,
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
    # The BL geoindex extract: IA capture timestamps for `.uk` resources, so
    # `cdx_timestamp` and self-dating. Registering a spec does NOT let it date a year:
    # `ark ingest` refuses the class until a human writes its `Decision:` line in
    # docs/registers/approved-sources-list.md. The parser exists ahead of that
    # decision so approving it is one command.
    "ukwa_geoindex": SourceSpec(
        key="ukwa_geoindex",
        source_name="ukwa_geoindex",
        evidence_type="cdx_timestamp",
        acquisition_method="bl_geoindex_extract",
        parse=parse_ukwa_geoindex,
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
    # journal and so cannot be replayed from a file (2026-07-25)
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
    # its annual half: a dated listing of a target that IS its registrable, under the
    # same web method as the source side
    "ukwa_link_target_bare": SourceSpec(
        key="ukwa_link_target_bare",
        source_name="ukwa_link_target_bare",
        evidence_type="artifact_listing",
        acquisition_method="ukwa_host_link_graph",
        parse=parse_ukwa_link_target_bare,
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
    # NCSA "What's New": the era's announcement list for newly launched sites,
    # and the only 1996 editorial directory artifact that survives
    "ncsa_whats_new": SourceSpec(
        key="ncsa_whats_new",
        source_name="ncsa_whats_new",
        evidence_type="dated_directory",
        acquisition_method="ncsa_whats_new_pages",
        parse=parse_ncsa_whats_new,
    ),
    "tucows_candidates": SourceSpec(
        key="tucows_candidates",
        source_name="tucows_mention",
        evidence_type="link_target",
        acquisition_method="tucows_release_vendor_url",
        parse=_parse_usenet_journal,
    ),
    "tucows_dated": SourceSpec(
        key="tucows_dated",
        source_name="tucows_catalogue",
        evidence_type="dated_directory",
        acquisition_method="tucows_release_date",
        parse=_parse_usenet_journal,
    ),
    # Scanned computer and internet trade press on archive.org. A 1997 issue printing
    # `foo.com` dates it for 1997 the way a dated directory page does.
    #
    # Scoped to computing titles on measurement: the same script and extractor gave 10.5
    # net-new pairs an item on `computermagazines` and 0.4 on the general `magazine_rack`,
    # so the subject matter is the variable and the corpus is not.
    #
    # Split like Usenet because the domains arrive through OCR, which fabricates hostnames.
    "tradepress_dated": SourceSpec(
        key="tradepress_dated",
        source_name="trade_press",
        evidence_type="dated_directory",
        acquisition_method="trade_press_issue_date",
        parse=_parse_usenet_journal,
    ),
    "tradepress_candidates": SourceSpec(
        key="tradepress_candidates",
        source_name="trade_press_mention",
        evidence_type="link_target",
        acquisition_method="trade_press_ocr_mention",
        parse=_parse_usenet_journal,
    ),
    # UUCP map postings from comp.mail.maps. See `ark.uucp` for why these are registry
    # evidence rather than a posted URL, and for the provenance gate between the two kinds
    # of map file. `artifact_listing` for the posting date, as the ISC DNS survey carries.
    "uucp_listing": SourceSpec(
        key="uucp_listing",
        source_name="uucp_map_registry",
        evidence_type="artifact_listing",
        acquisition_method="uucp_map_registry_posting",
        parse=_parse_usenet_journal,
    ),
    # `whois_creation` for the registrar's own approved/received line, which is
    # the same claim AFNIC's `.fr` open data makes and carries the same type.
    "uucp_creation": SourceSpec(
        key="uucp_creation",
        source_name="uucp_map_creation",
        evidence_type="whois_creation",
        acquisition_method="uucp_map_registrar_approval",
        parse=_parse_usenet_journal,
    ),
    # A defacement mirror index. `artifact_listing` and NO corroboration split, because
    # the operators saved a copy of the page at that host on that date: a name that did not
    # resolve could not be in the index, so the hostname is verified by the act of
    # mirroring rather than typed from memory.
    # Domain-dispute proceedings: a dated docket naming a registered domain in its
    # own column. Self-dating, no corroboration split.
    # DK Hostmaster's own zone list, `domaincount/domains.txt`, in three Wayback captures
    # inside 2001. Each opens with the registry's dated count of its own register
    # (`20011217: 349694 subdomains of DK`), which dates every name below it: the registry
    # stating its own register, as MYNIC, TWNIC and IDNIC do.
    # A delimited field of a self-dating artifact, so no corroboration split.
    "dk_hostmaster_dk_zonen_domains_txt_wayback_2001": SourceSpec(
        key="dk_hostmaster_dk_zonen_domains_txt_wayback_2001",
        source_name="dk_hostmaster_dk_zonen_domains_txt_wayback_2001",
        evidence_type="artifact_listing",
        acquisition_method="registry_zone_list_wayback_capture",
        parse=parse_registry_items,
    ),
    "udrp_proceedings": SourceSpec(
        key="udrp_proceedings",
        source_name="udrp_proceedings",
        evidence_type="artifact_listing",
        acquisition_method="icann_udrp_proceedings_list",
        parse=parse_udrp_proceedings,
    ),
    "attrition_dated": SourceSpec(
        key="attrition_dated",
        source_name="attrition_defacement",
        evidence_type="artifact_listing",
        acquisition_method="attrition_defacement_mirror_index",
        parse=_parse_usenet_journal,
    ),
    # Hand-maintained maps: the container is fresh, the entries are not, so the
    # posting date evidences nothing and these stay candidate-only.
    "uucp_mentions": SourceSpec(
        key="uucp_mentions",
        source_name="uucp_map_mention",
        evidence_type="link_target",
        acquisition_method="uucp_map_hand_maintained",
        parse=_parse_usenet_journal,
    ),
    # The rtfm.mit.edu Usenet FAQ mirror. A FAQ carries its own revision date and lists
    # dozens of sites, so the date is intrinsic; unlike the UUCP maps above the URLs are
    # prose typed by a human, so the ordinary corroboration split applies.
    #
    # The year is the revision header, NOT `Date:`: rtfm keeps one copy of each FAQ, the
    # last auto-repost, and of 12,318 documents carrying both, 6,610 disagree.
    "rtfm_dated": SourceSpec(
        key="rtfm_dated",
        source_name="rtfm_faq",
        evidence_type="dated_directory",
        acquisition_method="rtfm_faq_revision_date",
        parse=_parse_usenet_journal,
    ),
    "rtfm_candidates": SourceSpec(
        key="rtfm_candidates",
        source_name="rtfm_faq_mention",
        evidence_type="link_target",
        acquisition_method="rtfm_faq_mention",
        parse=_parse_usenet_journal,
    ),
    # Addresses in the same Usenet messages that `domains_in_message` never looked
    # at: `ftp://` hosts, `mailto:` links and typed addresses in the body. Same
    # corpus, same risk, so the same corroboration split.
    "usenet_addr_dated": SourceSpec(
        key="usenet_addr_dated",
        source_name="usenet_address",
        evidence_type="dated_directory",
        acquisition_method="usenet_post_address",
        parse=_parse_usenet_journal,
    ),
    "usenet_addr_candidates": SourceSpec(
        key="usenet_addr_candidates",
        source_name="usenet_address_mention",
        evidence_type="link_target",
        acquisition_method="usenet_post_address_mention",
        parse=_parse_usenet_journal,
    ),
    # Addresses written bare in the body of the same Usenet messages, `foo.com`
    # with no scheme and no `www.`. See `ark.usenet.bare_domains_in_body` for the
    # guards and for why the corroboration split, not the pattern, is what makes
    # the recall safe. Its own source name so the addition can be measured and
    # dropped without disturbing what `usenet_announce` already claimed.
    "usenet_bare_dated": SourceSpec(
        key="usenet_bare_dated",
        source_name="usenet_bare",
        evidence_type="dated_directory",
        acquisition_method="usenet_post_bare_host",
        parse=_parse_usenet_journal,
    ),
    "usenet_bare_candidates": SourceSpec(
        key="usenet_bare_candidates",
        source_name="usenet_bare_mention",
        evidence_type="link_target",
        acquisition_method="usenet_post_bare_host_mention",
        parse=_parse_usenet_journal,
    ),
    # Registry whois records people pasted whole into Usenet posts. The date is the
    # registry's own `Record created on 20-Jul-2000.`, so `whois_creation` and rule 6 gives
    # that year and no other. The NAME is what the corroboration split guards, a person
    # having chosen and reflowed the block. See
    # `scripts/sources/usenet/collect_usenet_whois.py` for the binding rule that keeps one
    # record's creation line off the next record's name.
    "usenet_whois_dated": SourceSpec(
        key="usenet_whois_dated",
        source_name="usenet_whois_paste",
        evidence_type="whois_creation",
        acquisition_method="transcribed_whois_record",
        parse=_parse_usenet_whois_journal,
    ),
    "usenet_whois_candidates": SourceSpec(
        key="usenet_whois_candidates",
        source_name="usenet_whois_paste_mention",
        evidence_type="link_target",
        acquisition_method="usenet_post_whois_mention",
        parse=_parse_usenet_whois_journal,
    ),
    # The FERC-released Enron corpus: ~517,000 dated 1999-2002 business emails.
    # A dated message naming a domain attests it, exactly as a dated Usenet post
    # does. Its own lineage, because corporate email is independent of every
    # crawl, of Usenet and of the registries.
    "enron_dated": SourceSpec(
        key="enron_dated",
        source_name="enron_email",
        evidence_type="dated_directory",
        acquisition_method="enron_message_date",
        parse=_parse_usenet_journal,
    ),
    "enron_candidates": SourceSpec(
        key="enron_candidates",
        source_name="enron_email_mention",
        evidence_type="link_target",
        acquisition_method="enron_message_mention",
        parse=_parse_usenet_journal,
    ),
    # Public pipermail mailing-list archives, one month file per list per month,
    # each message dated by its own `Date:` header. Same shape as a dated Usenet
    # post and the same corroboration split. Newsgroup-gatewayed lists are left
    # out at collection time, see `scripts/sources/mail_corpora/collect_mailing_lists.py`.
    "maillist_dated": SourceSpec(
        key="maillist_dated",
        source_name="maillist_archive",
        evidence_type="dated_directory",
        acquisition_method="maillist_message_date",
        parse=_parse_usenet_journal,
    ),
    "maillist_candidates": SourceSpec(
        key="maillist_candidates",
        source_name="maillist_archive_mention",
        evidence_type="link_target",
        acquisition_method="maillist_message_mention",
        parse=_parse_usenet_journal,
    ),
    "usenet_dated": SourceSpec(
        key="usenet_dated",
        source_name="usenet_announce",
        evidence_type="dated_directory",
        acquisition_method="usenet_post_date",
        parse=_parse_usenet_journal,
    ),
    "usenet_candidates": SourceSpec(
        key="usenet_candidates",
        source_name="usenet_mention",
        evidence_type="link_target",
        acquisition_method="usenet_post_mention",
        parse=_parse_usenet_journal,
    ),
    "nypw_firstcdx": SourceSpec(
        key="nypw_firstcdx",
        source_name="nypw_firstcdx",
        evidence_type="cdx_timestamp",
        acquisition_method="nypw_first_capture_index",
        parse=parse_nypw_firstcdx,
    ),
    # The TimeMap sibling of the index above. The index gives one row per URL and so
    # can only offer a domain its FIRST year, which the IA-derived baseline already
    # holds; a TimeMap gives every capture.
    #
    # Folder year is the year of FIRST capture, not of the content, so folder Y can only
    # add years Y+1..2001: aim it at the years adjacent to the hole. The 1996 folder
    # measured 14.2 EE, the 2000 folder 4,144.2 EE on two parts.
    "nypw_timemaps": SourceSpec(
        key="nypw_timemaps",
        source_name="nypw_timemaps",
        evidence_type="cdx_timestamp",
        acquisition_method="nypw_timemap",
        parse=parse_nypw_timemap,
    ),
    # The same 34 partitions read again with the status filter off: 6.37M rows, 12.8%
    # of the corpus, and no archive request because the bytes are on disk. The yield is
    # a 2001 effect like its sibling's, a non-200 row adding nothing in a covered year.
    "nypw_timemaps_nonok": SourceSpec(
        key="nypw_timemaps_nonok",
        source_name="nypw_timemaps_nonok",
        evidence_type="cdx_timestamp",
        acquisition_method="nypw_timemap_non_200",
        parse=parse_nypw_timemap_nonok,
    ),
    "cdx_snapshot": SourceSpec(
        key="cdx_snapshot",
        source_name="ia_cdx_bulk",
        evidence_type="cdx_timestamp",
        acquisition_method="ia_cdx_collapsed_query",
        parse=parse_cdx_snapshot,
    ),
    # URLMerchant's whole for-sale inventory, printed as static A-Z listing pages and
    # captured by Wayback. `artifact_listing`: each page is a table the generator printed
    # out of the broker's own listings database, stamping the instant in its own
    # `<META NAME="UPDATED" CONTENT="Tuesday, Jul 17 2001 1:19:41 AM">`.
    #
    # Two lanes, an owner having submitted each name by hand: the date is a machine's and
    # the name is a person's typing, 44.8% typo upper bound on the novel half. Split by
    # `scripts/sources/directories/split_urlmerchant.py` before ingest.
    "urlmerchant_dated": SourceSpec(
        key="urlmerchant_dated",
        source_name="urlmerchant_inventory",
        evidence_type="artifact_listing",
        acquisition_method="broker_inventory_listing",
        parse=_parse_usenet_journal,
    ),
    "urlmerchant_candidates": SourceSpec(
        key="urlmerchant_candidates",
        source_name="urlmerchant_inventory_mention",
        evidence_type="link_target",
        acquisition_method="broker_inventory_listing",
        parse=_parse_usenet_journal,
    ),
    # Jeb Bush's gubernatorial mail, released by him in 2015 as Florida public records.
    # `dated_directory` and the corroboration split, exactly as `enron_email` carries:
    # what dates a message is its own unindented `Sent:` line, written by the sending
    # mail client, and what names the host is a person typing an address.
    #
    # Hosts are anchored on an `@`, a scheme or a `www.` label by `parse_jeb_mail.py`
    # (scripts/sources/mail_corpora/), because a missing space after a full stop forges a
    # domain under a high-weight TLD out of prose: `Candace Rice.To tell the truth` reads
    # as `rice.to`, and the wide pattern cost 200.8 EE of fabrication.
    "jeb_mail_dated": SourceSpec(
        key="jeb_mail_dated",
        source_name="jeb_bush_gubernatorial_email",
        evidence_type="dated_directory",
        acquisition_method="released_mailbox_sent_date",
        parse=_parse_usenet_journal,
    ),
    "jeb_mail_candidates": SourceSpec(
        key="jeb_mail_candidates",
        source_name="jeb_bush_gubernatorial_email_mention",
        evidence_type="link_target",
        acquisition_method="released_mailbox_mention",
        parse=_parse_usenet_journal,
    ),
}
