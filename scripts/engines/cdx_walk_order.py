"""Rank the extended walk's queue by measured net-new EE per request, one figure per part.

Every answered request (200 or 504) in every lane's `log.tsv` is charged to its (suffix, kind)
unit. Each `walk_*` journal is priced once: its (host, year) rows absent from his same-year file
and from our additions banked before the walk (`data/queue/cdx_held/`), weighted by his English
share, by binary search in the C-sorted year files. The output, `{"units": {"<suffix> <kind>":
{"p1", "p2", "n"}}}`, is what the lanes re-read; a unit no lane has answered keeps its price.
"""

from __future__ import annotations

import gzip
import json
import mmap
import os
from pathlib import Path

from ark.english_share import english_weights
from ark.hostnames import host_of

DATA = Path(os.environ.get("ARK_WALK_DATA", Path(__file__).resolve().parents[2] / "data"))


def contains(mm: mmap.mmap, key: bytes) -> bool:
    """Whether a line equal to `key` is in the C-sorted file mapped by `mm`."""
    lo, hi = 0, len(mm)
    while lo < hi:
        start = mm.rfind(b"\n", 0, (lo + hi) // 2) + 1
        end = mm.find(b"\n", start)
        line = mm[start : len(mm) if end < 0 else end]
        if line == key:
            return True
        lo, hi = (end + 1, hi) if line < key and end >= 0 else (lo, start)
    return False


class Release:
    """Sorted year files in a folder, mapped on first use; a missing year holds nothing."""

    def __init__(self, directory: Path):
        self.dir, self.maps = directory, {}

    def holds(self, year: int, host: str) -> bool:
        if year not in self.maps:
            path = self.dir / f"{year}.txt"
            self.maps[year] = None
            if path.exists() and path.stat().st_size:
                with open(path, "rb") as fh:
                    self.maps[year] = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        return self.maps[year] is not None and contains(self.maps[year], host.encode())


def price(path: Path, held: list[Release], weights: dict) -> float:
    ee = 0.0
    with gzip.open(path, "rt") as fh:
        for line in fh:
            row = json.loads(line)
            host, year = host_of(row["url"]), row["timestamp"][:4]
            if host and year.isdigit() and not any(r.holds(int(year), host) for r in held):
                ee += weights.get(host.rsplit(".", 1)[-1], 0.0)
    return ee


def main() -> None:
    baseline = json.loads((DATA / "baseline.json").read_text())["current"]
    held = [Release(DATA.parent / baseline["directory"]), Release(DATA / "queue/cdx_held")]
    weights = {t: float(w) for t, w in english_weights().items()}
    out, cache_path = DATA / "queue/cdx_order.json", DATA / "queue/cdx_order.priced.json"
    try:
        cache = json.loads(cache_path.read_text())
    except (OSError, ValueError):
        cache = {}
    if cache.get("marker") != baseline["marker"]:
        cache = {"marker": baseline["marker"], "journals": {}}
    units: dict[str, list] = {}
    names: dict[str, str] = {}
    for log in DATA.glob("raw/cdx_walk/*/log.tsv"):
        for r in (line.rstrip("\n").split("\t") for line in open(log)):
            if len(r) >= 8 and not r[0].startswith("#"):
                names[f"walk_{r[1]}_ps{r[2]}_p{r[3]}_{r[4]}-{r[5]}"] = unit = f"{r[1]} {r[6]}"
                if r[7] in ("200", "HTTP504"):  # a refusal is the address's state, not a price
                    units.setdefault(unit, [0, 0.0, 0.0])[0] += 1
    for part, folder in ((1, "raw/cdx_suffix"), (2, "raw/extended/ia_cdx_hostnames")):
        for path in (DATA / folder).glob("walk_*.jsonl.gz"):
            unit = names.get(path.name.split("_cut_")[0].removesuffix(".jsonl.gz"))
            key = f"{folder}/{path.name}"
            if unit in units:
                try:
                    if key not in cache["journals"]:
                        cache["journals"][key] = price(path, held, weights)
                except (OSError, EOFError, ValueError) as exc:
                    print(f"unpriced {key}: {exc}")
                    continue
                units[unit][part] += cache["journals"][key]
    order = json.loads(out.read_text()).get("units", {}) if out.exists() else {}
    for unit, (n, ee1, ee2) in units.items():
        order[unit] = {"p1": round(ee1 / n, 2), "p2": round(ee2 / n, 2), "n": n}
    for path, doc in ((out, {"marker": baseline["marker"], "units": order}), (cache_path, cache)):
        path.with_suffix(".tmp").write_text(json.dumps(doc, indent=1))
        os.replace(path.with_suffix(".tmp"), path)
    best = max(order.items(), key=lambda kv: kv[1]["p1"] + kv[1]["p2"], default=("none", {}))
    print(f"ranked {len(order)} units; best {best[0]} {best[1]}")


if __name__ == "__main__":
    main()
