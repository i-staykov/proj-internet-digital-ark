"""Substitute the round report's placeholders from the live store or the archive's figures.

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
    uv run python scripts/round/fill_report.py --write-figures <stage>/audit/report_figures.json
    uv run python scripts/round/fill_report.py --figures <stage>/audit/report_figures.json

The packager writes the figures into the archive and ships no report, so the report is filled
on the laptop from them with no store, and a wording edit never repackages. t and the scores
are derived at fill time from the growth figures and today's date.

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

from ark.baseline import (  # noqa: E402
    CURRENT_ROUND_LABEL,
    REVIEWER_BASELINE_PAIRS,
    REVIEWER_EXTENDED_EE,
)
from ark.english_share import english_weights  # noqa: E402
from ark.export import NETNEW_DIR  # noqa: E402
from ark.figures import now_in_his_clock, score_line, t_days_assignment, t_span  # noqa: E402

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
# and the fill is what keeps its figures identical to the report's.
# (template, target, an unwritten round section is fatal). Fatal for the report, which
# ships: an empty section 5 reaching the reviewer is the failure the whole token
# mechanism exists to prevent. Not fatal for the email, which is a draft the owner finishes by
# hand at submission time and which never leaves `private/`. Making it fatal there would
# block every packaging run for a document nobody is sending yet.
DOCUMENTS = (
    (Path("docs/report.template.md"), Path("docs/report.md"), True),
    (Path("private/email.template.md"), Path("private/email-draft.md"), False),
)


def hostname_breakdown() -> dict[str, tuple[int, Decimal]]:
    """(records, EE) per acquisition method over the SHIPPED hostname files.

    Joined against the shipped manifest rather than the store, so the figures describe
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
        # His raw line count, never the store's registrable count: one counting unit only.
        "BASELINEPAIRS": f"{REVIEWER_BASELINE_PAIRS:,}",
    }
    # The 2002 to 2013 additions as `extended_export.py` measured them, zero before any. Each
    # part is its growth over his EE for its years with his S beside it, never the two summed;
    # only the EE increments add, into the combined increment his brief asks for. t is whole
    # days from the 2 August assignment, as he would count it today. Post-merge totals add the
    # rounded figures the table prints, so its "2 + 4" check holds to the last place.
    manifest = Path("output/extended_years/manifest.json")
    ext = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
    ext_ee = Decimal(ext.get("increment_ee", "0"))
    ext_growth = ext_ee / REVIEWER_EXTENDED_EE * 100 if REVIEWER_EXTENDED_EE else Decimal(0)
    baseline_ee = Decimal(str(f["ee_baseline"]))
    four = Decimal("0.0001")
    subs |= {
        "EXTPAIRS": f"{ext.get('accepted_new', 0):,}",
        "EXTEE": f"{ext_ee:,.4f}",
        "EXTGROWTH": f"{ext_growth:.4f}%",
        "EXTBASELINEEE": f"{REVIEWER_EXTENDED_EE:,.4f}",
        "EEPOSTMERGE": f"{baseline_ee.quantize(four) + ee_total.quantize(four):,.4f}",
        "EXTPOSTMERGE": f"{REVIEWER_EXTENDED_EE.quantize(four) + ext_ee.quantize(four):,.4f}",
        "COMBINEDEE": f"{ee_total.quantize(four) + ext_ee.quantize(four):,.4f}",
        "DISTINCTNEW": f"{distinct_added():,}",
        # At the ten places `score_line` prints, so each occurs in the filled report.
        "GROWTH_CORE": f"{growth.quantize(Decimal('1E-10')):f}",
        "GROWTH_EXT": f"{ext_growth.quantize(Decimal('1E-10')):f}",
    }
    # The mail quotes the reconciliation count too, and it is read from the audit rather
    # than typed, because a mail claiming a pass count the audit does not hold is the one
    # error he would never have to look for.
    audit = newest_audit(Path(__file__).resolve().parents[2] / "output/merge")
    checks = []
    if audit is not None:
        checks = json.loads(audit.read_text(encoding="utf-8")).get("reconciliation", [])
    subs["RECONCILIATION"] = f"{sum(1 for c in checks if c.get('passed'))} of {len(checks)}"

    return subs


def dated(subs: dict[str, str], now: str) -> dict[str, str]:
    """t, its span and both scores, as he would count them on `now`."""
    t = t_days_assignment(now)
    return {
        "TDAYS": str(t),
        "TSPAN": t_span(now),
        "SCORE_CORE": score_line(Decimal(subs["GROWTH_CORE"]), t),
        "SCORE_EXT": score_line(Decimal(subs["GROWTH_EXT"]), t),
    }


def distinct_added() -> int:
    """Distinct names across every shipped addition, 1996 to 2013: `additions/`, `hostnames/` and
    `extended_years/additions/`, counted as the report's `LC_ALL=C sort -u | wc -l` counts them.
    The brief's supporting statistic beside the record counts; it never enters the EE."""
    import duckdb

    years = range(1996, 2002)
    files = [NETNEW_DIR / f"{y}.txt" for y in years] + [
        NETNEW_DIR / f"{y}_hostnames.txt" for y in years
    ]
    files += sorted(Path("output/extended_years/additions").glob("*.txt"))
    files = [str(p) for p in files if p.is_file()]
    if not files:
        return 0
    conn = duckdb.connect()
    try:
        return conn.execute(
            "SELECT count(DISTINCT name) FROM read_csv(?, header=false, delim='\x01', quote='', "
            "escape='', columns={'name': 'VARCHAR'})",
            [files],
        ).fetchone()[0]
    finally:
        conn.close()


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
    parser.add_argument("--figures", type=Path, help="fill from this JSON, opening no store")
    parser.add_argument("--write-figures", type=Path, help="write the store's figures here, only")
    args = parser.parse_args()

    if args.figures:
        subs = json.loads(args.figures.read_text(encoding="utf-8"))
    else:
        conn = connect_read_only_patiently(DB)
        subs = substitutions(figures(conn))
        conn.close()
    if args.write_figures:
        args.write_figures.write_text(json.dumps(subs, indent=2) + "\n", encoding="utf-8")
        print(f"{args.write_figures}: written")
        return
    subs |= dated(subs, now_in_his_clock())

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
