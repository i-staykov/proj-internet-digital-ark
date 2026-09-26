"""Flatten, validate and re-price the findings the hourly tick drains out of the fleet.

**A fleet figure never reaches the register alone.** The leg that measured a corpus priced
it against the pushed snapshot, which is a copy of the store's exports and his baseline and
not the store; it can be hours stale, and it was produced by the same agent that wants the
answer to be large. So a FIND its own verify lane confirmed is priced a second time HERE, by
`price_items.py` or `price_hostnames.py`, against the live store, and the scribe books both
numbers side by side. The program a leg runs prices the same items against the snapshot the
last push staged, and how far it agrees with the store goes beside them in `store_price.json`.
A FIND that ships no items cannot be re-priced, and that says so in the register.

Four subcommands, in order: the tick runs drain and validate, `just bank` runs reprice and,
once its commit has landed, outcome over this drain and every drain banked before it.

    drain     the downloaded run directories become one directory per lead, and the old
              TSV ledger becomes the fleet ledger's legacy lines, once
    validate  every sidecar against the fleet's own schema, via the fleet's own validator
    reprice   every confirmed FIND against the live store and by the program
    outcome   one fleet ledger line per confirmed FIND: both figures, the decision, banked

    uv run python scripts/harness/fleet_findings.py drain data/fleet_findings/incoming \\
        --fleet ~/Documents/GitHub/ark-fleet
    uv run python scripts/harness/fleet_findings.py validate data/fleet_findings/incoming \\
        --fleet ~/Documents/GitHub/ark-fleet
    uv run python scripts/harness/fleet_findings.py reprice data/fleet_findings/incoming
    uv run python scripts/harness/fleet_findings.py outcome data/fleet_findings/incoming \\
        data/fleet_findings/banked/*/ --fleet ~/Documents/GitHub/ark-fleet [--register R] [--db D]
"""

from __future__ import annotations

import argparse
import hashlib
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
# What the program prices against: the snapshot the last push staged. Relative to REPO, so
# no local path reaches store_price.json.
SNAPSHOT = Path("output/fleet_snapshot")
# A corpus `read.yaml` read whole: its journal parts and `receipt.json` on the VPS, pulled
# here per lead. The pull is the gate: only a complete read whose every part matches the
# sha256 the receipt lists lands, so what the bank ingests is exactly what the read wrote.
VPS_JOURNALS = "/projects/ark-data/journals"
FLEET_READ = REPO / "data/raw/fleet_read"
READ = "read.json"
# A part's name as `read.py` writes it and `ark.hostnames.FLEETREAD` reads it: never a path.
PART = re.compile(r"fleetread_[a-z0-9]+(?:_[a-z0-9]+)*__[a-z0-9][a-z0-9-]*_\d{4}\.jsonl\.gz")
# The old spend record, converted into legacy lines and then set aside. `ARK_FLEET_LEDGER`
# moves it, so a drain under test never moves the real one.
LEDGER = REPO / "data/logs/fleet_ledger.tsv"
# The store whose ingested files say which sources are banked, read only, under the bank's lock.
DB = REPO / "data/ark.duckdb"
# The decisions that let a source's rows into the store at all.
INGESTIBLE = frozenset({"master", "candidate-only"})

_ITEMS_EE = re.compile(r"net-new AFTER the split\s*:\s*([\d,]+) pairs, ([\d,]+\.?\d*) EE")
_HOST_EE = re.compile(r"NET-NEW hostname years ([\d,]+)\s+([\d,]+\.?\d*) EE")
# The old ledger's first field: the drain's minute, as the tick's run label writes it.
_STAMP = re.compile(r"\d{8}T\d{4}Z")
# A row a test drain wrote into the live TSV: 5 tokens and no window. #171 drops these by
# this shape; converted first, they would stand in the fleet ledger for good.
_TEST_ROW = re.compile(r"\d{8}T\d{4}Z\t5\t\?")


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
    """The old TSV ledger as the fleet ledger's legacy lines, set aside once fleet main has them.

    Each row becomes `{"row", "line", "at"}`: its 1-based line number, its text, and its own
    stamp as the line's time. The fleet keys a legacy line on the row and the text together,
    because the old ledger repeats identical rows, so each tick's rerun adds none. Anything
    short of every row on the clone's `origin/main` keeps the file for the next tick, since
    push_fleet.sh's replay can drop an unpushed line: a fleet clone that predates
    `scripts/ledger.py`, a row with no stamp to date it, a test drain's row still waiting for
    #171's drop, or a push not landed yet. None stops the tick. The file is renamed
    `.converted`, beside any earlier one, never deleted.
    """
    tsv = Path(os.environ.get("ARK_FLEET_LEDGER") or LEDGER)
    if not tsv.is_file():
        return
    if not fleet_ledger.available(fleet):
        where = "no --fleet was given" if fleet is None else f"{fleet} has no scripts/ledger.py"
        print(f"drain: {tsv.name} kept, {where} to convert it into")
        return
    body = tsv.read_text(encoding="utf-8")
    lines = body.removesuffix("\n").split("\n") if body else []
    tests = sum(1 for line in lines if _TEST_ROW.fullmatch(line))
    if tests:
        print(
            f"drain: {tsv.name} kept, {tests} rows are a test drain's (5 tokens, no window):"
            " #171's drop must run before the conversion"
        )
        return
    rows = []
    for number, line in enumerate(lines, 1):
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
    landed = fleet_ledger.lines(fleet, "legacy", ref="origin/main")
    held = {(line.get("row"), line.get("line")) for line in landed}
    found = sum((row["row"], row["line"]) in held for row in rows)
    if found != len(rows):
        print(f"drain: {tsv.name} kept, fleet main holds {found} of its {len(rows)} rows ({said})")
        return
    aside, n = tsv.with_name(f"{tsv.name}.converted"), 1
    while aside.exists():
        n += 1
        aside = tsv.with_name(f"{tsv.name}.converted.{n}")
    tsv.rename(aside)
    print(f"drain: {tsv.name} converted, {len(rows)} legacy lines ({said}), now {aside.name}")


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


def journals_remote() -> str:
    """Where a read's journal parts live, the same host `items_remote` names."""
    if os.environ.get("ARK_READ_REMOTE"):
        return os.environ["ARK_READ_REMOTE"]
    items = items_remote()
    return items.removesuffix(VPS_ITEMS) + VPS_JOURNALS if items.endswith(VPS_ITEMS) else ""


def _sha256(path: Path, whole=None) -> str:
    """The file's sha256, feeding the same bytes to `whole` when one is passed."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
            if whole is not None:
                whole.update(chunk)
    return digest.hexdigest()


def verify_read(directory: Path) -> str:
    """ "" when the directory holds a complete read whose parts match its receipt, else why."""
    try:
        receipt = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "no readable receipt.json"
    if receipt.get("complete") is not True:
        return "the receipt does not say complete"
    parts = receipt.get("parts") or []
    if not parts:
        return "the receipt lists no parts"
    listed = {str(part.get("name")) for part in parts}
    stray = sorted(n for n in listed if not PART.fullmatch(n))
    if stray:
        return f"{stray[0]} is not a fleet read part name"
    extra = sorted(p.name for p in directory.iterdir() if p.name not in listed | {"receipt.json"})
    if extra:
        return f"{extra[0]} is not in the receipt"
    whole = hashlib.sha256()
    for part in parts:
        path = directory / str(part.get("name"))
        if not path.is_file() or _sha256(path, whole) != part.get("sha256"):
            return f"{path.name} is missing or does not match its sha256"
    wanted = receipt.get("journal_sha256")
    if wanted and whole.hexdigest() != wanted:
        return "the parts together do not match journal_sha256"
    return ""


def fetch_read(lead: Path) -> Path | None:
    """The lead's whole read in `data/raw/fleet_read/<slug>/`, pulled and verified.

    A read already here and verified is not pulled again. A pull that does not verify is
    removed, so a half-copied or incomplete read never reaches the bank.
    """
    target = FLEET_READ / lead.name
    if target.is_dir() and not verify_read(target):
        return target
    remote = journals_remote()
    if not remote:
        print(f"reprice: no ARK_VPS in local.env, so {lead.name}'s read cannot be pulled")
        return None
    staging = FLEET_READ / f".{lead.name}.part"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    done = subprocess.run(
        ["rsync", "-a", f"{remote}/{lead.name}/", f"{staging}/"], capture_output=True, text=True
    )
    why = done.stderr.strip() if done.returncode else verify_read(staging)
    if why:
        shutil.rmtree(staging, ignore_errors=True)
        print(f"reprice: {lead.name}'s read not pulled: {why}")
        return None
    shutil.rmtree(target, ignore_errors=True)
    staging.rename(target)
    where = target.relative_to(REPO) if target.is_relative_to(REPO) else target
    print(f"reprice: pulled {lead.name}'s whole read into {where}")
    return target


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
    """Run the store pricer over the leg's own items and return what it measured.

    A lead the fleet read whole is priced on its pulled journal parts, at hostname grain,
    where error captures date no year.
    """
    if (lead / READ).is_file():
        parts = fetch_read(lead)
        if parts is None:
            return {"status": "the read was not pulled, see the run log", "ee": None}
        grain, script = "hostname", "price_hostnames.py"
        cmd = ["uv", "run", "python", f"scripts/pricing/{script}", str(parts)]
    else:
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
    `fleet_ledger.WITHIN`, over every store price in `incoming` and the drains banked beside
    it. A find counts once, at its latest price; one the program did not price breaks the run, so an
    outage or a zero cannot keep it alive."""
    latest: dict[str, dict] = {}
    banked = (incoming.parent / "banked").glob(f"*/*/{STORE_PRICE}")
    for path in [*banked, *incoming.glob(f"*/{STORE_PRICE}")]:
        doc = load(path)
        if fleet_ledger.positive(doc.get("ee")) is None:
            continue
        slug = path.parent.name
        if slug not in latest or str(doc.get("at") or "") >= str(latest[slug].get("at") or ""):
            latest[slug] = doc
    run = 0
    for doc in sorted(latest.values(), key=lambda d: str(d.get("at") or ""), reverse=True):
        store, program = float(doc["ee"]), fleet_ledger.positive(doc.get("fleet_program_ee"))
        if program is None or abs(program - store) > fleet_ledger.WITHIN * store:
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
            program_ee = result["fleet_program_ee"]
            result["agreement_pct"] = fleet_ledger.agreement_pct(result["ee"], program_ee)
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
        f"reprice: the program agrees with the store within {fleet_ledger.WITHIN:.0%} "
        f"on the last {streak(incoming)} finds in a row"
    )
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


def ingested(db: Path) -> set[str] | None:
    """Every source name the store's ingest wrote, or None when the store cannot be read.
    Read only and capped through `ark.db`: `just bank` holds the lock that keeps any writer out."""
    try:
        from ark.db import connect_read_only_patiently

        conn = connect_read_only_patiently(db, patience_s=60)
    except Exception as exc:
        print(f"outcome: the store could not be opened ({exc}), so nothing is banked")
        return None
    try:
        rows = conn.execute("SELECT DISTINCT source_name FROM ingested_file").fetchall()
    except Exception as exc:
        print(f"outcome: the store's ingested files could not be read ({exc}), nothing is banked")
        return None
    finally:
        conn.close()
    return {str(name) for (name,) in rows if name}


def outcome(roots: list[Path], fleet: Path, register: Path | None, db: Path = DB) -> int:
    """One outcome line per confirmed FIND with a store price under `roots`, in one append.

    The line carries both figures and how far they agree, so the streak that hands the
    decision to the program's figure is read from the fleet ledger and not from a count kept
    here. **`banked` is the store's say, not the bank's**: true only once the source the
    register block names is among the store's ingested files under a decision that admits
    rows. A standing-rule master over a source with no ingest spec banks nothing, and a
    master a previous bank committed and ingested is banked whenever this runs next. It is a
    JSON bool: the fleet keys a line on slug, decision and banked, and the string `"true"`
    would key as another line.

    The bank passes this drain and every drain banked before it, so a find the owner
    approves later, or one ingested later, gains its banked line then; a line the ledger
    holds already is kept, not added. A slug under several roots is booked from its most
    settled copy. Exits 1 when the lines did not land, so the bank keeps its drain.
    """
    # Imported here: the register is read through the store package, which the drain the
    # tick runs every hour has no need of.
    import fleet_request

    from ark import approvals

    decided = approvals.load(register or fleet_request.REGISTER)
    finds: dict[str, Path] = {}
    for root in roots:
        for path in sidecars(root):
            finding = load(path)
            lead = path.parent
            if finding.get("verdict") != "FIND":
                continue
            if (finding.get("verify") or {}).get("status") != "confirmed":
                continue
            if not (lead / STORE_PRICE).is_file():
                continue
            if lead.name not in finds or freshness(lead) > freshness(finds[lead.name]):
                finds[lead.name] = lead
    if not finds:
        print("outcome: no confirmed FIND with a store price, nothing to book")
        return 0
    # Source and class as the request block names them: a whole read's block is its own
    # hostname source in the capture class, whatever class the scout recorded.
    classes = {
        slug: fleet_request.request_class(lead, load(lead / LEAD)) for slug, lead in finds.items()
    }
    sources = {slug: source for slug, (source, _) in classes.items()}
    decisions = {slug: decision_of(decided, *classes[slug]) for slug in finds}
    held: set[str] = set()
    if INGESTIBLE & set(decisions.values()):
        held = {fleet_request.source_key(name) for name in ingested(db) or ()}
    rows = []
    for slug, lead in finds.items():
        store = load(lead / STORE_PRICE)
        store_ee = _figure(store.get("ee"))
        program_ee = _figure(store.get("fleet_program_ee"))
        rows.append(
            {
                "slug": slug,
                "store_ee": store_ee,
                "program_ee": program_ee,
                "agreement_pct": fleet_ledger.agreement_pct(store_ee, program_ee),
                "decision": decisions[slug],
                "banked": decisions[slug] in INGESTIBLE and sources[slug] in held,
            }
        )
    ok, said = fleet_ledger.append(fleet, "outcome", rows)
    banked = sum(row["banked"] for row in rows)
    said = said if ok else f"not booked: {said}"
    print(f"outcome: {len(rows)} confirmed finds, {banked} banked in the store, {said}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["drain", "validate", "reprice", "outcome"])
    ap.add_argument(
        "incoming",
        type=Path,
        nargs="+",
        help="the drain; outcome also takes the drains banked before it",
    )
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
        "--db",
        type=Path,
        default=DB,
        help="outcome: the store whose ingested files say what is banked, read only",
    )
    args = ap.parse_args(argv)

    roots = [root.expanduser() for root in args.incoming]
    if args.command != "outcome" and len(roots) > 1:
        ap.error(f"{args.command} takes one directory")
    incoming = roots[0]
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
        # An unmatched glob of banked drains arrives as its own pattern: nothing to book there.
        return outcome([root for root in roots if root.is_dir()], fleet, args.register, args.db)
    return validate(incoming, fleet)


if __name__ == "__main__":
    raise SystemExit(main())
