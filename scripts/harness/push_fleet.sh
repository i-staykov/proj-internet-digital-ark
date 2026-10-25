#!/usr/bin/env bash
# Commit and push the lead statuses, ledger lines and snapshot.json this checkout wrote
# into the fleet clone.
#
# A leg picks its slug from fleet MAIN, so a lead status pushed to a feature branch
# strands the verdict and the next leg re-deals settled slugs. `git push -q` with no
# refspec pushes whatever branch the clone is on, so name the branch and refuse.
# The tick and `just bank` both call it; a push that never lands is shouted, not fatal.
#
# With --snapshot it first writes the staged snapshot's claim into the clone's snapshot.json,
# and exits non-zero unless fleet main holds it after the push.
#
# Usage: bash scripts/harness/push_fleet.sh <fleet clone> <label> [--snapshot]
set -euo pipefail

FLEET="${1:?push_fleet.sh <fleet clone> <label>}"
LABEL="${2:?push_fleet.sh <fleet clone> <label>}"
SNAPSHOT="${3:-}"

BR="$(git -C "$FLEET" branch --show-current)"
if [ "$BR" != main ]; then
    echo "fleet clone is on $BR, not main: statuses, ledger and snapshot.json uncommitted."
    echo "  A leg picks from main, so a stranded verdict re-deals a settled slug."
    echo "  Check the clone out on main and re-run the sync."
    [ "$SNAPSHOT" = --snapshot ] && exit 1
    exit 0
fi
if [ "$SNAPSHOT" = --snapshot ]; then
    uv run python scripts/harness/snapshot_manifest.py --out output/fleet_snapshot \
        --publish-expected "$FLEET"
fi
# **A rejected push must never be swallowed**: a queue that still reports settled
# leads as open keeps the generator from refilling it. Fetch, replay our writes onto
# the remote's files, retry, and SHOUT if it never lands. The replay re-runs the
# writer, which reads the drain and not the clone, so a hard reset is safe; this checkout
# is snapshot.json's only writer, so its copy is put back after the reset.
#
# **The ledger lines are replayed from the clone itself**, so none waits for its writer to
# run again. The lines this clone added are read off its own commits before the fetch moves
# origin/main, and appended again after the reset, kind by kind, through the fleet's keyed
# append, which adds none the remote already holds.
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
    rm -f "$TMP/ark_snapshot.json"
    [ -f snapshot.json ] && cp snapshot.json "$TMP/ark_snapshot.json" || true
    git add leads 2>/dev/null || true
    git add ledger 2>/dev/null || true
    [ -f snapshot.json ] && git add snapshot.json || true
    git commit -q -m "Fleet sync $LABEL" || true
    for attempt in 1 2 3; do
        git push -q origin main 2>/dev/null && exit 0
        echo "fleet push rejected on attempt $attempt, replaying onto the remote"
        git diff --no-color --no-ext-diff origin/main HEAD -- ledger 2>/dev/null \
            | sed -n 's/^+{/{/p' > "$TMP/ark_ledger_lines.jsonl" || true
        git fetch -q origin main && git reset -q --hard origin/main
        [ -f "$TMP/ark_snapshot.json" ] && cp "$TMP/ark_snapshot.json" snapshot.json || true
        if [ -s "$TMP/ark_ledger_lines.jsonl" ]; then
            (cd "$ROOT_FOR_MERGE" && uv run python -c "$REPLAY" \
                "$HERE" "$FLEET" "$TMP/ark_ledger_lines.jsonl") || true
        fi
        (cd "$ROOT_FOR_MERGE" && uv run python scripts/harness/fleet_leads.py \
            data/fleet_findings/incoming --fleet "$FLEET" --write) || true
        git add leads 2>/dev/null || true
        git add ledger 2>/dev/null || true
        [ -f snapshot.json ] && git add snapshot.json || true
        git commit -q -m "Fleet sync $LABEL" || true
        sleep $(( attempt * 3 ))
    done
    echo "FLEET SYNC NOT PUSHED after three attempts. The fleet queue will over-report"
    echo "  open leads until they land, so the dealer will re-deal settled work."
    exit 1
) || true
[ "$SNAPSHOT" != --snapshot ] || git -C "$FLEET" show origin/main:snapshot.json 2>/dev/null \
    | cmp -s - "$FLEET/snapshot.json"
