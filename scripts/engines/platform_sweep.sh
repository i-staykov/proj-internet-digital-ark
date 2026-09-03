#!/usr/bin/env bash
# Walk the platform-parent queue with the CDX domain sweep, one parent at a time.
#
# The second archive client slot (beside the vedge gap engine): the gaploc unit
# stands down while this runs, keeping the two-clients maximum. Runs as a plain
# user process with an absolute deadline, the collector convention; resumable,
# because the sweep keeps a per-parent state file and writes a .done marker when
# a parent's namespace is exhausted. Pause: touch /tmp/ark-pause-sweeps.
#
# Usage: bash scripts/engines/platform_sweep.sh <deadline_epoch> [parents_file]
set -uo pipefail
# the VPS working copy keeps scripts/ one level shallower than the repo, so seek
# the project root by its landmark instead of assuming a fixed depth
cd "$(dirname "$0")"
while [ ! -d data/raw ] && [ "$PWD" != "/" ]; do cd ..; done

DEADLINE="${1:?absolute epoch deadline}"
PARENTS="${2:-data/raw/cdx/platform_parents.txt}"
SWEEP="scripts/engines/cdx_suffix_sweep.py"
[ -f "$SWEEP" ] || SWEEP="scripts/cdx_suffix_sweep.py"

while IFS= read -r parent; do
    [ -z "$parent" ] && continue
    [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "deadline reached"; break; }
    safe="${parent//./_}"
    if [ -e "data/raw/cdx_suffix/suffix_${safe}.done" ]; then
        echo "$parent: done marker present, skipping"
        continue
    fi
    echo "=== $parent ==="
    uv run python "$SWEEP" "$parent" --deadline "$DEADLINE" --delay 2.0 || {
        # a refused or throttled parent is queued again rather than lost; walk
        # the retry file once the queue is done
        echo "$parent: sweep exited non-zero, moving on"
        echo "$parent" >> data/raw/cdx/platform_retry.txt
    }
done < "$PARENTS"
echo "queue walked"
