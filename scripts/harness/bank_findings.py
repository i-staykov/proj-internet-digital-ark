"""The scribe, as code: book fleet findings into the register, deterministically.

The sonnet scribe did four mechanical things every round: append one register row per
finding, write the result line onto the hypothesis block, re-rank the triage queue, and
leave the working tree ready to commit. Nothing in that list needs a model once the
findings carry their fields in a fixed shape, and a model was the second-largest token
cost in the loop. So this is that scribe, at zero tokens.

It never ingests and never decides: a FIND is booked exactly like a CLOSED, and the
approval path (`standing_rule.py`, then `sync_approvals.py`) is the only thing that reaches
the store. Findings whose file lacks a parseable verdict are booked as BLOCKED with the
file named, which is the fleet's fallback contract carried through.

**The prose row is unchanged; the sidecar is what a program is allowed to believe.** Since
S9 a leg arrives as a directory: `finding.md` in the register voice, `finding.json` in the
fleet's schema, and `store_price.json` written by `fleet_findings.py reprice`. Where the
sidecar disagrees with the prose about a verdict, a figure or a URL, the sidecar wins,
because the prose is written to be read and the sidecar is written to be checked. **A fleet
figure never reaches the register alone**: the EE cell carries the store's own re-price
beside it, or says in words why there is none.

    uv run python scripts/harness/bank_findings.py data/fleet_findings/incoming \\
        --hypotheses ~/Documents/GitHub/ark-fleet/hypotheses.md --run-label wave-123
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTER = REPO / "docs/registers/sources.md"
CLOSED = REPO / "docs/registers/sources-closed.md"
TABLE_HEADING = "## Evaluated and rejected"
CLOSED_HEADING = "| source | date | measured | reason | link |"

_FIELD = re.compile(r"^([a-z_ ]+):\s*(.*)$")
# `>` and a trailing comma end a URL as often as a space does, because the prose writes
# artifacts as `<http://host/path>, the CMU data set`. A link with a bracket on the end is a
# link that does not open.
_URL = re.compile(r"https?://[^\s`)>\"']+")


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
            "lens",
            "evidence class",
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
    # The figure, from the `ee:` field or from the verdict line that carries it instead:
    # a scout writes `verdict: CLOSED, 20.92 EE against a 5,000 EE floor`, and reading only
    # the first field booked that source as unpriced.
    ee_match = re.search(r"[\d,]+(?:\.\d+)?", fields.get("ee", "")) or re.search(
        r"([\d,]+(?:\.\d+)?)\s*EE", fields.get("verdict", "")
    )
    ee = ee_match.group(len(ee_match.groups())).replace(",", "") if ee_match else "0"
    return {"slug": slug, "verdict": verdict, "ee": ee, "fields": fields}


def _json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def overlay(finding: dict, lead: Path) -> dict:
    """The prose finding, with the sidecar's machine-readable fields laid over it."""
    # The lead travelled with the artifact, so a closed row can name the lens, the class and
    # the URL even when the prose beside it is three lines of refusal.
    finding["lead"] = _json(lead / "lead.json")
    sidecar = _json(lead / "finding.json")
    if not sidecar:
        return finding
    finding["slug"] = sidecar.get("slug") or finding["slug"]
    verdict = str(sidecar.get("verdict") or "").upper()
    if verdict in {"FIND", "CLOSED", "BLOCKED"}:
        finding["verdict"] = verdict
    pricing = sidecar.get("pricing") or {}
    if isinstance(pricing.get("ee"), int | float):
        finding["ee"] = f"{pricing['ee']:,.1f}"
    artifact = sidecar.get("artifact") or {}
    if artifact.get("url"):
        finding["fields"].setdefault("artifact", str(artifact["url"]))
    if sidecar.get("reason"):
        finding["fields"].setdefault("reason", str(sidecar["reason"]))
    finding["verify"] = (sidecar.get("verify") or {}).get("status", "pending")
    finding["store"] = _json(lead / "store_price.json")
    return finding


def findings_in(incoming: Path) -> list[dict]:
    """Every finding in the drained directory, one per lead directory and per loose file."""
    out: list[dict] = []
    for lead in sorted(p for p in incoming.iterdir() if p.is_dir()):
        prose, sidecar = lead / "finding.md", lead / "finding.json"
        if not prose.is_file() and not sidecar.is_file():
            continue
        base = (
            parse_finding(prose)
            if prose.is_file()
            else {"slug": lead.name, "verdict": "BLOCKED", "ee": "0", "fields": {}}
        )
        base["slug"] = lead.name
        out.append(overlay(base, lead))
    out += [parse_finding(p) for p in sorted(incoming.glob("*.md"))]
    return out


def booked_slugs() -> set[str]:
    """Every slug either register already carries, so a re-drained run books nothing twice.

    Cheap and deliberately loose: the first cell of a row in `sources.md`, and the name
    before the ` / ` in `sources-closed.md`. Both files are hundreds of kilobytes of prose
    and are streamed a line at a time rather than parsed.
    """
    out: set[str] = set()
    for path, split in ((REGISTER, False), (CLOSED, True)):
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.startswith("| "):
                    continue
                cell = line[2:].split("|", 1)[0].strip()
                out.add(cell.split(" / ")[0].strip() if split else cell)
    return out


def one_per_slug(findings: list[dict]) -> list[dict]:
    """One finding per slug, keeping the one that says the most.

    A wave can hand over the same slug twice: a price leg's copy and the verify leg's, or a
    leg artifact whose root directory is called `findings` beside the lead directory it is a
    copy of. A FIND outranks a measured negative, a sidecar outranks prose alone, and a
    settled verify outranks a pending one.
    """
    rank = {"FIND": 3, "CLOSED": 2, "BLOCKED": 1, "SKIPPED": 0}

    def score(f: dict) -> tuple[int, int, int]:
        settled = 1 if f.get("verify") not in (None, "pending") else 0
        return (rank.get(f["verdict"], 0), 1 if "store" in f else 0, settled)

    best: dict[str, dict] = {}
    for f in findings:
        if f["slug"] not in best or score(f) > score(best[f["slug"]]):
            best[f["slug"]] = f
    return [best[slug] for slug in sorted(best)]


def first_clause(text: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    for stop in (". ", "; "):
        if stop in text[:limit]:
            return text[: text.index(stop) + 1]
    return text[:limit]


def register_row(f: dict, run_label: str) -> str:
    """One row in the eleven columns `convert_register.py` gave the register.

    Cells the finding does not carry read `n/a`. The row is the whole entry: a
    finding that needs more than this writes a `## Detail` section for it by hand.
    """
    day = dt.date.today().isoformat()
    dates = first_clause(f["fields"].get("what dates one item", ""), 140) or "n/a"
    probe = first_clause(f["fields"].get("probe", "") or f["fields"].get("reason", ""), 200)
    url = _URL.search(f["fields"].get("artifact", ""))
    verdict = f["verdict"] + (f" ({f['verify']})" if f.get("verify") else "")
    cells = [
        f["slug"],
        f"{day}, fleet {run_label}",
        "n/a",
        f["fields"].get("method", "n/a") or "n/a",
        dates,
        "n/a",
        f"{ee_cell(f)} ({day})",
        probe or "n/a",
        "n/a",
        verdict,
        f"<{url.group(0)}>" if url else "n/a",
    ]
    tidy = [re.sub(r"\s+", " ", cell).replace("|", r"\|").strip() for cell in cells]
    return _within_limit(tidy)


def ee_cell(f: dict) -> str:
    """The figure, and where it came from.

    A fleet leg prices against the pushed snapshot, so its number is a measurement made
    somewhere else against a copy. When the laptop has re-priced the same items on the live
    store the two sit side by side and a reader can see the gap; when it has not, the cell
    says why in words. Neither is allowed to look like the other.
    """
    store = f.get("store")
    if store is None or f["verdict"] != "FIND":
        return f"{f['ee']} EE"
    if isinstance(store.get("ee"), int | float):
        return f"fleet {f['ee']} EE, store {store['ee']:,.1f} EE"
    return f"fleet {f['ee']} EE, store not re-priced: {store.get('status') or 'no store price'}"


# The register's rows are read in a terminal and a test refuses one over 500 characters.
# It fired three times on 2026-09-04 alone, always on the same cell: a wave writes its
# REUSABLE finding into `method`, which had no cap while `dates` and `probe` did, and the
# finding is genuinely worth keeping, so truncating it looked like losing something.
#
# It is not lost. The full text is in the fleet's own `hypotheses.md`, which ships inside
# `source/fleet.tar.gz` with every delivery, so the row can point at the ledger instead of
# repeating it. A measured LAW earns a section in `laws.md` by hand; a row is an index entry.
ROW_LIMIT = 500
_LEDGER = "see the fleet hypothesis ledger"


def _within_limit(cells: list[str]) -> str:
    """The row, trimming the prose cells in order until the whole row fits.

    Method first and probe second, because those are the two a wave writes freely; every
    other cell is a slug, a figure, a verdict or a link, and a truncated link is worse than
    a long row. If both are down to the pointer and the row is still long, it is returned
    long: that is a row worth a human looking at, not one worth mangling.
    """

    def assemble() -> str:
        return "| " + " | ".join(cells) + " |"

    for index in (3, 7):
        if len(assemble()) <= ROW_LIMIT:
            break
        overhead = len(assemble()) - len(cells[index])
        budget = ROW_LIMIT - overhead - len(_LEDGER) - 2
        if budget < 40:
            cells[index] = _LEDGER
        else:
            cells[index] = (first_clause(cells[index], budget).rstrip() + " " + _LEDGER).strip()
    return assemble()


def closed_row(f: dict, run_label: str) -> str:
    """The five-column row a measured negative gets, in `sources-closed.md`.

    **A negative does not belong in `sources.md`** (#74's floors, restated by Ivo on
    2026-09-09): only a priced FIND and a banked source get a block there. A scout lead that
    closed under the floor was reaching it as a row of eleven `n/a` cells, which is a row
    that says a source was evaluated and records nothing about it. Here the lens, the figure
    and the artifact are the row, and they come from `lead.json` and the prose beside it.
    """
    day = dt.date.today().isoformat()
    lead = f.get("lead") or {}
    etype = lead.get("evidence_class") or f["fields"].get("evidence class") or "unclassified"
    lens = lead.get("lens") or f["fields"].get("lens") or "no lens recorded"
    url = _URL.search(
        f["fields"].get("artifact", "") or str((lead.get("artifact") or {}).get("url") or "")
    )
    measured = f"{f['ee']} EE" if f["ee"] not in ("0", "0.0") else "not priced"
    reason = first_clause(
        f["fields"].get("probe", "")
        or f["fields"].get("reason", "")
        or f["fields"].get("verdict", ""),
        300,
    )
    cells = [
        f"{f['slug']} / {etype}",
        f"{day}, fleet {run_label}",
        measured,
        f"lens {lens}. {reason}".strip(),
        url.group(0) if url else "",
    ]
    tidy = [re.sub(r"\s+", " ", cell).replace("|", r"\|").strip() for cell in cells]
    return "| " + " | ".join(tidy) + " |"


def append_closed(rows: list[str]) -> None:
    text = CLOSED.read_text(encoding="utf-8")
    at = text.index(CLOSED_HEADING)
    sep = text.index("|---|", at)
    line_end = text.index("\n", sep) + 1
    CLOSED.write_text(text[:line_end] + "\n".join(rows) + "\n" + text[line_end:], "utf-8")


def append_rows(rows: list[str]) -> None:
    text = REGISTER.read_text(encoding="utf-8")
    at = text.index(TABLE_HEADING)
    # The table starts under the heading and its intro; insert right after the header
    # row separator so newest entries lead, matching how the scribe wrote them.
    sep = text.index("|---|", at)
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

    findings = one_per_slug(findings_in(args.incoming))
    if not findings:
        print("nothing to bank")
        return 0
    if args.results_only:
        wrote = write_result_lines(args.hypotheses, findings)
        print(f"{wrote} result lines written to {args.hypotheses}")
        return 0

    already = booked_slugs()
    fresh = [f for f in findings if f["slug"] not in already]
    for f in findings:
        if f["slug"] in already:
            print(f"already booked: {f['slug']} has a row, not written again")
    # Two registers, and which one a finding goes to is its verdict. A FIND is a measurement
    # worth reading beside the others; everything else is a closed row so nobody re-tests it.
    rows = [register_row(f, args.run_label) for f in fresh if f["verdict"] == "FIND"]
    closed = [closed_row(f, args.run_label) for f in fresh if f["verdict"] != "FIND"]
    if args.dry_run:
        print("\n".join(rows + closed))
        return 0
    if rows:
        append_rows(rows)
    if closed:
        append_closed(closed)
    wrote = write_result_lines(args.hypotheses, findings)
    print(
        f"booked {len(rows)} FIND rows into {REGISTER.name} and {len(closed)} into "
        f"{CLOSED.name}; {wrote} result lines written to {args.hypotheses}"
    )
    # The line the recipe reads: a drain that booked nothing new is finished rather than
    # failed, and may be archived even though no commit came out of it.
    print(
        f"scribe: {len(rows) + len(closed)} new rows, {len(findings) - len(fresh)} already booked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
