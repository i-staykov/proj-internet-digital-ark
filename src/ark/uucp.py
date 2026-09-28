"""UUCP map postings: a registry dump the Usenet parser was reading as prose.

`comp.mail.maps` carried the UUCP maps, and from 1993 the `.CA` portion was generated
from the Canadian domain registry. Such a posting declares itself in the file:

    #R Automatically generated from a .CA domain registration form

and lists one entry per name keyed by `#N`, with the registrar's `received:` /
`approved:` dates inside the entry. This is registry data, so under Section XIII it is
a CANDIDATE lane: it never dates a year in the annual masters.

**The provenance gate must not be skipped.** Two kinds of posting share the format.
A `.CA` registry-generated file is regenerated at posting time, so presence dates the
name to the posting (`registry_listing`), and the registrar lines are `registry_creation`.
A classic hand-maintained map is reposted on a schedule while its entries go stale:
only 1,031 of 12,486 in-window entries with a `#W` stamp are within a year of the
posting, so those are `uncorroborated`.
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
