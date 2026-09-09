"""Write the `Decision:` line the standing approval rule already authorises, and no other.

**The rule, verbatim in its four parts** (Ivo, 2026-08-29, CLAUDE.md rule 7): the loop writes
the decision itself, citing the rule, when the class is already master-eligible, a
machine-written stamp inside the artifact dates one item and is quoted, the terms permit it,
and `ark check` passes after the ingest. Failing any one parks it `pending`.

**Why this is a program and not a judgement.** Every one of the first three conditions is a
lookup: the class is in the approved list already or it is not, the lead's stamp has a digit
in it or it does not, the terms URL and the robots verdict were recorded at scout time or
they were not. A model asked to weigh them adds nothing except the chance of talking itself
into a yes. What it cannot decide is condition 4, because that is a fact about a run that has
not happened, so this writes the line, `just sync` ingests and gates, and **a red gate parks
the line back to `pending`**. That ordering is the fourth condition, enforced rather than
asserted.

Nothing here approves a class nobody has approved before. The first source of a class always
reaches Ivo through `sync_approvals.py`, which is the whole point: the standing rule extends
a decision he has taken, it never takes a new one.

    uv run python scripts/harness/standing_rule.py data/fleet_findings/incoming \\
        --fleet ~/Documents/GitHub/ark-fleet [--write]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark import approvals  # noqa: E402
from ark.evidence_types import MASTER_TYPES  # noqa: E402

REGISTER = REPO / "docs/registers/approved-sources-list.md"
CITATION = (
    "Decided by the loop under the standing approval rule (CLAUDE.md rule 7, Ivo 2026-08-29): "
    "the class is already master-eligible, the stamp {stamp} dates one item, the terms at "
    "{terms} permit it, and the ingest this line releases is gated by `ark check`, which parks "
    "the line back to pending if it fails. Fleet run {run}, store re-price {ee:,.1f} EE."
)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def confirmed_finds(incoming: Path) -> dict[str, dict]:
    """The confirmed FINDs the laptop has re-priced, keyed by slug.

    A FIND its own verify lane disputed, or one nothing here could re-price, is not a
    candidate for an automatic decision. Both are visible in the register row; neither is
    evidence enough to spend a human's standing permission on.
    """
    out: dict[str, dict] = {}
    for lead in sorted(p for p in incoming.iterdir() if p.is_dir()):
        finding = _json(lead / "finding.json")
        store = _json(lead / "store_price.json")
        if finding.get("verdict") != "FIND":
            continue
        if (finding.get("verify") or {}).get("status") != "confirmed":
            continue
        if not isinstance(store.get("ee"), int | float) or store["ee"] <= 0:
            continue
        out[slugify(str(finding.get("slug") or lead.name))] = {"finding": finding, "store": store}
    return out


def class_is_already_eligible(etype: str, source: str, decided: dict) -> bool:
    """Another source of this same evidence type is approved for the annual master."""
    if etype not in MASTER_TYPES:
        return False
    return any(
        a.evidence_type == etype and a.decision == "master" and a.source_name != source
        for a in decided.values()
    )


def reasons_to_park(approval, lead: dict, decided: dict) -> list[str]:
    """The conditions this source fails, in the rule's own order. Empty means all hold."""
    bad: list[str] = []
    if not class_is_already_eligible(approval.evidence_type, approval.source_name, decided):
        bad.append(f"no other {approval.evidence_type} source is approved as master")
    stamp = str(lead.get("what_dates_one_item") or "")
    if not re.search(r"\d", stamp):
        bad.append("the lead names no stamp with a digit in it, so it names a category")
    artifact = lead.get("artifact") or {}
    if not artifact.get("terms_url"):
        bad.append("the lead records no terms page")
    if artifact.get("robots") != "allowed":
        bad.append(f"robots is {artifact.get('robots') or 'unrecorded'}, not allowed")
    return bad


def decide(text: str, approval, citation: str) -> str:
    """The register with this one source's pending line flipped, and the rule cited under it."""
    lines = text.splitlines(keepends=True)
    for index in range(approval.line - 1, len(lines)):
        if lines[index].startswith("Decision: pending"):
            lines[index] = "Decision: master\n" + citation + "\n"
            return "".join(lines)
    raise ValueError(f"no pending decision line under {approval.source_name}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("incoming", type=Path)
    ap.add_argument("--fleet", type=Path, required=True)
    ap.add_argument("--register", type=Path, default=REGISTER)
    ap.add_argument("--write", action="store_true", help="without it, say what it would decide")
    args = ap.parse_args(argv)

    incoming, fleet = args.incoming.expanduser(), args.fleet.expanduser()
    if not incoming.is_dir():
        print(f"{incoming} is not a directory", file=sys.stderr)
        return 1
    finds = confirmed_finds(incoming)
    if not finds:
        print("standing rule: no confirmed and re-priced FIND, nothing to decide")
        return 0

    written = 0
    # Re-read the register per source rather than iterating one parse of it: a decision adds
    # its citation line, so every line number below the one just written has moved.
    pending = approvals.pending(args.register)
    wanted = [a.source_name for a in pending if slugify(a.source_name) in finds]
    for source in wanted:
        decided = approvals.load(args.register)
        approval = next(
            (a for a in approvals.pending(args.register) if a.source_name == source), None
        )
        if approval is None:
            continue
        slug = slugify(approval.source_name)
        lead = _json(fleet / "leads" / f"{slug}.json")
        bad = reasons_to_park(approval, lead, decided)
        if bad:
            print(f"parked: {approval.source_name} stays pending, {'; '.join(bad)}")
            continue
        citation = CITATION.format(
            stamp=json.dumps(str(lead["what_dates_one_item"])),
            terms=(lead.get("artifact") or {})["terms_url"],
            run=finds[slug]["finding"].get("run_id", "unknown"),
            ee=finds[slug]["store"]["ee"],
        )
        if not args.write:
            print(f"would decide: {approval.source_name} / {approval.evidence_type}")
            continue
        args.register.write_text(
            decide(args.register.read_text(encoding="utf-8"), approval, citation), encoding="utf-8"
        )
        written += 1
        print(f"decided: {approval.source_name} / {approval.evidence_type} is master")
    if args.write and written:
        print(f"standing rule: {written} decisions written, the ingest and the gate follow")
    elif not written:
        print("standing rule: nothing decided; what is left goes to Ivo as an approval request")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
