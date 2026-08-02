#!/usr/bin/env bash
# Keep the language supervisor alive and, more importantly, keep it *working*.
#
# The supervisor already handles the failures it can see: it batches, it backs
# off when the circuit breaks, and it stops when the work list empties. What it
# cannot do is notice that it has died, or that it is running and producing
# nothing. Both have to be caught from outside.
#
# **A liveness check on the process is not enough**, and that is the whole
# reason this exists. A batch that hangs on a socket leaves the supervisor alive
# and the journal frozen, which a PID check reports as healthy. The archive has
# refused this project three times, twice overnight, so the expensive failure is
# precisely the quiet one: eight hours of an alive process classifying nothing.
#
# So the test is progress, not presence. If the newest journal has not grown
# between two checks, the run is treated as stalled and restarted.
#
# Every intervention is logged with a timestamp, because a restart is evidence
# about the archive's behaviour and belongs in the record.
#
# The engine settings are parameters, not constants. They were hardcoded here,
# which meant any retune of the supervisor would be silently reverted the first
# time the watchdog restarted it, and the log would show a rate that no longer
# matched the settings anyone believed were running.
#
# Usage: bash scripts/watchdog_lang.sh [check_seconds] [deadline_epoch] [batch] [workers] [min_delay]
set -uo pipefail

INTERVAL="${1:-600}"
DEADLINE="${2:-0}"
BATCH="${3:-400}"
WORKERS="${4:-2}"
MIN_DELAY="${5:-1.5}"
LOG="data/logs/lang_watchdog.log"
DIR="data/raw/lang"
mkdir -p data/logs

# Restart with the same window the supervisor was given, recomputed each time
# from the deadline so a restart never runs past it.
restart() {
    local remaining=$(( DEADLINE - $(date +%s) ))
    if [ "$remaining" -le 60 ]; then
        echo "$(date '+%F %T') deadline reached, not restarting" >> "$LOG"
        return 1
    fi
    nohup bash scripts/supervise_lang.sh "$remaining" "$BATCH" "$WORKERS" "$MIN_DELAY" \
        > /dev/null 2>&1 &
    echo "$(date '+%F %T') restarted supervisor for ${remaining}s" \
        "(batch=${BATCH} workers=${WORKERS} min_delay=${MIN_DELAY})" >> "$LOG"
    return 0
}

# Total bytes across finished journals plus whatever the in-flight `.part` has
# written. The `.part` is what moves between checks; finished journals only
# change when a batch ends, so watching them alone would report a stall for the
# whole of a long batch.
progress() {
    cat <(find "$DIR" -maxdepth 1 -name 'lang_*.jsonl.gz*' -type f -exec stat -f '%z' {} + 2>/dev/null) \
        | awk '{s += $1} END {print s + 0}'
}

[ "$DEADLINE" -eq 0 ] && DEADLINE=$(( $(date +%s) + 176000 ))
last=$(progress)
echo "$(date '+%F %T') watchdog start: every ${INTERVAL}s until $(date -r "$DEADLINE" '+%F %T')" \
    "(batch=${BATCH} workers=${WORKERS} min_delay=${MIN_DELAY})" >> "$LOG"

while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    sleep "$INTERVAL"

    if ! pgrep -f "supervise_lang.sh" > /dev/null 2>&1; then
        echo "$(date '+%F %T') supervisor absent" >> "$LOG"
        restart || break
        last=$(progress)
        continue
    fi

    now=$(progress)
    if [ "$now" -le "$last" ]; then
        echo "$(date '+%F %T') stalled: journal bytes ${last} -> ${now}, killing and restarting" >> "$LOG"
        pkill -f "supervise_lang.sh" > /dev/null 2>&1
        pkill -f "ark lang" > /dev/null 2>&1
        sleep 5
        restart || break
    fi
    last=$(progress)
done

echo "$(date '+%F %T') watchdog done" >> "$LOG"
