"""When each TLD was delegated, for TLDs that did not exist throughout 1996-2001.

**A domain cannot have existed before its TLD did.** `domain_creation_bulk` was admitted in
phase 5 after checking exactly this, but the check was written against the six TLDs delegated in
2001 and so could not see a TLD delegated in 2005 or later. Measured 2026-08-24 against the live
store: **1,087 assigned pairs predate their own TLD's delegation**, across fourteen TLDs, led by
`.eu` at 409 and `.info` at 202. Small in weight, 450.2 equivalent-English, and exactly the class
the reviewer's validator is entitled to reject.

Only TLDs delegated in 1996 or later need an entry. Everything absent from this table existed for
the whole window and is unconstrained.
"""

# ICANN delegation year. A pair is impossible if its assigned year is EARLIER than this.
DELEGATED: dict[str, int] = {
    # the 2001 new-gTLD round
    "aero": 2001,
    "biz": 2001,
    "coop": 2001,
    "info": 2001,
    "museum": 2001,
    "name": 2001,
    "pro": 2002,
    # the 2004-2005 sponsored round and later
    "asia": 2007,
    "cat": 2005,
    "eu": 2005,
    "jobs": 2005,
    "mobi": 2005,
    "post": 2012,
    "tel": 2007,
    "travel": 2005,
}


def sql_predicate(column: str = "domain", year_column: str = "assigned_year") -> str:
    """A SQL predicate that is true only for pairs whose TLD already existed that year.

    Emitted rather than hand-written at each call site, because the `.arpa` filter had to be
    repeated in four places in `export.py` and a fifth destination was added without it.
    """
    clauses = [
        f"NOT ({column} LIKE '%.{tld}' AND {year_column} < {year})"
        for tld, year in sorted(DELEGATED.items())
    ]
    return "\n      AND ".join(clauses)
