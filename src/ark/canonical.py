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
# 1996-2001 subdomains and are only rejected in the registered label
_LABEL = re.compile(r"^[a-z0-9_]([a-z0-9_-]*[a-z0-9_])?$")
# the registered label itself must be strictly valid DNS
_STRICT_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
# define pattern to match IPv4 addresses
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


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
    # remove trailing dot
    host = host.rstrip(".")
    if not host:
        return None, "empty line"
    if _IPV4.match(host):
        return None, "ip address, not a domain"
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
