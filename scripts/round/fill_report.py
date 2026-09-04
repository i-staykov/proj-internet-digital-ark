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

    uv run python scripts/round/fill_report.py --check     # report which tokens remain
    uv run python scripts/round/fill_report.py             # write filled copies

`docs/*.template.md` are the sources; `docs/*.md` are generated. Edit the
templates, never the filled copies, or the next refresh discards the edit.
"""

import argparse
import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

from ark.db import connect_read_only_patiently

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_figures import BASELINE, figures  # noqa: E402

from ark.baseline import (  # noqa: E402
    CURRENT_BASELINE_RELEASED,
    CURRENT_ROUND_LABEL,
    REVIEWER_BASELINE_PAIRS,
    SUBMITTED_ROUNDS,
)
from ark.english_share import english_weights  # noqa: E402
from ark.evidence_types import MASTER_TYPES  # noqa: E402
from ark.export import NETNEW_DIR  # noqa: E402
from ark.figures import cumulative as score_total  # noqa: E402
from ark.figures import now_in_his_clock, score, scored_under_rule, t_days  # noqa: E402

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

    **Read from the audit rather than from the store, because the two disagree by a few
    records and the report used to print both.** The store counts a canonicalised
    (domain, year); the audit counts what survives export into the annual files and is
    then scored by the reviewer's own calculator, so a name his validator refuses is in
    the first and not the second. His figure is the one that matters and it is the one
    the headline quotes, so the table comes from the same file: per year,
    `baseline_unique + registrables + hostnames == merged_unique`, which he can check
    against `audit/merge_stats_ark_*.csv` line by line.
    """
    merge_dir = Path(__file__).resolve().parents[2] / "output/merge"
    newest = newest_audit(merge_dir)
    if newest is None:
        return "_No merge audit in this build; `merge_against_baseline.py` produces it._"
    audit = json.loads(newest.read_text(encoding="utf-8"))
    # Four columns, not six: the baseline and post-merge columns are one subtraction
    # apart and each was wrapping to three lines in his Word rendering, which cost more
    # of his attention than it bought. Both remain in `audit/merge_stats_ark_*.csv`.
    lines = [
        "| Year | Registrables | Hostnames | Equivalent-English added |",
        "|------|-----------:|-----------:|--------------:|",
    ]
    for row in audit["years"]:
        reg = row.get("submitted_registrable", row["accepted_new"])
        host = row.get("submitted_hostnames", 0)
        lines.append(
            f"| {row['year']} | {reg:,} | {host:,} | "
            f"{Decimal(row['equivalent_english_increment']):,.4f} |"
        )
    t = audit["totals"]
    reg = int(t.get("submitted_registrable_records", t["accepted_new_records"]))
    host = int(t.get("submitted_hostname_records", 0))
    lines.append(
        f"| **Total** | **{reg:,}** | **{host:,}** | "
        f"**{Decimal(t['equivalent_english_increment']):,.4f}** |"
    )
    return "\n".join(lines)


# One line per source saying what dates a record and how the artifact was obtained, for
# the attribution table in section 2. The FIGURES beside them are read from the store and
# the shipped files; only these two phrases are typed, and a source missing here still
# appears, described by its evidence class, so the table can never silently drop a row.
# Hostname sources are keyed by acquisition method because both live under one source row.
GROUNDS: dict[str, tuple[str, str]] = {
    "nypw_timemap_hostgrain": (
        "NYPW TimeMaps (IA, CC BY 4.0), 34 parts held since round 6, re-read at hostname grain",
        "the row's own 14-digit capture timestamp",
    ),
    "ia_cdx_domain_sweep": (
        "IA CDX `matchType=domain` sweeps of `.uk` suffixes and subdomain platforms, raw journals",
        "the row's own 14-digit capture timestamp",
    ),
    "early_web_hostgrain": (
        "IA Early Web CDX index, 224 parts held since July, re-read at hostname grain",
        "the row's own 14-digit capture timestamp",
    ),
    "usfedgov_extract_hostgrain": (
        "IA USFEDGOV-EXTRACT 1996-2001 merged CDX indexes, one capture per host, bulk download",
        "the row's own 14-digit capture timestamp",
    ),
    "usenet_body_url": (
        "Every non-alt Usenet hierarchy of the archive.org collection, 224 GB read whole, "
        "hosts taken only from explicit http, https and ftp URLs in the post BODY",
        "the post's own machine-written `Date:` header",
    ),
    "isc_survey_host_list": (
        "ISC Internet Domain Survey per-TLD host files (9607, 9701, 9707), read at hostname grain",
        "the survey's own YYMM edition code in the artifact's path",
    ),
    "ripe_snapshot_nserver": (
        "RIPE database snapshot of 1999-08-04 (FUNET mirror), nameservers of its domain objects",
        "the dump's own generation stamp on line 2 of the payload",
    ),
    "ripe_changed_nserver": (
        "RIPE 2004 split edition, each object's nameserver set at its latest `changed:` date",
        "the object's latest machine-stamped `changed:` line",
    ),
    "nypw_timemaps": (
        "NYPW TimeMaps, 34 parts, reopened after a 14 EE closure on the 1996 folder",
        "the row's own 14-digit capture timestamp",
    ),
    "nypw_timemaps_nonok": (
        "same files, rows with a non-200 status the parser used to discard",
        "the row's own 14-digit capture timestamp",
    ),
    "ia_cdx_bulk": (
        "IA CDX per-domain queries over bracketed gaps and the candidate pool",
        "the capture timestamp of a URL on that host",
    ),
    "usenet_address": (
        "Usenet archives (IA), sender and body addresses",
        "the post's `Date:` header, corroborated by a second source",
    ),
    "usenet_announce": (
        "Usenet site announcements (IA)",
        "the post's `Date:` header, corroborated by a second source",
    ),
    "usenet_bare": (
        "Usenet archives (IA), bare hostnames in bodies",
        "the post's `Date:` header, corroborated by a second source",
    ),
    "chastity_list_blacklist": (
        "Chastity filter blacklist tarball, 2001",
        "tar member headers `Dec 14 2001` and dated diff filenames",
    ),
    "mynic_my_change_report": (
        "MYNIC `.my` fortnightly change reports (IA)",
        "the per-day heading over each `New`/`Delete` entry",
    ),
    "coza_deletion_listing": (
        "CO.ZA registry deletion shortlists (IA)",
        "the capture stamp on a registry page naming live names",
    ),
    "jeb_bush_gubernatorial_email": (
        "Florida governor's office e-mail export",
        "the mail client's own `Sent:` line",
    ),
    "early_bulk_whois_snapshot": (
        "early bulk whois transcriptions (Berkman)",
        "the registry creation date in the record, that year only",
    ),
    "cctld_register_listing_capture": (
        "ccTLD register listings `.mt`, `.sa` and others (IA)",
        "the capture stamp on the registry's own register page",
    ),
    "junkfilter_dated_blocklist": (
        "junkfilter blocklist releases 1997-2001",
        "`Last-Modified`, in-body `$Id` and tar member stamps agreeing",
    ),
    "granitecanyon_zone_rejects": (
        "Granite Canyon public DNS rejected-zone lists (IA)",
        "the list's own generation stamp, e.g. `7-May-2001 22:11 GMT`",
    ),
    "urlmerchant_inventory": (
        "URLMerchant domain broker inventory (IA)",
        "the page's own `META UPDATED` generator stamp",
    ),
    "fac_single_audit": (
        "Federal Audit Clearinghouse single-audit data",
        "the row's `AUDITEEDATESIGNED`, corroborated by a second source",
    ),
    "ripe_dbase_split_2004": (
        "RIPE database split dump (ftp.funet.fi)",
        "the object's own `changed:` line, that year only",
    ),
    "rdap_snapshot": (
        "registry RDAP over generated sibling names",
        "the registry's creation date, that year only",
    ),
    "rtfm_faq": (
        "MIT rtfm FAQ archive",
        "the FAQ's own `Last-modified:` line, corroborated by a second source",
    ),
    "usenet_whois_paste": (
        "whois output pasted into Usenet posts",
        "the registry's `Record created on` line inside the paste",
    ),
}

# What the table says about a source nobody described above, by evidence class.
CLASS_GROUNDS = {
    "cdx_timestamp": "a Wayback capture timestamp",
    "dated_directory": "the dated artifact's own stamp",
    "artifact_listing": "the artifact's own machine-written stamp",
    "whois_creation": "the registry's creation date, that year only",
    "link_source": "the crawl date on the link record",
}

# Rows below this share of the increment collapse into one line; the full per-source
# figures ship in `audit/source_contribution.csv` and the collapsed line says so.
ATTRIBUTION_FLOOR_EE = Decimal("1000")


def hostname_breakdown() -> tuple[dict[str, tuple[int, Decimal]], Decimal]:
    """(records, EE) per acquisition method over the SHIPPED hostname files, and the
    share of them that are `www.` forms below a registrable (`www.<parent>` itself is
    refused at ingest, so what remains is `www.sub.parent`).

    Joined against the shipped manifest rather than the store, so the table describes
    the files in the archive: the store holds hostname rows the export filters out.
    """
    import duckdb

    repo = Path(__file__).resolve().parents[2]
    netnew = repo / "output/netnew"
    manifest = netnew / "hostnames_evidence_manifest.csv"
    files = sorted(netnew.glob("*_hostnames.txt"))
    if not manifest.is_file() or not files:
        return {}, Decimal(0)
    weights = [(tld, float(share)) for tld, share in english_weights().items()]
    conn = duckdb.connect()
    conn.execute("CREATE TABLE w(tld VARCHAR, weight DOUBLE)")
    conn.executemany("INSERT INTO w VALUES (?, ?)", weights)
    conn.execute("CREATE TABLE h(hostname VARCHAR, assigned_year INTEGER)")
    for path in files:
        year = int(path.name.split("_")[0])
        conn.execute(
            f"INSERT INTO h SELECT lower(trim(column0)), {year} FROM read_csv(?, header=false, "
            "delim='\x01', columns={'column0': 'VARCHAR'})",
            [str(path)],
        )
    rows = conn.execute(
        """
        SELECT m.acquisition_method, count(*), sum(coalesce(w.weight, 0))
        FROM h
        JOIN read_csv_auto(?, header=true) m USING (hostname, assigned_year)
        LEFT JOIN w ON w.tld = regexp_extract(h.hostname, '([a-z0-9-]+)$', 1)
        GROUP BY 1
        """,
        [str(manifest)],
    ).fetchall()
    www = conn.execute(
        # coalesce: the files exist but are empty at the start of a round
        "SELECT coalesce(sum(CASE WHEN hostname LIKE 'www.%' THEN 1 ELSE 0 END) / count(*), 0) "
        "FROM h"
    ).fetchone()[0]
    conn.close()
    return (
        {m: (int(n), Decimal(str(round(ee, 4)))) for m, n, ee in rows},
        Decimal(str(www)),
    )


def attribution_table(f: dict, hosts: dict[str, tuple[int, Decimal]]) -> str:
    """Section 2's table over BOTH units, ranked by equivalent-English."""
    rows = []
    for r in f["by_source"]:
        what, dates = GROUNDS.get(
            r["source"],
            ("see `sources.md`", CLASS_GROUNDS.get(r["evidence_type"], r["evidence_type"])),
        )
        rows.append((r["source"], "registrable", what, dates, r["pairs"], Decimal(str(r["ee"]))))
    for method, (n, ee) in hosts.items():
        what, dates = GROUNDS.get(method, ("see `sources.md`", "a Wayback capture timestamp"))
        rows.append((method, "hostname", what, dates, n, ee))
    rows.sort(key=lambda r: r[5], reverse=True)
    shown = [r for r in rows if r[5] >= ATTRIBUTION_FLOOR_EE]
    rest = [r for r in rows if r[5] < ATTRIBUTION_FLOOR_EE]
    # Separator dash counts set the docx column widths when a line exceeds pandoc's
    # width, which every row here does; the two prose columns get the room.
    lines = [
        "| Source, unit | Artifact, and how it was obtained | What dates one record "
        "| Records | EE |",
        "|--------------|--------------------------|----------------------|--------:|-------:|",
    ]
    for name, unit, what, dates, n, ee in shown:
        lines.append(f"| `{name}`, {unit} | {what} | {dates} | {n:,} | {ee:,.0f} |")
    if rest:
        n = sum(r[4] for r in rest)
        ee = sum((r[5] for r in rest), Decimal(0))
        lines.append(
            f"| {len(rest)} further sources | each under {ATTRIBUTION_FLOOR_EE:,.0f} EE, "
            f"listed in `audit/source_contribution.csv` | | {n:,} | {ee:,.0f} |"
        )
    total_n = sum(r[4] for r in rows)
    total_ee = sum((r[5] for r in rows), Decimal(0))
    lines.append(f"| **Total** | | | **{total_n:,}** | **{total_ee:,.0f}** |")
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
    merge_dir = Path(__file__).resolve().parents[2] / "output/merge"
    newest = newest_audit(merge_dir)
    if newest is None:
        return None
    return json.loads(newest.read_text(encoding="utf-8"))["totals"]


ATTRIBUTION_TOP_ROWS = 6


def attribution_rows(f: dict, hosts: dict[str, tuple[int, Decimal]]) -> list[tuple]:
    """Both units as (name, unit, what, dates, records, EE), ranked by EE."""
    rows = []
    for r in f["by_source"]:
        what, dates = GROUNDS.get(
            r["source"],
            ("see `sources.md`", CLASS_GROUNDS.get(r["evidence_type"], r["evidence_type"])),
        )
        rows.append((r["source"], "registrable", what, dates, r["pairs"], Decimal(str(r["ee"]))))
    for method, (n, ee) in hosts.items():
        what, dates = GROUNDS.get(method, ("see `sources.md`", "a Wayback capture timestamp"))
        rows.append((method, "hostname", what, dates, n, ee))
    rows.sort(key=lambda r: r[5], reverse=True)
    return rows


def attribution_top(f: dict, hosts: dict[str, tuple[int, Decimal]]) -> str:
    """The few sources that carry the round, one row each; the long tail is one row
    pointing at the register. Ivo, 2026-09-02: the full table cost a page of the
    report and belongs in `sources.md` and `audit/source_contribution.csv`."""
    rows = attribution_rows(f, hosts)
    shown, rest = rows[:ATTRIBUTION_TOP_ROWS], rows[ATTRIBUTION_TOP_ROWS:]
    lines = [
        "| Source | Unit | What dates one record | Records | EE |",
        "|------------------------|------|----------------------------|--------:|-------:|",
    ]
    for name, unit, _what, dates, n, ee in shown:
        lines.append(f"| `{name}` | {unit} | {dates} | {n:,} | {ee:,.0f} |")
    if rest:
        n = sum(r[4] for r in rest)
        ee = sum((r[5] for r in rest), Decimal(0))
        units = sorted({r[1] for r in rest})
        unit = units[0] if len(units) == 1 else "both"
        lines.append(
            f"| {len(rest)} further sources | {unit} | one row each in `sources.md` "
            f"and `audit/source_contribution.csv` | {n:,} | {ee:,.0f} |"
        )
    total_n = sum(r[4] for r in rows)
    total_ee = sum((r[5] for r in rows), Decimal(0))
    lines.append(f"| **Total** | | | **{total_n:,}** | **{total_ee:,.0f}** |")
    return "\n".join(lines)


def grouped_ee(f: dict, hosts: dict[str, tuple[int, Decimal]]) -> dict[str, str]:
    """Section 3's per-lane figures, summed from the same rows as the table so the
    prose cannot drift from it."""
    by = {r["source"]: (r["pairs"], Decimal(str(r["ee"]))) for r in f["by_source"]}

    def total(names: list[str]) -> tuple[int, Decimal]:
        n = sum(by.get(x, (0, Decimal(0)))[0] for x in names)
        ee = sum((by.get(x, (0, Decimal(0)))[1] for x in names), Decimal(0))
        return n, ee

    nypw = ["nypw_timemaps", "nypw_timemaps_nonok"]
    cdx = ["ia_cdx_bulk"]
    usenet = ["usenet_address", "usenet_announce", "usenet_bare"]
    other = [x for x in by if x not in nypw + cdx + usenet]
    h_nypw = hosts.get("nypw_timemap_hostgrain", (0, Decimal(0)))
    h_sweep = hosts.get("ia_cdx_domain_sweep", (0, Decimal(0)))
    h_ew = hosts.get("early_web_hostgrain", (0, Decimal(0)))
    h_fg = hosts.get("usfedgov_extract_hostgrain", (0, Decimal(0)))
    list_methods = ("robot_compiled_blocklist", "dated_blocklist_release")
    lists = [hosts.get(m, (0, Decimal(0))) for m in list_methods]
    h_list = (sum(r[0] for r in lists), sum((r[1] for r in lists), Decimal(0)))
    return {
        "HOST_NYPW_EE": f"{h_nypw[1]:,.0f}",
        "HOST_NYPW_N": f"{h_nypw[0]:,}",
        "HOST_EARLYWEB_EE": f"{h_ew[1]:,.0f}",
        "HOST_EARLYWEB_N": f"{h_ew[0]:,}",
        "HOST_USFEDGOV_EE": f"{h_fg[1]:,.0f}",
        "HOST_USFEDGOV_N": f"{h_fg[0]:,}",
        "HOST_BLOCKLIST_EE": f"{h_list[1]:,.0f}",
        "HOST_BLOCKLIST_N": f"{h_list[0]:,}",
        "HOST_SWEEP_EE": f"{h_sweep[1]:,.0f}",
        "HOST_SWEEP_N": f"{h_sweep[0]:,}",
        "REG_NYPW_EE": f"{total(nypw)[1]:,.0f}",
        "REG_CDX_EE": f"{total(cdx)[1]:,.0f}",
        "REG_USENET_EE": f"{total(usenet)[1]:,.0f}",
        "REG_OTHER_EE": f"{total(other)[1]:,.0f}",
        "REG_OTHER_N": f"{len(other)}",
    }


def substitutions(f: dict) -> dict[str, str]:
    accepted = accepted_totals()
    hosts, www_share = hostname_breakdown()
    h_pairs = sum(n for n, _ in hosts.values())
    h_ee = sum((ee for _, ee in hosts.values()), Decimal(0))
    # Fall back to the store only when no merge has been run, so a missing audit
    # produces a slightly different number rather than an empty placeholder.
    total = int(accepted["accepted_new_records"]) if accepted else f["netnew_pairs"] + h_pairs
    ee_total = (
        Decimal(accepted["equivalent_english_increment"])
        if accepted
        else Decimal(f["ee_netnew"]) + h_ee
    )
    reg_pairs = int(accepted["submitted_registrable_records"]) if accepted else f["netnew_pairs"]
    # **The headline increment comes from the MERGE AUDIT and the growth rate from the
    # LIVE STORE, so a stale audit makes lines 3 and 4 contradict line 5.** Caught on
    # 2026-08-26 with the audit reading 769,438 records and 488,722 EE beside a live
    # 5.3344% that implies 712,801. Both numbers were individually right and the table was
    # nonsense. Re-run `merge_against_baseline.py` after the last ingest of a round; this
    # refuses to fill rather than shipping a self-contradicting table. The audit scores
    # both units, so the store side of the comparison is registrables plus hostnames.
    if accepted:
        store_ee = Decimal(f["ee_netnew"]) + h_ee
        drift = abs(store_ee - ee_total)
        # Relative, because a running collector moves the store by a few pairs while the
        # merge is scoring files. 0.05% catches a stale ROUND (488,722 against 712,801 is
        # 31%) while tolerating the handful of pairs a live ingest adds mid-run. For a
        # submission, stop the ingest loop first so the drift is zero.
        if drift > max(Decimal("50"), ee_total * Decimal("0.0005")):
            raise SystemExit(
                "merge audit is stale: it reports "
                f"{ee_total:,.4f} equivalent-English over {total:,} records, but the store "
                f"and hostname files hold {store_ee:,.4f} over {f['netnew_pairs'] + h_pairs:,}. "
                "Run `uv run python scripts/round/merge_against_baseline.py` and refill."
            )

    # The growth rate has to come from the same place as the increment. It did not: the
    # increment was the merge audit's and the rate the store's, which differ by the twelve
    # pairs the export filter drops, so the cumulative sentence printed components summing
    # to 32.6315 beside a total of 32.6316.
    growth = (
        Decimal(str(accepted["equivalent_english_growth_rate_pct"]))
        if accepted and accepted.get("equivalent_english_growth_rate_pct") is not None
        else Decimal(str(f["ee_netnew_growth_pct"]))
    )
    baseline_ee = Decimal(str(f["ee_baseline"]))
    reg_ee = ee_total - h_ee
    by_source = {r["source"]: r for r in f["by_source"]}
    cdx_bulk = by_source.get("ia_cdx_bulk", {}).get("pairs", 0)
    subs: dict[str, str] = {
        "TOTAL": f"{total:,}",
        # Four decimals, because that is the precision the reviewer reports back in
        # and a rounded total reads to him as a different number than the one he
        # computed with his own calculator.
        "EE": f"{ee_total:,.4f}",
        "EEGROWTH": f"{growth:.4f}%",
        "REGPAIRS": f"{reg_pairs:,}",
        "REGEE": f"{reg_ee:,.4f}",
        "REGGROWTH": f"{reg_ee / baseline_ee * 100:.4f}%",
        "HOSTPAIRS": f"{h_pairs:,}",
        "HOSTEE": f"{h_ee:,.4f}",
        "HOSTGROWTH": f"{h_ee / baseline_ee * 100:.4f}%",
        "WWWSHARE": f"{www_share * 100:.1f}%",
        "CDXBULK": f"{cdx_bulk:,}",
        "UNIQUE": f"{f['netnew_unique_domains']:,}",
        "NEWDOMAINS": f"{f['netnew_domains_absent_from_baseline']:,}",
        "CANDIDATES": f"{f['candidate_pool']:,}",
        "BASELINE": BASELINE,
        "ROUND": CURRENT_ROUND_LABEL,
        "EEBASELINE": f"{f['ee_baseline']:,.4f}",
        "ATTRIBUTION_TABLE": attribution_table(f, hosts),
        "ATTRIBUTION_TOP": attribution_top(f, hosts),
        **grouped_ee(f, hosts),
        "MASTERTYPES": ", ".join(f"`{t}`" for t in sorted(MASTER_TYPES) if t != "prior_reused"),
        "PER_YEAR_TABLE": per_year_table(f),
        "DATASETS_SEARCHED": datasets_searched(),
        "POOL_RESTRICTED": pool_restricted(),
        "CUMULATIVE": cumulative(f, growth),
        "CUMULATIVE_SENTENCE": cumulative_sentence(f, growth),
        "MERGE_RECONCILIATION": merge_reconciliation(),
        "REPRODUCTION_RESULT": reproduction_result(),
    }
    # The REVIEWER'S raw record count, not the store's. These differ by 1.6 million,
    # because the store canonicalises to registrable domains and he counts lines, and
    # a sentence that set his count for one release beside our count for the next
    # would read as a shrinking baseline. Quote one counting unit or the other, never
    # one of each.
    subs["BASELINEPAIRS"] = f"{REVIEWER_BASELINE_PAIRS:,}"
    # The ISC folder is a question and not a claim (C-70), so its size is counted from the
    # files that actually ship rather than typed into the prose, where it would drift.
    isc = 0
    for year in range(1996, 2002):
        path = NETNEW_DIR / f"{year}-ISC.txt"
        if path.is_file():
            with path.open(encoding="utf-8", errors="replace") as fh:
                isc += sum(1 for line in fh if line.strip())
    subs["ISCPAIRS"] = f"{isc:,}"

    return subs


def reproduction_result() -> str:
    """What the archive's own reproduction actually did, when it was last run.

    Read from a file rather than asserted in prose, because a report that claims
    "verified" is worth nothing next to one that names the run. `just ship` writes
    it; if it is absent the report says so instead of implying a pass.
    """
    path = Path(__file__).resolve().parents[2] / "docs/reproduction.txt"
    if not path.is_file():
        return (
            "_The reproduction has not been run against this build. "
            "`bash verify.sh` inside the archive is the first check._"
        )
    return path.read_text(encoding="utf-8").strip()


class ScoreRow(NamedTuple):
    """One round under `S_i = 10 p_i / t_i`; `scored` says whether his rule covered it."""

    label: str
    p: Decimal
    t: int
    s: Decimal
    scored: bool


def score_rows(growth: Decimal) -> list[ScoreRow]:
    """Every submitted round and this one, priced by `ark.figures`.

    The awarded percentages and both timestamps are quoted in
    `ark.baseline.SUBMITTED_ROUNDS`; the arithmetic is his rule as `ark.figures` states
    it. This round uses its own unverified growth and this minute as its receipt, and is
    never marked scored, because he has not seen it.
    """
    rows = []
    for r in SUBMITTED_ROUNDS:
        t = t_days(r[6], r[7])
        rows.append(ScoreRow(r[0], r[5], t, score(r[5], t), scored_under_rule(r[7])))
    t_now = t_days(CURRENT_BASELINE_RELEASED, now_in_his_clock())
    rows.append(
        ScoreRow(f"{CURRENT_ROUND_LABEL} (this round)", growth, t_now, score(growth, t_now), False)
    )
    return rows


def _score_parts(rows: list[ScoreRow]) -> tuple[Decimal, Decimal, list[ScoreRow], list[ScoreRow]]:
    """Cumulative percentage, his S_total, the rounds he scored and the ones before the rule."""
    pct = sum((r.p for r in rows), Decimal(0))
    scored = [r for r in rows if r.scored]
    early = [r for r in rows[:-1] if not r.scored]
    return pct, score_total(r.s for r in scored), scored, early


def _per_round(rows: list[ScoreRow]) -> str:
    """`label: p / t = S`, p at the six places he awards so the division checks by hand."""
    return "; ".join(f"{r.label.split()[0]}: {r.p:.6f}% / {r.t}d = {r.s:.6f}" for r in rows)


def cumulative(f: dict, growth: Decimal) -> str:
    """Both official records: the cumulative percentage and the time-weighted score.

    The percentage record is the direct arithmetic sum of what he awarded, round 1
    included on Ivo's instruction of 2026-09-02 even though it was awarded on records.
    The score record is the sum of S_i over the rounds he has scored, which his rule
    only covers from its 2026-08-20 update: earlier rounds get their would-be S in a
    clause of their own, and this round its prediction, labelled as such.
    """
    rows = score_rows(growth)
    pct, total, scored, early = _score_parts(rows)
    this = rows[-1]
    early_labels = ", ".join(r.label for r in early[:-1]) + f" and {early[-1].label}"
    return (
        f"**Score, by both rules in your brief.** Cumulative verified percentage "
        f"**{pct:.4f}%**, this round counted at its own unverified {growth:.4f}% and round 1 "
        f"on records. Time-weighted **S = {total:.6f}** over the rounds you have scored "
        f"({_per_round(scored)}), with t_i the elapsed time from the release of the package "
        "a round is measured against to receipt, rounded up to whole days in your clock, "
        "which reproduces the 6.88 and 6.302372 you quoted. This round would add "
        f"{this.s:.6f} at t = {this.t} if received now. Rounds {early_labels} predate the "
        f"rule; under it they would have scored {_per_round(early)}."
    )


def merge_reconciliation() -> str:
    """The D3 merge audit, read from the file the packaging step produced.

    Read rather than recomputed. `merge_against_baseline.py` scores every annual file
    with the reviewer's own calculator, which takes minutes, and a second derivation
    here would be a second thing to keep in step with the first. If the audit is
    absent the report says so instead of implying the merge was run.
    """
    merge_dir = Path(__file__).resolve().parents[2] / "output/merge"
    newest = newest_audit(merge_dir)
    if newest is None:
        return (
            "_The merge has not been run against this build. "
            "`uv run python source/scripts/round/merge_against_baseline.py` produces it._"
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
        f"| **accepted increment** | **{int(t['accepted_new_records']):,}** | "
        f"**{Decimal(t['equivalent_english_increment']):,.4f}** |",
        f"| post-merge total | {int(t['post_merge_records']):,} | "
        f"{Decimal(t['post_merge_equivalent_english_total']):,.4f} |",
    ]
    return "\n".join(
        [
            *rows,
            "",
            f"Overlap with the baseline is **{int(t['already_in_baseline_records']):,} records**, "
            f"so all {int(t['submitted_records']):,} submitted count once, and "
            f"**{passed} of {len(checks)} reconciliation checks pass**. "
            "`merge_against_baseline.py` unions both units into the baseline, deduplicates on the "
            "lowercased line within each year and scores every file with your own calculator; the "
            "per-check verdicts are in `audit/merge_audit_ark_*.json` and the per-year form in "
            "`audit/merge_stats_ark_*.csv`, in your column names.",
        ]
    )


def cumulative_sentence(f: dict, growth: Decimal) -> str:
    """The same two records, as one sentence for the email."""
    rows = score_rows(growth)
    pct, total, scored, _ = _score_parts(rows)
    this = rows[-1]
    # Both readings of t_i, because his 0903 update redefined it and the two differ by
    # almost 4x on this round alone. Quoting one silently would be a claim, not a figure.
    from ark.figures import t_days_assignment

    t_abs = t_days_assignment(now_in_his_clock())
    s_abs = score(growth, t_abs)
    return (
        f"Cumulative verified percentage {pct:.4f}%, time-weighted score {total:.6f} over the "
        f"rounds you scored. **Your 0903 t_i change makes this round either {this.s:.6f} or "
        f"{s_abs:.6f}** (t = 1 on the benchmark interval, t = {t_abs} days on the absolute "
        f"task-assignment interval). Which do you intend, and does it re-score the awarded "
        f"rounds?"
    )


def pool_restricted() -> str:
    """Candidate-pool names under namespaces nobody could register in freely.

    Was typed as 575,417 and had drifted, in the one sentence of the report that argues
    the gate is worth something. Generated so it cannot drift again, and the namespaces
    are now named in the prose so a reviewer can reproduce the query.
    """
    from ark.db import DEFAULT_DB_PATH, connect_read_only_patiently
    from ark.delegation import shipping_filter

    conn = connect_read_only_patiently(DEFAULT_DB_PATH)
    try:
        n = conn.execute(f"""
            SELECT count(*) FROM domain d
            WHERE (d.domain LIKE '%.edu' OR d.domain LIKE '%.gov' OR d.domain LIKE '%.mil')
              AND NOT EXISTS (SELECT 1 FROM domain_year dy WHERE dy.domain = d.domain)
              AND {shipping_filter("d.", with_year=False)}
        """).fetchone()[0]
    finally:
        conn.close()
    return f"{n:,}"


def _register_rows(text: str, heading: str) -> int:
    """Rows of one register table, by the heading it sits under.

    Rows the register itself labels "Not a source" are notes about our own queue,
    not families searched, and counting them overstated the headline by two.
    """
    if heading not in text:
        return 0
    section = text.split(heading, 1)[1].split("\n## ", 1)[0]
    return sum(
        1
        for line in section.splitlines()
        if line.startswith("|")
        and not line.startswith("|--")
        and not line.lower().startswith("| source")
        and "not a source" not in line.lower()
    )


def datasets_searched(docs: Path | None = None) -> str:
    """The register of families searched, read from the register rather than retyped.

    The reviewer asks for every external dataset and repository searched. That list
    only stays true if it is derived from the register itself: a hand-written copy
    omits whatever was added after it was written, and the omission is invisible.

    The register has two halves and they are counted separately, because a prose
    sentence that said "roughly sixty" sat directly above a generated "26" in the
    first draft of this section. Developed sources get a `## ` heading each;
    families evaluated and rejected are one table row each under a single heading.
    Both are searches, and the second half is much the larger.

    **Both files are counted.** The rejected half lives in two documents since
    `convert_register.py` moved closed families to `sources-closed.md`, and counting
    `sources.md` alone dropped the figure from 495 to 129, which would have
    understated our own work to the reviewer fourfold.
    """
    docs = docs or Path(__file__).resolve().parents[2] / "docs"
    path = docs / "sources.md"
    if not path.is_file():
        return "_`sources.md` not found beside this report._"

    text = path.read_text(encoding="utf-8")
    closed = docs / "sources-closed.md"
    closed_text = closed.read_text(encoding="utf-8") if closed.is_file() else ""

    # Headings at this level that are prose about the file rather than a source.
    skip = {
        "Summary",
        "Source names that are not separate sources",
        "Evaluated and rejected",
        "Measured, and each blocked on something other than work",
        # the appendix `convert_register.py` writes: one `### ` block per row above
        "Detail",
    }
    developed = [
        line[3:].strip()
        for line in text.splitlines()
        if line.startswith("## ") and line[3:].strip() not in skip
    ]

    rejected = _register_rows(text, "## Evaluated and rejected") + _register_rows(
        closed_text, "## Closed families, converted from the register"
    )

    if not developed and not rejected:
        return "_No families recorded._"

    # Counts only, and the names deliberately omitted. The reviewer's requirement is
    # that every dataset searched be documented, not that it be documented twice: the
    # register itself ships beside the report and is the place to read it. Naming all
    # 26 developed families inline cost most of a page and told him nothing the file
    # does not, which is why the list was cut on Ivo's instruction (2026-08-17).
    return (
        f"**{len(developed) + rejected} source families searched and recorded** in "
        f"`sources.md` and `sources-closed.md`: {len(developed)} developed, {rejected} evaluated "
        "and closed with the measurement that closed them, so the same ground is not broken twice."
    )


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
