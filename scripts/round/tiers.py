"""The labelled tiers, `tier_c/` and `tier_d/`: web-evidenced host-years outside the additions.

Each input row is a 1996 to 2001 (year, host) his file for that year lacks, with the dated web
record of exactly that host then: a capture of it, or a dated capture of a page that links to it.
The tier says where his 1996 to 2013 files hold the name around that year:

    tier_c  only in an earlier year
    tier_d  in no year

A row whose stated tier his files do not bear out refuses, as does one his same-year file holds.
Every row is netted against the export's 1996 to 2001 additions (`output/netnew`), and a host-year
named twice keeps its capture.

Writes `<tier>/<year>.txt` (one name a line, sorted), `<tier>/provenance.csv` (`name, year, kind,
source_file, position`) and `tiers.csv` (tier, kind, host-years, EE). His files are only read.

    uv run python scripts/round/tiers.py [--src data/labelled/tiers] [--out output/tiers]
        [--his DIR] [--additions DIR]
    uv run python scripts/round/tiers.py --readme output/tiers/tiers.csv   # the README's bullet

`--src` holds `*.tsv`, no header: year, host, kind (`capture` or `link`), tier (`C` or `D`),
source_file (the replay URL of the capture, or of the linking page), position (the capture's
14-digit stamp, or `replay #<stamp> <page URL>`).
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

TIERS = {"C": "tier_c", "D": "tier_d"}
COLUMNS = ("year", "host", "kind", "tier", "source_file", "position")


def build(src: Path, out: Path, his: Path, additions: Path | None = None) -> list[tuple]:
    years = [str(his / f"{y}.txt") for y in range(1996, 2014)]
    conn = duckdb.connect()
    conn.execute(f"SET memory_limit = '{DB_MEMORY_LIMIT}'")
    conn.execute("SET preserve_insertion_order = false")
    conn.execute(
        "CREATE TABLE ours AS SELECT DISTINCT ON (year, host) CAST(year AS INTEGER) AS year, host, "
        "kind, tier, source_file, position FROM read_csv(?, header = false, delim = '\t', "
        "quote = '', escape = '', columns = ?) ORDER BY year, host, kind",
        [sorted(str(p) for p in src.glob("*.tsv")), dict.fromkeys(COLUMNS, "VARCHAR")],
    )
    names = [f"{y}{s}.txt" for y in range(1996, 2002) for s in ("", "_hostnames")]
    files = [str(additions / n) for n in names if additions and (additions / n).is_file()]
    if files:
        conn.execute(
            "CREATE TABLE adds AS SELECT column0 AS host, CAST(regexp_extract(filename, "
            "'/([0-9]{4})[^/]*$', 1) AS INTEGER) AS year FROM read_csv(?, header = false, "
            "delim = '\t', quote = '', escape = '', filename = true, all_varchar = true)",
            [files],
        )
        conn.execute(
            "DELETE FROM ours WHERE EXISTS (SELECT 1 FROM adds a "
            "WHERE a.host = ours.host AND a.year = ours.year)"
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
    (wrong,) = conn.execute(
        "SELECT count(*) FROM (SELECT o.tier, coalesce(bool_or(h.year < o.year), false) AS before, "
        "coalesce(bool_or(h.year > o.year), false) AS after, o.year NOT BETWEEN 1996 AND 2001 "
        "OR o.kind NOT IN ('capture', 'link') AS odd FROM ours o LEFT JOIN held h "
        "ON h.host = o.host GROUP BY o.year, o.host, o.tier, o.kind) "
        "WHERE odd OR after OR tier NOT IN ('C', 'D') OR before <> (tier = 'C')"
    ).fetchone()
    if wrong:
        sys.exit(f"refusing: his files do not bear out the tier of {wrong} rows")
    if out.exists():
        shutil.rmtree(out)
    for letter, tier in TIERS.items():
        (out / tier).mkdir(parents=True)
        for year in range(1996, 2002):
            hosts = conn.execute(
                "SELECT host FROM ours WHERE tier = ? AND year = ? ORDER BY host", [letter, year]
            ).fetchall()
            (out / tier / f"{year}.txt").write_text("".join(f"{h}\n" for (h,) in hosts))
        conn.execute(
            "COPY (SELECT host AS name, year, kind, source_file, position FROM ours "
            f"WHERE tier = '{letter}' ORDER BY year, host) "
            f"TO '{out / tier / 'provenance.csv'}' (HEADER)"
        )
    conn.execute("CREATE TABLE w (tld VARCHAR, weight DOUBLE)")
    conn.executemany(
        "INSERT INTO w VALUES (?, ?)", [(k, float(v)) for k, v in english_weights().items()]
    )
    rows = conn.execute("""
        SELECT CASE tier WHEN 'C' THEN 'tier_c' ELSE 'tier_d' END, kind, count(*),
            round(sum(coalesce(w.weight, 0)), 1)
        FROM ours LEFT JOIN w ON w.tld = regexp_extract(host, '([a-z0-9-]+)$', 1)
        GROUP BY ALL ORDER BY ALL""").fetchall()
    with (out / "tiers.csv").open("w", newline="") as fh:
        csv.writer(fh).writerows([("tier", "kind", "host_years", "ee"), *rows])
    return rows


def readme(sizes: Path) -> str:
    """The README's bullet for the two folders, with their sizes."""
    with sizes.open(newline="") as fh:
        rows = [
            (r["tier"], r["kind"], int(r["host_years"]), float(r["ee"])) for r in csv.DictReader(fh)
        ]

    def size(tier: str) -> str:
        part = [r for r in rows if r[0] == tier]
        kinds = ", ".join(f"{r[2]:,} by a {r[1]}" for r in part)
        n, ee = sum(r[2] for r in part), sum(r[3] for r in part)
        return f"{n:,} host-years, {ee:,.1f} equivalent-English: {kinds}"

    return (
        "- `tier_c/`, `tier_d/`: 1996 to 2001 host-years your file for that year lacks, each with\n"
        "  its own web evidence of exactly that name in that year (a capture of it, or a dated\n"
        "  capture of a page that links to it), set apart from `additions/` by where your 1996 to\n"
        "  2013 files hold the name: `tier_c` only in an earlier year\n"
        f"  ({size('tier_c')}); `tier_d` in no year\n"
        f"  ({size('tier_d')}). One file a year, and `provenance.csv`:\n"
        "  `name, year, kind, source_file, position`, the replay URL of the capture or of the\n"
        "  linking page, and its stamp. None is an addition and none is in the growth figure; you\n"
        "  decide."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", type=Path, default=REPO / "data/labelled/tiers")
    ap.add_argument("--out", type=Path, default=REPO / "output/tiers")
    ap.add_argument("--his", type=Path, help="his release's year files (default: the baseline)")
    ap.add_argument("--additions", type=Path, default=REPO / "output/netnew")
    ap.add_argument("--readme", type=Path, help="print the README's bullet from this tiers.csv")
    args = ap.parse_args()
    if args.readme:
        print(readme(args.readme))
        return
    his = args.his or baseline_dir().resolve()
    for tier, kind, n, ee in build(args.src, args.out, his, args.additions):
        print(f"{tier}\t{kind}\t{n:,}\t{ee:,.1f} EE")


if __name__ == "__main__":
    main()
