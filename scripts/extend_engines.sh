#!/usr/bin/env bash
# Move the unattended engines onto a later deadline without stopping any of them now.
#
# Every long-running loop here takes an absolute epoch and exits at it, which is
# deliberate: a runaway collector is worse than a stopped one, and a deadline is the
# one guarantee that survives the agent losing its context. The cost is that widening
# the window means restarting, and restarting a healthy collector throws work away:
# `supervise_cdx_pool.sh` kills the batch in flight and its `.part` is discarded, so a
# restart 20 minutes into a 55-minute batch costs those 20 minutes for nothing.
#
# So this restarts nothing. It waits for each loop to reach its own deadline and exit,
# then starts exactly one replacement on the new one. The handover costs a single batch
# gap and happens whether or not anyone is awake for it.
#
# **It cannot make a second copy.** Each waiter re-checks the process table immediately
# before launching and stands down if anything already holds the slot, so a second run
# of this script, or a hand-started collector in the meantime, wins. The patterns are
# bracketed because `pgrep -f` matches the caller's own command line otherwise, which
# has twice reported the opposite of the truth here; a bracketed pattern cannot match
# the literal text of itself.
#
# This is not a watchdog and must not become one. It performs one handover per engine
# and exits. A loop that restarts a collector whenever it is absent would eventually
# restart it with settings that have since been retuned, which is the reason the
# supervisor/watchdog pair was collapsed into one process in the first place.
#
# Usage: bash scripts/extend_engines.sh <deadline_epoch> [rdap_batches]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:?usage: extend_engines.sh <deadline_epoch> [rdap_batches]}"
RDAP_BATCHES="${2:-70}"
NOW="$(date +%s)"

if [ "$DEADLINE" -le "$NOW" ]; then
    echo "deadline $DEADLINE is not in the future" >&2
    exit 1
fi

LOG="data/logs/extend_engines.log"
mkdir -p data/logs
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

human() { date -u -d "@$1" '+%F %T UTC' 2>/dev/null || date -u -r "$1" '+%F %T UTC'; }

# Block until nothing matches the pattern, then run the command once, if and only if
# the slot is still empty. $1 label, $2 bracketed pattern, rest is the command.
handover() {
    local label="$1" pattern="$2"
    shift 2
    while pgrep -f "$pattern" >/dev/null 2>&1; do sleep 60; done
    # Re-check rather than trust the loop above: minutes may have passed, and starting
    # a second copy is the one failure this script must never produce.
    if pgrep -f "$pattern" >/dev/null 2>&1; then
        note "handover ${label}: slot taken again, standing down"
        return 0
    fi
    note "handover ${label}: starting on deadline $(human "$DEADLINE")"
    nohup "$@" >/dev/null 2>&1 </dev/null &
    disown
    note "handover ${label}: pid $!"
}

note "extend: three engines to $(human "$DEADLINE"), rdap ${RDAP_BATCHES} batches"

# The candidate-pool CDX engine, which is the discovery half. Same prefix and same
# target list, because the queue file is rebuilt in place by `just cycle` and the
# supervisor re-reads it every batch.
(
    handover cdx_pool 'supervise_cdx_poo[l]' \
        env ARK_TARGETS=data/raw/cdx/queue_pool_local.txt ARK_PREFIX=cdx_pool \
        caffeinate -i bash scripts/supervise_cdx_pool.sh "$DEADLINE" 600 8 900 0.5 0.15 3.0 70
) &

# The discovery loop: ingests, rebuilds derived lists, checks yield, reports.
(
    handover discover_cycle 'discover_cycl[e]' \
        caffeinate -i uv run python scripts/discover_cycle.py --until "$DEADLINE" --every 3600
) &

# The registry sweep. It takes a batch count rather than a deadline and stops early
# when the target list runs out, so the count is sized to overshoot the window.
(
    handover rdap_sweep 'rdap_pool_swee[p]' \
        caffeinate -i bash scripts/rdap_pool_sweep.sh "$RDAP_BATCHES" 5000 2 1.0 1.0
) &

wait
note "extend: all handovers settled"
