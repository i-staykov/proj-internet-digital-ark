"""Tell the fleet what became of each lead, by writing its status back into `leads/`.

**The queue is only true if the end of the pipeline writes to it.** A lead reaches
`verified` in the fleet and then leaves for the laptop, which books it, decides it, ingests
it or refuses it. Nothing there is visible from GitHub, so without this the dealer keeps
seeing a settled lead as live work and re-deals it, which is exactly how six settled slugs
were relaunched on 2026-09-01 when result lines were written late.

Two terminal statuses, and the schema has no third:

    banked   the register has decided it, master or candidate-only, so the store either
             holds it or will on the next ingest
    closed   a measured negative: a CLOSED finding, or a FIND its own verify lane disputed

Everything else is left exactly as it is. A confirmed FIND still waiting on Ivo is not
settled, and a BLOCKED leg is a leg to run again, not a lead to bury.

The file is rewritten key by key, never regenerated, so a field this laptop knows nothing
about survives; the fleet's own validator is then asked whether the result is still a lead.

    uv run python scripts/harness/fleet_leads.py data/fleet_findings/incoming \\
        --fleet ~/Documents/GitHub/ark-fleet [--write]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark import approvals  # noqa: E402

REGISTER = REPO / "docs/registers/approved-sources-list.md"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def banked_slugs(register: Path) -> set[str]:
    """Every source the register has decided one way or the other, as slugs."""
    return {
        slugify(a.source_name) for a in approvals.load(register).values() if a.decision != "pending"
    }


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


def validate(fleet: Path, lead_file: Path) -> str:
    """Ask the fleet's own validator whether what we wrote is still a lead."""
    contract = fleet / "scripts/contract.py"
    if not contract.is_file():
        return "not validated, the fleet clone has no validator"
    done = subprocess.run(
        [sys.executable, str(contract), "validate", str(lead_file), "--schema", "lead"],
        capture_output=True,
        text=True,
    )
    return "valid" if done.returncode == 0 else f"INVALID: {done.stdout.strip()}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("incoming", type=Path)
    ap.add_argument("--fleet", type=Path, required=True)
    ap.add_argument("--register", type=Path, default=REGISTER)
    ap.add_argument("--write", action="store_true", help="without it, say what it would write")
    args = ap.parse_args(argv)

    incoming, fleet = args.incoming.expanduser(), args.fleet.expanduser()
    if not incoming.is_dir():
        print(f"{incoming} is not a directory", file=sys.stderr)
        return 1
    banked = banked_slugs(args.register)
    written = 0
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
        if not args.write:
            print(f"would write: {slug} is {status}")
            continue
        lead["status"] = status
        lead_file.write_text(json.dumps(lead, indent=2) + "\n", encoding="utf-8")
        written += 1
        print(f"leads: {slug} is {status} ({validate(fleet, lead_file)})")
    if args.write:
        print(f"leads: {written} statuses written to {fleet / 'leads'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
