"""Flatten, validate and re-price the findings `just sync` drains out of the fleet.

**A fleet figure never reaches the register alone.** The leg that measured a corpus priced
it against the pushed snapshot, which is a copy of the store's exports and his baseline and
not the store; it can be hours stale, it holds no corroboration split, and it was produced by
the same agent that wants the answer to be large. So a FIND its own verify lane confirmed is
priced a second time HERE, by `price_items.py` or `price_hostnames.py`, against the live
store, and the scribe books both numbers side by side. A FIND that ships no items cannot be
re-priced, and that says so in the register rather than passing as measured.

Three subcommands, in the order `just sync` runs them:

    drain     the downloaded run directories become one directory per lead
    validate  every sidecar against the fleet's own schema, via the fleet's own validator
    reprice   every confirmed FIND against the live store

    uv run python scripts/harness/fleet_findings.py drain data/fleet_findings/incoming
    uv run python scripts/harness/fleet_findings.py validate data/fleet_findings/incoming \\
        --fleet ~/Documents/GitHub/ark-fleet
    uv run python scripts/harness/fleet_findings.py reprice data/fleet_findings/incoming \\
        --fleet ~/Documents/GitHub/ark-fleet
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SIDECAR = "finding.json"
PROSE = "finding.md"
STORE_PRICE = "store_price.json"
# What the leg has to leave beside its finding for the laptop to be able to check it. Both
# pricers read this shape: one JSON object per line, `{"item", "year", "text"}`.
ITEM_FILES = ("items.jsonl.gz", "items.jsonl")
LEDGER = REPO / "data/logs/fleet_ledger.tsv"

_ITEMS_EE = re.compile(r"net-new AFTER the split\s*:\s*([\d,]+) pairs, ([\d,]+\.?\d*) EE")
_HOST_EE = re.compile(r"NET-NEW hostname years ([\d,]+)\s+([\d,]+\.?\d*) EE")


def _number(text: str) -> float:
    return float(text.replace(",", ""))


def sidecars(incoming: Path) -> list[Path]:
    """Every drained lead directory's sidecar, in a stable order."""
    return sorted(p / SIDECAR for p in sorted(incoming.iterdir()) if (p / SIDECAR).is_file())


def load(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


# --- drain --------------------------------------------------------------------


def drain(incoming: Path) -> int:
    """One directory per lead at the top, whatever shape the artifact arrived in.

    An S3 artifact is `leads/<slug>/{finding.json,finding.md,items.jsonl}`; the waves before
    it uploaded `findings/*.md` and nothing else. Both end up where the scribe and the
    pricer look, and a lead directory moves WHOLE so a sidecar keeps the items beside it.
    A slug already drained is left alone: a run is re-downloaded until it completes, and
    the copy already here is the one the register rows were written from.
    """
    moved = leads = 0
    for run in sorted(p for p in incoming.iterdir() if p.is_dir() and p.name.startswith("run_")):
        for lead in sorted(p for p in run.rglob("*") if p.is_dir() and (p / SIDECAR).is_file()):
            target = incoming / lead.name
            if target.exists():
                print(f"drain: {lead.name} is already here, the artifact copy is dropped")
                shutil.rmtree(lead, ignore_errors=True)
                continue
            shutil.move(str(lead), str(target))
            leads += 1
        for prose in sorted(run.rglob("*.md")):
            target = incoming / prose.name
            if target.exists():
                continue
            shutil.move(str(prose), str(target))
            moved += 1
        ledger_rows(run)
        shutil.rmtree(run, ignore_errors=True)
    print(f"drain: {leads} lead directories, {moved} loose findings")
    return 0


def ledger_rows(run: Path) -> None:
    """One ledger line per telemetry file, so the window's spend survives the tidy."""
    label = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    for telemetry in sorted(run.rglob("telemetry.json")):
        doc = load(telemetry)
        if not doc:
            continue
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as out:
            out.write(
                f"{label}\t{doc.get('tokens_in_plus_out', 0)}\t{doc.get('seven_day_pct', '?')}\n"
            )


# --- validate -----------------------------------------------------------------


def validate(incoming: Path, fleet: Path) -> int:
    """Every sidecar against the fleet's schema, using the fleet's own validator.

    Not a second implementation: the schema and the subset of JSON Schema it is written in
    both live in the fleet, and a copy here would drift the week the schema changes. A
    sidecar that fails is kept as `finding.json.rejected` and replaced by the contract's own
    BLOCKED fallback, which is what the fleet would have written had it caught it itself.
    """
    contract = fleet / "scripts/contract.py"
    if not contract.is_file():
        print(f"validate: no validator at {contract}, nothing checked", file=sys.stderr)
        return 1
    bad = 0
    for path in sidecars(incoming):
        done = subprocess.run(
            [sys.executable, str(contract), "validate", str(path), "--schema", "finding"],
            capture_output=True,
            text=True,
        )
        if done.returncode == 0:
            continue
        bad += 1
        print(f"validate: {path.parent.name} does not validate")
        for line in done.stdout.splitlines():
            print(f"  {line}")
        rejected = path.with_suffix(".json.rejected")
        shutil.copyfile(path, rejected)
        subprocess.run(
            [
                sys.executable,
                str(contract),
                "fallback",
                str(path),
                "--lane",
                str(load(rejected).get("lane") or "price"),
                "--run-id",
                str(load(rejected).get("run_id") or "unknown"),
                "--reason",
                "schema",
                "--from",
                str(rejected),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    print(f"validate: {len(sidecars(incoming))} sidecars, {bad} replaced by a BLOCKED fallback")
    return 0


# --- reprice ------------------------------------------------------------------


def items_file(lead: Path) -> Path | None:
    for name in ITEM_FILES:
        if (lead / name).is_file():
            return lead / name
    return None


def grain_of(slug: str, finding: dict, fleet: Path) -> str:
    """The lead's grain, which decides which pricer answers.

    The lead file is the authority because it is where the scout recorded what one record
    is. A finding whose lead has been tidied away falls back to its own track, which is the
    only thing in the sidecar that distinguishes the two units.
    """
    lead = load(fleet / "leads" / f"{slug}.json")
    grain = lead.get("grain")
    if grain in {"hostname", "registrable", "candidate"}:
        return str(grain)
    # No lead file. The track is all that is left, and the fallback is the general pricer:
    # `price_items.py` prices the (domain, year) unit for any corpus, while
    # `price_hostnames.py` answers only for records that are hosts BENEATH a registrable
    # and refuses a file of bare names outright.
    return (
        "candidate" if (finding.get("pricing") or {}).get("track") == "candidate" else "registrable"
    )


def price(lead: Path, finding: dict, fleet: Path) -> dict:
    """Run the store pricer over the leg's own items and return what it measured."""
    slug = lead.name
    items = items_file(lead)
    if items is None:
        return {"status": "no items shipped", "ee": None}
    grain = grain_of(slug, finding, fleet)
    script = "price_hostnames.py" if grain == "hostname" else "price_items.py"
    cmd = ["uv", "run", "python", f"scripts/pricing/{script}", "--items", str(items)]
    done = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    (lead / "store_price.txt").write_text(done.stdout + done.stderr, encoding="utf-8")
    if done.returncode != 0:
        return {"status": f"{script} exited {done.returncode}", "ee": None, "cmd": " ".join(cmd)}
    pattern = _HOST_EE if grain == "hostname" else _ITEMS_EE
    found = pattern.search(done.stdout)
    if not found:
        return {"status": f"{script} printed no net-new line", "ee": None, "cmd": " ".join(cmd)}
    return {
        "status": "priced",
        "pricer": script,
        "cmd": " ".join(cmd),
        "grain": grain,
        "netnew": int(_number(found.group(1))),
        "ee": _number(found.group(2)),
        "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def reprice(incoming: Path, fleet: Path) -> int:
    """Every confirmed FIND, priced again on the live store beside the fleet's figure."""
    for path in sidecars(incoming):
        finding = load(path)
        lead = path.parent
        if finding.get("verdict") != "FIND":
            continue
        status = (finding.get("verify") or {}).get("status", "pending")
        if status != "confirmed":
            print(f"reprice: {lead.name} is {status}, not re-priced")
            (lead / STORE_PRICE).write_text(
                json.dumps({"status": f"verify {status}", "ee": None}, indent=2) + "\n",
                encoding="utf-8",
            )
            continue
        result = price(lead, finding, fleet)
        result["fleet_ee"] = (finding.get("pricing") or {}).get("ee")
        (lead / STORE_PRICE).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        if result["ee"] is None:
            print(f"reprice: {lead.name} NOT re-priced, {result['status']}")
            continue
        fleet_ee = result["fleet_ee"]
        gap = f", the fleet said {fleet_ee:,.1f}" if isinstance(fleet_ee, int | float) else ""
        print(f"reprice: {lead.name} is worth {result['ee']:,.1f} EE on the store{gap}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["drain", "validate", "reprice"])
    ap.add_argument("incoming", type=Path)
    ap.add_argument("--fleet", type=Path, help="the fleet clone, for its schema and its leads")
    args = ap.parse_args(argv)

    incoming = args.incoming.expanduser()
    if not incoming.is_dir():
        print(f"{incoming} is not a directory", file=sys.stderr)
        return 1
    if args.command == "drain":
        return drain(incoming)
    if args.fleet is None:
        ap.error(f"{args.command} needs --fleet")
    fleet = args.fleet.expanduser()
    return validate(incoming, fleet) if args.command == "validate" else reprice(incoming, fleet)


if __name__ == "__main__":
    raise SystemExit(main())
