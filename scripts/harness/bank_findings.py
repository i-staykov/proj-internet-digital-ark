"""The scribe, as code: book fleet findings into the register, deterministically.

The sonnet scribe did four mechanical things every round: append one register row per
finding, write the result line onto the hypothesis block, re-rank the triage queue, and
leave the working tree ready to commit. Nothing in that list needs a model once the
findings carry their fields in a fixed shape, and a model was the second-largest token
cost in the loop. So this is that scribe, at zero tokens.

It never ingests and never decides: a FIND is booked exactly like a CLOSED, and the
admitter (a model, run separately by `just bank`) is the only thing that touches the
store. Findings whose file lacks a parseable verdict are booked as BLOCKED with the
file named, which is the fleet's fallback contract carried through.

    uv run python scripts/harness/bank_findings.py data/fleet_findings/incoming \\
        --hypotheses ~/Documents/GitHub/ark-fleet/hypotheses.md --run-label wave-123
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTER = REPO / "docs/sources.md"
TABLE_HEADING = "## Evaluated and rejected"

_FIELD = re.compile(r"^([a-z_ ]+):\s*(.*)$")
_URL = re.compile(r"https?://[^\s`)\"']+")


def parse_finding(path: Path) -> dict:
    slug = path.stem
    fields: dict[str, str] = {}
    current = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "):
            slug = line[2:].strip() or slug
            continue
        m = _FIELD.match(line)
        if m and m.group(1).strip() in {
            "verdict",
            "ee",
            "probe",
            "what dates one item",
            "artifact",
            "measurement",
            "screen check",
            "method",
            "next",
            "reason",
            "reviewed",
            "repriced",
        }:
            current = m.group(1).strip()
            fields[current] = m.group(2).strip()
        elif current and (line.startswith(("  ", "\t")) or not line):
            fields[current] = (fields[current] + " " + line.strip()).strip()
    verdict = fields.get("verdict", "").split()[0].upper() if fields.get("verdict") else "BLOCKED"
    if verdict not in {"FIND", "CLOSED", "BLOCKED", "SKIPPED"}:
        verdict = "BLOCKED"
    ee_match = re.search(r"[\d,]+(?:\.\d+)?", fields.get("ee", "0"))
    ee = ee_match.group(0).replace(",", "") if ee_match else "0"
    return {"slug": slug, "verdict": verdict, "ee": ee, "fields": fields}


def first_clause(text: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    for stop in (". ", "; "):
        if stop in text[:limit]:
            return text[: text.index(stop) + 1]
    return text[:limit]


def register_row(f: dict, run_label: str) -> str:
    day = dt.date.today().isoformat()
    dates = first_clause(f["fields"].get("what dates one item", ""), 160) or "not stated"
    probe = first_clause(f["fields"].get("probe", "") or f["fields"].get("reason", ""))
    url = _URL.search(f["fields"].get("artifact", ""))
    link = f" Artifact: <{url.group(0)}>." if url else ""
    return (
        f"| **{f['slug']} ({day}, fleet {run_label})** | **{f['verdict']} at {f['ee']} EE, "
        f"against the ark-data sync.** What dates one item: {dates}.{link} {probe} |"
    )


def append_rows(rows: list[str]) -> None:
    text = REGISTER.read_text(encoding="utf-8")
    at = text.index(TABLE_HEADING)
    # The table starts two lines under the heading; insert right after the header row
    # separator so newest entries lead, matching how the scribe wrote them.
    sep = text.index("|---|---|", at)
    line_end = text.index("\n", sep) + 1
    REGISTER.write_text(text[:line_end] + "\n".join(rows) + "\n" + text[line_end:], "utf-8")


def write_result_lines(hypo: Path, findings: list[dict]) -> int:
    text = hypo.read_text(encoding="utf-8")
    wrote = 0
    for f in findings:
        head = f"## {f['slug']} |"
        if head not in text:
            continue
        block_start = text.index(head)
        block_end = text.find("\n## ", block_start + 1)
        block_end = len(text) if block_end == -1 else block_end
        if "\nresult:" in text[block_start:block_end]:
            continue
        clause = first_clause(f["fields"].get("probe", "") or f["fields"].get("reason", ""), 160)
        line = f"result: {f['verdict']}, {f['ee']} EE, {clause}\n"
        text = text[:block_end].rstrip("\n") + "\n" + line + text[block_end:].lstrip("\n")
        wrote += 1
    hypo.write_text(text, "utf-8")
    return wrote


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("incoming", type=Path)
    ap.add_argument("--hypotheses", type=Path, required=True)
    ap.add_argument("--run-label", default="run")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--results-only",
        action="store_true",
        help="only the result lines, so the next pick sees them before the admitter runs",
    )
    args = ap.parse_args()

    files = sorted(args.incoming.glob("*.md"))
    if not files:
        print("nothing to bank")
        return 0
    findings = [parse_finding(p) for p in files]
    rows = [register_row(f, args.run_label) for f in findings]
    if args.dry_run:
        print("\n".join(rows))
        return 0
    if args.results_only:
        wrote = write_result_lines(args.hypotheses, findings)
        print(f"{wrote} result lines written to {args.hypotheses}")
        return 0
    append_rows(rows)
    wrote = write_result_lines(args.hypotheses, findings)
    finds = sum(1 for f in findings if f["verdict"] == "FIND")
    print(
        f"booked {len(findings)} findings ({finds} FIND) into the register; "
        f"{wrote} result lines written to {args.hypotheses}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
