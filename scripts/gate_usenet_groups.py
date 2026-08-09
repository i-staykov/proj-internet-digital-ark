"""Decide whether a Usenet group covers 1996-2001 before paying to download it.

**This gate barely fires, and that is the finding rather than a defect.** It is kept
because the negative result is worth more than the tool: it stops the next person
rebuilding it.

The plan was cheap. A `.mbox.zip` can be read from the front: the local file header
sits at offset 0 and the deflate stream after it inflates from its first byte, so one
HTTP range request for a quarter megabyte yields the opening messages of a 400 MB
archive. Mailboxes are written in posting order, so the opening messages date the
group's start, and a group starting after 2001 could be skipped unread. 54.8% of the
messages in the August sample are out of window and the waste is concentrated in
whole groups, so the prize was most of a 382 GB download.

**These archives are stored newest-first.** Measured, not assumed, and measured only
because the gate was validated against 48 groups whose true yield was already known:
it discarded 21 of them holding 88% of the sample's equivalent-English.
`comp.cad.autocad` opens on 2011 and 2012 and does not reach 2001 until 77.8% of the
way in. The front of the file dates the END of a group's life.

So the only thing a prefix can prove is that a group died before the window opened,
which is the rule implemented here and which rejected 1 group in 48. Knowing whether
an archive reaches BACK into 1996-2001 needs its tail, and a deflate stream cannot be
decompressed from the middle, so there is no cheap version of that question. Download
first and gate during the parse instead.

    uv run python scripts/gate_usenet_groups.py --from-file groups.txt --out keep.txt
    uv run python scripts/gate_usenet_groups.py --from-file groups.txt --report v.csv

Writes the groups worth downloading, one per line, ready for
`probe_usenet_groups.py --from-file`.
"""

import argparse
import csv
import re
import threading
import time
import urllib.error
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parsedate_to_datetime
from pathlib import Path

DOWNLOAD_BASE = "https://archive.org/download"
USER_AGENT = "internet-digital-ark research crawler (contact: ivaylo.staykov@taktile.com)"
FIRST, LAST = 1996, 2001
# 256 KB of compressed mbox is a few hundred messages, which is far more than the
# handful needed to date the start and cheap enough to spend on 15,000 groups.
WINDOW_BYTES = 1 << 18
DATE_LINE = re.compile(rb"^Date:\s*(.+?)\r?$", re.IGNORECASE | re.MULTILINE)


def url_for(group: str) -> str:
    return f"{DOWNLOAD_BASE}/usenet-{group.split('.', 1)[0]}/{group}.mbox.zip"


def head_bytes(group: str, timeout: float) -> bytes:
    request = urllib.request.Request(
        url_for(group),
        headers={"User-Agent": USER_AGENT, "Range": f"bytes=0-{WINDOW_BYTES - 1}"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(WINDOW_BYTES)


def inflate_prefix(blob: bytes) -> bytes:
    """Inflate as much of the first zip member as the prefix allows.

    Truncation is expected and is not an error: the point is to read the opening
    messages, not the archive. A stored (uncompressed) member is returned as-is.
    """
    if len(blob) < 30 or blob[:4] != b"PK\x03\x04":
        return b""
    method = int.from_bytes(blob[8:10], "little")
    name_len = int.from_bytes(blob[26:28], "little")
    extra_len = int.from_bytes(blob[28:30], "little")
    start = 30 + name_len + extra_len
    payload = blob[start:]
    if method == 0:
        return payload
    if method != 8:
        return b""
    try:
        # -15: a raw deflate stream, no zlib wrapper, which is what zip stores
        return zlib.decompressobj(-15).decompress(payload)
    except zlib.error:
        return b""


def years_in(text: bytes, limit: int = 400) -> list[int]:
    years: list[int] = []
    for match in DATE_LINE.finditer(text):
        raw = match.group(1).decode("latin-1", "replace").strip()
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            continue
        if parsed is not None and 1970 <= parsed.year <= 2030:
            years.append(parsed.year)
            if len(years) >= limit:
                break
    return years


def judge(group: str, timeout: float) -> dict:
    """Keep unless the archive's NEWEST messages already predate the window.

    These archives are stored newest-first, which is the opposite of what a mailbox
    usually is and the opposite of what the first version of this gate assumed. It
    was measured rather than guessed: `comp.cad.autocad` opens on 2011 and 2012 and
    does not reach 2001 until 77.8% of the way in, and reading only the front made
    the gate discard 21 of 48 sampled groups holding 88% of the sample's value.

    So the front of the file dates the END of the group's life, not its start, and
    the only thing it can prove is that a group died before the window opened. That
    is a narrow test and it fires rarely, which is the honest outcome: with this
    layout no cheap pre-download gate can tell whether an archive reaches BACK into
    1996-2001, because the deflate stream cannot be decompressed from the middle.
    """
    try:
        blob = head_bytes(group, timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        return {
            "group": group,
            "keep": True,
            "reason": f"unreadable ({type(exc).__name__})",
            "newest_year": "",
            "seen": 0,
        }
    years = years_in(inflate_prefix(blob))
    if not years:
        return {
            "group": group,
            "keep": True,
            "reason": "no dates in prefix",
            "newest_year": "",
            "seen": 0,
        }
    newest = max(years)
    if any(FIRST <= y <= LAST for y in years):
        return {
            "group": group,
            "keep": True,
            "reason": "in window at the head",
            "newest_year": newest,
            "seen": len(years),
        }
    if newest < FIRST:
        return {
            "group": group,
            "keep": False,
            "reason": f"ends {newest}, before {FIRST}",
            "newest_year": newest,
            "seen": len(years),
        }
    # Newest is after the window. Because the file runs backwards, the in-window
    # material sits deeper in and cannot be seen from here. Keep it.
    return {
        "group": group,
        "keep": True,
        "reason": f"ends {newest}, may reach back",
        "newest_year": newest,
        "seen": len(years),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("groups", nargs="*")
    ap.add_argument("--from-file", type=Path)
    ap.add_argument("--out", type=Path, help="write the groups worth downloading here")
    ap.add_argument("--report", type=Path, help="write every verdict as CSV")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()

    groups = list(args.groups)
    if args.from_file:
        groups += [ln.strip() for ln in args.from_file.read_text().splitlines() if ln.strip()]
    if not groups:
        raise SystemExit("no groups given")

    verdicts: list[dict] = []
    done = 0
    lock = threading.Lock()
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(judge, g, args.timeout): g for g in groups}
        for future in as_completed(futures):
            verdict = future.result()
            with lock:
                verdicts.append(verdict)
                done += 1
                if done % 200 == 0 or done == len(groups):
                    kept = sum(1 for v in verdicts if v["keep"])
                    rate = done / max(time.monotonic() - started, 1e-6)
                    print(
                        f"{done:,}/{len(groups):,} judged, {kept:,} kept, "
                        f"{done - kept:,} skipped, {rate:.1f}/s",
                        flush=True,
                    )

    verdicts.sort(key=lambda v: v["group"])
    keep = [v["group"] for v in verdicts if v["keep"]]
    if args.out:
        args.out.write_text("\n".join(keep) + "\n")
        print(f"wrote {args.out} ({len(keep):,} groups)")
    if args.report:
        with args.report.open("w", newline="") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=["group", "keep", "reason", "newest_year", "seen"]
            )
            writer.writeheader()
            writer.writerows(verdicts)
        print(f"wrote {args.report}")

    skipped = len(verdicts) - len(keep)
    print(f"\n{len(keep):,} kept, {skipped:,} skipped ({skipped / len(verdicts) * 100:.1f}%)")


if __name__ == "__main__":
    main()
