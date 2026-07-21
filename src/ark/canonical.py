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

_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$") # define accepted label characters for domain names
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$") # define pattern to match IPv4 addresses


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
    # scheme, path, query, fragment, userinfo, port
    host = re.sub(r"^[a-z][a-z0-9+.-]*://", "", host) # remove URL scheme
    host = host.removeprefix("//") # remove scheme-relative prefix
    host = re.split(r"[/?#]", host, maxsplit=1)[0] # remove suffix
    host = host.rsplit("@", maxsplit=1)[-1] # remove userinfo
    host = re.sub(r":\d+$", "", host) # remove port
    host = host.rstrip(".") # remove trailing dot
    if not host or _IPV4.match(host): # remove empty or IPv4 addresses
        return None
    if not all(_LABEL.match(label) for label in host.split(".")): # remove invalid labels
        return None
    result = extract(host) # extract domain and suffix using the pinned PSL
    if not result.domain or not result.suffix: # reject if either is missing
        return None
    return f"{result.domain}.{result.suffix}"
