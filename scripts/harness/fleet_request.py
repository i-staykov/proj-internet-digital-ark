"""Write the pending request block a fleet FIND needs, so there is something to decide.

**Nothing else writes one.** `standing_rule.py` and `sync_approvals.py` both iterate blocks
that already exist in `docs/registers/approved-sources-list.md`; the only writer was
`request_approval.py` behind `just approve`, run by a human, and before that the model
admitter this replaced. So a confirmed FIND from the fleet used to reach the register as a
row and stop: no block, no `Decision:` line, nothing for the standing rule to flip and
nothing for Ivo to merge.

**The registered spec gets the good block.** When the slug names a spec `ark ingest` knows,
`request_approval.py` writes the request, with a seeded-random sample of real records and
live links, which is the whole point of that tool: the reader checks records rather than an
agent's argument. That is the path for a source this repository can already ingest.

**Everything else gets the honest short block.** A source the fleet has just found has no
spec, no parser and no collector here, so there is nothing to sample and nothing an approval
could ingest yet. The block says exactly that, carries both figures, quotes the stamp, names
the items file the figures came from, and asks for the decision anyway, because the decision
is what unblocks writing the collector. `bank_approved.py` is loud about a block it cannot
bank, which is the behaviour wanted here rather than a silent yes.

**The standing rule's finds, by its figure, and an ask only where it parks.** The candidates
are `standing_rule.confirmed_finds`, so every block written here is one the standing rule
reads, and the block quotes the figure that decides. A source the standing rule would decide
gets its block and no ask: `standing_rule.py` writes its `Decision:` line in the same bank.
A source it parks gets its OPEN entry, the ask the owner reads, naming why: headed
`Approve <source> / <class>` when the class is new, and `Outside the standing bounds:
<source> / <class>` when only the admission or a clause failed, which `queue.md` omits.

    uv run python scripts/harness/fleet_request.py INCOMING [--fleet FLEET] [--write]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_ledger  # noqa: E402
import standing_rule  # noqa: E402

from ark import approvals  # noqa: E402
from ark.evidence_types import MASTER_TYPES  # noqa: E402
from ark.hostnames import fleet_read_source_name  # noqa: E402
from ark.key_decisions import raise_open  # noqa: E402
from ark.sources import SOURCES  # noqa: E402

REGISTER = REPO / "docs/registers/approved-sources-list.md"
SECTION = "## Pending requests"
FIGURE = {"store": "the store", "program": "the program"}
NO_ASK = "no ask: the standing rule decides it"
# The ask for a park in an approved class; `lead_queue.py` keeps it off the new-class list.
OUTSIDE = "Outside the standing bounds: {} / {}"
# Where `fleet_findings.py` pulls a lead's whole read, one directory of journal parts.
FLEET_READ = REPO / "data/raw/fleet_read"
READ_CLASS = "cdx_timestamp"


def _json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def source_key(slug: str) -> str:
    """The register's naming, which is the spec's: underscores, not hyphens."""
    return re.sub(r"[^a-z0-9]+", "_", slug.lower()).strip("_")


def candidates(incoming: Path, outcomes: list[dict]) -> list[tuple[Path, dict, dict, dict]]:
    """The standing rule's confirmed FINDs, each with its lead and its deciding figure.

    The same finds by the same figure, so a block written here is never one the standing
    rule cannot see: `find` is its entry, with the re-price, `figure` and `ee`.
    """
    return [
        (find["dir"], find["finding"], _json(find["dir"] / "lead.json"), find)
        for find in standing_rule.confirmed_finds(incoming, outcomes).values()
    ]


def figure_said(find: dict) -> str:
    """The deciding figure, in bold, and what it was measured on."""
    store = find["store"]
    if find["figure"] == "program":
        return (
            f"**{find['ee']:,.1f} EE net-new by the program on the pushed snapshot**, which "
            f"agreed with the live store within 1% on the last {fleet_ledger.STREAK} finds"
        )
    netnew = store.get("netnew") or 0
    return f"**{find['ee']:,.1f} EE net-new on the live store** over {netnew:,} records"


def request_class(lead_dir: Path, lead: dict) -> tuple[str, str | None]:
    """(source, evidence type) the lead's block asks about.

    A lead the fleet read whole banks its journal parts under its own hostname source, in
    the capture class, whatever class the scout recorded for the sample.
    """
    if (lead_dir / "read.json").is_file():
        return fleet_read_source_name(lead_dir.name), READ_CLASS
    return source_key(lead_dir.name), lead.get("evidence_class")


def read_lines(lead_dir: Path) -> list[str]:
    """The ingest and journal lines of a read lead's block, from the pulled receipt."""
    parts = FLEET_READ / lead_dir.name
    where = parts.relative_to(REPO) if parts.is_relative_to(REPO) else parts
    receipt = _json(parts / "receipt.json")
    sha = receipt.get("journal_sha256") or "no receipt on this machine"
    count = len(receipt.get("parts") or [])
    return [
        f"- ingest: ark ingest-hostnames {where}/",
        f"- journal sha256: {sha}, {count} part(s), {receipt.get('lines', 0):,} rows read "
        f"whole from the artifact",
    ]


def block(lead_dir: Path, finding: dict, lead: dict, find: dict) -> str:
    """The short block, built from the sidecar, the lead and the re-price. No prose invented.

    Every line is a fact one of those three files carries. Where one of them says nothing,
    the line says so: an approval decided on a blank is worse than one deferred. One fact per
    line and no blank line, the shape the compactor keeps a pending block in.
    """
    key, etype = request_class(lead_dir, lead)
    read = etype == READ_CLASS and (lead_dir / "read.json").is_file()
    spec = SOURCES.get(key)
    store = find["store"]
    stamp = str(lead.get("what_dates_one_item") or "not recorded in the lead")
    artifact = (lead.get("artifact") or {}) | (finding.get("artifact") or {})
    fleet_ee = (finding.get("pricing") or {}).get("ee")
    fleet_said = f"{fleet_ee:,.1f}" if isinstance(fleet_ee, int | float) else "no figure"
    store_ee = store.get("ee")
    store_said = f"{store_ee:,.1f} EE" if isinstance(store_ee, int | float) else "no figure"
    items = lead_dir / "items.jsonl"
    # Relative when it is under the checkout, which is where the drain puts it, and absolute
    # when someone points this at a directory elsewhere rather than crashing on the block.
    where = items.relative_to(REPO) if items.is_relative_to(REPO) else items
    head = (
        read_lines(lead_dir)
        if read
        else [
            (
                f"- ingest spec: `{key}`"
                if spec
                else "- ingest spec: none in this repository yet. The fleet found and priced "
                "this; no collector or parser here reads it, so a yes is a decision to write "
                "one and `bank_approved.py` will say it banked nothing until that exists"
            ),
            f"- journal: `{where if items.is_file() else 'not on this machine'}`, "
            f"the items the figures below were measured from",
        ]
    )
    lines = [
        f"### {key} / {etype}",
        *head,
        f"- refetch: {artifact.get('url') or 'the lead records no URL'}",
        f"- terms: {artifact.get('terms_url') or 'the lead records no terms page'}, "
        f"robots {artifact.get('robots') or 'unrecorded'}",
        f"- what dates one item: {stamp}",
        (
            f"- measured {dt.date.today().isoformat()}: {figure_said(find)}, by "
            f"`{store.get('pricer')}`. The fleet said {fleet_said} EE against the pushed "
            f"snapshot; the store figure is the one to read"
            if find["figure"] == "store"
            else f"- measured {dt.date.today().isoformat()}: {figure_said(find)}. The live "
            f"store re-price by `{store.get('pricer')}` said {store_said}, and the fleet said "
            f"{fleet_said} EE; the program's figure is the one to read"
        ),
        f"- fleet run {finding.get('run_id', 'unknown')}, lens {lead.get('lens', 'unrecorded')}, "
        f"grain {lead.get('grain', 'unrecorded')}, verified by a second leg",
        f"- potential: {find['ee']:.0f}",
        "Decision: pending",
    ]
    return "".join(" ".join(line.split()) + "\n" for line in lines)


def heading(key: str, etype: str, reasons: list[str]) -> str:
    """`Approve <source> / <class>` when the class is new, else the outside-the-bounds ask.

    Both carry `<source> / <class>`, the phrase the gate's surfaced test looks for.
    """
    if standing_rule.NEW_CLASS.format(etype) in reasons:
        return f"Approve {key} / {etype}"
    return OUTSIDE.format(key, etype)


def surface(
    key: str,
    etype: str,
    lead: dict,
    find: dict,
    reasons: list[str],
    decisions: Path | None = None,
) -> bool:
    """The OPEN entry in `key-decisions.md`, which is the one surface the owner reads.

    A pending block with no OPEN entry is a request nobody was told about, and the gate
    refuses it (`test_every_pending_approval_is_surfaced_in_the_live_files`). The tool
    path writes its own; this is the short path's, for a source the standing rule parks,
    with `reasons` the ones it parked on.
    """
    body = (
        f"Parked by the standing rule: {'; '.join(reasons)}. Found and priced by the fleet "
        f"under the {lead.get('lens', 'unrecorded')} lens, confirmed by a second leg: "
        f"{figure_said(find)}. The block is under `## Pending requests` in "
        f"`approved-sources-list.md`; merge the approval pull request to say yes, close it to "
        f"leave the source pending.\n\nWorth: {find['ee']:.0f} EE."
    )
    if decisions is not None and not Path(decisions).is_file():
        # A register somewhere else, as in a test, has no decisions document beside it.
        # Writing to the real one from there is what put a fake entry into the live
        # `key-decisions.md` on 2026-09-15 and had the hourly sync refuse a dirty clone.
        print(f"request: no decisions document at {decisions}, OPEN entry not written")
        return False
    return raise_open(heading(key, etype, reasons), body, decisions)


def append(register: Path, text: str) -> None:
    """Insert above the section's first block, so the newest ask is the first one read.

    The section's `None.` goes once something is pending, and a blank line parts each block
    from the next, the shape the compactor writes.
    """
    current = register.read_text(encoding="utf-8")
    start = current.index(SECTION)
    stop = current.find("\n## ", start)
    stop = len(current) if stop == -1 else stop + 1
    intro, sep, blocks = current[start + len(SECTION) : stop].partition("\n### ")
    said = [line for line in intro.splitlines() if line.strip() and line.strip() != "None."]
    section = "\n\n".join([SECTION, *(["\n".join(said)] if said else []), text.rstrip("\n")])
    section += "\n\n" + ("### " + blocks.rstrip("\n") + "\n\n" if sep else "")
    rest = current[:start] + section + current[stop:]
    register.write_text(rest.rstrip("\n") + "\n", encoding="utf-8")


def by_the_tool(key: str, lead_dir: Path, lead: dict, artifact: dict) -> bool:
    """`request_approval.py` for a spec this repository can already ingest. True when it wrote.

    Its refusals are all good ones (a rejected class, a decided class, a store that already
    holds the source's rows), so a non-zero exit is reported and the short block is written
    instead of nothing.
    """
    items = lead_dir / "items.jsonl"
    if not items.is_file():
        return False
    done = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/harness/request_approval.py",
            key,
            "--journal",
            str(items),
            "--source-url",
            str(artifact.get("url") or ""),
            "--dating",
            str(lead.get("what_dates_one_item") or ""),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if done.returncode == 0:
        print(f"request: {key} written by request_approval.py, with its sample")
        return True
    why = done.stdout.strip() or done.stderr.strip()
    print(f"request: request_approval.py refused {key}: {why}")
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("incoming", type=Path)
    ap.add_argument("--register", type=Path, default=REGISTER)
    ap.add_argument("--write", action="store_true", help="without it, say what it would write")
    ap.add_argument(
        "--fleet",
        type=Path,
        default=None,
        help="the fleet clone whose ledger holds the outcome lines; without it the store "
        "re-price decides",
    )
    ap.add_argument(
        "--decisions",
        type=Path,
        default=None,
        help="key-decisions.md; by default the one beside the register, docs/lore/key-decisions.md",
    )
    args = ap.parse_args(argv)

    incoming = args.incoming.expanduser()
    if not incoming.is_dir():
        print(f"{incoming} is not a directory", file=sys.stderr)
        return 1

    fleet = args.fleet.expanduser() if args.fleet else None
    outcomes = fleet_ledger.lines(fleet, "outcome")
    written = 0
    for lead_dir, finding, lead, find in candidates(incoming, outcomes):
        key, etype = request_class(lead_dir, lead)
        if etype not in MASTER_TYPES:
            print(f"request: {key} is {etype or 'of no recorded class'}, which needs no approval")
            continue
        decided = approvals.load(args.register)
        if (key, etype) in decided:
            print(f"request: {key} / {etype} already has a block, left alone")
            continue
        # The standing rule's own test, on the register as it stands and the lead it will
        # read, so a source it decides in this bank is not asked about first.
        ask = standing_rule.reasons_to_park(
            SimpleNamespace(source_name=key, evidence_type=etype), lead, decided
        )
        said = "and ask" if ask else NO_ASK
        if not args.write:
            by = FIGURE[find["figure"]]
            print(f"would write: {key} / {etype}, {find['ee']:,.1f} EE by {by}, {said}")
            continue
        artifact = (lead.get("artifact") or {}) | (finding.get("artifact") or {})
        if not (SOURCES.get(key) and by_the_tool(key, lead_dir, lead, artifact)):
            append(args.register, block(lead_dir, finding, lead, find))
            if ask:
                decisions = (
                    args.decisions or args.register.parent.parent / "lore" / "key-decisions.md"
                )
                surface(key, etype, lead, find, ask, decisions)
                print(f"request: wrote a pending block for {key} / {etype}, and its OPEN entry")
            else:
                print(f"request: wrote a pending block for {key} / {etype}, {NO_ASK}")
        written += 1
    if args.write:
        print(f"request: {written} blocks written; the standing rule decides them next")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
