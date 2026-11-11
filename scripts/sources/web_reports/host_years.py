"""A capture index on stdin reduced to one capture per host and year, for runner-grep's `reduce`.

A whole index names each host thousands of times and the record is (host, year), so of each
host's captures answered 2xx or 3xx in one year only the earliest is kept, a 2xx before a 3xx:
a `{url, timestamp, status}` journal row, the form the hostname ingest and the extended export
read. Rows are classic CDX (the ` CDX N b a m s ...` legend places stamp, URL and status;
without one they are fields 2, 3 and 5) or CDXJ (`key stamp {json}`), whose row keeps its
`filename`, `offset` and `length`: where no Wayback replays the capture, they locate it. The
host is the URL's, never the key's: a SURT key drops `www`. An index is sorted by key, so a
host's rows lie together and memory holds one key's hosts; an unsorted one only repeats rows.
Stdlib only.

    gzip -dc index.cdx.gz | python3 scripts/sources/web_reports/host_years.py out.jsonl.gz
"""

from __future__ import annotations

import gzip
import json
import re
import sys

YEARS = {str(y) for y in range(1996, 2014)}
_JSON_URL = re.compile(r'"url": ?"([^"]+)"')
_JSON_STATUS = re.compile(r'"status": ?"(\d{3})"')
_JSON_WHERE = re.compile(r'"(filename|offset|length)": ?"([^"]+)"')


def host_of(url: str) -> str:
    rest = url.split("://", 1)[-1]
    return rest.split("/", 1)[0].split("@")[-1].split(":", 1)[0].strip().lower().rstrip(".")


def reduce(lines, out) -> dict[str, int]:
    """Write the kept rows of `lines` to `out`; the counts of what was read and kept."""
    ts_at, url_at, status_at = 1, 2, 4
    group, best = None, {}
    seen = {"rows": 0, "kept": 0}

    def flush() -> None:
        for (_host, _year), (_rank, ts, url, status, where) in sorted(best.items()):
            row = {"url": url, "timestamp": ts, "status": status, **where}
            out.write(json.dumps(row) + "\n")
        seen["kept"] += len(best)
        best.clear()

    for line in lines:
        if line.startswith((" CDX", "CDX")):
            legend = line.split()[1:]
            if {"b", "a", "s"} <= set(legend):
                ts_at, url_at, status_at = legend.index("b"), legend.index("a"), legend.index("s")
            continue
        seen["rows"] += 1
        where = {}
        fields = line.split()
        if len(fields) > 2 and fields[2].startswith("{"):
            blob = line.split(" ", 2)[2]
            url, status = _JSON_URL.search(blob), _JSON_STATUS.search(blob)
            if not url or not status:
                continue
            ts, url, status = fields[1], url.group(1), status.group(1)
            where = dict(_JSON_WHERE.findall(blob))
        elif len(fields) > max(ts_at, url_at, status_at):
            ts, url, status = fields[ts_at], fields[url_at], fields[status_at]
        else:
            continue
        if len(ts) != 14 or ts[:4] not in YEARS or status[:1] not in "23" or len(status) != 3:
            continue
        key = fields[0].split(")", 1)[0].split("/", 1)[0]
        if key != group:
            flush()
            group = key
        host = host_of(url)
        if "." not in host or host.rsplit(".", 1)[-1].isdigit():
            continue
        at = (host, ts[:4])
        cand = (0 if status[0] == "2" else 1, ts, url, status, where)
        if at not in best or cand[:2] < best[at][:2]:
            best[at] = cand
    flush()
    return seen


def main() -> int:
    sys.stdin.reconfigure(errors="replace")
    with gzip.open(sys.argv[1], "wt") as out:
        seen = reduce(sys.stdin, out)
    print(f"{seen['rows']:,} rows -> {seen['kept']:,} host-years", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
