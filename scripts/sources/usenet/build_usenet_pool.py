"""Body URLs from a whole Usenet mbox pool, in parallel, one shard per worker.

This is what produced the `usenet_body_url_hostnames` lane that `ark ingest-usenet-hostnames`
reads: thirteen pools, 224 GB of mbox text, 328.2M posts. The sample builders beside it read a
handful of archives serially; this reads every archive in a pool and each worker writes its own
`{item, year, text}` shard.

    uv run python scripts/sources/usenet/build_usenet_pool.py data/raw/usenet_uk OUTDIR 8

**Body only, and this is the whole evidence question.** A `Path`, `Xref`, `NNTP-Posting-Host`,
`Message-ID`, `From` or `Organization` host is a news relay or a mailbox, never a host that served
a page, so only an explicit `http://`, `https://` or `ftp://` URL after the header block counts. A
first pass that ignored the distinction was 81.45% wrong on a smaller corpus.

**The post boundary carries the sign.** Google Groups exports separate posts with
`From <signed 64-bit id>` and about half those ids are negative. Without `-?` in the pattern half
the boundaries are missed, and every unrecognised post's HEADER block lands in the previous post's
body, which put 14.02% of extracted hosts back into the corpus through the door the paragraph above
closes, `Organization:` alone accounting for 12.65%. The rule this leaves: when an extractor's
recall looks like a coin flip, suspect the record separator before the field parser.

The archives themselves are deleted after a pool is read, because archive.org serves them again by
name from `data/raw/usenet_catalog.json`, and the shards are a few hundred MB against 224 GB.
"""

from __future__ import annotations

import gzip
import json
import multiprocessing as mp
import re
import subprocess
import sys
from pathlib import Path

URL = re.compile(rb"(?:https?|ftp)://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
YEAR = re.compile(rb"(19|20)\d{2}")
# Google Groups exports separate posts with `From <signed 64-bit id>` and about half
# the ids are negative. Without the sign, half the boundaries are missed and every
# unrecognised post's header block lands in the previous post's body.
BOUNDARY = re.compile(rb"^From (-?\d+|\S+@\S+)")
IN_WINDOW = {1996, 1997, 1998, 1999, 2000, 2001}


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


def one_zip(zp: Path, out, stats: dict) -> None:
    proc = subprocess.Popen(["unzip", "-p", str(zp)], stdout=subprocess.PIPE)
    in_headers = False
    prev_blank = True
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
        row = {"item": f"{zp.name}#{n}", "year": year, "text": " ".join(hosts)}
        out.write(json.dumps(row) + "\n")

    for raw in proc.stdout:
        line = raw.rstrip(b"\r\n")
        if prev_blank and not in_headers and BOUNDARY.match(line):
            if n:
                flush()
            n += 1
            stats["posts"] += 1
            in_headers, year, body, prev_blank = True, None, [], False
            continue
        blank = not line.strip()
        if in_headers:
            if blank:
                in_headers = False
            elif line[:5].lower() == b"date:":
                year = year_of(line)
        else:
            body.append(line)
        prev_blank = blank
    if n:
        flush()
    proc.stdout.close()
    proc.wait()
    stats["files"] += 1


def worker(args) -> dict:
    index, paths, outdir = args
    stats = {"posts": 0, "in_window": 0, "with_urls": 0, "files": 0, "bytes": 0}
    dest = Path(outdir) / f"shard_{index:03d}.jsonl.gz"
    with gzip.open(dest, "wt") as out:
        for p in paths:
            stats["bytes"] += p.stat().st_size
            try:
                one_zip(p, out, stats)
            except Exception as exc:  # a corrupt member must not lose the shard
                print(f"  {p.name}: {type(exc).__name__} {exc}", flush=True)
    print(f"shard {index:03d}: {stats}", flush=True)
    return stats


def main() -> int:
    pool_dir, outdir, workers = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
    outdir.mkdir(parents=True, exist_ok=True)
    files = sorted(pool_dir.rglob("*.mbox.zip"))
    print(f"{pool_dir}: {len(files):,} archives, {sum(f.stat().st_size for f in files):,} B")
    chunks = [(i, files[i::workers], outdir) for i in range(workers)]
    with mp.Pool(workers) as pool:
        results = pool.map(worker, chunks)
    total = {k: sum(r[k] for r in results) for k in results[0]}
    print("TOTAL", json.dumps(total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
