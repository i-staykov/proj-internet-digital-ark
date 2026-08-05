#!/usr/bin/env bash
# Query the candidate pool against the IA CDX index for an unattended stretch.
#
# One process, not the supervisor-plus-watchdog pair the language engine used.
# That pair existed because a supervisor blocked on a batch cannot notice that
# the batch has hung, so a second process had to watch the journal. Here the
# batch is backgrounded and this loop polls it, which gets the same stall
# detection with one PID to anchor `caffeinate` to and no chance of a watchdog
# restarting a supervisor with settings that have since been retuned.
#
# **Presence is not progress.** A batch stuck on a socket leaves the process
# alive and the journal frozen, which a PID check reports as healthy. The archive
# has refused this project outright three times, so the expensive failure is the
# quiet one: hours of an alive process finding nothing. The test is therefore
# journal growth, which is real because `write_journal_line` flushes per record.
#
# The stall window has to clear the archive's own slowest answer. A single CDX
# query has been observed taking 183 seconds to return, so a window near that
# would kill healthy batches; 900s is comfortably clear of it.
#
# **Noticing a finished batch and judging a stalled one are different clocks, and
# conflating them cost 15% of a day's throughput.** The first version slept the
# whole stall window between checks, so a batch that finished early in that window
# was not noticed for up to 900s, and worse, its `.part` had been renamed away by
# then, so the size check read 0 and logged a clean completion as a stall. On
# 4 August every single batch was logged `stalled`, which also skipped the
# exhaustion and backoff branches below, and left roughly 11 idle minutes per
# batch against 50-90 minutes of work. So liveness is polled often (POLL) and
# journal growth is judged rarely (CHECK), and the loop re-tests the PID after
# every sleep, because a dead process cannot be stalled.
#
# Journals are named `cdx_pool_<UTC>` rather than `cdx_<UTC>`. They still match
# the `cdx_*` glob that every ingest command and the engine's own resume scan
# use, so nothing needs teaching about them, while the name still says which
# population the run drew from. The two pools stay separate lists and separate
# journals; only the skip-set is shared, which is what stops either pool from
# re-asking a domain the other already settled.
#
# Usage: bash scripts/supervise_cdx_pool.sh [deadline_epoch] [batch] [workers] [check_seconds]
set -uo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"

DEADLINE="${1:-0}"
BATCH="${2:-1200}"
WORKERS="${3:-8}"
CHECK="${4:-900}"
DELAY="${5:-0.5}"
MIN_DELAY="${6:-0.15}"
# Ceiling below the 5s default on purpose: on 29 July a throttle burst pinned a
# run at 5s and it managed 240 domains/hour for the rest of the batch. Pacing is
# a safety valve, and this workload is latency-bound, so a low ceiling costs
# nothing and buys recovery.
MAX_DELAY="${7:-3.0}"
TIMEOUT="${8:-70}"
# How often to look at whether the batch is still alive. Not a tuning knob: it
# only has to be small against a batch (50-90 min) and against the stall window,
# so that a finished batch is re-dispatched promptly.
POLL=30

# Which population to work, set by the caller rather than baked in. Two disjoint
# lists go to the same index by the same method, so they want one supervisor and
# not two copies that drift apart:
#
#   candidate pool (default), domains with no year at all, a hit adds a NAME
#     ARK_TARGETS=data/raw/cdx/pool_candidates.txt ARK_PREFIX=cdx_pool
#   gap pool, held domains with a bracketed missing year, a hit adds a YEAR
#     ARK_TARGETS=data/raw/cdx/gap_candidates.txt  ARK_PREFIX=cdx_gap
#
# The prefix must start `cdx_` so the journals stay inside the `cdx_*` glob that
# every ingest command and the engine's own resume scan already use. That shared
# skip set is deliberate: neither population should ever re-ask a domain the
# other has already settled.
TARGETS="${ARK_TARGETS:-data/raw/cdx/pool_candidates.txt}"
PREFIX="${ARK_PREFIX:-cdx_pool}"
DIR="data/raw/cdx"
LOG="data/logs/${PREFIX}.log"
# One batch's own output, truncated per dispatch. The exhaustion and backoff
# decisions are read from this and never from a tail of the shared log: a killed
# batch writes no summary of its own, so a tail would still be showing the
# PREVIOUS batch's "nothing new to query" and the loop would stop 90 batches
# early, which is exactly the silent failure this whole script exists to avoid.
BATCH_OUT="data/logs/${PREFIX}_batch.out"
mkdir -p data/logs

[ "$DEADLINE" -eq 0 ] && DEADLINE=$(( $(date +%s) + 86400 ))

note() { echo "$(date '+%F %T') $*" >> "$LOG"; }

journal_bytes() {
    # the in-flight `.part` is what moves; a finished batch leaves the poll loop
    # on its own, so there is no reason to watch anything else
    stat -f '%z' "${JOURNAL}${PART}" 2>/dev/null || echo 0
}

PART=".part"
BATCH_PID=""
JOURNAL=""

dispatch() {
    JOURNAL="$DIR/${PREFIX}_$(date -u +%Y%m%dT%H%M%SZ).jsonl.gz"
    : > "$BATCH_OUT"
    uv run ark cdx "$TARGETS" -n "$BATCH" --workers "$WORKERS" \
        --delay "$DELAY" --min-delay "$MIN_DELAY" --max-delay "$MAX_DELAY" \
        --timeout "$TIMEOUT" --out "$JOURNAL" > "$BATCH_OUT" 2>&1 &
    BATCH_PID=$!
    note "batch dispatched pid=${BATCH_PID} -> ${JOURNAL}"
}

# SIGTERM to `uv run` alone can leave the real process behind, so the pattern
# match is a backstop. It matches "bin/ark cdx", the venv executable, rather than
# "ark cdx", which would also match this script's own command line.
stop_batch() {
    kill "$BATCH_PID" 2>/dev/null
    sleep 5
    pkill -f "bin/ark cdx" 2>/dev/null
    sleep 2
}

trap 'note "supervisor asked to stop"; stop_batch; exit 0' TERM INT

note "start: until $(date -r "$DEADLINE" '+%F %T'), batch=${BATCH} workers=${WORKERS}" \
    "check=${CHECK}s delay=${DELAY}/${MIN_DELAY}/${MAX_DELAY} timeout=${TIMEOUT}"

pause=60
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    dispatch
    stalled=0
    last=-1
    waited=0
    while kill -0 "$BATCH_PID" 2>/dev/null; do
        sleep "$POLL"
        # The batch finished during that sleep. It is not stalled, and its `.part`
        # is already renamed, so falling through to the size check would read 0
        # and misreport a clean completion.
        kill -0 "$BATCH_PID" 2>/dev/null || break
        # a batch may legitimately outlive the deadline; stop it rather than
        # letting the window run over
        if [ "$(date +%s)" -ge "$DEADLINE" ]; then
            note "deadline reached mid-batch, stopping"
            stop_batch
            break 2
        fi
        waited=$(( waited + POLL ))
        [ "$waited" -lt "$CHECK" ] && continue
        waited=0
        now=$(journal_bytes)
        if [ "$now" -le "$last" ]; then
            note "stalled: journal bytes ${last} -> ${now}, restarting batch"
            stop_batch
            stalled=1
            break
        fi
        last="$now"
    done
    wait "$BATCH_PID" 2>/dev/null
    grep -v "domain/s\]" "$BATCH_OUT" >> "$LOG" 2>/dev/null

    # A killed batch reports nothing about the pool, so read neither exhaustion
    # nor health out of it. Just go again.
    if [ "$stalled" -eq 1 ]; then
        sleep 60
        continue
    fi
    if grep -q "nothing new to query" "$BATCH_OUT"; then
        note "pool exhausted, stopping"
        break
    fi
    # A broken circuit or a batch of pure failures means the archive has stopped
    # answering. Back off further each time rather than returning at the pace it
    # just refused.
    if grep -qE "circuit_broken|'queried': 0" "$BATCH_OUT"; then
        pause=$(( pause * 2 ))
        [ "$pause" -gt 1800 ] && pause=1800
        note "archive refusing, backing off ${pause}s"
    else
        pause=60
    fi
    sleep "$pause"
done

note "supervisor done"
