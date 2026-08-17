#!/usr/bin/env bash
# Ask the registry about the candidate pool, straight at the authoritative servers.
#
# `ark gaps --creation` addresses only domains that ALREADY hold a year: it looks
# for a missing year adjacent to a held one. The candidate pool is the other
# population, names held with no year at all, and it had never been asked until
# 2026-08-08. A creation date landing in window gives such a name its first year,
# which makes it a net-new DOMAIN rather than only a net-new pair.
#
# **This does not compete with the CDX engines.** They are metered against
# `web.archive.org`; this talks to the registries. The two run side by side,
# which is the whole reason this is worth doing while the engines are saturated.
#
# **One process, not shards.** `ark rdap` now routes each domain to its own
# registry from the IANA bootstrap file and paces each registry with its own
# adaptive governor, so concurrency lives inside the process and separate shard
# processes would only fight each other for the same governor-less pace. The old
# version of this script started four processes against `rdap.org`; that route
# refused 18.8% of its queries at 0.83 q/s, and the direct route measured 75 q/s
# with zero refusals over 2,400 queries.
#
# Batching exists for resume, not for pacing. Every run rescans the journal
# directory at start to skip settled domains, which is cheap now and gets dearer
# as the journals grow, so batches are large. A killed batch loses nothing: the
# journal is renamed on the way out and its answers are skipped next time.
#
# Usage: bash scripts/rdap_pool_sweep.sh [batches] [per-batch] [workers] [delay] [min-delay]
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

BATCHES="${1:-6}"
LIMIT="${2:-100000}"
WORKERS="${3:-32}"
# Pacing, because one registry per pace does not fit all of them. Verisign
# sustained 118 q/s with no refusals, so the defaults are its settings. PIR is the
# opposite and the register got it wrong: it was read as "blocks rather than
# throttles" after 403 for 9,253 consecutive requests, when in fact 1,334 paced
# queries drew zero refusals. Pass a slower pace for a registry that meters.
DELAY="${4:-0.02}"
MIN_DELAY="${5:-0.002}"
LIST="${LIST:-data/raw/rdap/pool_targets_verisign.txt}"

if [ ! -s "$LIST" ]; then
    echo "missing $LIST, run scripts/build_rdap_pool_list.py first" >&2
    exit 1
fi

mkdir -p data/logs
echo "sweeping $BATCHES batches x $LIMIT queries at $WORKERS workers over $LIST"

# **A batch that hangs must not hang the sweep, and this had no guard until
# 2026-08-13.** On that day a `.uk` batch froze at exactly 2,000 of 5,000 queries and
# sat there for two hours and forty minutes with the process alive, its own progress
# line degrading from 1.00 to 4.87 seconds per domain. `supervise_cdx_pool.sh` has
# argued the case since the beginning: presence is not progress, so the test is journal
# growth rather than a PID. The CDX engine got that watchdog and this one never did,
# which is why the failure landed here.
#
# Bytes are a sound growth test at this pace even though gzip buffers, because a
# 15-minute window at 1 q/s writes roughly 190 KB. It would not be sound for a fast
# registry, where CHECK should be raised rather than the test changed.
POLL="${POLL:-60}"
CHECK="${CHECK:-900}"

journal_bytes() {
    # The run writes `.part` and renames on exit, so both names have to be tried.
    for f in "$1" "$1.part"; do
        if [ -f "$f" ]; then
            wc -c < "$f" | tr -d ' '
            return
        fi
    done
    echo 0
}

# Killing the wrapper is not killing the run. `uv run` spawns a python child, and on
# 2026-08-13 a `pkill -f` took the wrapper while the child carried on querying, so the
# stall survived its own remedy. Children first, then the parent.
stop_batch() {
    pkill -P "$1" 2>/dev/null
    kill "$1" 2>/dev/null
    sleep 3
    pkill -9 -P "$1" 2>/dev/null
    kill -9 "$1" 2>/dev/null
    wait "$1" 2>/dev/null
}

for i in $(seq 1 "$BATCHES"); do
    stamp=$(date -u '+%Y%m%dT%H%M%SZ')
    out="data/raw/rdap/rdap_pool_${stamp}.jsonl.gz"
    echo "[$(date -u '+%H:%M:%S')] batch $i/$BATCHES -> $out"
    uv run ark rdap "$LIST" -n "$LIMIT" --workers "$WORKERS" \
        --delay "$DELAY" --min-delay "$MIN_DELAY" --timeout 20 --out "$out" \
        >> "data/logs/rdap_pool_sweep.log" 2>&1 &
    pid=$!

    last=-1
    waited=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep "$POLL"
        # It finished during that sleep. Not stalled, and its journal is already
        # renamed, so falling through to the size check would read the wrong thing.
        kill -0 "$pid" 2>/dev/null || break
        waited=$(( waited + POLL ))
        [ "$waited" -lt "$CHECK" ] && continue
        waited=0
        now=$(journal_bytes "$out")
        if [ "$now" -le "$last" ]; then
            echo "[$(date -u '+%H:%M:%S')] stalled: journal bytes ${last} -> ${now}, killing batch $i"
            stop_batch "$pid"
            break
        fi
        last="$now"
    done
    wait "$pid" 2>/dev/null

    # A killed batch still publishes what it had, so an empty journal means the run
    # could not start or the list is exhausted. Either way, stop rather than spin.
    [ -s "$out" ] || { echo "no journal written, stopping"; break; }
done

echo "sweep finished. Ingest with:"
echo "  uv run ark ingest rdap_snapshot data/raw/rdap/rdap_pool_*.jsonl.gz"
