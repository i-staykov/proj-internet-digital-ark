#!/usr/bin/env bash
# Convert and bank suffix-sweep journals on a loop, while the sweep keeps running.
#
# The sweep writes capture rows for days. This turns what it has found into
# `cdx_snapshot` journals and ingests them, so the store tracks the sweep rather
# than waiting for it to finish. A journal on disk is not yet a result.
#
# **Re-reading a growing journal is not wasted work.** Each pass converts every
# capture row seen so far, and the ingest ledger keys on content hash, so a pass
# that adds nothing new is refused cheaply. The alternative, tracking a byte
# offset into a gzip stream, is fragile for no gain at this size.
#
# Usage: bash scripts/cdx_suffix_bank.sh <deadline_epoch> [interval_seconds]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:?usage: cdx_suffix_bank.sh <deadline_epoch> [interval]}"
INTERVAL="${2:-2700}"
LOG="data/logs/cdx_suffix_bank.log"
mkdir -p data/logs

note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

LOCK="data/logs/cdx_suffix_bank.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    note "another banker holds $LOCK"
    exit 1
fi
echo "$$" > "$LOCK/pid"
cleanup() { rm -rf "$LOCK"; }
trap 'cleanup' EXIT
trap 'cleanup; exit 143' TERM
trap 'cleanup; exit 130' INT

note "banking suffix sweeps until $(date -u -r "$DEADLINE" '+%F %T UTC' 2>/dev/null || echo "$DEADLINE")"

round=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    round=$((round + 1))
    tag="s$(date -u +%Y%m%dT%H%M%SZ)"
    note "round $round, tag $tag"

    uv run python scripts/cdx_suffix_convert.py --tag "$tag" >> "$LOG" 2>&1
    journal="data/raw/cdx/cdx_suffix_${tag}.jsonl.gz"
    if [ ! -s "$journal" ]; then
        note "  no journal produced"
    else
        for attempt in $(seq 1 40); do
            if uv run ark ingest cdx_snapshot "$journal" >> "$LOG" 2>&1; then
                break
            fi
            if ! tail -3 "$LOG" | grep -q "Conflicting lock"; then
                note "  ingest failed for a reason that is not the write lock"
                break
            fi
            sleep 45
        done
    fi

    remaining=$((DEADLINE - $(date +%s)))
    [ "$remaining" -le 0 ] && break
    hop=$INTERVAL
    [ "$hop" -gt "$remaining" ] && hop=$remaining
    slept=0
    while [ "$slept" -lt "$hop" ]; do
        sleep 30
        slept=$((slept + 30))
    done
done

note "suffix banker finished after $round round(s)"
