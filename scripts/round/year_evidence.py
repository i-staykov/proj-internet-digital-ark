"""The third part, `year_evidence/`: names he holds, dated by our record in a new year.

Each input row is a (year, host) his file for that year lacks while another file of his holds the
host (another year, or `candidate_pool.txt`), with the dated non-web record that names it then.
The tier says where his own files place the name around that year, the strongest first:

    1_bracketed   he holds the exact host in a year before and in a year after
    2_after_only  only in a later year: the record dates the name earlier than he does
    3_before_only only in an earlier year: the record carries the name on
    4_pool_only   in no year file of his, only in his candidate pool

Writes one `year,host` file per tier, `provenance.csv` (the input's columns and the tier, in tier
order) and `tiers.csv` (host-years, EE, and the share resting on a dated URL or print record).
Refuses a row his same-year file holds. His files are only read.

    uv run python scripts/round/year_evidence.py [--src data/labelled/nonweb_years]
        [--out output/year_evidence] [--his DIR]
"""

import argparse
import csv
import shutil
import sys
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from ark.baseline import baseline_dir  # noqa: E402
from ark.db import DB_MEMORY_LIMIT  # noqa: E402
from ark.english_share import english_weights  # noqa: E402

TIERS = ("1_bracketed", "2_after_only", "3_before_only", "4_pool_only")
URL_CLASSES = ("message body: URL host", "dated print, OCR text")


def build(src: Path, out: Path, his: Path) -> list[tuple]:
    years = [str(his / f"{y}.txt") for y in range(1996, 2014)]
    conn = duckdb.connect()
    conn.execute(f"SET memory_limit = '{DB_MEMORY_LIMIT}'")
    conn.execute("SET preserve_insertion_order = false")
    conn.execute(
        "CREATE TABLE ours AS SELECT CAST(year AS INTEGER) AS year, host, class, source, locator "
        "FROM read_csv(?, header = true, all_varchar = true)",
        [str(src / "provenance.csv")],
    )
    conn.execute(
        "CREATE TABLE held AS SELECT DISTINCT host, "
        "CAST(regexp_extract(filename, '([0-9]{4})[.]txt$', 1) AS INTEGER) AS year "
        "FROM read_csv(?, columns = {'host': 'VARCHAR'}, header = false, delim = '\t', "
        "quote = '', escape = '', filename = true) "
        "WHERE host IN (SELECT host FROM ours)",
        [years],
    )
    (same,) = conn.execute("SELECT count(*) FROM ours o JOIN held h USING (host, year)").fetchone()
    if same:
        sys.exit(f"refusing: {same} rows sit in his file for their own year")
    conn.execute("CREATE TABLE w (tld VARCHAR, weight DOUBLE)")
    conn.executemany(
        "INSERT INTO w VALUES (?, ?)", [(k, float(v)) for k, v in english_weights().items()]
    )
    conn.execute(f"""
        CREATE TABLE tiered AS SELECT o.*, CASE
            WHEN bool_or(h.year < o.year) AND bool_or(h.year > o.year) THEN '{TIERS[0]}'
            WHEN bool_or(h.year > o.year) THEN '{TIERS[1]}'
            WHEN bool_or(h.year < o.year) THEN '{TIERS[2]}'
            ELSE '{TIERS[3]}' END AS tier
        FROM ours o LEFT JOIN held h ON h.host = o.host
        GROUP BY ALL""")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for tier in TIERS:
        conn.execute(
            f"COPY (SELECT year, host FROM tiered WHERE tier = '{tier}' ORDER BY year, host) "
            f"TO '{out / (tier + '.csv')}' (HEADER)"
        )
    conn.execute(
        "COPY (SELECT year, host, class, source, locator, tier FROM tiered "
        f"ORDER BY tier, year, host) TO '{out / 'provenance.csv'}' (HEADER)"
    )
    url = ", ".join(f"'{c}'" for c in URL_CLASSES)
    rows = conn.execute(f"""
        SELECT tier, count(*), round(sum(coalesce(w.weight, 0)), 1),
            round(avg(CASE WHEN class IN ({url}) THEN 1 ELSE 0 END), 4)
        FROM tiered LEFT JOIN w ON w.tld = regexp_extract(host, '([a-z0-9-]+)$', 1)
        GROUP BY tier ORDER BY tier""").fetchall()
    with (out / "tiers.csv").open("w", newline="") as fh:
        csv.writer(fh).writerows([("tier", "host_years", "ee", "dated_url_share"), *rows])
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", type=Path, default=REPO / "data/labelled/nonweb_years")
    ap.add_argument("--out", type=Path, default=REPO / "output/year_evidence")
    ap.add_argument("--his", type=Path, help="his release's year files (default: the baseline)")
    args = ap.parse_args()
    for tier, n, ee, share in build(args.src, args.out, args.his or baseline_dir().resolve()):
        print(f"{tier}\t{n:,}\t{ee:,.1f} EE\t{share:.1%} dated URL or print")


if __name__ == "__main__":
    main()
