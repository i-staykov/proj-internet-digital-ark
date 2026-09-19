"""Generate `docs/registers/queue.md`, the one list Ivo decides from.

**Why a generated page and not a register.** `approved-sources-list.md` binds `ark ingest`
and `sources-closed.md` stops a re-test; neither is a queue. The queue is what is still
live, ranked by what it is worth, and it goes stale the moment a lead moves. So it is
derived from the fleet's own `leads/*.json` every sync and never hand-edited.

**Ranked on `ee_low`, not `ee_high`.** The high figure is a projection and has been wrong
by five orders of magnitude at least once: `isc-domain-survey-free-editions` was scouted at
2,500,000 EE and measured at 6.2. The low figure is what a leg was willing to stand behind.

Ivo's floor of 2026-09-19: 5,000 EE of net-new to warrant his attention, master or
candidate, both tracks scoring at the same rate. Anything under it that has an obvious
ruling is ingested without asking.

**Named `lead_queue` and not `queue`.** `scripts/round/` lands on `sys.path` when anything
in it runs, so a module called `queue.py` here shadows the standard library's and every
import of `urllib3` below it dies on `queue.LifoQueue`. That took the hourly sync down on
2026-09-19 and stopped banking for a cycle.

    uv run python scripts/round/lead_queue.py --fleet ~/Documents/GitHub/ark-fleet [--write]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/registers/queue.md"
STORE = REPO / "data/ark.duckdb"
FLOOR = 5000.0

# What Ivo is actually being asked for, coarsest first. A lead's `blocked_on` is free
# text written by a scout, so it is matched rather than parsed.
ASKS = (
    ("download", re.compile(r"download|over the 1 ?gi?b|content type|exit [456]", re.I)),
    ("rule", re.compile(r"\brule\b|ruling", re.I)),
    ("permission", re.compile(r"permission|approval|terms", re.I)),
    ("rerun", re.compile(r"re-run|pricing cmd|runner that can", re.I)),
)


def ask_of(blocked: str) -> str:
    for name, pattern in ASKS:
        if pattern.search(blocked):
            return name
    return "review"


def banked(store: Path) -> set[str]:
    """Slugs the store already holds, from the names its own ingest wrote.

    **The reason this reads the store and not the lead file.** A lead reaches `verified`
    in the fleet, the laptop ingests it, and nothing writes `banked` back unless the class
    also carries a `Decision:` line. Four leads worth about 94,000 EE sat in this queue on
    2026-09-19 having been ingested days earlier, which is a queue that spends Ivo's
    attention on finished work. Read-only, and a held lock just means no check this run.
    """
    try:
        import duckdb

        conn = duckdb.connect(str(store), read_only=True)
    except Exception:
        return set()
    out: set[str] = set()
    try:
        for table, column in (
            ("ingested_file", "source_name"),
            ("evidence", "acquisition_method"),
        ):
            for (name,) in conn.execute(f"SELECT DISTINCT {column} FROM {table}").fetchall():
                if name:
                    out.add(re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-"))
    except Exception:
        return out
    finally:
        conn.close()
    return out


def held_state(slug: str, held: set[str]) -> str:
    """ "" for unheld, "banked" for a name that is exactly this lead, "similar" otherwise.

    **Only an exact name drops a lead.** The ingest and the scout shorten differently, so a
    looser match is a guess, and a wrong guess here deletes a live lead: the never-read
    Usenet hierarchies share a class name with the partition already banked, and the whole
    point of that lead is the partition nobody has read. A guess is shown, never acted on.
    """
    if slug in held:
        return "banked"
    parts = [p for p in slug.split("-") if len(p) > 3]
    if len(parts) >= 3 and any(sum(p in name for p in parts) >= 3 for name in held):
        return "similar"
    return ""


def leads(fleet: Path, held: set[str]) -> list[dict]:
    live = []
    for path in sorted((fleet / "leads").glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or doc.get("status") not in ("scouted", "verified"):
            continue
        size = doc.get("size_estimate") or {}
        low, high = size.get("ee_low"), size.get("ee_high")
        if not isinstance(low, (int, float)):
            low = 0.0
        if not isinstance(high, (int, float)):
            high = low
        blocked = str(doc.get("blocked_on") or "")
        slug = doc.get("slug") or path.stem
        state = held_state(slug, held)
        if state == "banked":
            continue
        live.append(
            {
                "slug": slug,
                "status": doc.get("status"),
                "low": float(low),
                "high": float(high),
                "blocked": blocked,
                "ask": ask_of(blocked) if blocked else "ingest",
                "class": str(doc.get("evidence_class") or "").split("(")[0].strip(),
                "held": state,
            }
        )
    return sorted(live, key=lambda r: (-r["low"], -r["high"]))


def render(rows: list[dict]) -> str:
    over = [r for r in rows if max(r["low"], r["high"]) >= FLOOR]
    under = len(rows) - len(over)
    out = [
        "# Queue",
        "",
        "Generated by `scripts/round/lead_queue.py` from the fleet's `leads/*.json`.",
        "Never hand-edit: an edit here is lost on the next sync, and the lead file is",
        "the thing the dealer reads.",
        "",
        f"**{len(over)} live lead(s) at or above the {FLOOR:,.0f} EE floor**, ranked on the LOW",
        "estimate, which is what a leg stood behind. The high figure is a projection and has been",
        "wrong by five orders of magnitude. Both tracks score at the same rate, so a candidate",
        f"counts like a master. {under} live lead(s) fall under the floor and are not listed.",
        "",
    ]
    # **The decisions, not the leads.** 22 rows is not a thing anyone decides; four asks
    # is. Each ask is one ruling that unblocks every lead under it, so it is ranked by
    # what it unblocks rather than by how many rows carry it.
    by_ask: dict[str, list[dict]] = {}
    for r in over:
        by_ask.setdefault(r["ask"], []).append(r)
    ranked = sorted(by_ask.items(), key=lambda kv: -sum(x["low"] for x in kv[1]))
    out += ["## Decide these, biggest first", ""]
    for ask, rows_for in ranked:
        low = sum(x["low"] for x in rows_for)
        high = sum(x["high"] for x in rows_for)
        best = max(rows_for, key=lambda x: x["low"])["slug"]
        out.append(
            f"- **{ask}**, {len(rows_for)} lead(s), {low:,.0f} to {high:,.0f} EE. "
            f"Biggest: `{best}`."
        )
    out += [
        "",
        "## Every live lead above the floor",
        "",
        "| EE low | EE high | asks for | lead | store |",
        "|---:|---:|---|---|---|",
    ]
    for r in over:
        out.append(
            f"| {r['low']:,.0f} | {r['high']:,.0f} | {r['ask']} "
            f"| `{r['slug']}` | {r['held'] or 'new'} |"
        )
    if any(r["held"] == "similar" for r in over):
        out += [
            "",
            "`similar` means the store already holds a name close to this one. It is a "
            "guess, not a match: check before spending a decision on it.",
        ]
    out += ["", "## What each ask means", ""]
    for name, text in (
        (
            "download",
            "the artifact is over the fleet runner's 1 GiB cap or off its type "
            "allowlist. The laptop has the disk; this is a runner limit, not a licence "
            "question.",
        ),
        (
            "rule",
            "a reading of the brief only Ivo settles, such as whether a link TARGET "
            "may date a year.",
        ),
        (
            "permission",
            "a letter to a custodian, or a terms page nobody has read against our use.",
        ),
        ("rerun", "no decision at all: a measurement that ran out of its window."),
        ("ingest", "nothing blocks it."),
    ):
        if any(r["ask"] == name for r in over):
            out.append(f"- **{name}**: {text}")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fleet", type=Path, default=Path.home() / "Documents/GitHub/ark-fleet")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    if not (args.fleet / "leads").is_dir():
        print(f"no leads/ under {args.fleet}")
        return 1
    page = render(leads(args.fleet, banked(STORE)))
    if args.write:
        OUT.write_text(page, encoding="utf-8")
        print(f"wrote {OUT.relative_to(REPO)}, {len(page.splitlines())} lines")
    else:
        print(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
