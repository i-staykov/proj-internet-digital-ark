"""The reviewer's TLD English-share table, which is what the score is made of.

The work is scored in **equivalent-English domains**: each (domain, year) record contributes
the English primary-page-language share of its right-most TLD, so `foo.uk` is worth 0.9813
of a record and `foo.de` 0.1324. The `CC-MAIN-2024-10`-derived table is his and is
reproduced exactly: his three-domain worked example gives 1.2766 here.

**The rule is his and is deliberately not improved on**: right-most label only, the row
where `lang == 'eng'`, share as a fraction, and **zero when the model does not know the
TLD**. Guessing a share for an unlisted TLD scores us on a number he cannot reproduce.

Vendored rather than read from git-ignored `feedback-phase-3/`, or a fresh clone ranks
everything at zero. Pinned like the public suffix list; sha256 begins 480d86bc287e.

**A fractional total is not a claim about individual domains.** It is an expected count over
a population and must never be described as a set of domains identified as English.
"""

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

SHARE_PATH = Path(__file__).parent / "data" / "tld_english_share.json"


@lru_cache(maxsize=1)
def english_weights(path: Path | None = None) -> dict[str, Decimal]:
    """TLD -> English page-language share as a fraction, the reviewer's own rule.

    Cached because callers ask per domain over hundreds of thousands of rows.
    `Decimal` rather than `float` so a total can be compared digit for digit with
    what his calculator prints; his figures are exact to four decimal places and
    binary floating point would not reproduce them.
    """
    raw = json.loads((path or SHARE_PATH).read_text(encoding="utf-8"))
    required = ("tld", "lang", "perc_of_tld")
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"English-share table is missing {', '.join(missing)}")
    weights = {
        str(tld).lower(): Decimal(str(share)) / Decimal("100")
        for tld, lang, share in zip(raw["tld"], raw["lang"], raw["perc_of_tld"], strict=True)
        if tld and lang == "eng"
    }
    if not weights:
        raise ValueError("English-share table contains no 'eng' rows")
    return weights


def weight_of(domain: str, weights: dict[str, Decimal] | None = None) -> Decimal:
    """What one (domain, year) record of this domain is worth to the score."""
    table = weights if weights is not None else english_weights()
    return table.get(domain.rsplit(".", 1)[-1].lower(), Decimal("0"))
