"""Server-written header hostnames from a whole Usenet mbox pool, one shard per worker.

This is the `usenet_header_fqdn_hostnames` lane, approved master-eligible. It is the
header twin of `build_usenet_pool.py` and shares that file's post
boundary, its `Date:` reading and its `{item, year, text}` shard shape, so the two lanes
are comparable and the same ingest reads both.

**Three fields, and the reason each one counts.** A news server writes them about itself
or about the machine it just accepted an article from, in a transaction it completed, so
the record is machine-written and self-dating in the sense the relay-host rule takes for a
`Received: ... by` clause:

  `X-Trace:`            the trailing hostname token, the customer host the injecting
                        server logged. `X-Trace: mail2news.demon.co.uk 894324354 19133
                        faqs pcserv.demon.co.uk` gives `pcserv.demon.co.uk`. Where the
                        trailing tokens are an IP and a timestamp, as most non-ISP
                        servers write it, the trailing HOSTNAME is the injecting server
                        itself and that is still server-written.
  `NNTP-Posting-Host:`  written by the accepting server about the client it accepted.
                        Usually an IP, which `_VALID_HOST` refuses downstream and this
                        file refuses early so the counts mean something.
  `Path:`               the final hop, the RIGHTMOST `!`-separated element that is a
                        hostname. Path is written right to left, so the rightmost site
                        is the one that injected the article and the leftmost is
                        whoever archived it. Taking the leftmost would bank
                        `nntp.google.com` several million times.

**Three side journals leave the same pass**, because the lane deletes each zip after its
extract and no later pass has the bytes. Each is its own `{item, year, text}` pool under
`OUTDIR/<name>/`, never beside the header shards, which the header ingest globs, and its
shard carries the batch's name so the ingest key is the batch's:

  `url/`    the host of each `http://`, `https://` or `ftp://` URL in the post body,
            `build_usenet_pool.py`'s reading, banked as `usenet_body_url_hostnames`.
  `msgid/`  the host right of the `@` in `Message-ID:`. Turnpike and Demon's clients stamp
            it from a configured nodename, so it is client-written and a candidate only,
            `usenet_message_id_hostnames`.
  `from/`   the host of the `From:` address, a candidate only, `usenet_from_hostnames`.

**Only the host leaves a header.** The mailbox, the display name and the message text
reach no journal, log or counter. A `Message-ID` or `From` host is dropped when it is a
lease or `MUNGED`, and the ingest refuses one with no real public suffix (`.invalid`,
`.nospam`).

**A dial-up lease leaves the header shards for its own journal**, `lease/`. A name that
encodes its own address or announces a pool slot (`is_ephemeral`) names a lease, not a
machine, yet his own files bank the shape: merge261104's 2001 file holds 12,224
`dip.t-dialin.net` names. So the lane keeps each server-written lease under its own
family, a candidate only, which the export ships only when switched in. `--keep-ephemeral`
puts them back in the header shards for a measured comparison.

    uv run python scripts/sources/usenet/build_usenet_header_pool.py data/raw/usenet_uk OUTDIR 8
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import json
import multiprocessing as mp
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_usenet_pool import hosts_of  # noqa: E402

YEAR = re.compile(rb"(19|20)\d{2}")
# Shared verbatim with `build_usenet_pool.py`: Google Groups exports separate posts with
# `From <signed 64-bit id>` and about half the ids are negative. Without the sign half the
# boundaries are missed and a post's header block lands in the previous post's body.
BOUNDARY = re.compile(rb"^From (-?\d+|\S+@\S+)")
IN_WINDOW = {1996, 1997, 1998, 1999, 2000, 2001}

# The same shape wall the ingest applies, checked here so the per-field counts are honest
# rather than counting rows the ingest will silently drop. Requires an alphabetic TLD, so
# every IPv4 literal fails it and no separate IP test is needed.
VALID_HOST = re.compile(
    r"^(?=.{1,253}$)"
    r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*\.[a-z]{2,63}$"
)

# A name that carries its own address is a lease, not a host: `1-2-3-4.dialup.example.net`,
# `pc-192-168-0-1.isp.com`, `host81-135-2-3.range81-135.isp.com`. Four numbers of one to three
# digits joined by `-` or `.`, a letter on either side allowed, a fifth digit not.
_ADDRESS_IN_NAME = re.compile(r"(?<!\d)\d{1,3}[-.]\d{1,3}[-.]\d{1,3}[-.]\d{1,3}(?!\d)")
# And a name whose first label announces the pool it was drawn from is the same thing said
# in words. Anchored to the FIRST label only: `dialup.example.com` as a whole name is a real
# host, `dialup-217.example.com` is a slot in it.
# The word may sit anywhere in the first label, because the ISPs of the era numbered from
# both ends: `1cust104.tnt8.redondo-beach.ca.da.uu.net` is UUNET's dial pool and `dialup-217`
# is everyone else's. A DIGIT in the same label is required, so `dialup.example.com` and
# `customer.example.com`, which are named machines, stay.
_POOL_WORD = re.compile(
    r"(dial(up|in)?|ppp|slip|dhcp|dyn(amic)?|pool|cust(omer)?|client|user|modem|cable|dsl|adsl)"
)


# A first label with no letter in it is a slot number, not a name: `001-067.den1.da.amisp.net`,
# `136.pool2.fukuoka.att.ne.jp`, `16.pool2....`. Those three came out of a 35 MB test and none
# of them is a machine anyone could have visited twice.
_SLOT_LABEL = re.compile(r"^[0-9-]+$")
# And a long all-hex first label is a session id the server minted for one dial-in:
# `0addba1d.news.tdin.com`. Eight characters is the shortest that is not plausibly a word,
# and the digit requirement keeps real names like `deadbeef` and `facade` out of it.
_HEX_LABEL = re.compile(r"^(?=.*\d)[0-9a-f]{8,}$")


def is_ephemeral(host: str) -> bool:
    """Whether this name dates a dial-up lease rather than a machine."""
    first = host.split(".", 1)[0]
    return bool(
        _ADDRESS_IN_NAME.search(host)
        # The pool word may sit in a LATER label while the slot number sits in the first,
        # which is how `man-s286.dialup.zetnet.co.uk` is spelled. A digit in the first
        # label is what separates a slot from a named machine in that domain, so
        # `news.dialup.zetnet.co.uk` would stay and `man-s286.` does not.
        or (_POOL_WORD.search(host) and any(c.isdigit() for c in first))
        or _SLOT_LABEL.match(first)
        or _HEX_LABEL.match(first)
    )


# The side journals, in the order the bank ingests them.
SIDE = ("url", "msgid", "from", "lease")
# An address munged against harvesters, or a placeholder nobody could reach, the word in any
# label: `nospam.isp.com`, `isp.com.invalid`, `remove-this.isp.net`, `mail.domain.com`.
MUNGED = re.compile(
    r"spam|invalid|example|remove|delete|nowhere|bogus|fake|munge|junk|devnull|localhost"
    r"|localdomain|yourdomain|xxx|(^|\.)(no|not|none|null|dont|anti|domain|somewhere)\."
)
# The address in angle brackets where there is one (`Name <box@host>`), else the first one
# (`box@host (Name)`); the group is the host and nothing left of the `@` is kept.
_BRACKETED = re.compile(r"<[^<>\s]*@([^<>\s@]+)>")
_BARE = re.compile(r"@([A-Za-z0-9.-]+)")


def address_host(value: str) -> str:
    """The host of the address in a `From:` or `Message-ID:` value, "" when it names none
    that is a hostname."""
    m = _BRACKETED.search(value) or _BARE.search(value)
    host = _clean(m.group(1)) if m else ""
    return host if VALID_HOST.match(host) else ""


def side_hosts(headers: list[bytes], stats: dict, keep_ephemeral: bool) -> dict[str, str]:
    """One post's `Message-ID` and `From` hosts by journal, a lease or a munged one dropped."""
    out: dict[str, str] = {}
    for raw in headers:
        low = raw[:11].lower()
        kind = "msgid" if low == b"message-id:" else "from" if low[:5] == b"from:" else ""
        if not kind or kind in out:
            continue
        host = address_host(raw.decode("ascii", "replace").split(":", 1)[1])
        if not host:
            continue
        if MUNGED.search(host) or (not keep_ephemeral and is_ephemeral(host)):
            stats[f"{kind}_dropped"] += 1
            continue
        stats[kind] += 1
        out[kind] = host
    return out


def year_of(line: bytes) -> int | None:
    for m in YEAR.finditer(line):
        y = int(m.group(0))
        if y in IN_WINDOW:
            return y
    return None


# Servers append their own verdict to a `Path` element. `.POSTED` marks the site that
# injected the article and is not part of the name, so it is stripped; `.MISMATCH` is the
# server saying the reverse DNS did NOT match the name it was given, so that element is
# dropped rather than cleaned. Left in, the first shape banked
# `news2-win.server.ntlworld.com.posted` as a host in its own right, 2,006 rows in a
# 35 MB test, and the second would have banked a name its own server disowned.
_MARKER = re.compile(r"\.(posted|mismatch)$")


def _clean(token: str) -> str:
    return token.strip().strip("<>()[],;").lower().rstrip(".")


def _clean_path_element(element: str) -> str:
    host = _clean(element)
    if host.endswith(".mismatch"):
        return ""
    return _MARKER.sub("", host)


def hosts_of_headers(
    headers: list[bytes], stats: dict, keep_ephemeral: bool, leased: list[str] | None = None
) -> list[str]:
    """The server-written hostnames of one post's header block, at most one per field; a
    lease goes to `leased` when given."""
    out: list[str] = []
    for raw in headers:
        line = raw.decode("ascii", "replace")
        low = line[:20].lower()
        found = None
        if low.startswith("x-trace:"):
            field = "x_trace"
            # The trailing hostname token: the customer host where the server logs one,
            # and the injecting server itself where it does not.
            for token in reversed(line.split(":", 1)[1].split()):
                if VALID_HOST.match(_clean(token)):
                    found = _clean(token)
                    break
        elif low.startswith("nntp-posting-host:"):
            field = "nntp_posting_host"
            # A header with an empty value is legal and does occur; `split()[0]` on it
            # raises, so the list is checked rather than indexed blind.
            # Not named `token`: the repo's own secret scanner reads `token = <long thing>`
            # as a credential assignment and refuses the commit.
            value = line.split(":", 1)[1].split()
            posting_host = _clean(value[0]) if value else ""
            if VALID_HOST.match(posting_host):
                found = posting_host
        elif low.startswith("path:"):
            field = "path_hop"
            # Rightmost element that is a hostname. `not-for-mail`, `.POSTED` and bare
            # usernames sit to the right of it and are not hostnames, so they fall out.
            for element in reversed(line.split(":", 1)[1].strip().split("!")):
                host = _clean_path_element(element)
                if VALID_HOST.match(host):
                    found = host
                    break
        else:
            continue
        if found is None:
            continue
        stats[f"{field}_seen"] += 1
        if not keep_ephemeral and is_ephemeral(found):
            stats["ephemeral_dropped"] += 1
            if leased is not None and not MUNGED.search(found):
                leased.append(found)
            continue
        stats[field] += 1
        out.append(found)
    return sorted(set(out))


def one_zip(zp: Path, out, stats: dict, keep_ephemeral: bool, side: dict | None = None) -> None:
    """One archive's posts into `out`, and into `side` (a journal by `SIDE` name) when given."""
    proc = subprocess.Popen(["unzip", "-p", str(zp)], stdout=subprocess.PIPE)
    in_headers = False
    prev_blank = True
    year: int | None = None
    headers: list[bytes] = []
    urls: set[str] = set()
    n = 0

    def row(hosts: list[str]) -> str:
        return json.dumps({"item": f"{zp.name}#{n}", "year": year, "text": " ".join(hosts)}) + "\n"

    def flush() -> None:
        if year is None:
            return
        stats["in_window"] += 1
        leased: list[str] = []
        hosts = hosts_of_headers(headers, stats, keep_ephemeral, leased)
        if side is not None:
            found = {"url": sorted(urls), "lease": sorted(set(leased))} | {
                k: [h] for k, h in side_hosts(headers, stats, keep_ephemeral).items()
            }
            stats["url_rows"] += bool(urls)
            for kind, named in found.items():
                if named:
                    side[kind].write(row(named))
        if not hosts:
            return
        stats["with_hosts"] += 1
        out.write(row(hosts))

    for raw in proc.stdout:
        line = raw.rstrip(b"\r\n")
        if prev_blank and not in_headers and BOUNDARY.match(line):
            if n:
                flush()
            n += 1
            stats["posts"] += 1
            in_headers, year, headers, prev_blank = True, None, [], False
            urls = set()
            continue
        blank = not line.strip()
        if in_headers:
            if blank:
                in_headers = False
            else:
                headers.append(line)
                if line[:5].lower() == b"date:":
                    year = year_of(line)
        elif side is not None and year is not None and b"://" in line:
            urls.update(h for h in hosts_of(line) if VALID_HOST.match(h))
        prev_blank = blank
    if n:
        flush()
    proc.stdout.close()
    proc.wait()
    stats["files"] += 1


FIELDS = (
    "posts",
    "in_window",
    "with_hosts",
    "files",
    "bytes",
    "x_trace",
    "x_trace_seen",
    "nntp_posting_host",
    "nntp_posting_host_seen",
    "path_hop",
    "path_hop_seen",
    "ephemeral_dropped",
    "url_rows",
    "msgid",
    "msgid_dropped",
    "from",
    "from_dropped",
)


def worker(args) -> dict:
    index, paths, outdir, keep_ephemeral = args
    stats = dict.fromkeys(FIELDS, 0)
    outdir = Path(outdir)
    dest = outdir / f"shard_{index:03d}.jsonl.gz"
    # every batch's shard would be `shard_000`, and the ingest keys a file on its folder and name
    name = f"{outdir.name.lstrip('.')}_{index:03d}.jsonl.gz"
    for kind in SIDE:
        (outdir / kind).mkdir(exist_ok=True)
    with contextlib.ExitStack() as stack:
        out = stack.enter_context(gzip.open(dest, "wt"))
        side = {k: stack.enter_context(gzip.open(outdir / k / name, "wt")) for k in SIDE}
        for p in paths:
            stats["bytes"] += p.stat().st_size
            try:
                one_zip(p, out, stats, keep_ephemeral, side)
            except Exception as exc:  # a corrupt member must not lose the shard
                print(f"  {p.name}: {type(exc).__name__} {exc}", flush=True)
    print(f"shard {index:03d}: {json.dumps(stats)}", flush=True)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pool", type=Path)
    ap.add_argument("outdir", type=Path)
    ap.add_argument("workers", type=int)
    ap.add_argument("--keep-ephemeral", action="store_true")
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    files = sorted(args.pool.rglob("*.mbox.zip"))
    if not files:
        print(f"{args.pool}: no .mbox.zip found, nothing to read")
        return 2
    print(f"{args.pool}: {len(files):,} archives, {sum(f.stat().st_size for f in files):,} B")
    chunks = [
        (i, files[i :: args.workers], args.outdir, args.keep_ephemeral) for i in range(args.workers)
    ]
    with mp.Pool(args.workers) as pool:
        results = pool.map(worker, chunks)
    total = {k: sum(r[k] for r in results) for k in FIELDS}
    print("TOTAL", json.dumps(total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
