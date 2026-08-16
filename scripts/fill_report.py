"""Substitute the round report's placeholders from the live store.

The report must not contain a figure that disagrees with the shipped files, and
the way that happens is a human retyping a number after the data moved. So the
report is written with `[PLACEHOLDER]` tokens and this fills them from the same
queries `report_figures.py` uses.

Two properties worth having. It is idempotent in the sense that re-running it on
a filled report is a no-op (there are no tokens left to match), so the source of
truth stays in git as a template. And it **fails loudly on a token it cannot
fill**, rather than shipping a report with `[TOTAL]` in it, which is the one
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

from ark.db import connect_read_only_patiently

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from report_figures import BASELINE, figures, markdown  # noqa: E402

from ark.baseline import REVIEWER_BASELINE_PAIRS  # noqa: E402
from ark.evidence_types import MASTER_TYPES  # noqa: E402
from ark.stats import collect_stats  # noqa: E402

# The one column a reviewer actually interrogates: not where a name was found,
# but what establishes the year. Kept here rather than in prose so the per-source
# table cannot describe a source the store no longer contains, or omit one it
# gained. An unlisted source falls back to a pointer at `sources.md`.
DATE_BASIS = {
    "usenet_announce": "post date of the announcement",
    "usenet_address": "post date of the message carrying the address",
    "usenet_bare": "post date of the message carrying the address",
    "ia_cdx_bulk": "Wayback capture timestamp",
    "uucp_map_registry": "posting date of the registry's generated dump",
    "uucp_map_creation": "the registrar's own `approved:` date",
    "enron_email": "the message `Date:` header",
    "rtfm_faq": "the FAQ's revision header",
    "trade_press": "the issue cover date",
    "tucows_catalogue": "software release date",
    "afnic_fr": "registry creation date",
    "isc_survey": "survey run date",
    "early_web_cdx": "Wayback capture timestamp",
    "rdap_snapshot": "the registry's own `registration` event date",
    "rdap": "the registry's own `registration` event date",
    "maillist_archive": "the message `Date:` header",
    "page_directory": "capture timestamp of the archived catalogue page",
    "page_expansion": "capture timestamp of the archived page",
    "ukwa_link_source": "UK Web Archive crawl date",
    "ncsa_whats_new": "the announcement page's own date",
    "internet_scout": "the Scout Report issue date",
    "arquivo_ia": "capture timestamp",
    "arquivo_roteiro": "capture timestamp",
}

DB = Path("data/ark.duckdb")
# Template in, filled document out. Filling in place would consume the template,
# and the numbers have to be refilled every time the archive is re-cut, so the
# template is the thing that lives in git and the filled copy is a build product.
#
# One report, not one per round. Dated filenames meant the packaging script had
# to be repointed every round and once shipped the previous round's report beside
# this round's data. The round is identified by its content and its git tag, not
# by its filename.
#
# Nothing addressed to a person is filled here. `package_delivery.sh` ships
# `git archive HEAD`, so every tracked file reaches the reviewer, and the
# 2 August archive carried an email draft's "notes for Ivo" section, which was
# private reasoning about how to present the work to him. Email drafts live in
# `private/`, which is git-ignored, and are written by hand.
DOCUMENTS = ((Path("docs/report.template.md"), Path("docs/report.md")),)


def _section(md: str, heading: str) -> str:
    """Pull one `### heading` block out of the markdown emitter's output."""
    blocks = md.split("### ")
    for block in blocks:
        if block.startswith(heading):
            body = block[len(heading) :].strip("\n")
            return body.strip()
    raise KeyError(f"no section titled {heading!r} in the figures output")


def per_year_table(f: dict) -> str:
    """Volume per year, beside the baseline it is measured against.

    The per-source split and the growth thresholds have their own tables, so
    neither is repeated here.
    """
    lines = [
        f"| Year | {BASELINE}, this counting unit | Additions | Capture-backed |",
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
    conn = connect_read_only_patiently(DB)
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


def ee_source_table(f: dict) -> str:
    """Per source, ordered by the metric the round is scored on.

    Ordered by equivalent-English rather than by pair count, because those two
    orders disagree: 23,678 `.ca` pairs outrank 107,304 pairs of mixed Usenet
    origin, and a table sorted by volume would put the weaker source first.
    """
    lines = [
        "| Source | What carries the date | Evidence type | Admissible | Net-new pairs | "
        "Equivalent-English |",
        "|---|---|---|---|--:|--:|",
    ]
    for row in f["by_source"]:
        admissible = "master" if row["master"] else "**candidate only**"
        lines.append(
            f"| `{row['source']}` | {DATE_BASIS.get(row['source'], 'see `sources.md`')} | "
            f"`{row['evidence_type']}` | {admissible} | {row['pairs']:,} | {row['ee']:,.1f} |"
        )
    lines.append(f"| **Total** | | | | **{f['netnew_pairs']:,}** | **{f['ee_netnew']:,.1f}** |")
    return "\n".join(lines)


def corroboration_sentence(f: dict) -> str:
    """Cross-source agreement in one line, because it is not the deliverable.

    This was a table. The reviewer's interest is the annual files, and a
    corroboration statistic is a nice-to-have beside them, so it earns a sentence
    rather than a section.
    """
    conn = connect_read_only_patiently(DB)
    stats = collect_stats(conn)
    conn.close()
    return (
        f"Beyond that, {stats['independently_corroborated_netnew']:,} of this round's pairs are "
        f"confirmed by two or more independent collection lineages rather than one, and every "
        f"asserted pair in the collection carries {stats['avg_sources_per_pair']} distinct sources "
        f"on average."
    )


def admissibility_sentence(f: dict) -> str:
    """Whether every source in the table may back an annual-file entry.

    Generated rather than asserted. The reviewer asked precisely this question of
    the previous draft, and the honest answer has to come from the shipped rows:
    if a candidate-only type ever backed an assignment, this says so by name
    instead of repeating a claim that had stopped being true.
    """
    n_sources = len(f["by_source"])
    if f["all_sources_master"]:
        return (
            f"**All {n_sources} are master sources, so all {f['netnew_pairs']:,} pairs are "
            f"admitted to the annual files.** None of them is candidate-only. Names may pass "
            f"through the candidate pool on the way in, and this round many did, but a pair is "
            f"only counted once a master source dates it."
        )
    named = ", ".join(f"`{s}`" for s in f["non_master_sources"])
    return (
        f"**{n_sources - len(f['non_master_sources'])} of {n_sources} are master sources.** "
        f"These are not, and their rows do not enter the annual files: {named}."
    )


def substitutions(f: dict) -> dict[str, str]:
    md = markdown(f)

    subs: dict[str, str] = {
        "TOTAL": f"{f['netnew_pairs']:,}",
        "UNIQUE": f"{f['netnew_unique_domains']:,}",
        "NEWDOMAINS": f"{f['netnew_domains_absent_from_baseline']:,}",
        "CANDIDATES": f"{f['candidate_pool']:,}",
        "HARVESTED": f"{f['harvested_this_round']:,}",
        "CAPTUREBACKED": f"{f['capture_backed_total']:,}",
        "BASELINE": BASELINE,
        "EE": f"{f['ee_netnew']:,.1f}",
        "EEBASELINE": f"{f['ee_baseline']:,.1f}",
        "EEGROWTH": f"{f['ee_netnew_growth_pct']:.4f}%",
        "EEMEAN": f"{f['ee_mean_weight']:.4f}",
        "EE_SOURCE_TABLE": ee_source_table(f),
        "CORROBORATION": corroboration_sentence(f),
        "ADMISSIBLE": admissibility_sentence(f),
        "MASTERTYPES": ", ".join(f"`{t}`" for t in sorted(MASTER_TYPES) if t != "prior_reused"),
        "PER_YEAR_TABLE": per_year_table(f),
        "SOURCE_TABLE": source_table(f),
        "COMPLETENESS_TABLE": _section(md, "Completeness"),
        "CDX_TABLE": cdx_table(),
        "CDX_FAILURES": cdx_failures(),
        "DATASETS_SEARCHED": datasets_searched(),
    }
    base_share = 100.0 * f["netnew_pairs"] / f["baseline_pairs"] if f["baseline_pairs"] else 0.0
    subs["BASELINESHARE"] = f"{base_share:.2f}%"
    # The REVIEWER'S raw record count, not the store's. These differ by 1.6 million,
    # because the store canonicalises to registrable domains and he counts lines, and
    # a sentence that set his count for one release beside our count for the next
    # would read as a shrinking baseline. Quote one counting unit or the other, never
    # one of each.
    subs["BASELINEPAIRS"] = f"{REVIEWER_BASELINE_PAIRS:,}"
    subs["STOREBASELINEPAIRS"] = f"{f['baseline_pairs']:,}"

    # The acceptance threshold, derived rather than typed. It moved by 106,022 EE when
    # the reviewer reissued the baseline mid-round, and a hand-written 5% figure in the
    # prose would have quietly kept describing the old one.
    target = float(f["ee_baseline"]) * 0.05
    subs["EE5PCT"] = f"{target:,.2f}"
    subs["EE5PCTGAP"] = f"{target - float(f['ee_netnew']):,.2f}"

    return subs


def datasets_searched() -> str:
    """The register of families searched, read from `sources.md` rather than retyped.

    The reviewer asks for every external dataset and repository searched. That list
    only stays true if it is derived from the register itself: a hand-written copy
    omits whatever was added after it was written, and the omission is invisible.

    `sources.md` gives one `## ` heading per family. Headings that are not families
    are skipped by name, since the file also uses that level for its own front matter.
    """
    path = Path(__file__).resolve().parents[1] / "docs" / "sources.md"
    if not path.is_file():
        return "_`sources.md` not found beside this report._"

    skip = {"Summary", "Source names that are not separate sources"}
    families = [
        line[3:].strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ") and line[3:].strip() not in skip
    ]
    if not families:
        return "_No families recorded._"

    lines = [
        f"**{len(families)} source families are recorded in `docs/sources.md`**, each with what "
        "dates an item, where to obtain it, and the measurement that closed it where it "
        "was closed:",
        "",
    ]
    lines += [f"- {name}" for name in families]
    return "\n".join(lines)


def _cdx_notes(markdown_form: bool) -> str:
    """Borrow the CDX campaign measurement rather than re-deriving it.

    One implementation, used by both the standalone tool and the report, because
    the reviewer now asks for these numbers in the deliverable and two versions of
    a success rate is exactly the drift this whole file exists to prevent.
    """
    from cdx_execution_notes import CDX_DIR, render, scan

    tallies = scan(CDX_DIR)
    if not tallies:
        return "No CDX journals were found on this machine."
    return render(tallies, markdown_form)


def cdx_table() -> str:
    return _cdx_notes(markdown_form=True).split("\n\nOf ")[0]


def cdx_failures() -> str:
    body = _cdx_notes(markdown_form=True)
    _, _, tail = body.partition("\n\nOf ")
    return f"Of {tail}" if tail else body


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

    conn = connect_read_only_patiently(DB)
    subs = substitutions(figures(conn))
    conn.close()

    failed = False
    for template, target in DOCUMENTS:
        # `private/` is git-ignored, so a fresh clone has no email template. That
        # must not fail the report build, which is the part that ships.
        if not template.exists():
            print(f"{template}: absent, skipping")
            continue
        remaining = fill(template, target, subs, args.check)
        if remaining:
            print(f"{template}: UNFILLED {remaining}", file=sys.stderr)
            failed = True
        else:
            print(f"{target}: {'would fill' if args.check else 'filled'} cleanly")
    if failed:
        # Loud, because a report containing the literal text [TOTAL] is worse
        # than one containing a number an hour out of date.
        raise SystemExit("refusing to leave a placeholder in a document that ships")


if __name__ == "__main__":
    main()
