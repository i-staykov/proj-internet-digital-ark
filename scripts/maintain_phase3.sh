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

VPS="${ARK_VPS:-digga@10.1.0.6}"
VPS_REPO="${ARK_VPS_REPO:-/projects/proj-internet-digital-ark}"

for i in $(seq 1 "$ITERATIONS"); do
    echo "$(date '+%F %T') pass ${i}" >> "$LOG"

    # Fetch the other machine's journals before ingesting anything, because work
    # that is still on the VPS appears in no number measured here. Leaving this to
    # a human has failed twice: 5,793 year-records sat remote for a day and a half
    # in July, and 1,500 queries sat remote overnight on 7 August while a monitor
    # with a stale filename glob reported everything home.
    #
    # `--ignore-existing` never rewrites a journal already here, and a failure is
    # not fatal: the VPN is often down, and a pass that cannot reach the VPS should
    # still fold in everything local. `-o BatchMode=yes` so a missing key fails fast
    # rather than blocking the loop on a password prompt.
    rsync -a --ignore-existing --timeout=120 \
        -e "ssh -o ConnectTimeout=15 -o BatchMode=yes" \
        "${VPS}:${VPS_REPO}/data/raw/cdx/cdx_*.jsonl.gz" data/raw/cdx/ \
        >> "$LOG" 2>&1 || echo "  vps unreachable this pass, continuing" >> "$LOG"

    bash scripts/ingest_new_usenet.sh auto >> "$LOG" 2>&1

    # Re-offer every Usenet journal on disk, not only the ones this pass split.
    # Ledgering is by content hash, so an already-ingested journal is skipped in
    # milliseconds and this costs nothing; what it buys is that a journal
    # orphaned by a failed ingest gets picked up on the next pass instead of
    # sitting on disk forever. That happened on 1 August: two journals holding
    # 92 archives' worth of work were written, failed to ingest against a locked
    # store, and nothing would have offered them again.
    for journal in data/raw/usenet/usenet_dated_*.jsonl.gz; do
        [ -e "$journal" ] || continue
        uv run ark ingest usenet_dated "$journal" >> "$LOG" 2>&1
    done
    for journal in data/raw/usenet/usenet_candidates_*.jsonl.gz; do
        [ -e "$journal" ] || continue
        uv run ark ingest usenet_candidates "$journal" >> "$LOG" 2>&1
    done

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

    # Registry journals, which this loop did not know about until 8 August. The
    # RDAP sweep of the candidate pool wrote 19,705 in-window creation dates,
    # roughly 12,000 equivalent-English, and every one of them sat unread on disk
    # because nothing here looked. A collector whose journals no loop ingests is
    # a collector whose work is invisible to every measurement taken afterwards,
    # which is the same failure the VPS journals caused twice.
    for journal in data/raw/rdap/rdap_*.jsonl.gz; do
        [ -e "$journal" ] || continue
        uv run ark ingest rdap_snapshot "$journal" >> "$LOG" 2>&1
    done

    sleep "$PAUSE"
done
echo "$(date '+%F %T') maintenance loop finished" >> "$LOG"
