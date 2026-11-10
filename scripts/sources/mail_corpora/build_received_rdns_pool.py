"""Reverse-DNS hosts from the `Received: from` clause of the list mail held on disk.

A receiving MTA that looks its peer up writes `from <helo> (<rdns.host> [<address>])`: the name
in the parentheses is the server's own lookup of the machine it accepted the message from, the
mail twin of a news server's `NNTP-Posting-Host`. Only that name is read. The HELO token is the
sender's word. A clause with an address alone, `unknown`, a name sendmail marks `(may be
forged)`, a private or loopback address and a local name date nothing. A dial-up lease (the
Usenet header lane's `is_ephemeral`) goes to `lease/shard_000.jsonl.gz`, its own family.

**What dates one item** is the line's own stamp, which the same server wrote after its last
`;`. A line whose year is not its month file's is dropped, as `build_apache_header_pool.py`
drops a message.

Reads `data/raw/apache_lists` and `data/raw/maillists` once into
`data/raw/received_rdns_items/shard_000.jsonl.gz`, the `{item, year, text}` rows `ark
ingest-received-rdns-hostnames` banks: the item is the message's pointer in its own lane, the
text its hosts, and no mailbox, name or message text is kept or logged. No request is made. The
tick starts it as its own user unit, `ark-received`, while `left()` is 1
(`scripts/harness/scheduled_sync.sh`).

    uv run python scripts/sources/mail_corpora/build_received_rdns_pool.py
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ark.usenet import message_year  # noqa: E402


def _script(rel: str):
    path = ROOT / "scripts/sources" / rel
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


apache = _script("mail_corpora/build_apache_header_pool.py")
maillist = _script("mail_corpora/build_maillist_pool.py")
is_ephemeral = _script("usenet/build_usenet_header_pool.py").is_ephemeral

APACHE, MAILLISTS = ROOT / "data/raw/apache_lists", ROOT / "data/raw/maillists"
SHARD = ROOT / "data/raw/received_rdns_items/shard_000.jsonl.gz"
LEASE = SHARD.parent / "lease" / SHARD.name
# `from <helo> (<ident>@<rdns> [<address>]`, the ident optional, then sendmail's own doubt.
RDNS = re.compile(
    r"^received:\s*from\s+\S+\s+\((?:[^\s()\[\]@]+@)?(" + apache._HOST + r")\.?\s+"
    r"\[(\d{1,3}(?:\.\d{1,3}){3})\]\s*(\(may be forged\))?",
    re.IGNORECASE,
)
PRIVATE = re.compile(r"^(?:10|127|192\.168|169\.254|172\.(?:1[6-9]|2\d|3[01]))\.")
LOCAL = frozenset(
    "local localdomain localnet lan internal intranet home corp priv private invalid".split()
)
PARTITION = re.compile(r"__(\d{4})-")


def rdns_hosts(
    header_block: str, partition_year: int, leased: list[str] | None = None
) -> list[str]:
    """The reverse-DNS host of every `Received: from` line of one UNFOLDED header block that
    its server stamped in the partition's year; a lease goes to `leased` when given."""
    out = []
    for line in header_block.split("\n"):
        match = RDNS.match(line)
        if match is None or match[3] or PRIVATE.match(match[2]):
            continue
        host = match[1].lower()
        if host.rsplit(".", 1)[1] in LOCAL or host.startswith("localhost."):
            continue
        if message_year(line.rsplit(";", 1)[1] if ";" in line else "") == partition_year:
            if not is_ephemeral(host):
                out.append(host)
            elif leased is not None:
                leased.append(host)
    return out


def headers(path: Path, lane: ModuleType) -> Iterator[str]:
    """Each message's unfolded header block, split as `lane` splits the file, so `#n` is the
    message its lane numbers n: the Apache lane reads text, the pipermail lane bytes, and a
    lone `\\r` or a Unicode space moves a boundary between the two."""
    block: list[str] | None = None
    in_headers = False
    opener = gzip.open if path.suffix == ".gz" else open
    text = isinstance(lane.BOUNDARY.pattern, str)
    mode = {"mode": "rt", "encoding": "utf-8", "errors": "replace"} if text else {"mode": "rb"}
    with opener(path, **mode) as fh:
        for raw in fh:
            line = raw.rstrip("\r\n" if text else b"\r\n")
            if not in_headers and lane.BOUNDARY.match(line):
                if block is not None:
                    yield apache.unfold(block)
                in_headers, block = True, []
            elif in_headers:
                if line.strip():
                    block.append(line if text else line.decode("utf-8", "replace"))
                else:
                    in_headers = False
    if block is not None:
        yield apache.unfold(block)


def month_files() -> list[tuple[Path, str, ModuleType]]:
    """Every month file with its lane's item stem and the lane: `<domain>/<list>__<YYYY-MM>`
    for an Apache mbox, `<host>/<list>__<YYYY-Month>.txt` for a pipermail file."""
    mboxes = sorted(APACHE.glob("*/*.mbox.gz"))
    files = [(p, f"{p.parent.name}/{p.name.removesuffix('.mbox.gz')}", apache) for p in mboxes]
    return files + [(p, maillist.item_stem(p), maillist) for p in maillist.month_files(MAILLISTS)]


def left() -> int:
    """1 while a corpus is here and its lease shard is not."""
    return int(not LEASE.exists() and (APACHE.is_dir() or MAILLISTS.is_dir()))


def main() -> int:
    if not left():
        print("received: nothing left to read", flush=True)
        return 0
    if subprocess.run(["bash", str(ROOT / "scripts/harness/hold.sh"), "holds"]).returncode == 0:
        print("received: held", flush=True)
        return 0
    stats: Counter[str] = Counter()
    LEASE.parent.mkdir(parents=True, exist_ok=True)
    # a shard already banked is not rewritten: only the leases are read again
    again = not SHARD.exists()
    partial, lease_partial = SHARD.with_name(".shard_000.tmp"), LEASE.with_name(".shard_000.tmp")
    with gzip.open(partial, "wt") as out, gzip.open(lease_partial, "wt") as lease_out:
        for path, stem, lane in month_files():
            year = PARTITION.search(path.name)
            if year is None:
                stats["bad_name"] += 1
                continue
            stats["files"] += 1
            try:
                for n, block in enumerate(headers(path, lane), 1):
                    stats["messages"] += 1
                    leased: list[str] = []
                    hosts = sorted(set(rdns_hosts(block, int(year[1]), leased)))
                    for sink, named in ((out, hosts), (lease_out, sorted(set(leased)))):
                        if named:
                            stats["with_hosts" if sink is out else "with_leases"] += 1
                            row = {
                                "item": f"{stem}#{n}",
                                "year": int(year[1]),
                                "text": " ".join(named),
                            }
                            sink.write(json.dumps(row) + "\n")
            except (OSError, EOFError) as exc:  # one cut month must not lose the shard
                stats["unreadable"] += 1
                print(f"received: {stem}: {type(exc).__name__}", flush=True)
    if again:
        partial.rename(SHARD)
    else:
        partial.unlink()
    lease_partial.rename(LEASE)
    print(f"received: {json.dumps(stats)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
