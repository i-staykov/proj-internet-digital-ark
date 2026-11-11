"""One row per linked host and year from a WAT file, the Archive's own link extract of an ARC file.

    gzip -dc PART_arc.wat.gz | python3 scripts/sources/web_reports/wat_links.py out.jsonl.gz

A WAT record is the metadata of one capture: its URL, its 14-digit date, the ARC file and the
offset it sits at, and the links its HTML holds. Kept: a hyperlink (`A@/href`, `AREA@/href`)
with an absolute http or https URL to another host, from a capture of 1996 to 2013 that
answered 2xx. A row is the earliest such capture of a year for the linked host, `{host, year,
url, timestamp, file, offset, length, link}`, so the link reopens as that byte range of that
ARC file. Hosts without a dot or with a numeric last label are dropped.
"""

import gzip
import json
import re
import sys

HREF = ("A@/href", "AREA@/href")
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
            links = http["HTML-Metadata"]["Links"]
            status = http["Response-Message"]["Status"]
        except (ValueError, KeyError, TypeError):
            continue
        stamp, page = str(head.get("Date", "")), str(head.get("Target-URI", ""))
        if not ("1996" <= stamp[:4] <= "2013" and len(stamp) == 14 and status.startswith("2")):
            continue
        own = host_of(page)
        gz = record["Container"].get("Gzip-Metadata", {})
        length = sum(
            int(gz.get(k, 0)) for k in ("Header-Length", "Deflate-Length", "Footer-Length")
        )
        for link in links:
            url = str(link.get("url", "")).strip()
            if link.get("path") not in HREF or not url.lower().startswith(("http://", "https://")):
                continue
            host = host_of(url)
            if host == own or not NAME.match(host):
                continue
            key = (host, stamp[:4])
            if key not in best or stamp < best[key]["timestamp"]:
                best[key] = {
                    "host": host,
                    "year": stamp[:4],
                    "url": page,
                    "timestamp": stamp,
                    "file": record["Container"]["Filename"],
                    "offset": record["Container"]["Offset"],
                    "length": length,
                    "link": url,
                }
    for key in sorted(best):
        out.write(json.dumps(best[key]) + "\n")
    seen["kept"] = len(best)
    return seen


def main() -> int:
    sys.stdin.reconfigure(errors="replace")
    with gzip.open(sys.argv[1], "wt") as out:
        seen = reduce(sys.stdin, out)
    print(f"{seen['records']:,} records -> {seen['kept']:,} linked host-years", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
