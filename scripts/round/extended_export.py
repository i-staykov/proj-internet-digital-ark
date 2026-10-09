"""Write `output/extended_years/`: our 2002 to 2013 additions to his same-year files.

A host-year ships only by its own capture, as an addition to his file for that year
(`AGENTS.md`, The window). The input is the capture journal every converter already writes,
JSONL(.gz) rows `{"url", "timestamp", "status"?}`, one folder per source under
`data/raw/extended/<source>/`. The folder names a source in `SOURCES`, which fixes its method
and replay, and the register must approve it (`ark.approvals`), so a dataset never ships ahead
of its decision: an unknown or unapproved folder refuses the run before a row is read.
`--in SOURCE=GLOB` replaces the defaults, to price a dataset into a scratch `--out`.

As the core's hostname ingest does, an error lane (`hostnames.error_lane`) dates nothing, and a
journal whose family must carry a status (`hostnames.status_required`) is refused whole at a
row without one. A row is kept when its stamp's year is 2002 to 2013, its status is not 4xx or
5xx, its host passes his `HOST_RE` (`hostnames.host_of`) and has a registrable, and its TLD
existed that year (`ark.delegation.existed`). Each kept host-year carries its earliest
capture; whatever his same-year file holds, by exact name, is dropped by `comm`.

Written, all sorted and unique under LC_ALL=C, nothing loaded whole into memory; packaging
merges each additions file with his (`package_delivery.sh`):

    additions/YYYY.txt  ours alone, for years with an addition
    evidence_ledger.csv one row per addition: its capture, file, line and the file's sha256
    dedup_report.csv    his merge_stats columns, one row per year we submitted to
    manifest.json       the release, the inputs, and per year the counts, EE and sha256s

    uv run python scripts/round/extended_export.py [--in SOURCE=GLOB ...] [--out DIR]
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

from ark import approvals, held  # noqa: E402
from ark import hostnames as hn  # noqa: E402
from ark.baseline import (  # noqa: E402
    CURRENT_BASELINE_MARKER,
    EXTENDED_YEARS,
    REVIEWER_EXTENDED_EE_BY_YEAR,
    baseline_dir,
)
from ark.canonical import to_registrable  # noqa: E402
from ark.delegation import existed  # noqa: E402
from ark.english_share import english_weights  # noqa: E402
from ark.evidence_types import WEB_METHODS  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "merge_against_baseline", Path(__file__).with_name("merge_against_baseline.py")
)
_merge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_merge)
COLUMNS = _merge.COLUMNS

OUT = Path("output/extended_years")
# `*` takes each file's source from its folder's name.
INPUTS = {"*": "data/raw/extended/*/*.jsonl*"}
# The capture sources a folder may name, each the core ingests as `cdx_timestamp`: its method,
# and where a reader replays one of its captures. Anything else is not a capture and fails closed.
EVIDENCE_TYPE = "cdx_timestamp"
_WAYBACK = "https://web.archive.org/web/{ts}/{url}"
SOURCES = {
    hn.SOURCE_NAME: (hn.SWEEP_METHOD, _WAYBACK),
    hn.EARLY_WEB_SOURCE: (hn.EARLY_WEB_METHOD, _WAYBACK),
    hn.DARTMOUTH_ARCS_SOURCE: (hn.DARTMOUTH_ARCS_METHOD, _WAYBACK),
    hn.HOSTCDX_SOURCE: (hn.HOSTCDX_METHOD, _WAYBACK),
    hn.ARQUIVO_SOURCE: (hn.ARQUIVO_METHOD, "https://arquivo.pt/wayback/{ts}/{url}"),
}
LEDGER = ("year", "host", "method", "source_file", "line", "source_sha256", "evidence_url")
RULE = (
    "a 2xx or 3xx capture of the exact host, stamped in the year, from an approved capture "
    "source (status-less only outside the families that must carry one, never an error lane); "
    "host valid by his HOST_RE, TLD existing that year; minus his same-year file"
)
_STATUS = re.compile(r"[2-5][0-9][0-9]")
_C = {**os.environ, "LC_ALL": "C"}


def rel(path: Path) -> str:
    """Repo-relative, links not followed, and never a local absolute path: the ledger ships."""
    try:
        return Path(os.path.abspath(path)).relative_to(REPO).as_posix()
    except ValueError:
        return path.name


def resolve_inputs(given: dict[str, str]) -> list[tuple[str, Path]]:
    """(source, journal) for every file the globs match, refused whole unless each source is
    a capture source in `SOURCES` that the register approves."""
    found = [
        (Path(p).parent.name if s == "*" else s, Path(p))
        for s, g in sorted(given.items())
        for p in sorted(glob.glob(g))
    ]
    for source in sorted({s for s, _ in found}):
        if source not in SOURCES or SOURCES[source][0] not in WEB_METHODS:
            raise SystemExit(f"{source}: not a capture source in SOURCES, so it dates nothing")
        try:
            approvals.check(source, EVIDENCE_TYPE)
        except approvals.NotApproved as exc:
            raise SystemExit(f"{source}: {exc}") from None
    return found


def stat_of(path: Path) -> dict:
    st = path.stat()
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns}


def read_rows(inputs: list[tuple[str, Path]], rows_out: Path, drops: Counter) -> list[dict]:
    """Every kept capture as `year<TAB>host<TAB>ts<TAB>input<TAB>line<TAB>url`, and each input
    as the manifest records it. A refused journal's rows are cut back out."""
    described = []
    with rows_out.open("wb") as out:
        for index, (source, path) in enumerate(inputs):
            seen, start, refused = Counter(), out.tell(), None
            if hn.error_lane(path):
                refused = "an error lane, whose captures are errors"
            else:
                strict = hn.status_required(path)
                with (gzip.open if path.suffix == ".gz" else open)(path, "rb") as stream:
                    for lineno, line in enumerate(stream, 1):
                        reason, row = screen(line, strict)
                        if reason == "no_status":
                            refused = f"line {lineno} carries no capture status"
                            break
                        seen[reason or "kept"] += 1
                        if row:
                            year, host, ts, url = row
                            out.write(f"{year}\t{host}\t{ts}\t{index}\t{lineno}\t{url}\n".encode())
            if refused:
                out.seek(start)
                out.truncate()
                seen = Counter(journal_refused=1)
                print(f"{rel(path)}: refused, {refused}", file=sys.stderr)
            kept = seen.pop("kept", 0)
            drops.update(seen)
            described.append(
                {"source": source, "method": SOURCES[source][0], "path": rel(path)}
                | {"sha256": file_sha(path), "kept": kept}
                | ({"refused": refused} if refused else {})
                | stat_of(path)
            )
    return described


def screen(line: bytes, strict: bool) -> tuple[str | None, tuple | None]:
    """Why a journal line dates nothing, or None and (year, host, ts, url). `strict`: the
    journal's family must carry a status, so a row without one is `no_status`."""
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
    elif strict:
        return "no_status", None
    ts = str(row.get("timestamp", ""))
    if len(ts) != 14 or not ts.isdigit():
        return "bad_timestamp", None
    year = int(ts[:4])
    if year not in EXTENDED_YEARS:
        return "outside_window", None
    url = " ".join(str(row.get("url", "")).split())
    host = hn.host_of(url)
    if host is None:
        return "invalid_host", None
    if not existed(host.rsplit(".", 1)[-1], year):
        return "tld_did_not_exist", None
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
                         SOURCES[source["source"]][1].format(ts=ts, url=url))
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
                entry["additions_sha256"] = file_sha(adds)
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


# Inputs that moved on leave the export pricing exactly what it read, so `just state` still
# quotes its GATE lines, stamped with its `written_at`.
INPUTS_MOVED = "an input was added, changed or removed since the export"


def stale(out: Path) -> list[str]:
    """Why `out` no longer describes the release and the inputs it was written from."""
    path = out / "manifest.json"
    if not path.is_file():
        # Nothing to export and nothing written is current: the GATE lines price no addition.
        return [f"{path} is missing"] if out.exists() or resolve_inputs(INPUTS) else []
    manifest = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    if manifest["baseline"] != CURRENT_BASELINE_MARKER:
        problems.append(f"written against {manifest['baseline']}, not {CURRENT_BASELINE_MARKER}")
    if any(int(year) not in EXTENDED_YEARS for year in manifest.get("years", {})):
        problems.append("holds a year outside 2002 to 2013")
    recorded = [(i["path"], i["size"], i["mtime_ns"]) for i in manifest["inputs"]]
    now = [(rel(p), *stat_of(p).values()) for _, p in resolve_inputs(manifest["globs"])]
    if recorded != now:
        problems.append(INPUTS_MOVED)
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--in", dest="given", action="append", default=[], metavar="SOURCE=GLOB")
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
