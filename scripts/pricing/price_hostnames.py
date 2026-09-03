"""Price a corpus at hostname grain against the live store, writing nothing.

**Why a second pricer.** `price_items.py` collapses every name to its registrable and
prices the (domain, year) unit, which is right for the annual masters and wrong for
the second unit the reviewer accepted on 2026-09-01: 180 suffix journals it priced at
0 were worth 301,650 EE once the hostnames beneath the held registrables were counted.
The 26 `keep_until_priced` corpora in `docs/retention.md` were all priced the first
way, so none of them has a number at this grain, and until now the only way to get
one was `ark ingest-hostnames`, which takes the store's single write lock and writes
evidence rows. Pricing must not do either.

**It runs the ingest's own funnel**, imported from `ark.hostnames` rather than copied:
the 14-digit stamp dates the row, `_host_of` accepts RFC 1123 hosts only, the host must
reduce to a parent registrable and not be it, and `www.<parent>` is the parent's own
site. A hostname year is net-new when the store's `hostname_year` lacks it AND the
reviewer's baseline file for that year lacks it, which is exactly the export's rule.
The parent (registrable, year) pairs the same rows would assign are priced beside,
because the ingest writes both and a corpus can pay in either.

Two input shapes, the same ones the rest of the project already emits:

    uv run python scripts/pricing/price_hostnames.py data/raw/<x>_hostgrain/   # {url, timestamp}
    uv run python scripts/pricing/price_hostnames.py --items items.jsonl.gz    # {item, year, text}
    uv run python scripts/pricing/price_hostnames.py <dir> --head 200000 --sample-of 2413003

In `--items` mode `text` is one URL or hostname, or whitespace-separated several. The
linear projection printed under `--sample-of` is an UPPER bound: hostnames under one
parent saturate as a corpus is read, so quote the measured figure and label the
projection as such.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark.baseline import baseline_dir  # noqa: E402
from ark.canonical import to_registrable  # noqa: E402
from ark.db import connect_read_only_patiently  # noqa: E402
from ark.english_share import english_weights, weight_of  # noqa: E402
from ark.hostnames import YEARS, _host_of  # noqa: E402


def _opener(path: Path):  # noqa: ANN202 - a file object of either kind
    return gzip.open(path, "rt", errors="replace") if path.suffix == ".gz" else path.open()


def journal_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        files.extend(sorted(p.glob("*.jsonl*")) if p.is_dir() else [p])
    return files


def _year_of(record: dict) -> int | None:
    if "year" in record:
        try:
            year = int(record["year"])
        except (TypeError, ValueError):
            return None
        return year if year in YEARS else None
    text = str(record.get("date", ""))
    for i in range(len(text) - 3):
        chunk = text[i : i + 4]
        if chunk.isdigit() and int(chunk) in YEARS:
            return int(chunk)
    return None


def read_rows(
    files: list[Path], items: bool, head: int | None
) -> tuple[dict[tuple[str, int], str], Counter[str]]:
    """Distinct (host, year) with the earliest stamp seen, through the ingest's funnel."""
    counts: Counter[str] = Counter()
    seen: dict[tuple[str, int], str] = {}
    for path in files:
        read = 0
        with _opener(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                if head is not None and read >= head:
                    counts["head_cut_files"] += 1
                    break
                read += 1
                counts["lines"] += 1
                try:
                    row = json.loads(line)
                except ValueError:
                    counts["unparseable"] += 1
                    continue
                if items:
                    year = _year_of(row)
                    if year is None:
                        counts["undated_or_out_of_window"] += 1
                        continue
                    stamp = f"{year}0000000000"
                    urls = str(row.get("text", "")).split()
                else:
                    stamp = str(row.get("timestamp", ""))
                    if len(stamp) != 14 or not stamp.isdigit():
                        counts["bad_timestamp"] += 1
                        continue
                    year = int(stamp[:4])
                    if year not in YEARS:
                        counts["out_of_window"] += 1
                        continue
                    urls = [str(row.get("url", ""))]
                for url in urls:
                    host = _host_of(url)
                    if host is None:
                        counts["no_host"] += 1
                        continue
                    key = (host, year)
                    if key not in seen or stamp < seen[key]:
                        seen[key] = stamp
    return seen, counts


def funnel(seen: dict[tuple[str, int], str], counts: Counter[str]) -> list[tuple[str, str, int]]:
    """(hostname, parent, year) for the rows that could become hostname records."""
    parents: dict[str, str] = {}
    for host in {h for h, _ in seen}:
        reg = to_registrable(host)
        if reg is None:
            counts["rejected_host"] += 1
        elif reg == host:
            counts["registrable_row"] += 1
        elif host == f"www.{reg}":
            counts["www_of_parent"] += 1
        else:
            parents[host] = reg
    counts["distinct_host_years"] = len(seen)
    return [(h, parents[h], y) for (h, y) in sorted(seen) if h in parents]


def price(conn, rows: list[tuple[str, str, int]], baseline: Path | None) -> dict:  # noqa: ANN001
    """Difference the candidate rows against the store and the baseline files, read-only."""
    weights = english_weights()
    conn.execute("CREATE TEMP TABLE cand (hostname TEXT, parent TEXT, year INTEGER)")
    conn.executemany("INSERT INTO cand VALUES (?, ?, ?)", rows)
    conn.execute("CREATE TEMP TABLE baseline_host (hostname TEXT, year INTEGER)")
    years = sorted({y for _, _, y in rows})
    baseline_years = []
    for year in years:
        path = (baseline / f"{year}.txt") if baseline else None
        if path and path.exists():
            baseline_years.append(year)
            conn.execute(
                f"""
                INSERT INTO baseline_host
                SELECT lower(trim(column0)), {year}
                FROM read_csv('{path}', header=false, delim='\\x01',
                              columns={{'column0': 'VARCHAR'}})
                WHERE lower(trim(column0)) IN (SELECT hostname FROM cand WHERE year = {year})
                """
            )
    netnew = conn.execute(
        """
        SELECT c.hostname, c.parent, c.year,
               hy.hostname IS NOT NULL AS in_store,
               b.hostname IS NOT NULL AS in_baseline,
               d.domain IS NOT NULL AS parent_held
        FROM cand c
        LEFT JOIN hostname_year hy ON hy.hostname = c.hostname AND hy.assigned_year = c.year
        LEFT JOIN baseline_host b ON b.hostname = c.hostname AND b.year = c.year
        LEFT JOIN domain d ON d.domain = c.parent
        """
    ).fetchall()
    parent_new = conn.execute(
        """
        SELECT DISTINCT c.parent, c.year FROM cand c
        LEFT JOIN domain_year dy ON dy.domain = c.parent AND dy.assigned_year = c.year
        WHERE dy.domain IS NULL
        """
    ).fetchall()

    out: dict = {
        "candidates": len(rows),
        "in_store": sum(1 for r in netnew if r[3]),
        "in_baseline_only": sum(1 for r in netnew if r[4] and not r[3]),
        "parent_held_share": (sum(1 for r in netnew if r[5]) / len(rows)) if rows else 0.0,
        "baseline_years_checked": baseline_years,
    }
    new_rows = [r for r in netnew if not r[3] and not r[4]]
    by_year: Counter[int] = Counter()
    ee_by_year: dict[int, Decimal] = {}
    by_tld: dict[str, Decimal] = {}
    total = Decimal(0)
    for host, _parent, year, *_ in new_rows:
        w = weight_of(host, weights)
        by_year[year] += 1
        ee_by_year[year] = ee_by_year.get(year, Decimal(0)) + w
        tld = host.rsplit(".", 1)[-1]
        by_tld[tld] = by_tld.get(tld, Decimal(0)) + w
        total += w
    out["netnew_hostname_years"] = len(new_rows)
    out["netnew_by_year"] = dict(sorted(by_year.items()))
    out["netnew_ee_by_year"] = {y: str(v) for y, v in sorted(ee_by_year.items())}
    out["netnew_ee"] = total
    out["top_tlds"] = [(t, str(v)) for t, v in sorted(by_tld.items(), key=lambda kv: -kv[1])[:6]]
    out["parent_pairs_netnew"] = len(parent_new)
    out["parent_pairs_netnew_ee"] = sum((weight_of(p, weights) for p, _ in parent_new), Decimal(0))
    return out


def report(label: str, counts: Counter[str], priced: dict, sample_of: int | None) -> str:
    lines = [f"== hostname pricing{': ' + label if label else ''} =="]
    lines.append(
        f"lines {counts['lines']:,}  distinct host-years {counts['distinct_host_years']:,}  "
        f"candidates {priced['candidates']:,}"
    )
    drops = {
        k: counts[k]
        for k in (
            "bad_timestamp",
            "out_of_window",
            "undated_or_out_of_window",
            "no_host",
            "rejected_host",
            "registrable_row",
            "www_of_parent",
            "unparseable",
        )
        if counts[k]
    }
    if drops:
        lines.append("dropped: " + ", ".join(f"{k} {v:,}" for k, v in drops.items()))
    lines.append(
        f"already in store {priced['in_store']:,}  in his baseline only "
        f"{priced['in_baseline_only']:,}  parent held {priced['parent_held_share']:.1%}"
    )
    if not priced["baseline_years_checked"]:
        lines.append("WARNING: no baseline files found, every hostname counts as net-new")
    lines.append(
        f"NET-NEW hostname years {priced['netnew_hostname_years']:,}  "
        f"{priced['netnew_ee']:,.4f} EE   (quote this)"
    )
    for y, n in priced["netnew_by_year"].items():
        lines.append(
            f"    {y}: {n:>9,} hosts  {Decimal(priced['netnew_ee_by_year'][y]):>14,.4f} EE"
        )
    if priced["top_tlds"]:
        lines.append(
            "    top TLDs: " + ", ".join(f"{t} {Decimal(v):,.1f}" for t, v in priced["top_tlds"])
        )
    lines.append(
        f"parent (registrable, year) pairs net-new beside: {priced['parent_pairs_netnew']:,}  "
        f"{priced['parent_pairs_netnew_ee']:,.4f} EE"
    )
    if sample_of and counts["lines"]:
        factor = Decimal(sample_of) / Decimal(counts["lines"])
        lines.append(
            f"linear projection to {sample_of:,} lines: {priced['netnew_ee'] * factor:,.0f} EE, "
            "an UPPER bound (hosts under one parent saturate); do not quote it as the price"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", type=Path, help="journal files or dirs of {url, timestamp}")
    ap.add_argument("--items", type=Path, help="JSONL(.gz) of {item, year|date, text} instead")
    ap.add_argument("--head", type=int, help="read at most this many lines per file")
    ap.add_argument("--sample-of", type=int, help="lines in the whole corpus, for the projection")
    ap.add_argument("--label", default="")
    ap.add_argument("--json", type=Path, help="also write the figures here")
    args = ap.parse_args()
    if bool(args.items) == bool(args.paths):
        ap.error("give journal paths or --items, not both and not neither")

    files = [args.items] if args.items else journal_files(args.paths)
    seen, counts = read_rows(files, items=bool(args.items), head=args.head)
    rows = funnel(seen, counts)
    conn = connect_read_only_patiently()
    try:
        # several of these run side by side when a batch of corpora is priced, and
        # DuckDB's default is most of the machine per process
        conn.execute("SET memory_limit = '3GB'")
        conn.execute("SET threads = 2")
        priced = price(conn, rows, baseline_dir())
    finally:
        conn.close()
    print(report(args.label, counts, priced, args.sample_of))
    if args.json:
        payload = {**priced, "counts": dict(counts), "label": args.label}
        args.json.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
