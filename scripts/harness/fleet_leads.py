"""Tell the fleet what became of each lead, by writing its status back into `leads/`.

**The queue is only true if the end of the pipeline writes to it.** A lead reaches
`verified` in the fleet and then leaves for the laptop, which books it, decides it, ingests
it or refuses it. Nothing there is visible from GitHub, so without this the dealer keeps
seeing a settled lead as live work and re-deals it, which is exactly how six settled slugs
were relaunched on 2026-09-01 when result lines were written late.

Two terminal statuses, and the schema has no third:

    banked   the bank booked it: the fleet ledger holds an outcome line for the slug whose
             `banked` is true, which the bank appends once its register commit has landed
    closed   a measured negative: a CLOSED finding, or a FIND its own verify lane disputed

Everything else is left exactly as it is. A confirmed FIND still waiting on Ivo is not
settled, and a BLOCKED leg is a leg to run again, not a lead to bury.

**Banked is read off the ledger, not the register.** A register block is keyed on the name
it was written under, which is a lead's slug only when the block was written from it, so a
register match never banked a source named by hand or by a tool. An outcome line carries
the lead's own slug. Only a JSON `true` counts: a line whose `banked` is the string "true"
books nothing.

The file is rewritten key by key, never regenerated, so a field this laptop knows nothing
about survives. **Only a lead the fleet's own validator passes is written**: the result is
checked in-process against the clone's `schemas/lead.json` before the write, and one that
fails, or a clone with no validator, is named and left as it was. No history entry is
added, because the lead schema has no laptop lane.

    uv run python scripts/harness/fleet_leads.py data/fleet_findings/incoming \\
        --fleet ~/Documents/GitHub/ark-fleet [--write]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_ledger  # noqa: E402

CONTRACT = "scripts/contract.py"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def banked_slugs(fleet: Path) -> set[str]:
    """Every slug the fleet ledger holds an outcome line for whose `banked` is true."""
    return {
        slugify(str(line.get("slug") or ""))
        for line in fleet_ledger.lines(fleet, "outcome")
        if line.get("banked") is True
    } - {""}


def status_for(finding: dict, banked: set[str], slug: str) -> str | None:
    """`banked`, `closed`, or None for a lead that is not settled yet."""
    verdict = finding.get("verdict")
    verify = (finding.get("verify") or {}).get("status", "pending")
    if verdict == "CLOSED":
        return "closed"
    if verdict == "FIND" and verify == "disputed":
        return "closed"
    if verdict == "FIND" and verify == "confirmed" and slug in banked:
        return "banked"
    return None


def validator(fleet: Path) -> Callable[[dict], list[str]] | None:
    """The fleet's own lead check, loaded from the clone's `scripts/contract.py`, or None.

    Loaded by path, not run on a written file, so a lead is checked before it is written
    and a failing one never reaches the clone. The check is the command line's own:
    `check_schema` against `schemas/lead.json`, then `check_semantics`.
    """
    path = fleet / CONTRACT
    if not path.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("fleet_contract", path)
        contract = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(contract)
        schema = json.loads((contract.SCHEMAS / "lead.json").read_text(encoding="utf-8"))
    except Exception as exc:  # a clone's validator that will not load checks nothing
        print(f"leads: the fleet's validator did not load ({exc})", file=sys.stderr)
        return None
    return lambda lead: contract.check_schema(lead, schema) + contract.check_semantics(lead)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("incoming", type=Path)
    ap.add_argument("--fleet", type=Path, required=True)
    ap.add_argument("--write", action="store_true", help="without it, say what it would write")
    args = ap.parse_args(argv)

    incoming, fleet = args.incoming.expanduser(), args.fleet.expanduser()
    if not incoming.is_dir():
        print(f"{incoming} is not a directory", file=sys.stderr)
        return 1
    banked = banked_slugs(fleet)
    check = validator(fleet)
    written = refused = 0
    for lead_dir in sorted(p for p in incoming.iterdir() if p.is_dir()):
        finding = _json(lead_dir / "finding.json")
        if not finding:
            continue
        slug = slugify(str(finding.get("slug") or lead_dir.name))
        status = status_for(finding, banked, slug)
        if status is None:
            print(f"leads: {slug} is not settled here, left as the fleet has it")
            continue
        lead_file = fleet / "leads" / f"{slug}.json"
        lead = _json(lead_file)
        if not lead:
            print(f"leads: {slug} has no lead file in the fleet clone, nothing written")
            continue
        if lead.get("status") == status:
            continue
        lead = dict(lead, status=status)
        bad = ["the fleet clone has no validator"] if check is None else check(lead)
        if bad:
            refused += 1
            said = "not written" if args.write else "would not be written"
            why = "; ".join(bad[:3])
            print(f"leads: {slug} {said} as {status}, it fails the fleet's lead check: {why}")
            continue
        if not args.write:
            print(f"would write: {slug} is {status}")
            continue
        lead_file.write_text(json.dumps(lead, indent=2) + "\n", encoding="utf-8")
        written += 1
        print(f"leads: {slug} is {status}")
    if args.write:
        tail = f", {refused} refused by the fleet's lead check" if refused else ""
        print(f"leads: {written} statuses written to {fleet / 'leads'}{tail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
