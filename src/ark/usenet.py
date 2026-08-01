"""Dated website announcements from Usenet archives.

Giganews donated its Usenet archive to the Internet Archive in 2013. The
announcement and commerce hierarchies contain, per message, a posting date and
one or more website URLs, which is item-level year evidence of an unusual kind:
the date is intrinsic to the artifact rather than recovered from a crawl.

That matters for the years this project is weakest in. A moderated announcement
posted in 1997 saying "new site at example.com" is contemporaneous evidence that
the site was live in 1997, and it does not depend on the Internet Archive having
crawled it. Our 1996 and 1997 additions are 0.4% and 0.0% capture-backed, so a
route that does not need a capture reaches exactly where the crawl cannot.

**Two things make this source dangerous, and both shape the design.**

A URL in a message body is typed by a human. The corpus contains
`weddinqnetwork.com` and `dmjbuisness.co.uk`, and roughly a quarter of the
never-before-seen names are within one edit of a name the store already holds.
Admitting those would put invented domains into an annual file, which is the one
failure this project cannot afford.

And a mention is not an announcement. A moderated group whose stated purpose is
announcing new websites is an editorially curated dated listing, which the brief
treats as master-eligible. A commerce or marketplace group is people advertising,
where a URL may be a competitor, a typo or an aspiration.

**Corroboration is what gates admission**, and it is the only thing that does. A
domain another source already places in an annual file is real, so the only open
question is the year, which the post answers with an auditable Message-ID: that
half becomes `dated_directory`. A name appearing only in Usenet has neither its
existence nor its year independently attested, so it becomes `link_target` and
goes to the candidate pool to earn its own evidence. This is the same split
`expand.py` applies to archived directory pages, and for the same reason: the
post may be sound while the transcription is not.

Group purpose is recorded rather than enforced, and that is a deliberate choice
worth stating because it is the one place a reviewer might reasonably disagree.
The stricter alternative would admit only moderated announcement groups. It was
not taken because, once corroboration has established that the domain is real,
a URL written in a dated public post is contemporaneous evidence that the site
was in use that year whether the group was moderated or not: advertising a dead
site is unusual. `is_moderated_announce` therefore exists to *report* the
split rather than to gate it, every evidence row names the group it came from,
and a reviewer who disagrees can filter on that name without reprocessing
anything.

Nothing is discarded either way. A name that cannot be admitted becomes a
candidate, which is what the candidate pool is for.
"""

import email
import email.utils
import re
import zipfile
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

from ark.bulk import BulkRecord
from ark.canonical import to_registrable
from ark.ingest import YEARS

# Moderated announcement forums whose names do not follow the `.announce` or
# `.moderated` convention that `is_moderated_announce` relies on.
MODERATED_ANNOUNCE_GROUPS = frozenset(
    {
        "comp.internet.net-happenings",
    }
)


def is_moderated_announce(group: str) -> bool:
    """Whether a group is a moderated announcement forum.

    Usenet convention carries most of this: a group whose last component is
    `announce` or `moderated` is moderated by long-standing practice, so the
    rule is expressed as a suffix test rather than a list nobody will maintain.
    `MODERATED_ANNOUNCE_GROUPS` then names the handful that are moderated
    announcement forums without saying so in their name, of which
    `comp.internet.net-happenings` is the important one.

    This classification is reported, not enforced. See the module docstring.
    """
    return (
        group in MODERATED_ANNOUNCE_GROUPS
        or group.endswith(".announce")
        or group.endswith(".moderated")
    )


_URL = re.compile(r"https?://[^\s<>\"'\)\],;]+", re.IGNORECASE)
# the Giganews rewrite: a bare `YYYY/MM/DD` or `YYYY-MM-DD` where RFC 822 expects
# "Tue, 18 Jun 1996 12:00:00 GMT"
_ISO_DATE = re.compile(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})")
_MESSAGE_SEP = re.compile(rb"^From ", re.MULTILINE)

# Hosts that carry no registrable information of their own: free-hosting and
# archive infrastructure collapse to one registered domain under III.8, and the
# Usenet plumbing is not a website anyone announced.
INFRASTRUCTURE = frozenset(
    {
        "google.com",
        "googlegroups.com",
        "archive.org",
        "deja.com",
        "dejanews.com",
        "usenet.com",
        "giganews.com",
        "w3.org",
        "ietf.org",
    }
)


def message_year(raw_date: str) -> int | None:
    """The posting year, or None if the header is missing or unreadable.

    Two formats, and missing the second one is expensive. Most posts carry an
    RFC 822 date, but the Giganews donation rewrote a large share of them as a
    bare `YYYY/MM/DD`, which `parsedate_to_datetime` rejects outright. In
    `comp.infosystems.www.announce` that is **21,346 of 23,282 messages**, so a
    parser that only understands RFC 822 silently discards 92% of the archive
    and reports the remainder as though it were the whole corpus.
    """
    if not raw_date:
        return None
    text = raw_date.strip()
    year: int | None = None
    try:
        parsed = email.utils.parsedate_to_datetime(text)
        year = parsed.year if parsed is not None else None
    except (TypeError, ValueError, OverflowError):
        year = None
    if year is None:
        match = _ISO_DATE.match(text)
        if match:
            year = int(match.group(1))
    return year


def urls_in(text: str) -> list[str]:
    """Every http(s) URL in a message body, in order of appearance."""
    return _URL.findall(text or "")


def domains_in_message(body: str, from_header: str) -> list[str]:
    """Registrable domains a message points at, deduplicated in order.

    The `From:` domain counts because in announcement and vendor posts the
    sender is very often the site being announced, and it is the one string in
    the message that a mail system validated rather than a human typed.
    """
    found: dict[str, None] = {}
    for url in urls_in(body):
        domain = to_registrable(url)
        if domain and domain not in INFRASTRUCTURE:
            found[domain] = None
    _, address = email.utils.parseaddr(from_header or "")
    if "@" in address:
        domain = to_registrable(address.rsplit("@", 1)[1])
        if domain and domain not in INFRASTRUCTURE:
            found[domain] = None
    return list(found)


def iter_messages(path: Path) -> Iterator[bytes]:
    """Yield each raw message from an mbox, or from a zip holding one.

    The archives ship as `<group>.mbox.zip`. Reading the member directly avoids
    unpacking 300 MB of mbox to disk for a single pass.
    """
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                with archive.open(name) as fh:
                    yield from _split_mbox(fh.read())
    else:
        yield from _split_mbox(path.read_bytes())


def _split_mbox(blob: bytes) -> Iterator[bytes]:
    starts = [m.start() for m in _MESSAGE_SEP.finditer(blob)]
    if not starts:
        if blob.strip():
            yield blob
        return
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(blob)
        yield blob[start:end]


def parse_usenet(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Yield one record per (domain, posting year) found in an archive.

    The evidence value is the `Message-ID`, which is the opaque record
    identifier that makes a claim auditable: it names the exact post a year
    assignment came from, and Usenet message IDs are globally unique by design.
    """
    for raw in iter_messages(path):
        stats["messages"] += 1
        try:
            message = email.message_from_bytes(raw)
        except Exception:  # noqa: BLE001 - one malformed post must not end the run
            stats["unparseable_message"] += 1
            continue
        year = message_year(message.get("Date", ""))
        # Counted apart on purpose. A group that is entirely out of window and a
        # group whose dates cannot be read look identical under one counter, and
        # they call for opposite responses: drop the source, or fix the parser.
        # `alt.www.webmaster` is 170 MB and 100% out of window (2006 to 2013),
        # while `comp.infosystems.www.announce` looked 92% undated until the
        # Giganews date format was handled.
        if year is None:
            stats["unreadable_date"] += 1
            continue
        if year not in YEARS:
            stats["out_of_window"] += 1
            continue
        message_id = (message.get("Message-ID") or "").strip()
        if not message_id:
            stats["no_message_id"] += 1
            continue

        body = _body_text(message)
        domains = domains_in_message(body, message.get("From", ""))
        if not domains:
            stats["no_domains"] += 1
            continue
        stats["messages_with_domains"] += 1
        for domain in domains:
            stats["records"] += 1
            yield BulkRecord(
                raw=domain,
                year=year,
                evidence_value=f"usenet post {message_id}",
                evidence_url=f"https://archive.org/details/usenet-{path.stem.split('.')[0]}",
            )


def _body_text(message: email.message.Message) -> str:
    """Best-effort plain text of a post, tolerating any declared charset."""
    parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == "text":
                parts.append(_decode_part(part))
    else:
        parts.append(_decode_part(message))
    return "\n".join(parts)


def _decode_part(part: email.message.Message) -> str:
    try:
        payload = part.get_payload(decode=True)
    except Exception:  # noqa: BLE001 - malformed encodings are common here
        payload = None
    if payload is None:
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    charset = part.get_content_charset() or "latin-1"
    try:
        return payload.decode(charset, "replace")
    except LookupError:
        return payload.decode("latin-1", "replace")
