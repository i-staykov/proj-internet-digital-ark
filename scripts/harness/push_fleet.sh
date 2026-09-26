#!/usr/bin/env bash
# Commit and push the result lines, lead statuses and ledger lines this checkout wrote into
# the fleet clone.
#
# A leg picks its slug from fleet MAIN, so a result line pushed to a feature branch
# strands the verdict and the next leg re-deals settled slugs. `git push -q` with no
# refspec pushes whatever branch the clone is on, so name the branch and refuse.
# The tick and `just bank` both call it; a push that never lands is shouted, not fatal.
#
# Usage: bash scripts/harness/push_fleet.sh <fleet clone> <label>
set -euo pipefail

FLEET="${1:?push_fleet.sh <fleet clone> <label>}"
LABEL="${2:?push_fleet.sh <fleet clone> <label>}"

BR="$(git -C "$FLEET" branch --show-current)"
if [ "$BR" != main ]; then
    echo "fleet clone is on $BR, not main: result lines and lead statuses left uncommitted."
    echo "  A leg picks from main, so a stranded verdict re-deals a settled slug."
    echo "  Check the clone out on main and re-run the sync."
    exit 0
fi
# **A rejected push must never be swallowed**: a queue that still reports settled
# leads as open keeps the generator from refilling it. Fetch, replay our writes onto
# the remote's files, retry, and SHOUT if it never lands. The replay re-runs the
# writer, which reads the drain and not the clone, so a hard reset is safe.
#
# **The ledger lines are replayed from the clone itself**, because the old TSV the legacy
# lines came from is deleted once converted and nothing here could write them again. The
# lines this clone added are read off its own commits before the fetch moves origin/main,
# and appended again after the reset, kind by kind, through the fleet's keyed append,
# which adds none the remote already holds.
ROOT_FOR_MERGE="$(pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="${TMPDIR:-/tmp}"
REPLAY='
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import fleet_ledger
kinds = {}
for text in Path(sys.argv[3]).read_text().splitlines():
    try:
        line = json.loads(text)
    except ValueError:
        continue
    if isinstance(line, dict) and isinstance(line.get("kind"), str):
        kinds.setdefault(line["kind"], []).append(line)
for kind, rows in kinds.items():
    print(f"ledger replay, {kind}: {fleet_ledger.append(Path(sys.argv[2]), kind, rows)[1]}")
'
(
    cd "$FLEET" || exit 1
    git add leads 2>/dev/null || true
    git add ledger 2>/dev/null || true
    [ -f hypotheses.md ] && git add hypotheses.md || true
    git commit -q -m "Result lines $LABEL" || true
    for attempt in 1 2 3; do
        git push -q origin main 2>/dev/null && exit 0
        echo "fleet push rejected on attempt $attempt, replaying onto the remote"
        # The hypothesis ledger left the fleet with v1 (ark-fleet #83); the replay of
        # its result lines runs only where the file still exists.
        [ -f hypotheses.md ] && cp hypotheses.md "$TMP/ark_result_lines.md" || true
        git diff --no-color --no-ext-diff origin/main HEAD -- ledger 2>/dev/null \
            | sed -n 's/^+{/{/p' > "$TMP/ark_ledger_lines.jsonl" || true
        git fetch -q origin main && git reset -q --hard origin/main
        if [ -f hypotheses.md ] && [ -f "$TMP/ark_result_lines.md" ]; then
            (cd "$ROOT_FOR_MERGE" && uv run python scripts/harness/merge_result_lines.py \
                "$TMP/ark_result_lines.md" "$FLEET/hypotheses.md")
        fi
        if [ -s "$TMP/ark_ledger_lines.jsonl" ]; then
            (cd "$ROOT_FOR_MERGE" && uv run python -c "$REPLAY" \
                "$HERE" "$FLEET" "$TMP/ark_ledger_lines.jsonl") || true
        fi
        (cd "$ROOT_FOR_MERGE" && uv run python scripts/harness/fleet_leads.py \
            data/fleet_findings/incoming --fleet "$FLEET" --write) || true
        git add leads 2>/dev/null || true
        git add ledger 2>/dev/null || true
        [ -f hypotheses.md ] && git add hypotheses.md || true
        git commit -q -m "Result lines $LABEL" || true
        sleep $(( attempt * 3 ))
    done
    echo "RESULT LINES NOT PUSHED after three attempts. The fleet queue will over-report"
    echo "  open leads until they land, so the dealer will re-deal settled work."
    exit 1
) || true
