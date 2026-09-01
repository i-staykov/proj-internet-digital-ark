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
    # **Two-letter ccTLDs delegated AFTER the window.** `existed_predicate` waves through
    # anything two characters long, on the reasoning that ccTLDs existed throughout, and
    # these are the exceptions it therefore could not see. Measured 2026-08-31 the shipped
    # files carried 79 pairs under three of them and every one is a Usenet extraction
    # artifact: `eat.me`, `blow.me`, `byte.me`, `dontemail.me`, `e-mail.me`, `find.me`,
    # `call.me`, `contact.me`, joke and anti-harvester addresses typed into From: headers
    # years before `.me` existed. **Not one carries registry evidence**, which is what
    # separates them from the 138 suffix-shaped names that DO (`name.ca` has the Canadian
    # registry's own approval notice, `plc.nu` is in the .nu registry's expiry list, and
    # eleven more sit in RIPE or RDAP). Those are real registrations and stay.
    "ax": 2006,
    "bl": 2007,
    "bq": 2010,
    "cw": 2010,
    "me": 2007,
    "mf": 2007,
    "rs": 2007,
    "ss": 2011,
    "sx": 2010,
    "tl": 2005,
    "xk": 2016,
}


# **The eight gTLDs that existed for the whole window.** Everything else with a label of
# three or more characters was delegated in 2001 or later, so a 1996-2001 pair under it is
# impossible. Two-letter labels are ccTLDs, which existed throughout except for the handful
# listed in DELEGATED above.
WINDOW_GTLDS = ("com", "net", "org", "edu", "gov", "mil", "int", "arpa")


def existed_predicate(column: str = "domain", year_column: str = "assigned_year") -> str:
    """True only for pairs whose TLD could have existed in that year.

    **Why an allowlist and not a longer DELEGATED table.** `DELEGATED` names sixteen TLDs and
    stops at 2012, so it could not see the 2013 new-gTLD programme, which delegated roughly
    1,200 more. Text extraction then banks any English word that later became a gTLD, and
    measured 2026-08-31 the shipped files carried **749 such pairs and 423.9 EE across 131
    TLDs**: `.you`, `.here`, `.now`, `.sucks`, `.box`, `.world`, `.earth`. Several of those
    carry weight 1.0000, the maximum in the model, so they cost more per pair than almost
    anything real. Enumerating 1,200 delegations would go stale the same way; enumerating
    what DID exist does not, because that set is closed and in the past.

    Kept beside `sql_predicate` rather than replacing it: that one encodes real delegation
    years for TLDs that arrived DURING or just after the window, which this rule cannot
    express, and both are applied.
    """
    allowed = ", ".join(f"'{g}'" for g in sorted(WINDOW_GTLDS))
    tld = f"lower(split_part({column}, '.', -1))"
    # A two-letter label is a ccTLD; DELEGATED still constrains the few that arrived late.
    return f"(length({tld}) = 2 OR {tld} IN ({allowed}))"


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


def shipping_filter(prefix: str = "", with_year: bool = True) -> str:
    """The rows allowed into a shipped file, for a given table alias.

    Lives here rather than in `export` because `contribution` needs the same predicate
    and importing it from `export` is a cycle. Built per call site rather than
    string-replaced: the `.arpa` rule survives a blanket `.replace("domain", "dy.domain")`
    but the delegation rule also names `assigned_year`, and that replace leaves the year
    unqualified, which killed three of the four export destinations the first time.
    """
    dom = f"{prefix}domain" if prefix else "domain"
    if not with_year:
        # The candidate pool claims no year, so "the TLD did not exist YET" cannot apply to
        # it. But "the TLD never existed in the window at all" still can: a candidate under
        # `.sucks` can never be dated 1996-2001, so it is noise wherever it sits.
        return f"{dom} NOT LIKE '%.arpa'\n      AND {existed_predicate(dom)}"
    year = f"{prefix}assigned_year" if prefix else "assigned_year"
    return (
        f"{dom} NOT LIKE '%.arpa'"
        f"\n      AND {existed_predicate(dom, year)}"
        f"\n      AND {sql_predicate(dom, year)}"
    )
