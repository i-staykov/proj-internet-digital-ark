"""The reviewer's ISC validation protocol, run on one of our non-web candidate classes.

His experiment on the ISC survey hosts (his release, `isc_survey_hostnames/
ISC_DNS_Hostname_IA_CDX_Validation_Experiment.md`): a seeded uniform reservoir sample of 1,800
hostname-year records, one exact-host ask a record (`url=<hostname>/*`, 1996 to 2013, any
status, `limit=1`), and a transient error retried, never counted as a miss. ISC scored 48 of
1,800.

`draw` samples a class out of the shipped provenance, `header_candidates_provenance.csv`, by a
regex on its `source` column; `ask` queries each sampled record and keeps a receipt an ask.
`ask` is a CDX client: it runs only on a lane the channel rule gives it, one ask at a time.

    uv run python scripts/round/class_validation.py draw PROVENANCE.csv OUT --sources '_lease_'
    uv run python scripts/round/class_validation.py ask OUT
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
from collections.abc import Callable, Iterable
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark.cdx import CDX_ENDPOINT, RateGovernor, _retry_after_seconds, http_fetch  # noqa: E402

N, SEED = 1800, 20261110
FIELDS = ("hostname", "target_year", "source", "record_location", "source_url")


def draw(rows: Iterable[dict], sources: str, n: int = N, seed: int = SEED) -> tuple[list, int]:
    """A uniform reservoir sample of `n` records whose source matches, and the population."""
    wanted, rng, kept, seen = re.compile(sources), random.Random(seed), [], 0
    for row in rows:
        if not wanted.search(row["source"]):
            continue
        seen += 1
        if len(kept) < n:
            kept.append(row)
        elif (slot := rng.randrange(seen)) < n:
            kept[slot] = row
    return kept, seen


def ask_url(hostname: str) -> str:
    asked = "from=1996&to=2013&fl=timestamp,original,status&limit=1&output=json"
    return f"{CDX_ENDPOINT}?url={hostname}/*&{asked}"


def outcome(status: int, body: str) -> str:
    """`capture`, `no_capture`, or `error`: only an answered ask is a result."""
    if status != 200:
        return "error"
    try:
        rows = json.loads(body) if body.strip() else []
    except ValueError:
        return "error"
    return "capture" if len(rows) > 1 else "no_capture"


def ask(out: Path, fetch: Callable[[str], tuple[int, str]], gov: RateGovernor, passes: int) -> dict:
    """Ask every sampled record not answered yet, up to `passes` times; write the summary."""
    with (out / "sample_manifest.csv").open(newline="", encoding="utf-8") as fh:
        sample = list(csv.DictReader(fh))
    receipts, final = out / "receipts.jsonl", {}
    if receipts.is_file():
        for line in receipts.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["outcome"] != "error":
                final[r["hostname"], r["target_year"]] = r["outcome"]
    with receipts.open("a", encoding="utf-8") as log:
        for _ in range(passes):
            todo = [r for r in sample if (r["hostname"], r["target_year"]) not in final]
            for row in todo:
                gov.wait()
                url = ask_url(row["hostname"])
                status, body = fetch(url)
                got = outcome(status, body)
                gov.on_success() if got != "error" else gov.on_throttle(_retry_after_seconds(body))
                log.write(
                    json.dumps(
                        {
                            "hostname": row["hostname"],
                            "target_year": row["target_year"],
                            "url": url,
                            "status": status,
                            "body": body[:500],
                            "outcome": got,
                            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        }
                    )
                    + "\n"
                )
                log.flush()
                if got != "error":
                    final[row["hostname"], row["target_year"]] = got
            if len(final) == len(sample):
                break
    captures = sum(v == "capture" for v in final.values())
    summary = {
        "sampled": len(sample),
        "capture": captures,
        "no_capture": len(final) - captures,
        "unresolved": len(sample) - len(final),
        "share": round(captures / len(sample), 6) if sample else 0.0,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    hits = sorted({h for (h, _y), v in final.items() if v == "capture"})
    (out / "captured_hosts.txt").write_text("".join(h + "\n" for h in hits), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="step", required=True)
    d = sub.add_parser("draw")
    d.add_argument("provenance", type=Path)
    d.add_argument("out", type=Path)
    d.add_argument("--sources", required=True, help="regex on the provenance source column")
    a = sub.add_parser("ask")
    a.add_argument("out", type=Path)
    a.add_argument("--passes", type=int, default=6)
    args = parser.parse_args(argv)
    if args.step == "draw":
        with args.provenance.open(newline="", encoding="utf-8") as fh:
            kept, seen = draw(csv.DictReader(fh), args.sources)
        args.out.mkdir(parents=True, exist_ok=True)
        with (args.out / "sample_manifest.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, FIELDS, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            writer.writerows(kept)
        note = {"sources": args.sources, "population": seen, "sampled": len(kept), "seed": SEED}
        (args.out / "draw.json").write_text(json.dumps(note, indent=1) + "\n", encoding="utf-8")
        print(json.dumps(note))
        return 0
    summary = ask(args.out, http_fetch(), RateGovernor(delay=1.0, min_delay=1.0), args.passes)
    print(json.dumps(summary))
    return 0 if summary["unresolved"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
