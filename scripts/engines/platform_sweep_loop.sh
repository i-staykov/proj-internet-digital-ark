#!/usr/bin/env bash
# Keep one archive client busy until the deadline, refilling its own queue, and
# never let one parent hold the slot.
#
# Why this exists, beside platform_sweep.sh: that script walks a fixed file and
# prints "queue walked". When the file runs out the process EXITS, and nothing
# notices. On 2026-09-05 that left one of the two client slots dead for 17 hours
# while the other ground a parent worth 211 capture rows per host. Half capacity
# on the worst target in the set.
#
# So the queue is refilled here rather than supplied once, and each parent runs
# under a time cap. The cap is the part that matters: the ranker divides by
# capture rows per host, but `rows_per_host.tsv` holds 339 parents out of
# thousands, so for most of the queue the divisor is unmeasured and the ranking
# degrades to "sub-hosts we lack" alone. That is precisely the metric that put
# `com.au` first at 210.98 rows per host. Depth cannot be known before asking,
# so it is bounded after: a parent over PARENT_CAP is parked, not finished, and
# the sweep's own state file means the work already done is kept.
#
# Parking measures the thing the ranker was missing, so parked parents are worth
# re-reading later with a real cost attached rather than being lost.
#
# **300 seconds, measured, not 600.** The ranked queue interleaves big institutional
# namespaces (.edu, .gov, .ac.uk) because they have the most sub-hosts we lack, and
# their cost is unmeasured so nothing discounts them. At a 600s cap a run of them cut
# collection to 0.33 journals per minute; at 300s the same stretch ran at 1.0, three
# times the parent throughput. Nothing is lost by cutting earlier: the sweep is
# resumable and the round's own law is that breadth pays where depth does not.
#
# The two-clients maximum is unchanged. This runs at most twice, once per queue
# half, and each instance holds one slot.
#
# Usage: bash scripts/engines/platform_sweep_loop.sh <deadline_epoch> <parents_file> <shard 0|1>
set -uo pipefail
cd "$(dirname "$0")"
while [ ! -d data/raw ] && [ "$PWD" != "/" ]; do cd ..; done

DEADLINE="${1:?absolute epoch deadline}"
PARENTS="${2:?parents file}"
SHARD="${3:-0}"
PARENT_CAP="${ARK_PARENT_CAP:-300}"
SWEEP="scripts/engines/cdx_suffix_sweep.py"
[ -f "$SWEEP" ] || SWEEP="scripts/cdx_suffix_sweep.py"
RANKER="scripts/engines/rank_platform_parents.py"
DEEP="data/raw/cdx/platform_deep.txt"

sweep_one() {
    local parent="$1" safe="${parent//./_}"
    [ -e "data/raw/cdx_suffix/suffix_${safe}.done" ] && return 0
    echo "=== $parent ==="
    uv run python "$SWEEP" "$parent" --deadline "$DEADLINE" --delay 2.0 &
    local pid=$! waited=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep 10
        waited=$(( waited + 10 ))
        [ "$waited" -lt "$PARENT_CAP" ] && continue
        # deep namespace. park it: the shallow parents behind it in the queue
        # are each worth more per request than the rest of this one.
        echo "$parent: over ${PARENT_CAP}s, deep namespace, parked"
        echo "$parent" >> "$DEEP"
        kill -TERM "$pid" 2>/dev/null
        # the wrapper is `uv run python`, so the python child needs killing too
        pgrep -f "$SWEEP $parent " | while read -r child; do kill -TERM "$child" 2>/dev/null; done
        sleep 3
        kill -KILL "$pid" 2>/dev/null
        pgrep -f "$SWEEP $parent " | while read -r child; do kill -KILL "$child" 2>/dev/null; done
        return 0
    done
    wait "$pid" 2>/dev/null || {
        echo "$parent: sweep exited non-zero, moving on"
        echo "$parent" >> data/raw/cdx/platform_retry.txt
    }
}

refill() {
    # Ask the ranker for parents this queue has not already burned. Sharded by
    # parity so the two clients never converge on the same parent, which would
    # be worse than idling: it spends the scarce slot on rows the other client
    # is already fetching.
    #
    # **Read the ranker's --out FILE, never its stdout.** It prints only its top
    # 15 as a human summary and writes the ranked list to the file. Piping stdout
    # asked 20,000 parents' worth of ranking and got 15, all of them long since
    # swept, so refill reported "found nothing" and both clients sat idle with a
    # full pool on disk. That cost about an hour of collection on 2026-09-05.
    [ -f "$RANKER" ] || return 1
    local ranked="data/raw/cdx/ranked_shard${SHARD}.txt"
    uv run python "$RANKER" --net-new --top 20000 --out "$ranked" >/dev/null 2>&1 || return 1
    [ -s "$ranked" ] || return 1
    awk -v s="$SHARD" 'NF && $1 !~ /^#/ {n++; if (n % 2 == s) print $1}' "$ranked" > "$PARENTS.refill" || return 1
    awk 'NR==FNR {seen[$0]=1; next} !seen[$0]' "$PARENTS" "$PARENTS.refill" \
        | while IFS= read -r p; do
            [ -e "data/raw/cdx_suffix/suffix_${p//./_}.done" ] || grep -qxF "$p" "$DEEP" 2>/dev/null || echo "$p"
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
    line=$(( line + 1 ))
    parent="$(sed -n "${line}p" "$PARENTS")"
    if [ -z "$parent" ]; then
        if refill; then continue; fi
        echo "queue empty and refill found nothing, waiting"
        line=$(( line - 1 ))
        sleep 300
        continue
    fi
    sweep_one "$parent"
done
echo "deadline reached"
