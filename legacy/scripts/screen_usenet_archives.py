"""Report each Usenet archive's in-window coverage, so the queue can be pruned.

The 5 August decay measurement found that yield is bimodal rather than smoothly
decaying: a group whose Giganews archive covers 1996-2001 returns roughly a
thousand net-new pairs, and a group whose archive begins in 2003 returns nothing
at all. Four of 28 probed archives contributed exactly zero between them, and
`uk.misc` gave one record from 172.9 MB. Across the whole probe, **4,023,027 of
5,283,482 messages were out of window**, so three quarters of the bytes bought
nothing.

Neither of the selection rules used so far predicts this. Round one matched on
group *name*, which selects announcement forums and misses that ordinary
discussion groups yield just as well. Round two capped on *size*, which defers
large groups regardless of whether they are the productive ones. Both are
proxies for the thing that actually decides it, which is whether the archive
covers the window at all.

This measures that directly, and the first attempt at it was wrong in a way worth
recording. Reading the **head** of each mbox is the obvious cheap screen, and it
fails: `uk.finance` yields thousands of in-window pairs but its first 2,000
messages are all 2011-2013, and `uk.transport` reads as 2002-2003. **The Giganews
exports are not in chronological order**, so a head sample says nothing about a
group's coverage. The screen therefore strides across the whole archive, taking
every Nth message, which still skips the expensive part (parsing every message
body and extracting URLs) while sampling the file uniformly.

Note what this can and cannot do. It prunes the *ingest* queue, saving parse
time, and tells you which groups deserve a re-fetch at a larger size cap. It
cannot prune the *download* queue, because the dates are only visible once the
bytes are here, and reordering downloads would need a per-group date range that
archive.org does not publish.

    uv run python scripts/screen_usenet_archives.py data/raw/usenet_probe*/*.zip
    uv run python scripts/screen_usenet_archives.py --keep-list keep.txt <archives>
"""

import argparse
import email
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ark.ingest import YEARS  # noqa: E402
from ark.usenet import iter_messages, message_year  # noqa: E402


def coverage(path: Path, stride: int) -> tuple[int, int, int | None, int | None]:
    """(sampled, in-window, earliest year, latest year) over a stride sample.

    Every `stride`-th message, not the first N: see the module docstring. The
    archives are not date-ordered, so a contiguous sample from anywhere in the
    file is a sample of one period rather than of the group.
    """
    sampled = in_window = 0
    earliest: int | None = None
    latest: int | None = None
    for index, raw in enumerate(iter_messages(path)):
        if index % stride:
            continue
        sampled += 1
        try:
            message = email.message_from_bytes(raw)
        except Exception:  # noqa: BLE001 - one malformed post must not end the screen
            continue
        year = message_year(message.get("Date", ""))
        if year is None or not 1980 < year < 2030:
            continue
        earliest = year if earliest is None else min(earliest, year)
        latest = year if latest is None else max(latest, year)
        if year in YEARS:
            in_window += 1
    return sampled, in_window, earliest, latest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--stride", type=int, default=25, help="sample every Nth message")
    parser.add_argument(
        "--threshold",
        type=float,
        default=1.0,
        help="percent of sampled messages in window below which a group is dropped",
    )
    parser.add_argument("--keep-list", type=Path, help="write the surviving archive paths here")
    args = parser.parse_args()

    keep: list[Path] = []
    print(f"{'in-window %':>11}  {'sampled':>7}  {'span':>11}  group")
    for path in args.archives:
        sampled, in_window, earliest, latest = coverage(path, args.stride)
        share = 100.0 * in_window / sampled if sampled else 0.0
        span = f"{earliest or '?'}-{latest or '?'}"
        if share >= args.threshold:
            keep.append(path)
        print(f"{share:>10.1f}%  {sampled:>7,}  {span:>11}  {path.name}")

    dropped = len(args.archives) - len(keep)
    print(f"\nkeep {len(keep)}, drop {dropped} of {len(args.archives)}")
    if args.keep_list:
        args.keep_list.write_text("\n".join(str(p) for p in keep) + "\n")


if __name__ == "__main__":
    main()
