"""Body URLs from the pipermail archives on disk, one `{item, year, text}` shard per worker.

The mailing-list twin of `scripts/sources/usenet/build_usenet_pool.py`, reading the 2,622
month files `collect_mailing_lists.py` fetched into `data/raw/maillists/<host>/` and feeding
`ark ingest-maillist-hostnames`. Same evidence question, same answer: only the host authority
of an explicit `http://`, `https://` or `ftp://` URL after the header block counts. A
`Received`, `Message-ID`, `From` or `List-*` host is a mail relay or a mailbox, never a host
that served a page.

    uv run python scripts/sources/mail_corpora/build_maillist_pool.py \
        data/raw/maillists data/raw/maillists_items 8

**What dates one item** is the message's own `Date:` header, written by the sending mail
client and preserved verbatim by Mailman. The item pointer is `<host>/<file>#<n>`, message
`n` of that month file, and the file is still served by name from the archive host.

**The message boundary is pipermail's `From <sender>  <ctime>` line.** Mailman writes the
sender either as `user@host` or, in the obfuscated `.txt` form, as `user at host`, and a
`From ` at the start of a body line is escaped to `>From `, so the boundary is safe to match
without a preceding blank line. The two newsgroup-gatewayed lists are skipped exactly as the
registrable collector skips them: their messages are the Usenet corpus again, and one body
of observation must not look like two lineages.

The month files stay on disk. They are 869 MB, and unlike the Usenet pools they are the
project's own copy of a host that sets a crawl delay.
"""

from __future__ import annotations

import gzip
import json
import multiprocessing as mp
import re
import sys
from pathlib import Path

URL = re.compile(rb"(?:https?|ftp)://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
YEAR = re.compile(rb"(19|20)\d{2}")
# The sender token varies (`user at host`, `user@host`, `Name <user@host>`, `user@host
# (Name)`), so the ctime tail is what identifies the line: no body sentence beginning
# `From ` ends in ` Fri Jun  1 13:49:11 2001`, and a real one would be escaped `>From `.
BOUNDARY = re.compile(
    rb"^From \S.*\s[A-Z][a-z]{2} [A-Z][a-z]{2} +\d{1,2} \d{2}:\d{2}:\d{2} \d{4}\s*$"
)
IN_WINDOW = {1996, 1997, 1998, 1999, 2000, 2001}
# Bidirectionally gatewayed with a newsgroup, so already in the Usenet lane.
SKIP_LISTS = frozenset({"python-list", "python-announce-list"})


def year_of(line: bytes) -> int | None:
    for m in YEAR.finditer(line):
        y = int(m.group(0))
        if y in IN_WINDOW:
            return y
    return None


def hosts_of(body: bytes) -> list[str]:
    out = []
    for m in URL.finditer(body):
        url = m.group(0).decode("ascii", "replace")
        host = url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0].strip().lower()
        if host and "." in host:
            out.append(host.rstrip("."))
    return out


def item_stem(path: Path) -> str:
    """`<host>/<list>__<YYYY-Month>.txt`, the same whether the file on disk is gzipped."""
    name = path.name[:-3] if path.name.endswith(".gz") else path.name
    return f"{path.parent.name}/{name}"


def one_file(path: Path, out, stats: dict) -> None:
    opener = gzip.open if path.suffix == ".gz" else open
    stem = item_stem(path)
    in_headers = False
    year = None
    body: list[bytes] = []
    n = 0

    def flush() -> None:
        if year is None:
            return
        stats["in_window"] += 1
        hosts = hosts_of(b"\n".join(body))
        if not hosts:
            return
        stats["with_urls"] += 1
        row = {"item": f"{stem}#{n}", "year": year, "text": " ".join(hosts)}
        out.write(json.dumps(row) + "\n")

    with opener(path, "rb") as fh:
        for raw in fh:
            line = raw.rstrip(b"\r\n")
            if not in_headers and BOUNDARY.match(line):
                if n:
                    flush()
                n += 1
                stats["posts"] += 1
                in_headers, year, body = True, None, []
                continue
            if in_headers:
                if not line.strip():
                    in_headers = False
                elif line[:5].lower() == b"date:":
                    year = year_of(line)
            else:
                body.append(line)
    if n:
        flush()
    stats["files"] += 1


def worker(args) -> dict:
    index, paths, outdir = args
    stats = {"posts": 0, "in_window": 0, "with_urls": 0, "files": 0, "bytes": 0}
    dest = Path(outdir) / f"shard_{index:03d}.jsonl.gz"
    with gzip.open(dest, "wt") as out:
        for p in paths:
            stats["bytes"] += p.stat().st_size
            try:
                one_file(p, out, stats)
            except Exception as exc:  # a corrupt file must not lose the shard
                print(f"  {p.name}: {type(exc).__name__} {exc}", flush=True)
    print(f"shard {index:03d}: {stats}", flush=True)
    return stats


def month_files(root: Path) -> list[Path]:
    files = []
    for p in sorted(root.glob("*/*.txt")) + sorted(root.glob("*/*.txt.gz")):
        if p.name.split("__", 1)[0] in SKIP_LISTS:
            continue
        files.append(p)
    return sorted(files)


def main() -> int:
    root, outdir, workers = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
    outdir.mkdir(parents=True, exist_ok=True)
    files = month_files(root)
    print(f"{root}: {len(files):,} month files, {sum(f.stat().st_size for f in files):,} B")
    chunks = [(i, files[i::workers], outdir) for i in range(workers)]
    with mp.Pool(workers) as pool:
        results = pool.map(worker, chunks)
    total = {k: sum(r[k] for r in results) for k in results[0]}
    print("TOTAL", json.dumps(total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
