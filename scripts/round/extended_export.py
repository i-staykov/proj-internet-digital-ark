"""Write `output/extended_years/`: our 2002 to 2015 additions to his same-year files.

A host-year ships only by its own capture, as an addition to his file for that year
(`AGENTS.md`, The window). The input is the capture journal every converter already writes,
JSONL(.gz) rows `{"url", "timestamp", "status"?}`, one folder per method under
`data/raw/extended/<method>/`, so the method is declared by where a file is put and never
guessed from its name. `--in METHOD=GLOB` replaces the defaults, to price a dataset into a
scratch `--out`.

A row is kept when its stamp's year is 2002 to 2015, its method is in `WEB_METHODS`, its
status is not 4xx or 5xx, its host passes his `HOST_RE` (`hostnames.host_of`) and has a
registrable, and its TLD existed that year: the eight window gTLDs, a two-letter ccTLD, or a
TLD `DELEGATED` by then. Any other TLD fails closed. Each kept host-year carries its earliest
capture; whatever his same-year file holds, by exact name, is dropped by `comm`.

Written, all sorted and unique under LC_ALL=C, nothing loaded whole into memory:

    YYYY.txt            his file merged with ours, `sort -m -u`, for years with an addition
    additions/YYYY.txt  ours alone
    evidence_ledger.csv one row per addition: its capture, file, line and the file's sha256
    dedup_report.csv    his merge_stats columns, one row per year we submitted to
    manifest.json       the release, the inputs, and per year the counts, EE and sha256s

    uv run python scripts/round/extended_export.py [--in METHOD=GLOB ...] [--out DIR]
    uv run python scripts/round/extended_export.py --check   # exit 1 if the output is stale
"""

import argparse
import csv
import glob
import gzip
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark import held  # noqa: E402
from ark.baseline import (  # noqa: E402
    CURRENT_BASELINE_MARKER,
    EXTENDED_YEARS,
    REVIEWER_EXTENDED_EE_BY_YEAR,
    baseline_dir,
)
from ark.canonical import to_registrable  # noqa: E402
from ark.delegation import DELEGATED, WINDOW_GTLDS  # noqa: E402
from ark.english_share import english_weights  # noqa: E402
from ark.evidence_types import WEB_METHODS  # noqa: E402
from ark.hostnames import host_of  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "merge_against_baseline", Path(__file__).with_name("merge_against_baseline.py")
)
_merge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_merge)
COLUMNS = _merge.COLUMNS

OUT = Path("output/extended_years")
# `*` takes each file's method from its folder's name.
INPUTS = {"*": "data/raw/extended/*/*.jsonl*"}
LEDGER = ("year", "host", "method", "source_file", "line", "source_sha256", "evidence_url")
RULE = (
    "a 2xx or 3xx (or status-less) capture of the exact host, stamped in the year, by a method "
    "in WEB_METHODS; host valid by his HOST_RE, TLD existing that year; minus his same-year file"
)
_STATUS = re.compile(r"[2-5][0-9][0-9]")
_C = {**os.environ, "LC_ALL": "C"}


def tld_existed(tld: str, year: int) -> bool:
    if tld in WINDOW_GTLDS:
        return tld != "arpa"
    if len(tld) == 2:
        return DELEGATED.get(tld, 0) <= year
    return DELEGATED.get(tld, year + 1) <= year


def replay(method: str, ts: str, url: str) -> str:
    """The capture's replay URL: Arquivo's for its methods, the Wayback Machine's otherwise."""
    if method.startswith("arquivo"):
        return f"https://arquivo.pt/wayback/{ts}/{url}"
    return f"https://web.archive.org/web/{ts}/{url}"


def rel(path: Path) -> str:
    """Repo-relative, links not followed, and never a local absolute path: the ledger ships."""
    try:
        return Path(os.path.abspath(path)).relative_to(REPO).as_posix()
    except ValueError:
        return path.name


def resolve_inputs(given: dict[str, str]) -> list[tuple[str, Path]]:
    found = [
        (Path(p).parent.name if m == "*" else m, Path(p))
        for m, g in sorted(given.items())
        for p in sorted(glob.glob(g))
    ]
    for method, path in found:
        if method not in WEB_METHODS:
            raise SystemExit(f"{path}: {method} is not in WEB_METHODS, a new class is the owner's")
    return found


def stat_of(path: Path) -> dict:
    st = path.stat()
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns}


def read_rows(inputs: list[tuple[str, Path]], rows_out: Path, drops: Counter) -> list[dict]:
    """Every kept capture as `year<TAB>host<TAB>ts<TAB>input<TAB>line<TAB>url`, and each input
    as the manifest records it."""
    described = []
    with rows_out.open("w", encoding="utf-8") as out:
        for index, (method, path) in enumerate(inputs):
            kept = 0
            with (gzip.open if path.suffix == ".gz" else open)(path, "rb") as stream:
                for lineno, line in enumerate(stream, 1):
                    reason, row = screen(line)
                    if reason:
                        drops[reason] += 1
                        continue
                    year, host, ts, url = row
                    out.write(f"{year}\t{host}\t{ts}\t{index}\t{lineno}\t{url}\n")
                    kept += 1
            described.append(
                {"method": method, "path": rel(path), "sha256": file_sha(path), "kept": kept}
                | stat_of(path)
            )
    return described


def screen(line: bytes) -> tuple[str | None, tuple | None]:
    """Why a journal line dates nothing, or None and (year, host, ts, url)."""
    if not line.strip():
        return "blank", None
    try:
        row = json.loads(line)
    except ValueError:
        return "unparseable", None
    if "status" in row:
        status = str(row["status"]).strip()
        if not _STATUS.fullmatch(status):
            return "bad_status", None
        if status[0] in "45":
            return "error_status", None
    ts = str(row.get("timestamp", ""))
    if len(ts) != 14 or not ts.isdigit():
        return "bad_timestamp", None
    year = int(ts[:4])
    if year not in EXTENDED_YEARS:
        return "outside_2002_2015", None
    url = " ".join(str(row.get("url", "")).split())
    host = host_of(url)
    if host is None:
        return "invalid_host", None
    if not tld_existed(host.rsplit(".", 1)[-1], year):
        return "tld_not_yet_delegated", None
    if to_registrable(host) is None:
        return "no_registrable", None
    return None, (year, host, ts, url)


def file_sha(path: Path) -> str:
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def his_file(year: int) -> Path:
    """His file for the year, refused unless `comm` can read it byte for byte."""
    path = baseline_dir() / f"{year}.txt"
    if not path.is_file():
        raise SystemExit(f"{path}: he has no {year} file, so nothing can be added to it")
    held.check_sorted(path)
    found = subprocess.run(["grep", "-q", "-e", "[^a-z0-9.-]", "-e", "^$", str(path)], env=_C)
    if found.returncode != 1:
        raise SystemExit(f"{path}: a line is not a lowercase name (grep {found.returncode})")
    return path


def export(globs: dict[str, str], out: Path) -> dict:
    weights = english_weights()
    drops: Counter = Counter()
    if out.exists():
        shutil.rmtree(out)
    (out / "additions").mkdir(parents=True)
    ledger_fh = (out / "evidence_ledger.csv").open("w", newline="", encoding="utf-8")
    ledger = csv.writer(ledger_fh, lineterminator="\n")
    ledger.writerow(LEDGER)
    with tempfile.TemporaryDirectory(dir=out) as tmp, ledger_fh:
        work, rows, ordered = Path(tmp), Path(tmp) / "rows.tsv", Path(tmp) / "sorted.tsv"
        described = read_rows(resolve_inputs(globs), rows, drops)
        sort = ["sort", "-S", "2G", "-T", str(work), "-o", str(ordered), str(rows)]
        subprocess.run(sort, env=_C, check=True)
        # Sorted by year, host, then stamp, so the first row of each host-year is its earliest.
        ours: dict[int, tuple] = {}
        last = None
        with ordered.open(encoding="utf-8") as fh:
            for line in fh:
                year, host, rest = line.split("\t", 2)
                if (year, host) == last:
                    drops["duplicate"] += 1
                    continue
                last = (year, host)
                if int(year) not in ours:
                    ours[int(year)] = tuple(
                        (work / f"{kind}_{year}.txt").open("w", encoding="utf-8")
                        for kind in ("ours", "ev")
                    )
                ours[int(year)][0].write(f"{host}\n")
                ours[int(year)][1].write(f"{host}\t{rest}")
        for names, evidence in ours.values():
            names.close()
            evidence.close()

        years, report = {}, []
        for year in sorted(ours):
            his = his_file(year)
            mine, adds = work / f"ours_{year}.txt", out / "additions" / f"{year}.txt"
            submitted = held.lines(mine)
            already = held.intersect(mine, his, work / f"held_{year}.txt")
            accepted = held.minus(mine, his, adds)
            baseline = held.lines(his)
            tlds: Counter = Counter()
            by_method: Counter = Counter()
            evidence = work / f"ev_{year}.txt"
            with adds.open(encoding="utf-8") as a, evidence.open(encoding="utf-8") as ev:
                for host in (h.rstrip("\n") for h in a):
                    tlds[host.rsplit(".", 1)[-1]] += 1
                    for row in ev:  # both sorted by host: a merge-join
                        h, ts, index, lineno, url = row.rstrip("\n").split("\t", 4)
                        if h == host:
                            break
                    source = described[int(index)]
                    by_method[source["method"]] += 1
                    ledger.writerow(
                        (year, host, source["method"], source["path"], lineno, source["sha256"],
                         replay(source["method"], ts, url))
                    )  # fmt: skip
            ee = sum((weights.get(t, Decimal(0)) * n for t, n in tlds.items()), Decimal(0))
            his_ee = REVIEWER_EXTENDED_EE_BY_YEAR[year]
            growth = ee / his_ee * 100 if his_ee else Decimal(0)
            entry = {
                "submitted_unique": submitted,
                "already_in_baseline": already,
                "accepted_new": accepted,
                "baseline_file": his.name,
                "baseline_unique": baseline,
                "baseline_sha256": file_sha(his),
                "baseline_ee": f"{his_ee:.4f}",
                "increment_ee": f"{ee:.4f}",
                "merged_unique": baseline + accepted,
                "growth_pct": f"{growth:.6f}",
                "accepted_by_method": dict(sorted(by_method.items())),
            }
            if accepted:
                merged = out / f"{year}.txt"
                with merged.open("wb") as fh:
                    merge = ["sort", "-m", "-u", str(his), str(adds)]
                    subprocess.run(merge, stdout=fh, env=_C, check=True)
                entry |= {"additions_sha256": file_sha(adds), "merged_sha256": file_sha(merged)}
            else:
                adds.unlink()
            years[str(year)] = entry
            report.append(
                (year, baseline, submitted, already, accepted, baseline + accepted,
                 f"{ee:.4f}", f"{growth:.6f}")
            )  # fmt: skip

    with (out / "dedup_report.csv").open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh, lineterminator="\n").writerows([COLUMNS, *report])
    total_ee = sum((Decimal(e["increment_ee"]) for e in years.values()), Decimal(0))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True)
    manifest = {
        "baseline": CURRENT_BASELINE_MARKER,
        "written_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit.stdout.strip(),
        "evidence_rule": RULE,
        "inputs": described,
        "globs": dict(sorted(globs.items())),
        "dropped": dict(sorted(drops.items())),
        "accepted_new": sum(e["accepted_new"] for e in years.values()),
        "increment_ee": f"{total_ee:.4f}",
        "years": years,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return manifest


def stale(out: Path) -> list[str]:
    """Why `out` no longer describes the release and the inputs it was written from."""
    path = out / "manifest.json"
    if not path.is_file():
        return [f"{path} is missing"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    if manifest["baseline"] != CURRENT_BASELINE_MARKER:
        problems.append(f"written against {manifest['baseline']}, not {CURRENT_BASELINE_MARKER}")
    recorded = [(i["path"], i["size"], i["mtime_ns"]) for i in manifest["inputs"]]
    now = [(rel(p), *stat_of(p).values()) for _, p in resolve_inputs(manifest["globs"])]
    if recorded != now:
        problems.append("an input was added, changed or removed since the export")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--in", dest="given", action="append", default=[], metavar="METHOD=GLOB")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--check", action="store_true", help="exit 1 if the output is stale")
    args = ap.parse_args()
    if args.check:
        problems = stale(args.out)
        for problem in problems:
            print(f"  {problem}")
        if problems:
            raise SystemExit(f"{args.out} is stale: rerun scripts/round/extended_export.py")
        print(f"{args.out} is current")
        return
    manifest = export(dict(item.split("=", 1) for item in args.given) or INPUTS, args.out)
    print(
        f"{args.out}: {len(manifest['inputs'])} inputs, {manifest['accepted_new']:,} additions, "
        f"{manifest['increment_ee']} EE over {len(manifest['years'])} years"
    )


if __name__ == "__main__":
    main()
