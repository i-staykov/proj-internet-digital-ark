"""Write the human-facing result files out of the provenance store.

Three targets: net-new year files and their evidence manifest (small, the
committed work product), the candidate list, and the merged master lists
(baseline + additions, large, delivery-archive material).
"""

import json
from decimal import Decimal
from pathlib import Path

import duckdb
from loguru import logger

from ark.baseline import CURRENT_BASELINE_MARKER, baseline_dir
from ark.contribution import DEFAULT_REPORT_DIR, write_contribution_tables
from ark.delegation import shipping_filter as _shipping_filter
from ark.delegation import shipping_filter_for as _shipping_filter_for
from ark.english_share import english_weights
from ark.evidence_types import web_evidence_exists, web_evidence_sql
from ark.ingest import YEARS
from ark.provenance import PROVENANCE_DIR, write_provenance
from ark.stats import BASELINE_TYPE

NETNEW_DIR = Path("output/netnew")
CANDIDATES_PATH = Path("output/candidate_unverified.txt")
MASTERS_DIR = Path("data/exports")


# A pair is an addition when the baseline holds NO evidence for that (domain, year), the
# test `stats.py` and `contribution.py` apply. Deliberately not "the row this assignment
# points at is not baseline": the baseline rolls forward, so an absorbed addition still
# points at its original CDX row while now also carrying baseline evidence, and the weaker
# test re-exports every past addition as new.
# **Spec XIII: the annual CLAIM is website evidence only** (C-90). The store keeps every
# row, because a row that cannot date a year is still evidence and still a candidate; what
# this filters is what we ASSERT. `evidence_types.WEB_METHODS` is the allowlist and an
# unknown method fails closed.


_NOT_IN_BASELINE = f"""
    NOT EXISTS (
        SELECT 1 FROM evidence p
        WHERE p.domain = dy.domain AND p.evidence_year = dy.assigned_year
          AND p.evidence_type = '{BASELINE_TYPE}'
    )
"""


# **The shipping filter: no `.arpa`, and no pair whose TLD did not yet exist.**
# The rule is the whole TLD, not the reverse-DNS pattern: narrowing to `in-addr`/`ip6` left
# `ignore.arpa` shipping at weight 1.0000, the model's maximum. Filtered here rather than
# deleted from the store, which would be a destructive migration; `dropped_domains.txt`
# ships the excluded baseline lines. `ark.delegation` owns the years, so the rule is in one
# place for all four destinations it reaches.
_NOT_REVERSE_DNS = _shipping_filter()


# `www.<a name already held that year>` SHIPS. Measured on him: his merges hold all
# 1,313,547 `www.` hostnames of the 2026-09-02 submission and he credited the round, so
# withholding them cost 233,999.15 EE and bought nothing.
#
# Not applied to the export. Kept because `scripts/round/round_figures.py` imports it to
# report the alias share, which tells us which corpus to read next: a bulk CDX index
# re-read at hostname grain is 99.5% to 100.0% alias, a typed-URL corpus 22.2%.
NOT_WWW_ALIAS = """
    (hy.hostname NOT LIKE 'www.%' OR (
        NOT EXISTS (SELECT 1 FROM baseline_hostname b
                    WHERE b.hostname = substr(hy.hostname, 5) AND b.year = hy.assigned_year)
        AND NOT EXISTS (SELECT 1 FROM hostname_year h2
                        WHERE h2.hostname = substr(hy.hostname, 5)
                          AND h2.assigned_year = hy.assigned_year)
        AND NOT EXISTS (SELECT 1 FROM domain_year dy
                        WHERE dy.domain = substr(hy.hostname, 5)
                          AND dy.assigned_year = hy.assigned_year)
    ))
"""

# A hostname is net-new against the baseline FILES, not against store membership, because the
# store collapsed the baseline to registrables at ingest and so cannot answer "is
# alice.cjb.net itself already a benchmark record".
NOT_IN_BASELINE_HOSTNAME = """
    NOT EXISTS (SELECT 1 FROM baseline_hostname b
                WHERE b.hostname = hy.hostname AND b.year = hy.assigned_year)
"""

# The registrable half has refused `.arpa` and a pair predating its own TLD since 2026-08-18,
# and the hostname half refused neither until 2026-09-03: `bust.web.site` at 1996 and
# `comp.domaine.name` at 2000 were shipping. Same rule, same module, different column name.
HOSTNAME_SHIPPING_FILTER = _shipping_filter_for("hy.hostname", "hy.assigned_year")


def load_baseline_hostnames(conn: duckdb.DuckDBPyConnection) -> None:
    """The reviewer's own annual files as a temp table, which both rules above read.

    The directory is resolved, not hardcoded: inside a delivery the files sit at
    `../baseline/<marker>/`, and the repository path alone silently exported every hostname
    as net-new in the tier-2 rehearsal.
    """
    baseline_files = baseline_dir()
    conn.execute("CREATE OR REPLACE TEMP TABLE baseline_hostname (hostname VARCHAR, year INTEGER)")
    for year in YEARS:
        baseline_file = baseline_files / f"{year}.txt"
        if baseline_file.exists():
            conn.execute(f"""
                INSERT INTO baseline_hostname
                SELECT lower(trim(column0)), {year}
                FROM read_csv('{baseline_file}', header=false, delim='\\x01',
                              columns={{'column0': 'VARCHAR'}})
            """)
        else:
            logger.warning(f"no baseline file for {year}: every hostname exports as net-new")


# DNS observations are candidates only. Annual promotion requires exact-host web evidence
# for the target year. Candidate counts deduplicate names across survey years.
ISC_SOURCE = "isc_survey_hostnames"
# His structural rule as SQL: dot-separated labels, letters, digits and interior hyphens only,
# ending in an alphabetic TLD label. The same pattern as `hostnames._VALID_HOST`, spelled here
# because these rows never pass through that funnel: they are read straight out of evidence.
# No lookahead here either, for the same RE2 reason; the query pairs it with a `length()` test.
_HOSTNAME_RE = (
    r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*\.[a-z]{2,63}$"
)


def export_isc_provenance(
    conn: duckdb.DuckDBPyConnection, netnew_dir: Path, stats: dict[str, int]
) -> None:
    """Write provenance for exactly the reconciled hostname-years, then measure the files."""
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE isc_provenance AS
        SELECT DISTINCT
               i.hostname,
               i.assigned_year AS target_year,
               regexp_extract(e.evidence_value, 'isc survey ([0-9]{{4}}-[0-9]{{2}}) host ', 1)
                   AS survey_edition,
               regexp_extract(e.evidence_url, '([^/]+)$', 1) AS source_file,
               e.evidence_url AS source_url,
               e.evidence_value AS record_location,
               e.acquisition_method AS extraction_method
        FROM evidence e JOIN source s ON s.source_id = e.source_id
        JOIN isc_export i
          ON i.hostname = lower(regexp_extract(e.evidence_value, '([^ ]+)$', 1))
         AND i.assigned_year = e.evidence_year
        WHERE s.name = '{ISC_SOURCE}'
    """)
    missing = conn.execute("""
        SELECT count(*) FROM isc_provenance
        WHERE coalesce(trim(survey_edition), '') = ''
           OR coalesce(trim(source_file), '') = ''
           OR coalesce(trim(source_url), '') = ''
           OR coalesce(trim(record_location), '') = ''
           OR coalesce(trim(extraction_method), '') = ''
           OR try_cast(substr(survey_edition, 1, 4) AS INTEGER) <> target_year
    """).fetchone()[0]
    if missing:
        raise ValueError(f"ISC candidates have {missing} incomplete provenance rows")
    uncovered = conn.execute("""
        SELECT count(*) FROM isc_export i
        WHERE NOT EXISTS (SELECT 1 FROM isc_provenance p
                          WHERE p.hostname = i.hostname AND p.target_year = i.assigned_year)
    """).fetchone()[0]
    if uncovered:
        raise ValueError(f"ISC candidates have {uncovered} hostname-years without provenance")
    path = netnew_dir / "isc_survey_provenance.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(f"""
        COPY (SELECT * FROM isc_provenance
              ORDER BY hostname, target_year, survey_edition, source_url,
                       record_location, extraction_method)
        TO '{path}' (HEADER true)
    """)
    stats["isc_provenance_rows"] = conn.execute(
        "SELECT count(*) FROM read_csv(?, header=true, all_varchar=true)", [str(path)]
    ).fetchone()[0]
    tlds = conn.execute(
        """
        SELECT regexp_extract(hostname, '[^.]+$') AS tld, count(*) AS hosts
        FROM read_csv(?, header=false, columns={'hostname': 'VARCHAR'})
        GROUP BY tld ORDER BY tld
    """,
        [str(netnew_dir / "isc_candidates.txt")],
    ).fetchall()
    weights = english_weights()
    ee = sum((weights.get(tld, Decimal(0)) * n for tld, n in tlds), Decimal(0))
    summary = {
        "baseline": CURRENT_BASELINE_MARKER,
        "track": "candidate",
        "counting_unit": "distinct exact hostname across all survey years",
        "candidates": sum(n for _, n in tlds),
        "equivalent_english": str(ee.quantize(Decimal("0.0001"))),
        "hostname_years": sum(stats[f"isc_{year}"] for year in YEARS),
        "by_year": {str(year): stats[f"isc_{year}"] for year in YEARS},
        "provenance_rows": stats["isc_provenance_rows"],
        "tld_counts": dict(tlds),
    }
    (netnew_dir / "isc_candidates_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    logger.info(f"ISC candidates: {summary['candidates']:,}, {ee} equivalent-English")
    conn.execute("DROP TABLE isc_provenance")


def export_isc_hostnames(
    conn: duckdb.DuckDBPyConnection,
    netnew_dir: Path,
    stats: dict[str, int],
    baseline: Path | None = None,
) -> None:
    """Write candidates absent by exact name from reviewer candidates and all annual years.

    `baseline_hostname` must contain the current six annual files. A held parent or a
    different `www.` form does not exclude a hostname. No annual table is modified.
    """
    conn.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE isc_export AS
        SELECT DISTINCT hy.hostname, hy.assigned_year FROM (
            SELECT lower(regexp_extract(e.evidence_value, '([^ ]+)$', 1)) AS hostname,
                   e.domain AS parent, e.evidence_year AS assigned_year
            FROM evidence e JOIN source s ON s.source_id = e.source_id
            WHERE s.name = '{ISC_SOURCE}'
        ) hy
        WHERE hy.hostname <> hy.parent AND hy.hostname LIKE '%.' || hy.parent
          AND length(hy.hostname) <= 253
          AND regexp_matches(hy.hostname, '{_HOSTNAME_RE}')
          AND {_shipping_filter_for("hy.hostname", "hy.assigned_year")}
        """
    )
    if conn.execute("SELECT count(*) FROM isc_export").fetchone()[0]:
        baseline = baseline or baseline_dir()
        required = [baseline / f"{year}.txt" for year in YEARS] + [baseline / "candidate_pool.txt"]
        absent = [str(path) for path in required if not path.is_file()]
        if absent:
            raise FileNotFoundError(f"ISC reconciliation requires current baseline files: {absent}")
        conn.execute(
            """
            DELETE FROM isc_export WHERE hostname IN (
                SELECT lower(trim(column0)) FROM read_csv(
                    ?, header=false, delim='\x01', quote='',
                    columns={'column0': 'VARCHAR'})
            )
        """,
            [str(baseline / "candidate_pool.txt")],
        )
        for table, column in (
            ("baseline_hostname", "hostname"),
            ("hostname_year", "hostname"),
            ("domain_year", "domain"),
        ):
            conn.execute(f"""
                DELETE FROM isc_export
                WHERE hostname IN (SELECT lower(trim({column})) FROM {table})
            """)
    for year in YEARS:
        query = f"""
            SELECT hostname FROM isc_export WHERE assigned_year = {year} ORDER BY hostname
        """
        stats[f"isc_{year}"] = _copy_query(conn, query, netnew_dir / f"{year}-ISC.txt")
    stats["isc_candidates"] = _copy_query(
        conn,
        "SELECT DISTINCT hostname FROM isc_export ORDER BY hostname",
        netnew_dir / "isc_candidates.txt",
    )


def _copy_query(conn: duckdb.DuckDBPyConnection, query: str, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(f"COPY ({query}) TO '{path}' (HEADER false)")
    return conn.execute(f"SELECT count(*) FROM ({query})").fetchone()[0]


def netnew_shipped_pairs(conn: duckdb.DuckDBPyConnection, baseline: Path | None = None) -> int:
    """Net-new pairs that will actually reach the annual files.

    **Not the store's raw net-new total, and the difference is the point.**
    `_shipping_filter` drops a pair whose TLD did not exist in its year, so the store holds
    more net-new pairs than any export writes. Packaging compares its exported line count
    against this: against the raw total a current export looks permanently stale, 726,344
    against 726,336.

    The diff against his own annual files is part of the same argument: it drops 304 pairs
    our ingested baseline evidence does not know he holds.
    """
    load_his_annual_files(conn, baseline)
    total = 0
    for year in YEARS:
        total += conn.execute(
            f"""
            SELECT COUNT(DISTINCT dy.domain) FROM domain_year dy
            WHERE dy.assigned_year = {year} AND {_NOT_IN_BASELINE}
              AND {_shipping_filter("dy.")}
              AND {_not_in_his_annual("dy.domain", "dy.assigned_year")}
            """
        ).fetchone()[0]
    return total


def load_his_annual_files(conn: duckdb.DuckDBPyConnection, baseline: Path | None = None) -> None:
    """Load the reviewer's six annual files into `his_annual(name, year)`.

    **The store's own baseline evidence is not a substitute.** That evidence is whatever
    release was ingested, and his current release can add names after it: one such gap put
    303 names into the 2001 additions that his `merged260908` already held. Diffing against
    his files at export time makes the overlap zero by construction.
    """
    baseline = baseline or baseline_dir()
    conn.execute("CREATE OR REPLACE TEMP TABLE his_annual(name VARCHAR, year INTEGER)")
    if not baseline.is_dir():
        # A store with no baseline beside it is a fresh init or a test, and there is
        # nothing to diff against. A baseline that exists but is INCOMPLETE is the
        # dangerous case and still raises below, because a half-loaded diff silently
        # ships the half it could not read.
        logger.warning(f"no baseline at {baseline}: shipped lists are not diffed against his")
        return
    for year in YEARS:
        path = baseline / f"{year}.txt"
        if not path.is_file():
            raise FileNotFoundError(f"the export needs the reviewer's {year}.txt to diff against")
        conn.execute(
            f"""
            INSERT INTO his_annual
            SELECT lower(trim(column0)), {year} FROM read_csv(
                ?, header=false, delim='\x01', quote='',
                columns={{'column0': 'VARCHAR'}})
            """,
            [str(path)],
        )


def _not_in_his_annual(column: str, year_expr: str) -> str:
    """SQL excluding a name the reviewer already lists for that year. Needs `his_annual`."""
    return f"""
        NOT EXISTS (
            SELECT 1 FROM his_annual h
            WHERE h.name = lower(trim({column})) AND h.year = {year_expr}
        )
    """


def export_header_candidates(
    conn: duckdb.DuckDBPyConnection, netnew_dir: Path, stats: dict[str, int]
) -> None:
    """XIII's source-specific candidate asset: every hostname in the claim whose only dated
    evidence is a non-web class (a server-written mail or Usenet header, a DNS listing), with
    per-host provenance, a summary and the exclusion ledger of the same validation run. Runs
    after the pool is reconciled, so every name here is in `candidate_additions.txt`."""
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE header_provenance AS
        SELECT DISTINCT hy.hostname, hy.assigned_year AS target_year, s.name AS source,
               e.acquisition_method, e.evidence_type, e.evidence_value AS record_location,
               e.evidence_url AS source_url
        FROM candidate_pool c
        JOIN hostname_year hy ON hy.hostname = c.name
        JOIN evidence e ON e.evidence_id = hy.evidence_id
        JOIN source s ON s.source_id = e.source_id
        WHERE c.unit = 'hostname' AND NOT ({web_evidence_sql("e")})
    """)
    stats["header_candidates"] = _copy_query(
        conn,
        "SELECT DISTINCT hostname FROM header_provenance ORDER BY hostname",
        netnew_dir / "header_candidates.txt",
    )
    provenance_path = netnew_dir / "header_candidates_provenance.csv"
    conn.execute(f"""
        COPY (SELECT * FROM header_provenance
              ORDER BY hostname, target_year, source, record_location)
        TO '{provenance_path}' (HEADER true)
    """)
    # The exclusion ledger XIII asks of every validation run, for this collection: the rows
    # the hostname gate quarantined, one per record, with the reason and the decision.
    ledger_path = netnew_dir / "header_candidates_exclusions.csv"
    conn.execute(f"""
        COPY (
            SELECT DISTINCT hy.hostname,
                   'candidate' AS scope,
                   e.evidence_url AS source_file,
                   e.evidence_value AS record_location,
                   'fails the hostname syntax or suffix rule (XIII gate)' AS exclusion_reason,
                   'lowercased at ingest; quarantined, not exported' AS normalization_decision,
                   e.evidence_url AS evidence_reference
            FROM hostname_year hy
            JOIN evidence e ON e.evidence_id = hy.evidence_id
            WHERE NOT ({web_evidence_sql("e")}) AND NOT ({HOSTNAME_SHIPPING_FILTER})
            ORDER BY hy.hostname
        ) TO '{ledger_path}' (HEADER true)
    """)
    tlds = conn.execute("""
        SELECT regexp_extract(hostname, '[^.]+$') AS tld, count(*) AS hosts
        FROM (SELECT DISTINCT hostname FROM header_provenance) GROUP BY tld ORDER BY tld
    """).fetchall()
    weights = english_weights()
    ee = sum((weights.get(tld, Decimal(0)) * n for tld, n in tlds), Decimal(0))
    by_source = dict(
        conn.execute(
            "SELECT source, count(DISTINCT hostname) FROM header_provenance GROUP BY 1 ORDER BY 1"
        ).fetchall()
    )
    by_year = {
        str(year): n
        for year, n in conn.execute(
            "SELECT target_year, count(*) FROM header_provenance GROUP BY 1 ORDER BY 1"
        ).fetchall()
    }
    count_csv = "SELECT count(*) FROM read_csv(?, header=true, all_varchar=true)"
    summary = {
        "baseline": CURRENT_BASELINE_MARKER,
        "track": "candidate",
        "collection": "hostnames whose only dated evidence is a non-web class (Section XIII)",
        "counting_unit": "distinct exact hostname across years",
        "candidates": stats["header_candidates"],
        "equivalent_english": str(ee.quantize(Decimal("0.0001"))),
        "hostname_years": sum(by_year.values()),
        "by_year": by_year,
        "by_source": by_source,
        "provenance_rows": conn.execute(count_csv, [str(provenance_path)]).fetchone()[0],
        "excluded_by_integrity_gate": conn.execute(count_csv, [str(ledger_path)]).fetchone()[0],
        "promotion": "an exact-host, target-year web capture retained beside the record",
    }
    (netnew_dir / "header_candidates_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    logger.info(f"header candidates: {summary['candidates']:,}, {ee} equivalent-English")
    conn.execute("DROP TABLE header_provenance")


def export_all(
    conn: duckdb.DuckDBPyConnection,
    netnew_dir: Path = NETNEW_DIR,
    candidates_path: Path = CANDIDATES_PATH,
    masters_dir: Path = MASTERS_DIR,
    report_dir: Path = DEFAULT_REPORT_DIR,
    provenance_dir: Path = PROVENANCE_DIR,
    baseline: Path | None = None,
    with_provenance: bool = False,
) -> dict[str, int]:
    """Write every result file. Every destination is a parameter, so a caller
    that redirects the outputs redirects all of them; leaving one hardcoded let
    the test suite overwrite the real contribution tables with a test store."""
    stats: dict[str, int] = {}
    baseline = baseline or baseline_dir()
    load_his_annual_files(conn, baseline)

    for year in YEARS:
        netnew_query = f"""
            SELECT DISTINCT dy.domain FROM domain_year dy
            WHERE dy.assigned_year = {year} AND {_NOT_IN_BASELINE}
              AND {_shipping_filter("dy.")}
              AND {_not_in_his_annual("dy.domain", str(year))}
              AND {web_evidence_exists("dy.evidence_id")}
            ORDER BY dy.domain
        """
        count = _copy_query(conn, netnew_query, netnew_dir / f"{year}.txt")
        stats[f"netnew_{year}"] = count
        # His rows plus ours, under the same XIII screen the additions pass: the merged
        # annual file is a website-evidence product too, and until 2026-09-22 it carried
        # the registrable rows the screen refused (251,178 of them in 2001).
        masters_query = f"""
            SELECT DISTINCT dy.domain FROM domain_year dy
            WHERE dy.assigned_year = {year} AND {_shipping_filter("dy.")}
              AND (NOT ({_NOT_IN_BASELINE}) OR {web_evidence_exists("dy.evidence_id")})
            ORDER BY dy.domain
        """
        stats[f"master_{year}"] = _copy_query(conn, masters_query, masters_dir / f"{year}.txt")

    # The hostname half of the annual contribution ships beside the registrable half.
    # Brief IV.8 requires exact qualifying hostnames, not a registrable-only roll-up;
    # these are annual records, not auxiliary seeds. Shipping predicates are shared
    # with `round_figures.py` so the reported and exported populations cannot drift.
    load_baseline_hostnames(conn)
    not_in_baseline = NOT_IN_BASELINE_HOSTNAME
    for year in YEARS:
        hostname_query = f"""
            SELECT DISTINCT hy.hostname FROM hostname_year hy
            WHERE hy.assigned_year = {year} AND {not_in_baseline}
              AND {HOSTNAME_SHIPPING_FILTER}
              AND {_not_in_his_annual("hy.hostname", str(year))}
              AND {web_evidence_exists("hy.evidence_id")}
            ORDER BY hy.hostname
        """
        count = _copy_query(conn, hostname_query, netnew_dir / f"{year}_hostnames.txt")
        stats[f"netnew_hostnames_{year}"] = count

    export_isc_hostnames(conn, netnew_dir, stats, baseline)
    export_isc_provenance(conn, netnew_dir, stats)

    # The manifest carries the same rows as the shipped files: a row for a hostname
    # the benchmark already lists would read as an addition it is not.
    hostname_manifest_query = f"""
        SELECT hy.hostname, hy.parent_domain, hy.assigned_year, e.evidence_type,
               e.evidence_value, s.name AS source, e.acquisition_method, e.evidence_url
        FROM hostname_year hy
        JOIN evidence e ON hy.evidence_id = e.evidence_id
        JOIN source s ON e.source_id = s.source_id
        WHERE {not_in_baseline} AND {HOSTNAME_SHIPPING_FILTER}
          AND {_not_in_his_annual("hy.hostname", "hy.assigned_year")}
          AND {web_evidence_sql("e")}
        ORDER BY hy.hostname, hy.assigned_year
    """
    hostname_manifest = netnew_dir / "hostnames_evidence_manifest.csv"
    hostname_manifest.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(f"COPY ({hostname_manifest_query}) TO '{hostname_manifest}' (HEADER true)")

    manifest_query = f"""
        SELECT dy.domain, dy.assigned_year, e.evidence_type, e.evidence_value,
               s.name AS source, e.acquisition_method, e.evidence_url
        FROM domain_year dy
        JOIN evidence e ON dy.evidence_id = e.evidence_id
        JOIN source s ON e.source_id = s.source_id
        WHERE e.evidence_type != '{BASELINE_TYPE}' AND {_NOT_IN_BASELINE}
          AND {_shipping_filter("dy.")}
          AND {_not_in_his_annual("dy.domain", "dy.assigned_year")}
          AND {web_evidence_sql("e")}
        ORDER BY dy.domain, dy.assigned_year
    """
    path = netnew_dir / "evidence_manifest.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(f"COPY ({manifest_query}) TO '{path}' (HEADER true)")

    candidates_query = (
        """
        SELECT d.domain FROM domain d
        WHERE NOT EXISTS (SELECT 1 FROM domain_year dy WHERE dy.domain = d.domain)
          AND """
        + _shipping_filter("d.", with_year=False)
        + """
        ORDER BY d.domain
    """
    )
    stats["candidates"] = _copy_query(conn, candidates_query, candidates_path)

    # THE CANDIDATE TRACK, as one pool. He scores candidates separately and at the same
    # rate as annual records, so this is held to the same net-new standard: every candidate
    # collection we hold, unioned, minus every name he already has in his candidate pool or
    # in any of his six annual files.
    #
    # One file, not one per collection: provenance belongs in `provenance/` and
    # `isc_survey_provenance.csv`, and splitting the pool by origin makes the reviewer
    # reconcile three files to count one track.
    #
    # The whole pool is NOT the claim: our registrable pool held 2,279,755 names and 29,327
    # of them were absent from his files, so shipping the pool as the contribution would
    # overstate the registrable half of this track by 78x.
    #
    # **A registrable name whose every year fails XIII is a candidate, not nothing** (C-90:
    # "failing rows re-track to candidates"). Until 2026-09-21 the pool took only names with
    # NO year at all, so a registry list ingested as `artifact_listing` earned a year the
    # annual screen then refused, and the name fell between the two tracks: the `.dk` zone
    # list's 251,114 rows shipped in neither file. His own baseline rows are excluded by
    # type rather than by method, because `prior_reused` is not a web method either and
    # every one of his 33.7M names would otherwise enter the pool only to be deleted below.
    conn.execute(f"""
        CREATE OR REPLACE TEMP TABLE candidate_pool AS
        SELECT DISTINCT d.domain AS name, 'registrable' AS unit FROM domain d
        WHERE NOT EXISTS (SELECT 1 FROM domain_year dy
                          WHERE dy.domain = d.domain AND {web_evidence_exists("dy.evidence_id")})
          AND NOT EXISTS (SELECT 1 FROM evidence p
                          WHERE p.domain = d.domain AND p.evidence_type = '{BASELINE_TYPE}')
          AND {_shipping_filter("d.", with_year=False)}
    """)
    # the ISC survey hostnames, already reduced by `export_isc_hostnames` against his
    # candidate pool and every annual file, and against everything we hold ourselves
    conn.execute("""
        INSERT INTO candidate_pool
        SELECT DISTINCT hostname, 'hostname' FROM isc_export
    """)
    # **A hostname whose every year fails XIII is a candidate too.** XIII names the classes
    # (mail and Usenet delivery headers, DNS listings, registry events, mentions) and says to
    # store them as source-specific candidate assets with provenance; the ISC arm above is that
    # shape for one source. Same rule as the registrable arm: no web-method year for the exact
    # host, the hostname gate, then the reconciliation below against his files.
    conn.execute(f"""
        INSERT INTO candidate_pool
        SELECT DISTINCT hy.hostname, 'hostname' FROM hostname_year hy
        WHERE NOT EXISTS (SELECT 1 FROM hostname_year hz
                          WHERE hz.hostname = hy.hostname
                            AND {web_evidence_exists("hz.evidence_id")})
          AND NOT EXISTS (SELECT 1 FROM candidate_pool c WHERE c.name = hy.hostname)
          AND {HOSTNAME_SHIPPING_FILTER}
    """)
    his_pool = baseline / "candidate_pool.txt"
    if his_pool.is_file():
        conn.execute(
            """
            DELETE FROM candidate_pool WHERE name IN (
                SELECT lower(trim(column0)) FROM read_csv(
                    ?, header=false, delim='\x01', quote='',
                    columns={'column0': 'VARCHAR'})
            )
        """,
            [str(his_pool)],
        )
    elif baseline.is_dir():
        raise FileNotFoundError(f"the candidate claim needs his pool to diff against: {his_pool}")
    conn.execute("""
        DELETE FROM candidate_pool WHERE name IN (SELECT name FROM his_annual)
    """)
    stats["candidate_additions"] = _copy_query(
        conn,
        "SELECT DISTINCT name FROM candidate_pool ORDER BY name",
        netnew_dir / "candidate_additions.txt",
    )
    export_header_candidates(conn, netnew_dir, stats)
    weights = english_weights()
    counts = conn.execute(
        """
        SELECT unit, regexp_extract(name, '([a-z0-9-]+)$', 1) AS tld, count(*)
        FROM candidate_pool GROUP BY 1, 2
        """
    ).fetchall()
    by_unit: dict[str, tuple[int, Decimal]] = {}
    for unit, tld, n in counts:
        held_n, held_ee = by_unit.get(unit, (0, Decimal(0)))
        by_unit[unit] = (held_n + n, held_ee + weights.get(tld, Decimal(0)) * n)
    summary = {
        "baseline": CURRENT_BASELINE_MARKER,
        "track": "candidate",
        "counting_unit": "distinct name, registrable domains and exact hostnames in one pool",
        "candidates": sum(n for n, _ in by_unit.values()),
        "equivalent_english": str(sum((ee for _, ee in by_unit.values()), Decimal(0))),
        "by_unit": {
            u: {"names": n, "equivalent_english": str(ee)} for u, (n, ee) in by_unit.items()
        },
    }
    (netnew_dir / "candidate_additions_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    # per-source and per-year contribution tables, which ship in the audit folder
    stats.update(write_contribution_tables(conn, report_dir))

    # The provenance graph itself, so a reader can ask "why is this domain in this year?"
    # without the source data or a copy of the database.
    #
    # **Off by default, because it is 52% of this command.** Measured 2026-09-18: 229 of
    # 444 seconds, writing 2,319 MB over 81.7M evidence and 28.0M hostname_year rows. It
    # is read in exactly two places, `just rebuild` and `package_delivery.sh`, and neither
    # runs hourly. The sync that fires every hour paid for it anyway.
    if with_provenance:
        provenance = write_provenance(conn, provenance_dir)
        stats["provenance_mb"] = provenance["megabytes"]

    logger.info(f"export: {stats}")
    return stats
