#!/usr/bin/env bash
# Keep one archive client busy until the deadline, refilling its own queue.
#
# Why this exists, beside platform_sweep.sh: that script walks a fixed file and
# prints "queue walked". When the file runs out the process EXITS, and nothing
# notices. On 2026-09-05 that left one of the two client slots dead for 17 hours
# while the other ground a parent worth 211 capture rows per host. Half capacity
# on the worst target in the set.
#
# So the queue is refilled here rather than supplied once. When the file is
# walked, the ranker is asked for more parents, skipping any with a .done marker
# and any already held. An empty refill is not a reason to exit either: the
# ranker's input grows as the gap engine ingests, so it waits and asks again.
#
# The two-clients maximum is unchanged. This runs at most twice, once per queue
# half, and each instance holds one slot.
#
# Both instances refill from the same ranking, so each takes its own half by
# parity of rank. Without that they would converge on the same top parent and
# sweep it twice, which is worse than idling: it spends the scarce client slot
# on rows the other client is already fetching.
#
# Usage: bash scripts/engines/platform_sweep_loop.sh <deadline_epoch> <parents_file> <shard 0|1>
set -uo pipefail
cd "$(dirname "$0")"
while [ ! -d data/raw ] && [ "$PWD" != "/" ]; do cd ..; done

DEADLINE="${1:?absolute epoch deadline}"
PARENTS="${2:?parents file}"
SHARD="${3:-0}"
SWEEP="scripts/engines/cdx_suffix_sweep.py"
[ -f "$SWEEP" ] || SWEEP="scripts/cdx_suffix_sweep.py"
RANKER="scripts/engines/rank_platform_parents.py"

sweep_one() {
    local parent="$1" safe="${parent//./_}"
    [ -e "data/raw/cdx_suffix/suffix_${safe}.done" ] && return 0
    echo "=== $parent ==="
    uv run python "$SWEEP" "$parent" --deadline "$DEADLINE" --delay 2.0 || {
        echo "$parent: sweep exited non-zero, moving on"
        echo "$parent" >> data/raw/cdx/platform_retry.txt
    }
}

refill() {
    # Ask the ranker for parents this queue has not already burned. Ranked by
    # lack x weight / cost, so a shallow parent outranks a big namespace even
    # when the big one has more absent names.
    [ -f "$RANKER" ] || return 1
    uv run python "$RANKER" --net-new --top 400 2>/dev/null \
        | awk -v s="$SHARD" 'NF && $1 !~ /^#/ {n++; if (n % 2 == s) print $1}' > "$PARENTS.refill" || return 1
    # drop anything finished or already in this queue
    awk 'NR==FNR {seen[$0]=1; next} !seen[$0]' "$PARENTS" "$PARENTS.refill" \
        | while IFS= read -r p; do
            [ -e "data/raw/cdx_suffix/suffix_${p//./_}.done" ] || echo "$p"
        done > "$PARENTS.new"
    if [ -s "$PARENTS.new" ]; then
        cat "$PARENTS.new" >> "$PARENTS"
        echo "refilled with $(wc -l < "$PARENTS.new" | tr -d ' ') parents"
        return 0
    fi
    return 1
}

line=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    while [ -e /tmp/ark-pause-sweeps ]; do sleep 60; done
    line=$((line + 1))
    parent="$(sed -n "${line}p" "$PARENTS")"
    if [ -z "$parent" ]; then
        # queue walked. refill rather than exit, and wait if there is nothing yet
        if refill; then continue; fi
        echo "queue empty and refill found nothing, waiting"
        line=$((line - 1))
        sleep 300
        continue
    fi
    sweep_one "$parent"
done
echo "deadline reached"
