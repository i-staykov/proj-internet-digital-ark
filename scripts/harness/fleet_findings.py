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
    uv run python scripts/harness/fleet_findings.py reprice data/fleet_findings/incoming
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SIDECAR = "finding.json"
PROSE = "finding.md"
LEAD = "lead.json"
STORE_PRICE = "store_price.json"
# Where a price leg leaves the `{host, year}` lines it measured (the fleet's ITEMS_DIR).
# They outlive the leg so that `pricing.cmd` re-runs for verify, and they are the only copy:
# the run artifact carries the finding, the lead and the extractor, and no data at all.
VPS_ITEMS = "/projects/ark-data/items"
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


def freshness(lead: Path) -> tuple[int, int]:
    """How settled a copy of a lead is: a second opinion first, then the run that wrote it.

    Two unprocessed runs can carry the same slug, because a price wave and the verify wave
    that answers it are drained together. The price copy says `verify.status: pending` and
    the verify copy says `confirmed`, so keeping whichever arrived first threw away the only
    copy a re-price and the standing rule will act on.
    """
    finding = load(lead / SIDECAR)
    settled = (finding.get("verify") or {}).get("status", "pending") != "pending"
    run_id = str(finding.get("run_id") or "")
    return (1 if settled else 0, int(run_id) if run_id.isdigit() else 0)


def drain(incoming: Path) -> int:
    """One directory per lead at the top, whatever shape the artifact arrived in.

    An S3 artifact is `leads/<slug>.json` beside `leads/<slug>/{finding.json,finding.md,
    extract.py,verify.json}`; the waves before it uploaded `findings/*.md` and nothing else.
    Both end up where the scribe and the pricer look. The lead directory moves WHOLE and the
    lead file moves INTO it as `lead.json`, because the grain and the dating stamp are read
    from the lead and the fleet clone here is never pulled, so the artifact's copy is the
    only one that is certainly the one the leg saw.
    """
    moved = leads = 0
    for run in sorted(p for p in incoming.iterdir() if p.is_dir() and p.name.startswith("run_")):
        for lead in sorted(p for p in run.rglob("*") if p.is_dir() and (p / SIDECAR).is_file()):
            target = incoming / lead.name
            side = lead.parent / f"{lead.name}.json"
            if side.is_file() and not (lead / LEAD).exists():
                shutil.move(str(side), str(lead / LEAD))
            if target.exists():
                if freshness(lead) <= freshness(target):
                    print(f"drain: {lead.name} is already here in a copy at least as settled")
                    shutil.rmtree(lead, ignore_errors=True)
                    continue
                print(f"drain: {lead.name} arrives more settled than the copy here, replacing it")
                shutil.rmtree(target)
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
    """One ledger line per leg, so the window's spend survives the tidy.

    The artifact's `telemetry.json` is `{"legs": [row, ...]}`, one row per leg. Reading the
    top level as a row logged a zero for every wave, which is the shape of a ledger that is
    being written and not read.
    """
    label = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    for telemetry in sorted(run.rglob("telemetry.json")):
        doc = load(telemetry)
        rows = doc.get("legs") if isinstance(doc.get("legs"), list) else [doc]
        for row in rows:
            if not isinstance(row, dict) or not row:
                continue
            LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with LEDGER.open("a", encoding="utf-8") as out:
                out.write(
                    f"{label}\t{row.get('tokens_in_plus_out', 0)}\t"
                    f"{row.get('seven_day_pct', '?')}\n"
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


def items_remote() -> str:
    """Where the items live, which is not in the artifact.

    A price leg writes `{host, year}` lines to `$ITEMS_DIR/<slug>.jsonl` on the VPS so that
    `pricing.cmd` still re-runs for the verify leg two waves later; the artifact carries the
    finding, the lead and the extractor and none of the data. So the re-price has to fetch
    them, and a laptop with no `ARK_VPS` cannot re-price at all, which is worth saying out
    loud rather than reporting as a missing file.
    """
    if os.environ.get("ARK_ITEMS_REMOTE"):
        return os.environ["ARK_ITEMS_REMOTE"]
    env = REPO / "local.env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            name, _, value = line.strip().partition("=")
            if name.strip() == "ARK_VPS" and value.strip():
                return f"{value.strip().strip(chr(34)).strip(chr(39))}:{VPS_ITEMS}"
    return ""


def fetch_items(lead: Path) -> Path | None:
    """The leg's items, from beside the finding or from the box that has them."""
    here = items_file(lead)
    if here is not None:
        return here
    remote = items_remote()
    if not remote:
        print(f"reprice: no ARK_VPS in local.env, so {lead.name}'s items cannot be fetched")
        return None
    target = lead / "items.jsonl"
    done = subprocess.run(
        ["rsync", "-a", f"{remote}/{lead.name}.jsonl", str(target)],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0 or not target.is_file():
        print(f"reprice: {lead.name}.jsonl is not at {remote}: {done.stderr.strip()}")
        return None
    print(f"reprice: fetched {lead.name}.jsonl from the items directory")
    return target


def grain_of(slug: str, finding: dict, lead_dir: Path) -> str:
    """The lead's grain, which decides which pricer answers.

    The lead file is the authority because it is where the scout recorded what one record
    is, and the copy read is the ARTIFACT'S, moved in by the drain: the fleet clone on this
    laptop is never pulled by the sync, so its `leads/` can be days behind the wave being
    banked. A finding whose lead did not travel falls back to its own track, which is the
    only thing in the sidecar that distinguishes the two units.
    """
    lead = load(lead_dir / LEAD)
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


def price(lead: Path, finding: dict) -> dict:
    """Run the store pricer over the leg's own items and return what it measured."""
    items = fetch_items(lead)
    if items is None:
        return {"status": "no items to price, see the run log", "ee": None}
    grain = grain_of(lead.name, finding, lead)
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


def reprice(incoming: Path) -> int:
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
        result = price(lead, finding)
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
    ap.add_argument("--fleet", type=Path, help="the fleet clone, for its schema (validate only)")
    args = ap.parse_args(argv)

    incoming = args.incoming.expanduser()
    if not incoming.is_dir():
        print(f"{incoming} is not a directory", file=sys.stderr)
        return 1
    if args.command == "drain":
        return drain(incoming)
    if args.command == "reprice":
        return reprice(incoming)
    if args.fleet is None:
        ap.error("validate needs --fleet")
    return validate(incoming, args.fleet.expanduser())


if __name__ == "__main__":
    raise SystemExit(main())
