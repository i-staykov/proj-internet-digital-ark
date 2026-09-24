"""Convert suffix-sweep journals into the `cdx_snapshot` journal format, incrementally.

**Why convert rather than add a source.** `cdx_snapshot / cdx_timestamp` is
already approved master and its parser, invariants and provenance lineage are
tested. The suffix sweep produces the same *evidence*, an Internet Archive capture
timestamp for a domain, in a different *shape*: one row per capture rather than
one row per domain with a year list. So the right move is a converter, not a new
`SourceSpec`, which would duplicate a reviewed decision for no gain.

**Exact host only.** A capture dates a registrable only when its host IS the registrable:
`www.x.com` and `sub.x.com` are hostname records and never date `x.com` here.

**Only new or grown journals are read**, per the state file beside the output. gzip cannot
resume, so a grown journal is read whole again; the ingest dedups per (domain, year,
source), so its repeated rows add nothing. A run that finds nothing writes nothing.

A journal still being written has no gzip end-of-stream marker, so a truncated tail is
normal and everything before it is valid. A corrupt one is named on every run and read
again only once it changes.

    uv run python scripts/engines/cdx_suffix_convert.py --tag 20260821
"""

import argparse
import glob
import gzip
import json
import os
import sys
import time
import zlib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from ark.canonical import to_registrable  # noqa: E402
from ark.hostnames import YEARS, host_of  # noqa: E402
from ark.journal import open_journal_for_write  # noqa: E402

STATE_NAME = "cdx_suffix_convert.state.tsv"


def load_state(path: Path) -> dict[str, tuple[int, int, str]]:
    """Journal name to (size, mtime_ns, outcome) as last read."""
    if not path.exists():
        return {}
    state = {}
    for line in path.read_text().splitlines():
        name, size, mtime_ns, outcome = line.split("\t")
        state[name] = (int(size), int(mtime_ns), outcome)
    return state


def save_state(path: Path, state: dict[str, tuple[int, int, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("".join(f"{n}\t{s}\t{m}\t{o}\n" for n, (s, m, o) in sorted(state.items())))
    os.replace(tmp, path)


def read_journal(path: str, years: defaultdict[str, set[int]]) -> tuple[int, str]:
    """Add one journal's exact-host registrable years; return its row count and outcome."""
    # per journal, because a journal is one parent's hosts and they rarely recur in the next
    exact: dict[str, str | None] = {}
    rows = 0
    try:
        with gzip.open(path, "rt", errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                    stamp, url = str(d["timestamp"]), str(d["url"])
                except (ValueError, KeyError, TypeError):
                    continue
                rows += 1
                if len(stamp) != 14 or not stamp.isdigit():
                    continue
                year = int(stamp[:4])
                if year not in YEARS:
                    continue
                # only the platform walk records a status; its query keeps 2xx and 3xx already
                if "status" in d and str(d["status"])[:1] not in ("2", "3"):
                    continue
                authority = url.split("://", 1)[-1].split("/", 1)[0]
                if authority not in exact:
                    host = host_of(authority)
                    exact[authority] = host if host and to_registrable(host) == host else None
                if exact[authority]:
                    years[exact[authority]].add(year)
    except EOFError:
        return rows, "truncated"
    except (OSError, zlib.error) as exc:
        # BadGzipFile is an OSError, a corrupt deflate stream is not
        print(f"bad gzip, skipped: {os.path.basename(path)}: {exc}")
        return rows, "bad"
    return rows, "ok"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", default=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    ap.add_argument("--glob", default="data/raw/cdx_suffix/*.jsonl.gz")
    ap.add_argument("--out", type=Path, default=Path("data/raw/cdx"))
    ap.add_argument("--state", type=Path, help=f"default <out>/{STATE_NAME}")
    args = ap.parse_args(argv)
    state_path = args.state or args.out / STATE_NAME
    dest = args.out / f"cdx_suffix_{args.tag}.jsonl.gz"
    if dest.exists():
        # the ingest ledger keys on the name, so new bytes under it would be refused
        sys.exit(f"{dest} exists: pass another --tag")

    state = load_state(state_path)
    years: defaultdict[str, set[int]] = defaultdict(set)
    read = unchanged = bad = rows = 0
    for path in sorted(glob.glob(args.glob)):
        name = os.path.basename(path)
        try:
            st = os.stat(path)
        except FileNotFoundError:
            continue
        seen = state.get(name)
        if seen and seen[:2] == (st.st_size, st.st_mtime_ns):
            unchanged += 1
            if seen[2] == "bad":
                bad += 1
                print(f"still bad: {name}")
            continue
        n, outcome = read_journal(path, years)
        read += 1
        rows += n
        bad += outcome == "bad"
        # the stat from before the read, so rows a live sweep appends meanwhile come next run
        state[name] = (st.st_size, st.st_mtime_ns, outcome)

    if years:
        args.out.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        with open_journal_for_write(part) as fh:
            for dom, ys in sorted(years.items()):
                fh.write(
                    json.dumps(
                        {
                            "domain": dom,
                            "status": 200,
                            "years": sorted(ys),
                            "strategy": "suffix_sweep",
                        }
                    )
                    + "\n"
                )
        os.replace(part, dest)
    # after the output, so a crash between the two re-reads rather than loses
    if read:
        save_state(state_path, state)

    print(f"{read:,} journal(s) read, {unchanged:,} unchanged, {bad:,} bad; {rows:,} capture rows")
    if years:
        print(f"  {len(years):,} exact-host registrables -> {dest}")
        print(f"  next: uv run ark ingest cdx_snapshot {dest}")
    else:
        print("  nothing new, nothing written")


if __name__ == "__main__":
    main()
