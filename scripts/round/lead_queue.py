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
REGISTERS = (REPO / "docs/registers/sources.md", REPO / "docs/registers/sources-closed.md")
FLOOR = 5000.0
_EE = re.compile(r"([\d,]+(?:\.\d+)?)\s*EE")
# `store 3,681.7 EE` beside `fleet 35,429.9 EE` means the fleet counted rows the store
# already holds, so the store figure is the one that is net-new and it wins.
_STORE_EE = re.compile(r"store\s+([\d,]+(?:\.\d+)?)\s*EE", re.I)
_WORTH = re.compile(r"^Worth:\s*[^\d-]*(-?[\d,]+(?:\.\d+)?)\s*EE", re.M)
# The ISC survey is the one hostname collection the candidate claim admits by name, so it
# is the single exception to the grain rule in `_track`.
_ISC = re.compile(r"\bisc\b|isc_survey", re.I)

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


def measured(paths: tuple[Path, ...] = REGISTERS) -> dict[str, tuple[float | None, str]]:
    """What each slug was WORTH when somebody read the artifact, from the register tables.

    **A lead carries a scout's estimate and the register carries a measurement, and only
    the second is a number.** On 2026-09-19 four leads stood in this queue between 16,958
    and 200,662 EE that the register already recorded as 93.9 EE, 1,389.1 EE, 0 EE and
    banked-on-2026-09-10: about 380,000 EE of headroom that does not exist. An estimate is
    what a leg was willing to guess before reading the artifact, so once the artifact has
    been read the guess has no standing at all.

    Columns are found by their header rather than counted, because the two registers do
    not agree on width and a fixed index reads the wrong cell in one of them. Every row of
    `sources-closed.md` is closed by the page it sits on, whatever word its reason opens
    with, the way `find.py` reads it.
    """
    out: dict[str, tuple[float | None, str]] = {}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        closed_page = path.name == REGISTERS[1].name
        cols: dict[str, int] = {}
        for line in text.splitlines():
            if not line.startswith("|"):
                continue
            # `\|` is a pipe inside a cell, not a boundary.
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
            head = [c.lower() for c in cells]
            # `sources.md` carries `verdict` and `net-new EE`; `sources-closed.md` carries
            # `reason` and `measured`. Read both.
            if "source" in head and ("verdict" in head or "reason" in head):
                cols = {name: i for i, name in enumerate(head)}
                word = "verdict" if "verdict" in head else "reason"
                cols["verdict"] = head.index(word)
                cols["ee"] = next(
                    (i for i, n in enumerate(head) if "net-new ee" in n or n == "measured"), -1
                )
                continue
            if not cols or cols["ee"] < 0 or len(cells) <= max(cols["ee"], cols["verdict"]):
                continue
            slug = cells[cols["source"]].strip("`*").split(" / ")[0].strip()
            if not slug or slug.startswith("-"):
                continue
            cell = cells[cols["ee"]]
            hit = _STORE_EE.search(cell) or _EE.search(cell)
            worth = float(hit.group(1).replace(",", "")) if hit else None
            verdict = "CLOSED" if closed_page else cells[cols["verdict"]].upper()
            prior = out.get(slug)
            # A CLOSED row is the last word on a slug however many rows precede it: it is
            # written by the re-price that refused the lead.
            if prior is None or "CLOSED" in verdict or (prior[0] is None and worth is not None):
                out[slug] = (worth, verdict)
    return out


def verdict_of(slug: str, reg: dict[str, tuple[float | None, str]]) -> tuple[float | None, str]:
    """The register's word on this lead: its measured EE and whether it is closed.

    Matched on the slug itself or on the slug with a suffix, because a re-price is filed as
    `<slug>-reprice` and is the same lead measured twice. Never on a prefix of the slug,
    which would let a shorter unrelated name speak for this one.
    """
    worth, state = None, ""
    for name, (value, verdict) in reg.items():
        if name != slug and not name.startswith(slug + "-"):
            continue
        if "CLOSED" in verdict:
            return value, "closed"
        if value is not None and (worth is None or value < worth):
            worth, state = value, "measured"
    return worth, state


def _track(evidence_class: str, grain: str = "") -> str:
    """Whether anything this lead writes can reach a shipped file today.

    **The GRAIN decides, not the class name.** `export.py` builds the candidate pool from
    registrable domains plus the ISC survey hostnames and nothing else, and Section XIII
    admits a host to the annual masters only through `WEB_METHODS`. So a hostname-grain
    lead whose class is not a web method reaches neither file however well it is dated.
    Read off the code rather than guessed: the prose regex this replaces called
    `ripe-hostcount-hidden-output-files` a shipping lead at the head of the queue, worth
    100,000 EE, because its class string begins `artifact_listing`. That is an AXFR
    transcript at hostname grain, which is neither a web method nor the ISC survey, and the
    brief lists DNS among the candidates.

    A class the scout wrote is free text and the ingest may yet write a different method,
    so an unrecognised grain is "?" and never "ships".
    """
    try:
        from ark.evidence_types import WEB_METHODS
    except ImportError:
        return "?"
    head = (
        evidence_class.split("(")[0].strip().split()[0].strip(",:").lower()
        if evidence_class
        else ""
    )
    if head in WEB_METHODS:
        return "ships"
    if grain == "registrable":
        return "ships"
    if grain == "hostname":
        return "ships" if _ISC.search(evidence_class) else "stranded"
    return "?"


def leads(fleet: Path, held: set[str], reg: dict | None = None) -> list[dict]:
    reg = measured() if reg is None else reg
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
        worth, said = verdict_of(slug, reg)
        if said == "closed":
            continue
        verdict_text = next(
            (v for n, (w, v) in reg.items() if n == slug or n.startswith(slug + "-")), ""
        )
        if said == "measured":
            # One figure, not a range: a measurement has no spread and showing the old
            # estimate beside it invites the estimate to be believed.
            low = high = worth
        live.append(
            {
                "slug": slug,
                "status": doc.get("status"),
                "low": float(low),
                "high": float(high),
                "measured": said == "measured",
                "blocked": blocked,
                "ask": ask_of(blocked) if blocked else "ingest",
                "class": str(doc.get("evidence_class") or "").split("(")[0].strip(),
                "held": state,
                "track": _track(str(doc.get("evidence_class") or ""), str(doc.get("grain") or "")),
                "grain": str(doc.get("grain") or ""),
                "url": str((doc.get("artifact") or {}).get("url") or ""),
                "terms": str((doc.get("artifact") or {}).get("terms_url") or ""),
                "dates": " ".join(str(doc.get("what_dates_one_item") or "").split()),
                "said": verdict_text.lower(),
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
                "measured": True,
                "track": "ships",
            }
        )
    return out


def _cell(text: str, width: int) -> str:
    """One table cell: pipes escaped, whitespace collapsed, cut at `width`."""
    flat = " ".join(text.split()).replace("|", "\\|")
    return flat if len(flat) <= width else flat[: width - 1].rstrip() + "…"


def render(rows: list[dict], checked: bool = True) -> str:
    """The page: Ivo's approval list, grouped by what his yes unlocks.

    **Only a measured figure is a row.** A scout's estimate has been wrong by five orders of
    magnitude, so an unmeasured lead is named in one line at the foot and priced before it is
    asked about. Nothing on the page is marked as the laptop's own work to do: a lead is
    measured and ingested, measured and queued under the ruling it needs, or closed.
    """
    decisions = [r for r in rows if r["class"] == "decision in key-decisions.md"]
    leads = [r for r in rows if r["class"] != "decision in key-decisions.md"]
    measured = [r for r in leads if r.get("measured")]
    unmeasured = [r for r in leads if not r.get("measured")]
    outlet = next((d for d in decisions if "outlet" in d["slug"].lower()), None)
    stranded = [r for r in measured if r["track"] == "stranded"]
    permission = [r for r in measured if r["track"] != "stranded" and r["ask"] == "permission"]
    ingest = [r for r in measured if r["track"] != "stranded" and r["ask"] != "permission"]
    out = [
        "# Queue",
        "",
        "Generated by `scripts/round/lead_queue.py` from the fleet's `leads/*.json`, the OPEN",
        "block of `key-decisions.md` and the register rows that priced each lead. Never hand-edit.",
        "Every figure here was measured against the store after reading the artifact; a lead a",
        "scout only estimated is named at the foot and not asked about. Letters are off the table.",
        "One yes unlocks everything under its heading.",
        "",
        "## What your yes unlocks, biggest first",
        "",
    ]
    groups: list[tuple[str, float, list[dict]]] = []
    if outlet or stranded:
        title = outlet["slug"] if outlet else "Give the XIII-excluded hostnames a candidate outlet"
        worth = (outlet["low"] if outlet else 0.0) + sum(r["low"] for r in stranded)
        groups.append((title, worth, stranded))
    for d in decisions:
        if d is not outlet:
            groups.append((d["slug"], d["low"], []))
    if permission:
        asked = sum(r["low"] for r in permission)
        groups.append(("Read these terms, or write for permission", asked, permission))
    for title, worth, members in sorted(groups, key=lambda g: -g[1]):
        out.append(f"### {title}")
        out.append("")
        if members and outlet and title == outlet["slug"]:
            out.append(
                f"**{worth:,.0f} EE**: {outlet['low']:,.0f} EE of hostname-years already in the "
                f"store and {sum(r['low'] for r in members):,.0f} EE measured in the "
                f"{len(members)} sources below, each read on this laptop. All hostname grain, "
                "all classes XIII keeps out of the annual files, none in the candidate claim "
                "until you rule."
            )
        else:
            out.append(f"**{worth:,.0f} EE**")
        if members:
            out += [
                "",
                "| EE | source | measured on | what dates one item | terms |",
                "|---:|---|---|---|---|",
            ]
            for r in sorted(members, key=lambda r: -r["low"]):
                name = f"[`{r['slug']}`]({r['url']})" if r.get("url") else f"`{r['slug']}`"
                out.append(
                    f"| {r['low']:,.1f} | {name} | "
                    f"{_cell(r.get('said') or 'the register row', 90)} | "
                    f"{_cell(r.get('dates') or 'not quoted', 140)} | "
                    f"{_cell(r.get('terms') or 'none recorded', 70)} |"
                )
        out.append("")
    if ingest:
        out += ["## Measured and shippable, ingested without asking", ""]
        for r in sorted(ingest, key=lambda r: -r["low"]):
            out.append(f"- {r['low']:,.1f} EE `{r['slug']}`: {_cell(r.get('said') or '', 120)}")
        out.append("")
    out += ["## Not yet measured", ""]
    if unmeasured:
        out.append(
            f"{len(unmeasured)} lead(s) carry only a scout's estimate and are not asked about "
            "until read: "
            + ", ".join(f"`{r['slug']}`" for r in sorted(unmeasured, key=lambda r: r["slug"]))
            + "."
        )
    else:
        out.append("None. Every live lead has been read and priced.")
    if not checked:
        out += ["", "**The store could not be read this run**, so nothing was dropped as banked."]
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
