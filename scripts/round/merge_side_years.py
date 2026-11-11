"""Merge each `output/side_years/<name>/` into `output/extended_years/`, after each export.

A side run is `extended_export.py --in SOURCE=GLOB --out output/side_years/<name>` on the machine
that holds that source's journals: the same screen, the same net of his same-year file, its own
ledger and manifest. Here its additions join ours: per year the union, `LC_ALL=C` sorted; the
ledger one row a name, ours where both hold it, in the order `verify.sh` hashes it; the manifest's
counts, sha256 and EE for that year recomputed, and the run recorded under `side`, so `--check`,
which reads `inputs` alone, is unchanged. Idempotent: a run already merged at the same
`written_at` is skipped, and the extended export rewrites the folder whole, so the bank and the
ship run this after it.

    uv run python scripts/round/merge_side_years.py [--out output/extended_years] [--side DIR]
"""

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from ark.english_share import english_weights  # noqa: E402

_C = {"LC_ALL": "C", "PATH": "/usr/bin:/bin"}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 22):
            digest.update(chunk)
    return digest.hexdigest()


def rows(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        yield next(reader)
        yield from reader


def merge_ledgers(ours: Path, side: Path, out: Path) -> None:
    """Both sorted by (year, host) as written; one row a (year, host), ours first."""
    a, b = rows(ours), rows(side)
    head = next(a)
    if next(b) != head:
        raise SystemExit(f"{side} has other ledger columns than {ours}")
    x, y = next(a, None), next(b, None)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(head)
        while x or y:
            kx = (x[0], x[1].encode()) if x else None
            ky = (y[0], y[1].encode()) if y else None
            if y is None or (x is not None and kx <= ky):
                w.writerow(x)
                if ky == kx:
                    y = next(b, None)
                x = next(a, None)
            else:
                w.writerow(y)
                y = next(b, None)


def merge(out: Path, side_root: Path) -> list[str]:
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    done = manifest.setdefault("side", {})
    merged = []
    weights = english_weights()
    for side in sorted(p for p in side_root.glob("*") if (p / "manifest.json").is_file()):
        theirs = json.loads((side / "manifest.json").read_text(encoding="utf-8"))
        if done.get(side.name, {}).get("written_at") == theirs["written_at"]:
            continue
        if theirs["baseline"] != manifest["baseline"]:
            raise SystemExit(f"{side} was screened against {theirs['baseline']}")
        part = out / "evidence_ledger.csv.part"
        merge_ledgers(out / "evidence_ledger.csv", side / "evidence_ledger.csv", part)
        part.replace(out / "evidence_ledger.csv")
        for year, entry in sorted(theirs["years"].items()):
            if not entry["accepted_new"]:
                continue
            ours, add = out / "additions" / f"{year}.txt", side / "additions" / f"{year}.txt"
            union = out / "additions" / f"{year}.txt.part"
            sources = [str(p) for p in (ours, add) if p.is_file()]
            subprocess.run(["sort", "-m", "-u", "-o", str(union), *sources], env=_C, check=True)
            union.replace(ours)
            tlds = Counter()
            with ours.open(encoding="utf-8") as fh:
                for host in fh:
                    tlds[host.rstrip("\n").rsplit(".", 1)[-1]] += 1
            ee = sum((weights.get(t, Decimal(0)) * n for t, n in tlds.items()), Decimal(0))
            mine = manifest["years"].setdefault(year, {**entry, "accepted_new": 0})
            accepted = sum(tlds.values())
            his_ee = Decimal(mine["baseline_ee"])
            mine.update(
                accepted_new=accepted,
                submitted_unique=mine["already_in_baseline"] + accepted,
                additions_sha256=sha(ours),
                increment_ee=f"{ee:.4f}",
                merged_unique=mine["baseline_unique"] + accepted,
                growth_pct=f"{(ee / his_ee * 100 if his_ee else Decimal(0)):.6f}",
            )
        done[side.name] = {k: theirs[k] for k in ("written_at", "commit", "globs", "inputs")}
        merged.append(side.name)
    if merged:
        years = manifest["years"].values()
        manifest["accepted_new"] = sum(e["accepted_new"] for e in years)
        total = sum((Decimal(e["increment_ee"]) for e in years), Decimal(0))
        manifest["increment_ee"] = f"{total:.4f}"
        manifest_path.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
        report = out / "dedup_report.csv"
        with report.open(newline="", encoding="utf-8") as fh:
            head = next(csv.reader(fh))
        with report.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(head)
            for year, e in sorted(manifest["years"].items()):
                w.writerow((year, e["baseline_unique"], e["submitted_unique"],
                            e["already_in_baseline"], e["accepted_new"], e["merged_unique"],
                            e["increment_ee"], e["growth_pct"]))  # fmt: skip
    return merged


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=Path("output/extended_years"))
    ap.add_argument("--side", type=Path, default=Path("output/side_years"))
    args = ap.parse_args()
    if not args.side.is_dir() or not (args.out / "manifest.json").is_file():
        print("side years: none to merge")
        return
    merged = merge(args.out, args.side)
    print(f"side years: merged {', '.join(merged) if merged else 'none new'}")


if __name__ == "__main__":
    main()
