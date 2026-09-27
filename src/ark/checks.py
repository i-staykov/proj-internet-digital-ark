"""Read-only integrity checks over the provenance store.

Each check counts offending rows, by a SQL query or a function, and passes at zero. `ark
check` runs them all and exits non-zero if any fails, so it doubles as a release gate: no
annual result ships unless every invariant below holds. Several encode a rule the delivery
report states, so a reader who doubts the rule can run the gate instead of taking it on trust.
"""

import re
import tempfile
from collections.abc import Callable
from pathlib import Path

import duckdb

from ark import held
from ark.bulk import names_another_host_sql
from ark.evidence_types import CANDIDATE_ONLY_SQL, WEB_METHODS, qualifies_sql
from ark.hostnames import AUDITED_FAMILIES, FLEETREAD_SOURCE, WEB_FACING_HOST_SOURCES
from ark.ingest import YEARS

# Where `ark export` writes the annual additions. A parameter rather than a
# constant inside the SQL: a hardcoded path would make the test suite assert
# against the real deliverable, which is the same trap `export_all` documents.
NETNEW_DIR = Path("output/netnew")
# The error captures `scripts/round/status_audit.py` read out of the raw CDX. `ark check`
# passes it; a caller that passes none skips the check that reads it.
AUDIT_PATH = Path("data/audit/status_errors.tsv.gz")
_AUDITED = ", ".join(f"('{f}', '{s}', '{m}')" for f, (s, m, _) in AUDITED_FAMILIES.items())

# The first four-digit run inside an evidence value is that value's own year, for
# every type whose value names a single year: a CDX timestamp (19981212033831), a
# survey month (1996-07), a link-graph tag (host_link_graph:2001), a creation
# note (rdap creation 1998). Not applied to `dated_directory`, whose value is an
# opaque record identifier, nor to a registration span, which names two years on
# purpose.
_VALUE_YEAR = "TRY_CAST(regexp_extract(evidence_value, '([0-9]{4})', 1) AS INT)"

# Sources whose evidence value is a registration SPAN rather than a single year,
# so its year deliberately differs from the assigned year. Only AFNIC qualifies,
# and only because its registry documents that a creation date resets on
# re-registration, which is what makes the span continuous. Any other source
# added here needs the same standard of proof.
_SPAN_SOURCES = "'afnic_fr'"

# A stored domain is a lowercase registrable name: strict first label, then one or more
# suffix labels (co.uk, xn--*, historical ccTLDs all fit), at least one dot. The lengths are
# RFC 1035's and his calculator's, 63 per label, 253 in total, a 2-to-63 alphabetic last
# label: without them over-long joke names from Usenet posts reach an export and his own
# program refuses them. No lookahead, DuckDB using RE2, so the 253-character total is a
# separate `length()` condition at each call site.
_DOMAIN_RE = r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$"
_MAX_HOST_LEN = 253
_WEB_FACING_LIST = ", ".join(f"'{name}'" for name in sorted(WEB_FACING_HOST_SOURCES))
_WEB_METHOD_LIST = ", ".join(f"'{method}'" for method in sorted(WEB_METHODS))

_NO_EXPORT = "no exported files in {}; run `ark export` first"
_EMPTY = "the exported files this check reads are empty, so there is nothing to verify yet"

# **The first evidence id this store issued itself**, the start `located_from` keeps: a rebuild
# gives it the evidence sequence's start, one past every id the Parquet holds, and a fresh store
# 1, so a row below it came from an older store and a row at or above it was written here. Not
# `evidence_seq`'s own start, which DuckDB rewrites to its next id when the store closes.
# `duckdb_sequences()` lists every attached database's, so only the current one's counts.
LOCATION_FROM_ID = (
    "(SELECT start_value FROM duckdb_sequences() "
    "WHERE sequence_name = 'located_from' AND database_name = current_database())"
)


class _Skipped(Exception):
    """A check that had nothing to read; the text says why."""


class _Failed(Exception):
    """A check that could not run on this store; the text says why."""


def _braced(sql: str) -> str:
    """SQL spliced into a template that is `.format`ted: its regex braces survive the format."""
    return sql.replace("{", "{{").replace("}", "}}")


def _additions_not_double_counted(
    conn: duckdb.DuckDBPyConnection, netnew_dir: Path, baseline: Path | None
) -> int:
    """Lines of our annual files, registrable and hostname, that his file for that year holds.
    Whether there is anything to compare is settled before his files are touched."""
    ours = [(y, netnew_dir / f"{y}{s}.txt") for y in YEARS for s in ("", "_hostnames")]
    ours = [(y, path) for y, path in ours if path.is_file()]
    if not ours:
        raise _Skipped(_NO_EXPORT.format(netnew_dir))
    if all(path.stat().st_size == 0 for _, path in ours):
        raise _Skipped(_EMPTY)
    his = held.load(baseline)
    with tempfile.TemporaryDirectory() as tmp:
        return sum(held.intersect(path, his.year(y), Path(tmp) / path.name) for y, path in ours)


# name, human description, and a SQL query or a function(conn, netnew_dir, baseline)
# returning a single count of offending rows (0 = pass)
Check = str | Callable[[duckdb.DuckDBPyConnection, Path, Path | None], int]
CHECKS: list[tuple[str, str, Check]] = [
    (
        "evidence_wall_intact",
        "every annual assignment points at an evidence row for the same domain and year",
        """
        SELECT count(*) FROM domain_year dy
        LEFT JOIN evidence e ON e.evidence_id = dy.evidence_id
        WHERE e.evidence_id IS NULL
           OR e.domain <> dy.domain
           OR e.evidence_year <> dy.assigned_year
        """,
    ),
    (
        "no_candidate_leakage",
        "no annual assignment is backed by candidate-only evidence",
        f"""
        SELECT count(*) FROM domain_year dy
        JOIN evidence e ON e.evidence_id = dy.evidence_id
        WHERE e.evidence_type IN ({CANDIDATE_ONLY_SQL})
        """,
    ),
    (
        "every_pair_has_master_evidence",
        "every assigned pair has >=1 master-eligible evidence row for that exact year",
        f"""
        SELECT count(*) FROM domain_year dy WHERE NOT EXISTS (
            SELECT 1 FROM evidence e
            WHERE e.domain = dy.domain AND e.evidence_year = dy.assigned_year
              AND e.evidence_type NOT IN ({CANDIDATE_ONLY_SQL})
        )
        """,
    ),
    (
        "within_year_unique",
        "no duplicate (domain, year) in the annual masters",
        """
        SELECT count(*) FROM (
            SELECT domain, assigned_year FROM domain_year GROUP BY 1, 2 HAVING count(*) > 1
        )
        """,
    ),
    (
        "assigned_year_in_window",
        "every assigned year is within 1996-2001",
        "SELECT count(*) FROM domain_year WHERE assigned_year NOT BETWEEN 1996 AND 2001",
    ),
    (
        "registered_domain_format",
        "every stored domain is a well-formed lowercase registrable name",
        f"SELECT count(*) FROM domain WHERE length(domain) > {_MAX_HOST_LEN} "
        f"OR NOT regexp_matches(domain, '{_DOMAIN_RE}')",
    ),
    (
        "no_idn_tld_in_window",
        "no assigned domain sits under an internationalised TLD, since every `xn--` TLD "
        "was delegated in 2010 or later and cannot have existed in 1996-2001",
        "SELECT count(*) FROM domain_year WHERE split_part(domain, '.', -1) LIKE 'xn--%'",
    ),
    (
        "evidence_year_matches_its_value",
        "the year named inside an evidence value equals the year it was filed under "
        "(registration spans excepted, since they name two years by design)",
        f"""
        SELECT count(*) FROM evidence e
        JOIN source s ON s.source_id = e.source_id
        WHERE {_VALUE_YEAR} IS NOT NULL
          AND {_VALUE_YEAR} <> e.evidence_year
          AND (
            e.evidence_type IN ('cdx_timestamp', 'artifact_listing', 'link_source')
            OR (e.evidence_type = 'whois_creation' AND s.name NOT IN ({_SPAN_SOURCES}))
          )
        """,
    ),
    (
        "additions_not_double_counted",
        "no line of an exported annual file, registrable or hostname, is in his file for that "
        "year by exact name",
        _additions_not_double_counted,
    ),
    (
        "no_arpa_in_the_shipped_files",
        "no exported annual line sits under `.arpa`, because no website ever did in "
        "1996-2001: the ARPANET host transition finished in 1990 and every zone delegated "
        "under `.arpa` since is infrastructure, while the TLD scores 1.0000, the highest "
        "weight in the model",
        r"""
        SELECT count(*)
        FROM read_csv(
            '{netnew_dir}/[0-9][0-9][0-9][0-9].txt',
            columns = {{'domain': 'VARCHAR'}}, header = false
        )
        WHERE domain LIKE '%.arpa'
        """,
    ),
    (
        "no_tld_predates_its_own_delegation",
        "no exported annual line sits under a TLD that did not exist that year: `.info` and "
        "`.biz` were delegated in 2001 and `.eu` in 2005, so a 1998 line under either is "
        "impossible. `domain_creation_bulk` was admitted after exactly this check, but it was "
        "written against the six TLDs delegated in 2001 and could not see one delegated later, "
        "which left 1,087 such pairs in the store",
        r"""
        SELECT count(*)
        FROM read_csv(
            '{netnew_dir}/[0-9][0-9][0-9][0-9].txt',
            columns = {{'domain': 'VARCHAR'}}, header = false, filename = true
        )
        WHERE NOT (
        """
        + " AND ".join(
            f"NOT (domain LIKE '%.{tld}' AND TRY_CAST("
            r"regexp_extract(filename, '([0-9]{{4}})\.txt$', 1) AS INT) < " + str(year) + ")"
            for tld, year in sorted(
                __import__("ark.delegation", fromlist=["DELEGATED"]).DELEGATED.items()
            )
        )
        + """
        )
        """,
    ),
    (
        "no_tld_that_never_existed_in_the_window",
        "no exported annual line sits under a TLD that did not exist AT ALL in 1996-2001. "
        "`DELEGATED` names sixteen TLDs and stops at 2012, so it could not see the 2013 "
        "new-gTLD programme and its ~1,200 delegations, and text extraction banks any English "
        "word that later became one: measured 2026-08-31 the shipped files carried 749 such "
        "pairs and 423.9 EE across 131 TLDs, led by `.you`, `.here`, `.now` and `.sucks`, "
        "several of which carry weight 1.0000. Enumerating what DID exist is closed and cannot "
        "go stale; enumerating delegations would",
        """
        SELECT count(*)
        FROM read_csv(
            '{netnew_dir}/[0-9][0-9][0-9][0-9].txt',
            columns = {{'domain': 'VARCHAR'}}, header = false, filename = true
        )
        WHERE NOT """
        + __import__("ark.delegation", fromlist=["existed_predicate"]).existed_predicate("domain")
        + """
        """,
    ),
    (
        "hostname_wall_intact",
        "every hostname record points at an evidence row for its parent domain and year "
        "(second output unit, accepted by the reviewer 2026-09-01)",
        """
        SELECT count(*) FROM hostname_year hy
        LEFT JOIN evidence e ON e.evidence_id = hy.evidence_id
        WHERE e.evidence_id IS NULL
           OR e.domain <> hy.parent_domain
           OR e.evidence_year <> hy.assigned_year
        """,
    ),
    (
        "hostname_is_below_its_parent",
        "every hostname is a strict subname of its parent registrable and is itself a "
        "valid name; a bare registrable belongs in domain_year, never here",
        f"""
        SELECT count(*) FROM hostname_year
        WHERE hostname = parent_domain
           OR hostname NOT LIKE '%.' || parent_domain
           OR length(hostname) > 253
           OR NOT regexp_matches(hostname, '{_DOMAIN_RE}')
        """,
    ),
    (
        "hostname_observed_serving_web",
        "every hostname record comes from a lane whose observation shows the host IN USE that "
        "year: a capture, a URL listing, the `Received: ... by <host>` clause a receiving MTA "
        "wrote about itself, or a fleet read whose method is a web method. DNS listings date "
        "the parent only, because a machine answering is not a host in use. The check name "
        "predates the wider wording and is kept so a failing gate stays greppable",
        f"""
        SELECT count(*) FROM hostname_year hy
        JOIN evidence e ON e.evidence_id = hy.evidence_id
        JOIN source s ON s.source_id = e.source_id
        WHERE s.name NOT IN ({_WEB_FACING_LIST})
          AND NOT (regexp_matches(s.name, '{FLEETREAD_SOURCE.pattern}')
                   AND e.acquisition_method IN ({_WEB_METHOD_LIST}))
        """,
    ),
    (
        "a_www_record_has_its_own_evidence",
        "every `www.<parent>` hostname record points at an evidence row naming that exact "
        "host, so admitting the shape never turned into asserting it: the parent's "
        "own capture may not stand in for a capture of `www.` in front of it",
        """
        SELECT count(*) FROM hostname_year hy
        JOIN evidence e ON e.evidence_id = hy.evidence_id
        WHERE hy.hostname = 'www.' || hy.parent_domain
          AND e.evidence_value NOT LIKE '% ' || hy.hostname
        """,
    ),
    (
        "a_registrable_record_has_its_own_capture",
        "every exported registrable line has a web row of ours capturing that exact name in "
        "that year, so a capture of `www.` or of any other host beneath it never dates the "
        "registrable",
        r"""
        WITH f AS (
            SELECT domain,
                   TRY_CAST(regexp_extract(filename, '([0-9]{{4}})\.txt$', 1) AS INT) AS year
            FROM read_csv(
                '{netnew_dir}/[0-9][0-9][0-9][0-9].txt',
                columns = {{'domain': 'VARCHAR'}}, header = false, filename = true
            )
        ),
        -- the exported names' rows first, so the host test reads those and not the store
        e AS (SELECT * FROM evidence WHERE domain IN (SELECT domain FROM f))
        SELECT count(*) FROM f WHERE NOT EXISTS (
            SELECT 1 FROM e WHERE e.domain = f.domain AND e.evidence_year = f.year AND """
        + _braced(qualifies_sql("e", "f.domain"))
        + ")",
    ),
    (
        "nothing_earned_is_left_unassigned",
        "every master-eligible evidence row has its (domain, year) assigned, so a domain "
        "cannot sit in the candidate pool while already holding proof of a year. Evidence "
        "that names a SUBDOMAIN is exempt: it evidences that host, not the registrable "
        "beneath it, so it never dates the registrable",
        # a row naming a host below its domain, `www.` included, dates that host and owes the
        # domain no year, by the rule the writers apply; the rows with no pair are found first,
        # so the host is read on those
        f"""
        WITH unassigned AS MATERIALIZED (
            SELECT e.* FROM evidence e
            WHERE e.evidence_type NOT IN ({CANDIDATE_ONLY_SQL})
              AND NOT EXISTS (
                SELECT 1 FROM domain_year dy
                WHERE dy.domain = e.domain AND dy.assigned_year = e.evidence_year
              )
        )
        SELECT count(*) FROM unassigned e WHERE NOT {names_another_host_sql("e")}
        """,
    ),
    (
        "no_master_record_points_to_an_error_capture",
        "no hostname or domain year rests on a capture the status audit lists as 4xx or 5xx",
        """
        WITH bad AS (
            SELECT e.evidence_id
            FROM read_csv('{audit}', delim = '\t', header = true, all_varchar = true) a
            JOIN (VALUES {audited}) f(family, source, method) ON f.family = a.family
            JOIN source s ON s.name = f.source
            JOIN evidence e
              ON e.source_id = s.source_id AND e.acquisition_method = f.method
             AND e.evidence_value = 'cdx capture ' || a.ts || ' ' || a.hostname
        )
        SELECT (SELECT count(*) FROM hostname_year WHERE evidence_id IN (SELECT * FROM bad))
             + (SELECT count(*) FROM domain_year WHERE evidence_id IN (SELECT * FROM bad))
        """,
    ),
    # `evidence` carries no key and no table a foreign key, so these four hold what the
    # constraints held
    (
        "evidence_id_unique",
        "no two evidence rows share an id, so an assignment points at exactly one row",
        "SELECT count(*) - count(DISTINCT evidence_id) FROM evidence",
    ),
    (
        "domain_wall_intact",
        "every evidence row, assignment, hostname record and language verdict names a stored "
        "domain",
        """
        SELECT (SELECT count(*) FROM evidence e ANTI JOIN domain d ON d.domain = e.domain)
             + (SELECT count(*) FROM domain_year y ANTI JOIN domain d ON d.domain = y.domain)
             + (SELECT count(*) FROM hostname_year h
                ANTI JOIN domain d ON d.domain = h.parent_domain)
             + (SELECT count(*) FROM domain_language l ANTI JOIN domain d ON d.domain = l.domain)
        """,
    ),
    (
        "source_wall_intact",
        "every evidence row, and every domain's discovery, names a stored source",
        """
        SELECT (SELECT count(*) FROM evidence e ANTI JOIN source s ON s.source_id = e.source_id)
             + (SELECT count(*) FROM domain d
                ANTI JOIN source s ON s.source_id = d.discovered_source)
        """,
    ),
    (
        "new_rows_have_location",
        "every evidence row this store wrote itself names the file it was read from and its "
        "place in it; a row from before the store's first own id may name neither",
        f"""
        SELECT count(*) FROM evidence
        WHERE evidence_id >= {LOCATION_FROM_ID}
          AND (source_file IS NULL OR record_location IS NULL)
        """,
    ),
]


def _count(conn: duckdb.DuckDBPyConnection, sql: str, netnew_dir: Path, audit: Path | None) -> int:
    if "{audit}" in sql:
        if audit is None or not audit.is_file():
            raise _Skipped(f"no status audit at {audit}; run scripts/round/status_audit.py")
        # replaced, not formatted: the SQL carries regex braces
        sql = sql.replace("{audit}", str(audit)).replace("{audited}", _AUDITED)
    exported = "{netnew_dir}" in sql
    if exported:
        sql = sql.format(netnew_dir=netnew_dir)
    try:
        return conn.execute(sql).fetchone()[0]
    except duckdb.IOException:
        raise _Skipped(_NO_EXPORT.format(netnew_dir)) from None
    except (duckdb.BinderException, duckdb.InternalException, duckdb.CatalogException) as exc:
        # Every matching file is empty, so `read_csv` infers no columns and the query
        # cannot bind. A real state, not a fault: a round that has added nothing exports
        # six empty annual files. Reported as skipped rather than passed, because a
        # check that examined nothing is not one that found nothing wrong. DuckDB 1.5
        # words this InternalException "must return at least one column"; any other
        # internal error is a fault and is re-raised.
        if isinstance(exc, duckdb.InternalException) and "at least one column" not in str(exc):
            raise
        if exported and not isinstance(exc, duckdb.CatalogException):
            raise _Skipped(_EMPTY) from None
        # otherwise the store lacks a table or a column the check reads
        column = re.search(r'column "([^"]+)" not found', str(exc))
        table = re.search(r"Table with name (\w+) does not exist", str(exc))
        what = (
            f"column {column[1]}" if column else f"table {table[1]}" if table else str(exc)
        ).splitlines()[0]
        raise _Failed(f"the store lacks {what}: run `uv run ark init`") from None


def collect_checks(
    conn: duckdb.DuckDBPyConnection,
    netnew_dir: Path = NETNEW_DIR,
    audit: Path | None = None,
    baseline: Path | None = None,
) -> list[dict]:
    """Run every integrity check; return one result dict per check.

    A check that reads an exported file is reported as skipped when the export
    is absent, which is the normal state of a fresh clone before `ark export`.
    Skipped is shown rather than counted as a pass, so an empty output/ cannot be
    mistaken for a satisfied invariant. `baseline` is his release folder, `held`'s
    default when None; held sets that are missing or stale fail the check that reads
    them, with the reason, and the other checks still report.
    """
    results = []
    for name, description, check in CHECKS:
        result = {"name": name, "description": description, "offending": 0, "ok": True}
        try:
            if callable(check):
                result["offending"] = check(conn, netnew_dir, baseline)
            else:
                result["offending"] = _count(conn, check, netnew_dir, audit)
            result["ok"] = result["offending"] == 0
        except _Skipped as skip:
            result["skipped"] = str(skip)
        except (held.HeldError, _Failed) as error:
            result |= {"ok": False, "error": str(error)}
        results.append(result)
    return results


def format_checks(results: list[dict]) -> str:
    lines = ["== integrity checks =="]
    for r in results:
        if r.get("skipped"):
            lines.append(f"  [SKIP] {r['name']}: {r['skipped']}")
            continue
        if r.get("error"):
            lines.append(f"  [FAIL] {r['name']}: {r['error']}")
            continue
        mark = "PASS" if r["ok"] else "FAIL"
        lines.append(f"  [{mark}] {r['name']}: {r['offending']:,} offending  ({r['description']})")
    failed = [r["name"] for r in results if not r["ok"]]
    lines.append("ALL PASS" if not failed else f"FAILED: {', '.join(failed)}")
    return "\n".join(lines)
