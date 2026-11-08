"""The cdx run's row: a day's yield per lane, question kind and window, with its 7-day band.

    python3 scripts/agents/lane_yield.py [--date YYYY-MM-DD]    # default yesterday UTC

The date's rows of every `data/raw/cdx_walk/lane*/log.tsv` (`cdx_extended_walk.py`) become
rows of `data/logs/productivity.tsv`, the date's earlier rows replaced: date, lane, kind
(`page`, or an ask tier such as `ask-gap`), window (`1996-2001`, `2002-2013`), requests,
answered (200 or 504, as `cdx_walk_order.py` counts), paused_seconds (the pauses this kind's
answers caused, overlaps once, inside the date), ee (the window's journals as the bank priced
them, `data/queue/cdx_order.priced.json`), ee_per_client_second (ee over the lane's wall seconds
in the date, first start to last end, pauses included, one client whatever its workers: a lane
idle part of the day is rated over the part it walked), band_low and band_high (that ee a second
over the lane's previous seven rows of the kind and window, blank under three). `LEVERS` is the
levers file the cdx run may pull from.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("ARK_WALK_DATA", ROOT / "data"))
OUT = ROOT / "data/logs/productivity.tsv"
LEVERS = ROOT / "scripts/engines/levers.json"
WINDOWS = ("1996-2001", "2002-2013")
HEADER = "date lane kind window requests answered paused_seconds ee ee_per_client_second"
HEADER = HEADER.split() + ["band_low", "band_high"]
ANSWERED = {"200", "HTTP504"}
PAUSE = re.compile(r"# pause (\d+) s")
BAND = 7


def priced(data: Path) -> dict[str, list[float]]:
    """Journal name to its EE in 1996-2001 and 2002-2013, from the walk order's cache."""
    try:
        cache = json.loads((data / "queue/cdx_order.priced.json").read_text())["journals"]
    except (OSError, ValueError, KeyError):
        return {}
    out: dict[str, list[float]] = {}
    for key, ee in cache.items():
        part = 0 if key.startswith("raw/cdx_suffix/") else 1
        out.setdefault(Path(key).name.removesuffix(".jsonl.gz"), [0.0, 0.0])[part] += float(ee)
    return out


def epoch(stamp: str) -> float:
    return dt.datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.UTC).timestamp()


def union(spans: list[tuple[float, float]]) -> float:
    total, end = 0.0, float("-inf")
    for a, b in sorted(spans):
        a = max(a, end)
        if b > a:
            total, end = total + b - a, b
    return total


def day(lines, date: str, ee: dict[str, list[float]]) -> tuple[dict[str, dict], float]:
    """Each kind's requests, answers, EE a window and pauses in the date, and the lane's wall
    seconds. A pause line is charged to the row before it, whose answer caused it."""
    t0 = epoch(date.replace("-", "") + "T000000Z")
    t1 = t0 + 86400
    kinds: dict[str, dict] = {}
    first, last, before = t1, t0, None

    def entry(kind: str) -> dict:
        blank = {"requests": 0, "answered": 0, "ee": [0.0, 0.0], "pauses": []}
        return kinds.setdefault(kind, blank)

    for line in lines:
        if m := PAUSE.match(line):
            if before and before[1] < t1 and before[1] + int(m[1]) > t0:
                clip = (max(before[1], t0), min(before[1] + int(m[1]), t1))
                entry(before[0])["pauses"].append(clip)
                first, last = min(first, clip[0]), max(last, clip[1])
            continue
        r = line.rstrip("\n").split("\t")
        if len(r) < 14 or not r[2].isdigit():
            continue
        try:
            at, secs = epoch(r[0]), float(r[9])
        except ValueError:
            continue
        kind = r[1] if r[6] == "ask" else "page"
        before = (kind, at + secs)
        if at < t1 and at + secs > t0:
            first, last = min(first, max(at, t0)), max(last, min(at + secs, t1))
        if not t0 <= at < t1:
            continue
        k = entry(kind)
        k["requests"] += 1
        k["answered"] += r[7] in ANSWERED
        cut = "" if r[8] == "1" else f"_cut_{r[0]}"
        p1, p2 = ee.get(f"walk_{r[1]}_ps{r[2]}_p{r[3]}_{r[4]}-{r[5]}{cut}", (0.0, 0.0))
        k["ee"][0] += p1
        k["ee"][1] += p2
    return kinds, max(0.0, last - first)


def read(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    rows = (ln.split("\t") for ln in path.read_text().splitlines()[1:])
    return [r for r in rows if len(r) == len(HEADER)]


def write(out: Path, data: Path, date: str) -> int:
    """The date's rows, replacing earlier ones for it; how many were written."""
    kept = [r for r in read(out) if r[0] != date]
    ee, new = priced(data), []
    for log in sorted(data.glob("raw/cdx_walk/lane*/log.tsv")):
        lane = log.parent.name
        with open(log, errors="replace") as fh:
            kinds, wall = day(fh, date, ee)
        for kind, k in sorted(kinds.items()):
            for i, window in enumerate(WINDOWS):
                rate = k["ee"][i] / wall if wall else 0.0
                same = [r for r in kept if r[1:4] == [lane, kind, window] and r[0] < date]
                band = [float(r[8]) for r in sorted(same)[-BAND:]]
                low, high = (f"{min(band):.5f}", f"{max(band):.5f}") if len(band) >= 3 else ("", "")
                counts = [k["requests"], k["answered"], round(union(k["pauses"]))]
                row = [date, lane, kind, window, *counts, f"{k['ee'][i]:.2f}", f"{rate:.5f}"]
                new.append([*map(str, row), low, high])
    rows = sorted(kept + new)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text("".join("\t".join(r) + "\n" for r in [HEADER, *rows]))
    os.replace(tmp, out)
    return len(new)


def lines(path: Path) -> dict[str, str]:
    """Each lane's last date as one line: a kind's answers, pauses, EE and rate a window."""
    rows = read(path)
    last: dict[str, str] = {}
    for r in rows:
        last[r[1]] = max(last.get(r[1], ""), r[0])
    parts: dict[str, dict[str, list[str]]] = {}
    for r in rows:
        if r[0] == last[r[1]]:
            band = f" (band {r[9]} to {r[10]})" if r[9] else ""
            kind = parts.setdefault(r[1], {})
            kind.setdefault(r[2], [f"{r[2]} {r[5]} of {r[4]} answered, {r[6]} s paused"])
            kind[r[2]].append(f"{r[7]} EE {r[3]} at {r[8]} a second{band}")
    return {
        lane: f"{last[lane]}: " + "; ".join(", ".join(v) for v in kinds.values())
        for lane, kinds in parts.items()
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    yesterday = (dt.datetime.now(dt.UTC) - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    ap.add_argument("--date", default=yesterday)
    a = ap.parse_args(argv)
    dt.date.fromisoformat(a.date)
    print(f"lane yield {a.date}: {write(OUT, DATA, a.date)} rows")


if __name__ == "__main__":
    main()
