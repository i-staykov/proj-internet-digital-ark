"""The signed-off evidence taxonomy.

A type's disposition decides where its rows may go: master types may back
a (domain, year) assignment, candidate-only types never do. The schema's
CHECK constraint is generated from these sets, so code and schema cannot
drift apart.
"""

# master-eligible: a row of this type may create a domain_year assignment
MASTER_TYPES = frozenset(
    {
        "cdx_timestamp",
        "artifact_listing",
        "link_source",
        "dated_directory",
        "whois_creation",
    }
)

# candidate-only: stored for provenance and verification priority, never a year
CANDIDATE_ONLY_TYPES = frozenset({"link_target"})

ALL_TYPES = MASTER_TYPES | CANDIDATE_ONLY_TYPES
CANDIDATE_ONLY_SQL = ", ".join(f"'{t}'" for t in sorted(CANDIDATE_ONLY_TYPES))

# **Spec XIV, and the unit is the METHOD, not the type.** The annual masters are a
# website-evidence product: a row may enter the CLAIM only when the retained evidence
# shows the exact host serving the web in the target year. `artifact_listing` and
# `dated_directory` each land on both sides of that line, so the type cannot decide it.
#
# The list is an ALLOWLIST and unknown methods fail closed, into candidates. A method
# missing here costs a claim we can add back; a method wrongly here is a claim he
# refuses, and refusals are what the screen exists to prevent.
WEB_METHODS = frozenset(
    {
        # IA CDX, the reference standard: an exact-host capture with its stamp
        "ia_cdx_collapsed_query",
        "ia_cdx_domain_sweep",
        "ia_cdx_year_query",
        "ia_cdx_gap_hostgrain",
        "bulk_cdx_file",
        "wayback_availability",
        # TimeMap, the same index read through Memento. `nypw_timemap_non_200` is NOT
        # here: XIV asks for a non-error capture and that method is defined by not
        # being one.
        "nypw_timemap",
        "nypw_timemap_hostgrain",
        "nypw_firstcdx_hostgrain",
        # the registrable-grain arm of the line above. It can only ever offer a domain its
        # FIRST year, which the IA-derived baseline already holds, so it is here for
        # consistency with its own sibling and not for what it adds.
        "nypw_first_capture_index",
        # a custodian's own per-host/year web-capture extract
        "arquivo_cdxj",
        "arquivo_ia_cdxj_hostgrain",
        "poland_pl_extract_hostgrain",
        "early_web_hostgrain",
        # a custodian's dated per-host mirror of the page itself. A defaced site was
        # serving the web at the stamped date and attrition mirrored what it served,
        # which is his custodian pattern and is non-error by construction.
        "attrition_defacement_mirror_index",
        # a custodian's own dated request log: an HTTP Archive agent's request to the exact
        # host, answered 2xx or 3xx (#449)
        "httparchive_har_entry",
        # a dated crawl list's node: a page fetched inside one year, status-less (#286)
        "crawl_list_node",
        # a dated web link graph naming the target host
        "ukwa_host_link_graph",
        "ukwa_hostgrain",
        "bl_geoindex_extract",
        # a captured page's own link to the host, the page dated by its capture stamp
        "page_link_host",
        # a captured bookmark file's entry for the host, dated by the browser's own ADD_DATE
        "bookmark_entry_host",
    }
)


# **What kind of web evidence a method is, as the delivery names it per row**: a dated web
# link graph naming the host, a dated dataset record (a crawl list's fetched page, an HTTP
# Archive request), else a capture of the host from an archive's index or extract.
_LINK_GRAPH = ("ukwa_host_link_graph", "ukwa_hostgrain", "bl_geoindex_extract", "page_link_host")
_DATASET = ("crawl_list_node", "httparchive_har_entry")
_BOOKMARK = ("bookmark_entry_host",)


def evidence_kind_sql(method: str) -> str:
    """`capture`, `link graph`, `dataset` or `dated bookmark entry` for a web method, else NULL."""
    graph = ", ".join(f"'{m}'" for m in _LINK_GRAPH)
    dataset = ", ".join(f"'{m}'" for m in _DATASET)
    bookmark = ", ".join(f"'{m}'" for m in _BOOKMARK)
    web = ", ".join(f"'{m}'" for m in sorted(WEB_METHODS | {REDIRECT_METHOD}))
    return (
        f"(CASE WHEN {method} IN ({graph}) THEN 'link graph'"
        f" WHEN {method} IN ({dataset}) THEN 'dataset'"
        f" WHEN {method} IN ({bookmark}) THEN 'dated bookmark entry'"
        f" WHEN {method} IN ({web}) THEN 'capture' END)"
    )


# **The one method admitted by its STATUS rather than by its name.** XIV's "non-error"
# qualifier attaches to the custodian-extract pattern, not to the IA CDX pattern beside it,
# and a NYPW TimeMap row IS the IA index read through Memento. So the status alone does not
# disqualify it, and the binding test is the section's opening sentence: web presence in the
# target year. A 2xx or 3xx is a server for the exact host answering deliberately and is
# admitted. 4xx and 5xx stay candidates: a wildcard vhost answers 404 for any name.
REDIRECT_METHOD = "nypw_timemap_non_200"
_STATUS_IN_VALUE = r"status (\d{3})"
# **A capture enters the masters only when the exact host answered 2xx or 3xx.** An error
# capture keeps its status in `evidence_value` (`cdx capture <ts> status 404 <host>`), so it
# stays a candidate whatever its method. Python's `re` and DuckDB read the pattern alike.
ERROR_STATUS = r"(^| )status [45][0-9][0-9]( |$)"
# **A capture whose replay does not open as the exact host in its year is no web presence**:
# the replay check marks its row `replay failed` before the token it names last (`cdx capture
# <ts> replay failed <host>`, `replay failed <ts>`), so the record leaves the masters and ships
# as a candidate, whatever its method or status.
REPLAY_FAILED = r"(^| )replay failed( |$)"


def web_evidence_sql(alias: str = "e") -> str:
    """The XIV predicate, for a query that has `evidence` joined as `alias`."""
    allowed = ", ".join(f"'{method}'" for method in sorted(WEB_METHODS))
    return (
        f"({alias}.acquisition_method IN ({allowed})"
        f" AND NOT regexp_matches({alias}.evidence_value, '{ERROR_STATUS}')"
        f" AND NOT regexp_matches({alias}.evidence_value, '{REPLAY_FAILED}')"
        f" OR ({alias}.acquisition_method = '{REDIRECT_METHOD}'"
        f" AND regexp_extract({alias}.evidence_value, '{_STATUS_IN_VALUE}', 1)"
        " SIMILAR TO '[23]..'"
        f" AND NOT regexp_matches({alias}.evidence_value, '{REPLAY_FAILED}')))"
    )


_TS = "[0-9]{14}"
_CAPTURE = "^cdx capture [0-9]{14} (status [0-9]{3} )?(replay failed )?[^ ]+$"
_LINK = "^host_link_graph:[0-9]{4} [^ ]+$"
# the linking page as its ARC record, its capture stamp and URL, then the linked host
_PAGE_LINK = "^page link [0-9]{4} https?://[^ ]+#arc [0-9]+ [0-9]+ #[0-9]{14} [^ ]+ [^ ]+$"
# the bookmark file's capture, the entry's line and its ADD_DATE (epoch, then yyyymmdd), the host
_BOOKMARK_ENTRY = (
    "^bookmark entry [0-9]{4} https?://[^ ]+#replay #[0-9]{14} line [0-9]+"
    " ADD_DATE [0-9]+ [0-9]{8} [^ ]+$"
)
_HAR = "^har entry [0-9]{14} status [23][0-9]{2} [^ ]+$"
_STAMPED = (
    "^((replay failed )?[0-9]{14}"
    "|nypw (first capture|timemap capture) (status [0-9]{3} )?(replay failed )?[0-9]{14})$"
)
_MIRROR = "/mirror/[0-9]{4}/[0-9]{2}/[0-9]{2}/([^/]+)/?$"


def exact_host_expr(alias: str) -> str:
    """The one host a row's capture names, or NULL.

    Chosen by the value's format, one branch per format a web method writes, never by the URL
    alone: a format this does not know names no host, so it fails closed. `cdx capture <ts>
    [status <nnn>] <host>`, `host_link_graph:<year> <host>`, `page link <year> <arc>#arc <offset>
    <length> #<ts> <page> <host>` and `har entry <ts> status <2xx or 3xx> <host>` name it last;
    a bare stamp and a TimeMap stamp take the URL's host, only when the URL carries the same
    stamp; a defacement mirror names it in its path. `cdx capture <year>` and
    `host_link_graph:<year>` name none.
    """
    v, u = f"{alias}.evidence_value", f"lower({alias}.evidence_url)"
    url_host = (
        f"rtrim(regexp_extract({u}, '^https?://[^/]+/(web|wayback)/({_TS})/"
        f"([a-z][a-z0-9+.-]*://)?([^/@]*@)?([^/:?#]+)', 5), '.')"
    )
    url_ts = f"regexp_extract({u}, '^https?://[^/]+/(web|wayback)/({_TS})/', 2)"
    return f"""(CASE
        WHEN regexp_matches({v}, '{_CAPTURE}') OR regexp_matches({v}, '{_LINK}')
          OR regexp_matches({v}, '{_HAR}') OR regexp_matches({v}, '{_PAGE_LINK}')
          OR regexp_matches({v}, '{_BOOKMARK_ENTRY}')
          THEN lower(regexp_extract({v}, ' ([^ ]+)$', 1))
        WHEN regexp_matches({v}, '{_STAMPED}') AND {url_ts} = regexp_extract({v}, '({_TS})$', 1)
          THEN nullif({url_host}, '')
        WHEN {alias}.acquisition_method = 'attrition_defacement_mirror_index'
          THEN nullif(regexp_extract({u}, '{_MIRROR}', 1), '')
        END)"""


def exact_host_sql(alias: str, name: str) -> str:
    """True only when the row names exactly `name`; unknown is false, so `NOT (...)` is safe."""
    return f"coalesce({exact_host_expr(alias)} = {name}, false)"


def qualifies_sql(alias: str, name: str) -> str:
    """The test a shipped record's row passes: the XIV method screen, and a capture of exactly
    `name`. A capture of `www.` or any other host beneath it never dates the registrable."""
    return f"coalesce(({web_evidence_sql(alias)}) AND {exact_host_sql(alias, name)}, false)"


def web_evidence_exists(id_column: str, name_column: str) -> str:
    """The claim's screen for a record that names its evidence row and its own name, e.g.
    `dy.evidence_id` and `dy.domain`: that row passes `qualifies_sql`.

    Lives here, beside the allowlist, because the CLAIM and the FIGURES quoted about the claim
    must apply the same screen.
    """
    return f"""
    EXISTS (
        SELECT 1 FROM evidence w
        WHERE w.evidence_id = {id_column} AND {qualifies_sql("w", name_column)}
    )
"""
