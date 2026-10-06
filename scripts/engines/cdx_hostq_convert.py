"""Flatten the per-host CDX lane's `hostq_*` journals into `{url, timestamp, status}` capture
journals under `data/raw/cdx_suffix/`, where `ark ingest-hostnames` and
`cdx_suffix_convert.py` already read that shape.

**Same evidence, other shape.** A `hostq_*` line is one `matchType=host` answer,
`{host, status, captures: [{url, timestamp, status}]}`, already cut to 1996-2001 and 2xx or 3xx.
Each capture is emitted as it is: the ingest dates the host the capture was taken of, never the
host that was asked about, so the apex captures IA folds into a `www.` answer date the apex.

**Only answered hosts.** A line whose `status` is not 200 is a timeout or refusal and dates
nothing. A journal still open (`.part`) has no gzip end marker; everything before the cut is
read, and its output carries `_upto<stamp>` so the finished journal converts under its own name.
An output that exists is not rewritten.

    uv run python scripts/engines/cdx_hostq_convert.py data/raw/cdx_hostq/*.jsonl.gz
"""

import argparse
import json
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from ark.journal import open_journal_for_write  # noqa: E402


def read_lines(path: Path):
    """The journal's complete lines, tolerating a missing gzip end marker."""
    d = zlib.decompressobj(31)
    buf = b""
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            buf += d.decompress(chunk)
            *lines, buf = buf.split(b"\n")
            yield from lines


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("journals", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("data/raw/cdx_suffix"))
    args = ap.parse_args(argv)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    written = skipped = hosts = rows = 0
    for path in args.journals:
        name = path.name.removesuffix(".part").removesuffix(".jsonl.gz")
        if path.name.endswith(".part"):
            name += f"_upto{stamp}"
        dest = args.out / f"{name}.jsonl.gz"
        if dest.exists():
            skipped += 1
            continue
        part = dest.with_name(dest.name + ".tmp")
        with open_journal_for_write(part) as fh:
            for line in read_lines(path):
                rec = json.loads(line)
                if rec.get("status") != 200:
                    continue
                hosts += 1
                for c in rec.get("captures") or ():
                    fh.write(json.dumps({k: c[k] for k in ("url", "timestamp", "status")}) + "\n")
                    rows += 1
        part.rename(dest)
        written += 1
    print(f"{written} written, {skipped} converted before; {hosts:,} answered hosts, {rows:,} rows")


if __name__ == "__main__":
    main()
