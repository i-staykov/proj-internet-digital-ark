"""Verify and measure the shipped ISC files without the provenance store."""

import argparse
import json
import tempfile
from decimal import Decimal
from pathlib import Path

import duckdb

try:
    from ark.english_share import english_weights
except ModuleNotFoundError:
    from isc_survey_hostnames.english_share import english_weights

YEARS = range(1996, 2002)
NAMES = "read_csv(?, header=false, delim='\x01', quote='', columns={'hostname': 'VARCHAR'})"


def verify(collection: Path, baseline: Path, annual_dirs: list[Path], weights_path: Path) -> dict:
    """Require exact-name novelty, complete provenance and reproducible candidate-only EE."""
    with tempfile.TemporaryDirectory(prefix="isc-verify-") as scratch:
        with duckdb.connect(config={"memory_limit": "2GB", "temp_directory": scratch}) as conn:
            return _verify(conn, collection, baseline, annual_dirs, weights_path)


def _verify(conn, collection, baseline, annual_dirs, weights_path):
    summary = json.loads((collection / "isc_candidates_summary.json").read_text())
    if summary["baseline"] != baseline.name or summary["track"] != "candidate":
        raise ValueError("ISC summary must name the current candidate baseline")
    conn.execute("CREATE TEMP TABLE years (hostname VARCHAR, year INTEGER)")
    by_year = {}
    for year in YEARS:
        path = collection / f"{year}-ISC.txt"
        conn.execute(f"INSERT INTO years SELECT hostname, {year} FROM {NAMES}", [str(path)])
        n, distinct = conn.execute(
            "SELECT count(*), count(DISTINCT hostname) FROM years WHERE year = ?", [year]
        ).fetchone()
        if n != distinct:
            raise ValueError(f"ISC {year} list contains duplicate names")
        by_year[str(year)] = n
    conn.execute(
        f"CREATE TEMP TABLE candidates AS SELECT hostname FROM {NAMES}",
        [str(collection / "isc_candidates.txt")],
    )
    n, distinct = conn.execute(
        "SELECT count(*), count(DISTINCT hostname) FROM candidates"
    ).fetchone()
    if n != distinct:
        raise ValueError("ISC candidate list contains duplicate names")
    different = conn.execute("""
        SELECT count(*) FROM (
            (SELECT hostname FROM candidates EXCEPT SELECT hostname FROM years)
            UNION ALL
            (SELECT hostname FROM years EXCEPT SELECT hostname FROM candidates)
        )
    """).fetchone()[0]
    if different:
        raise ValueError("ISC candidate list differs from the survey-year union")
    invalid = conn.execute(r"""
        SELECT count(*) FROM candidates
        WHERE length(hostname) > 253 OR NOT regexp_full_match(hostname,
          '[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*\.[a-z]{2,63}')
    """).fetchone()[0]
    if invalid:
        raise ValueError(f"ISC candidate list contains {invalid} malformed names")

    excluded = [baseline / "candidate_pool.txt", *(baseline / f"{y}.txt" for y in YEARS)]
    for directory in annual_dirs:
        for year in YEARS:
            files = [directory / f"{year}{suffix}.txt" for suffix in ("", "_hostnames")]
            present = [p for p in files if p.is_file()]
            if not present:
                raise FileNotFoundError(f"Missing annual files for {year} in {directory}")
            excluded.extend(present)
    for path in excluded:
        overlap = conn.execute(
            f"""
            SELECT count(*) FROM candidates c
            WHERE EXISTS (SELECT 1 FROM {NAMES} held
                          WHERE lower(trim(held.hostname)) = c.hostname)
        """,
            [str(path)],
        ).fetchone()[0]
        if overlap:
            raise ValueError(f"ISC candidates overlap {path}: {overlap} exact names")

    conn.execute(
        """
        CREATE TEMP TABLE provenance AS
        SELECT * FROM read_csv(?, header=true, all_varchar=true)
    """,
        [str(collection / "isc_survey_provenance.csv")],
    )
    incomplete = conn.execute("""
        SELECT count(*) FROM provenance
        WHERE coalesce(trim(survey_edition), '') = ''
           OR coalesce(trim(source_file), '') = ''
           OR coalesce(trim(source_url), '') = ''
           OR coalesce(trim(record_location), '') = ''
           OR coalesce(trim(extraction_method), '') = ''
           OR try_cast(target_year AS INTEGER) IS NULL
           OR try_cast(substr(survey_edition, 1, 4) AS INTEGER)
                IS DISTINCT FROM try_cast(target_year AS INTEGER)
    """).fetchone()[0]
    if incomplete:
        raise ValueError(f"ISC provenance has {incomplete} incomplete rows")
    mismatch = conn.execute("""
        SELECT count(*) FROM (
            (SELECT hostname, year FROM years
             EXCEPT SELECT hostname, target_year::INTEGER FROM provenance)
            UNION ALL
            (SELECT hostname, target_year::INTEGER FROM provenance
             EXCEPT SELECT hostname, year FROM years)
        )
    """).fetchone()[0]
    if mismatch:
        raise ValueError(f"ISC provenance differs from the candidate years: {mismatch} keys")
    rows = conn.execute("SELECT count(*) FROM provenance").fetchone()[0]
    tlds = dict(
        conn.execute("""
        SELECT regexp_extract(hostname, '[^.]+$'), count(*)
        FROM candidates GROUP BY 1 ORDER BY 1
    """).fetchall()
    )
    weights = english_weights(weights_path)
    ee = sum((weights.get(tld, Decimal(0)) * count for tld, count in tlds.items()), Decimal(0))
    measured = {
        "candidates": n,
        "equivalent_english": str(ee.quantize(Decimal("0.0001"))),
        "hostname_years": sum(by_year.values()),
        "by_year": by_year,
        "provenance_rows": rows,
        "tld_counts": tlds,
    }
    for key, value in measured.items():
        if summary[key] != value:
            raise ValueError(f"ISC summary does not reproduce: {key}")
    return {"baseline": baseline.name, **measured}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--annual-dirs", type=Path, nargs="+", required=True)
    parser.add_argument("--weights", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.collection, args.baseline, args.annual_dirs, args.weights)
    print(
        f"ISC candidates PASS: {result['candidates']:,} unique hosts, "
        f"{result['equivalent_english']} equivalent-English, "
        f"{result['hostname_years']:,} survey hostname-years, "
        f"{result['provenance_rows']:,} provenance rows; "
        "zero reviewer-candidate or annual overlap"
    )


if __name__ == "__main__":
    main()
