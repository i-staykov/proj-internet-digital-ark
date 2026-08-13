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
# **`maintain.sh` is deliberately not here, and that was checked rather than assumed.**
# It is the fourth long-running process and the one that banks everything, so leaving it
# out would be the expensive omission. It takes an iteration count rather than a
# deadline: `maintain.sh 900 150` is 900 passes, and measured on 2026-08-12 it was on
# pass 124 after 18h33m, about 9 minutes a pass, which is roughly 4.8 days of headroom.
# If it is ever started with a smaller count than the window, it needs a handover too.
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

# One armed set at a time. The per-engine guard re-checks the process table just
# before launching, which is enough against a hand-started collector but not against
# a second copy of THIS script: two waiters blocked on the same pattern would both
# see an empty slot in the same instant and both launch. The deadline has already
# been moved twice in one round, so re-arming is a routine operation rather than a
# rare one, and `mkdir` is atomic where a test-then-write is not.
LOCK="data/logs/extend_engines.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    holder=$(cat "$LOCK/pid" 2>/dev/null || echo "unknown")
    if [ "$holder" != "unknown" ] && kill -0 "$holder" 2>/dev/null; then
        echo "already armed by pid ${holder}; stop it first (pkill -f 'extend_engine[s]')" >&2
        exit 1
    fi
    note "clearing a lock whose holder ${holder} is gone"
    rm -rf "$LOCK" && mkdir "$LOCK" || exit 1
fi
printf '%s\n' "$$" > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

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
    # **LIST must be passed explicitly.** `rdap_pool_sweep.sh` defaults to
    # `pool_targets_verisign.txt`, which is almost entirely journalled already, and on
    # 2026-08-13 a hand restart that omitted the variable swept it and reported 147
    # domains to query out of a 5,000 limit. A batch with nothing to do is
    # indistinguishable from an exhausted pool, so the failure is silent. The CDX branch
    # above has always passed its targets through `env` for exactly this reason and this
    # branch did not.
    handover rdap_sweep 'rdap_pool_swee[p]' \
        env LIST=data/raw/rdap/pool_targets_org.txt \
        caffeinate -i bash scripts/rdap_pool_sweep.sh "$RDAP_BATCHES" 5000 2 1.0 1.0
) &

wait
note "extend: all handovers settled"
