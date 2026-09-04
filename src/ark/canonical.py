"""Host canonicalization built on a vendored Public Suffix List.

The PSL snapshot is committed with the package so registrable-domain
extraction never fetches from the network and gives identical results
on every machine.
"""

import re
from pathlib import Path
from urllib.parse import unquote

import tldextract

PSL_PATH = Path(__file__).parent / "data" / "public_suffix_list.dat"

# ccTLDs of the 1996-2001 web that were retired and no longer appear in the
# PSL: Yugoslavia, Netherlands Antilles, Burma, Czechoslovakia, East Germany,
# Great Britain, East Timor, US minor islands, Zaire
HISTORICAL_SUFFIXES = (
    "yu",
    "ac.yu",
    "co.yu",
    "edu.yu",
    "gov.yu",
    "org.yu",
    "an",
    "com.an",
    "edu.an",
    "net.an",
    "org.an",
    "bu",
    "cs",
    "dd",
    "gb",
    "tp",
    "um",
    "zr",
    "com.zr",
)

extract = tldextract.TLDExtract(
    suffix_list_urls=[PSL_PATH.as_uri()],
    cache_dir=None,
    fallback_to_snapshot=False,
    extra_suffixes=HISTORICAL_SUFFIXES,
)

# accepted label characters while parsing; underscores occur in real
# 1996-2001 subdomains and are only rejected in the registered label.
#
# **The `{0,61}` is RFC 1035's 63-character label limit and it is not pedantry.** His own
# calculator enforces it (`[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?`), and without it the funnel
# admitted names that cannot exist in DNS: fourteen reached the 2026-09-04 export, every one a
# joke URL somebody typed into a Usenet post, of which
# `thisisaveryveryverylongurlandyoudontwantittowrap...` at 112 characters is the shape. His
# program rejected all fourteen and the ship gate caught the 7.4918 EE disagreement, which is
# exactly the check earning its place. A name over 63 characters in one label was never a
# domain, so this belongs in the funnel and not in a shipping filter.
_LABEL = re.compile(r"^[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?$")
# the registered label itself must be strictly valid DNS
_STRICT_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
# RFC 1035's total length, which his validator also enforces as `(?=.{1,253}\Z)`
_MAX_HOST_LEN = 253
# define pattern to match IPv4 addresses
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


# **A reverse-DNS zone is not a website and never was.** `build_query_queue.py` already knew
# this and refused to spend a capture request on one, but nothing stopped one being STORED, so
# 64 of them reached the shipped annual files: `206.in-addr.arpa` and friends, harvested out of
# Usenet `From:` headers and announcement bodies.
#
# The reason it matters more than 64 rows should is the weight. `.arpa` scores **1.0000** in the
# CC-MAIN model, the highest value in the whole table, above `.mil` at 0.9981, so this is junk
# concentrated in the top weight: exactly the shape law 5 describes. Ding's own validator accepts
# `206.in-addr.arpa` as a well-formed domain, so his side would score it too.
#
# Found 2026-08-18 by a hunt lens that noticed `.arpa` entering the metric at weight 1. Rejected
# here rather than at export, because this function is the single funnel every domain from every
# source passes through before touching the database.
_REVERSE_DNS = (".in-addr.arpa", ".ip6.arpa")


def _canonicalize(raw: str) -> tuple[str | None, str | None]:
    """Return (registrable, None) on success or (None, reject_reason)."""
    host = unquote(raw).strip().lower()
    if not host:
        return None, "empty line"
    # remove URL scheme
    host = re.sub(r"^[a-z][a-z0-9+.-]*://", "", host)
    # remove scheme-relative prefix
    host = host.removeprefix("//")
    # remove path, query and fragment
    host = re.split(r"[/?#]", host, maxsplit=1)[0]
    # remove userinfo
    host = host.rsplit("@", maxsplit=1)[-1]
    # remove port
    host = re.sub(r":\d+$", "", host)
    # remove stray separator punctuation around the name (".www.foo.com", ",foo.com");
    # never leading hyphens: those would alter the name itself
    host = host.strip(".,")
    if not host:
        return None, "empty line"
    if _IPV4.match(host):
        return None, "ip address, not a domain"
    if host.endswith(_REVERSE_DNS) or host in {"in-addr.arpa", "ip6.arpa"}:
        return None, "reverse-dns zone, not a website"
    if len(host) > _MAX_HOST_LEN:
        return None, "longer than 253 characters, so not a name DNS can carry"
    if not all(_LABEL.match(label) for label in host.split(".")):
        return None, "invalid hostname syntax"
    # extract domain and suffix using the pinned PSL plus historical ccTLDs
    result = extract(host)
    if not result.suffix:
        return None, "no known public suffix"
    if not result.domain:
        return None, "bare public suffix, not a registered domain"
    if not _STRICT_LABEL.match(result.domain):
        return None, "invalid character in registered label"
    return f"{result.domain}.{result.suffix}", None


def to_registrable(raw: str) -> str | None:
    """Reduce a host or URL to its registrable domain, or None for garbage.

    This is the dedup key for the whole pipeline: every domain, from every
    source, passes through here before touching the database. Input may be
    dirty (seed files carry mis-encoded URLs), so invalid lines return None
    rather than raising.
    """
    return _canonicalize(raw)[0]


def reject_reason(raw: str) -> str | None:
    """Explain why a line is dropped, or None if it canonicalizes fine."""
    return _canonicalize(raw)[1]
