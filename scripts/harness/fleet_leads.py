"""Tell the fleet what became of each lead, by writing its status back into `leads/`.

**The queue is only true if the end of the pipeline writes to it**: what the laptop books is
invisible from GitHub, so without this the dealer re-deals a settled lead.

Two terminal statuses, and the schema has no third:

    banked   the fleet ledger holds an outcome line for the slug whose `banked` is true,
             which the bank appends once its rows are ingested, drained or not
    closed   a CLOSED finding, or a FIND its verify disputed; it leaves `leads/` once
             `sources-closed.md` books its slug, since the register keeps the verdict

Everything else is left as it is: a confirmed FIND waiting on the owner is not settled, and a
BLOCKED leg is a leg to run again. **Banked is read off the ledger, not the register**, whose
blocks are keyed on the name they were written under; only a JSON `true` counts.

The file is rewritten key by key, so a field this laptop knows nothing about survives, and
only a lead the clone's own `schemas/lead.json` check passes is written; one that fails, or a
clone with no validator, is named and left as it was.

    uv run python scripts/harness/fleet_leads.py data/fleet_findings/incoming \\
        --fleet ~/GitHub/ark-fleet [--write]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_ledger  # noqa: E402

CONTRACT = "scripts/contract.py"
CLOSED_REGISTER = Path(__file__).resolve().parents[2] / "docs" / "registers" / "sources-closed.md"


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
    booked = CLOSED_REGISTER.read_text(encoding="utf-8") if CLOSED_REGISTER.is_file() else ""
    written = refused = 0
    settled: list[tuple[str, str]] = []
    drained = set()
    for lead_dir in sorted(p for p in incoming.iterdir() if p.is_dir()):
        finding = _json(lead_dir / "finding.json")
        if not finding:
            continue
        slug = slugify(str(finding.get("slug") or lead_dir.name))
        drained.add(slug)
        status = status_for(finding, banked, slug)
        if status is None:
            print(f"leads: {slug} is not settled here, left as the fleet has it")
            continue
        # A lead the fleet re-dealt after this artifact carries a finding that settles otherwise.
        now = _json(fleet / "leads" / slug / "finding.json")
        if now and status_for(now, banked, slug) != status:
            print(f"leads: {slug}: the fleet moved on past this drain, left as the fleet has it")
            continue
        settled.append((slug, status))
    # The drain's own verdict decides its slugs; the ledger decides every other lead.
    settled += [(slug, "banked") for slug in sorted(banked - drained)]
    for slug, status in settled:
        lead_file = fleet / "leads" / f"{slug}.json"
        lead = _json(lead_file)
        if not lead:
            if slug in drained:
                print(f"leads: {slug} has no lead file in the fleet clone, nothing written")
            continue
        if status == "closed" and re.search(rf"(?<![\w-]){re.escape(slug)}(?![\w-])", booked):
            if args.write:
                lead_file.unlink()
                shutil.rmtree(lead_file.with_suffix(""), ignore_errors=True)
            print(f"leads: {slug} is booked closed, so it leaves the queue (write: {args.write})")
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
