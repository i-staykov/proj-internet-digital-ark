"""Every group of an NNTP server (news.gmane.io by default) with its range and first
article year: the GROUPS file of `collect_nntp_header.py`. One connection, resumable.

    uv run python scripts/sources/mail_corpora/scan_nntp_groups.py OUT [SERVER]
"""

import email.utils
import json
import socket
import sys

OUT = sys.argv[1]
SERVER = sys.argv[2] if len(sys.argv) > 2 else "news.gmane.io"
sock = socket.create_connection((SERVER, 119), timeout=60)
f = sock.makefile("rwb")


def line() -> str:
    return f.readline().decode("latin1").rstrip("\r\n")


def cmd(c: str, multi: bool = False) -> list[str]:
    f.write((c + "\r\n").encode())
    f.flush()
    out = [line()]
    if multi and out[0][:1] == "2":
        while (row := line()) != ".":
            out.append(row)
    return out


def first_year(lo: int) -> int | None:
    for row in cmd(f"XOVER {lo}-{lo + 5}", True)[1:]:
        parts = row.split("\t")
        if len(parts) > 3:
            try:
                return email.utils.parsedate_to_datetime(parts[3]).year
            except (TypeError, ValueError):
                continue
    return None


line()
groups = [row.split()[0] for row in cmd("LIST ACTIVE", True)[1:]]
try:
    with open(OUT) as fh:
        done = {json.loads(row)["g"] for row in fh}
except FileNotFoundError:
    done = set()
with open(OUT, "a") as out:
    for g in groups:
        if g in done:
            continue
        r = cmd("GROUP " + g)[0].split()
        if r[0] != "211":
            out.write(json.dumps({"g": g, "err": r[0]}) + "\n")
            continue
        n, lo, hi = int(r[1]), int(r[2]), int(r[3])
        year = first_year(lo) if n else None
        out.write(json.dumps({"g": g, "n": n, "lo": lo, "hi": hi, "y": year}) + "\n")
        out.flush()
