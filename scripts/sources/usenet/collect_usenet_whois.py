"""Read the whois records people pasted into Usenet posts, for their creation dates.

A poster reporting a spammer, arguing over a name or answering "who owns this"
pastes the registry's whole answer into the body. The line that matters is the
registry's own, not the poster's:

    Domain Name: BSDSEARCH.COM
    ...
    Record created on 20-Jul-2000.

That string was written by InterNIC, not by the person quoting it, so it dates
the registration whatever year the post was made in. `whois_creation`, and rule
6 applies: it evidences its own year and nothing else.

**The defect this script exists to prevent, measured on this corpus.** A whois
block puts the name at the top and the creation line twenty to forty lines
below, so the name has to be found by looking back. An earlier pass looked back
150 lines and bound `Record created on 19-Dec-1998`, which is `openssl.org`'s,
to `engelschall.com`. The cause is that the two patterns disagreed about
markup: a message quoted the same block three times, once as plain text, once
quoted with `>`, and once HTML-escaped with `&nbsp;` runs. The date pattern
matches anywhere in a line so it read the escaped copy fine; the name pattern is
anchored at the start of the line so `&nbsp;&nbsp;Domain Name: OPENSSL.ORG` did
not match at all, and the nearest name it could see was the plain-text block
seventy-six lines earlier. This is the same mis-binding that once overstated the
Edelman transcriptions by 47%, arriving by a different route.

**So both patterns read the SAME normalised line**, `&nbsp;` and quote prefixes
stripped before either is tried, and a creation line more than `MAX_BACK` lines
below its name is dropped. With normalisation alone the openssl message binds
correctly; the cap is there because the next encoding will be one nobody has
seen. Every row carries its own `back` distance so the cap can be re-argued
against data rather than guessed again.

Writes a journal, never opens the store, uses no network. The split runs after.

    uv run python scripts/sources/usenet/collect_usenet_whois.py --workers 10
    ARK_USENET_SRC=data/raw/usenet_new uv run python scripts/sources/usenet/collect_usenet_whois.py
"""

import argparse
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ark.canonical import to_registrable  # noqa: E402
from ark.journal import journal_writer, write_journal_line  # noqa: E402
from ark.usenet import iter_messages, message_year  # noqa: E402

USENET = ROOT / os.environ.get("ARK_USENET_SRC", "data/raw/usenet")
OUT_DIR = ROOT / "data/raw/usenet_whois"
YEARS = range(1996, 2002)

# The furthest a creation line may sit below the name it belongs to. Measured on
# this corpus: a plain InterNIC block spans 19 to 25 lines from `Domain Name:` to
# `Record created on`, a Nominet one fewer, and the longest correct binding seen
# was 39. Beyond 40 every checked example was a leak from an adjacent record.
MAX_BACK = 40

_NAME = re.compile(r"^(?:domain\s*name|domain|domain-name)\s*[.:]+\s*(\S+)\s*$", re.I)
_NAME_ALONE = re.compile(r"^(?:domain\s*name|domain|domain-name)\s*[.:]+\s*$", re.I)
# Nominet and a few ccTLD registries print the name on the line after the label.
_HOSTLIKE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}(?:\.[a-z0-9-]{1,63})+$", re.I)
_CREATED = re.compile(
    r"(?:record\s+created\s+on|domain\s+created\s+on|created\s+on\s*[.:]|"
    r"creation\s+date\s*[.:]|created\s*[.:]|registered\s+on\s*[.:]|"
    r"domain\s+registered\s*[.:])\s*[.:]*\s*(.{0,32})",
    re.I,
)
_QUOTE = re.compile(r"^[\s>|]*")
_DATE_HEADER = re.compile(rb"(?mi)^Date:[ \t]*(.+)")
_MSGID = re.compile(rb"(?mi)^Message-ID:[ \t]*(.+)")

_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}
_D_DMY = re.compile(r"\b(\d{1,2})[-/ ]([A-Za-z]{3})[a-z]*[-/ ](\d{4})\b")
_D_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_D_MDY = re.compile(r"\b([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\b")
_D_COMPACT = re.compile(r"\b(\d{4})(\d{2})(\d{2})\b")


def normalise(line: str) -> str:
    """One reading of a line, shared by both patterns. See the module docstring."""
    return _QUOTE.sub("", line.replace("&nbsp;", " ").replace("&gt;", ">")).rstrip()


def creation_date(blob: str) -> tuple[int, int, int] | None:
    """The date in a registry creation field, in every spelling this era used.

    The whole date is kept, not just the year, because the evidence value has to
    carry the registry's own stamp: `ark check` reads the first four-digit run in
    that string back and compares it with the year the row was filed under, so a
    value naming only a group and a Message-ID would be checked against whatever
    digits those happened to contain.
    """
    match = _D_DMY.search(blob)
    if match:
        month = _MONTHS.get(match.group(2).lower())
        if month:
            return int(match.group(3)), month, int(match.group(1))
    match = _D_ISO.search(blob)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    match = _D_MDY.search(blob)
    if match:
        month = _MONTHS.get(match.group(1).lower())
        if month:
            return int(match.group(3)), month, int(match.group(2))
    match = _D_COMPACT.search(blob)
    if match:
        year, month, day = (int(g) for g in match.groups())
        if 1980 <= year <= 2015 and 1 <= month <= 12 and 1 <= day <= 31:
            return year, month, day
    return None


def creations_in(text: str) -> list[tuple[str, str, int, int]]:
    """(registrable domain, creation date, year, binding distance) in one message."""
    lines = text.split("\n")
    found: list[tuple[str, str, int, int]] = []
    name, name_at = None, -(10**9)
    for index, raw in enumerate(lines):
        line = normalise(raw)
        match = _NAME.match(line)
        if match:
            name, name_at = match.group(1).strip().rstrip(".").lower(), index
            continue
        if _NAME_ALONE.match(line) and index + 1 < len(lines):
            following = normalise(lines[index + 1]).strip().rstrip(".").lower()
            if _HOSTLIKE.match(following):
                name, name_at = following, index
            continue
        created = _CREATED.search(line)
        if created is None or name is None:
            continue
        back = index - name_at
        if back > MAX_BACK:
            continue
        stamped = creation_date(created.group(1))
        if stamped is None or stamped[0] not in YEARS:
            continue
        year, month, day = stamped
        domain = to_registrable(name)
        if domain:
            found.append((domain, f"{year:04d}-{month:02d}-{day:02d}", year, back))
    return found


def records_in_archive(path: Path) -> tuple[str, list[dict], dict]:
    """(group, one record per creation date found, stats). Runs in a worker."""
    stats: Counter = Counter()
    out: list[dict] = []
    seen: set[tuple[str, int]] = set()
    group = path.stem.replace(".mbox", "")
    try:
        for raw in iter_messages(path):
            stats["messages"] += 1
            head = raw[:4000]
            date_header = _DATE_HEADER.search(head)
            posted = (
                message_year(date_header.group(1).decode("latin-1", "replace"))
                if date_header
                else None
            )
            text = raw.decode("latin-1", "replace")
            hits = creations_in(text)
            if not hits:
                continue
            stats["messages_with_whois"] += 1
            msgid_match = _MSGID.search(head)
            msgid = (
                msgid_match.group(1).decode("latin-1", "replace").strip()[:120]
                if msgid_match
                else ""
            )
            for domain, created, year, back in hits:
                if (domain, year) in seen:
                    continue
                seen.add((domain, year))
                out.append(
                    {
                        "domain": domain,
                        "year": year,
                        # the registry's own string, which is what dates the row
                        "created": created,
                        "message_id": msgid,
                        "group": group,
                        "url": f"https://archive.org/details/usenet-{group.split('.')[0]}",
                        # kept so the MAX_BACK cap can be re-argued against data
                        "back": back,
                        "posted_year": posted,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        # one unreadable archive must not void the batch around it
        stats[f"failed_{type(exc).__name__}"] += 1
        print(f"  skip {path.name}: {type(exc).__name__}: {exc}", flush=True)
    return group, out, dict(stats)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--tag", default="", help="suffix for the journal name")
    args = ap.parse_args()

    archives = sorted(USENET.glob("*.mbox.zip"))
    if not archives:
        raise SystemExit(f"no .mbox.zip under {USENET}; set ARK_USENET_SRC")
    total_bytes = sum(p.stat().st_size for p in archives)
    print(f"{len(archives):,} archives, {total_bytes / 1e9:.1f} GB, {args.workers} workers")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    suffix = f"_{args.tag}" if args.tag else ""
    out = args.out_dir / f"usenet_whois{suffix}_{stamp}.jsonl.gz"

    totals: Counter = Counter()
    written = 0
    seen: set[tuple[str, int]] = set()
    started = time.time()
    with journal_writer(out) as fh, ProcessPoolExecutor(max_workers=args.workers) as pool:
        for n, (_group, records, stats) in enumerate(
            pool.map(records_in_archive, archives, chunksize=1), 1
        ):
            totals.update(stats)
            for record in records:
                key = (record["domain"], record["year"])
                if key in seen:
                    continue
                seen.add(key)
                write_journal_line(fh, record)
                written += 1
            if n % 500 == 0 or n == len(archives):
                elapsed = max(time.time() - started, 1)
                print(
                    f"  {n:,}/{len(archives):,} archives, {written:,} pairs, "
                    f"{n / elapsed * 3600:,.0f} archives/h",
                    flush=True,
                )

    print(f"\nwrote {out}")
    print(f"  messages {totals['messages']:,}")
    print(f"  messages carrying a pasted whois creation date: {totals['messages_with_whois']:,}")
    print(f"  distinct in-window (domain, creation year): {written:,}")
    failures = {k: v for k, v in totals.items() if k.startswith("failed_")}
    print(f"  archive failures: {failures or 'none'}")
    print("\nnext: uv run python scripts/sources/usenet/split_usenet_whois.py --write")


if __name__ == "__main__":
    main()
