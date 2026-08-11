"""Write an approval request a human can decide in about two minutes.

**The design constraint.** The reader does not trust the agent's argument, and should
not: an agent arguing that its own find is master evidence is the least trustworthy
artifact in the repository. So a request is built almost entirely out of things the
reader can check without reading any prose:

- **the source URL**, so the claim has an address;
- **a seeded-random sample of real records**, each with a live link. Seeded and
  printed, so the sample is reproducible and, crucially, **not chosen by the agent**.
  Given the choice I would pick flattering examples;
- **the measured figures**, produced by a program against the live store;
- **the counterfactual**: what the source is worth under the other reading, so the
  stake is visible before the decision rather than after;
- **the nearest already-closed family** from the register, since the strongest reason
  to refuse is usually that something of this shape has already failed.

The one sentence of judgement it does ask for is the **dating claim**: what dates one
item. That is the fastest filter available and it decides what the source can ever
be, so it is stated explicitly and attributed to the agent rather than smuggled in.

**It refuses to re-open a rejected class**, because an agent that forgets a rejection
re-proposes it a week later.

    uv run python scripts/request_approval.py udrp_proceedings \\
        --journal data/raw/udrp/udrp_proceedings.jsonl.gz \\
        --dating "a case exists only because the domain was registered and disputed" \\
        --source-url https://www.icann.org/udrp/proceedings-list.htm
"""

import argparse
import gzip
import json
import random
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import duckdb  # noqa: E402

from ark.approvals import load  # noqa: E402
from ark.english_share import english_weights  # noqa: E402
from ark.evidence_types import MASTER_TYPES  # noqa: E402
from ark.sources import SOURCES  # noqa: E402

APPROVALS = ROOT / "docs/open-approvals.md"
SAMPLE_SIZE = 6


def read_only_store(patience_s: int = 1800) -> duckdb.DuckDBPyConnection:
    deadline = time.monotonic() + patience_s
    while True:
        try:
            return duckdb.connect(str(ROOT / "data/ark.duckdb"), read_only=True)
        except duckdb.Error as exc:
            if "Conflicting lock" not in str(exc):
                raise
            if time.monotonic() >= deadline:
                raise SystemExit(
                    "the store stayed locked; re-run when the ingest finishes"
                ) from None
            time.sleep(5)


def records_of(journal: Path) -> list[dict]:
    opener = gzip.open if journal.suffix == ".gz" else open
    out = []
    with opener(journal, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def nearest_closed(source_name: str) -> str:
    """The closed family a reader should compare this against, via the screener."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "screen_hypothesis", ROOT / "scripts" / "screen_hypothesis.py"
    )
    screen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(screen)
    register = screen.closed_leads()
    hits = screen.collisions(source_name.replace("_", " "), register)
    if not hits:
        return "nothing in the closed register resembles this by name."
    shared, entry = hits[0]
    return (
        f"closest closed family, {shared} shared terms, `docs/sources.md:{entry.line}`: "
        f"**{entry.name}**, closed on {entry.closed_on}."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", help="the spec key, e.g. udrp_proceedings")
    ap.add_argument("--journal", type=Path, required=True, help="the collected journal")
    ap.add_argument("--source-url", default="", help="where a reader can see the source itself")
    ap.add_argument("--dating", default="", help="one sentence: what dates ONE item")
    ap.add_argument(
        "--seed", type=int, default=20260811, help="sample seed, printed in the request"
    )
    args = ap.parse_args()

    spec = SOURCES.get(args.source)
    if spec is None:
        raise SystemExit(f"unknown spec key: {args.source}. Known: {', '.join(sorted(SOURCES))}")
    if spec.evidence_type not in MASTER_TYPES:
        raise SystemExit(
            f"{args.source} is {spec.evidence_type}, which is candidate-only and needs no "
            f"approval: a candidate claims nothing. Just ingest it."
        )

    existing = load(APPROVALS).get((spec.source_name, spec.evidence_type))
    if existing and existing.decision == "rejected":
        raise SystemExit(
            f"{spec.source_name} / {spec.evidence_type} was REJECTED at "
            f"{APPROVALS}:{existing.line}. A rejection binds; do not re-request it "
            f"without new external evidence."
        )
    if existing and existing.decision != "pending":
        raise SystemExit(
            f"{spec.source_name} / {spec.evidence_type} is already decided as "
            f"'{existing.decision}' at {APPROVALS}:{existing.line}."
        )

    # A request generated after the ingest is worse than useless: every pair is
    # already held, so its counterfactual reads zero at stake for a decision that had
    # plenty. That is misleading rather than merely unhelpful, so refuse it.
    conn = read_only_store()
    try:
        already = conn.execute(
            "SELECT count(*) FROM evidence e JOIN source s USING (source_id) WHERE s.name = ?",
            [spec.source_name],
        ).fetchone()[0]
    finally:
        conn.close()
    if already:
        raise SystemExit(
            f"refusing to write a request: the store already holds {already:,} evidence rows "
            f"for {spec.source_name}, so nothing would be at stake and the counterfactual "
            f"would read zero.\n"
            f"A request is written BEFORE the ingest. If this class needs re-deciding, edit "
            f"its existing entry in {APPROVALS.name} and record why."
        )

    records = records_of(args.journal)
    pairs = {(r["domain"], r["year"]) for r in records if r.get("domain") and r.get("year")}
    weights = english_weights()

    conn = read_only_store()
    try:
        names = sorted({d for d, _ in pairs})
        held_pairs: set[tuple[str, int]] = set()
        attested: set[str] = set()
        for start in range(0, len(names), 4000):
            batch = names[start : start + 4000]
            marks = ", ".join("?" * len(batch))
            held_pairs |= {
                (d, y)
                for d, y in conn.execute(
                    f"SELECT domain, assigned_year FROM domain_year WHERE domain IN ({marks})",
                    batch,
                ).fetchall()
            }
        attested = {d for d, _ in held_pairs}
    finally:
        conn.close()

    def ee(rows) -> Decimal:
        return sum((weights.get(d.rsplit(".", 1)[-1], Decimal(0)) for d, _ in rows), Decimal(0))

    netnew = pairs - held_pairs
    corroborated = {(d, y) for d, y in netnew if d in attested}
    mean = ee(netnew) / len(netnew) if netnew else Decimal(0)

    rng = random.Random(args.seed)
    sample = rng.sample(records, min(SAMPLE_SIZE, len(records)))

    shown_journal = args.journal.relative_to(ROOT) if args.journal.is_absolute() else args.journal
    by_year = Counter(y for _d, y in netnew)
    lines = [
        f"### {spec.source_name} / {spec.evidence_type}",
        "",
        f"- ingest spec: `{args.source}`",
        f"- source: {args.source_url or 'NOT GIVEN, which is itself a reason to refuse'}",
        f"- journal: `{shown_journal}`",
        f"- agent's dating claim: {args.dating or 'NOT STATED, which is a reason to refuse'}",
        f"- {nearest_closed(spec.source_name)}",
        "",
        "**Check these before reading anything else.** Seeded-random sample, "
        f"seed `{args.seed}`, so it is reproducible and was not chosen by the agent:",
        "",
        "| record | domain | year claimed | open this |",
        "|---|---|--:|---|",
    ]
    for record in sample:
        ident = record.get("proceeding") or record.get("item") or record.get("message_id") or "?"
        url = record.get("url", "")
        lines.append(f"| `{ident}` | `{record.get('domain')}` | {record.get('year')} | {url} |")

    lines += [
        "",
        "**Measured against the live store**, by program, not by the agent:",
        "",
        "| | |",
        "|---|--:|",
        f"| records in the journal | {len(records):,} |",
        f"| distinct (domain, year) | {len(pairs):,} |",
        f"| over distinct domains | {len({d for d, _ in pairs}):,} |",
        f"| already held by the store | {len(pairs) - len(netnew):,} |",
        f"| absent from the store | {len(netnew) / max(len(pairs), 1):.1%} |",
        "",
        "**The counterfactual, so the stake is visible before you decide:**",
        "",
        "| decision | net-new pairs | equivalent-English |",
        "|---|--:|--:|",
        f"| `master` (self-dating, no split) | **{len(netnew):,}** | **{ee(netnew):,.1f}** |",
        f"| `master` (taking the corroboration split) | {len(corroborated):,} "
        f"| {ee(corroborated):,.1f} |",
        "| `candidate-only` | 0 | 0.0, and the names still grow the pool |",
        "",
        f"Mean equivalent-English weight of the net-new part: {mean:.4f}. "
        f"By year: {dict(sorted(by_year.items()))}.",
        "",
        "**Reasons a reader should refuse**, listed by the agent against its own request:",
        "",
        "- the sample links do not show that domain with that date;",
        "- the year is inferred from something other than the record itself;",
        "- the hostname comes out of prose rather than a structured field, in which "
        "case `candidate-only` or a split-taking spec is right, not `master`;",
        "- the closed family named above is the same population under another name.",
        "",
        "Decision: pending",
        "",
    ]

    block = "\n".join(lines)
    text = APPROVALS.read_text(encoding="utf-8")
    marker = "## Pending requests"
    if marker in text:
        head, tail = text.split(marker, 1)
        # drop the "nothing pending" placeholder once there is something
        placeholder = (
            "\nNothing pending. New requests are appended here by\n"
            "`uv run python scripts/request_approval.py <source> --journal <journal>`, "
            "which refuses to re-open a\nclass already marked `rejected`.\n"
        )
        tail = tail.replace(placeholder, "\n")
        APPROVALS.write_text(head + marker + tail.rstrip("\n") + "\n\n" + block, encoding="utf-8")
    else:
        APPROVALS.write_text(text.rstrip("\n") + "\n\n" + marker + "\n\n" + block, encoding="utf-8")

    print(f"appended a pending request to {APPROVALS.relative_to(ROOT)}")
    print(f"  {spec.source_name} / {spec.evidence_type}")
    print(f"  {len(netnew):,} net-new pairs at stake, {ee(netnew):,.1f} equivalent-English")
    print("  ingest refuses until its Decision line says master, candidate-only or rejected")


if __name__ == "__main__":
    main()
