"""Extract (host, sent year) rows from the Jeb Bush gubernatorial mail export.

The artifact is `https://archive.org/download/JebBushEmails/JebBushEmails-Text.7z`,
411,928,998 bytes, sha256 `821e796f7d9dcd0a5bcb08eaf70760d50f5296481f2175ac4ed45b3301f41f75`,
one solid LZMA block holding 626 text files. Only the 154 named `1999*`, `2000*` and `2001*`
matter: they carry 504,439 of the 505,927 in-window messages.

**What dates a message.** Its own unindented `Sent:` line, written by the sending mail
client into the export. A message block starts at a line beginning `From:` and runs to the
next one; the `Sent:` line is read out of the first twelve lines of the block, and a block
whose year is not 1996-2001 is dropped whole.

**Why the host is anchored.** `Candace Rice.To tell the truth` becomes `rice.to` under any
wide hostname pattern, and `.to`, `.st`, `.it` and `.you` all carry English weights, so a
missing space after a full stop manufactures a scoring domain out of prose. Measured cost of
the wide reading over this corpus: 200.8 EE and 400 pairs, 5.4%, and it inflates the
high-weight TLDs preferentially. So a host counts only with an `@` in front of it, a scheme,
or a `www.` label.

**Only the host is kept, never the mailbox.** These are public records naming private
citizens, and the local part of an address is of no use to the score. `ADDR` captures the
domain group alone and the local part is never written to a journal.

Five journals are written, one per field plus their union, because "which field pays" was
the question the family closed on: `From:` 1,235.4 EE against `To:`/`Cc:` 1,410.3 EE, the
inbound-public hypothesis refuted with the sign reversed. `anchored_all` is the union and
the one `scripts/sources/mail_corpora/split_jeb_mail.py` reads.

    7z x JebBushEmails-Text.7z -o<dir> 'Redacted/*'
    uv run python scripts/sources/mail_corpora/parse_jeb_mail.py \\
        --out-prefix data/raw/jeb_bush/jeb_bush <dir>/Redacted/*.txt
"""

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

_MONTHS = (
    "January February March April May June July August September October November December"
).split()
_SENT = re.compile(
    r"^Sent:\s*(?:\w+,\s*)?(?:" + "|".join(_MONTHS) + r")\s+\d{1,2},\s*(\d{4})",
    re.IGNORECASE,
)
# Exports from other clients put the weekday or the day first; the year is still the
# only four-digit run on the line.
_SENT_ANY = re.compile(r"^Sent:.*?\b(\d{4})\b")
_HEADER = re.compile(r"^(From|Sent|To|Cc|CC|Bcc|Subject|Attachments|Importance):\s*(.*)$")

_HOST = r"((?:[A-Za-z0-9][A-Za-z0-9\-]{0,62}\.)+[A-Za-z]{2,24})"
# The capture group is the host, so the mailbox never leaves this module.
_ADDR = re.compile(r"[A-Za-z0-9._%+\-]+@" + _HOST)
_URL = re.compile(r"(?:https?://|ftp://|www\.)" + _HOST, re.IGNORECASE)

_WINDOW = range(1996, 2002)
_LANES = ("addr_from", "addr_tocc", "addr_body", "url_body", "anchored_all")


def anchored(text: str) -> set[str]:
    """Hosts an `@`, a scheme or a `www.` label vouches for, as raw hostnames."""
    return set(_ADDR.findall(text)) | set(_URL.findall(text))


def sent_year(block: list[str]) -> int | None:
    """The year on the block's own `Sent:` line, or None if it has none in window."""
    for line in block[:12]:
        found = _SENT.match(line) or _SENT_ANY.match(line)
        if found is not None:
            year = int(found.group(1))
            return year if year in _WINDOW else None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-prefix", required=True, help="path prefix for the five journals")
    parser.add_argument("files", nargs="+", help="extracted `Redacted/*.txt` message files")
    args = parser.parse_args()

    Path(args.out_prefix).parent.mkdir(parents=True, exist_ok=True)
    handles = {
        lane: gzip.open(f"{args.out_prefix}.{lane}.jsonl.gz", "wt", encoding="utf-8")
        for lane in _LANES
    }
    in_window = 0
    try:
        for name in args.files:
            path = Path(name)
            lines = path.read_text(encoding="utf-8", errors="replace").replace("\r", "").split("\n")
            starts = [i for i, line in enumerate(lines) if line.startswith("From:")]
            for index, start in enumerate(starts):
                stop = starts[index + 1] if index + 1 < len(starts) else len(lines)
                block = lines[start:stop]
                year = sent_year(block)
                if year is None:
                    continue
                in_window += 1
                header: dict[str, list[str]] = {}
                cursor = 0
                while cursor < len(block):
                    found = _HEADER.match(block[cursor])
                    if found is None:
                        break
                    header.setdefault(found.group(1).lower(), []).append(found.group(2))
                    cursor += 1
                body = "\n".join(block[cursor:])
                item = f"{path.name}#L{start + 1}"
                lanes = {
                    "addr_from": anchored(" ".join(header.get("from", []))),
                    "addr_tocc": anchored(
                        " ".join(v for k in ("to", "cc", "bcc") for v in header.get(k, []))
                    ),
                    "addr_body": set(_ADDR.findall(body)),
                    "url_body": set(_URL.findall(body)),
                }
                union: set[str] = set()
                for lane, hosts in lanes.items():
                    union |= hosts
                    if hosts:
                        write(handles[lane], item, year, hosts)
                if union:
                    write(handles["anchored_all"], item, year, union)
    finally:
        for handle in handles.values():
            handle.close()
    print(f"in-window messages {in_window:,}", file=sys.stderr)
    return 0


def write(handle, item: str, year: int, hosts: set[str]) -> None:
    """One journal line per message per lane, hosts sorted so a re-run is byte-identical."""
    handle.write(json.dumps({"item": item, "year": year, "text": " ".join(sorted(hosts))}) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
