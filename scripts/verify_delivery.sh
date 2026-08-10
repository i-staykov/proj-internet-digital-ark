#!/usr/bin/env bash
# Check a delivery archive without unpacking the source snapshot or installing
# anything: coreutils and python3 are the only requirements. It ships at the
# root of the archive as `verify.sh`, because `just` and the project's
# dependencies live inside source/ and are not available until a reviewer has
# already decided to trust the contents.
#
# Three checks, each printed with its own verdict:
#   1. every file matches SHA256SUMS
#   2. the six annual addition files, with their pair counts
#   3. every one of those pairs is present in the evidence manifest
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

# Checks 4, 5 and 6 are gone with the standard they policed. They verified that
# `additions_english/` was a subset of the additions, that it partitioned them
# against `additions_unverified/`, and that every rejection in `disqualified.csv`
# carried a reason. The reviewer retired the page-level English standard in August
# 2026, the archive stopped shipping all three files, and the checks then printed
# three SKIP lines about folders that no longer exist. A check that examines
# nothing reads like a check that found nothing wrong, which is worse than not
# having it. `legacy/src/language.py` holds the engine.
PY

echo
if [ "$fail" -eq 0 ]; then
    echo "All checks passed."
else
    echo "Some checks FAILED (see above)." >&2
fi
exit "$fail"
