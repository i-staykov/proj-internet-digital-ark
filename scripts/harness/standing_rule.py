"""Write the `Decision:` line the standing rule already authorises, and no other.

**The rule** (CLAUDE.md, Autonomy): a lead inside the standing size, terms, robots and class
bounds gets its `Decision:` line from the loop; outside any bound it parks `pending`. The
owner approves a new evidence class and every send. The bounds live once, in the fleet's
`policy.json` `standing`.

**The fleet tests the bounds and this reads its verdict.** The lead's `standing` block says
whether the fleet admitted it and carries one `{ok, evidence}` per clause in CLAUSES, keyed by
the clause's name. A lead with no such block parks, as does one not admitted and one whose
clause is missing or not ok, and the park names the clause and the evidence the fleet wrote
for it. There is no byte bound here: the size clause is the fleet's, measured where the bytes
are.

**The one bound the fleet cannot test is the new class.** The register lives here, so whether
another source of the same evidence class is already approved for the master is a lookup in
it, and a class nobody has approved yet parks and reaches the owner through
`sync_approvals.py`. The standing rule extends a decision already taken; it never takes a new
one. The fleet's `class` clause is a different test, of a stream's grain and web method.

**Which figure decides.** The store re-price (`store_price.json` `ee`) decides until the
program's figure on the pushed snapshot (`fleet_program_ee`) has agreed with it within 1% on
the last ten finds booked as outcome lines in the fleet ledger; from then the program's figure
decides for a find that has one, and the store re-price still decides for a find that has
none. A confirmed FIND is a candidate when its deciding figure is a positive number, and the
citation names which figure decided and its value.

**Why this is a program and not a judgement.** Every bound is a lookup: the fleet admitted the
lead on every clause or it did not, the class has a master source in the register or it does
not. A model asked to weigh them adds nothing except the chance of talking itself into a yes.
`just bank` ingests what a decision here releases and runs `ark check`, and a red gate takes
the line and the rows back.

    uv run python scripts/harness/standing_rule.py INCOMING [--fleet FLEET] [--write]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_ledger  # noqa: E402

from ark import approvals  # noqa: E402
from ark.evidence_types import MASTER_TYPES  # noqa: E402
from ark.hostnames import fleet_read_source_name  # noqa: E402

REGISTER = REPO / "docs/registers/approved-sources-list.md"
# The fleet's standing clauses, in the order a park names them. A clause the lead does not
# carry is a bound nobody tested, so it parks like one that failed.
CLAUSES = ("size", "terms", "robots", "class", "window")
# Where each figure lives in `store_price.json`, and how a line names it.
FIELDS = {"store": "ee", "program": "fleet_program_ee"}
FIGURES = {"store": "the store re-price", "program": "the program's figure on the pushed snapshot"}
# The new-class reason, which `fleet_request.py` reads to head its ask as a class approval.
NEW_CLASS = "no other {} source is approved as master"
CITATION = (
    "- standing rule: the loop wrote the decision below (CLAUDE.md, Autonomy). The class is "
    "already approved for the master, and the fleet admitted the lead under standing policy "
    "{policy} with every clause ok: {clauses}. Fleet run {run}, decided on {figure}, "
    "{ee:,.1f} EE. The ingest the decision releases is gated by `ark check`, and a red gate "
    "takes the decision back."
)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _positive(value) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def lead_of(incoming: Path, slug: str) -> dict:
    """The lead as the leg saw it, from the artifact rather than from the fleet clone.

    The clone on this laptop is never pulled by the sync, so its `leads/` can be days behind
    the wave being banked, and a decision must not rest on a file that moved underneath it.
    The drain puts the artifact's copy at `<slug>/lead.json`.
    """
    return _json(incoming / slug / "lead.json")


def confirmed_finds(incoming: Path, outcomes: list[dict]) -> dict[str, dict]:
    """The confirmed FINDs with a deciding figure, keyed by their directory's slug.

    `outcomes` are the fleet ledger's outcome lines. Once the last ten finds in them agree
    within 1%, the program's figure decides for each find with a positive one, and the store
    re-price for every other, so a find the program did not price still gets its block. Each
    entry carries its directory, the sidecar, the re-price, which figure decided and its value.

    The key is the directory's, which the drain names after the sidecar's slug and
    `fleet_request.py` names the block after, so every block written there is found here.

    A FIND its own verify lane disputed, or one with no deciding figure, is not a candidate
    for an automatic decision. Both are visible in the register row; neither is evidence
    enough to spend a human's standing permission on.
    """
    streak = fleet_ledger.streak(list(outcomes))
    out: dict[str, dict] = {}
    for lead in sorted(p for p in incoming.iterdir() if p.is_dir()):
        finding = _json(lead / "finding.json")
        store = _json(lead / "store_price.json")
        if finding.get("verdict") != "FIND":
            continue
        if (finding.get("verify") or {}).get("status") != "confirmed":
            continue
        figure = "program" if streak and _positive(store.get(FIELDS["program"])) else "store"
        ee = store.get(FIELDS[figure])
        if not _positive(ee):
            continue
        out[slugify(lead.name)] = {
            "dir": lead,
            "finding": finding,
            "store": store,
            "figure": figure,
            "ee": ee,
        }
    return out


def class_is_already_eligible(etype: str, source: str, decided: dict) -> bool:
    """Another source of this same evidence type is approved for the annual master."""
    if etype not in MASTER_TYPES:
        return False
    return any(
        a.evidence_type == etype and a.decision == "master" and a.source_name != source
        for a in decided.values()
    )


def _evidence(clause) -> str:
    """What the fleet wrote for a clause, on one line."""
    value = clause.get("evidence") if isinstance(clause, dict) else clause
    if value is None or value == "":
        return "no evidence recorded"
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    return " ".join(text.split())


def _clause_names(clauses: dict) -> list[str]:
    return [*CLAUSES, *sorted(name for name in clauses if name not in CLAUSES)]


def reasons_to_park(approval, lead: dict, decided: dict) -> list[str]:
    """The bounds this source is outside, the new class first. Empty means all hold."""
    bad: list[str] = []
    if not class_is_already_eligible(approval.evidence_type, approval.source_name, decided):
        bad.append(NEW_CLASS.format(approval.evidence_type))
    standing = (lead or {}).get("standing")
    if not isinstance(standing, dict):
        bad.append("the lead carries no standing admission")
        return bad
    if standing.get("admitted") is not True:
        bad.append(f"the fleet did not admit it (admitted: {json.dumps(standing.get('admitted'))})")
    clauses = standing.get("clauses")
    clauses = clauses if isinstance(clauses, dict) else {}
    for name in _clause_names(clauses):
        clause = clauses.get(name)
        if clause is None:
            bad.append(f"the {name} clause is missing")
        elif not isinstance(clause, dict) or clause.get("ok") is not True:
            bad.append(f"the {name} clause is not ok: {_evidence(clause)}")
    return bad


def cite(lead: dict, find: dict) -> str:
    """The fact line above `Decision: master`: the clauses, their evidence and the figure.

    One line with single spaces, which the compactor keeps as it is written.
    """
    standing = lead.get("standing") or {}
    clauses = standing.get("clauses") or {}
    said = CITATION.format(
        policy=standing.get("policy_version", "unrecorded"),
        clauses="; ".join(
            f"{name} ({_evidence(clauses.get(name))})" for name in _clause_names(clauses)
        ),
        run=find["finding"].get("run_id", "unknown"),
        figure=FIGURES[find["figure"]],
        ee=find["ee"],
    )
    return " ".join(said.split())


def decide(text: str, approval, citation: str) -> str:
    """The register with this one source's pending line flipped and the rule cited above it.

    As a `- standing rule:` fact, the shape the compactor keeps for a loop decision: it drops
    a `Decided by` line, and the record of what decided with it. A `- parked:` line an earlier
    bank wrote is answered now, so it goes.
    """
    lines = text.splitlines(keepends=True)
    for index in range(approval.line - 1, len(lines)):
        if lines[index].startswith("Decision: pending"):
            lines[index] = citation + "\nDecision: master\n"
            start = approval.line - 1
            own = [line for line in lines[start:index] if not line.startswith("- parked:")]
            return "".join(lines[:start] + own + lines[index:])
    raise ValueError(f"no pending decision line under {approval.source_name}")


def find_for(source: str, finds: dict[str, dict]) -> dict | None:
    """The find a pending block asks about: the one its name slugifies to, or the lead a
    whole read banks under `fleet_<slug>_hostnames`, the name `fleet_request.py` files a
    read's block under."""
    find = finds.get(slugify(source))
    if find is not None:
        return find
    for find in finds.values():
        lead = find["dir"]
        if (lead / "read.json").is_file() and fleet_read_source_name(lead.name) == source:
            return find
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("incoming", type=Path)
    ap.add_argument("--register", type=Path, default=REGISTER)
    ap.add_argument(
        "--fleet",
        type=Path,
        default=None,
        help="the fleet clone whose ledger holds the outcome lines; without it the store "
        "re-price decides",
    )
    ap.add_argument("--write", action="store_true", help="without it, say what it would decide")
    args = ap.parse_args(argv)

    incoming = args.incoming.expanduser()
    if not incoming.is_dir():
        print(f"{incoming} is not a directory", file=sys.stderr)
        return 1
    fleet = args.fleet.expanduser() if args.fleet else None
    finds = confirmed_finds(incoming, fleet_ledger.lines(fleet, "outcome"))
    if not finds:
        print("standing rule: no confirmed FIND with a deciding figure, nothing to decide")
        return 0

    written = 0
    # Re-read the register per source rather than iterating one parse of it: a decision adds
    # its citation line, so every line number below the one just written has moved.
    pending = approvals.pending(args.register)
    wanted = [a.source_name for a in pending if find_for(a.source_name, finds) is not None]
    for source in wanted:
        decided = approvals.load(args.register)
        approval = next(
            (a for a in approvals.pending(args.register) if a.source_name == source), None
        )
        if approval is None:
            continue
        find = find_for(approval.source_name, finds)
        lead = lead_of(incoming, find["dir"].name)
        bad = reasons_to_park(approval, lead, decided)
        if bad:
            print(f"parked: {approval.source_name} stays pending, {'; '.join(bad)}")
            continue
        if not args.write:
            print(f"would decide: {approval.source_name} / {approval.evidence_type}")
            continue
        args.register.write_text(
            decide(args.register.read_text(encoding="utf-8"), approval, cite(lead, find)),
            encoding="utf-8",
        )
        written += 1
        print(f"decided: {approval.source_name} / {approval.evidence_type} is master")
    if args.write and written:
        print(f"standing rule: {written} decisions written, the ingest and the gate follow")
    elif not written:
        print("standing rule: nothing decided; what is left goes to the owner as an ask")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
