"""Write the human-facing result files out of the provenance store.

Two targets: the net-new year files, registrable and hostname, with their evidence manifests
(small, the committed work product), and the candidate lists. Held by him is the exact name in
his files, tested by `LC_ALL=C comm` through `held`. Packaging merges his year files with ours
into the masters, so the export writes none.
"""

import filecmp
import json
import os
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
from loguru import logger

from ark import held
from ark.baseline import CURRENT_BASELINE_MARKER
from ark.contribution import DEFAULT_REPORT_DIR, write_contribution_tables
from ark.delegation import shipping_filter as _shipping_filter
from ark.delegation import shipping_filter_for as _shipping_filter_for
from ark.english_share import english_weights
from ark.evidence_types import ERROR_STATUS, web_evidence_exists, web_evidence_sql
from ark.ingest import YEARS
from ark.provenance import PROVENANCE_DIR, write_provenance

NETNEW_DIR = Path("output/netnew")
CANDIDATES_PATH = Path("output/candidate_unverified.txt")
# `YYYY<TAB>registrable` for every pair of ours whose name his file for that year lacks
ATTESTED_NAME = "attested_registrables.txt"
# Written last and removed first, so a crashed export leaves none. Packaging reads it.
STAMP_NAME = "export_stamp.json"
# Where ship sets the bank's claim aside before the full export, so packaging can compare them
CLAIM_COPY_DIR = Path("data/exports/claim")


# **Spec XIII: the annual CLAIM is website evidence only**, from a row of ours capturing exactly
# the shipped name (`evidence_types.qualifies_sql`). The store keeps every row, because a row
# that cannot date a year is still evidence and still a candidate; what this filters is what
# we ASSERT. `evidence_types.WEB_METHODS` is the allowlist and an unknown method fails closed.


# **The shipping filter: no `.arpa`, and no pair whose TLD did not yet exist**, for the
# registrable and the hostname half alike. The rule is the whole TLD, not the reverse-DNS
# pattern: narrowing to `in-addr`/`ip6` left `ignore.arpa` shipping at weight 1.0000, the
# model's maximum. Filtered here rather than deleted from the store, which would be a
# destructive migration. `ark.delegation` owns the years, so the rule is in one place.
HOSTNAME_SHIPPING_FILTER = _shipping_filter_for("hy.hostname", "hy.assigned_year")


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
    conn: duckdb.DuckDBPyConnection, netnew_dir: Path, stats: dict[str, int]
) -> None:
    """Write `isc_export`, as `reduce_isc` left it, per survey year and as one list."""
    for year in YEARS:
        stats[f"isc_{year}"] = held.dump(
            conn,
            f"SELECT hostname FROM isc_export WHERE assigned_year = {year} ORDER BY hostname",
            netnew_dir / f"{year}-ISC.txt",
        )
    stats["isc_candidates"] = held.dump(
        conn,
        "SELECT DISTINCT hostname FROM isc_export ORDER BY hostname",
        netnew_dir / "isc_candidates.txt",
    )


def _minus_his(names: Path, his: held.Held, out: Path, taken: Path | None = None) -> int:
    """Write the lines of `names` that no candidate file and no year file of his holds, by
    exact name, and count them. `taken` gets those his candidate files hold, which the
    candidate summary counts."""
    if taken:
        held.intersect(names, his.candidates, taken)
    rest = names.with_name(f"{names.stem}_not_candidate.txt")
    held.minus(names, his.candidates, rest)
    return held.minus(rest, his.all, out)


def reduce_isc(conn: duckdb.DuckDBPyConnection, his: held.Held, work: Path) -> Path | None:
    """Build `isc_export`, the survey hostnames no file of his and no table of ours names, and
    return the file of those his candidate files hold, or None when the survey gave none.

    Exact names only: a held parent or a different `www.` form does not exclude a hostname.
    Needs `our_domain_year`. No annual table is modified.
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
    if not conn.execute("SELECT count(*) FROM isc_export").fetchone()[0]:
        return None
    names, taken = work / "isc.txt", work / "isc_held.txt"
    held.dump(conn, "SELECT DISTINCT hostname FROM isc_export ORDER BY 1", names)
    _minus_his(names, his, work / "isc_kept.txt", taken)
    held.read_names(conn, "isc_kept", work / "isc_kept.txt")
    conn.execute("""
        DELETE FROM isc_export
        WHERE hostname NOT IN (SELECT name FROM isc_kept)
           OR hostname IN (SELECT hostname FROM hostname_year)
           OR hostname IN (SELECT domain FROM our_domain_year)
    """)
    conn.execute("DROP TABLE isc_kept")
    return taken


@contextmanager
def _phase(name: str) -> Iterator[None]:
    """Log how long one step of the export took, so a slow bank names its slow step."""
    start = time.monotonic()
    yield
    logger.info(f"export: {name} {time.monotonic() - start:.1f}s")


def netnew_shipped_pairs(conn: duckdb.DuckDBPyConnection, baseline: Path | None = None) -> int:
    """Net-new pairs that will actually reach the annual files.

    **Not the store's raw net-new total, and the difference is the point.** Packaging compares
    its exported line count against this, so it is counted exactly as the export writes the
    registrable files: `held.netnew` into a scratch folder, which is our claim screened by the
    shipping filter and minus his year files by exact name. Each time the export learned a
    filter the guard did not, a current export read as stale for ever.
    """
    his = held.load(baseline)
    held.our_domain_year(conn)
    held.claim_pairs(conn)
    with tempfile.TemporaryDirectory(prefix="ark-shipped-") as tmp:
        return sum(held.netnew(conn, his, Path(tmp)).values())


def _write_attested(conn: duckdb.DuckDBPyConnection, his: held.Held, work: Path, out: Path) -> int:
    """Every year a pair of ours dates a registrable his file for that year lacks, by exact
    name and screened by nothing else: a pricer asks whether a name is dated at all, and his
    lines plus these are every dated name. The year is fixed width, so year then name is
    `LC_ALL=C` line order."""
    parts = {}
    for year in YEARS:
        dated = work / f"our_{year}.txt"
        held.dump(
            conn,
            f"SELECT domain FROM our_domain_year WHERE assigned_year = {year} ORDER BY 1",
            dated,
        )
        parts[year] = work / f"attested_{year}.txt"
        held.minus(dated, his.year(year), parts[year])
    part = out.with_name(out.name + ".part")
    try:
        with part.open("wb") as fh:
            for year in YEARS:
                tag = f"{year}\t".encode()
                with parts[year].open("rb") as names:
                    for line in names:
                        fh.write(tag + line)
        os.replace(part, out)
    finally:
        part.unlink(missing_ok=True)
    return held.lines(out)


def _write_manifests(conn: duckdb.DuckDBPyConnection, netnew_dir: Path) -> None:
    """One row per shipped line, read back from the written files, so a manifest describes no
    line that does not ship and misses none that does. Each cites the row its record cites,
    which qualifies. Needs `netnew_pair`."""
    conn.execute("CREATE OR REPLACE TEMP TABLE shipped_hostname (name VARCHAR, year INTEGER)")
    for year in YEARS:
        held.read_names(conn, "_shipped", netnew_dir / f"{year}_hostnames.txt", year)
        conn.execute("INSERT INTO shipped_hostname SELECT name, year FROM _shipped")
    conn.execute("DROP TABLE _shipped")
    hostnames = """
        SELECT hy.hostname, hy.parent_domain, hy.assigned_year, e.evidence_type,
               e.evidence_value, s.name AS source, e.acquisition_method, e.evidence_url
        FROM shipped_hostname n
        JOIN hostname_year hy ON hy.hostname = n.name AND hy.assigned_year = n.year
        JOIN evidence e ON e.evidence_id = hy.evidence_id
        JOIN source s ON s.source_id = e.source_id
        ORDER BY hy.hostname, hy.assigned_year
    """
    registrables = """
        SELECT n.domain, n.year AS assigned_year, e.evidence_type, e.evidence_value,
               s.name AS source, e.acquisition_method, e.evidence_url
        FROM netnew_pair n
        JOIN evidence e ON e.evidence_id = n.evidence_id
        JOIN source s ON s.source_id = e.source_id
        ORDER BY n.domain, n.year
    """
    for name, suffix, query in (
        ("hostnames_evidence_manifest.csv", "_hostnames", hostnames),
        ("evidence_manifest.csv", "", registrables),
    ):
        (rows,) = conn.execute(f"COPY ({query}) TO '{netnew_dir / name}' (HEADER true)").fetchone()
        shipped = sum(held.lines(netnew_dir / f"{year}{suffix}.txt") for year in YEARS)
        if rows != shipped:
            raise ValueError(f"{name} has {rows} rows for {shipped} shipped lines")


def _candidate_pool(conn: duckdb.DuckDBPyConnection, his: held.Held, work: Path) -> list[Path]:
    """Build `candidate_pool(name, unit)` and return the files of names his candidate files
    took out of its two store arms. Needs `claim_pair`, `our_domains` and `isc_export`."""
    arms = {
        # a registrable we found with no year of ours that ships as a web capture of it
        "registrable": f"""
            SELECT d.domain FROM domain d
            WHERE d.domain NOT IN (SELECT domain FROM claim_pair)
              AND {held.we_know("d")} AND {_shipping_filter("d.", with_year=False)}
            ORDER BY 1
        """,
        # **A hostname whose every year fails XIII is a candidate too.** XIII names the
        # classes (mail and Usenet delivery headers, DNS listings, registry events, mentions)
        # and says to store them as source-specific candidate assets with provenance; the ISC
        # arm is that shape for one source. Same rule as the registrable arm: no web capture
        # of the exact host in any year, then the hostname gate.
        "hostname": f"""
            SELECT DISTINCT hy.hostname FROM hostname_year hy
            WHERE NOT EXISTS (SELECT 1 FROM hostname_year hz
                              WHERE hz.hostname = hy.hostname
                                AND {web_evidence_exists("hz.evidence_id", "hz.hostname")})
              AND {HOSTNAME_SHIPPING_FILTER}
            ORDER BY 1
        """,
    }
    taken = []
    for unit, query in arms.items():
        names = work / f"pool_{unit}.txt"
        held.dump(conn, query, names)
        taken.append(work / f"pool_{unit}_held.txt")
        _minus_his(names, his, work / f"pool_{unit}_kept.txt", taken[-1])
        held.read_names(conn, f"_pool_{unit}", work / f"pool_{unit}_kept.txt")
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE candidate_pool AS
        SELECT name, 'registrable' AS unit FROM _pool_registrable
    """)
    # the ISC survey hostnames, already reduced by `reduce_isc` against every candidate and
    # annual name he holds, and against everything we hold ourselves
    conn.execute("INSERT INTO candidate_pool SELECT DISTINCT hostname, 'hostname' FROM isc_export")
    conn.execute("""
        INSERT INTO candidate_pool
        SELECT name, 'hostname' FROM _pool_hostname
        WHERE name NOT IN (SELECT name FROM candidate_pool)
    """)
    conn.execute("DROP TABLE _pool_registrable")
    conn.execute("DROP TABLE _pool_hostname")
    return taken


def export_header_candidates(
    conn: duckdb.DuckDBPyConnection, netnew_dir: Path, stats: dict[str, int]
) -> None:
    """XIII's source-specific candidate asset: every hostname in the claim whose only dated
    evidence is a non-web class (a server-written mail or Usenet header, a DNS listing), with
    per-host provenance, a summary and the exclusion ledger of the same validation run. Runs
    after the pool is reconciled, so every name here is in `candidate_additions.txt`. An
    error capture is web evidence that failed on its status, so it is not in this asset."""
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
          AND NOT regexp_matches(e.evidence_value, '{ERROR_STATUS}')
    """)
    stats["header_candidates"] = held.dump(
        conn,
        "SELECT DISTINCT hostname FROM header_provenance ORDER BY hostname",
        netnew_dir / "header_candidates.txt",
    )
    provenance_path = netnew_dir / "header_candidates_provenance.csv"
    conn.execute(f"""
        COPY (SELECT * FROM header_provenance
              ORDER BY hostname, target_year, source, record_location,
                       acquisition_method, evidence_type, source_url)
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
              AND NOT regexp_matches(e.evidence_value, '{ERROR_STATUS}')
            ORDER BY hy.hostname, e.evidence_url, e.evidence_value
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
    report_dir: Path = DEFAULT_REPORT_DIR,
    provenance_dir: Path = PROVENANCE_DIR,
    baseline: Path | None = None,
    with_provenance: bool = False,
    claim_only: bool = False,
) -> dict[str, int]:
    """Write every result file, or with `claim_only` only `claim_files` and the stamp: no
    manifests, ISC files or contribution tables. Every destination is a parameter, so a
    caller that redirects the outputs redirects all of them; leaving one hardcoded let the
    test suite overwrite the real contribution tables with a test store.

    `baseline` is his release folder, `held.his_dir()` by default. Without the held sets
    `ark intake` wrote for it, `held.HeldError` stops the export before it writes a file, the
    old stamp already gone."""
    if claim_only and with_provenance:
        raise ValueError("a claim export writes no provenance graph")
    (netnew_dir / STAMP_NAME).unlink(missing_ok=True)
    # read once: this connection holds the store, so nothing moves it before the stamp
    ledger = store_ledger(conn)
    stats: dict[str, int] = {}
    with _phase("held"):
        his = held.load(baseline)
        held.our_domain_year(conn)
        held.claim_pairs(conn)
        held.our_domains(conn)
    netnew_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=netnew_dir.parent, prefix=".export-") as tmp:
        work = Path(tmp)
        with _phase("attested registrables"):
            stats["attested_registrables"] = _write_attested(
                conn, his, work, netnew_dir / ATTESTED_NAME
            )

        with _phase("netnew"):
            for year, count in held.netnew(conn, his, work, netnew_dir).items():
                stats[f"netnew_{year}"] = count

        # The hostname half of the annual contribution ships beside the registrable half.
        # Brief IV.8 requires exact qualifying hostnames, not a registrable-only roll-up;
        # these are annual records, not auxiliary seeds.
        with _phase("hostnames"):
            for year in YEARS:
                hosts = work / f"host_{year}.txt"
                held.dump(
                    conn,
                    f"""
                    SELECT DISTINCT hy.hostname FROM hostname_year hy
                    WHERE hy.assigned_year = {year} AND {HOSTNAME_SHIPPING_FILTER}
                      AND {web_evidence_exists("hy.evidence_id", "hy.hostname")}
                    ORDER BY 1
                    """,
                    hosts,
                )
                stats[f"netnew_hostnames_{year}"] = held.minus(
                    hosts, his.year(year), netnew_dir / f"{year}_hostnames.txt"
                )

        # The claim runs the ISC reduction too: the summary counts his survey names among the
        # names he held, and what survives it joins the candidate pool.
        with _phase("isc"):
            isc_taken = reduce_isc(conn, his, work)
            taken = [isc_taken] if isc_taken else []
            if not claim_only:
                export_isc_hostnames(conn, netnew_dir, stats)
                export_isc_provenance(conn, netnew_dir, stats)

        if not claim_only:
            with _phase("manifests"):
                _write_manifests(conn, netnew_dir)

        # `candidates.txt` ships beside the claim, so it holds none of his names either: it was a
        # store-only list, and 341,674 of its 375,476 names were in his `candidate_pool.txt`.
        # A name only his release filed is his, not ours to offer back.
        with _phase("candidate_unverified"):
            unverified = work / "unverified.txt"
            held.dump(
                conn,
                f"""
                SELECT d.domain FROM domain d
                WHERE NOT EXISTS (SELECT 1 FROM our_domain_year dy WHERE dy.domain = d.domain)
                  AND {held.we_know("d")} AND {_shipping_filter("d.", with_year=False)}
                ORDER BY 1
                """,
                unverified,
            )
            stats["candidates"] = _minus_his(unverified, his, candidates_path)

        # THE CANDIDATE TRACK, as one pool. He scores candidates separately and at the same
        # rate as annual records, so this is held to the same net-new standard: every
        # candidate collection we hold, unioned, minus every name his release holds as a
        # candidate (`held.candidate_files`) or lists in any of his six annual files.
        #
        # One file, not one per collection: provenance belongs in `provenance/` and
        # `isc_survey_provenance.csv`, and splitting the pool by origin makes the reviewer
        # reconcile three files to count one track.
        #
        # The whole pool is NOT the claim: our registrable pool held 2,279,755 names and
        # 29,327 of them were absent from his files, so shipping the pool as the contribution
        # would overstate the registrable half of this track by 78x.
        #
        # **A registrable name whose every year fails XIII is a candidate, not nothing**:
        # failing rows re-track to candidates. When the pool took only names with NO year at
        # all, a registry list ingested as `artifact_listing` earned a year the annual screen
        # then refused, and the name fell between the two tracks: the `.dk` zone list's
        # 251,114 rows shipped in neither file.
        with _phase("candidate pool"):
            taken += _candidate_pool(conn, his, work)
            stats["candidate_additions"] = held.dump(
                conn,
                "SELECT DISTINCT name FROM candidate_pool ORDER BY name",
                netnew_dir / "candidate_additions.txt",
            )
            # the distinct names his candidate files took out of the claim, before his years
            held_names = held.union(taken, work / "held_by_him.txt")

        with _phase("header candidates"):
            export_header_candidates(conn, netnew_dir, stats)
        weights = english_weights()
        counts = conn.execute(
            """
            SELECT unit, regexp_extract(name, '([a-z0-9-]+)$', 1) AS tld, count(*)
            FROM candidate_pool GROUP BY 1, 2 ORDER BY 1, 2
            """
        ).fetchall()
        by_unit: dict[str, tuple[int, Decimal]] = {}
        for unit, tld, n in counts:
            unit_n, unit_ee = by_unit.get(unit, (0, Decimal(0)))
            by_unit[unit] = (unit_n + n, unit_ee + weights.get(tld, Decimal(0)) * n)
        summary = {
            "baseline": CURRENT_BASELINE_MARKER,
            "track": "candidate",
            "counting_unit": "distinct name, registrable domains and exact hostnames in one pool",
            "candidates": sum(n for n, _ in by_unit.values()),
            "equivalent_english": str(sum((ee for _, ee in by_unit.values()), Decimal(0))),
            "by_unit": {
                u: {"names": n, "equivalent_english": str(ee)} for u, (n, ee) in by_unit.items()
            },
            # what his release already held, and so what the claim is net of
            "held_by_him": {
                "names": held_names,
                "files": [str(p.relative_to(his.baseline)) for p in his.candidate_files],
            },
        }
        (netnew_dir / "candidate_additions_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )

        if not claim_only:
            # per-source and per-year contribution tables, which ship in the audit folder
            with _phase("contribution tables"):
                held.held_any(conn, his, work)
                stats.update(write_contribution_tables(conn, report_dir, his, netnew_dir))

    # The provenance graph itself, so a reader can ask "why is this domain in this year?"
    # without the source data or a copy of the database.
    #
    # **Off by default, because it is 52% of this command.** Measured 2026-09-18: 229 of
    # 444 seconds, writing 2,319 MB over 81.7M evidence and 28.0M hostname_year rows. It
    # is read in exactly two places, `just rebuild` and `package_delivery.sh`, and neither
    # runs hourly. The sync that fires every hour paid for it anyway.
    if with_provenance:
        with _phase("provenance"):
            provenance = write_provenance(conn, provenance_dir)
        stats["provenance_mb"] = provenance["megabytes"]

    stamp = {
        "mode": "claim" if claim_only else "full",
        "written_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **ledger,
        "baseline": CURRENT_BASELINE_MARKER,
        "provenance": with_provenance,
    }
    (netnew_dir / STAMP_NAME).write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    logger.info(f"export: {stats}")
    return stats


def claim_files(
    netnew_dir: Path = NETNEW_DIR, candidates_path: Path = CANDIDATES_PATH
) -> list[Path]:
    """Every file a claim export writes but its stamp. A full export writes each of them byte
    for byte the same, and ROUND.md is built from them."""
    names = [f"{year}{suffix}.txt" for suffix in ("", "_hostnames") for year in YEARS]
    names += ["candidate_additions.txt", "candidate_additions_summary.json"]
    names += [
        f"header_candidates{end}"
        for end in (".txt", "_provenance.csv", "_exclusions.csv", "_summary.json")
    ]
    names.append(ATTESTED_NAME)
    return [netnew_dir / name for name in names] + [candidates_path]


def store_ledger(conn: duckdb.DuckDBPyConnection) -> dict[str, int | None]:
    """What moves the store under an export: a new journal adds an `ingested_file` row, a grown
    one only raises the top evidence id, a seed adds `domain` rows and an unbank deletes rows, so
    two ledgers are compared for equality, never order."""
    return {
        "ingested_file_rows": conn.execute("SELECT count(*) FROM ingested_file").fetchone()[0],
        "max_evidence_id": conn.execute("SELECT max(evidence_id) FROM evidence").fetchone()[0],
        "domain_rows": conn.execute("SELECT count(*) FROM domain").fetchone()[0],
    }


def read_stamp(netnew_dir: Path = NETNEW_DIR) -> dict | None:
    """The stamp of the last export into `netnew_dir`, or None when there is none to read."""
    try:
        return json.loads((netnew_dir / STAMP_NAME).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def stamp_problems(
    conn: duckdb.DuckDBPyConnection | None = None,
    netnew_dir: Path = NETNEW_DIR,
    claim_dir: Path = CLAIM_COPY_DIR,
) -> list[str]:
    """Why the files on disk are not a shippable export, or nothing.

    Without `conn` it reads only files, so packaging refuses in seconds. With it, both stamps
    must match the store, and the bank's candidate claim must equal the full export's.
    """
    stamp = read_stamp(netnew_dir)
    if stamp is None:
        return [f"no readable {netnew_dir / STAMP_NAME}: run `just ship build`"]
    problems = []
    if stamp.get("mode") != "full":
        full_only = ["evidence_manifest.csv", "hostnames_evidence_manifest.csv"]
        full_only += [f"{year}-ISC.txt" for year in YEARS]
        full_only += ["isc_candidates.txt", "isc_candidates_summary.json"]
        full_only += ["isc_survey_provenance.csv"]
        stale = [netnew_dir / name for name in full_only]
        stale += [
            DEFAULT_REPORT_DIR / "source_contribution.csv",
            DEFAULT_REPORT_DIR / "year_growth.csv",
        ]
        problems.append(
            f"the last export was a {stamp.get('mode')} export, so these are stale: "
            f"{', '.join(map(str, stale))}; run `just ship build`"
        )
    if stamp.get("baseline") != CURRENT_BASELINE_MARKER:
        problems.append(
            f"the export diffed against {stamp.get('baseline')}, not {CURRENT_BASELINE_MARKER}"
        )
    if not stamp.get("provenance"):
        problems.append("the export wrote no provenance graph: run `ark export --provenance`")
    copy = read_stamp(claim_dir)
    if copy is None:
        problems.append(f"no bank stamp set aside at {claim_dir / STAMP_NAME}")
    if conn is None:
        return problems
    ledger = store_ledger(conn)
    stamped = {key: stamp.get(key) for key in ledger}
    if stamped != ledger:
        problems.append(
            f"the store moved after the export: its ledger is {ledger}, the stamp's {stamped}"
        )
    if copy is not None and {key: copy.get(key) for key in ledger} != stamped:
        problems.append("the bank's claim and the full export read different stores")
    ours, bank = netnew_dir / "candidate_additions.txt", claim_dir / "candidate_additions.txt"
    if not (ours.is_file() and bank.is_file() and filecmp.cmp(ours, bank, shallow=False)):
        problems.append(f"{bank} and {ours} differ")
    return problems
