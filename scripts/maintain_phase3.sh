#!/usr/bin/env bash
# Fold whatever the collectors have finished into the store, on a loop.
#
# One loop rather than two, because DuckDB takes a single writer and the Usenet
# ingest and the language ingest would otherwise collide at whatever interval
# they happened to share. Serialising them here costs nothing: both are seconds
# of work against hours of collection.
#
# Only COMPLETE journals are ingested. A collector writes `<name>.part` and
# renames on exit, so anything matching `*.jsonl.gz` is finished; ingesting a
# half-written journal would ledger it at a partial hash and make the rest of
# that run permanently unreachable.
#
# Usage: bash scripts/maintain_phase3.sh [iterations] [sleep_seconds]
set -uo pipefail

ITERATIONS="${1:-30}"
PAUSE="${2:-900}"
LOG="data/logs/maintain_phase3.log"
mkdir -p data/logs

for i in $(seq 1 "$ITERATIONS"); do
    echo "$(date '+%F %T') pass ${i}" >> "$LOG"

    bash scripts/ingest_new_usenet.sh auto >> "$LOG" 2>&1

    # Language journals are ledgered by content, so re-offering an ingested one
    # is skipped rather than double counted; no marker file is needed.
    for journal in data/raw/lang/lang_*.jsonl.gz; do
        [ -e "$journal" ] || continue
        uv run ark ingest-lang "$journal" >> "$LOG" 2>&1
    done

    # CDX candidate journals: the same, and this is what turns a discovered name
    # into a net-new domain.
    for journal in data/raw/cdx/cdx_*.jsonl.gz; do
        [ -e "$journal" ] || continue
        uv run ark ingest cdx_snapshot "$journal" >> "$LOG" 2>&1
    done

    sleep "$PAUSE"
done
echo "$(date '+%F %T') maintenance loop finished" >> "$LOG"
