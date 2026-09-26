"""Dated website announcements from Usenet archives (the Giganews donation to IA).

A post carries its own date and one or more website URLs, so the date is intrinsic to the
artifact. **Under Section XIII a Usenet post is a textual mention, so this is a CANDIDATE
lane: it cannot date a year in the annual masters.** It is scored on the candidate track at
the same rate.

**Two things make the source dangerous, and both shape the design.** A URL in a body is
typed by a human: the corpus holds `weddinqnetwork.com` and `dmjbuisness.co.uk`, and a
quarter of never-before-seen names are within one edit of a name the store holds. And a
mention is not an announcement: a moderated group announcing new sites is curated, a
commerce group is people advertising a competitor or an aspiration.

**Corroboration gates admission and nothing else does.** A domain another source already
places in an annual file is real, so only the year is open and the post answers it with an
auditable Message-ID. A name appearing only in Usenet becomes `link_target` and goes to the
candidate pool to earn its own evidence. Group purpose is RECORDED, not enforced:
`is_moderated_announce` reports the split, every evidence row names its group, and nothing
is discarded either way.
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
    """Whether a group is a moderated announcement forum. Reported, not enforced.

    A COMPONENT test, not a suffix test, because the marker is not always last:
    `news.announce.conferences` and `news.announce.newgroups` are both moderated.
    `MODERATED_ANNOUNCE_GROUPS` names the handful that say so nowhere in the name.
    """
    parts = set(group.split("."))
    return group in MODERATED_ANNOUNCE_GROUPS or bool(parts & {"announce", "moderated"})


_URL = re.compile(r"https?://[^\s<>\"'\)\],;]+", re.IGNORECASE)
# An address written without a scheme, `www.foo.com`, which `_URL` cannot see and which
# people wrote constantly in 1996-1999. Anchored on the `www.` label rather than any bare
# host; the lookbehind keeps it off hosts already inside a URL or an email address.
# `bare_domains_in_body` reads the bare form under its own source name, so the two stay
# comparable and nothing already ingested changes meaning.
_BARE_WWW = re.compile(
    r"(?<![\w.@/-])www\.[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+",
    re.IGNORECASE,
)
# The bare form, `foo.com` with no scheme and no `www.`. The pattern can afford recall
# because **every row passes `split_by_corroboration` before it can date anything**: a
# company name or half an email address is not a domain another lineage has placed in
# `domain_year`, so it becomes a candidate and asserts nothing.
#
# Four guards, each answering a real failure in this corpus:
#
#   * a **TLD allowlist**, the only anchor a bare name has; a generic dot rule fabricates
#     domains out of punctuation and file names (`ads.my`, `article.pl` sank the generic
#     token scan on `alt.bbs.lists`).
#   * the **lookbehind** `(?<![\w.@/-])`, which stops a match starting inside a longer
#     dotted token, so URLs and email addresses stay with the patterns that own them.
#   * the **lookahead** `(?![a-z0-9@-])`, which refuses `end.Company` and a domain-shaped
#     email local part such as `john.com@example.org`.
#   * **greedy labels before the TLD**, so `foo.com.au` matches whole.
#
# Body text only, never headers: `Path:`, `Xref:` and `Newsgroups:` are dotted tokens by
# construction, and reading them banks news servers and newsgroup names as websites.
_BARE_TLDS = "com|net|org|edu|gov|us|uk|au|ca|nz|ie|za|sg"
_BARE_DOMAIN = re.compile(
    rf"(?<![\w.@/-])[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)*\.(?:{_BARE_TLDS})(?![a-z0-9@-])",
    re.IGNORECASE,
)
# the Giganews rewrite: a bare `YYYY/MM/DD` or `YYYY-MM-DD` where RFC 822 expects
# "Tue, 18 Jun 1996 12:00:00 GMT"
_ISO_DATE = re.compile(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})")
_MESSAGE_SEP = re.compile(rb"^From ", re.MULTILINE)
# the RFC 822 header/body boundary, tolerating both line endings
_BODY_SEP = re.compile(rb"\r?\n\r?\n")

# Excluded by the registrable-grain extractor: these hosting and archive names collapse
# under canonicalization, and Usenet plumbing is not a website anyone announced. Not an
# annual output-unit rule.
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

    Two formats, and missing the second is expensive. The Giganews donation rewrote a
    large share of dates as a bare `YYYY/MM/DD`, which `parsedate_to_datetime` rejects:
    **21,346 of 23,282 messages** in `comp.infosystems.www.announce`, so an RFC 822-only
    parser silently discards 92% of the archive and reports the rest as the whole.
    """
    if not raw_date:
        return None
    # `Message.get` returns a `Header`, not a `str`, on an RFC 2047 encoded value, and
    # `Header` has no `.strip()`. Rare (one archive in 8,258) and costly: the splitter
    # does a batch in one call, so one bad archive aborts 2,500 and every bank retries
    # the identical batch.
    text = str(raw_date).strip()
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
    for host in _BARE_WWW.findall(body or ""):
        domain = to_registrable(host)
        if domain and domain not in INFRASTRUCTURE:
            found[domain] = None
    _, address = email.utils.parseaddr(from_header or "")
    if "@" in address:
        domain = to_registrable(address.rsplit("@", 1)[1])
        if domain and domain not in INFRASTRUCTURE:
            found[domain] = None
    return list(found)


def bare_domains_in_body(body: str) -> list[str]:
    """Registrable domains written bare in a message body, deduplicated in order.

    Separate from `domains_in_message` so the bare form carries its own source name and can
    be measured or dropped without touching what `usenet_announce` claimed. Pass the body,
    not the whole message: see `_BARE_DOMAIN`.

    The fourth guard lives here rather than in the pattern: all-digit labels before the TLD
    are a version string, not a site, or `upgraded to 4.0.2.au` canonicalises to the
    fabricated `2.au`. It costs the handful of genuinely all-numeric domains (`123.com`).
    """
    found: dict[str, None] = {}
    for host in _BARE_DOMAIN.findall(body or ""):
        if all(label.isdigit() for label in host.split(".")[:-1]):
            continue
        domain = to_registrable(host)
        if domain and domain not in INFRASTRUCTURE:
            found[domain] = None
    return list(found)


def body_of(raw: bytes) -> str:
    """The body of a raw message, split on the first blank line.

    A cheap split rather than a full `email` parse: this runs over 507 million messages,
    and the header block is exactly what must not be scanned. No blank line means no
    body and no yield, which is the safe direction.
    """
    match = _BODY_SEP.search(raw)
    return raw[match.end() :].decode("latin-1", "replace") if match else ""


def iter_messages(path: Path) -> Iterator[bytes]:
    """Yield each raw message from an mbox, or from a zip holding one.

    The archives ship as `<group>.mbox.zip` and the member is read directly rather than
    unpacked. It holds the decompressed mbox in memory, which is the limit on this route:
    the largest group so far is 150 MB compressed, about 600 MB expanded. Only the separator
    scan needs the whole blob, so a much larger group wants streaming.
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
    """Split an mbox on its `From ` separators.

    The classic mbox ambiguity: an unescaped body line beginning "From " cuts a message
    in two. Bounded and safe, because the fragment carries no `Date` or `Message-ID` and
    the caller drops it, so a mis-split costs one message and cannot invent evidence.
    """
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
        # Counted apart on purpose: a group wholly out of window and a group whose dates
        # cannot be read look identical under one counter and call for opposite responses,
        # drop the source or fix the parser.
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
