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
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

from ark.db import connect_read_only_patiently

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from report_figures import BASELINE, figures, markdown  # noqa: E402

from ark.baseline import (  # noqa: E402
    CURRENT_ROUND_LABEL,
    REVIEWER_BASELINE_PAIRS,
    SUBMITTED_ROUNDS,
)
from ark.evidence_types import MASTER_TYPES  # noqa: E402
from ark.stats import collect_stats  # noqa: E402

# The one column a reviewer actually interrogates: not where a name was found,
# but what establishes the year. Kept here rather than in prose so the per-source
# table cannot describe a source the store no longer contains, or omit one it
# gained. An unlisted source falls back to a pointer at `sources.md`.
DATE_BASIS = {
    "domain_creation_bulk": "the registry's own creation date for that domain",
    "us_domain_delegated": "the edition date of the delegated-zone list",
    "ripe_dbase_1999": "the snapshot's own generation stamp, `# 990804 00:07:01`",
    "ripe_dbase_changed": "the date on the object's own `changed:` transaction line",
    "squidguard_2001_blacklist": "the list's own compile stamp, or the diff's date",
    "iedr_register": "the register page's own `updated automatically at` line",
    "internic_zone": "the SOA serial inside the zone payload",
    "ukwa_geoindex": "the 14-digit capture timestamp on the row",
    "dartmouth_nber_captures": "the archive's own count of captures it holds in that year",
    "udrp_proceedings": "the commencement date of the dispute",
    "attrition_defacement": "the date the defacement was recorded",
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
# The email is filled too, but ONLY out of `private/`, which is git-ignored.
# `package_delivery.sh` ships `git archive HEAD`, so every tracked file reaches the
# reviewer, and the 2 August archive carried an email draft's "notes for Ivo" section:
# private reasoning about how to present the work to him. A template addressed to a
# person is one edit away from carrying that again, so the whole pair stays outside git
# and the fill is what keeps its five figures identical to the report's.
# (template, target, an unwritten round section is fatal). Fatal for the report, which
# ships: an empty section 5 reaching the reviewer is the failure the whole token
# mechanism exists to prevent. Not fatal for the email, which is a draft Ivo finishes by
# hand at submission time and which never leaves `private/`. Making it fatal there would
# block every packaging run for a document nobody is sending yet.
DOCUMENTS = (
    (Path("docs/report.template.md"), Path("docs/report.md"), True),
    (Path("private/email.template.md"), Path("private/email-draft.md"), False),
)


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


# Sources admitted in THIS round, with the one-line ground on which each was
# admitted. Ivo, 2026-08-26: a reader of the report should see WHY a new source was
# accepted, not only what it yielded, and `sources.md` should not be the only place
# that says so. Keyed by source name; a source absent from here is one the reviewer
# has already seen in an earlier round.
ADMITTED_THIS_ROUND = {
    "us_domain_delegated": (
        "a delegated-zone list is the registry serving those names at the instant the "
        "edition is stamped, the same instrument as a zone file"
    ),
    "iedr_register": (
        "the registry regenerated its whole register as static pages, each carrying the "
        "instant a cron wrote it"
    ),
    "internic_zone": "the zone file's own SOA serial, which the registry wrote",
    "ripe_dbase_1999": (
        "the snapshot states its own generation instant, so a domain object in it is the "
        "registry's database contents at that instant; used with the RIPE NCC's written "
        "permission and read for the domain name only, no contact or personal data"
    ),
    "ripe_dbase_changed": (
        "each registry object carries a dated `changed:` line per update applied to it, and "
        "an object cannot be modified before it exists, so the line evidences the "
        "registration at its own date; this is what rule 6 means by continued registration "
        "needing its own record, and it reaches 1996-1998 which the snapshot's own date "
        "cannot. The top eight changer addresses are ccTLD registry role accounts, DENIC "
        "alone 49.4%, and only the date is read, never the address beside it"
    ),
    "squidguard_2001_blacklist": (
        "the compiler's header asserts a successful fetch, 510,389 of 654,820 links tested "
        "successfully, so a listed host answered when the robot called"
    ),
    "ukwa_geoindex": "a per-row capture timestamp, self-dating and unsplit",
    "ukwa_link_source": "the crawl year on each host link-graph row",
}


def admitted_this_round(f: dict) -> str:
    """One line per source admitted this round, naming the ground it was admitted on."""
    present = [r["source"] for r in f["by_source"] if r["source"] in ADMITTED_THIS_ROUND]
    if not present:
        return ""
    items = "; ".join(f"**`{s}`**, {ADMITTED_THIS_ROUND[s]}" for s in present)
    return (
        "**Admitted this round, and the ground each was admitted on** (the full argument, "
        f"and every rejected source beside it, is in `sources.md`): {items}."
        + (
            " The 1999 RIPE database snapshot is used with the written permission of the "
            "**RIPE NCC**, gratefully acknowledged, and only the domain name is read from it."
            if "ripe_dbase_1999" in present
            else ""
        )
    )


def ee_source_table(f: dict) -> str:
    """Per source, ordered by the metric the round is scored on.

    Ordered by equivalent-English rather than by pair count, because those two
    orders disagree: 23,678 `.ca` pairs outrank 107,304 pairs of mixed Usenet
    origin, and a table sorted by volume would put the weaker source first.
    """
    # Four columns, not six. The date basis repeats section 3 and `sources.md`, and
    # an "admissible" column whose every value is "master" is a column of one fact,
    # stated once in the prose instead. A candidate-only row would still be marked,
    # so the distinction the reviewer asked for survives the cut.
    lines = [
        "| Source | Evidence type | Net-new pairs | Equivalent-English |",
        "|---|---|--:|--:|",
    ]
    # Sources contributing under a tenth of a percent of the round are folded into one
    # row. Nine of them together were 162 equivalent-English of 510,613 last round, so
    # they cost eight lines of a four-page report to say nothing. The full per-source
    # breakdown ships in `audit/` and in the provenance parquet either way.
    floor = Decimal("0.001") * Decimal(str(f["ee_netnew"]))
    shown = [r for r in f["by_source"] if r["ee"] >= floor]
    folded = [r for r in f["by_source"] if r["ee"] < floor]
    for row in shown:
        mark = "" if row["master"] else " **(candidate only)**"
        lines.append(
            f"| `{row['source']}`{mark} | `{row['evidence_type']}` | "
            f"{row['pairs']:,} | {row['ee']:,.1f} |"
        )
    if folded:
        lines.append(
            f"| *{len(folded)} further sources, each under 0.1% of the round* | | "
            f"{sum(r['pairs'] for r in folded):,} | {sum(r['ee'] for r in folded):,.1f} |"
        )
    lines.append(f"| **Total** | | **{f['netnew_pairs']:,}** | **{f['ee_netnew']:,.1f}** |")
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


def accepted_totals() -> dict | None:
    """The reviewer-equivalent figures from the latest merge audit, or None.

    **Section 1 must quote what HIS calculator will produce over the shipped files,
    not what our store holds.** The two differ by a handful of records, because the
    merge applies the normalisation his calculator applies and the store does not:
    on 2026-08-24 the store held 726,344 net-new pairs and 726,336 survived it. A
    report whose headline disagrees with its own reconciliation section by eight
    records is the kind of thing a reviewer bounces, and this register already warns
    that quoting a count in two places is how they come to disagree.
    """
    merge_dir = Path(__file__).resolve().parents[1] / "output/merge"
    audits = sorted(merge_dir.glob("merge_audit_ark*.json"))
    if not audits:
        return None
    # **By modification time, not by name.** Sorting alphabetically picks
    # `merge_audit_ark_20260824c.json` over a freshly written `merge_audit_ark.json`,
    # because the tagged name sorts last. That is how a stale audit survived a re-run on
    # 2026-08-26 and put a 488,722 increment beside a 5.3344% growth rate.
    newest = max(audits, key=lambda path: path.stat().st_mtime)
    return json.loads(newest.read_text(encoding="utf-8"))["totals"]


def substitutions(f: dict) -> dict[str, str]:
    md = markdown(f)
    accepted = accepted_totals()
    # Fall back to the store only when no merge has been run, so a missing audit
    # produces a slightly different number rather than an empty placeholder.
    total = int(accepted["accepted_new_records"]) if accepted else f["netnew_pairs"]
    ee_total = (
        Decimal(accepted["equivalent_english_increment"]) if accepted else Decimal(f["ee_netnew"])
    )
    # **The headline increment comes from the MERGE AUDIT and the growth rate from the
    # LIVE STORE, so a stale audit makes lines 3 and 4 contradict line 5.** Caught on
    # 2026-08-26 with the audit reading 769,438 records and 488,722 EE beside a live
    # 5.3344% that implies 712,801. Both numbers were individually right and the table was
    # nonsense. Re-run `merge_against_baseline.py` after the last ingest of a round; this
    # refuses to fill rather than shipping a self-contradicting table.
    if accepted:
        drift = abs(Decimal(f["ee_netnew"]) - ee_total)
        # Relative, because a running collector moves the store by a few pairs while the
        # merge is scoring files. 0.05% catches a stale ROUND (488,722 against 712,801 is
        # 31%) while tolerating the handful of pairs a live ingest adds mid-run. For a
        # submission, stop the ingest loop first so the drift is zero.
        if drift > max(Decimal("50"), ee_total * Decimal("0.0005")):
            raise SystemExit(
                "merge audit is stale: it reports "
                f"{ee_total:,.4f} equivalent-English over {total:,} records, but the store "
                f"holds {Decimal(f['ee_netnew']):,.4f} over {f['netnew_pairs']:,}. "
                "Run `uv run python scripts/merge_against_baseline.py` and refill."
            )

    subs: dict[str, str] = {
        "TOTAL": f"{total:,}",
        "UNIQUE": f"{f['netnew_unique_domains']:,}",
        "NEWDOMAINS": f"{f['netnew_domains_absent_from_baseline']:,}",
        "CANDIDATES": f"{f['candidate_pool']:,}",
        "HARVESTED": f"{f['harvested_this_round']:,}",
        "CAPTUREBACKED": f"{f['capture_backed_total']:,}",
        "BASELINE": BASELINE,
        "ROUND": CURRENT_ROUND_LABEL,
        # Four decimals, because that is the precision the reviewer reports back in
        # and a rounded total reads to him as a different number than the one he
        # computed with his own calculator.
        "EE": f"{ee_total:,.4f}",
        "EEBASELINE": f"{f['ee_baseline']:,.4f}",
        "EEGROWTH": f"{f['ee_netnew_growth_pct']:.4f}%",
        "EEMEAN": f"{f['ee_mean_weight']:.4f}",
        "EE_SOURCE_TABLE": ee_source_table(f),
        "ADMITTED_THIS_ROUND": admitted_this_round(f),
        "CORROBORATION": corroboration_sentence(f),
        "ADMISSIBLE": admissibility_sentence(f),
        "MASTERTYPES": ", ".join(f"`{t}`" for t in sorted(MASTER_TYPES) if t != "prior_reused"),
        "PER_YEAR_TABLE": per_year_table(f),
        "SOURCE_TABLE": source_table(f),
        "COMPLETENESS_TABLE": _section(md, "Completeness"),
        "CDX_TABLE": cdx_table(),
        "CDX_FAILURES": cdx_failures(),
        "DATASETS_SEARCHED": datasets_searched(),
        **ingest_counters(),
        "CUMULATIVE": cumulative(f),
        "CUMULATIVE_SENTENCE": cumulative_sentence(f),
        "MERGE_RECONCILIATION": merge_reconciliation(),
        "CROSS_SOURCE_AGREEMENT": cross_source_agreement(),
        "REPRODUCTION_RESULT": reproduction_result(),
        "ROUTES_TABLE": routes_table(f),
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


# The routes section 2 describes, in the order a reader should meet them. Only the
# prose lives here; every figure beside it is read from the store, because the section
# opens by claiming no number in this report is typed and a hand-copied pair count in
# the summary table would make that false the first time a collector banked anything.
# It did: round 5's four were written on 2026-08-17 and were stale within a day.
#
# RESET AT THE START OF EVERY ROUND, which is why it is empty now. Carrying the
# previous round's routes forward is not a small error: each row would keep its own
# heading while `by_source` quietly filled it with THIS round's pairs for a source
# that is no longer what the round is about.
ROUTES: tuple[tuple[str, str, str], ...] = (
    (
        "ia_cdx_bulk",
        "the two archive engines, a bracketed-gap population and the candidate pool",
        "the Wayback capture timestamp, per domain and year",
    ),
    (
        "rdap_snapshot",
        "the RDAP sweep over the candidate pool",
        "the registry's own creation date, which dates that year and no other",
    ),
)


def routes_table(f: dict) -> str:
    """Section 2's summary of where the round came from, figures read from the store."""
    if not ROUTES:
        # Deliberately a token, so `fill` refuses the document rather than shipping a
        # report whose central section is a blank table. `ark.baseline` names the round;
        # this names what the round was made of, and only a human can write that.
        return "[ROUTES_NOT_NAMED_FOR_THIS_ROUND]"
    by_source = {row["source"]: row for row in f["by_source"]}
    lines = [
        "| Route | What dates a year | Net-new pairs |",
        "|---|---|--:|",
    ]
    for key, what, dates in ROUTES:
        row = by_source.get(key)
        pairs = f"{row['pairs']:,}" if row else "_not in this round_"
        lines.append(f"| {what} | {dates} | {pairs} |")
    return "\n".join(lines)


def reproduction_result() -> str:
    """What the archive's own reproduction actually did, when it was last run.

    Read from a file rather than asserted in prose, because a report that claims
    "verified" is worth nothing next to one that names the run. `just ship` writes
    it; if it is absent the report says so instead of implying a pass.
    """
    path = Path(__file__).resolve().parents[1] / "docs/reproduction.txt"
    if not path.is_file():
        return (
            "_The reproduction has not been run against this build. "
            "`bash verify.sh` inside the archive is the first check._"
        )
    return path.read_text(encoding="utf-8").strip()


# The source whose credibility this round's section 2 rests on, and the sources whose
# independent agreement with it is worth quoting. Set per round; empty means the round
# has no such claim to make and the token is simply unused.
CROSS_SOURCE_CHECK: tuple[str, tuple[str, ...]] | None = None


def cross_source_agreement() -> str:
    """On how many (domain, year) pairs a bulk source and our own querying agree.

    Generated rather than typed, because it is the sentence that makes a third-party
    file believable and it moves every time an engine dates another pair. Round 5's
    hand-copied 138,979 was already 219 stale a day after it was measured.
    """
    if CROSS_SOURCE_CHECK is None:
        return "[CROSS_SOURCE_CHECK_NOT_SET_FOR_THIS_ROUND]"
    subject, against = CROSS_SOURCE_CHECK
    placeholders = ", ".join("?" for _ in against)
    conn = connect_read_only_patiently(Path(__file__).resolve().parents[1] / "data/ark.duckdb")
    try:
        n = conn.execute(
            f"""
            SELECT count(*) FROM (
              SELECT DISTINCT d.domain, d.evidence_year FROM evidence d
              JOIN source sd ON sd.source_id = d.source_id AND sd.name = ?
              WHERE EXISTS (
                SELECT 1 FROM evidence o
                JOIN source so ON so.source_id = o.source_id
                              AND so.name IN ({placeholders})
                WHERE o.domain = d.domain AND o.evidence_year = d.evidence_year))
            """,
            [subject, *against],
        ).fetchone()[0]
    finally:
        conn.close()
    return f"{n:,}"


def cumulative(f: dict) -> str:
    """Everything this project has contributed, against the corpus as it now stands.

    Not readable off the store: a round the reviewer has merged stops being net-new
    the moment he merges it. So the shipped rounds live in
    `ark.baseline.SUBMITTED_ROUNDS` and only the arithmetic happens here.

    The denominator is the CURRENT baseline, on Ivo's instruction of 2026-08-17,
    because that is the comparison he is scored on: what this project has added,
    measured against the corpus as it is today.
    """
    # One line, not a table. The per-round figures are the reviewer's own accepted
    # numbers, so he already holds them; what he cannot read off his own records is
    # the cumulative share, and that is the figure his competition score uses.
    total_records = 0
    total_ee = Decimal(0)
    per_round = []
    for label, _date, records, ee, _against in SUBMITTED_ROUNDS:
        total_records += records
        total_ee += ee
        per_round.append(f"round {label} {records:,} / {ee:,.0f}")

    shipped = len(SUBMITTED_ROUNDS)
    total_records += f["netnew_pairs"]
    total_ee += Decimal(str(f["ee_netnew"]))
    per_round.append(
        f"**{CURRENT_ROUND_LABEL}, this one {f['netnew_pairs']:,} / {f['ee_netnew']:,.0f}**"
    )

    pct = 100 * total_ee / Decimal(str(f["ee_baseline"]))
    return (
        f"**Cumulative.** Across the {shipped} rounds shipped so far plus this one, this project "
        f"has added {total_records:,} domain-year records worth {total_ee:,.4f} "
        f"equivalent-English, **{pct:.4f}%** of the {f['ee_baseline']:,.4f} the corpus holds "
        f"today. Records / equivalent-English by round, each at the figure you ACCEPTED rather "
        f"than the one submitted: {'; '.join(per_round)}."
    )


def merge_reconciliation() -> str:
    """The D3 merge audit, read from the file the packaging step produced.

    Read rather than recomputed. `merge_against_baseline.py` scores every annual file
    with the reviewer's own calculator, which takes minutes, and a second derivation
    here would be a second thing to keep in step with the first. If the audit is
    absent the report says so instead of implying the merge was run.
    """
    merge_dir = Path(__file__).resolve().parents[1] / "output/merge"
    audits = sorted(merge_dir.glob("merge_audit_ark*.json"))
    if not audits:
        return (
            "_The merge has not been run against this build. "
            "`uv run python source/scripts/merge_against_baseline.py` produces it._"
        )
    audit = json.loads(audits[-1].read_text(encoding="utf-8"))
    t = audit["totals"]
    checks = audit.get("reconciliation", [])
    passed = sum(1 for c in checks if c.get("passed"))
    rows = [
        "| | records | equivalent-English |",
        "|---|--:|--:|",
        f"| baseline `{t['baseline_marker']}` | {int(t['baseline_records']):,} | "
        f"{Decimal(t['baseline_equivalent_english_total']):,.4f} |",
        f"| submitted | {int(t['submitted_records']):,} | |",
        f"| already in the baseline | {int(t['already_in_baseline_records']):,} | |",
        f"| **accepted increment** | **{int(t['accepted_new_records']):,}** | "
        f"**{Decimal(t['equivalent_english_increment']):,.4f}** |",
        f"| post-merge total | {int(t['post_merge_records']):,} | "
        f"{Decimal(t['post_merge_equivalent_english_total']):,.4f} |",
    ]
    return "\n".join(
        [
            "**Computed here, not described.** `merge_against_baseline.py` unions these",
            "additions into the current baseline, deduplicated on the lowercased line within",
            "each year, and scores every file with your own calculator. Per-year form in",
            "`audit/merge_stats_ark_*.csv`, in your column names so the two audits diff directly.",
            "",
            *rows,
            "",
            f"**{passed} of {len(checks)} reconciliation checks pass**, all arithmetic identities,",
            "so a failure would be a defect rather than a finding: per year that",
            "`baseline_unique + accepted_new == merged_unique` and",
            "`already_in_baseline + accepted_new == submitted_unique`, that the per-year",
            "increments sum to the headline figure, and that a freshly measured baseline",
            "reproduces the totals this round was measured against. Each is listed with its",
            "verdict in `audit/merge_audit_ark_*.json`.",
        ]
    )


def cumulative_sentence(f: dict) -> str:
    """The same arithmetic as `cumulative`, as one sentence for the email.

    Two derivations of one figure would drift, so this reuses the totals rather than
    recomputing them, and the email gets no table: the reviewer asked for the
    cumulative number, not for a second copy of the report.
    """
    records = sum(r[2] for r in SUBMITTED_ROUNDS) + f["netnew_pairs"]
    ee = sum((r[3] for r in SUBMITTED_ROUNDS), Decimal(0)) + Decimal(str(f["ee_netnew"]))
    pct = 100 * ee / Decimal(str(f["ee_baseline"]))
    return (
        f"Cumulative across my rounds, which you asked me to track: {records:,} records and "
        f"{ee:,.4f} equivalent-English, which is {pct:.4f}% of the {f['ee_baseline']:,.4f} the "
        "corpus holds today. Each earlier round is counted at the figure you accepted rather "
        "than the one I submitted, so records of mine that had already reached the baseline by "
        "another route are not counted twice."
    )


def ingest_counters() -> dict:
    """Pipeline-wide normalisation and drop statistics, summed from `run_metrics`.

    Every `ark ingest` call records its own counters, so summing them is the only
    figure that describes the whole pipeline rather than one source. The reviewer
    asks for normalisation, salvage and dropped-domain statistics by name, and a
    hand-typed number here would be the one figure in the report nothing checks.
    """
    from ark.db import DEFAULT_DB_PATH, connect_read_only_patiently

    conn = connect_read_only_patiently(DEFAULT_DB_PATH)
    rows = conn.execute("SELECT metrics_json FROM run_metrics WHERE command = 'ingest'").fetchall()
    total: dict[str, int] = {}
    for (blob,) in rows:
        try:
            parsed = json.loads(blob)
        except (ValueError, TypeError):
            continue
        for key, value in parsed.items():
            if isinstance(value, int):
                total[key] = total.get(key, 0) + value
    # `out_of_window` is the bulk parsers' counter and `outside_window` the RDAP
    # one; they mean the same thing and are reported as one line.
    outside = total.get("out_of_window", 0) + total.get("outside_window", 0)
    return {
        "INGESTRUNS": f"{len(rows):,}",
        "RAWLINES": f"{total.get('lines', 0) + total.get('journal_lines', 0):,}",
        "STAGEDRECORDS": f"{total.get('records', 0):,}",
        "CORRECTED": f"{total.get('corrected', 0):,}",
        "REJECTED": f"{total.get('rejected', 0):,}",
        "OUTOFWINDOW": f"{outside:,}",
    }


def datasets_searched() -> str:
    """The register of families searched, read from `sources.md` rather than retyped.

    The reviewer asks for every external dataset and repository searched. That list
    only stays true if it is derived from the register itself: a hand-written copy
    omits whatever was added after it was written, and the omission is invisible.

    The register has two halves and they are counted separately, because a prose
    sentence that said "roughly sixty" sat directly above a generated "26" in the
    first draft of this section. Developed sources get a `## ` heading each;
    families evaluated and rejected are one table row each under a single heading.
    Both are searches, and the second half is much the larger.
    """
    path = Path(__file__).resolve().parents[1] / "docs" / "sources.md"
    if not path.is_file():
        return "_`sources.md` not found beside this report._"

    text = path.read_text(encoding="utf-8")

    # Headings at this level that are prose about the file rather than a source.
    skip = {
        "Summary",
        "Source names that are not separate sources",
        "Evaluated and rejected",
        "Measured, and each blocked on something other than work",
    }
    developed = [
        line[3:].strip()
        for line in text.splitlines()
        if line.startswith("## ") and line[3:].strip() not in skip
    ]

    rejected = 0
    if "## Evaluated and rejected" in text:
        section = text.split("## Evaluated and rejected", 1)[1].split("\n## ", 1)[0]
        rejected = sum(
            1
            for line in section.splitlines()
            if line.startswith("|")
            and not line.startswith("|--")
            and not line.lower().startswith("| source")
        )

    if not developed and not rejected:
        return "_No families recorded._"

    # Counts only, and the names deliberately omitted. The reviewer's requirement is
    # that every dataset searched be documented, not that it be documented twice: the
    # register itself ships beside the report and is the place to read it. Naming all
    # 26 developed families inline cost most of a page and told him nothing the file
    # does not, which is why the list was cut on Ivo's instruction (2026-08-17).
    return (
        f"**{len(developed) + rejected} source families have been searched and recorded**, "
        f"{len(developed)} developed far enough to earn their own section and {rejected} "
        "evaluated and closed, each with the measurement that closed it, so negative results "
        "stay visible and the same ground is not broken twice. `sources.md` ships beside this "
        "report and names every one, with its acquisition route, date semantics and yield."
    )


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


# The reviewer asks for the retrieval strategy, the errors and the domains added,
# not a census of every collector prefix we happened to name. Eighteen rows is most
# of a page in the Word file, so the long tail is folded into one row here and the
# full per-prefix breakdown ships in `audit/`. TOP_PREFIXES is the cut point.
TOP_PREFIXES = 6


def cdx_table() -> str:
    """The collector table, with everything below the top prefixes folded into one row."""
    from cdx_execution_notes import NOTES_MARKER

    table = _cdx_notes(markdown_form=True).split(NOTES_MARKER)[0].rstrip()
    lines = table.split("\n")
    head, rows = lines[:2], [ln for ln in lines[2:] if ln.startswith("|")]
    if not rows:
        return table
    total = rows[-1] if rows[-1].lower().startswith("| **all**") else None
    body = rows[:-1] if total else rows

    def cell(row: str, index: int) -> int:
        raw = row.split("|")[index].strip().replace(",", "").replace("*", "")
        return int(raw) if raw.isdigit() else 0

    kept, folded = body[:TOP_PREFIXES], body[TOP_PREFIXES:]
    if folded:
        # Sum the count columns; the two rate columns are recomputed from them so a
        # folded row cannot show an average of percentages, which is not a percentage.
        journals = sum(cell(r, 2) for r in folded)
        queries = sum(cell(r, 3) for r in folded)
        answered = sum(cell(r, 4) for r in folded)
        domains = sum(cell(r, 7) for r in folded)
        pairs = sum(cell(r, 8) for r in folded)
        rate = f"{100.0 * answered / queries:.1f}%" if queries else "n/a"
        kept.append(
            f"| *{len(folded)} further prefixes* | {journals:,} | {queries:,} | "
            f"{answered:,} | {rate} | | {domains:,} | {pairs:,} |"
        )
    return "\n".join(head + kept + ([total] if total else []))


def cdx_failures() -> str:
    from cdx_execution_notes import NOTES_MARKER

    body = _cdx_notes(markdown_form=True)
    _, marker, tail = body.partition(NOTES_MARKER)
    return f"{marker}{tail}" if tail else body


# The template marks each section whose prose a human must write for this round as
# `<!-- ROUND [ROUND]: ... -->`. An unwritten one is exactly the failure the token
# mechanism exists to prevent, and it slipped through: on 2026-08-18 `docs/report.md`
# held four of them, `--check` said "would fill cleanly", and `just ship` would have
# packaged a report whose sections 2, 4, 5 and 6 were empty. Sections 5 and 6 are the
# ones the template itself calls the ones he reads most closely.
UNWRITTEN_SECTION = re.compile(r"<!--\s*ROUND\b", re.I)

# A stub can also be satisfied from a tracked file rather than by hand, which is why
# this exists: `private/email-draft.md` is REGENERATED from its template, so prose typed
# straight into the draft is destroyed by the next fill. That happened, and the round's
# email had to be rewritten from a copy kept elsewhere. `docs/email-sections.md` is
# tracked (and export-ignored, so it never reaches the reviewer), holding one `## name`
# heading per section. The first stub in the template takes the first section, the second
# the second, in order, so the template keeps owning what sections exist.
EMAIL_SECTIONS = Path("docs/email-sections.md")
_STUB_RE = re.compile(r"<!--\s*ROUND\b.*?-->", re.S | re.I)


def written_sections(path: Path | None = None) -> list[str]:
    """Prose blocks under each `## ` heading, in file order. Empty if absent.

    `path=None` resolves `EMAIL_SECTIONS` at call time rather than binding it as a
    default at import, so a test can point this at a fixture. `ark.approvals` carries the
    same note for the same reason, and writing it the other way here cost two red tests.
    """
    path = Path(path) if path is not None else EMAIL_SECTIONS
    if not path.is_file():
        return []
    blocks, current = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if current is not None:
                blocks.append("\n".join(current).strip())
            current = []
        elif current is not None:
            current.append(line)
    if current is not None:
        blocks.append("\n".join(current).strip())
    return [b for b in blocks if b]


def fill(
    template: Path, target: Path, subs: dict[str, str], check: bool, stubs_fatal: bool
) -> list[str]:
    text = template.read_text()
    for token, value in subs.items():
        text = text.replace(f"[{token}]", value)
    # Satisfy stubs from the tracked sections file, in order, before counting them.
    sections = written_sections()
    if sections:
        for block in sections:
            text, n = _STUB_RE.subn(lambda _m, b=block: b, text, count=1)
            if not n:
                break
    remaining = sorted(set(re.findall(r"\[([A-Z_0-9]{2,})\]", text)))
    # Reported as a pseudo-token so it travels the same path as a real one: `--check`
    # lists it, `main` refuses, and the packaging script stops. One mechanism, not two,
    # because the second would be the one nobody wired up.
    stubs = len(UNWRITTEN_SECTION.findall(text))
    if stubs and stubs_fatal:
        remaining = sorted({*remaining, f"UNWRITTEN_ROUND_SECTIONS_x{stubs}"})
    # A non-fatal stub is still worth saying out loud, or the draft looks finished.
    if stubs and not stubs_fatal:
        print(f"{target}: {stubs} round section(s) still to write by hand")
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
    for template, target, stubs_fatal in DOCUMENTS:
        # `private/` is git-ignored, so a fresh clone has no email template. That
        # must not fail the report build, which is the part that ships.
        if not template.exists():
            print(f"{template}: absent, skipping")
            continue
        remaining = fill(template, target, subs, args.check, stubs_fatal)
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
