"""Relay hostnames from `Received: ... by <host>` in mail.gnome.org pipermail month files.

The Apache/IETF relay-host lane at a third host: same `by`-clause rule, same parser
(imported from build_apache_header_pool.py), same {item, year, text} shard shape.
A message's own Date: year must equal the year of the month file it is filed under,
else it is dropped. Item: gnome/<list>__<YYYY-Month>.txt#<n>, n = nth mbox message.
Month files are read off the socket, never kept. One connection, a pause per request.

    uv run python scripts/sources/mail_corpora/collect_gnome_header.py data/raw/gnome_header_items

`ark ingest-gnome-header-hostnames` reads the shard. Resumable: `swept.txt` names each done file.
"""

import gzip
import importlib.util
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = Path(sys.argv[1])
sys.path.insert(0, str(REPO / "src"))
from ark.usenet import message_year  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "ap", REPO / "scripts/sources/mail_corpora/build_apache_header_pool.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
BOUNDARY, unfold, by_hosts, IN_WINDOW = _mod.BOUNDARY, _mod.unfold, _mod.by_hosts, _mod.IN_WINDOW

BASE = "https://mail.gnome.org/archives/"
UA = "ark-research/1.0 (internet history project; contact via repository)"
PAUSE = 0.4
LIST_LINK = re.compile(r'href="([a-z0-9][a-z0-9._+-]*)/"')
MONTH_FILE = re.compile(r'href="((199[6-9]|200[01])-([A-Z][a-z]+)\.txt\.gz)"')


def get(url: str) -> bytes | None:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            time.sleep(PAUSE)
            return data
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            if code == 404:
                return None
            time.sleep(5 * (attempt + 1) ** 2)
    return None


def rows(text: str, stem: str, part_year: int, st: dict):
    header: list[str] = []
    in_h = False
    idx = 0

    def flush():
        if not header:
            return None
        block = unfold(header)
        year = None
        for line in block.split("\n"):
            if line[:5].lower() == "date:":
                year = message_year(line.split(":", 1)[1])
                break
        if year is None:
            st["undated"] += 1
            return None
        if year not in IN_WINDOW:
            st["out_of_window"] += 1
            return None
        if year != part_year:
            st["year_disagrees"] += 1
            return None
        hosts = by_hosts(block)
        if not hosts:
            st["no_by_host"] += 1
            return None
        st["with_hosts"] += 1
        return {"item": f"{stem}#{idx}", "year": year, "text": " ".join(sorted(set(hosts)))}

    for raw in io.StringIO(text):
        line = raw.rstrip("\r\n")
        if not in_h and BOUNDARY.match(line):
            if idx:
                r = flush()
                if r:
                    yield r
            idx += 1
            st["messages"] += 1
            in_h, header = True, []
            continue
        if in_h:
            if not line.strip():
                in_h = False
            else:
                header.append(line)
    if idx:
        r = flush()
        if r:
            yield r


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    done_path = OUT / "swept.txt"
    done = set(done_path.read_text().split()) if done_path.exists() else set()
    st = dict.fromkeys(
        [
            "files",
            "messages",
            "undated",
            "out_of_window",
            "year_disagrees",
            "no_by_host",
            "with_hosts",
        ],
        0,
    )
    index = get(BASE)
    lists = sorted(set(LIST_LINK.findall(index.decode("utf-8", "replace"))))
    print(f"{len(lists)} lists", flush=True)
    shard = open(OUT / "gnome_received.jsonl", "a")
    with open(done_path, "a") as donef:
        for lst in lists:
            page = get(f"{BASE}{lst}/")
            if not page:
                continue
            months = sorted(set(MONTH_FILE.findall(page.decode("utf-8", "replace"))))
            for fname, year, month in months:
                stem = f"gnome/{lst}__{year}-{month}.txt"
                if stem in done:
                    continue
                data = get(f"{BASE}{lst}/{fname}")
                if data is None:
                    continue
                try:
                    text = gzip.decompress(data).decode("utf-8", "replace")
                except OSError:
                    text = data.decode("utf-8", "replace")
                for r in rows(text, stem, int(year), st):
                    shard.write(json.dumps(r) + "\n")
                shard.flush()
                st["files"] += 1
                donef.write(stem + "\n")
                donef.flush()
            print(lst, json.dumps(st), flush=True)
    (OUT / "stats.json").write_text(json.dumps(st, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
