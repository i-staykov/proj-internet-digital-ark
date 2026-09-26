#!/usr/bin/env bash
# Check a delivery archive without unpacking the source snapshot or installing
# anything: coreutils and python3 are the only requirements. It ships at the
# root of the archive as `verify.sh`, because `just` and the project's
# dependencies live inside source/ and are not available until a reviewer has
# already decided to trust the contents.
#
# The verdicts, in the order printed: checksums; the annual addition files and their counts;
# an evidence row for every addition; the hostname files, disjoint from the registrable files,
# and an evidence row for each; the ISC candidate collection reconciled against the reference
# release; the header candidate collection complete and inside the claim; the evidence wall
# (every provenance assignment cites an evidence row shipped here); then the four deliverables
# D1 to D4: the code snapshot carries its lockfile, the experience summary covers what was
# asked, every merge reconciliation check passed and agrees with the shipped files, and the
# reviewer's own calculator reproduces the audit's baseline figure; last, E1, both open
# research questions folders, their questions, headings, labels and files.
#
# Checks 5 to 8 police the four deliverables he added on 2026-08-17, called D1 to D4
# throughout this project. They are checks rather than a checklist for one reason: the
# evidence wall broke in a shipped archive because the requirement lived only in
# prose, and the evidence-wall check exists because of that.
#
# Exit status is non-zero if any check fails, so it can gate a script.
set -uo pipefail
cd "${1:-$(dirname "$0")}"

fail=0
say() { printf '%-46s %s\n' "$1" "$2"; }

# --- 1. file integrity -------------------------------------------------------
if [ -f SHA256SUMS ]; then
    bad=$(shasum -a 256 -c SHA256SUMS 2>/dev/null | grep -vc ': OK$' || true)
    total=$(wc -l < SHA256SUMS | tr -d ' ')
    if [ "$bad" -eq 0 ]; then
        say "checksums" "PASS  $total files match SHA256SUMS"
    else
        say "checksums" "FAIL  $bad of $total files differ"; fail=1
    fi
else
    say "checksums" "SKIP  no SHA256SUMS here"
fi

# --- 2 and 3. the result, and the evidence behind it -------------------------
python3 - <<'PY' || fail=1
import csv
import sys
from pathlib import Path

years = range(1996, 2002)
additions = {}
for year in years:
    path = Path("additions") / f"{year}.txt"
    if not path.exists():
        print(f"{'annual additions':<46} FAIL  additions/{year}.txt is missing")
        sys.exit(1)
    additions[year] = {line.strip() for line in path.read_text().splitlines() if line.strip()}

total = sum(len(v) for v in additions.values())
per_year = ", ".join(f"{y}:{len(additions[y]):,}" for y in years)
print(f"{'annual additions':<46} PASS  {total:,} pairs ({per_year})")

manifest = Path("additions/evidence_manifest.csv")
if not manifest.exists():
    print(f"{'evidence for every addition':<46} FAIL  manifest is missing")
    sys.exit(1)

# One row per (domain, year) with the observation behind it. Reading it as a set
# and differencing is the whole check: a pair with no row would be a domain in an
# annual file that nothing supports, which is the one thing that must never ship.
covered = set()
with manifest.open(newline="", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        try:
            covered.add((row["domain"], int(row["assigned_year"])))
        except (KeyError, ValueError, TypeError):
            continue

claimed = {(d, y) for y, names in additions.items() for d in names}
missing = claimed - covered
if missing:
    sample = ", ".join(f"{d} ({y})" for d, y in sorted(missing)[:3])
    print(f"{'evidence for every addition':<46} FAIL  {len(missing):,} unsupported, e.g. {sample}")
    sys.exit(1)
print(f"{'evidence for every addition':<46} PASS  all {len(claimed):,} traced to an observation")

# The second output unit (accepted 2026-09-01): hostnames/NNNN_hostnames.txt, each line a
# valid hostname beneath a registrable, each traced to its own capture in the hostname
# manifest, and none of them repeating a line of the registrable file for that year.
hostnames = {}
for year in years:
    path = Path("hostnames") / f"{year}_hostnames.txt"
    hostnames[year] = (
        {line.strip() for line in path.read_text().splitlines() if line.strip()}
        if path.exists()
        else set()
    )
h_total = sum(len(v) for v in hostnames.values())
if h_total:
    per_year = ", ".join(f"{y}:{len(hostnames[y]):,}" for y in years)
    overlap = sum(len(hostnames[y] & additions[y]) for y in years)
    if overlap:
        print(f"{'hostname additions':<46} FAIL  {overlap:,} lines repeat the registrable file")
        sys.exit(1)
    print(f"{'hostname additions':<46} PASS  {h_total:,} records ({per_year}), disjoint from additions/")
    h_manifest = Path("hostnames/hostnames_evidence_manifest.csv")
    if not h_manifest.exists():
        print(f"{'evidence for every hostname':<46} FAIL  hostname manifest is missing")
        sys.exit(1)
    h_covered = set()
    with h_manifest.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                h_covered.add((row["hostname"], int(row["assigned_year"])))
            except (KeyError, ValueError, TypeError):
                continue
    h_claimed = {(d, y) for y, names in hostnames.items() for d in names}
    h_missing = h_claimed - h_covered
    if h_missing:
        sample = ", ".join(f"{d} ({y})" for d, y in sorted(h_missing)[:3])
        print(f"{'evidence for every hostname':<46} FAIL  {len(h_missing):,} unsupported, e.g. {sample}")
        sys.exit(1)
    print(f"{'evidence for every hostname':<46} PASS  all {len(h_claimed):,} traced to a capture")
else:
    print(f"{'hostname additions':<46} SKIP  no hostnames/ in this archive")

PY

# ISC candidates require complete provenance and exact-name reconciliation across all years.
if [ -d isc_survey_hostnames ]; then
    if command -v uv >/dev/null 2>&1; then
        marker=$(python3 -c 'import json; print(json.load(open("isc_survey_hostnames/isc_candidates_summary.json"))["baseline"])') && \
        uv run --with duckdb --no-project python verify_isc_candidates.py \
            --collection isc_survey_hostnames --baseline "baseline/$marker" \
            --annual-dirs masters additions hostnames \
            --weights isc_survey_hostnames/tld_english_share.json || fail=1
    else
        say "ISC candidates" "FAIL  needs uv (https://docs.astral.sh/uv/)"; fail=1
    fi
else
    say "ISC candidates" "SKIP  no isc_survey_hostnames/ in this archive"
fi

# The header candidate collection: its count matches its summary, every name has a provenance
# row, every name sits inside the candidate-track claim that counts it, and the exclusion
# ledger of its validation run is here.
if [ -d server_header_hostnames ]; then
python3 - <<'PY' || fail=1
import csv, json, sys
from pathlib import Path
def say(k, v): print(f"{k:<46} {v}")
d = Path("server_header_hostnames")
names = {l.strip() for l in (d / "header_candidates.txt").read_text().splitlines() if l.strip()}
summary = json.loads((d / "header_candidates_summary.json").read_text())
with (d / "header_candidates_provenance.csv").open(newline="") as f:
    prov = {r["hostname"] for r in csv.DictReader(f)}
claim = {l.strip() for l in Path("candidate_additions.txt").read_text().splitlines() if l.strip()}
problems = []
if len(names) != summary["candidates"]:
    problems.append(f"{len(names)} names, summary says {summary['candidates']}")
if names - prov:
    problems.append(f"{len(names - prov)} names without a provenance row")
if names - claim:
    problems.append(f"{len(names - claim)} names outside candidate_additions.txt")
if not (d / "header_candidates_exclusions.csv").is_file():
    problems.append("no exclusion ledger")
if problems:
    say("header candidates", "FAIL  " + "; ".join(problems)); sys.exit(1)
say("header candidates", f"PASS  {len(names)} names, each with a provenance row, each in the claim")
PY
else
    say "header candidates" "SKIP  no server_header_hostnames/ in this archive"
fi

# --- 4. the evidence wall, inside the shipped provenance ---------------------
# Added 2026-08-17, after an archive shipped with 11,316,960 of 16,619,832
# assignments pointing at an `evidence_id` that was not in the file beside them. A
# packaging change had filtered the evidence table to save 429 MB; every check above
# passed, because they all read the additions manifest and none of them read the
# parquet. The archive's central claim is that any line of any annual file traces to
# an observation IN THIS ARCHIVE, and nothing was testing it.
#
# `uv` is optional here on purpose: the rest of this script needs only coreutils and
# python3, and a reviewer who has not installed uv should still get the first three
# checks rather than an error.
if [ -f provenance/evidence.parquet ] && [ -f provenance/domain_year.parquet ]; then
    if command -v uv >/dev/null 2>&1; then
        orphans=$(uv run --with duckdb --no-project python -c "
import duckdb
c = duckdb.connect()
import os
n = c.execute('''
    SELECT count(*) FROM read_parquet('provenance/domain_year.parquet') dy
    WHERE NOT EXISTS (SELECT 1 FROM read_parquet('provenance/evidence.parquet') e
                      WHERE e.evidence_id = dy.evidence_id)
''').fetchone()[0]
if os.path.exists('provenance/hostname_year.parquet'):
    n += c.execute('''
        SELECT count(*) FROM read_parquet('provenance/hostname_year.parquet') hy
        WHERE NOT EXISTS (SELECT 1 FROM read_parquet('provenance/evidence.parquet') e
                          WHERE e.evidence_id = hy.evidence_id)
    ''').fetchone()[0]
print(n)
" 2>/dev/null | tail -1)
        case "$orphans" in
            0)   say "evidence wall intact" "PASS  every domain and hostname assignment resolves to a shipped evidence row" ;;
            ''|*[!0-9]*) say "evidence wall intact" "SKIP  could not read the provenance export" ;;
            *)   say "evidence wall intact" "FAIL  $orphans assignments cite evidence not in this archive"; fail=1 ;;
        esac
    else
        say "evidence wall intact" "SKIP  needs uv (https://docs.astral.sh/uv/)"
    fi
else
    say "evidence wall intact" "SKIP  no provenance export here"
fi

# --- 5 to 8. the four deliverables added on 2026-08-17 -----------------------
python3 - <<'PY' || fail=1
import json
import subprocess
import sys
import tarfile
from decimal import Decimal
from pathlib import Path

fail = False


def say(label, verdict):
    print(f"{label:<46} {verdict}")


# --- 5 (D1): the runnable code, its configuration and its dependencies -------
# "Complete" is not checkable, but "cannot possibly be installed" is: a snapshot
# without its lockfile pins nothing, so a reader would resolve different versions
# than the ones that produced the data.
snapshot = Path("source/source.tar.gz")
if not snapshot.is_file():
    say("D1 runnable code snapshot", "FAIL  source/source.tar.gz is missing")
    fail = True
else:
    wanted = {
        "pyproject.toml": "dependency manifest",
        "uv.lock": "resolved dependency versions",
        "justfile": "the documented command set",
        "scripts/round/merge_against_baseline.py": "the D3 merge and reconciliation",
        "scripts/round/round_figures.py": "the five headline figures",
        "src/ark/baseline.py": "which baseline the figures mean",
        "scripts/round/orq.py": "the open research questions builder",
    }
    try:
        with tarfile.open(snapshot) as tf:
            names = {n.lstrip("./") for n in tf.getnames()}
    except (tarfile.TarError, OSError) as exc:
        say("D1 runnable code snapshot", f"FAIL  unreadable: {exc}")
        fail = True
    else:
        absent = [f"{k} ({v})" for k, v in wanted.items() if k not in names]
        if absent:
            say("D1 runnable code snapshot", f"FAIL  missing {'; '.join(absent)}")
            fail = True
        else:
            say("D1 runnable code snapshot", f"PASS  {len(names):,} files, all key ones present")

# --- 6 (D2): the experience summary ------------------------------------------
# He named several things it must cover. Checking for each by name is crude and is
# exactly right here: the failure it catches is a summary that quietly drops one of
# them, which reads as complete.
summary = Path("experience-summary.md")
if not summary.is_file():
    say("D2 experience summary", "FAIL  experience-summary.md is missing")
    fail = True
else:
    text = summary.read_text(encoding="utf-8").lower()
    required = {
        "what worked": ("what worked", "successful"),
        "what did not": ("did not work", "unsuccessful"),
        "measured yields": ("yield", "per megabyte"),
        "limitations": ("limitation",),
        "lessons": ("lesson",),
        "reusable techniques": ("techniqu", "reusable"),
        "recommended directions": ("recommend", "direction"),
    }
    absent = [k for k, words in required.items() if not any(w in text for w in words)]
    words = len(text.split())
    if absent:
        say("D2 experience summary", f"FAIL  says nothing about {', '.join(absent)}")
        fail = True
    elif words < 300:
        say("D2 experience summary", f"FAIL  only {words} words, not a summary")
        fail = True
    else:
        say("D2 experience summary", f"PASS  {words:,} words, all seven topics covered")

# --- 7 (D3): the merge, the overlap, the increment, the reconciliation -------
audits = sorted(Path("audit").glob("merge_audit_ark*.json")) if Path("audit").is_dir() else []
audit = None
if not audits:
    say("D3 merge audit and reconciliation", "FAIL  no audit/merge_audit_ark*.json")
    fail = True
else:
    audit = json.loads(audits[-1].read_text(encoding="utf-8"))
    checks = audit.get("reconciliation", [])
    bad = [c for c in checks if not c.get("passed")]
    if not checks:
        say("D3 merge audit and reconciliation", "FAIL  the audit carries no checks")
        fail = True
    elif bad:
        say("D3 merge audit and reconciliation", f"FAIL  {len(bad)} of {len(checks)} failed")
        for c in bad[:3]:
            print(f"{'':<46}       {c['check']}: {c['detail']}")
        fail = True
    else:
        totals = audit["totals"]
        say(
            "D3 merge audit and reconciliation",
            f"PASS  {len(checks)} checks, overlap "
            f"{int(totals['already_in_baseline_records']):,}, increment "
            f"{int(totals['accepted_new_records']):,} records",
        )
        # The audit's own submitted count must equal what the archive actually ships,
        # or the audit describes a different round than the one in the box.
        shipped = 0
        for year in range(1996, 2002):
            for path in (
                Path("additions") / f"{year}.txt",
                Path("hostnames") / f"{year}_hostnames.txt",
            ):
                if path.is_file():
                    shipped += len({x.strip() for x in path.read_text().splitlines() if x.strip()})
        claimed = int(totals["submitted_records"])
        if shipped != claimed:
            say(
                "D3 audit agrees with the shipped files",
                f"FAIL  audit says {claimed:,} submitted, additions/ and hostnames/ hold {shipped:,}",
            )
            fail = True
        else:
            say("D3 audit agrees with the shipped files", f"PASS  {shipped:,} records both sides")

# --- 8 (D4): his calculator runs here and reproduces the audit ---------------
# The strongest check in this file, because it re-derives a number rather than
# comparing two of our own statements. His program needs no third-party packages, so
# a reviewer can run it with the python3 already required above.
calc = Path("equivalent_english_domain_calculator/equivalent_english_domains.py")
if not calc.is_file():
    say("D4 metric reproduces from his calculator", "FAIL  the calculator is not in this archive")
    fail = True
elif audit is None:
    say("D4 metric reproduces from his calculator", "SKIP  no merge audit to compare against")
else:
    # `original/` is the FIRST baseline, not the one the figures mean, so it must not
    # be the file this check picks up.
    baselines = [
        b for b in sorted(Path("baseline").glob("*/1996.txt")) if b.parent.name != "original"
    ]
    expected = next(
        (r["baseline_equivalent_english"] for r in audit["years"] if int(r["year"]) == 1996), None
    )
    if not baselines:
        say("D4 metric reproduces from his calculator", "SKIP  no current baseline shipped")
    elif expected is None:
        say("D4 metric reproduces from his calculator", "SKIP  the audit has no 1996 figure")
    else:
        out = Path("audit/_verify_1996")
        try:
            subprocess.run(
                [sys.executable, str(calc), str(baselines[0]), "--output-dir", str(out)],
                check=True,
                capture_output=True,
            )
            got = json.loads((out / "summary.json").read_text())["equivalent_english_domains"]
        except Exception as exc:
            say("D4 metric reproduces from his calculator", f"FAIL  it did not run: {exc}")
            fail = True
        else:
            if Decimal(got) == Decimal(expected):
                say(
                    "D4 metric reproduces from his calculator",
                    f"PASS  1996 baseline scores {Decimal(got):,.4f} on both sides",
                )
            else:
                say(
                    "D4 metric reproduces from his calculator",
                    f"FAIL  his calculator says {got}, the audit says {expected}",
                )
                fail = True
        for leftover in sorted(out.rglob("*"), reverse=True) if out.is_dir() else []:
            leftover.unlink() if leftover.is_file() else leftover.rmdir()
        if out.is_dir():
            out.rmdir()

sys.exit(1 if fail else 0)
PY
# --- 9 (E1): the two open research questions folders -------------------------
# Section IV-A asks for `Open Research Questions/` holding `Open Research Questions.docx`
# with its code, logs, samples and screenshots beside it, and section X for `开放性研究问题/`
# of plain-text answers under six headings. A missing folder fails; no screenshots warns.
python3 - <<'PY' || fail=1
import csv
import gzip
import html
import re
import sys
import zipfile
from pathlib import Path

LABEL = "E1 open research questions"
EN, ZH = Path("Open Research Questions"), Path("开放性研究问题")
QUESTIONS = (
    "How can historical web data from before 1996 be discovered and acquired at scale?",
    "How can the year in which a website existed be determined more accurately?",
)
HEADINGS = (
    "Proposed approaches",
    "Completed related work or tests",
    "Preliminary technical-feasibility findings",
    "Preliminary practical-operability findings",
    "Limitations",
    "Next steps",
)
LABELS = {"Validated", "Tested, not independently verified", "Pending validation"}
problems = [f"{folder}/ is missing" for folder in (EN, ZH) if not folder.is_dir()]


def contents(path):
    """Every byte a reader could see: a .docx is a zip and a .gz is compressed."""
    if path.suffix == ".docx":
        with zipfile.ZipFile(path) as z:
            return b"".join(z.read(name) for name in z.namelist())
    if path.suffix == ".gz":
        return gzip.decompress(path.read_bytes())
    return path.read_bytes()


if not problems:
    docx = EN / "Open Research Questions.docx"
    try:
        with zipfile.ZipFile(docx) as z:
            xml = z.read("word/document.xml").decode("utf-8")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        problems.append(f"{docx} unreadable: {exc}")
        xml = ""
    # A heading can be split across runs, so each paragraph's runs are joined first.
    paragraphs = [
        html.unescape("".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", p)))
        for p in re.findall(r"<w:p[\s>].*?</w:p>", xml, re.S)
    ]
    for question in QUESTIONS:
        if xml and not any(question in p for p in paragraphs):
            problems.append(f"the docx does not ask: {question}")
    answered = 0
    for path in sorted(ZH.glob("*.txt")):
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"{path} is not UTF-8")
            continue
        lines = {line.strip() for line in text.splitlines()}
        answered += bool(text.strip()) and set(HEADINGS) <= lines
    if answered < 2:
        problems.append(f"{answered} .txt answers carry the six headings, not 2")
    tests = EN / "tests.csv"
    if not tests.is_file():
        problems.append("tests.csv is missing")
    else:
        with tests.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        labels = {row.get("label", "") for row in rows}
        if not rows or labels - LABELS:
            problems.append(f"tests.csv labels outside the three: {sorted(labels - LABELS)}")
        for row in rows:
            for column in ("evidence", "code", "logs", "sample"):
                if row.get(column) and not (EN / row[column]).exists():
                    problems.append(f"tests.csv names a missing {row[column]}")
    for path in sorted(p for folder in (EN, ZH) for p in folder.rglob("*")):
        if path.is_symlink():
            problems.append(f"{path} is a link, not a copy")
        elif path.is_file():
            try:
                if b"private/" in contents(path):
                    problems.append(f"{path} names private/")
            except (OSError, zipfile.BadZipFile, EOFError) as exc:
                problems.append(f"{path} unreadable: {exc}")

if problems:
    print(f"{LABEL:<46} FAIL  {'; '.join(problems[:5])}")
    sys.exit(1)
shots = [p for p in (EN / "screenshots").glob("*") if p.is_file()] if (EN / "screenshots").is_dir() else []
print(f"{LABEL:<46} PASS  both folders, both questions, the six headings, three labels")
if not shots:
    print(f"{'':<46}       WARN  no screenshots/ beside the document")
PY

echo
if [ "$fail" -eq 0 ]; then
    echo "All checks passed."
else
    echo "Some checks FAILED (see above)." >&2
fi
exit "$fail"
