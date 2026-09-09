"""Relay hostnames from the `Received: ... by <host>` clause of dated Apache list messages.

Writes the `{item, year, text}` shards `ark ingest-apache-header-hostnames` reads, the same
shape `build_maillist_pool.py` and `build_usenet_pool.py` write.

    uv run python scripts/sources/mail_corpora/build_apache_header_pool.py \\
        data/raw/apache_lists data/raw/apache_header_items 8

**What dates one item** is the message's own `Date:` header, an RFC 822 date written by the
sending client and preserved verbatim by Ponymail, cross-checked against the `d=YYYY-MM`
partition the mbox was fetched under. A message whose `Date:` year disagrees with its partition
year is DROPPED rather than assigned to either: the GNOME lane measured that failure mode at
1 message in 64, a sender's clock set to the wrong year, and here the partition gives a second
opinion for free.

**Why only the `by` clause.** Ivo approved this class on 2026-09-09 for the `by` clause alone.
The receiving MTA writes its own name there, so the field is machine-written and self-dating,
which is why it takes no corroboration split. Three other fields in the same header are NOT
taken, each for its own reason:

- the `from` clause carries a HELO name the SENDER chose, so it is forgeable, and it is where
  the junk lives: one 1999 month yielded `blonville.caii`, `ecstasy.localnet` and bare IPs;
- the parenthesised reverse-DNS is written by the receiver but was not part of the approval,
  so it is left for a later ruling rather than taken quietly;
- `Message-ID` hosts are stamped by the client from a configured nodename, and the register
  already parks that as needing its own class reading.

**Four shapes in real `Received:` lines that a naive `by (\\S+)` gets wrong**, all four present
in `httpd/dev` 1999-01, with the parenthesised address swapped for an RFC 5737 documentation
one because a tracked file names no addresses:

    Received: (qmail 21311 invoked by uid 6000); 1 Jan 1999 19:30:10 -0000
    Received: from en by slarti with UUCP; 01 Jan 1999 19:30:26 -0000 (GMT)
    Received: from slarti.muc.de (192.0.2.10)
      by taz.hyperreal.org with SMTP; 1 Jan 1999 19:30:08 -0000
    Received: by en1.engelschall.com (Sendmail 8.9.1) for new-httpd@apache.org

qmail writes `invoked by uid 6000` and UUCP hops write a bare nodename, so a host token must
carry a dot to count. The third is the expensive one: its `by` clause sits on a FOLDED
continuation line, so headers must be unfolded before they are read or that hop is lost
silently. The fourth has no `from` clause at all.

The ingest applies the rest of the wall: `to_registrable` must resolve the name, a host that IS
its own registrable belongs to `domain_year` instead, and the parent must be held in the same
year. On the 1999-01 sample that wall admitted 127 of 129 net-new hosts and rejected exactly
the two malformed ones.
"""

from __future__ import annotations

import gzip
import json
import multiprocessing as mp
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ark.usenet import message_year  # noqa: E402

# A host token: labels of letters, digits and hyphens, at least one dot, no trailing dot.
_HOST = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+"
BY = re.compile(r"\bby\s+(" + _HOST + r")", re.IGNORECASE)
IP = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
# mbox message boundary. Ponymail writes `From MAILER-DAEMON <ctime>` and, for some months,
# the sender address instead, so the ctime tail is what identifies the line.
BOUNDARY = re.compile(
    r"^From \S.*\s[A-Z][a-z]{2} [A-Z][a-z]{2} +\d{1,2} \d{2}:\d{2}:\d{2} \d{4}\s*$"
)
IN_WINDOW = frozenset({1996, 1997, 1998, 1999, 2000, 2001})
STEM = re.compile(r"^(?P<list>.+)__(?P<month>\d{4}-\d{2})$")


def by_hosts(header_block: str) -> list[str]:
    """Every `by` host of every `Received:` line in one UNFOLDED header block."""
    out: list[str] = []
    for line in header_block.split("\n"):
        if not line[:9].lower().startswith("received:"):
            continue
        for match in BY.finditer(line):
            host = match.group(1).strip().rstrip(".").lower()
            # An IP literal names no domain, and `to_registrable` would refuse it anyway.
            if host and not IP.match(host):
                out.append(host)
    return out


def unfold(lines: list[str]) -> str:
    """RFC 822 unfolding: a line starting with space or tab continues the one before it."""
    return re.sub(r"\n[ \t]+", " ", "\n".join(lines))


def one_file(path: Path, out, stats: dict) -> None:
    """Read one `<list>__<YYYY-MM>.mbox.gz`, append its rows to an open shard."""
    match = STEM.match(path.name.replace(".mbox.gz", "").replace(".mbox", ""))
    if match is None:
        stats["bad_name"] += 1
        return
    partition_year = int(match["month"][:4])
    stem = f"{path.parent.name}/{path.name.replace('.mbox.gz', '').replace('.mbox', '')}"

    header: list[str] = []
    in_headers = False
    index = 0

    def flush() -> None:
        if not header:
            return
        block = unfold(header)
        year = None
        for line in block.split("\n"):
            if line[:5].lower() == "date:":
                year = message_year(line.split(":", 1)[1])
                break
        if year is None:
            stats["undated"] += 1
            return
        if year not in IN_WINDOW:
            stats["out_of_window"] += 1
            return
        if year != partition_year:
            # The archive filed it under a different year than its own Date: header claims.
            # One of the two is wrong and nothing here says which, so the message is dropped.
            stats["year_disagrees"] += 1
            return
        stats["in_window"] += 1
        hosts = by_hosts(block)
        if not hosts:
            stats["no_by_host"] += 1
            return
        stats["with_hosts"] += 1
        row = {"item": f"{stem}#{index}", "year": year, "text": " ".join(sorted(set(hosts)))}
        out.write(json.dumps(row) + "\n")

    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if not in_headers and BOUNDARY.match(line):
                if index:
                    flush()
                index += 1
                stats["messages"] += 1
                in_headers, header = True, []
                continue
            if in_headers:
                if not line.strip():
                    in_headers = False
                else:
                    header.append(line)
    if index:
        flush()
    stats["files"] += 1


def worker(args) -> dict:
    index, paths, outdir = args
    stats = {
        "files": 0,
        "messages": 0,
        "in_window": 0,
        "with_hosts": 0,
        "no_by_host": 0,
        "undated": 0,
        "out_of_window": 0,
        "year_disagrees": 0,
        "bad_name": 0,
    }
    dest = Path(outdir) / f"shard_{index:03d}.jsonl.gz"
    with gzip.open(dest, "wt") as out:
        for path in paths:
            try:
                one_file(path, out, stats)
            except Exception as exc:  # one corrupt month must not lose the shard
                print(f"  {path}: {type(exc).__name__} {exc}", flush=True)
    print(f"shard {index:03d}: {stats}", flush=True)
    return stats


def main() -> int:
    """`<pool root> <out dir> [workers] [done file]`.

    **The optional done file is what makes tranches safe.** The harvest runs for hours, so
    banking wants to happen in tranches rather than once at the end. But the ingest ledger
    keys on `<out dir>/<shard name>` plus a sha256, so a second build that re-read the first
    tranche's months would either recycle a shard name with different bytes, which the ledger
    refuses outright, or write a second evidence row for every host the first tranche already
    banked. Listing what has been read, and skipping it next time, avoids both: each tranche
    goes to its own out dir and reads only months no tranche has read. The `alt` lane paid for
    this lesson the hard way on 2026-09-08, see docs/lore/traps.md.
    """
    root, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    done_file = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    outdir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in root.glob("*/*.mbox.gz") if p.stat().st_size > 0)
    if done_file is not None and done_file.exists():
        already = set(done_file.read_text(encoding="utf-8").split())
        before = len(files)
        files = [p for p in files if f"{p.parent.name}/{p.name}" not in already]
        print(
            f"{done_file}: {len(already):,} list-months already read, {before - len(files)} skipped"
        )
    total = sum(p.stat().st_size for p in files)
    print(f"{root}: {len(files):,} list-months, {total:,} B to read")
    if not files:
        raise SystemExit("nothing new to read; every list-month on disk is in the done file")
    chunks = [(i, files[i::workers], outdir) for i in range(workers)]
    with mp.Pool(workers) as pool:
        results = pool.map(worker, chunks)
    merged = {key: sum(r[key] for r in results) for key in results[0]}
    print("TOTAL", json.dumps(merged))
    if done_file is not None:
        with done_file.open("a", encoding="utf-8") as fh:
            for path in files:
                fh.write(f"{path.parent.name}/{path.name}\n")
        print(f"{done_file}: {len(files):,} list-months appended")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
