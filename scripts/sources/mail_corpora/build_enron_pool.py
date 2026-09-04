"""Body URLs from the Enron mailbox release, one `{item, year, text}` shard for the whole tarball.

The third member of the body-URL family after `build_usenet_pool.py` and
`build_maillist_pool.py`, reading the CMU release `enron_mail_20150507.tar.gz` in one
streaming pass (no extraction, 443 MB on disk) and feeding `ark ingest-enron-hostnames`.
Same evidence question, same answer: only the host authority of an explicit `http://`,
`https://` or `ftp://` URL after the header block counts. `collect_enron.py` already banked
these messages at registrable grain; this keeps the host beneath the registrable.

    uv run python scripts/sources/mail_corpora/build_enron_pool.py \\
        data/raw/enron/enron_mail_20150507.tar.gz data/raw/enron_items

**What dates one item** is the message's own `Date:` header, written by the sending mail
client and kept by the release, parsed by `ark.usenet.message_year`. **The item is the
member's own path in the tarball**, `maildir/<custodian>/<folder>/<n>.`, one message per
member, so no boundary regex is needed and the pointer is exact.

The release carries no `Received:` chain: CMU regenerated it from PST files through JavaMail
and kept fifteen header fields, none of them transport. That is why the header arm of the
hypothesis measured 0 and this builder reads bodies only, like its two siblings.
"""

from __future__ import annotations

import gzip
import json
import re
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ark.usenet import message_year  # noqa: E402

# Case-insensitive on the scheme: Outlook-era mail carries `HTTP://` and `Http://` as typed.
URL = re.compile(rb"(?:https?|ftp)://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+", re.IGNORECASE)
IN_WINDOW = {1996, 1997, 1998, 1999, 2000, 2001}


def hosts_of(body: bytes) -> list[str]:
    out = []
    for m in URL.finditer(body):
        url = m.group(0).decode("ascii", "replace")
        host = url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0].strip().lower()
        if host and "." in host:
            out.append(host.rstrip("."))
    return out


def split_message(raw: bytes) -> tuple[list[bytes], bytes]:
    """Header lines and body, cut at the first blank line, either line ending."""
    for sep in (b"\r\n\r\n", b"\n\n"):
        head, found, body = raw.partition(sep)
        if found:
            return head.splitlines(), body
    return raw.splitlines(), b""


def year_of(headers: list[bytes]) -> int | None:
    for line in headers:
        if line[:5].lower() == b"date:":
            year = message_year(line[5:].decode("ascii", "replace").strip())
            return year if year in IN_WINDOW else None
    return None


def one_message(name: str, raw: bytes, out, stats: dict) -> None:
    stats["posts"] += 1
    headers, body = split_message(raw)
    year = year_of(headers)
    if year is None:
        return
    stats["in_window"] += 1
    hosts = hosts_of(body)
    if not hosts:
        return
    stats["with_urls"] += 1
    out.write(json.dumps({"item": name, "year": year, "text": " ".join(hosts)}) + "\n")


def build(tarball: Path, outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    stats = {"posts": 0, "in_window": 0, "with_urls": 0, "bytes": tarball.stat().st_size}
    started = time.time()
    with (
        gzip.open(outdir / "shard_000.jsonl.gz", "wt") as out,
        tarfile.open(tarball, "r|gz") as tar,
    ):
        for member in tar:
            if not member.isfile() or not member.name.startswith("maildir/"):
                continue
            fh = tar.extractfile(member)
            if fh is None:
                continue
            one_message(member.name, fh.read(), out, stats)
            if stats["posts"] % 100000 == 0:
                print(f"  {stats['posts']:,} messages, {time.time() - started:.0f}s", flush=True)
    return stats


def main() -> int:
    tarball, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    stats = build(tarball, outdir)
    print("TOTAL", json.dumps(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
