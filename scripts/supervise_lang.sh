#!/usr/bin/env bash
# Run `ark lang` in bounded batches for a long stretch, politely.
#
# Batches rather than one long run, for two reasons. A finished batch renames
# its journal, so completed work becomes ingestable while the next batch is
# still going; and the pause between batches gives web.archive.org a gap, which
# matters because this engine sends up to three requests per pair and the
# archive refused us outright on 1 August when it did not get one.
#
# The engine has its own circuit breaker: 25 consecutive failures ends a batch.
# If that keeps happening the archive is declining our traffic, so the backoff
# here lengthens rather than retrying at the same pace.
#
# Usage: bash scripts/supervise_lang.sh <seconds> [batch] [workers] [min_delay]
set -uo pipefail

DURATION="${1:-28800}"      # default 8 hours
BATCH="${2:-400}"
WORKERS="${3:-2}"
MIN_DELAY="${4:-1.5}"
TARGETS="data/raw/lang/lang_targets.txt"
LOG="data/logs/lang_supervisor.log"

mkdir -p data/logs
deadline=$(( $(date +%s) + DURATION ))
pause=60
batch_no=0

echo "$(date '+%F %T') supervisor start: ${DURATION}s, batch=${BATCH}, workers=${WORKERS}, min_delay=${MIN_DELAY}" >> "$LOG"

while [ "$(date +%s)" -lt "$deadline" ]; do
    batch_no=$(( batch_no + 1 ))
    echo "$(date '+%F %T') batch ${batch_no} start" >> "$LOG"

    output=$(uv run ark lang "$TARGETS" -n "$BATCH" --workers "$WORKERS" \
                --samples 2 --delay 2.0 --min-delay "$MIN_DELAY" 2>&1 | tail -4)
    echo "$output" >> "$LOG"

    if echo "$output" | grep -q "nothing new to classify"; then
        echo "$(date '+%F %T') work list exhausted, stopping" >> "$LOG"
        break
    fi

    # A broken circuit means the archive stopped answering. Back off hard and
    # for longer each time rather than returning at the same pace.
    if echo "$output" | grep -q "circuit_broken"; then
        pause=$(( pause * 2 ))
        [ "$pause" -gt 1800 ] && pause=1800
        echo "$(date '+%F %T') circuit broken, backing off ${pause}s" >> "$LOG"
    else
        pause=60
    fi

    sleep "$pause"
done

echo "$(date '+%F %T') supervisor done after ${batch_no} batches" >> "$LOG"
