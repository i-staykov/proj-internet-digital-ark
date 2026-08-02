#!/usr/bin/env bash
# Take the collectors down cleanly, fold in everything they produced, and build
# the delivery archive.
#
# This exists because the last twenty minutes before a deadline is exactly when
# a step gets skipped. Every delivery defect this project has shipped came from
# the assembly rather than the collection: an archive whose code did not match
# its data, one whose output/ was 1,513 pairs behind the store, one missing the
# candidate pool. Each of those is now a guard inside package_delivery.sh, and
# this script is the ordering that keeps those guards from firing.
#
# Order matters and is not arbitrary:
#   1. stop collectors, so nothing writes while the store is read
#   2. wait for journals to be renamed off `.part`, or their tail is lost
#   3. ingest everything, including anything orphaned by an earlier failure
#   4. export, then rebuild the two shipped sets from the store
#   5. run the gate, and REFUSE to package if it fails
#   6. package, then verify the archive from the outside
#
# Usage: bash scripts/finalise_delivery.sh [--keep-running]
set -uo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"

KEEP_RUNNING=0
[ "${1:-}" = "--keep-running" ] && KEEP_RUNNING=1

say() { printf '\n=== %s ===\n' "$1"; }

if [ "$KEEP_RUNNING" -eq 0 ]; then
    say "stopping collectors"
    # The watchdog first, or it restarts the supervisor being stopped.
    pkill -f watchdog_lang.sh
    pkill -f supervise_lang.sh
    pkill -f maintain_phase3.sh
    pkill -f fetch_usenet_groups.py
    sleep 2
    pkill -f "ark lang"
    sleep 3

    # A journal is written as `<name>.part` and renamed on clean exit. One that
    # is still `.part` was killed mid-write: everything before the last gzip
    # flush is readable, and ingesting it under its final name would ledger a
    # partial file by content hash and make the rest of that run permanently
    # unreachable. So they are left alone and reported.
    stranded=$(find data/raw -name '*.part' | wc -l | tr -d ' ')
    if [ "$stranded" != "0" ]; then
        echo "note: $stranded journal(s) still .part, not ingested:"
        find data/raw -name '*.part'
    fi
fi

say "ingesting everything outstanding"
for journal in data/raw/lang/lang_*.jsonl.gz; do
    [ -e "$journal" ] || continue
    uv run ark ingest-lang "$journal" 2>&1 | tail -1
done
bash scripts/ingest_new_usenet.sh final 2>&1 | tail -2
for journal in data/raw/usenet/usenet_dated_*.jsonl.gz; do
    [ -e "$journal" ] || continue
    uv run ark ingest usenet_dated "$journal" 2>&1 | tail -1
done
for journal in data/raw/usenet/usenet_candidates_*.jsonl.gz; do
    [ -e "$journal" ] || continue
    uv run ark ingest usenet_candidates "$journal" 2>&1 | tail -1
done

say "exporting"
uv run ark export 2>&1 | tail -1
uv run ark lang-report 2>&1 | tail -12

say "integrity gate"
if ! uv run ark check 2>&1 | tail -3; then
    echo "REFUSING TO PACKAGE: the integrity gate failed" >&2
    exit 1
fi

say "figures for the report and the email"
uv run python scripts/report_figures.py

say "filling the report and the email from those figures"
# Fails loudly on any token it cannot fill, because a report containing the
# literal text [ENGLISH] is worse than one containing a stale number.
uv run python scripts/fill_report.py

say "packaging"
bash scripts/package_delivery.sh 2>&1 | tail -8

say "next"
cat <<'EOF'
Before sending:
  1. `git add -A && git commit` the refilled report and email. package_delivery.sh
     ships `git archive HEAD`, so an uncommitted report is not the report inside
     the archive, and the clean-tree guard will have stopped the packaging above.
  2. Re-run this script with --keep-running so the refill is inside the archive.
  3. Unpack the archive somewhere unrelated to this repo and follow its own
     README literally. That test has found two defects nothing else did.

Edit docs/*.template.md, never docs/*.md: the latter are generated.
EOF
