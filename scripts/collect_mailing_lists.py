"""Dated domain mentions in public pipermail mailing-list archives.

Every message carries its own `Date:` header, so a message dated 1999 naming
`foo.com` attests `foo.com` for 1999 in exactly the sense a dated Usenet post
does. The date is intrinsic to the artifact rather than recovered from a crawl,
and the archive is bulk-downloadable one month file at a time, so a whole host
costs about a thousand cheap HTTP requests and no archive.org budget at all.

Two hosts are wired, both GNU Mailman pipermail and both openly readable:
`mail.python.org/pipermail/` and `mail.gnome.org/archives/`. Most of the rest of
the family is not reachable: lists.debian.org publishes no per-month bulk file,
lists.samba.org answers 426, sourceware.org 403 and lore.kernel.org sits behind
an Anubis challenge.

Newsgroup-gatewayed lists are skipped, see SKIP_LISTS. Their messages are the
same messages the Usenet corpus already holds, so counting them here would let
one body of observation look like two lineages.

Takes the corroboration split like every free-text source: these addresses and
URLs were typed by people.

    uv run python scripts/collect_mailing_lists.py --harvest
    uv run python scripts/collect_mailing_lists.py --write
"""

import argparse
import gzip
import re
import sys
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from ark.canonical import to_registrable  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402
from ark.usenet import INFRASTRUCTURE, message_year  # noqa: E402

STORE = ROOT / "data/ark.duckdb"
OUT_DIR = ROOT / "data/raw/maillists"
YEARS = range(1996, 2002)

# host tag -> pipermail index URL. The tag becomes the on-disk directory.
HOSTS = {
    "python": "https://mail.python.org/pipermail/",
    "gnome": "https://mail.gnome.org/archives/",
}

# Lists bidirectionally gatewayed with a newsgroup. Their traffic is already in
# the Usenet corpus, so including them would double-count one observation and
# would make `mailing_list` look independent of `usenet` when it is not.
SKIP_LISTS = frozenset({"python-list", "python-announce-list"})

USER_AGENT = "ark-research/1.0 (internet history project; contact via repository)"
REQUEST_PAUSE = 0.15

_LIST_LINK = re.compile(r'href="(?:[^"]*/)?([a-z0-9._+-]+)/"')
_MONTH_FILE = re.compile(r'href="((?:19|20)\d\d-[A-Z][a-z]+\.txt(?:\.gz)?)"')
_DATE = re.compile(r"(?mi)^Date:[ \t]*(.+)")
# Anchored exactly as the Enron and Usenet address work: a local part, an `@`,
# and a host ending in a TLD the metric rewards. A generic dot rule over mail
# bodies fabricates domains out of sentence punctuation.
_ADDR = re.compile(
    r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.(?:com|net|org|edu|gov|uk|au|ca|de|fr|nl|jp))\b",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://([A-Za-z0-9.-]+)", re.IGNORECASE)


def fetch(url: str, timeout: int = 120) -> bytes:
    """One polite GET."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


def month_files(base: str, listname: str) -> list[str]:
    """The in-window per-month archive filenames a list publishes."""
    try:
        index = fetch(base + listname + "/").decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - a missing list index is not a run failure
        return []
    names = sorted(set(_MONTH_FILE.findall(index)))
    return [n for n in names if int(n[:4]) in YEARS]


def harvest(host: str, base: str) -> None:
    """Download every in-window month file of every list on one host."""
    target = OUT_DIR / host
    target.mkdir(parents=True, exist_ok=True)
    index = fetch(base).decode("utf-8", "replace")
    lists = sorted(set(_LIST_LINK.findall(index)) - SKIP_LISTS)
    print(f"{host}: {len(lists)} lists", flush=True)

    jobs: list[tuple[str, str]] = []
    with ThreadPoolExecutor(6) as pool:
        found = pool.map(lambda name: month_files(base, name), lists)
        for listname, months in zip(lists, found, strict=True):
            jobs.extend((listname, month) for month in months)
    print(f"{host}: {len(jobs)} in-window month files", flush=True)

    def one(job: tuple[str, str]) -> int:
        listname, month = job
        dest = target / f"{listname}__{month}"
        if dest.exists() and dest.stat().st_size:
            return 0
        try:
            body = fetch(base + listname + "/" + month)
        except Exception:  # noqa: BLE001 - one missing month must not end the run
            return -1
        dest.write_bytes(body)
        time.sleep(REQUEST_PAUSE)
        return len(body)

    started = time.time()
    with ThreadPoolExecutor(5) as pool:
        failed = sum(1 for result in pool.map(one, jobs) if result < 0)
    print(f"{host}: harvested in {time.time() - started:.0f}s, {failed} failed", flush=True)


def read_messages(path: Path) -> list[str]:
    """Split one pipermail month file into messages, gzipped or not."""
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except Exception:  # noqa: BLE001 - a truncated month file is skipped, not fatal
            return []
    return re.split(r"(?m)^From ", raw.decode("latin-1", "replace"))[1:]


def open_store(attempts: int = 60, pause: float = 15.0) -> duckdb.DuckDBPyConnection:
    """Open the store read-only, waiting out the maintain loop's write lock."""
    for attempt in range(attempts):
        try:
            return duckdb.connect(str(STORE), read_only=True)
        except duckdb.IOException:
            if attempt == attempts - 1:
                raise
            print(f"store is locked, waiting ({attempt + 1}/{attempts})", flush=True)
            time.sleep(pause)
    raise RuntimeError("unreachable")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harvest", action="store_true", help="download month files first")
    parser.add_argument("--write", action="store_true", help="write both journals")
    args = parser.parse_args()

    if args.harvest:
        for host, base in HOSTS.items():
            harvest(host, base)

    stats: Counter = Counter()
    pairs: dict[tuple[str, int], tuple[str, str]] = {}
    started = time.time()
    for host in HOSTS:
        directory = OUT_DIR / host
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            listname = path.name.split("__", 1)[0]
            if listname in SKIP_LISTS:
                stats["skipped_gatewayed"] += 1
                continue
            stats["files"] += 1
            for message in read_messages(path):
                stats["messages"] += 1
                header = _DATE.search(message[:4000])
                if not header:
                    stats["undated"] += 1
                    continue
                try:
                    year = message_year(header.group(1).strip())
                except Exception:  # noqa: BLE001 - a malformed Date is one lost message
                    stats["bad_date"] += 1
                    continue
                if year not in YEARS:
                    stats["out_of_window"] += 1
                    continue
                stats["in_window"] += 1
                for pattern in (_ADDR, _URL):
                    for raw_host in pattern.findall(message):
                        domain = to_registrable(raw_host)
                        if domain and domain not in INFRASTRUCTURE:
                            pairs.setdefault((domain, year), (host, path.name))

    print(f"read {stats['messages']:,} messages in {time.time() - started:.0f}s: {dict(stats)}")
    print(f"distinct in-window (domain, year): {len(pairs):,}")

    conn = open_store()
    try:
        attested = {
            r[0] for r in conn.execute("SELECT DISTINCT domain FROM domain_year").fetchall()
        }
        held = {
            (r[0], r[1])
            for r in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
    finally:
        conn.close()

    dated, candidates = [], []
    fresh = 0
    for (domain, year), (host, filename) in sorted(pairs.items()):
        listname, month = filename.split("__", 1)
        record = {
            "domain": domain,
            "year": year,
            "message_id": f"{host}/{listname}/{month}",
            "group": listname,
            "url": HOSTS[host] + listname + "/" + month,
        }
        if domain in attested:
            dated.append(record)
            fresh += (domain, year) not in held
        else:
            candidates.append(record)
    print(f"  corroborated -> dated_directory : {len(dated):,}, of which {fresh:,} net-new")
    print(f"  seen only here -> candidates    : {len(candidates):,}")
    if not args.write:
        print("\ndry run; pass --write to create both journals")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, batch in (("maillist_dated", dated), ("maillist_candidates", candidates)):
        path = OUT_DIR / f"{name}.jsonl.gz"
        with journal_writer(path) as handle:
            for record in batch:
                write_journal_line(handle, record)
        print(f"wrote {path} ({len(batch):,} records)")


if __name__ == "__main__":
    main()
