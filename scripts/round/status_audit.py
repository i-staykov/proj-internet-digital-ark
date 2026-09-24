"""Which captures behind the hostname records answered with an error, read from the raw CDX.

    uv run python scripts/round/status_audit.py [--families nypw,early_web]

The hostname journals read before their rows carried a status name none, so this goes back
to the CDX they were cut from, under `data/raw/`: the NYPW TimeMaps and first-capture index,
the Early Web parts, the Dartmouth ARCS item indexes and the node CDX. It opens no store.

**An error capture is a (host, second) that some raw row answered 4xx or 5xx and no raw row
of the same family answered 2xx or 3xx.** An evidence row names the host and the second, not
the URL, so a same-second 200 of another page on the host still backs it.

It writes under `data/audit/`:

    status_errors.tsv.gz   hostname, ts, status, family: every error capture, sorted
    status_shipped.tsv     each shipped record resting on one: repoint it to the earliest
                           2xx or 3xx of its host-year, or retract it when there is none
    status_audit.json      the summary it prints

A family whose raw is gone keeps the rows the last audit wrote for it.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark.hostnames import YEARS, host_of  # noqa: E402

RAW = REPO / "data/raw"
NETNEW = REPO / "output/netnew"
OUT = REPO / "data/audit"
WINDOW = {str(y).encode() for y in YEARS}


@dataclass(frozen=True)
class Family:
    raw: tuple[str, ...]  # globs under data/raw
    cols: tuple[int, int, int]  # ts, url, status, as space-split fields
    journals: tuple[str, ...]
    # the group whose raw decides a shipped record of these (source, method) pairs
    group: str


FAMILIES = {
    "nypw": Family(
        ("nypw_timemaps/*.cdx.gz", "nypw/*firstcdx.gz"),
        (2, 3, 5),
        ("nypw_hostgrain/*.jsonl.gz", "nypw_firstcdx_hostgrain/*.jsonl.gz"),
        "ia_hostgrain",
    ),
    "early_web": Family(
        ("early_web/*.cdx.gz",),
        (1, 2, 4),
        ("early_web_hostgrain/*.jsonl.gz", "early_web_nonok_hostgrain/*.jsonl.gz"),
        "ia_hostgrain",
    ),
    "dartmouth_arcs": Family(
        ("dartmouth_arcs/*.cdx.gz",),
        (1, 2, 4),
        ("dartmouth_arcs_hostgrain/*.jsonl.gz",),
        "dartmouth_arcs",
    ),
    "host_cdx": Family(
        ("host_cdx/*.hostcdx.gz",),
        (1, 2, 4),
        ("hostcdx_hostgrain/*.jsonl.gz", "hostcdx_hostgrain_3xx/*.jsonl.gz"),
        "host_cdx",
    ),
}
# The shipped (source, method) pairs each group's raw decides.
GROUPS = {
    "ia_hostgrain": {
        ("ia_cdx_hostnames", "nypw_timemap_hostgrain"): "nypw",
        ("early_web_cdx_hostnames", "early_web_hostgrain"): "early_web",
    },
    "dartmouth_arcs": {("dartmouth_arcs_cdx_hostnames", "bulk_cdx_file"): "dartmouth_arcs"},
    "host_cdx": {("ia_node_host_cdx_hostnames", "bulk_cdx_file"): "host_cdx"},
}

Key = tuple[bytes, bytes]  # (host, ts)


def cheap_host(url: bytes) -> bytes:
    """`host_of` without its validation, on bytes: equal to it wherever it returns a host."""
    rest = url.split(b"://", 1)[-1]
    return rest.split(b"/", 1)[0].split(b":", 1)[0].strip().lower().rstrip(b".")


def rows(path: Path, cols: tuple[int, int, int]):
    """(ts, url, status) of every in-window raw row, streamed through `gzip -dc`."""
    ts_i, url_i, st_i = cols
    proc = subprocess.Popen(["gzip", "-dc", str(path)], stdout=subprocess.PIPE, bufsize=1 << 20)
    assert proc.stdout is not None
    for line in proc.stdout:
        fields = line.split(b" ", st_i + 1)
        if len(fields) <= st_i:
            continue
        ts = fields[ts_i]
        if len(ts) != 14 or ts[:4] not in WINDOW or not ts.isdigit():
            continue
        yield ts, fields[url_i], fields[st_i].rstrip(b"\n")
    if proc.wait() != 0:
        raise SystemExit(f"{path}: gzip exited {proc.returncode}; the audit is incomplete")


def status_class(status: bytes) -> str:
    if len(status) == 3 and status.isdigit() and status[:1] in b"2345":
        return status[:1].decode() + "xx"
    return "other"


def shipped_rows(netnew: Path) -> list[dict[str, str]]:
    """Every shipped record of an audited (source, method), with its host and second."""
    out = []
    audited = {pair: group for group, pairs in GROUPS.items() for pair in pairs}
    for name, grain in (
        ("hostnames_evidence_manifest.csv", "hostname"),
        ("evidence_manifest.csv", "domain"),
    ):
        with (netnew / name).open(newline="", encoding="utf-8") as fh:
            for rec in csv.DictReader(fh):
                pair = (rec["source"], rec["acquisition_method"])
                parts = rec["evidence_value"].split()
                if pair not in audited or len(parts) < 4 or parts[:2] != ["cdx", "capture"]:
                    continue
                out.append(
                    {
                        "name": rec[grain],
                        "grain": grain,
                        "year": rec["assigned_year"],
                        "host": parts[-1],
                        "ts": parts[2],
                        "method": pair[1],
                        "family": GROUPS[audited[pair]][pair],
                        "group": audited[pair],
                    }
                )
    return out


def audit_family(
    fam: Family, files: list[Path], want: set[Key], seen_at: dict, ok_year: dict
) -> dict:
    """The error captures of one family, and what its raw says about the shipped keys."""
    counts: Counter[str] = Counter()
    errors: dict[Key, bytes] = {}
    want_hosts = {h for h, _ in want}
    for path in files:
        for ts, url, status in rows(path, fam.cols):
            cls = status_class(status)
            counts[cls] += 1
            host = cheap_host(url)
            if host in want_hosts:
                key = (host, ts)
                if key in want:
                    seen_at.setdefault(key, set()).add(cls)
                if cls in ("2xx", "3xx"):
                    hy = (host, ts[:4])
                    if hy not in ok_year or ts < ok_year[hy]:
                        ok_year[hy] = ts
            if cls in ("4xx", "5xx"):
                valid = host_of(url.decode("latin-1"))
                key = (valid.encode(), ts) if valid else None
                if key and (key not in errors or status < errors[key]):
                    errors[key] = status
    # a same-second 2xx or 3xx of the host backs the evidence row, so it is no error capture
    error_hosts = {h for h, _ in errors}
    shadowed = 0
    for path in files:
        for ts, url, status in rows(path, fam.cols):
            if status_class(status) in ("2xx", "3xx"):
                host = cheap_host(url)
                if host in error_hosts and errors.pop((host, ts), None) is not None:
                    shadowed += 1
    return {"files": len(files), "rows": dict(counts), "errors": errors, "shadowed": shadowed}


def journal_hits(fam: Family, errors: dict[Key, bytes]) -> dict:
    """Journal rows whose capture is an error capture, with a few named."""
    hits, host_years, named = 0, set(), []
    for path in sorted(p for pattern in fam.journals for p in RAW.glob(pattern)):
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if "status" in row and str(row["status"])[:1] in "45":
                    continue  # an error row that says so is where it belongs
                host = host_of(str(row.get("url", "")))
                ts = str(row.get("timestamp", ""))
                if host and (host.encode(), ts.encode()) in errors:
                    hits += 1
                    host_years.add((host, ts[:4]))
                    if len(named) < 10:
                        named.append(f"{host} {ts} in {path.name}")
    return {"rows": hits, "host_years": len(host_years), "named": named}


def carried(path: Path, family: str) -> dict[Key, bytes]:
    """The rows the last audit wrote for a family this run did not read."""
    if not path.is_file():
        return {}
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        return {
            (r["hostname"].encode(), r["ts"].encode()): r["status"].encode()
            for r in reader
            if r["family"] == family
        }


def carried_shipped(path: Path, groups: set[str]) -> list[str]:
    """The shipped rows the last audit wrote for groups this run did not read whole."""
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)[1:]
    return [line for line in lines if FAMILIES[line.split("\t")[4]].group in groups]


def write_gz(path: Path, lines: list[str]) -> None:
    part = path.with_name(path.name + ".part")
    with part.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        gz.write("".join(lines).encode())
    part.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--families", default=",".join(FAMILIES), help="comma-separated subset")
    ap.add_argument("--netnew", type=Path, default=NETNEW, help="the export's manifests")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    names = [n for n in args.families.split(",") if n]
    args.out.mkdir(parents=True, exist_ok=True)
    errors_path = args.out / "status_errors.tsv.gz"

    shipped = shipped_rows(args.netnew)
    want = {(r["host"].encode(), r["ts"].encode()) for r in shipped}
    seen_at: dict[str, dict[Key, set[str]]] = {g: {} for g in GROUPS}
    ok_year: dict[str, dict[tuple[bytes, bytes], bytes]] = {g: {} for g in GROUPS}
    summary_path = args.out / "status_audit.json"
    before = json.loads(summary_path.read_text()) if summary_path.is_file() else {}

    summary: dict[str, dict] = {"families": {}, "shipped": {}}
    errors: dict[str, dict[Key, bytes]] = {}
    read: set[str] = set()
    for name, fam in FAMILIES.items():
        files = sorted(p for pattern in fam.raw for p in RAW.glob(pattern))
        if name not in names or not files:
            # never drop a family: what this run did not read, the last audit still says
            errors[name] = carried(errors_path, name)
            summary["families"][name] = before.get("families", {}).get(name, {})
            if name in names:
                summary["families"][name] = {"raw": "absent", "carried": len(errors[name])}
                print(f"{name}: raw absent, {len(errors[name]):,} error captures carried")
            continue
        for pattern in fam.raw:
            if not any(True for _ in RAW.glob(pattern)):
                print(f"{name}: no raw file matches {pattern}, read without it")
        got = audit_family(fam, files, want, seen_at[fam.group], ok_year[fam.group])
        read.add(name)
        errors[name] = got.pop("errors")
        got["error_captures"] = len(errors[name])
        got["journals"] = journal_hits(fam, errors[name])
        summary["families"][name] = got
        print(
            f"{name}: {got['files']} raw files, in window {got['rows']}; "
            f"{got['error_captures']:,} error captures ({got['shadowed']:,} backed by a "
            f"same-second 2xx or 3xx); journal rows on one: {got['journals']['rows']:,} "
            f"({got['journals']['host_years']:,} host-years)"
        )
        for line in got["journals"]["named"]:
            print(f"    {line}")

    lines = ["hostname\tts\tstatus\tfamily\n"]
    body = [
        f"{h.decode()}\t{t.decode()}\t{s.decode()}\t{name}\n"
        for name, errs in errors.items()
        for (h, t), s in errs.items()
    ]
    write_gz(errors_path, lines + sorted(body))

    report = ["hostname\tyear\tts\tstatus\tfamily\tmethod\tgrain\taction\trepoint_ts\n"]
    # a group is classified only when every family of it was read, or it keeps the last audit's
    whole = {g for g in GROUPS if all(n in read for n, f in FAMILIES.items() if f.group == g)}
    report += carried_shipped(args.out / "status_shipped.tsv", set(GROUPS) - whole)
    for group, pairs in GROUPS.items():
        mine = [r for r in shipped if r["group"] == group]
        if group not in whole:
            summary["shipped"][group] = before.get("shipped", {}).get(group, {})
            continue
        if not mine:
            continue
        tally: Counter[str] = Counter()
        by_family: Counter[str] = Counter()
        group_errors = {
            k: s
            for n, errs in errors.items()
            if FAMILIES[n].group == group
            for k, s in errs.items()
        }
        for r in mine:
            key = (r["host"].encode(), r["ts"].encode())
            classes = seen_at[group].get(key)
            if not classes:
                tally["not_in_raw"] += 1
            elif classes & {"2xx", "3xx"}:
                tally["ok"] += 1
            elif classes & {"4xx", "5xx"}:
                repoint = ok_year[group].get((key[0], key[1][:4]))
                action = "repoint" if repoint else "retract"
                tally[action] += 1
                by_family[f"{action}_{r['family']}"] += 1
                status = group_errors.get(key, b"").decode()
                report.append(
                    f"{r['host']}\t{r['year']}\t{r['ts']}\t{status}\t{r['family']}\t"
                    f"{r['method']}\t{r['grain']}\t{action}\t"
                    f"{repoint.decode() if repoint else ''}\n"
                )
            else:
                tally["other_status"] += 1
        on_error = tally["repoint"] + tally["retract"]
        summary["shipped"][group] = {"rows": len(mine), **tally, **by_family}
        methods = " + ".join(sorted({m for _, m in pairs}))
        detail = ", ".join(f"{by_family[f'retract_{f}']} {f}" for f in sorted(set(pairs.values())))
        print(
            f"shipped: {len(mine):,} {methods} records ({group}), {on_error:,} on a 4xx or 5xx "
            f"capture: {tally['retract']:,} to retract ({detail}), {tally['repoint']:,} to "
            f"repoint, {tally['not_in_raw']:,} not in the raw"
        )
    (args.out / "status_shipped.tsv").write_text(report[0] + "".join(sorted(report[1:])))
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    shown = errors_path.relative_to(REPO) if errors_path.is_relative_to(REPO) else errors_path.name
    print(f"wrote {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
