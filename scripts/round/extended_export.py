"""Write `output/extended_years/`: our 2002 to 2013 additions to his same-year files.

A host-year ships only by its own capture, as an addition to his file for that year
(`AGENTS.md`, The window). The input is the capture journal every converter already writes,
JSONL(.gz) rows `{"url", "timestamp", "status"?}`, one folder per source under
`data/raw/extended/<source>/`. The folder names a source in `SOURCES`, which fixes its method
and replay, and the register must approve it (`ark.approvals`), so a dataset never ships ahead
of its decision: an unknown or unapproved folder refuses the run before a row is read.
A fleet read's parts in `data/raw/fleet_read/<slug>/` join under the read's own source and the
method their names carry, once the register decides that source; an undecided read waits.
`--in SOURCE=GLOB` replaces the defaults, to price a dataset into a scratch `--out`.

As the core's hostname ingest does, an error lane (`hostnames.error_lane`) dates nothing, and a
journal whose family must carry a status (`hostnames.status_required`) is refused whole at a
row without one. A row is kept when its stamp's year is 2002 to 2013, its status is not 4xx or
5xx, its host passes his `HOST_RE` (`hostnames.host_of`) and has a registrable, and its TLD
existed that year (`ark.delegation.existed`). Each kept host-year carries its earliest
capture with a status, else its earliest status-less row (a crawl list's stamp is a year, not a
capture time); whatever his same-year file holds, by exact name, is dropped by `comm`.

Written, all sorted and unique under LC_ALL=C, nothing loaded whole into memory; packaging
merges each additions file with his (`package_delivery.sh`):

    additions/YYYY.txt  ours alone, for years with an addition
    evidence_ledger.csv one row per addition: its journal file, line and capture stamp
    dedup_report.csv    his merge_stats columns, one row per year we submitted to
    manifest.json       the release, the inputs with their sha256 and replay, per year the
                        counts, EE and sha256s

    uv run python scripts/round/extended_export.py [--in SOURCE=GLOB ...] [--out DIR]
    uv run python scripts/round/extended_export.py --check   # exit 1 if the output is stale
"""

import argparse
import ast
import contextlib
import csv
import functools
import glob
import gzip
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zlib
from collections import Counter
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import IO

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark import approvals, canonical, delegation, held  # noqa: E402
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
# What each input and each of his files gave the last run, so a run reads only what moved
# (`docs/lore/laws.md`, Store). An entry is keyed on its file's size and mtime_ns and on the
# screen's code, which holds because his files are frozen and a journal only grows.
CACHE = Path("data/staging/extended_rows")
# `*` takes each file's source from its folder's name.
INPUTS = {
    "*": "data/raw/extended/*/*.jsonl*",
    "fleetread": "data/raw/fleet_read/*/fleetread_*.jsonl.gz",
}
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
    hn.EOT_SOURCE: (hn.EOT_METHOD, _WAYBACK),  # eotarchive.org replays none at /wayback/
    hn.HAR_SOURCE: (hn.HAR_METHOD, "https://archive.org/details/httparchive_{ts:.4}"),  # the item
    hn.CRAWL_SOURCE: (hn.CRAWL_METHOD, ""),  # status-less; replayed as its list, `capture`
}
# The capture's URL is on its journal line and the journal's sha256 in the manifest, so neither
# repeats per row: the ledger is a third of the size.


def capture(source: str, path: Path) -> tuple[str, str]:
    """(method, replay) of one input: its source's in SOURCES, or a fleet read part's own
    method, replayed on the Wayback as the store replays it."""
    if hn.FLEETREAD_SOURCE.match(source):
        return hn.fleet_read_source(path)[1], _WAYBACK
    if source == hn.CRAWL_SOURCE:
        return hn.CRAWL_METHOD, hn.CRAWL_LISTS[path.name.split("_")[0]]
    return SOURCES[source]


LEDGER = ("year", "host", "method", "source_file", "line", "timestamp")
RULE = (
    "a 2xx or 3xx capture of the exact host, stamped in the year, from an approved capture "
    "source (status-less only outside the families that must carry one, never an error lane); "
    "host valid by his HOST_RE, TLD existing that year; minus his same-year file"
)
_STATUS = re.compile(r"[2-5][0-9][0-9]")
_C = {**os.environ, "LC_ALL": "C"}
SORT_MEMORY = "2G"  # sort's buffer: what it holds over this goes to its runs on the disk


def rel(path: Path) -> str:
    """Repo-relative, links not followed, and never a local absolute path: the ledger ships."""
    try:
        return Path(os.path.abspath(path)).relative_to(REPO).as_posix()
    except ValueError:
        return path.name


def resolve_inputs(given: dict[str, str]) -> list[tuple[str, Path]]:
    """(source, journal) for every file the globs match, refused whole unless each source is
    a capture source in `SOURCES` that the register approves; a fleet read's waits instead."""
    found = []
    for s, g in sorted(given.items()):
        for p in sorted(glob.glob(g)):
            try:
                fleet = hn.fleet_read_source(Path(p)) if s == "fleetread" else None
            except ValueError as exc:
                raise SystemExit(str(exc)) from None
            found.append((fleet[0] if fleet else Path(p).parent.name if s == "*" else s, Path(p)))
    undecided = set()
    for source in sorted({s for s, _ in found}):
        fleet = hn.FLEETREAD_SOURCE.match(source)
        if not fleet and (source not in SOURCES or SOURCES[source][0] not in WEB_METHODS):
            raise SystemExit(f"{source}: not a capture source in SOURCES, so it dates nothing")
        try:
            approvals.check(source, EVIDENCE_TYPE)
        except approvals.NotApproved as exc:
            if not fleet:
                raise SystemExit(f"{source}: {exc}") from None
            print(f"{source}: waits, {exc}", file=sys.stderr)
            undecided.add(source)
    return [(s, p) for s, p in found if s not in undecided]


def stat_of(path: Path) -> dict:
    st = path.stat()
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns}


def code_of(source: str) -> str:
    """A module's code: its ast without docstrings, so a comment, a docstring or formatting
    leaves it be and any other edit, a log line's included, changes it."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        kinds = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        if isinstance(node, kinds) and ast.get_docstring(node, clean=False) is not None:
            node.body = node.body[1:]
    return ast.dump(tree)


@functools.cache
def code_of_screen() -> str:
    """What a cached entry was made by: the window, the code it runs, the PSL, the one data file
    that code reads, and the libraries `to_registrable` calls."""
    digest = hashlib.sha256(repr(sorted(EXTENDED_YEARS)).encode())
    for part in (__file__, hn.__file__, canonical.__file__, delegation.__file__, held.__file__):
        digest.update(code_of(Path(part).read_text(encoding="utf-8")).encode())
    digest.update(canonical.PSL_PATH.read_bytes())
    for library in ("tldextract", "idna"):
        digest.update(importlib.metadata.version(library).encode())
    return digest.hexdigest()


def cache_entry(path: Path) -> Path:
    return CACHE / f"{hashlib.sha256(os.path.abspath(path).encode()).hexdigest()}.gz"


def entry_key(path: Path) -> bytes:
    """The entry's first line: the file's size and mtime_ns, and the screen's code."""
    return json.dumps([stat_of(path), code_of_screen()]).encode() + b"\n"


def cached(path: Path, key: bytes) -> tuple[dict, bytes] | None:
    """A file's entry, its facts and rows, while the file and the screen are as they were; a
    stale entry is a miss read no further than its key, a torn or foreign one a miss."""
    try:
        with cache_entry(path).open("rb") as fh:
            if fh.readline(len(key)) != key:
                return None
            head, _, rows = gzip.decompress(fh.read()).partition(b"\n")
        return json.loads(head), rows
    except (OSError, EOFError, ValueError, zlib.error):
        return None


def cache(path: Path, key: bytes, facts: dict, rows: bytes = b"") -> dict:
    """Write a file's entry under a temporary name and rename it in, so a reader never sees half.
    `key` is taken before the file is read, so a journal grown meanwhile is read again."""
    facts = {"key": json.loads(key)} | facts
    CACHE.mkdir(parents=True, exist_ok=True)
    temp = CACHE / f".{cache_entry(path).name}.{os.getpid()}"
    data = json.dumps(facts).encode() + b"\n" + rows
    temp.write_bytes(key + gzip.compress(data, compresslevel=1))
    os.replace(temp, cache_entry(path))
    return facts


def screened(path: Path) -> tuple[dict, bytes]:
    """What the manifest records of one input and its kept captures, `year<TAB>host<TAB>ts<SOH>
    line` lines, read again only when it moved. A refused journal keeps no row."""
    if hit := cached(path, key := entry_key(path)):
        return hit
    seen, rows, refused = Counter(), [], None
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
                    year, host, ts, statusless = row
                    rows.append(f"{year}\t{host}\t{statusless}{ts}\x01{lineno}\n")
    if refused:
        rows, seen = [], Counter(journal_refused=1)
    data = "".join(rows).encode()
    facts = {"sha256": file_sha(path), "kept": seen.pop("kept", 0), "drops": dict(seen)}
    return cache(path, key, facts | ({"refused": refused} if refused else {}), data), data


def read_rows(inputs: list[tuple[str, Path]], out: IO[bytes], drops: Counter) -> list[dict]:
    """Every kept capture to `out` as `year<TAB>host<TAB>ts<TAB>input<TAB>line`, and each input
    as the manifest records it."""
    described = []
    for index, (source, path) in enumerate(inputs):
        facts, data = screened(path)
        out.write(data.replace(b"\x01", b"\t%d\t" % index))
        drops.update(facts["drops"])
        if refused := facts.get("refused"):
            print(f"{rel(path)}: refused, {refused}", file=sys.stderr)
        method, replay = capture(source, path)
        described.append(
            {"source": source, "method": method, "path": rel(path), "replay": replay}
            | {"sha256": facts["sha256"], "kept": facts["kept"]}
            | ({"refused": refused} if refused else {})
            | facts["key"][0]
        )
    return described


@contextlib.contextmanager
def sorting(work: Path) -> Iterator[subprocess.Popen]:
    """`sort` under LC_ALL=C, fed on its stdin and read off its stdout, killed if the block
    raises and an error if it fails. The rows touch the disk only as its runs in `work`,
    compressed where zstd is installed, and as one year's two files (`by_year`): written whole
    beside a sorted copy, they took free space under the collectors' floor
    (`ark.disk.below_floor`) for minutes of every export."""
    cmd = ["sort", "-S", SORT_MEMORY, "-T", str(work)]
    cmd += ["--compress-program=zstd"] if shutil.which("zstd") else []
    with subprocess.Popen(cmd, env=_C, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as sort:
        try:
            yield sort
        except BaseException:
            sort.kill()
            raise
    if sort.returncode:
        raise subprocess.CalledProcessError(sort.returncode, cmd)


def by_year(rows: Iterable[str], work: Path, drops: Counter) -> Iterator[tuple[int, Path, Path]]:
    """Each year off the sorted rows, once its last row is read: the year, its names, and each
    name's row. Sorted by year, host, status-less flag, then stamp, the first row of each
    host-year is its earliest capture with a status, else its earliest status-less row."""

    def done() -> tuple[int, Path, Path]:
        names.close()
        evidence.close()
        return int(year), Path(names.name), Path(evidence.name)

    year = last = None
    for line in rows:
        this, host, rest = line.split("\t", 2)
        if this != year:
            if year is not None:
                yield done()
            year, last = this, None
            names, evidence = (
                (work / f"{kind}_{year}.txt").open("w", encoding="utf-8") for kind in ("ours", "ev")
            )
        if host == last:
            drops["duplicate"] += 1
            continue
        last = host
        names.write(f"{host}\n")
        evidence.write(f"{host}\t{rest}")
    if year is not None:
        yield done()


def screen(line: bytes, strict: bool) -> tuple[str | None, tuple | None]:
    """Why a journal line dates nothing, or None and (year, host, ts). `strict`: the
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
    return None, (year, host, ts, "0" if "status" in row else "1")


def file_sha(path: Path) -> str:
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def his_file(year: int) -> tuple[Path, dict]:
    """His file for the year, refused unless `comm` can read it byte for byte, and its line
    count and sha256, all checked again only when it moved."""
    path = baseline_dir() / f"{year}.txt"
    if not path.is_file():
        raise SystemExit(f"{path}: he has no {year} file, so nothing can be added to it")
    if hit := cached(path, key := entry_key(path)):
        return path, hit[0]
    held.check_sorted(path)
    found = subprocess.run(["grep", "-q", "-e", "[^a-z0-9.-]", "-e", "^$", str(path)], env=_C)
    if found.returncode != 1:
        raise SystemExit(f"{path}: a line is not a lowercase name (grep {found.returncode})")
    return path, cache(path, key, {"lines": held.lines(path), "sha256": file_sha(path)})


def export(globs: dict[str, str], out: Path) -> dict:
    weights = english_weights()
    drops: Counter = Counter()
    if out.exists():
        shutil.rmtree(out)
    (out / "additions").mkdir(parents=True)
    ledger_fh = (out / "evidence_ledger.csv").open("w", newline="", encoding="utf-8")
    ledger = csv.writer(ledger_fh, lineterminator="\n")
    ledger.writerow(LEDGER)
    with tempfile.TemporaryDirectory(dir=out) as tmp, ledger_fh, sorting(Path(tmp)) as sort:
        work = Path(tmp)
        inputs = resolve_inputs(globs)
        described = read_rows(inputs, sort.stdin, drops)
        sort.stdin.close()
        ordered = io.TextIOWrapper(sort.stdout, encoding="utf-8")
        years, report = {}, []
        for year, mine, evidence in by_year(ordered, work, drops):
            his, facts = his_file(year)
            adds = out / "additions" / f"{year}.txt"
            submitted = held.lines(mine)
            accepted = held.minus(mine, his, adds)
            mine.unlink()
            already = submitted - accepted  # each name of ours is his or an addition
            baseline = facts["lines"]
            tlds: Counter = Counter()
            by_method: Counter = Counter()
            with adds.open(encoding="utf-8") as a, evidence.open(encoding="utf-8") as ev:
                for host in (h.rstrip("\n") for h in a):
                    tlds[host.rsplit(".", 1)[-1]] += 1
                    for row in ev:  # both sorted by host: a merge-join
                        h, ts, index, lineno = row.rstrip("\n").split("\t")
                        ts = ts[1:]  # after the status-less flag
                        if h == host:
                            break
                    source = described[int(index)]
                    by_method[source["method"]] += 1
                    ledger.writerow((year, host, source["method"], source["path"], lineno, ts))
            evidence.unlink()
            ee = sum((weights.get(t, Decimal(0)) * n for t, n in tlds.items()), Decimal(0))
            his_ee = REVIEWER_EXTENDED_EE_BY_YEAR[year]
            growth = ee / his_ee * 100 if his_ee else Decimal(0)
            entry = {
                "submitted_unique": submitted,
                "already_in_baseline": already,
                "accepted_new": accepted,
                "baseline_file": his.name,
                "baseline_unique": baseline,
                "baseline_sha256": facts["sha256"],
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

    if globs == INPUTS:  # a scratch `--in` run leaves the release's entries be
        used = {cache_entry(p) for _, p in inputs} | {
            cache_entry(baseline_dir() / f"{y}.txt") for y in years
        }
        for unused in set(CACHE.glob("*.gz")) - used:
            unused.unlink()
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


def stale(out: Path, allow_added: bool = False) -> list[str]:
    """Why `out` no longer describes the release and the inputs it was written from.

    An input added since is a reason for the bank to export again and none for the packager
    to refuse: the export describes its own inputs exactly, and the new part ships next round.
    """
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
    recorded = {i["path"]: (i["size"], i["mtime_ns"]) for i in manifest["inputs"]}
    now = {rel(p): tuple(stat_of(p).values()) for _, p in resolve_inputs(manifest["globs"])}
    moved = any(now.get(path) != facts for path, facts in recorded.items())
    if moved or (not allow_added and now.keys() != recorded.keys()):
        problems.append(INPUTS_MOVED)
    ledger = out / "evidence_ledger.csv"
    if ledger.is_file():
        with ledger.open(encoding="utf-8") as fh:
            if fh.readline() != ",".join(LEDGER) + "\n":
                problems.append("its ledger's columns are not LEDGER's")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--in", dest="given", action="append", default=[], metavar="SOURCE=GLOB")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--check", action="store_true", help="exit 1 if the output is stale")
    ap.add_argument(
        "--allow-added", action="store_true", help="with --check: an input added since is current"
    )
    args = ap.parse_args()
    if args.check:
        problems = stale(args.out, allow_added=args.allow_added)
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
