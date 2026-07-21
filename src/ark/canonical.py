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

extract = tldextract.TLDExtract(
    suffix_list_urls=[PSL_PATH.as_uri()],
    cache_dir=None,
    fallback_to_snapshot=False,
)

# define accepted label characters for domain names
_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
# define pattern to match IPv4 addresses
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def to_registrable(raw: str) -> str | None:
    """Reduce a host or URL to its registrable domain, or None for garbage.

    This is the dedup key for the whole pipeline: every domain, from every
    source, passes through here before touching the database. Input may be
    dirty (seed files carry mis-encoded URLs), so invalid lines return None
    rather than raising.
    """
    host = unquote(raw).strip().lower()
    if not host:
        return None
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
    # remove empty or IPv4 addresses
    if not host or _IPV4.match(host):
        return None
    # remove invalid labels
    if not all(_LABEL.match(label) for label in host.split(".")):
        return None
    # extract domain and suffix using the pinned PSL
    result = extract(host)
    # reject if either is missing
    if not result.domain or not result.suffix:
        return None
    return f"{result.domain}.{result.suffix}"
