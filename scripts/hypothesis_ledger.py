"""The hypothesis ledger: what the harness has proposed, priced, adopted or killed.

**Why prose was not enough.** `docs/sources.md` is the authoritative narrative and
holds ~60 verdicts, which is what `just screen` parses to stop a dead lead. Prose
cannot carry *status*, so it cannot answer the question an unattended run asks
every time it wakes up: what did I propose on Tuesday that I never finished
pricing? A loop with no working memory re-proposes its own ideas.

So this is a small tab-separated file, one row per hypothesis, tracked in git and
readable without a tool. It is **not** a second copy of the register: a hypothesis
leaves here for `sources.md` when it closes, and `close` prints the prose row to
paste so the two cannot drift.

**Screening is not optional.** `add` runs the collision check itself and refuses a
hypothesis with no dating claim, because both gates are cheap and the expensive
mistake is starting work on something already closed.

    uv run python scripts/hypothesis_ledger.py add --dating typed "CPAN author metadata"
    uv run python scripts/hypothesis_ledger.py list
    uv run python scripts/hypothesis_ledger.py update H003 --status rejected \\
        --pairs 86 --ee 37.3 --mean 0.4338 --cost "2 requests" --verdict "94.7% already held"
    uv run python scripts/hypothesis_ledger.py close H003
"""

import argparse
import datetime as dt
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "docs/hypotheses.tsv"
COLUMNS = (
    "id",
    "opened",
    "updated",
    "status",
    "dating",
    "pairs",
    "domains",
    "ee",
    "mean",
    "cost",
    "title",
    "verdict",
)
STATUSES = ("screened", "fetching", "priced", "adopted", "rejected", "blocked")

_SPEC = importlib.util.spec_from_file_location(
    "screen_hypothesis", ROOT / "scripts" / "screen_hypothesis.py"
)
screen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(screen)


def today() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")


def read() -> list[dict]:
    if not LEDGER.exists():
        return []
    lines = LEDGER.read_text(encoding="utf-8").splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"), strict=False)) for line in lines[1:] if line.strip()]


def write(rows: list[dict]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    out = ["\t".join(COLUMNS)]
    for row in rows:
        out.append("\t".join(str(row.get(col, "")).replace("\t", " ") for col in COLUMNS))
    LEDGER.write_text("\n".join(out) + "\n", encoding="utf-8")


def next_id(rows: list[dict]) -> str:
    used = [
        int(r["id"][1:]) for r in rows if r.get("id", "").startswith("H") and r["id"][1:].isdigit()
    ]
    return f"H{max(used, default=0) + 1:03d}"


def cmd_add(args: argparse.Namespace) -> None:
    title = " ".join(args.title).strip()
    if not title:
        raise SystemExit("say what the source is, in words")
    register = screen.closed_leads()
    hits = screen.collisions(title, register)
    rows = read()
    if any(r.get("title") == title for r in rows):
        raise SystemExit(f"already in the ledger: {title}")

    print(f"screened against {len(register)} closed leads")
    verdict_bits = []
    for shared, entry in hits[:3]:
        kind = entry.closed_on
        print(f"  COLLIDES ({shared} terms, closed on {kind.upper()}) sources.md:{entry.line}")
        print(f"    {entry.name}")
        verdict_bits.append(f"collides with {entry.name} [{kind}]")
    if not hits:
        print("  no collision")
    reprobe = [e for _s, e in hits if e.closed_on == "availability"]
    if reprobe:
        print("  RE-PROBEABLE: those were closed on availability, not on measurement.")

    row = {
        "id": next_id(rows),
        "opened": today(),
        "updated": today(),
        "status": "screened",
        "dating": args.dating,
        "pairs": "",
        "domains": "",
        "ee": "",
        "mean": "",
        "cost": "",
        "title": title,
        "verdict": "; ".join(verdict_bits) if verdict_bits else "no collision at screening",
    }
    rows.append(row)
    write(rows)
    print(f"\nadded {row['id']}  dating={args.dating}  status=screened")
    if args.dating == "undated":
        print("  seed-only by construction: it can grow the pool and can never date a year")
    elif args.dating == "self":
        print("  self-dating: no corroboration split, so do NOT widen its extraction")
    else:
        print("  typed in a dated artifact: takes the corroboration split, so recall is safe")


def cmd_list(args: argparse.Namespace) -> None:
    rows = read()
    if args.status:
        rows = [r for r in rows if r.get("status") in args.status]
    if not rows:
        print("nothing in the ledger" + (f" with status {args.status}" if args.status else ""))
        return
    print(f"{'id':5} {'status':9} {'dating':8} {'pairs':>7} {'EE':>10}  title")
    print("-" * 100)
    for row in rows:
        print(
            f"{row.get('id', ''):5} {row.get('status', ''):9} {row.get('dating', ''):8} "
            f"{row.get('pairs', ''):>7} {row.get('ee', ''):>10}  {row.get('title', '')[:52]}"
        )
    open_work = [r for r in rows if r.get("status") in ("screened", "fetching", "priced")]
    if open_work:
        print(f"\n{len(open_work)} not finished: " + ", ".join(r["id"] for r in open_work))


def cmd_update(args: argparse.Namespace) -> None:
    rows = read()
    for row in rows:
        if row.get("id") != args.id:
            continue
        for field in ("status", "pairs", "domains", "ee", "mean", "cost", "verdict"):
            value = getattr(args, field, None)
            if value is not None:
                row[field] = value
        row["updated"] = today()
        write(rows)
        shown = "  ".join(f"{c}={row.get(c, '')}" for c in ("status", "pairs", "ee"))
        print(f"{args.id}: {shown}")
        return
    raise SystemExit(f"no such hypothesis: {args.id}")


def cmd_close(args: argparse.Namespace) -> None:
    """Print the prose row for `sources.md`, so the register stays authoritative."""
    for row in read():
        if row.get("id") != args.id:
            continue
        if row.get("status") not in ("rejected", "adopted"):
            print(f"warning: {args.id} is {row.get('status')}, not a closed verdict\n")
        print("Paste this into the 'Evaluated and rejected' table in docs/sources.md,")
        print("then the screener will catch this lead by itself:\n")
        bits = []
        if row.get("pairs"):
            bits.append(f"{row['pairs']} net-new pairs")
        if row.get("ee"):
            bits.append(f"{row['ee']} equivalent-English after the split")
        if row.get("mean"):
            bits.append(f"mean weight {row['mean']}")
        if row.get("cost"):
            bits.append(f"cost {row['cost']}")
        measured = ", ".join(bits) if bits else "not priced"
        print(
            f"| {row['title']} ({row['updated']}) | **{row.get('status', '').title()}: "
            f"{measured}.** {row.get('verdict', '')} |"
        )
        return
    raise SystemExit(f"no such hypothesis: {args.id}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="screen a hypothesis and record it")
    add.add_argument("title", nargs="+")
    add.add_argument("--dating", required=True, choices=sorted(screen.DATING))
    add.set_defaults(func=cmd_add)

    lst = sub.add_parser("list", help="what is in the ledger")
    lst.add_argument("--status", action="append", choices=STATUSES)
    lst.set_defaults(func=cmd_list)

    upd = sub.add_parser("update", help="record a measurement or a verdict")
    upd.add_argument("id")
    upd.add_argument("--status", choices=STATUSES)
    for field in ("pairs", "domains", "ee", "mean", "cost", "verdict"):
        upd.add_argument(f"--{field}")
    upd.set_defaults(func=cmd_update)

    close = sub.add_parser("close", help="print the docs/sources.md row for a decided hypothesis")
    close.add_argument("id")
    close.set_defaults(func=cmd_close)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
