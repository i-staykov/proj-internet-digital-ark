"""UUCP map postings: a registry dump the Usenet parser was reading as prose.

`comp.mail.maps` carried the UUCP maps, and from 1993 the `.CA` portion of them
was machine-generated from the Canadian domain registry. A posting states its own
provenance in the file:

    #R Automatically generated from a .CA domain registration form
    #W registry@cs.toronto.edu (UUCP Liaison)

and lists one entry per registered name, keyed by `#N`, with the registrar's own
`received:` and `approved:` dates inside each entry. That is a registry dump with
a date on it, which is the strongest evidence class this project accepts, and it
is structured rather than free text so it does not carry the transcription risk
that forces the Usenet corroboration split.

**The project has had this file on disk and marked ingested since 7 August, and
took nothing from it.** `domains_in_message` reads http(s) URLs, bare `www.`
hosts and the `From:` header address; a UUCP map entry contains none of those, so
1,480,910 `#N` registry lines across 23,768 map postings were parsed as the
sender's domain and discarded. Measured against the store snapshot, reading them
properly is worth about 23,700 equivalent-English. Nothing had to be downloaded
and nothing had to be re-crawled; the bytes were already here.

**The provenance gate is the part that must not be skipped.** Two kinds of map
posting share the format and only one of them is dated evidence:

- **`.CA` registry-generated files.** Regenerated from the live registration
  database at posting time, so every name in one existed on its posting date.
  Verified rather than assumed: all 8,309 in-window postings carry an internal
  generation stamp in the same year as the message `Date:` header, 569,157 of
  569,157 entries at gap zero. Posting date is `artifact_listing`; the
  `approved:` / `received:` lines are `whois_creation`, the same type AFNIC's
  `.fr` registry data carries. All 118,766 of those registrar lines occur inside
  `.CA`-generated files and none anywhere else.
- **Classic hand-maintained maps.** The container is reposted on a schedule but
  the entries are submitted by site admins and refresh only when someone
  resubmits. Of 12,486 in-window entries carrying a `#W` stamp, only 1,031 are
  within a year of the posting date; the mass sits at gaps of two to nine years,
  and 31,960 more carry no stamp at all. "Listed in a file posted in 1996, last
  touched in 1989" does not evidence 1996, so these are candidate-only.

Applying that gate is worth minus 2,241 pairs and minus 578.6 equivalent-English
against the ungated figure, and it is the difference between a registry claim and
an inference.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from ark.canonical import to_registrable
from ark.ingest import YEARS
from ark.usenet import iter_messages, message_year

# `#N` names the site. Aliases follow after commas, and only the first is the
# registered name; the rest are routing aliases that do not resolve.
_ENTRY = re.compile(rb"(?m)^#N[ \t]+([^\s,]+)")

# The self-declared provenance of a registry-generated file. Anchored to the
# whole marker rather than to ".CA" alone, because the bare string appears in
# ordinary prose inside hand-maintained entries too.
_REGISTRY_MARKER = re.compile(
    rb"(?mi)^#R[ \t]+Automatically generated from a \.CA domain registration form"
)

# The registrar's own dates, inside an entry, in the comment column.
_APPROVED = re.compile(rb"(?m)^#[ \t]+(?:approved|received):.*?\b(19\d\d|20\d\d)\b")

_DATE_HEADER = re.compile(rb"(?mi)^Date:[ \t]*(.+)")

# Splitting on the lookahead keeps each entry with its own `#N` line.
_ENTRY_SPLIT = re.compile(rb"(?m)(?=^#N[ \t])")


@dataclass(frozen=True)
class MapRecord:
    """One registered name, its year, and which evidence class dates it."""

    domain: str
    year: int
    basis: str  # "registry_listing", "registry_creation" or "uncorroborated"
    posting_year: int | None
    identifier: str


def is_registry_generated(message: bytes) -> bool:
    """Whether the posting declares itself generated from registration forms."""
    return bool(_REGISTRY_MARKER.search(message))


def _first_name(block: bytes) -> str | None:
    match = _ENTRY.search(block)
    if not match:
        return None
    raw = match.group(1).decode("latin-1", "replace").lstrip(".").rstrip(".;,")
    return to_registrable(raw) or None


def records_in(message: bytes, identifier: str = "") -> Iterator[MapRecord]:
    """Every dated registered name in one map posting, with its evidence class."""
    header = _DATE_HEADER.search(message[:4000])
    posting_year = None
    if header:
        posting_year = message_year(header.group(1).decode("latin-1", "replace").strip())

    registry = is_registry_generated(message)
    blocks = _ENTRY_SPLIT.split(message)
    if len(blocks) < 2:
        return

    for block in blocks[1:]:
        domain = _first_name(block)
        if not domain:
            continue
        if registry:
            # The file was regenerated at posting time, so presence in it dates
            # the name to that posting.
            if posting_year in YEARS:
                yield MapRecord(domain, posting_year, "registry_listing", posting_year, identifier)
            approved = _APPROVED.search(block)
            if approved:
                year = int(approved.group(1))
                if year in YEARS:
                    yield MapRecord(domain, year, "registry_creation", posting_year, identifier)
        else:
            # Hand-maintained: the container's date says nothing about the entry.
            if posting_year in YEARS:
                yield MapRecord(domain, posting_year, "uncorroborated", posting_year, identifier)


def records_in_archive(path: Path) -> Iterator[MapRecord]:
    """Every dated registered name in an mbox archive of map postings."""
    for message in iter_messages(path):
        yield from records_in(message, identifier=path.stem)
