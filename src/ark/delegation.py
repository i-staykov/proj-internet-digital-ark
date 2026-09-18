"""When each TLD was delegated, for TLDs that did not exist throughout 1996-2001.

**A domain cannot have existed before its TLD did**, and that is exactly the class the
reviewer's validator is entitled to reject: measured 1,087 pairs and 450.2 EE predating
their own TLD across fourteen TLDs, led by `.eu` at 409 and `.info` at 202.

Only TLDs delegated in 1996 or later need an entry. Anything absent existed for the whole
window and is unconstrained.
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
    # **Two-letter ccTLDs delegated AFTER the window**, the exceptions `existed_predicate`
    # cannot see because it waves through any two-character label. Measured: 79 pairs under
    # three of them, every one a Usenet extraction artifact (`eat.me`, `dontemail.me`,
    # joke and anti-harvester addresses typed into From: headers). None carries registry
    # evidence, which is what separates them from the 138 suffix-shaped names that do
    # (`name.ca` in the Canadian registry's approval notice, `plc.nu` in the .nu expiry
    # list), and those are real registrations that stay.
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


# **The eight gTLDs that existed for the whole window.** Any other label of three or more
# characters was delegated in 2001 or later, so a 1996-2001 pair under it is impossible.
# Two-letter labels are ccTLDs, which existed throughout bar the handful in DELEGATED.
WINDOW_GTLDS = ("com", "net", "org", "edu", "gov", "mil", "int", "arpa")


def existed_predicate(column: str = "domain", year_column: str = "assigned_year") -> str:
    """True only for pairs whose TLD could have existed in that year.

    **An allowlist, not a longer DELEGATED table.** The 2013 gTLD programme delegated some
    1,200 names, and text extraction banks any English word that later became one: measured
    749 such pairs and 423.9 EE across 131 TLDs (`.you`, `.now`, `.sucks`, `.world`), several
    at weight 1.0000, the model's maximum. Enumerating what DID exist cannot go stale,
    because that set is closed and in the past.

    Both predicates are applied. This one cannot express `sql_predicate`'s real delegation
    years for TLDs that arrived during or just after the window.
    """
    allowed = ", ".join(f"'{g}'" for g in sorted(WINDOW_GTLDS))
    tld = f"lower(split_part({column}, '.', -1))"
    # A two-letter label is a ccTLD; DELEGATED still constrains the few that arrived late.
    return f"(length({tld}) = 2 OR {tld} IN ({allowed}))"


def sql_predicate(column: str = "domain", year_column: str = "assigned_year") -> str:
    """A SQL predicate that is true only for pairs whose TLD already existed that year.

    Emitted, never hand-written at a call site: a destination added without it ships.
    """
    clauses = [
        f"NOT ({column} LIKE '%.{tld}' AND {year_column} < {year})"
        for tld, year in sorted(DELEGATED.items())
    ]
    return "\n      AND ".join(clauses)


def shipping_filter_for(column: str, year_column: str) -> str:
    """The same rule for a table whose name column is not called `domain`.

    `hostname_year` is the case that needs it: a hostname under a TLD that did not exist in
    its year is the same error as a domain under one, and gets the `.arpa` rule too.
    """
    return (
        f"{column} NOT LIKE '%.arpa'"
        f"\n      AND {existed_predicate(column, year_column)}"
        f"\n      AND {sql_predicate(column, year_column)}"
    )


def shipping_filter(prefix: str = "", with_year: bool = True) -> str:
    """The rows allowed into a shipped file, for a given table alias.

    Lives here rather than in `export` because `contribution` needs the same predicate and
    importing it from `export` is a cycle. Built per call site, never string-replaced: a
    blanket `.replace("domain", "dy.domain")` leaves `assigned_year` unqualified.
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
