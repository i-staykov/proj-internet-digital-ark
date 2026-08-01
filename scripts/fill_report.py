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
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from report_figures import figures, markdown  # noqa: E402

DB = Path("data/ark.duckdb")
# Template in, filled document out. Filling in place would consume the template,
# and the numbers have to be refilled every time the archive is re-cut, so the
# template is the thing that lives in git and the filled copy is a build product.
DOCUMENTS = (
    (Path("docs/report_260801.template.md"), Path("docs/report_260801.md")),
    (Path("docs/email_draft_260801.template.md"), Path("docs/email_draft_260801.md")),
)

# Measured, not derived from the store: these come from the supervisor logs and
# from the previous round's recorded position. Kept here rather than inline in
# the prose so there is one place to correct them.
# Measured over a complete batch on the corrected engine: 400 pairs classified
# between 14:02:53 and 15:08:18 CEST on 1 August, 65.4 minutes.
MEASURED_RATE = 367
PRIOR_BY_YEAR = {1996: 4994, 1997: 3534, 1998: 6029, 1999: 696, 2000: 9702, 2001: 7743}


def _section(md: str, heading: str) -> str:
    """Pull one `### heading` block out of the markdown emitter's output."""
    blocks = md.split("### ")
    for block in blocks:
        if block.startswith(heading):
            body = block[len(heading) :].strip("\n")
            return body.strip()
    raise KeyError(f"no section titled {heading!r} in the figures output")


def language_pairs_table(f: dict) -> str:
    """Section 6.1's table for domain-year records, per year and in total."""
    lines = [
        "| Year | pairs added | English | Named other | Undetermined | Syntax-anomalous |"
        " Not yet reached |",
        "|---|--:|--:|--:|--:|--:|--:|",
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
            f"{row.get('undetermined', 0):,} | 0 | {row.get('unchecked', 0):,} |"
        )
    lines.append(
        f"| **Total** | **{totals['added']:,}** | **{totals['english']:,}** | "
        f"**{totals['other']:,}** | **{totals['undetermined']:,}** | **0** | "
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
        "| Scope | domains added | English | Named other | Undetermined | Syntax-anomalous |"
        " Not yet reached |",
        "|---|--:|--:|--:|--:|--:|--:|",
        f"| all six years, deduplicated | **{f['netnew_unique_domains']:,}** | "
        f"**{by_verdict.get('english', 0):,}** | **{by_verdict.get('other', 0):,}** | "
        f"**{by_verdict.get('undetermined', 0):,}** | **0** | "
        f"**{by_verdict.get('unchecked', 0):,}** |",
        "",
        "A domain verified English in one year and another language in a different year counts in "
        "both columns, because the claim is made per year, so these columns can sum to more than "
        "the domains-added figure.",
    ]
    return "\n".join(lines)


def per_year_table(f: dict) -> str:
    lines = [
        "| Year | Net-new pairs | Capture-backed | English-verified | Disqualified |"
        " Not yet reached |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    t = f["verdict_totals"]
    for year in sorted(f["verdicts_by_year"]):
        row = f["verdicts_by_year"][year]
        added = sum(row.values())
        cb = f["capture_backed_by_year"].get(year, 0)
        share = 100.0 * cb / added if added else 0.0
        disq = row.get("other", 0) + row.get("undetermined", 0)
        lines.append(
            f"| {year} | {added:,} | {cb:,} ({share:.1f}%) | {row.get('english', 0):,} | "
            f"{disq:,} | {row.get('unchecked', 0):,} |"
        )
    cb_total = f["capture_backed_total"]
    cb_share = 100.0 * cb_total / f["netnew_pairs"] if f["netnew_pairs"] else 0.0
    lines.append(
        f"| **Total** | **{f['netnew_pairs']:,}** | **{cb_total:,} ({cb_share:.1f}%)** | "
        f"**{t['english']:,}** | **{t['other'] + t['undetermined']:,}** | "
        f"**{t['unchecked']:,}** |"
    )
    return "\n".join(lines)


def source_table(f: dict) -> str:
    conn = duckdb.connect(str(DB), read_only=True)
    rows = conn.execute("""
        SELECT source, evidence_type, files_ingested, evidence_rows,
               pairs_backed, netnew_pairs, netnew_domains, candidate_domains
        FROM read_csv('data/reports/source_contribution.csv', header = true)
        WHERE evidence_type <> 'prior_reused' AND netnew_pairs > 0
        ORDER BY netnew_pairs DESC
    """).fetchall()
    conn.close()
    lines = [
        "| Source | Evidence type | Files | Evidence rows | Accepted pairs |"
        " Net-new vs merged260730 | Net-new domains |",
        "|---|---|--:|--:|--:|--:|--:|",
    ]
    for src, etype, files, ev, backed, netnew, newdom, _cand in rows:
        lines.append(
            f"| `{src}` | `{etype}` | {files:,} | {ev:,} | {backed:,} | {netnew:,} | {newdom:,} |"
        )
    return "\n".join(lines)


def substitutions(f: dict) -> dict[str, str]:
    t = f["verdict_totals"]
    unverified = t["other"] + t["undetermined"] + t["unchecked"]
    md = markdown(f)
    usenet = next((r["pairs"] for r in f["by_source"] if r["source"] == "usenet_announce"), 0)
    cb_share = 100.0 * f["capture_backed_total"] / f["netnew_pairs"] if f["netnew_pairs"] else 0.0

    subs: dict[str, str] = {
        "ENGLISH": f"{t['english']:,}",
        "UNVERIFIED": f"{unverified:,}",
        "TOTAL": f"{f['netnew_pairs']:,}",
        "UNIQUE": f"{f['netnew_unique_domains']:,}",
        "NEWDOMAINS": f"{f['netnew_domains_absent_from_baseline']:,}",
        "CANDIDATES": f"{f['candidate_pool']:,}",
        "HARVESTED": f"{f['harvested_this_round']:,}",
        "CAPTUREBACKED": f"{f['capture_backed_total']:,}",
        "CBSHARE": f"{cb_share:.1f}%",
        "USENETPAIRS": f"{usenet:,}",
        "PER_YEAR_TABLE": per_year_table(f),
        "LANG_PAIRS_TABLE": language_pairs_table(f),
        "LANG_DOMAINS_TABLE": language_domains_table(f),
        "SOURCE_TABLE": source_table(f),
        "COMPLETENESS_TABLE": _section(md, "Completeness"),
        "REASON_TABLE": _section(md, "Every judged rejection, by reason"),
        "RATE": f"{MEASURED_RATE}",
    }
    # Which year grew most is asserted in prose, so it is derived rather than
    # typed: the ordering changes as the secondary stream ingests, and a
    # sentence naming the wrong year is the kind of error a reviewer checks.
    growth = {y: (f["netnew_by_year"].get(y, 0) - p) / p for y, p in PRIOR_BY_YEAR.items() if p}
    subs["TOPGROWTH"] = str(max(growth, key=lambda y: growth[y]))

    for year, prior in PRIOR_BY_YEAR.items():
        now = f["netnew_by_year"].get(year, 0)
        subs[f"Y{year}"] = f"{now:,}"
        change = 100.0 * (now - prior) / prior if prior else 0.0
        subs[f"C{year}"] = f"+{change:,.0f}%"

    # Projection to Monday 12:00 UTC. Stated as arithmetic in the report, so the
    # inputs are visible: the measured rate, the window, and the observed share
    # of settled verdicts that come back English.
    hours = 48
    classified = MEASURED_RATE * hours
    # 258 of 400 records in the first complete v3 batch came back english, so the
    # share is measured rather than assumed. The low row applies a 70% duty
    # allowance for the archive refusing us, which it has done three times.
    english_share = 0.645
    # Rounded to the nearest 500. A projection quoted to four significant figures
    # claims a precision the inputs do not have, and it invites being held to the
    # exact number.
    def _round(n: float) -> str:
        return f"{int(round(n / 500.0) * 500):,}"

    subs["PROJ_LOW"] = _round(classified * 0.7 * english_share)
    subs["PROJ_HIGH"] = _round(classified * english_share)
    subs["PROJECTED"] = _round(classified)
    subs["X"] = f"{t['english']:,}"
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
