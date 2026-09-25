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

**One row per slug.** A FIND gets a row in `sources.md`, anything else a row in
`sources-closed.md`, each at the top of that page's one table. A slug already on either
page is not written again, except that a FIND re-measuring its own FIND row replaces it.

**The prose row is unchanged; the sidecar is what a program is allowed to believe.** A leg
arrives as a directory: `finding.md` in the register voice, `finding.json` in the fleet's
schema, and `store_price.json` written by `fleet_findings.py reprice`. Where the sidecar
disagrees with the prose about a verdict, a figure or a URL, the sidecar wins, because the
prose is written to be read and the sidecar is written to be checked. **A fleet figure
never reaches the register alone**: the EE cell carries the store's own re-price beside it,
or says in words why there is none.

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
REGISTER_HEADER = "| source | version or date | coverage period |"
CLOSED_HEADING = "| source | date | measured | reason | link |"

_FIELD = re.compile(r"^([a-z_ ]+):\s*(.*)$")
# `>` and a trailing comma end a URL as often as a space does, because the prose writes
# artifacts as `<http://host/path>, the CMU data set`. A link with a bracket on the end is a
# link that does not open.
_URL = re.compile(r"https?://[^\s`)>\"']+")
# `compact_registers.py` reads URLs with this pattern and copies every one a row names into
# its link cell, less RFC 2606 example hosts, which name no source. A row whose link cell
# already holds them all is one it leaves as written.
_LINKED = re.compile(r"https?://[^\s`)>\]<\"'|,\\]+")
_EXAMPLE = re.compile(r"https?://(?:[^/:]*\.)?example\.(?:com|org|net)(?:[/:]|$)", re.I)
_PIPE = re.compile(r"(?<!\\)\|")
# The pages cite no decision number; a wave's prose sometimes does, and loses it here with
# the words that only pointed at it: the brackets round a list of them, a `per` before one.
_NO = r"(?:C-\d{1,3}|ADR-\d+)"
_DECISION_NO = re.compile(
    rf"\s*\((?:(?:per|under|see)\s+)?{_NO}(?:\s*[,/;]\s*(?:and\s+)?{_NO})*\)"
    rf"|[\s,]*\b(?:per|under|see)\s+{_NO}(?:\s*[,/]\s*(?:and\s+)?{_NO})*\b"
    rf"|\b{_NO}(?:\s*[,/]\s*(?:and\s+)?{_NO})*\b[:,]?\s*"
)


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
    # The first word, whatever follows it: `CLOSED, 20.92 EE` and `FIND: 6,000 EE` both count.
    word = re.match(r"\s*([A-Za-z]+)", fields.get("verdict", ""))
    verdict = word.group(1).upper() if word else "BLOCKED"
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


def first_cell(line: str) -> str | None:
    """A row's first cell, its slug on `sources.md`; None for a line that is not a row."""
    if not line.startswith("| "):
        return None
    return _PIPE.split(line[2:], maxsplit=1)[0].strip()


def closed_key(line: str) -> str | None:
    """The slug of a `sources-closed.md` row: its first cell before the ` / class`."""
    cell = first_cell(line)
    return None if cell is None else cell.split(" / ")[0].strip()


def slugs(path: Path, key=first_cell) -> dict[str, str]:
    """Each slug on one page to its row, the topmost where a slug repeats.

    Deliberately loose, and streamed a line at a time: every `| ` line but a header counts,
    so a slug in any table on the page is booked.
    """
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            slug = key(line)
            if slug and not line.startswith("| source |"):
                out.setdefault(slug, line.rstrip("\n"))
    return out


def _cells(row: str) -> list[str]:
    return [cell.strip() for cell in _PIPE.split(row.strip())[1:-1]]


def fate(f: dict, row: str, open_rows: dict[str, str], closed_rows: dict[str, str]) -> str:
    """What writing this finding's row does: `new`, `replace` or `booked`.

    A slug is written once. The one exception is a FIND re-measuring its own FIND row on
    `sources.md`: a moved figure or verify status replaces that row. A row with any other
    verdict was settled by a person or the loop and is left alone, and a closed slug is
    never reopened from here. Only the figure and the verdict are compared, dates aside,
    so a drain retried on another day writes nothing.
    """
    key = first_cell(row) if f["verdict"] == "FIND" else closed_key(row)
    if key in closed_rows:
        return "booked"
    if key not in open_rows:
        return "new"
    old, new = _cells(open_rows[key]) + [""] * 11, _cells(row)
    if f["verdict"] != "FIND" or not old[9].startswith("FIND"):
        return "booked"

    def measured(cells: list[str]) -> tuple[str, str]:
        return re.sub(r"\s*\(\d{4}-\d{2}-\d{2}\)$", "", cells[6]), cells[9]

    return "booked" if measured(old) == measured(new) else "replace"


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


def _clip(text: str, limit: int) -> str:
    """The first `limit` characters, less a URL the cut would leave half written."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    head, _, tail = cut.rpartition(" ")
    return head if "://" in tail and not text[limit].isspace() else cut


def first_clause(text: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    for stop in (". ", "; "):
        if stop in text[:limit]:
            return text[: text.index(stop) + 1]
    return _clip(text, limit)


def drop_decision_numbers(text: str) -> str:
    """The text without decision numbers; a URL is kept whole, because a cut one does not open."""
    parts = re.split(r"(https?://\S+)", text)
    return "".join(p if i % 2 else _DECISION_NO.sub("", p) for i, p in enumerate(parts))


def _tidy(cells: list[str]) -> list[str]:
    """One line per cell, each `|` escaped exactly once, and no decision number before the link."""
    cells = [drop_decision_numbers(cell) for cell in cells[:-1]] + cells[-1:]
    return [_PIPE.sub(r"\\|", re.sub(r"\s+", " ", cell)).strip() for cell in cells]


def links(artifact: str, texts: list[str]) -> str:
    """The link cell: the artifact first, then every other URL the texts name."""
    first = _URL.search(artifact)
    cell = [first.group(0)] if first and not _EXAMPLE.match(first.group(0)) else []
    held = {u.rstrip(".;:") for u in _LINKED.findall(" ".join(cell))}
    for text in texts:
        for url in (u.rstrip(".;:") for u in _LINKED.findall(str(text))):
            if url not in held and not _EXAMPLE.match(url):
                held.add(url)
                cell.append(url)
    return " ".join(f"<{u}>" for u in cell)


def register_row(f: dict, run_label: str) -> str:
    """One row in the eleven columns of the `sources.md` table; the row is the whole entry.

    Cells the finding does not carry read `n/a`. The link cell holds the artifact, then every
    other URL the finding names.
    """
    day = dt.date.today().isoformat()
    # The lead's stamp when the prose gives none, the one its request block quotes.
    lead = f.get("lead") or {}
    stamp = f["fields"].get("what dates one item") or str(lead.get("what_dates_one_item") or "")
    dates = first_clause(stamp, 140) or "n/a"
    probe = first_clause(f["fields"].get("probe", "") or f["fields"].get("reason", ""), 200)
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
    ]
    cells.append(links(f["fields"].get("artifact", ""), [*f["fields"].values(), *cells]) or "n/a")
    return _within_limit(_tidy(cells))


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


# A row is an index entry read in a terminal, held to 500 characters. **A long cell is
# TRUNCATED, and never replaced by a pointer** to another file: 400 characters of the
# reason index the source where a pointer to a file that may go does not.
ROW_LIMIT = 500
_CUT = "..."


def _within_limit(cells: list[str], order: tuple[int, ...] = (3, 7), keep: int = 0) -> str:
    """The row, trimming the prose cells in `order` until the whole row fits.

    Method first and probe second, because those are the two a wave writes freely; every
    other cell is a slug, a figure, a verdict or a link, and a truncated link is worse than
    a long row. If both are down to the pointer and the row is still long, it is returned
    long: that is a row worth a human looking at, not one worth mangling. The closed row
    has one prose cell, its reason, and passes `(3,)` and its verdict prefix as `keep`, the
    characters no trim removes.

    What survives is the START of the cell, cut inside the prose and not at a clause, because
    a reason that opens with a short sentence has its whole substance after that full stop.
    """

    def assemble() -> str:
        return "| " + " | ".join(cells) + " |"

    for index in order:
        if len(assemble()) <= ROW_LIMIT:
            break
        head, rest = cells[index][:keep], cells[index][keep:]
        budget = ROW_LIMIT - (len(assemble()) - len(rest)) - len(_CUT)
        kept = _clip(rest, budget).rstrip() if budget >= 40 else ""
        cells[index] = head + kept + _CUT if kept or not head else head.rstrip()
    return assemble()


def is_brief_audit(f: dict) -> bool:
    return f["slug"].startswith("brief-audit-") or f["fields"].get("lens", "") == "brief-audit"


def closed_row(f: dict, run_label: str) -> str:
    """The five-column row a measured negative gets, in `sources-closed.md`.

    **A negative does not belong in `sources.md`**: only a priced FIND and a banked source
    get a row there. The reason opens with its verdict word, then the lens and the probe;
    the class, the figure and the artifact come from `lead.json` and the prose beside it.
    The link cell holds the artifact, then every other URL the finding names.
    """
    day = dt.date.today().isoformat()
    lead = f.get("lead") or {}
    # A class is a token like `link_source` and a lens a name like `registry-publications`,
    # both as a wave wrote them, sometimes as paragraphs; each is held to a clause.
    etype = first_clause(
        lead.get("evidence_class") or f["fields"].get("evidence class") or "unclassified", 80
    )
    lens = first_clause(lead.get("lens") or f["fields"].get("lens") or "no lens recorded", 60)
    lens = lens.rstrip(".")
    artifact = f["fields"].get("artifact", "") or str((lead.get("artifact") or {}).get("url") or "")
    measured = f"{f['ee']} EE" if f["ee"] not in ("0", "0.0") else "not priced"
    reason = first_clause(
        f["fields"].get("probe", "")
        or f["fields"].get("reason", "")
        or f["fields"].get("verdict", ""),
        300,
    )
    # The verdict leads; a probe that opens with it again loses the repeat.
    reason = re.sub(rf"^{f['verdict']}\b[\s,.:;]*", "", reason, flags=re.I)
    cells = [
        f"{f['slug']} / {etype}",
        f"{day}, fleet {run_label}",
        measured,
        f"{f['verdict']}. lens {lens}. {reason}".strip(),
    ]
    cells.append(links(artifact, [*f["fields"].values(), *cells]))
    return _within_limit(_tidy(cells), order=(3,), keep=len(f["verdict"]) + 2)


def _insert(path: Path, header: str, rows: list[str], key) -> int:
    """Write `rows` at the top of the table under `header`, dropping rows with their keys.

    The table is the run of `|` lines after the header's separator; everything else on the
    page is kept byte for byte. Returns how many old rows were replaced.
    """
    text = path.read_text(encoding="utf-8")
    body = text.index("\n", text.index("|---|", text.index(header))) + 1
    end = body
    while end < len(text) and text.startswith("|", end):
        end = text.find("\n", end) + 1 or len(text)
    new = {key(row) for row in rows}
    old = text[body:end].splitlines(keepends=True)
    kept = [line for line in old if key(line) not in new]
    written = "".join(row + "\n" for row in rows)
    path.write_text(text[:body] + written + "".join(kept) + text[end:], "utf-8")
    return len(old) - len(kept)


def append_rows(rows: list[str], path: Path | None = None) -> int:
    return _insert(path or REGISTER, REGISTER_HEADER, rows, first_cell)


def append_closed(rows: list[str], path: Path | None = None) -> int:
    return _insert(path or CLOSED, CLOSED_HEADING, rows, closed_key)


def write_result_lines(hypo: Path, findings: list[dict]) -> int:
    """Append a `result:` line to each finding's block in the fleet's hypothesis ledger.

    A lead's fate goes back through `fleet_leads.py` into `leads/<slug>.json`, so a missing
    ledger is the normal case, and it writes nothing rather than stopping the sync.
    """
    if not hypo.is_file():
        return 0
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
    ap.add_argument(
        "--registers",
        type=Path,
        help="the directory holding sources.md and sources-closed.md, to run on a copy",
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

    register, closed_page = REGISTER, CLOSED
    if args.registers:
        register, closed_page = args.registers / REGISTER.name, args.registers / CLOSED.name
    open_rows, closed_rows = slugs(register), slugs(closed_page, closed_key)
    # Two registers, and which one a finding goes to is its verdict. A FIND is a measurement
    # worth reading beside the others; everything else is a closed row so nobody re-tests it.
    rows: list[str] = []
    closed: list[str] = []
    counts = {"new": 0, "replace": 0, "booked": 0}
    for f in findings:
        # A brief audit reads his brief against a rule of ours, and its FIND means "a rule
        # to decide", not a source with a figure. It stays in the drain for a human.
        if is_brief_audit(f):
            print(f"rule audit, not a source: {f['slug']} is left in the drain for a human to file")
            continue
        row = (
            register_row(f, args.run_label)
            if f["verdict"] == "FIND"
            else closed_row(f, args.run_label)
        )
        what = fate(f, row, open_rows, closed_rows)
        counts[what] += 1
        if what == "booked":
            print(f"already booked: {f['slug']} has a row, not written again")
            continue
        if what == "replace":
            print(f"replaced: {f['slug']} was re-measured, so its row is rewritten")
        (rows if f["verdict"] == "FIND" else closed).append(row)
    if args.dry_run:
        print("\n".join(rows + closed))
        print(f"dry run: {len(rows) + len(closed)} rows, none written")
        return 0
    if rows:
        append_rows(rows, register)
    if closed:
        append_closed(closed, closed_page)
    wrote = write_result_lines(args.hypotheses, findings)
    print(
        f"booked {len(rows)} FIND rows into {register.name} and {len(closed)} into "
        f"{closed_page.name}; {wrote} result lines written to {args.hypotheses}"
    )
    # The line the recipe reads: a drain that booked nothing new is finished rather than
    # failed, and may be archived even though no commit came out of it.
    print(
        f"scribe: {counts['new']} new rows, {counts['replace']} replaced, "
        f"{counts['booked']} already booked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
