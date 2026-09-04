"""The separately labelled unparsed pool his section XI asks for.

XI: "Retain malformed but potentially recoverable values only in a separately labeled unparsed or
normalization-review file." We counted those values and dropped them: `no_host`, `rejected_host`
and `registrable_row` are stats in the ingest's log and nothing else.

**They did not need to be captured at ingest, which is why this is a reader.** The journals are
kept, so a value the funnel refused is recoverable by re-reading them and applying the same funnel
again. That matters practically: two collectors are mid-run for days at a time, and a version of
this that changed `ingest_hostname_journal` would have meant editing code a live fold loop calls.

The distinction XI draws is between malformed-but-recoverable and simply-not-a-hostname, and the
funnel already knows which is which, so each row carries the reason:

- `not_rfc1123`  underscores, over-long labels, a numeric TLD. The era really had these names, so
  they are recoverable if he ever rules on the shape.
- `is_registrable` the value IS its own registrable, so it belongs in `additions/` and is not
  malformed at all. Kept because a reader comparing counts will otherwise wonder where it went.
- `no_public_suffix` no known suffix, so `to_registrable` cannot place it. Usually a typo in a
  typed URL, occasionally a TLD the pinned list postdates.
- `reverse_dns` an `in-addr.arpa` or `ip6.arpa` name, refused as infrastructure.

    uv run python scripts/round/unparsed_pool.py [--dirs data/raw/cdx_suffix ...] [--limit N]
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
import sys  # noqa: E402

sys.path.insert(0, str(REPO / "src"))

from ark.canonical import to_registrable  # noqa: E402
from ark.hostnames import _VALID_HOST, _host_of  # noqa: E402

OUT = REPO / "output/netnew/candidates_unparsed.txt"
DEFAULT_DIRS = ("data/raw/cdx_suffix", "data/raw/cdx_gap_hostgrain", "data/raw/nypw_hostgrain")


def reason_for(raw: str) -> str | None:
    """Why the funnel refused this value, or None if it did not."""
    host = _host_of(raw)
    if host is None:
        bare = raw.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0].strip().lower()
        if not bare:
            return None
        if bare.endswith((".in-addr.arpa", ".ip6.arpa")):
            return "reverse_dns"
        return "not_rfc1123" if not _VALID_HOST.match(bare) else "no_public_suffix"
    parent = to_registrable(host)
    if parent is None:
        return "no_public_suffix"
    if parent == host:
        return "is_registrable"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dirs", nargs="*", default=list(DEFAULT_DIRS))
    ap.add_argument("--limit", type=int, default=0, help="stop after N journals, 0 for all")
    ap.add_argument(
        "--stable-after",
        type=int,
        default=25,
        help="stop once N consecutive journals add no new refused value (0 to disable)",
    )
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    counts: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    read = 0
    # **The refused set saturates, so scanning every journal buys nothing.** 25 journals of
    # `cdx_suffix` hold 14.4M values and yield 4,306 distinct refused ones, and the whole
    # corpus is 300M values: an exhaustive pass would cost an hour per round to add almost
    # nothing, because the same malformed shapes recur on the same platforms. So the pass
    # stops when N consecutive journals add no new value, which is the same saturation
    # argument as everywhere else in this project, applied to a pool rather than a corpus.
    barren = 0
    for name in args.dirs:
        root = REPO / name
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.jsonl.gz")):
            if args.limit and read >= args.limit:
                break
            read += 1
            before = len(seen)
            try:
                with gzip.open(path, "rt", errors="replace") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            row = json.loads(line)
                        except ValueError:
                            continue
                        raw = str(row.get("url", ""))
                        if not raw:
                            continue
                        counts["values"] += 1
                        why = reason_for(raw)
                        if why is None:
                            continue
                        bare = raw.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0].lower()
                        if bare:
                            seen.add((bare, why))
                            counts[why] += 1
            except (EOFError, OSError):
                counts["truncated_journals"] += 1
            barren = 0 if len(seen) > before else barren + 1
            if args.stable_after and barren >= args.stable_after:
                counts["stopped_on_saturation"] = 1
                break
        if counts.get("stopped_on_saturation"):
            break

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        fh.write("# value\treason\n")
        for value, why in sorted(seen):
            fh.write(f"{value}\t{why}\n")
    tail = " (stopped on saturation)" if counts.get("stopped_on_saturation") else ""
    print(f"{read:,} journals, {counts['values']:,} values, {len(seen):,} distinct refused{tail}")
    for why, n in counts.most_common():
        if why not in {"values", "truncated_journals", "stopped_on_saturation"}:
            print(f"  {why:18} {n:>12,}")
    if counts["truncated_journals"]:
        print(f"  {'truncated journals':18} {counts['truncated_journals']:>12,} (a live collector)")
    print(f"wrote {args.out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
