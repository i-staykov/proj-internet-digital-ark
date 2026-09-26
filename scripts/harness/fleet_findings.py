"""Flatten, validate and re-price the findings the hourly tick drains out of the fleet.

**A fleet figure never reaches the register alone.** The leg that measured a corpus priced
it against the pushed snapshot, which is a copy of the store's exports and his baseline and
not the store; it can be hours stale, it holds no corroboration split, and it was produced by
the same agent that wants the answer to be large. So a FIND its own verify lane confirmed is
priced a second time HERE, by `price_items.py` or `price_hostnames.py`, against the live
store, and the scribe books both numbers side by side. A FIND that ships no items cannot be
re-priced, and that says so in the register rather than passing as measured.

Four subcommands, in order: the tick runs drain and validate, `just bank` runs reprice and,
once the register commit has landed, outcome.

    drain     the downloaded run directories become one directory per lead, and the old
              TSV ledger becomes the fleet ledger's legacy lines, once
    validate  every sidecar against the fleet's own schema, via the fleet's own validator
    reprice   every confirmed FIND against the live store
    outcome   one fleet ledger line per confirmed FIND: both figures, the decision, banked

    uv run python scripts/harness/fleet_findings.py drain data/fleet_findings/incoming \\
        --fleet ~/Documents/GitHub/ark-fleet
    uv run python scripts/harness/fleet_findings.py validate data/fleet_findings/incoming \\
        --fleet ~/Documents/GitHub/ark-fleet
    uv run python scripts/harness/fleet_findings.py reprice data/fleet_findings/incoming
    uv run python scripts/harness/fleet_findings.py outcome data/fleet_findings/incoming \\
        --fleet ~/Documents/GitHub/ark-fleet [--register R] [--banked]
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_ledger  # noqa: E402

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
# Evidence classes whose names arrive in a delimited field of a self-dating artifact (C-86).
NO_SPLIT_CLASSES = frozenset({"artifact_listing", "whois_creation"})
# The old spend record, converted once into legacy lines and then deleted. `ARK_FLEET_LEDGER`
# moves it, so a drain under test never deletes the real one.
LEDGER = REPO / "data/logs/fleet_ledger.tsv"

_ITEMS_EE = re.compile(r"net-new AFTER the split\s*:\s*([\d,]+) pairs, ([\d,]+\.?\d*) EE")
_HOST_EE = re.compile(r"NET-NEW hostname years ([\d,]+)\s+([\d,]+\.?\d*) EE")
# The old ledger's first field: the drain's minute, as the tick's run label writes it.
_STAMP = re.compile(r"\d{8}T\d{4}Z")


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


def drain(incoming: Path, fleet: Path | None = None) -> int:
    """One directory per lead at the top, whatever shape the artifact arrived in.

    An S3 artifact is `leads/<slug>.json` beside `leads/<slug>/{finding.json,finding.md,
    extract.py,verify.json}`; the waves before it uploaded `findings/*.md` and nothing else.
    Both end up where the scribe and the pricer look. The lead directory moves WHOLE and the
    lead file moves INTO it as `lead.json`, because the grain and the dating stamp are read
    from the lead and the fleet clone here is never pulled, so the artifact's copy is the
    only one that is certainly the one the leg saw.

    **A scout lead takes the same path.** A lead closed at filing ships `leads/<slug>/scout.md`
    and its lead file, and no `finding.json`. Moved by bare name, every `scout.md` would
    collide on `incoming/scout.md`, and the negative would be booked under the word `scout`
    or not at all. It scores the lowest freshness, so it never replaces a copy with a
    finding, and a second scout copy of the same slug is dropped. What `.md` is left after
    that is loose prose with a name of its own, such as `_scout/`'s lead-less negatives.
    """
    convert_ledger(fleet)
    moved = leads = 0
    for run in sorted(p for p in incoming.iterdir() if p.is_dir() and p.name.startswith("run_")):
        for lead in sorted(p for p in run.rglob("*") if p.is_dir() and _lead_dir(p)):
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
        keep_leftovers(incoming, run)
        shutil.rmtree(run, ignore_errors=True)
    print(f"drain: {leads} lead directories, {moved} loose findings")
    return 0


def _lead_dir(path: Path) -> bool:
    """A directory holding a finding, or a scout lead's directory holding only its prose."""
    if (path / SIDECAR).is_file():
        return True
    return path.parent.name == "leads" and (path / "scout.md").is_file()


def keep_leftovers(incoming: Path, run: Path) -> None:
    """Anything the drain did not recognise, kept where a human can find it.

    The run directory is removed once it is drained, so a file no rule matched (a rejected
    lead, a leg's extractor, a shape a later wave invents) would go with it silently. They
    are few and small, and a corpus nobody can re-read is the failure this whole lane exists
    to avoid, so they move rather than vanish. The run's `telemetry.json` is not one: the
    fleet ledger's leg lines hold each leg's spend, so it dies with the run.
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


def convert_ledger(fleet: Path | None) -> None:
    """The old TSV ledger, once, as the fleet ledger's legacy lines, and deleted only then.

    Each row becomes `{"row", "line", "at"}`: its 1-based line number, its text, and its own
    stamp as the line's time. The fleet keys a legacy line on the row and the text together,
    because the old ledger repeats identical rows, so a rerun over a fresh copy adds none.
    Anything short of every row in the fleet ledger keeps the file for the next tick: a fleet
    clone that predates `scripts/ledger.py`, which the sync never pulls, or a row with no
    stamp to date it. Neither stops the tick.
    """
    tsv = Path(os.environ.get("ARK_FLEET_LEDGER") or LEDGER)
    if not tsv.is_file():
        return
    if not fleet_ledger.available(fleet):
        where = "no --fleet was given" if fleet is None else f"{fleet} has no scripts/ledger.py"
        print(f"drain: {tsv.name} kept, {where} to convert it into")
        return
    body = tsv.read_text(encoding="utf-8")
    rows = []
    for number, line in enumerate(body.removesuffix("\n").split("\n") if body else [], 1):
        stamp = line.split("\t", 1)[0]
        try:
            if not _STAMP.fullmatch(stamp):
                raise ValueError(stamp)
            at = datetime.strptime(stamp, "%Y%m%dT%H%MZ").strftime("%Y-%m-%dT%H:%M:00Z")
        except ValueError:
            print(f"drain: {tsv.name} kept, row {number} has no stamp to date it: {line[:60]!r}")
            return
        rows.append({"row": number, "line": line, "at": at})
    ok, said = fleet_ledger.append(fleet, "legacy", rows)
    if not ok:
        print(f"drain: {tsv.name} kept, the fleet ledger refused it: {said}")
        return
    tsv.unlink()
    print(f"drain: {tsv.name} converted, {len(rows)} rows as legacy lines ({said}), and deleted")


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
    # C-86: a listing or a registry record is a delimited field, and takes no split.
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


# --- outcome ------------------------------------------------------------------


def _figure(value) -> float | None:
    """A figure as JSON can carry it: a finite number, else None."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None


def decision_of(decided: dict, source: str, etype) -> str:
    """The register's decision for a find's source and class, or `pending` while no block
    exists. A lead that names no class takes its source's block."""
    if (source, etype) in decided:
        return decided[(source, etype)].decision
    if not etype:
        for (name, _), approval in decided.items():
            if name == source:
                return approval.decision
    return "pending"


def outcome(incoming: Path, fleet: Path, register: Path | None, banked: bool) -> int:
    """One outcome line per confirmed FIND with a store price, in one append.

    The line carries both figures and how far they agree, so the streak that hands the
    decision to the program's figure is read from the fleet ledger and not from a count kept
    here. `banked` is true only for a `master` decision whose register commit has landed,
    which the caller says with `--banked`, and it is a JSON bool: the fleet keys a line on
    slug, decision and banked, and the string `"true"` would key as another line.
    """
    # Imported here: the register is read through the store package, which the drain the
    # tick runs every hour has no need of.
    import fleet_request

    from ark import approvals

    decided = approvals.load(register or fleet_request.REGISTER)
    rows = []
    for path in sidecars(incoming):
        finding = load(path)
        lead = path.parent
        if finding.get("verdict") != "FIND":
            continue
        if (finding.get("verify") or {}).get("status") != "confirmed":
            continue
        if not (lead / STORE_PRICE).is_file():
            continue
        store = load(lead / STORE_PRICE)
        store_ee = _figure(store.get("ee"))
        program_ee = _figure(store.get("fleet_program_ee"))
        # The source is named the way the request block names it.
        source = fleet_request.source_key(lead.name)
        decision = decision_of(decided, source, load(lead / LEAD).get("evidence_class"))
        rows.append(
            {
                "slug": lead.name,
                "store_ee": store_ee,
                "program_ee": program_ee,
                "agreement_pct": fleet_ledger.agreement_pct(store_ee, program_ee),
                "decision": decision,
                "banked": decision == "master" and banked,
            }
        )
    if not rows:
        print("outcome: no confirmed FIND with a store price, nothing to book")
        return 0
    ok, said = fleet_ledger.append(fleet, "outcome", rows)
    print(f"outcome: {len(rows)} confirmed finds, {said if ok else f'not booked: {said}'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["drain", "validate", "reprice", "outcome"])
    ap.add_argument("incoming", type=Path)
    ap.add_argument(
        "--fleet",
        type=Path,
        help="the fleet clone: its ledger for drain and outcome, its schema for validate",
    )
    ap.add_argument(
        "--register",
        type=Path,
        help="outcome: the approvals register, by default docs/registers/approved-sources-list.md",
    )
    ap.add_argument(
        "--banked",
        action="store_true",
        help="outcome: the register commit has landed, so a master decision is banked",
    )
    args = ap.parse_args(argv)

    incoming = args.incoming.expanduser()
    if not incoming.is_dir():
        print(f"{incoming} is not a directory", file=sys.stderr)
        return 1
    fleet = args.fleet.expanduser() if args.fleet is not None else None
    if args.command == "drain":
        return drain(incoming, fleet)
    if args.command == "reprice":
        return reprice(incoming)
    if fleet is None:
        ap.error(f"{args.command} needs --fleet")
    if args.command == "outcome":
        return outcome(incoming, fleet, args.register, args.banked)
    return validate(incoming, fleet)


if __name__ == "__main__":
    raise SystemExit(main())
