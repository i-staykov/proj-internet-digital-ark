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

    uv run python scripts/harness/fleet_request.py data/fleet_findings/incoming [--write]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark import approvals  # noqa: E402
from ark.evidence_types import MASTER_TYPES  # noqa: E402
from ark.sources import SOURCES  # noqa: E402

REGISTER = REPO / "docs/registers/approved-sources-list.md"
SECTION = "## Pending requests"


def _json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def source_key(slug: str) -> str:
    """The register's naming, which is the spec's: underscores, not hyphens."""
    return re.sub(r"[^a-z0-9]+", "_", slug.lower()).strip("_")


def candidates(incoming: Path) -> list[tuple[Path, dict, dict, dict]]:
    """Every confirmed FIND the laptop re-priced, with its lead and its store figure."""
    out = []
    for lead_dir in sorted(p for p in incoming.iterdir() if p.is_dir()):
        finding = _json(lead_dir / "finding.json")
        store = _json(lead_dir / "store_price.json")
        lead = _json(lead_dir / "lead.json")
        if finding.get("verdict") != "FIND":
            continue
        if (finding.get("verify") or {}).get("status") != "confirmed":
            continue
        if not isinstance(store.get("ee"), int | float) or store["ee"] <= 0:
            continue
        out.append((lead_dir, finding, lead, store))
    return out


def block(lead_dir: Path, finding: dict, lead: dict, store: dict) -> str:
    """The short block, built from the sidecar, the lead and the re-price. No prose invented.

    Every line is a fact one of those three files carries. Where one of them says nothing,
    the line says so: an approval decided on a blank is worse than one deferred.
    """
    key = source_key(lead_dir.name)
    spec = SOURCES.get(key)
    stamp = str(lead.get("what_dates_one_item") or "not recorded in the lead")
    artifact = (lead.get("artifact") or {}) | (finding.get("artifact") or {})
    fleet_ee = (finding.get("pricing") or {}).get("ee")
    fleet_said = f"{fleet_ee:,.1f}" if isinstance(fleet_ee, int | float) else "no figure"
    items = lead_dir / "items.jsonl"
    # Relative when it is under the checkout, which is where the drain puts it, and absolute
    # when someone points this at a directory elsewhere rather than crashing on the block.
    where = items.relative_to(REPO) if items.is_relative_to(REPO) else items
    lines = [
        f"### {key} / {lead.get('evidence_class')}",
        "",
        (
            f"- ingest spec: `{key}`"
            if spec
            else "- ingest spec: none in this repository yet. The fleet found and priced this; "
            "no collector or parser here reads it, so a yes is a decision to write one and "
            "`bank_approved.py` will say it banked nothing until that exists"
        ),
        f"- journal: `{where if items.is_file() else 'not on this machine'}`, "
        f"the items the figures below were measured from",
        f"- refetch: {artifact.get('url') or 'the lead records no URL'}",
        f"- terms: {artifact.get('terms_url') or 'the lead records no terms page'}, "
        f"robots {artifact.get('robots') or 'unrecorded'}",
        f"- what dates one item: {stamp}",
        (
            f"- measured {dt.date.today().isoformat()}: **{store['ee']:,.1f} EE net-new on the "
            f"live store** over {store.get('netnew', 0):,} records, by `{store.get('pricer')}`. "
            f"The fleet said {fleet_said} EE against the pushed snapshot; the store figure is "
            f"the one to read"
        ),
        f"- fleet run {finding.get('run_id', 'unknown')}, lens {lead.get('lens', 'unrecorded')}, "
        f"grain {lead.get('grain', 'unrecorded')}, verified by a second leg",
        f"- potential: {store['ee']:.0f}",
        "",
        "Decision: pending",
        "",
    ]
    return "\n".join(lines)


def append(register: Path, text: str) -> None:
    """Insert under the pending heading, so the newest ask is the first one read."""
    current = register.read_text(encoding="utf-8")
    at = current.index(SECTION) + len(SECTION)
    end = current.index("\n", at) + 1
    register.write_text(current[:end] + "\n" + text + current[end:], encoding="utf-8")


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
    args = ap.parse_args(argv)

    incoming = args.incoming.expanduser()
    if not incoming.is_dir():
        print(f"{incoming} is not a directory", file=sys.stderr)
        return 1

    written = 0
    for lead_dir, finding, lead, store in candidates(incoming):
        key = source_key(lead_dir.name)
        etype = lead.get("evidence_class")
        if etype not in MASTER_TYPES:
            print(f"request: {key} is {etype or 'of no recorded class'}, which needs no approval")
            continue
        decided = approvals.load(args.register)
        if (key, etype) in decided:
            print(f"request: {key} / {etype} already has a block, left alone")
            continue
        if not args.write:
            print(f"would write: {key} / {etype}, {store['ee']:,.1f} EE on the store")
            continue
        artifact = (lead.get("artifact") or {}) | (finding.get("artifact") or {})
        if not (SOURCES.get(key) and by_the_tool(key, lead_dir, lead, artifact)):
            append(args.register, block(lead_dir, finding, lead, store))
            print(f"request: wrote a pending block for {key} / {etype}")
        written += 1
    if args.write:
        print(f"request: {written} blocks written; the standing rule decides them next")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
