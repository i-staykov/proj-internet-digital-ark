#!/usr/bin/env bash
# Fold whatever the collectors have finished into the store, on a loop.
#
# One loop rather than one per source, because DuckDB takes a single writer and
# two ingest loops would collide at whatever interval they happened to share.
# Serialising them here costs nothing: each is seconds of work against hours of
# collection.
#
# Only COMPLETE journals are ingested. A collector writes `<name>.part` and
# renames on exit, so anything matching `*.jsonl.gz` is finished; ingesting a
# half-written journal would ledger it at a partial hash and make the rest of
# that run permanently unreachable.
#
# Usage: bash scripts/maintain.sh [iterations] [sleep_seconds]
set -uo pipefail

ITERATIONS="${1:-30}"
PAUSE="${2:-900}"
LOG="data/logs/maintain.log"
mkdir -p data/logs

VPS="${ARK_VPS:-digga@10.1.0.6}"
VPS_REPO="${ARK_VPS_REPO:-/projects/proj-internet-digital-ark}"

# One `ark ingest` per SOURCE, not one per file. This is the whole fix for a
# measured problem: the four per-file loops this replaces spawned 636 separate
# invocations per pass at the current file counts, each one opening the store
# read-write, reading the ledger, finding the file already banked and closing. With
# PAUSE at 150s that is 636 write-lock acquisitions every two and a half minutes,
# and the lock was measured **held 16 of 18 samples over 90 seconds, 89%**, on
# 11 August. Every reader queued behind it: the pricer, the state generator, the
# residual auditor, and `ark seed`, which could not get in at all. The log carries
# 7,646 `already ingested, skipping` lines across 6,156 invocations, which is the
# same story counted a second way.
#
# Batching changes nothing about what gets ingested. `ingest_files` sorts the paths
# itself, skips per file from the ledger, and wraps each file in its own
# `try/except` that counts `files_failed` and continues, so a bad file is contained
# exactly as it was before and now shows up in the summary instead of scrolling past
# in a shell loop. It also collapses 636 `record_metrics` rows and 636
# `_enqueue_unverified` passes into one each.
#
# Re-offering every journal on disk stays deliberate and unchanged: ledgering is by
# content hash, so an already-ingested journal costs milliseconds, and it is what
# rescues a journal orphaned by a failed ingest. On 1 August two journals holding 92
# archives' worth of work were written, failed against a locked store, and nothing
# would ever have offered them again.
#
# The one limit to watch is the argument list. 636 paths is roughly 30 KB, far below
# ARG_MAX, but a glob grown into the thousands would need `xargs`: an `ls` over
# 19,231 usenet archives has already overflowed exec once in this project.
ingest_all() {
    local key="$1"
    shift
    # An unmatched glob arrives as the literal pattern, so test the first argument
    # rather than trusting that the shell expanded anything.
    [ -e "$1" ] || return 0
    uv run ark ingest "$key" "$@" >> "$LOG" 2>&1
}

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

    # Every journal on disk is re-offered, not only the ones this pass produced.
    # See `ingest_all` above for why that is cheap and what it rescues.
    ingest_all usenet_dated      data/raw/usenet/usenet_dated_*.jsonl.gz
    ingest_all usenet_candidates data/raw/usenet/usenet_candidates_*.jsonl.gz

    # CDX candidate journals, which is what turns a discovered name into a net-new
    # domain.
    ingest_all cdx_snapshot      data/raw/cdx/cdx_*.jsonl.gz

    # Registry journals, which this loop did not know about until 8 August. The
    # RDAP sweep of the candidate pool wrote 19,705 in-window creation dates,
    # roughly 12,000 equivalent-English, and every one of them sat unread on disk
    # because nothing here looked. A collector whose journals no loop ingests is
    # a collector whose work is invisible to every measurement taken afterwards,
    # which is the same failure the VPS journals caused twice.
    ingest_all rdap_snapshot     data/raw/rdap/rdap_*.jsonl.gz

    sleep "$PAUSE"
done
echo "$(date '+%F %T') maintenance loop finished" >> "$LOG"
