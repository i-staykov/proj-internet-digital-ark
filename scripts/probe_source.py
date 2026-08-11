"""Turn a URL into a priceable journal from a TOML description, writing no Python.

**What this is for.** The discovery loop's own output says it cannot write the
fetcher that turns a source into dated items, and that step used to stand between
a hypothesis and a number: 186 lines of collector before anyone could find out
whether the source was worth 186 lines. Of the last four sources considered, two
were rejected on measurement and never needed a parser at all. So the thing worth
making cheap is the **measurement**, not the ingest.

    uv run python scripts/probe_source.py probes/example.toml
    just price --items data/raw/probes/example.jsonl --label example

**What it deliberately cannot do.** Its output has no entry in `ark.sources.SOURCES`,
so `ark ingest` has no spec to run and there is no path by which a probe can date a
year. That is not a policy, it is an absence, which is the same safety ADR-003 chose:
an unwired thing cannot contaminate. A source that prices well still earns a
hand-written collector whose refusals are specific to its document, and a human still
classifies the class in `docs/approved-sources-list.md`. Reasoning in ADR-004.

**It refuses to guess.** No column sniffing, no "find the date somewhere on the page".
The spec names the column or field, and a spec that names the wrong one fails on the
first rows rather than quietly producing plausible rubbish. Yield is the number this
tool exists to produce, so a silent drop is the one failure that would turn its answer
into a lie: it therefore reports what it threw away, by reason, and says so out loud
when it kept less than half.

A spec, with only `name`, `url`, `kind` and the two field names required:

    name = "example_directory"
    url  = "https://example.org/1997/companies.html"
    kind = "html_table"        # html_table | lines | jsonl
    domain_column = 1          # html_table: 0-based cell index
    date_column   = 3
    table = 0                  # optional: which <table>, default every row on the page
    header_rows = 1            # optional: rows to skip
    domain_pattern = "..."     # optional: mine every match inside the cell, for a
                               # cell that lists several names
    # kind = "lines"           -> domain_pattern, date_pattern (regex, group 1 or whole)
    # kind = "jsonl"           -> domain_field, date_field (dotted, digits index lists)
    year = 1997                # optional: the whole page is one year, so no date field
"""

import argparse
import html
import json
import re
import sys
import tomllib
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ark.canonical import to_registrable  # noqa: E402

OUT_DIR = ROOT / "data/raw/probes"
YEARS = range(1996, 2002)
UA = (
    "InternetDigitalArk/1.0 (historical domain research, 1996-2001; "
    "contact ivaylo.staykov@taktile.com)"
)
ROW_RE = re.compile(r"(?is)<tr[^>]*>(.*?)</tr>")
CELL_RE = re.compile(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>")
TABLE_RE = re.compile(r"(?is)<table[^>]*>(.*?)</table>")
# A year anywhere in the cell, which is what the pricer does with a `date` too. The
# window is checked separately so an out-of-window row is refused with its own reason
# rather than counted as undated: those two say different things about a source.
ANY_YEAR_RE = re.compile(r"\b(19\d{2}|20[0-2]\d)\b")
KINDS = ("html_table", "lines", "jsonl")


def cell_text(cell: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", cell))).strip()


def fetch(url: str, timeout: int = 180) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        raise SystemExit(f"could not fetch {url}: {exc}") from exc


def page_for(spec: dict, cache: Path, refetch: bool) -> str:
    """Fetch once and keep it. Iterating on a spec must not re-ask the host, both
    because that is rude and because a changing page makes two runs incomparable."""
    if cache.exists() and not refetch:
        print(f"  using the cached copy: {cache.relative_to(ROOT)}")
        return cache.read_text(encoding="utf-8", errors="replace")
    body = fetch(spec["url"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(body, encoding="utf-8")
    print(f"  fetched {len(body):,} bytes -> {cache.relative_to(ROOT)}")
    return body


def need(spec: dict, *keys: str) -> None:
    missing = [k for k in keys if not spec.get(k) and spec.get(k) != 0]
    if missing:
        raise SystemExit(
            f"kind '{spec['kind']}' needs {', '.join(keys)}; missing {', '.join(missing)}.\n"
            f"This tool does not guess which column holds the hostname: a guess that is "
            f"wrong prices the wrong thing and reads as a bad source."
        )


def dotted(record: dict, path: str):
    """`events.0.eventDate`, where a digit indexes a list. Returns None on any miss,
    because a field that is absent and a field that is empty mean the same here."""
    node = record
    for part in path.split("."):
        if isinstance(node, list):
            if not part.isdigit() or int(part) >= len(node):
                return None
            node = node[int(part)]
        elif isinstance(node, dict):
            if part not in node:
                return None
            node = node[part]
        else:
            return None
    return node


def rows_of(spec: dict, page: str) -> list[list[str]]:
    tables = TABLE_RE.findall(page)
    index = spec.get("table")
    if index is not None:
        if index >= len(tables):
            raise SystemExit(
                f"the page has {len(tables)} table(s); the spec asks for index {index}"
            )
        page = tables[index]
    return [[cell_text(c) for c in CELL_RE.findall(row)] for row in ROW_RE.findall(page)]


def pairs_from(spec: dict, page: str, stats: Counter):
    """Yield `(identifier, raw hostname, date text, whole row)` before validation.

    Extraction and judgement are separate on purpose: everything below counts its
    refusals in one place, so the summary cannot disagree with what was written.
    """
    kind = spec["kind"]
    if kind == "html_table":
        need(spec, "domain_column")
        dcol, tcol = spec["domain_column"], spec.get("date_column")
        # One cell holding several hostnames is a common real shape, not an edge
        # case: the UDRP dockets list every disputed name of a case in one cell. A
        # cell taken whole would refuse those rows and price the source too low,
        # which is the failure this tool exists to avoid.
        inner = re.compile(spec["domain_pattern"]) if spec.get("domain_pattern") else None
        for number, row in enumerate(rows_of(spec, page)):
            if number < spec.get("header_rows", 0):
                continue
            stats["rows_seen"] += 1
            if dcol >= len(row) or (tcol is not None and tcol >= len(row)):
                stats["refused_short_row"] += 1
                continue
            when = row[tcol] if tcol is not None else ""
            whole = " | ".join(row)
            if inner is None:
                yield f"row {number}", row[dcol], when, whole
                continue
            found = inner.findall(row[dcol])
            if not found:
                stats["refused_no_hostname_in_cell"] += 1
                continue
            for hit in found:
                yield f"row {number}", hit if isinstance(hit, str) else hit[0], when, whole
    elif kind == "lines":
        need(spec, "domain_pattern")
        dpat = re.compile(spec["domain_pattern"])
        tpat = re.compile(spec["date_pattern"]) if spec.get("date_pattern") else None
        for number, line in enumerate(page.splitlines()):
            if not line.strip():
                continue
            stats["rows_seen"] += 1
            found = dpat.search(line)
            if not found:
                stats["refused_no_hostname_match"] += 1
                continue
            when = tpat.search(line) if tpat else None
            yield (
                f"line {number}",
                found.group(1) if found.groups() else found.group(0),
                (when.group(1) if when and when.groups() else (when.group(0) if when else "")),
                line.strip()[:400],
            )
    else:
        need(spec, "domain_field")
        for number, line in enumerate(page.splitlines()):
            line = line.strip()
            if not line:
                continue
            stats["rows_seen"] += 1
            try:
                record = json.loads(line)
            except ValueError:
                stats["refused_unparseable_json"] += 1
                continue
            name = dotted(record, spec["domain_field"])
            when = dotted(record, spec["date_field"]) if spec.get("date_field") else ""
            if name is None:
                stats["refused_field_absent"] += 1
                continue
            yield f"record {number}", str(name), str(when or ""), line[:400]


def year_of(spec: dict, date_text: str, stats: Counter) -> int | None:
    fixed = spec.get("year")
    if fixed is not None:
        return int(fixed) if int(fixed) in YEARS else None
    found = ANY_YEAR_RE.search(date_text)
    if not found:
        stats["refused_no_date"] += 1
        return None
    year = int(found.group(1))
    if year not in YEARS:
        stats["refused_year_out_of_window"] += 1
        return None
    return year


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec", type=Path, help="the TOML description of one source")
    ap.add_argument("--refetch", action="store_true", help="re-ask the host, ignoring the cache")
    ap.add_argument("--limit", type=int, default=None, help="stop after N accepted records")
    args = ap.parse_args()

    spec = tomllib.loads(args.spec.read_text(encoding="utf-8"))
    for key in ("name", "url", "kind"):
        if not spec.get(key):
            raise SystemExit(f"the spec needs a `{key}`")
    if spec["kind"] not in KINDS:
        raise SystemExit(f"kind must be one of {', '.join(KINDS)}, not '{spec['kind']}'")
    if spec.get("year") is not None and int(spec["year"]) not in YEARS:
        raise SystemExit(f"`year = {spec['year']}` is outside 1996-2001, so nothing would be kept")

    print(f"probing {spec['name']}: {spec['url']}")
    page = page_for(spec, OUT_DIR / f"{spec['name']}.source", args.refetch)

    stats: Counter = Counter()
    written: set[tuple[str, int]] = set()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{spec['name']}.jsonl"
    years: Counter = Counter()
    with out.open("w", encoding="utf-8") as fh:
        for ident, raw, date_text, whole in pairs_from(spec, page, stats):
            year = year_of(spec, date_text, stats)
            if year is None:
                continue
            domain = to_registrable(raw)
            if not domain:
                stats["refused_not_a_hostname"] += 1
                continue
            if (domain, year) in written:
                stats["duplicate"] += 1
                continue
            written.add((domain, year))
            years[year] += 1
            # `text` carries only the accepted hostname, so the pricer measures exactly
            # what was kept. The untouched row goes in `raw` for a human to check.
            fh.write(
                json.dumps(
                    {
                        "item": f"{spec['name']} {ident}",
                        "domain": domain,
                        "year": year,
                        "text": domain,
                        "raw": whole,
                        "url": spec["url"],
                    }
                )
                + "\n"
            )
            if args.limit and len(written) >= args.limit:
                stats["stopped_at_limit"] += 1
                break

    seen = stats["rows_seen"]
    kept = len(written)
    print(f"\n  rows seen        : {seen:,}")
    print(
        f"  accepted         : {kept:,} distinct (domain, year) over "
        f"{len({d for d, _ in written}):,} domains"
    )
    for reason, count in sorted(stats.items()):
        if reason.startswith("refused_") or reason == "duplicate":
            print(f"    {reason:30s} {count:,}")
    print(f"  by year          : {dict(sorted(years.items()))}")
    print(f"  wrote            : {out.relative_to(ROOT)}")
    if seen and kept / seen < 0.5:
        print(
            f"\n  KEPT {kept / seen:.1%} OF ROWS. Below half, the likely explanation is the spec "
            f"rather than the source:\n  check the column indices against the cached copy before "
            f"believing the price."
        )
    print(
        f"\n  next: just price --items {out.relative_to(ROOT)} --label {spec['name']}\n"
        f"  A probe cannot date a year: it has no ingest spec, by design (ADR-004). "
        f"If it prices well it earns a collector."
    )
    if not kept:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
