"""One row per captured host and earlier year its own server dated a page to, from a WAT file.

    gzip -dc PART_arc.wat.gz | python3 scripts/sources/web_reports/wat_modified.py out.jsonl.gz

A WAT record keeps the response headers of its capture. Kept: a 2xx capture of 1996 to 2013
whose `Last-Modified` header names a year from 1996 on and before the capture's own. A row is
the earliest such capture for the host and that year, `{host, year, url, timestamp, file,
offset, length, modified}`, so the header reopens as that byte range of that ARC file. The
year is the server's word on its own page, a measure only: nothing banks from it.
"""

import gzip
import json
import re
import sys
from email.utils import parsedate

NAME = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]*[a-z0-9]$")


def host_of(url: str) -> str:
    rest = re.split("[/?#]", url.split("://", 1)[-1], maxsplit=1)[0]
    return rest.split("@")[-1].split(":", 1)[0].strip().lower().rstrip(".")


def reduce(lines, out) -> dict[str, int]:
    best: dict[tuple[str, str], dict] = {}
    seen = {"records": 0, "kept": 0}
    for line in lines:
        if not line.startswith('{"Container"'):
            continue
        seen["records"] += 1
        try:
            record = json.loads(line)
            head = record["Envelope"]["ARC-Header-Metadata"]
            http = record["Envelope"]["Payload-Metadata"]["HTTP-Response-Metadata"]
            status = http["Response-Message"]["Status"]
            headers = http.get("Headers") or {}
        except (ValueError, KeyError, TypeError):
            continue
        stamp, page = str(head.get("Date", "")), str(head.get("Target-URI", ""))
        if not ("1996" <= stamp[:4] <= "2013" and len(stamp) == 14 and status.startswith("2")):
            continue
        modified = next((str(v) for k, v in headers.items() if k.lower() == "last-modified"), "")
        when = parsedate(modified) if modified else None
        host = host_of(page)
        if not when or not NAME.match(host):
            continue
        year = when[0] + (1900 if when[0] < 100 else 0)
        if not 1996 <= year < int(stamp[:4]):
            continue
        key = (host, str(year))
        if key not in best or stamp < best[key]["timestamp"]:
            gz = record["Container"].get("Gzip-Metadata", {})
            best[key] = {
                "host": host,
                "year": str(year),
                "url": page,
                "timestamp": stamp,
                "file": record["Container"]["Filename"],
                "offset": record["Container"]["Offset"],
                "length": sum(
                    int(gz.get(k, 0)) for k in ("Header-Length", "Deflate-Length", "Footer-Length")
                ),
                "modified": modified,
            }
    for key in sorted(best):
        out.write(json.dumps(best[key]) + "\n")
    seen["kept"] = len(best)
    return seen


def main() -> int:
    sys.stdin.reconfigure(errors="replace")
    with gzip.open(sys.argv[1], "wt") as out:
        seen = reduce(sys.stdin, out)
    print(f"{seen['records']:,} records -> {seen['kept']:,} dated host-years", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
