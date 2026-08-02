"""Substitute the report's and the email's placeholders from the live store.

The report must not contain a figure that disagrees with the shipped files, and
the way that happens is a human retyping a number after the data moved. So the
report is written with `[PLACEHOLDER]` tokens and this fills them from the same
queries `report_figures.py` uses.

Two properties worth having. It is idempotent in the sense that re-running it on
a filled report is a no-op (there are no tokens left to match), so the source of
truth stays in git as a template. And it **fails loudly on a token it cannot
fill**, rather than shipping a report with `[ENGLISH]` in it, which is the one
outcome worse than a stale number.

    uv run python scripts/fill_report.py --check     # report which tokens remain
    uv run python scripts/fill_report.py             # write filled copies

`docs/*.template.md` are the sources; `docs/*.md` are generated. Edit the
templates, never the filled copies, or the next refresh discards the edit.
"""

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from report_figures import figures, markdown  # noqa: E402

DB = Path("data/ark.duckdb")
# Template in, filled document out. Filling in place would consume the template,
# and the numbers have to be refilled every time the archive is re-cut, so the
# template is the thing that lives in git and the filled copy is a build product.
DOCUMENTS = (
    (Path("docs/report_260802.template.md"), Path("docs/report_260802.md")),
    (Path("docs/email_draft_260802.template.md"), Path("docs/email_draft_260802.md")),
)

SUPERVISOR_LOG = Path("data/logs/lang_supervisor.log")
JOURNAL_DIR = Path("data/raw/lang")
# Used only if the supervisor log cannot be read. It is the last figure the log
# did produce, so a missing log gives a stale number rather than a wrong shape.
FALLBACK_RATE = 356
# When the engine stops and the numbers are refreshed for the last time:
# Monday 3 August 2026, 12:00 UTC. The same epoch the watchdog was given.
ENGINE_DEADLINE_EPOCH = 1785758400


def measured_throughput() -> tuple[int, int, int, float]:
    """Pairs per hour, over every batch whose journal is still current.

    Quoting one batch as "the measured rate" is an estimate wearing a
    measurement's clothes, and this report quoted two different rates for one
    engine before the figures were derived. So the rate is computed here from
    the supervisor's own log, over exactly the batches whose journals are in
    `data/raw/lang/`. A journal that was superseded by an engine version bump
    moves to `superseded/` and drops out of the average by itself.

    Returns (pairs_per_hour, batches, pairs, minutes).
    """
    if not SUPERVISOR_LOG.exists():
        return FALLBACK_RATE, 0, 0, 0.0
    current = {p.name for p in JOURNAL_DIR.glob("*.jsonl.gz")}
    started: datetime | None = None
    batches = pairs = 0
    minutes = 0.0
    for line in SUPERVISOR_LOG.read_text(errors="replace").splitlines():
        start = re.match(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) batch \d+ start", line)
        if start:
            started = datetime.strptime(start.group(1), "%Y-%m-%d %H:%M:%S")
            continue
        done = re.match(r"^(\d\d:\d\d:\d\d) \|.*'classified': (\d+).*-> (\S+)", line)
        if not done or started is None:
            continue
        if Path(done.group(3)).name not in current:
            continue
        hh, mm, ss = (int(v) for v in done.group(1).split(":"))
        ended = started.replace(hour=hh, minute=mm, second=ss)
        # The completion line carries a time and no date, so a batch that ran
        # across midnight ends "before" it started.
        if ended < started:
            ended += timedelta(days=1)
        batches += 1
        pairs += int(done.group(2))
        minutes += (ended - started).total_seconds() / 60.0
        started = None
    if not minutes:
        return FALLBACK_RATE, 0, 0, 0.0
    return round(60.0 * pairs / minutes), batches, pairs, minutes


def _section(md: str, heading: str) -> str:
    """Pull one `### heading` block out of the markdown emitter's output."""
    blocks = md.split("### ")
    for block in blocks:
        if block.startswith(heading):
            body = block[len(heading) :].strip("\n")
            return body.strip()
    raise KeyError(f"no section titled {heading!r} in the figures output")


def language_pairs_table(f: dict) -> str:
    """Section 6.1's table for domain-year records, per year and in total.

    No syntax-anomalous column. It is structurally zero, and it describes the
    spelling of the domain rather than the language of the site, so a column of
    zeros beside English and Undetermined invites the reader to compare two
    different things. The count is stated in prose instead.
    """
    lines = [
        "| Year | pairs added | English | Named other | Undetermined | Not yet reached |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    totals = {"added": 0, "english": 0, "other": 0, "undetermined": 0, "unchecked": 0}
    for year in sorted(f["verdicts_by_year"]):
        row = f["verdicts_by_year"][year]
        added = sum(row.values())
        totals["added"] += added
        for key in ("english", "other", "undetermined", "unchecked"):
            totals[key] += row.get(key, 0)
        lines.append(
            f"| {year} | {added:,} | {row.get('english', 0):,} | {row.get('other', 0):,} | "
            f"{row.get('undetermined', 0):,} | {row.get('unchecked', 0):,} |"
        )
    lines.append(
        f"| **Total** | **{totals['added']:,}** | **{totals['english']:,}** | "
        f"**{totals['other']:,}** | **{totals['undetermined']:,}** | "
        f"**{totals['unchecked']:,}** |"
    )
    return "\n".join(lines)


def language_domains_table(f: dict) -> str:
    """Section 6.1's table for cross-year unique domains.

    One row, not six, and that is not laziness. Within a single year a domain
    appears exactly once, so a per-year "unique domains" table would reproduce
    the pair counts column for column and imply a distinction that does not
    exist. The cross-year figure is the one that says something the pair table
    does not: how many distinct websites this submission contributes.
    """
    by_verdict = f["unique_domains_by_verdict"]
    lines = [
        "| Scope | domains added | English | Named other | Undetermined | Not yet reached |",
        "|---|--:|--:|--:|--:|--:|",
        f"| all six years, deduplicated | **{f['netnew_unique_domains']:,}** | "
        f"**{by_verdict.get('english', 0):,}** | **{by_verdict.get('other', 0):,}** | "
        f"**{by_verdict.get('undetermined', 0):,}** | "
        f"**{by_verdict.get('unchecked', 0):,}** |",
        "",
        "A domain verified English in one year and another language in a different year counts in "
        "both columns, because the claim is made per year, so these columns can sum to more than "
        "the domains-added figure.",
    ]
    return "\n".join(lines)


def per_year_table(f: dict) -> str:
    """Volume per year, beside the baseline it is measured against.

    The verdict breakdown is section 3's table and the growth thresholds are
    section 8's, so neither is repeated here.
    """
    lines = [
        "| Year | merged260730, this counting unit | Additions | Capture-backed |",
        "|---|--:|--:|--:|",
    ]
    for year in sorted(f["netnew_by_year"]):
        added = f["netnew_by_year"][year]
        base = f["baseline_by_year"].get(year, 0)
        cb = f["capture_backed_by_year"].get(year, 0)
        share = 100.0 * cb / added if added else 0.0
        lines.append(f"| {year} | {base:,} | {added:,} | {cb:,} ({share:.1f}%) |")
    cb_total = f["capture_backed_total"]
    cb_share = 100.0 * cb_total / f["netnew_pairs"] if f["netnew_pairs"] else 0.0
    lines.append(
        f"| **Total** | **{f['baseline_pairs']:,}** | **{f['netnew_pairs']:,}** | "
        f"**{cb_total:,} ({cb_share:.1f}%)** |"
    )
    return "\n".join(lines)


def source_table(f: dict) -> str:
    """The per-source table, with every column feedback section 7 names.

    Scoped to sources that contribute to this round: net-new pairs or names in
    the candidate pool. Sources from the initial gathering now score zero on
    both, because merged260730 absorbed their additions, and listing twenty rows
    of zeros reports the initial gathering rather than this round. Section 7's
    "zero-yield or failure reasons" is answered by the assessment table beside
    this one, which names the sources tried this round and rejected.
    """
    conn = duckdb.connect(str(DB), read_only=True)
    rows = conn.execute("""
        SELECT source, evidence_type, files_ingested, evidence_rows,
               pairs_backed, netnew_pairs, netnew_domains, candidate_domains
        FROM read_csv('data/reports/source_contribution.csv', header = true)
        WHERE evidence_type <> 'prior_reused'
        ORDER BY netnew_pairs DESC, candidate_domains DESC, source
    """).fetchall()
    conn.close()
    lines = [
        "| Source | Evidence type | Files | Evidence rows | Accepted pairs |"
        " Net-new pairs | Domains absent from baseline | Candidates found |",
        "|---|---|--:|--:|--:|--:|--:|--:|",
    ]
    contributing = 0
    for src, etype, files, ev, backed, netnew, newdom, cand in rows:
        # In if it added pairs this round, or if its whole contribution is names
        # in the candidate pool. A source with accepted pairs and no net-new ones
        # is an initial-gathering source the baseline has absorbed.
        if netnew == 0 and not (cand > 0 and backed == 0):
            continue
        if netnew:
            contributing += 1
        lines.append(
            f"| `{src}` | `{etype}` | {files:,} | {ev:,} | {backed:,} | {netnew:,} | "
            f"{newdom:,} | {cand:,} |"
        )
    lines.append("")
    lines.append(
        f"{contributing} sources contributed net-new pairs. Rows showing zero there are "
        "candidate-only sources, whose whole contribution is names awaiting evidence."
    )
    return "\n".join(lines)


def substitutions(f: dict) -> dict[str, str]:
    t = f["verdict_totals"]
    unverified = t["other"] + t["undetermined"] + t["unchecked"]
    md = markdown(f)
    rate, batches, rate_pairs, rate_minutes = measured_throughput()

    subs: dict[str, str] = {
        "ENGLISH": f"{t['english']:,}",
        "UNVERIFIED": f"{unverified:,}",
        "TOTAL": f"{f['netnew_pairs']:,}",
        "UNIQUE": f"{f['netnew_unique_domains']:,}",
        "NEWDOMAINS": f"{f['netnew_domains_absent_from_baseline']:,}",
        "CANDIDATES": f"{f['candidate_pool']:,}",
        "HARVESTED": f"{f['harvested_this_round']:,}",
        "CAPTUREBACKED": f"{f['capture_backed_total']:,}",
        "PER_YEAR_TABLE": per_year_table(f),
        "LANG_PAIRS_TABLE": language_pairs_table(f),
        "LANG_DOMAINS_TABLE": language_domains_table(f),
        "SOURCE_TABLE": source_table(f),
        "COMPLETENESS_TABLE": _section(md, "Completeness"),
        "REASON_TABLE": _section(md, "Every judged rejection, by reason"),
        "RATE": f"{rate}",
        "RATEBATCHES": f"{batches}",
        "RATEPAIRS": f"{rate_pairs:,}",
        "RATEMINUTES": f"{rate_minutes:,.0f}",
    }
    base_share = 100.0 * f["netnew_pairs"] / f["baseline_pairs"] if f["baseline_pairs"] else 0.0
    subs["BASELINESHARE"] = f"{base_share:.2f}%"

    # Projection to the engine's cut-off, Monday 3 August 12:00 UTC. Stated as
    # arithmetic in the report, so the inputs are visible: the measured rate,
    # the window remaining at fill time, and the observed share of settled
    # verdicts that come back English. The window is computed, not typed,
    # because a hardcoded horizon goes stale every time the fill re-runs.
    deadline = datetime.fromtimestamp(ENGINE_DEADLINE_EPOCH)
    hours = max(0.0, (deadline - datetime.now()).total_seconds() / 3600.0)
    subs["WINDOW"] = f"{hours:.0f}"
    classified = rate * hours
    # The English share is the store's, over every settled verdict, not one
    # batch's: a single batch has read 64.5% and the running figure is nearer
    # 58%, because the queue interleaves early-year pairs that yield less. The
    # low projection applies a 70% duty allowance for the archive refusing the
    # engine, which it has done three times.
    total_judged = t["english"] + t["other"] + t["undetermined"]
    english_share = (t["english"] / total_judged) if total_judged else 0.60
    subs["SHARE"] = f"{100 * english_share:.1f}%"

    # Rounded to the nearest 500. A projection quoted to four significant figures
    # claims a precision the inputs do not have, and it invites being held to the
    # exact number.
    def _round(n: float) -> str:
        return f"{int(round(n / 500.0) * 500):,}"

    subs["PROJ_LOW"] = _round(classified * 0.7 * english_share)
    subs["PROJ_HIGH"] = _round(classified * english_share)
    subs["PROJECTED"] = _round(classified)
    # What the email quotes: the size the English set reaches by the cut-off,
    # so the current count plus the projected additions.
    subs["MONDAY_LOW"] = _round(t["english"] + classified * 0.7 * english_share)
    subs["MONDAY_HIGH"] = _round(t["english"] + classified * english_share)
    return subs


def fill(template: Path, target: Path, subs: dict[str, str], check: bool) -> list[str]:
    text = template.read_text()
    for token, value in subs.items():
        text = text.replace(f"[{token}]", value)
    remaining = sorted(set(re.findall(r"\[([A-Z_0-9]{2,})\]", text)))
    if not check and not remaining:
        target.write_text(text)
    return remaining


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report, do not write")
    args = parser.parse_args()

    conn = duckdb.connect(str(DB), read_only=True)
    subs = substitutions(figures(conn))
    conn.close()

    failed = False
    for template, target in DOCUMENTS:
        remaining = fill(template, target, subs, args.check)
        if remaining:
            print(f"{template}: UNFILLED {remaining}", file=sys.stderr)
            failed = True
        else:
            print(f"{target}: {'would fill' if args.check else 'filled'} cleanly")
    if failed:
        # Loud, because a report containing the literal text [ENGLISH] is worse
        # than one containing a number an hour out of date.
        raise SystemExit("refusing to leave a placeholder in a document that ships")


if __name__ == "__main__":
    main()
