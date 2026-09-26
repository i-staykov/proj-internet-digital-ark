"""Flatten, validate and re-price the findings the hourly tick drains out of the fleet.

**A fleet figure never reaches the register alone.** The leg that measured a corpus priced
it against the pushed snapshot, which is a copy of the store's exports and his baseline and
not the store; it can be hours stale, and it was produced by the same agent that wants the
answer to be large. So a FIND its own verify lane confirmed is priced a second time HERE, by
`price_items.py` or `price_hostnames.py`, against the live store, and the scribe books both
numbers side by side. The program a leg runs prices the same items against the snapshot the
last push staged, and how far it agrees with the store goes beside them in `store_price.json`.
A FIND that ships no items cannot be re-priced, and that says so in the register.

Three subcommands, in order: the tick runs drain and validate, `just bank` runs reprice.

    drain     the downloaded run directories become one directory per lead
    validate  every sidecar against the fleet's own schema, via the fleet's own validator
    reprice   every confirmed FIND against the live store and by the program

    uv run python scripts/harness/fleet_findings.py drain data/fleet_findings/incoming
    uv run python scripts/harness/fleet_findings.py validate data/fleet_findings/incoming \\
        --fleet ~/Documents/GitHub/ark-fleet
    uv run python scripts/harness/fleet_findings.py reprice data/fleet_findings/incoming
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
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
# What the program prices against: the snapshot the last push staged. Relative to REPO, so
# no local path reaches store_price.json.
SNAPSHOT = Path("output/fleet_snapshot")
# The program agrees with the store when its figure is within this share of the store's.
WITHIN = 0.01
# The spend record. `ARK_FLEET_LEDGER` moves it, so a drain under test never writes the real one.
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
            # **The slug in the sidecar names the directory, never the directory's own name.**
            # A leg artifact's root directory is called `findings`, so a copy of one banked
            # beside its lead directory as a second lead, and the same finding went into the
            # register twice under the same slug (measured 2026-09-09 on
            # `ietf-mail-archive-received-by`). Keying on the slug makes the two collide, and
            # the collision is then resolved on which copy is more settled.
            slug = str(load(lead / SIDECAR).get("slug") or lead.name)
            target = incoming / slug
            side = lead.parent / f"{slug}.json"
            if side.is_file() and not (lead / LEAD).exists():
                shutil.move(str(side), str(lead / LEAD))
            if target.exists():
                if freshness(lead) <= freshness(target):
                    print(f"drain: {slug} is already here in a copy at least as settled")
                    shutil.rmtree(lead, ignore_errors=True)
                    continue
                print(f"drain: {slug} arrives more settled than the copy here, replacing it")
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
        keep_leftovers(incoming, run)
        shutil.rmtree(run, ignore_errors=True)
    print(f"drain: {leads} lead directories, {moved} loose findings")
    return 0


def keep_leftovers(incoming: Path, run: Path) -> None:
    """Anything the drain did not recognise, kept where a human can find it.

    The run directory is removed once it is drained, so a file no rule matched (a rejected
    lead, a leg's extractor, a shape a later wave invents) would go with it silently. They
    are few and small, and a corpus nobody can re-read is the failure this whole lane exists
    to avoid, so they move rather than vanish.
    """
    left = [p for p in run.rglob("*") if p.is_file() and p.name != "telemetry.json"]
    if not left:
        return
    keep = incoming / "_unread" / run.name
    for path in left:
        target = keep / path.relative_to(run)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))
    print(f"drain: {len(left)} unrecognised files from {run.name} kept in {keep}")


def ledger_rows(run: Path) -> None:
    """One ledger line per leg, so the window's spend survives the tidy.

    The artifact's `telemetry.json` is `{"legs": [row, ...]}`, one row per leg. Reading the
    top level as a row logged a zero for every wave, which is the shape of a ledger that is
    being written and not read.
    """
    label = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    ledger = Path(os.environ.get("ARK_FLEET_LEDGER") or LEDGER)
    for telemetry in sorted(run.rglob("telemetry.json")):
        doc = load(telemetry)
        rows = doc.get("legs") if isinstance(doc.get("legs"), list) else [doc]
        for row in rows:
            if not isinstance(row, dict) or not row:
                continue
            ledger.parent.mkdir(parents=True, exist_ok=True)
            with ledger.open("a", encoding="utf-8") as out:
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
    # A listing or a registry record is a delimited field, and takes no split. Imported
    # here: the drain the tick runs every hour has no need of the pricer.
    from ark.price_snapshot import NO_SPLIT_CLASSES

    lead_doc = load(lead / LEAD)
    if script == "price_items.py" and lead_doc.get("evidence_class") in NO_SPLIT_CLASSES:
        cmd.append("--no-split")
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


def _positive(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) and value > 0 else None


def agreement_pct(store_ee, program_ee) -> float | None:
    """The program's figure as a percentage of the store's, or None without both."""
    store, program = _positive(store_ee), _positive(program_ee)
    return None if store is None or program is None else round(100 * program / store, 2)


def _program(
    lead: Path, items: Path, track: str, evidence_class, keys=("ee", "netnew_pairs")
) -> tuple:
    """One `ark price-snapshot` run on one track: the EE and net-new count its `keys` name,
    and a status. Its stderr goes beside the store pricer's output, so the status never
    carries a path."""
    out = lead / f"program_{track}.json"
    out.unlink(missing_ok=True)
    cmd = ["uv", "run", "ark", "price-snapshot", "--snapshot", str(SNAPSHOT)]
    cmd += ["--items", str(items), "--track", track, "--out", str(out)]
    if evidence_class:
        cmd += ["--class", str(evidence_class)]
    done = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    (lead / f"program_{track}.txt").write_text(done.stderr, encoding="utf-8")
    try:
        doc = json.loads(out.read_text(encoding="utf-8"))
        rule = str(doc["split"]).split(":")[0]
        return float(doc[keys[0]]), int(doc[keys[1]]), f"priced, {track}, split {rule}"
    except (OSError, ValueError, KeyError, TypeError):
        return None, None, f"price-snapshot exited {done.returncode}, see program_{track}.txt"


def program_price(lead: Path, finding: dict, items: Path) -> dict:
    """The items priced again by the command a leg runs, against the snapshot the last push
    staged, with the program's own split. `fleet_program_ee` is the annual track in the unit
    the store's figure measures, on hostname grain its hostname years; a finding that claims
    the candidate track gets that figure too, under its own key."""
    evidence_class = load(lead / LEAD).get("evidence_class")
    grain = grain_of(lead.name, finding, lead)
    tracks = ["annual"]
    claimed = (finding.get("pricing") or {}).get("track")
    if grain == "candidate" or claimed == "candidate":
        tracks.append("candidate")
    result: dict = {}
    for track in tracks:
        name = "program" if track == "annual" else f"program_{track}"
        keys = ("ee", "netnew_pairs")
        if grain == "hostname" and track == "annual":
            keys = ("ee_hostname_years", "netnew_hostname_years")
        ee, netnew, status = _program(lead, items, track, evidence_class, keys)
        result.update({f"fleet_{name}_ee": ee, f"{name}_netnew": netnew, f"{name}_status": status})
    return result


def streak(incoming: Path) -> int:
    """How many finds in a row, newest first, the program and the store agree on within
    WITHIN, over every store price in `incoming` and the drains banked beside it. A find
    counts once, at its latest price; one the program did not price breaks the run, so an
    outage or a zero cannot keep it alive."""
    latest: dict[str, dict] = {}
    banked = (incoming.parent / "banked").glob(f"*/*/{STORE_PRICE}")
    for path in [*banked, *incoming.glob(f"*/{STORE_PRICE}")]:
        doc = load(path)
        if _positive(doc.get("ee")) is None:
            continue
        slug = path.parent.name
        if slug not in latest or str(doc.get("at") or "") >= str(latest[slug].get("at") or ""):
            latest[slug] = doc
    run = 0
    for doc in sorted(latest.values(), key=lambda d: str(d.get("at") or ""), reverse=True):
        store, program = float(doc["ee"]), _positive(doc.get("fleet_program_ee"))
        if program is None or abs(program - store) > WITHIN * store:
            break
        run += 1
    return run


def reprice(incoming: Path) -> int:
    """Every confirmed FIND, priced again on the live store and by the program, beside the
    fleet's figure."""
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
        # the items price() found or fetched, when there were any
        items = items_file(lead)
        if items is not None:
            result.update(program_price(lead, finding, items))
            result["agreement_pct"] = agreement_pct(result["ee"], result["fleet_program_ee"])
        (lead / STORE_PRICE).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        if result["ee"] is None:
            print(f"reprice: {lead.name} NOT re-priced, {result['status']}")
        else:
            fleet_ee = result["fleet_ee"]
            gap = f", the fleet said {fleet_ee:,.1f}" if isinstance(fleet_ee, int | float) else ""
            print(f"reprice: {lead.name} is worth {result['ee']:,.1f} EE on the store{gap}")
        if items is None:
            continue
        program, share = result["fleet_program_ee"], result["agreement_pct"]
        if program is None:
            print(f"reprice: {lead.name} NOT priced by the program, {result['program_status']}")
        else:
            of = f", {share}% of the store's" if share is not None else ""
            print(f"reprice: {lead.name} is worth {program:,.1f} EE by the program{of}")
    print(
        f"reprice: the program agrees with the store within {WITHIN:.0%} "
        f"on the last {streak(incoming)} finds in a row"
    )
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
