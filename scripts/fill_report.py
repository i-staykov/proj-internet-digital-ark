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
from report_figures import BASELINE, figures  # noqa: E402

from ark.baseline import (  # noqa: E402
    CURRENT_ROUND_LABEL,
    REVIEWER_BASELINE_PAIRS,
    SUBMITTED_ROUNDS,
)
from ark.evidence_types import MASTER_TYPES  # noqa: E402

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


def per_year_table(f: dict) -> str:
    """Volume and equivalent-English per year, read from the shipped merge audit.

    **Read from the audit rather than from the store, because the two disagree by 12
    records and the report used to print both.** The store counts a canonicalised
    (domain, year); the audit counts what survives export into the annual files and is
    then scored by the reviewer's own calculator, so a name his validator refuses is in
    the first and not the second. His figure is the one that matters and it is the one
    the headline quotes, so the table now comes from the same file: the columns satisfy
    `baseline_unique + accepted_new == merged_unique` per year, which he can check
    against `audit/merge_stats_ark_*.csv` line by line.
    """
    merge_dir = Path(__file__).resolve().parents[1] / "output/merge"
    newest = newest_audit(merge_dir)
    if newest is None:
        return "_No merge audit in this build; `merge_against_baseline.py` produces it._"
    audit = json.loads(newest.read_text(encoding="utf-8"))
    lines = [
        f"| Year | {BASELINE} | Additions | Merged | Equivalent-English added |",
        "|---|--:|--:|--:|--:|",
    ]
    for row in audit["years"]:
        lines.append(
            f"| {row['year']} | {row['baseline_unique']:,} | {row['accepted_new']:,} | "
            f"{row['merged_unique']:,} | {Decimal(row['equivalent_english_increment']):,.4f} |"
        )
    t = audit["totals"]
    lines.append(
        f"| **Total** | **{int(t['baseline_records']):,}** | "
        f"**{int(t['accepted_new_records']):,}** | **{int(t['post_merge_records']):,}** | "
        f"**{Decimal(t['equivalent_english_increment']):,.4f}** |"
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


# Sources admitted in THIS round, with the one-line ground each was admitted on and the
# receipt a reviewer can open. Everything not listed here was approved in an earlier round
# and is unchanged, so the report does not re-argue it. Ivo, 2026-08-26: the additions are
# what has to be verifiable, and nothing else earns space.
NEW_THIS_ROUND = {
    "ripe_dbase_1999": (
        "the file's own generation stamp, `# 990804 00:07:01` on line 2",
        "ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz",
    ),
    "ripe_dbase_changed": (
        "the date on each object's own `changed:` transaction line",
        "same file, `*ch:` attribute",
    ),
    "us_domain_delegated": (
        "the edition's tar-preserved mtime, or its capture stamp",
        "archive.org/details/2015.04.ftp.isc.org and www.isi.edu/in-notes/",
    ),
    "squidguard_2001_blacklist": (
        "the list's own `compiled in ... on 2001.12.18` header, or the diff's filename date",
        "archive.debian.org/.../squidguard_1.2.0.orig.tar.gz",
    ),
    "namewinner_expiring": (
        "the per-row date `25-OCT-01`, on every line",
        "web.archive.org/web/20011026120205id_/namewinner.com/whole_list.php?del=tab",
    ),
    "can_domain_registry_notices": (
        "the registry's own `Date-Approved:` field in its public approval notice",
        "archive.org/download/usenet-can/can.domain.mbox.zip",
    ),
    "cctld_register_listing_inbody": (
        "the register page's own machine-written timestamp, or the row's due date",
        "twnic.net.tw/DN/fz1.shtml and idnic.net.id/Info/RekapBelumBayar.html",
    ),
    "dartmouth_bfs_seed": (
        "field 2 of each CDX row, a 14-digit capture timestamp",
        "archive.org, Dartmouth_10KwebURLs_GWB BFS level 0",
    ),
    "iedr_register": (
        "the register page's own `updated automatically at ... 2001` line",
        "IE Domain Registry register, archived",
    ),
    "internic_zone": (
        "the SOA serial inside the zone payload, `1997041800`",
        "InterNIC 1997 zone files, nic.mil mirror",
    ),
    "ukwa_geoindex": (
        "the 14-digit capture timestamp on each row",
        "webarchive.org.uk/datasets/ukwa.ds.2/geo/",
    ),
}


def new_sources_table(f: dict) -> str:
    """The additions of this round, with grounds and receipts, so they can be checked."""
    by_name = {row["source"]: row for row in f["by_source"]}
    lines = [
        "| Source | Evidence type | What dates one item | Receipt | Pairs | EE |",
        "|---|---|---|---|--:|--:|",
    ]
    shown = 0
    for name, (ground, receipt) in NEW_THIS_ROUND.items():
        row = by_name.get(name)
        if row is None:
            continue
        shown += 1
        lines.append(
            f"| `{name}` | `{row['evidence_type']}` | {ground} | {receipt} | "
            f"{row['pairs']:,} | {row['ee']:,.1f} |"
        )
    if not shown:
        return "No source was admitted for the first time in this round."
    return "\n".join(lines)


def newest_audit(merge_dir: Path) -> Path | None:
    """The most recently WRITTEN merge audit, or None.

    **By modification time, never by name, and there is exactly one of these because two
    call sites disagreeing is how the report contradicted itself twice on 2026-08-26.**
    Sorting alphabetically picks `merge_audit_ark_20260824c.json` over a freshly written
    `merge_audit_ark.json`, since the tagged name sorts last. That put a 488,722 increment
    beside a 5.3344% growth rate in section 1, and after that was fixed in one place it did
    the same again in section 8's merge table.
    """
    audits = list(merge_dir.glob("merge_audit_ark*.json"))
    if not audits:
        return None
    return max(audits, key=lambda path: path.stat().st_mtime)


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
    newest = newest_audit(merge_dir)
    if newest is None:
        return None
    return json.loads(newest.read_text(encoding="utf-8"))["totals"]


def substitutions(f: dict) -> dict[str, str]:
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
        "BASELINE": BASELINE,
        "ROUND": CURRENT_ROUND_LABEL,
        # Four decimals, because that is the precision the reviewer reports back in
        # and a rounded total reads to him as a different number than the one he
        # computed with his own calculator.
        "EE": f"{ee_total:,.4f}",
        "EEBASELINE": f"{f['ee_baseline']:,.4f}",
        "EEGROWTH": f"{f['ee_netnew_growth_pct']:.4f}%",
        "NEW_SOURCES_TABLE": new_sources_table(f),
        "DECISIONS": str(len(NEW_THIS_ROUND.keys() & {r["source"] for r in f["by_source"]})),
        "MASTERTYPES": ", ".join(f"`{t}`" for t in sorted(MASTER_TYPES) if t != "prior_reused"),
        "PER_YEAR_TABLE": per_year_table(f),
        "DATASETS_SEARCHED": datasets_searched(),
        "CUMULATIVE": cumulative(f),
        "CUMULATIVE_SENTENCE": cumulative_sentence(f),
        "MERGE_RECONCILIATION": merge_reconciliation(),
        "REPRODUCTION_RESULT": reproduction_result(),
        "ROUTES_TABLE": routes_table(f),
    }
    # The REVIEWER'S raw record count, not the store's. These differ by 1.6 million,
    # because the store canonicalises to registrable domains and he counts lines, and
    # a sentence that set his count for one release beside our count for the next
    # would read as a shrinking baseline. Quote one counting unit or the other, never
    # one of each.
    subs["BASELINEPAIRS"] = f"{REVIEWER_BASELINE_PAIRS:,}"

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
        "the RDAP sweep over generated sibling names and over `.uk` we already hold",
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


def cumulative(f: dict) -> str:
    """The competition score, which is the sum of the percentages he awarded.

    Not a ratio and not derivable from the store. His update log of 2026-08-18 defines
    it as "the direct arithmetic sum of all official percentage increases awarded", each
    taken against the baseline of the day that round arrived. So the per-round figures
    are quoted from his feedback in `ark.baseline.SUBMITTED_ROUNDS` and only the addition
    happens here. Round 1 is held out of the sum: it was awarded on records, before the
    equivalent-English metric existed, so adding it would mix two units.
    """
    scored = [r for r in SUBMITTED_ROUNDS if r[5] is not None]
    this = Decimal(str(f["ee_netnew_growth_pct"]))
    total = sum((r[5] for r in scored), Decimal(0)) + this
    awarded = ", ".join(f"{r[5]}%" for r in scored)
    unscored = [r for r in SUBMITTED_ROUNDS if r[5] is None]
    return (
        f"**Cumulative.** Summing the increases you have awarded, which is how the update log "
        f"of 2026-08-18 defines the score: {awarded} and this round's {this:.4f}% give "
        f"**{total:.4f}%**, with round {unscored[0][0]}'s {unscored[0][2]:,} records held out "
        f"because it was awarded at 17.38% on records before the equivalent-English metric "
        f"existed."
    )


def merge_reconciliation() -> str:
    """The D3 merge audit, read from the file the packaging step produced.

    Read rather than recomputed. `merge_against_baseline.py` scores every annual file
    with the reviewer's own calculator, which takes minutes, and a second derivation
    here would be a second thing to keep in step with the first. If the audit is
    absent the report says so instead of implying the merge was run.
    """
    merge_dir = Path(__file__).resolve().parents[1] / "output/merge"
    newest = newest_audit(merge_dir)
    if newest is None:
        return (
            "_The merge has not been run against this build. "
            "`uv run python source/scripts/merge_against_baseline.py` produces it._"
        )
    audit = json.loads(newest.read_text(encoding="utf-8"))
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
            "`merge_against_baseline.py` unions these additions into the current baseline,",
            "deduplicated on the lowercased line within each year, and scores every file with your",
            "own calculator. Per-year form in `audit/merge_stats_ark_*.csv`, in your column names",
            "so the two audits diff directly.",
            "",
            *rows,
            "",
            f"**{passed} of {len(checks)} reconciliation checks pass.** All are arithmetic",
            "identities, so a failure would be a defect rather than a finding: per year that",
            "`baseline_unique + accepted_new == merged_unique`, that the per-year increments sum",
            "to the headline, and that a freshly measured baseline reproduces the totals this",
            "round was measured against. Each is listed with its verdict in",
            "`audit/merge_audit_ark_*.json`.",
        ]
    )


def cumulative_sentence(f: dict) -> str:
    """The same sum as `cumulative`, as one sentence for the email."""
    scored = [r for r in SUBMITTED_ROUNDS if r[5] is not None]
    this = Decimal(str(f["ee_netnew_growth_pct"]))
    total = sum((r[5] for r in scored), Decimal(0)) + this
    return (
        f"Cumulative, as the direct sum of the percentages you have awarded: "
        f"{' + '.join(str(r[5]) for r in scored)} + {this:.4f} = {total:.4f}%. Round 1 is "
        "not in that sum because it was awarded on records, at 17.38%, before the "
        "equivalent-English metric existed."
    )


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


# The reviewer asks for the retrieval strategy, the errors and the domains added,
# not a census of every collector prefix we happened to name. Eighteen rows is most
# of a page in the Word file, so the long tail is folded into one row here and the
# full per-prefix breakdown ships in `audit/`. TOP_PREFIXES is the cut point.
TOP_PREFIXES = 3


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
