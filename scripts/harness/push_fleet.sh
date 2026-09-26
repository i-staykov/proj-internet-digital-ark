#!/usr/bin/env bash
# Commit and push the result lines, lead statuses and snapshot.json this checkout wrote into
# the fleet clone.
#
# A wave picks its slugs from fleet MAIN, so a result line pushed to a feature branch
# strands the verdict and the next wave re-deals settled slugs. `git push -q` with no
# refspec pushes whatever branch the clone is on, so name the branch and refuse.
# The tick and `just bank` both call it; a push that never lands is shouted, not fatal.
#
# Usage: bash scripts/harness/push_fleet.sh <fleet clone> <label>
set -euo pipefail

FLEET="${1:?push_fleet.sh <fleet clone> <label>}"
LABEL="${2:?push_fleet.sh <fleet clone> <label>}"

BR="$(git -C "$FLEET" branch --show-current)"
if [ "$BR" != main ]; then
    echo "fleet clone is on $BR, not main: result lines, lead statuses and snapshot.json uncommitted."
    echo "  A wave picks from main, so a stranded verdict re-deals a settled slug."
    echo "  Check the clone out on main and re-run the sync."
    exit 0
fi
# **A rejected push must never be swallowed**: a queue that still reports settled
# leads as open keeps the generator from refilling it. Fetch, replay our writes onto
# the remote's files, retry, and SHOUT if it never lands. The replay re-runs the
# writer, which reads the drain and not the clone, so a hard reset is safe; this checkout
# is snapshot.json's only writer, so its copy is put back after the reset.
ROOT_FOR_MERGE="$(pwd)"
TMP="${TMPDIR:-/tmp}"
(
    cd "$FLEET" || exit 1
    rm -f "$TMP/ark_snapshot.json"
    [ -f snapshot.json ] && cp snapshot.json "$TMP/ark_snapshot.json" || true
    git add leads 2>/dev/null || true
    [ -f hypotheses.md ] && git add hypotheses.md || true
    [ -f snapshot.json ] && git add snapshot.json || true
    git commit -q -m "Result lines $LABEL" || true
    for attempt in 1 2 3; do
        git push -q origin main 2>/dev/null && exit 0
        echo "fleet push rejected on attempt $attempt, replaying onto the remote"
        # The hypothesis ledger left the fleet with v1 (ark-fleet #83); the replay of
        # its result lines runs only where the file still exists.
        [ -f hypotheses.md ] && cp hypotheses.md "$TMP/ark_result_lines.md" || true
        git fetch -q origin main && git reset -q --hard origin/main
        [ -f "$TMP/ark_snapshot.json" ] && cp "$TMP/ark_snapshot.json" snapshot.json || true
        if [ -f hypotheses.md ] && [ -f "$TMP/ark_result_lines.md" ]; then
            (cd "$ROOT_FOR_MERGE" && uv run python scripts/harness/merge_result_lines.py \
                "$TMP/ark_result_lines.md" "$FLEET/hypotheses.md")
        fi
        (cd "$ROOT_FOR_MERGE" && uv run python scripts/harness/fleet_leads.py \
            data/fleet_findings/incoming --fleet "$FLEET" --write) || true
        git add leads 2>/dev/null || true
        [ -f hypotheses.md ] && git add hypotheses.md || true
        [ -f snapshot.json ] && git add snapshot.json || true
        git commit -q -m "Result lines $LABEL" || true
        sleep $(( attempt * 3 ))
    done
    echo "RESULT LINES NOT PUSHED after three attempts. The fleet queue will over-report"
    echo "  open leads until they land, so the dealer will re-deal settled work."
    exit 1
) || true
