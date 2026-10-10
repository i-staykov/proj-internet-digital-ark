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

from ark.db import connect_read_only_patiently

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_figures import BASELINE, figures  # noqa: E402

from ark.baseline import CURRENT_ROUND_LABEL, REVIEWER_EXTENDED_EE  # noqa: E402
from ark.english_share import english_weights  # noqa: E402
from ark.figures import now_in_his_clock, score_line, t_days_assignment  # noqa: E402

DB = Path("data/ark.duckdb")
# Template in, filled document out. Filling in place would consume the template,
# and the numbers have to be refilled every time the archive is re-cut, so the
# template is the thing that lives in git and the filled copy is a build product.
#
# One report, not one per round: the round is identified by its content and its git tag.
#
# The email is filled too, but ONLY out of `private/`, which is git-ignored.
# `package_delivery.sh` ships `git archive HEAD`, so every tracked file reaches the
# reviewer, and an email draft's notes section holds private reasoning about how to
# present the work to him. A template addressed to a person is one edit away from
# carrying that, so the whole pair stays outside git
# and the fill is what keeps its five figures identical to the report's.
# (template, target, an unwritten round section is fatal). Fatal for the report, which
# ships: an empty section 5 reaching the reviewer is the failure the whole token
# mechanism exists to prevent. Not fatal for the email, which is a draft the owner finishes by
# hand at submission time and which never leaves `private/`. Making it fatal there would
# block every packaging run for a document nobody is sending yet.
DOCUMENTS = (
    (Path("docs/report.template.md"), Path("docs/report.md"), True),
    (Path("private/email.template.md"), Path("private/email-draft.md"), False),
)


# One line per source saying what dates a record and how the artifact was obtained, for
# the attribution table in section 2. The FIGURES beside them are read from the store and
# the shipped files; only these two phrases are typed, and a source missing here still
# appears, described by its evidence class, so the table can never silently drop a row.
# Hostname sources are keyed by acquisition method because both live under one source row.
GROUNDS: dict[str, tuple[str, str]] = {
    "bulk_cdx_file": (
        "a public Internet Archive CDX index read whole",
        "the row's own 14-digit capture timestamp in the archive's index",
    ),
    "nypw_timemap_hostgrain": (
        "NYPW TimeMaps (IA, CC BY 4.0), 34 parts held since round 6, re-read at hostname grain",
        "the row's own 14-digit capture timestamp, in the archive's Not Your Parents' Web "
        "first-capture index",
    ),
    "ia_cdx_domain_sweep": (
        "IA CDX `matchType=domain` sweeps, two clients, parents ranked by the hosts we lack",
        "the row's own 14-digit capture timestamp",
    ),
    "usenet_server_written_header": (
        "Usenet spool (IA), already held, re-read for the three headers a news server writes "
        "about itself: `Path:`, `X-Trace:`, `NNTP-Posting-Host:`",
        "the post's own machine-written `Date:` header",
    ),
    "ietf_list_received_by": (
        "IETF mail archive, one raw mbox per list-month",
        "the message's `Date:` header, checked against the month the archive filed it under",
    ),
    "apache_list_received_by": (
        "Apache mailing-list archive, the same clause at a second host",
        "the message's `Date:` header, checked against the month the archive filed it under",
    ),
    "poland_pl_extract_hostgrain": (
        "Poland `.pl` ccTLD extraction 2001-12-31 (IA), 19 CDX indexes, 1.24 GB, each verified "
        "against its published sha256",
        "the row's own 14-digit capture timestamp, from the original URL and never the SURT key",
    ),
    "arquivo_ia_cdxj_hostgrain": (
        "Arquivo.pt `IA.cdxj` capture index, held since 2026-08, re-read at hostname grain",
        "the row's own 14-digit capture timestamp",
    ),
    "ia_cdx_gap_hostgrain": (
        "IA CDX queries over bracketed year gaps, read at hostname grain",
        "the row's own 14-digit capture timestamp",
    ),
    "usenet_header_fqdn_hostnames": (
        "the registrable half of the Usenet server-header lane above",
        "the post's own machine-written `Date:` header",
    ),
    "poland_pl_extract_hostnames": (
        "the registrable half of the Poland `.pl` extraction above",
        "the row's own 14-digit capture timestamp",
    ),
    "usenet_body_url_hostnames": (
        "the registrable half of the Usenet body-URL lane",
        "the post's own machine-written `Date:` header",
    ),
    "ia_cdx_hostnames": (
        "the registrable half of the CDX sweeps above",
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
        "Every non-alt Usenet hierarchy (IA), 224 GB read whole, hosts only from explicit "
        "http, https and ftp URLs in the post body",
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
        "IA CDX per-domain queries over bracketed year gaps and the candidate pool",
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


def hostname_breakdown() -> dict[str, tuple[int, Decimal]]:
    """(records, EE) per acquisition method over the SHIPPED hostname files.

    Joined against the shipped manifest rather than the store, so the table describes
    the files in the archive: the store holds hostname rows the export filters out.
    """
    import duckdb

    repo = Path(__file__).resolve().parents[2]
    netnew = repo / "output/netnew"
    manifest = netnew / "hostnames_evidence_manifest.csv"
    files = sorted(netnew.glob("*_hostnames.txt"))
    if not manifest.is_file() or not files:
        return {}
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
    conn.close()
    return {m: (int(n), Decimal(str(round(ee, 4)))) for m, n, ee in rows}


def newest_audit(merge_dir: Path) -> Path | None:
    """The most recently WRITTEN merge audit, or None.

    **By modification time, never by name, and there is exactly one of these because two
    call sites that disagree make the report contradict itself.** Sorting alphabetically
    picks `merge_audit_ark_20260824c.json` over a freshly written `merge_audit_ark.json`,
    since the tagged name sorts last, and puts a stale increment beside a live growth rate.
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


# A source is named in the report when it carries at least this much of the round; the rest
# is one row pointing at the register: nothing under 4,000 EE by name.
ATTRIBUTION_FLOOR_EE = Decimal(4000)


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
    pointing at the register. The full table costs a page of the report and
    belongs in `sources.md` and `audit/source_contribution.csv`."""
    rows = attribution_rows(f, hosts)
    shown = [r for r in rows if r[5] >= ATTRIBUTION_FLOOR_EE]
    rest = rows[len(shown) :]
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


def substitutions(f: dict) -> dict[str, str]:
    accepted = accepted_totals()
    hosts = hostname_breakdown()
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
    # **The headline increment comes from the MERGE AUDIT and the growth rate from the
    # LIVE STORE, so a stale audit makes lines 3 and 4 contradict line 5**, each number
    # right on its own and the table nonsense. Re-run `merge_against_baseline.py` after the
    # last ingest of a round; this refuses to fill rather than shipping a self-contradicting
    # table. The audit scores both units, so the store side of the comparison is
    # registrables plus hostnames.
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

    # The growth rate comes from the same place as the increment: the merge audit's and the
    # store's differ by the pairs the export filter drops, so mixing them disagrees in the
    # fourth place.
    growth = (
        Decimal(str(accepted["equivalent_english_growth_rate_pct"]))
        if accepted and accepted.get("equivalent_english_growth_rate_pct") is not None
        else Decimal(str(f["ee_netnew_growth_pct"]))
    )
    subs: dict[str, str] = {
        "TOTAL": f"{total:,}",
        # Four decimals, because that is the precision the reviewer reports back in
        # and a rounded total reads to him as a different number than the one he
        # computed with his own calculator.
        "EE": f"{ee_total:,.4f}",
        "EEGROWTH": f"{growth:.4f}%",
        "BASELINE": BASELINE,
        "ROUND": CURRENT_ROUND_LABEL,
        "EEBASELINE": f"{f['ee_baseline']:,.4f}",
        "ATTRIBUTION_TOP": attribution_top(f, hosts),
        "MERGE_RECONCILIATION": merge_reconciliation(),
    }
    # The 2002 to 2013 additions as `extended_export.py` measured them, zero before any. Each
    # part is its growth over his EE for its years with his S beside it, never the two summed;
    # t is whole days from the 2 August assignment, as he would count it today.
    manifest = Path("output/extended_years/manifest.json")
    ext = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
    ext_ee = Decimal(ext.get("increment_ee", "0"))
    ext_growth = ext_ee / REVIEWER_EXTENDED_EE * 100 if REVIEWER_EXTENDED_EE else Decimal(0)
    t_now = t_days_assignment(now_in_his_clock())
    subs |= {
        "EXTPAIRS": f"{ext.get('accepted_new', 0):,}",
        "EXTEE": f"{ext_ee:,.4f}",
        "EXTGROWTH": f"{ext_growth:.4f}%",
        "EXTBASELINEEE": f"{REVIEWER_EXTENDED_EE:,.4f}",
        "TDAYS": str(t_now),
        "SCORE_CORE": score_line(growth, t_now),
        "SCORE_EXT": score_line(ext_growth, t_now),
    }
    return subs


def merge_reconciliation() -> str:
    """The merge audit, read from the file the packaging step produced.

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
            (
                f"**Not one of the {int(t['submitted_records']):,} records submitted is already "
                "in the baseline"
                if int(t["already_in_baseline_records"]) == 0
                else f"Of the {int(t['submitted_records']):,} records submitted, "
                f"**{int(t['already_in_baseline_records']):,} are already in the baseline** and "
                "are excluded"
            )
            + f"; {passed} of {len(checks)} reconciliation checks pass.** Per-check verdicts: "
            "`audit/merge_audit_ark_*.json`; the per-year form, in your column names: "
            "`audit/merge_stats_ark_*.csv`.",
        ]
    )


# The template marks each section whose prose a human must write for this round as
# `<!-- ROUND [ROUND]: ... -->`. An unwritten one is exactly the failure the token
# mechanism exists to prevent: without this `--check` says "would fill cleanly" over a
# report with empty sections, and sections 5 and 6 are the ones the template itself
# says he reads most closely.
UNWRITTEN_SECTION = re.compile(r"<!--\s*ROUND\b", re.I)


def fill(
    template: Path, target: Path, subs: dict[str, str], check: bool, stubs_fatal: bool
) -> list[str]:
    text = template.read_text()
    for token, value in subs.items():
        text = text.replace(f"[{token}]", value)
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
