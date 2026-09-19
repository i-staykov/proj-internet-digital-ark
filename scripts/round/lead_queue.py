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
DECISIONS = REPO / "docs/lore/key-decisions.md"
# Written whenever the store can be read, so a locked store costs freshness and not the
# check itself. The hourly sync holds the write lock about half of every hour, and a
# silently skipped check puts banked sources back in front of Ivo.
CACHE = REPO / "data/banked_slugs.txt"
FLOOR = 5000.0
_WORTH = re.compile(r"^Worth:\s*[^\d-]*(-?[\d,]+(?:\.\d+)?)\s*EE", re.M)
# Whether a class can reach either shipped file at all. Section XIII admits web evidence
# to the annual masters, and the candidate claim is registrable domains plus the ISC
# hostnames, so a hostname-grain mail, Usenet or DNS record reaches neither. Matched on
# the scout's own free-text class, so it is a signal and not a gate.
_STRANDED = re.compile(
    r"mail|usenet|relay|received|nntp|posting|header|dns|whois|rdap|ngram|"
    r"book_mention|author_mail|buildhost",
    re.I,
)
_SHIPS = re.compile(
    r"cdx|capture|link.?graph|web.?archive|timemap|geoindex|crawl_timestamp|wayback|"
    r"artifact_listing|dated_directory|registry|cctld",
    re.I,
)

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
        if CACHE.is_file():
            return set(CACHE.read_text(encoding="utf-8").split())
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
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text("\n".join(sorted(out)) + "\n", encoding="utf-8")
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
    parts = {p for p in slug.split("-") if len(p) > 3}
    for name in held:
        # Both directions, because either side may be the longer word: the ingest wrote
        # `poland_pl_extract_hostgrain` where the scout wrote `...-extraction-...`, and a
        # one-way `part in name` test scores that 1 and calls a banked source new.
        others = {q for q in name.split("-") if len(q) > 3}
        overlap = sum(any(p in q or q in p for q in others) for p in parts)
        if overlap >= 2:
            return "similar"
    return ""


def _track(evidence_class: str) -> str:
    """ "stranded" if nothing this class writes can reach a shipped file today."""
    if _STRANDED.search(evidence_class):
        return "stranded"
    return "ships" if _SHIPS.search(evidence_class) else "?"


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
                "track": _track(str(doc.get("evidence_class") or "")),
            }
        )
    return sorted(live, key=lambda r: (-r["low"], -r["high"]))


def decisions(path: Path) -> list[dict]:
    """The repository's own open asks, read from the OPEN block of `key-decisions.md`.

    They belong in the same list as the fleet's leads because they compete for the same
    thing, which is one person's attention, and some of them are worth more than any lead.
    Each carries its own `Worth: <n> EE` line; one without a figure is not ranked here.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    start = text.find("## OPEN")
    if start < 0:
        return []
    body = text[start : text.find("## CLOSED", start) if "## CLOSED" in text else len(text)]
    out = []
    for block in re.split(r"\n(?=### )", body)[1:]:
        title = block.split("\n", 1)[0].removeprefix("### ").strip()
        found = _WORTH.search(block)
        if not found:
            continue
        worth = abs(float(found.group(1).replace(",", "")))
        out.append(
            {
                "slug": title,
                "status": "open",
                "low": worth,
                "high": worth,
                "blocked": "rule",
                "ask": "rule",
                "class": "decision in key-decisions.md",
                "held": "",
                "track": "ships",
            }
        )
    return out


def render(rows: list[dict], checked: bool = True) -> str:
    over = [r for r in rows if max(r["low"], r["high"]) >= FLOOR]
    under = len(rows) - len(over)
    out = [
        "# Queue",
        "",
        "Generated by `scripts/round/lead_queue.py` from the fleet's `leads/*.json`.",
        "Never hand-edit: an edit here is lost on the next sync, and the lead file is",
        "the thing the dealer reads.",
        "",
        f"**{len(over)} open item(s) at or above the {FLOOR:,.0f} EE floor**, ranked on the LOW",
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
    stranded = [r for r in over if r["track"] == "stranded"]
    if stranded:
        out += [
            f"**{len(stranded)} of these {len(over)} items, "
            f"{sum(r['low'] for r in stranded):,.0f} EE at the low estimate, are in classes "
            "that ship NOWHERE today.** A hostname-year that "
            "Section XIII keeps out of the annual masters has no candidate file to fall into: the "
            "candidate claim is registrable domains plus the ISC hostnames and nothing else. Until "
            "that is decided, working any of them adds rows to the store and nothing to the claim.",
            "",
        ]
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
        "| EE low | EE high | ships? | asks for | what |",
        "|---:|---:|---|---|---|",
    ]
    for r in over:
        out.append(
            f"| {r['low']:,.0f} | {r['high']:,.0f} | {r['track']} | {r['ask']} "
            f"| `{r['slug']}`{' (store has a near name)' if r['held'] else ''} |"
        )
    if not checked:
        out += [
            "",
            "**The store could not be read this run**, so nothing was dropped as banked and "
            "the `store` column is not to be trusted here.",
        ]
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
    page = render(
        sorted(
            leads(args.fleet, banked(STORE)) + decisions(DECISIONS),
            key=lambda r: (-r["low"], -r["high"]),
        )
    )
    if args.write:
        OUT.write_text(page, encoding="utf-8")
        print(f"wrote {OUT.relative_to(REPO)}, {len(page.splitlines())} lines")
    else:
        print(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
