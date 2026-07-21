"""Host canonicalization built on a vendored Public Suffix List.

The PSL snapshot is committed with the package so registrable-domain
extraction never fetches from the network and gives identical results
on every machine.
"""

from pathlib import Path

import tldextract

PSL_PATH = Path(__file__).parent / "data" / "public_suffix_list.dat"

extract = tldextract.TLDExtract(
    suffix_list_urls=[PSL_PATH.as_uri()],
    cache_dir=None,
    fallback_to_snapshot=False,
)
