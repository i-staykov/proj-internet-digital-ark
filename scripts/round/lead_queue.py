"""Generate `docs/registers/queue.md`, the new classes and the send the owner decides.

**Why a generated page and not a register.** `approved-sources-list.md` binds `ark ingest`
and `sources-closed.md` stops a re-test; neither is a queue. The queue is what is still
live, ranked by what it is worth, and it goes stale the moment a lead moves. So it is
derived from the fleet's own `leads/*.json` every sync and never hand-edited.

**Two things are his to decide, and the page lists nothing else: a new evidence class and
the send** (CLAUDE.md, Autonomy). A lead inside the standing size, terms, robots and class
bounds is read and banked by the loop without asking, and a download, a terms page or a
re-run is the loop's to settle, not his. So a lead is on the page only when it asks for a
class nothing admits yet, and the send is where the round stands against the 5% gate, read
from `data/brief.json`.

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

    uv run python scripts/round/lead_queue.py [--fleet DIR] [--write]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/registers/queue.md"
# Written by the bank from the store it measured, so the send is read here without opening it.
BRIEF = REPO / "data/brief.json"
REGISTERS = (REPO / "docs/registers/sources.md", REPO / "docs/registers/sources-closed.md")
FLOOR = 5000.0
_EE = re.compile(r"([\d,]+(?:\.\d+)?)\s*EE")
# `store 3,681.7 EE` beside `fleet 35,429.9 EE` means the fleet counted rows the store
# already holds, so the store figure is the one that is net-new and it wins.
_STORE_EE = re.compile(r"store\s+([\d,]+(?:\.\d+)?)\s*EE", re.I)
# The ISC survey is the one hostname collection the candidate claim admits by name, so it
# is the single exception to the grain rule in `_track`.
_ISC = re.compile(r"\bisc\b|isc_survey", re.I)

# What Ivo is still asked for, and nothing else: a new evidence class and the send. A lead's
# `blocked_on` is free text written by a scout, so it is matched rather than parsed. A rule
# a scout asks for is a ruling on what counts as evidence, so it is a class; a download, a
# terms page or a re-run matches neither, because the standing bounds decide those.
ASKS = (
    (
        "class",
        re.compile(r"new (evidence )?class|evidence class|eligib|admissib|\brul(e|ing)\b", re.I),
    ),
    ("send", re.compile(r"\bsend\b|\bsubmi(t|ssion)\b|5% gate", re.I)),
)

_SPEC = importlib.util.spec_from_file_location(
    "fleet_ledger", REPO / "scripts/harness/fleet_ledger.py"
)
fleet_ledger = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fleet_ledger)


def ask_of(blocked: str) -> str:
    """The ask a blocker puts to Ivo, or "" for one that is not his."""
    for name, pattern in ASKS:
        if pattern.search(blocked):
            return name
    return ""


def _json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def banked(fleet: Path) -> set[str]:
    """The leads the bank has banked: every slug the fleet ledger holds an outcome line for
    whose `banked` is true, and every lead whose own status is `banked`.

    **Why a banked lead is dropped at all.** A lead reaches `verified` in the fleet, the
    laptop ingests it, and a queue read off the lead file alone keeps it. Four leads worth
    about 94,000 EE sat in this queue on 2026-09-19 having been ingested days earlier, which
    is a queue that spends Ivo's attention on finished work.

    **Never the store, and no cached list of it.** The store's names are the ingest's, which
    are a lead's slug only by luck, while an outcome line carries the lead's own slug and is
    written by the bank once its register commit lands. So the hourly tick and the bank read
    the same set and neither opens the store. Only a JSON `true` counts.
    """
    out = {
        str(line["slug"])
        for line in fleet_ledger.lines(fleet, "outcome")
        if line.get("banked") is True and line.get("slug")
    }
    for path in sorted((fleet / "leads").glob("*.json")):
        doc = _json(path)
        if doc.get("status") == "banked":
            out.add(str(doc.get("slug") or path.stem))
    return out


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
        if slug in held:
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
                "ask": ask_of(blocked),
                "class": str(doc.get("evidence_class") or "").split("(")[0].strip(),
                "track": _track(str(doc.get("evidence_class") or ""), str(doc.get("grain") or "")),
                "grain": str(doc.get("grain") or ""),
                "url": str((doc.get("artifact") or {}).get("url") or ""),
                "terms": str((doc.get("artifact") or {}).get("terms_url") or ""),
                "dates": " ".join(str(doc.get("what_dates_one_item") or "").split()),
                "said": verdict_text.lower(),
            }
        )
    return sorted(live, key=lambda r: (-r["low"], -r["high"]))


def _cell(text: str, width: int) -> str:
    """One table cell: pipes escaped, whitespace collapsed, cut at `width`."""
    flat = " ".join(text.split()).replace("|", "\\|")
    return flat if len(flat) <= width else flat[: width - 1].rstrip() + "…"


def send_line(path: Path = BRIEF) -> str:
    """The send, the one ask no lead carries: where the round stands against the 5% gate, read
    from the brief the bank writes, the way `bank_hygiene.py gate` reads it."""
    brief = _json(path)
    try:
        percent = float(brief.get("round_percent", brief.get("percent")))
        target = float(brief.get("gate_pct", 5.0))
    except (TypeError, ValueError):
        return "Not known here: `data/brief.json` is missing or carries no round figure."
    label = str(brief.get("round", "?"))
    name = label if label.lower().startswith("round") else f"Round {label}"
    marker = str(brief.get("baseline", "?"))
    if percent >= target:
        return (
            f"**{name} crossed the {target:g}% gate** at {percent:.4f}% against `{marker}`, and "
            "the send is yours: merge any open approval PR, then run `just ship` where the "
            "store is."
        )
    gap = brief.get("round_distance_to_gate_ee", brief.get("distance_to_gate_ee"))
    number = isinstance(gap, int | float) and not isinstance(gap, bool)
    short = f", {gap:,.0f} EE short" if number else ""
    return (
        f"Nothing to send: {name} stands at {percent:.4f}% against `{marker}`, under the "
        f"{target:g}% gate{short}."
    )


def render(rows: list[dict], send: str = "", missing: str = "") -> str:
    """The page: the send, then the new classes Ivo is asked for, grouped by what his yes
    unlocks.

    **Only a measured figure is a row.** A scout's estimate has been wrong by five orders of
    magnitude, so a lead asking for a class on an estimate alone is named in one line and
    priced before it is asked about. A lead whose class the loop can bank, or whose blocker
    is the loop's to settle, is not on the page at all.
    """
    # A stranded lead's class reaches neither file, so what it waits on is a class outlet.
    asked = [r for r in rows if r["ask"] == "class" or r["track"] == "stranded"]
    measured = [r for r in asked if r.get("measured")]
    unmeasured = [r for r in asked if not r.get("measured")]
    stranded = [r for r in measured if r["track"] == "stranded"]
    classes: dict[str, list[dict]] = {}
    for r in measured:
        if r["track"] != "stranded":
            classes.setdefault(r["class"] or "unnamed", []).append(r)
    out = [
        "# Queue",
        "",
        "Generated by `scripts/round/lead_queue.py` from the fleet's `leads/*.json` and ledger,",
        "the register rows that priced each lead and `data/brief.json`. Never hand-edit. You",
        "approve a new evidence class and every send, and nothing else is asked here: a lead",
        "inside the standing bounds is read without asking. Every figure was measured against",
        "the store after reading the artifact. Letters are off the table. One yes unlocks",
        "everything under its heading.",
        "",
        "## The send",
        "",
        send or send_line(),
        "",
        "## New evidence classes, biggest first",
        "",
    ]
    if missing:
        out += [missing, ""]
    groups: list[tuple[str, float, list[dict]]] = []
    if stranded:
        title = "Give the XIII-excluded hostnames a candidate outlet"
        groups.append((title, sum(r["low"] for r in stranded), stranded))
    for name, members in classes.items():
        groups.append((f"Admit `{_cell(name, 80)}`", sum(r["low"] for r in members), members))
    for title, worth, members in sorted(groups, key=lambda g: -g[1]):
        out += [
            f"### {title}",
            "",
            f"**{worth:,.0f} EE**",
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
    if not groups and not missing:
        out += ["None. No measured lead asks for a new evidence class.", ""]
    if unmeasured:
        out.append(
            f"{len(unmeasured)} lead(s) ask for a class on a scout's estimate alone and are "
            "priced before they are asked about: "
            + ", ".join(f"`{r['slug']}`" for r in sorted(unmeasured, key=lambda r: r["slug"]))
            + "."
        )
    return "\n".join(out).rstrip("\n") + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fleet", type=Path, default=Path.home() / "Documents/GitHub/ark-fleet")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    fleet = args.fleet.expanduser()
    rows: list[dict] = []
    missing = ""
    if (fleet / "leads").is_dir():
        rows = leads(fleet, banked(fleet))
    else:
        print(f"no leads/ under {fleet}: the page says the fleet queue is not there")
        missing = (
            "The fleet queue is not there: the fleet clone has no `leads/`, so no lead is "
            "listed this run."
        )
    page = render(rows, send_line(BRIEF), missing)
    if args.write:
        OUT.write_text(page, encoding="utf-8")
        print(f"wrote {OUT.relative_to(REPO)}, {len(page.splitlines())} lines")
    else:
        print(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
