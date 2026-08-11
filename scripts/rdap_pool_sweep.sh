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

for i in $(seq 1 "$BATCHES"); do
    stamp=$(date -u '+%Y%m%dT%H%M%SZ')
    out="data/raw/rdap/rdap_pool_${stamp}.jsonl.gz"
    echo "[$(date -u '+%H:%M:%S')] batch $i/$BATCHES -> $out"
    uv run ark rdap "$LIST" -n "$LIMIT" --workers "$WORKERS" \
        --delay "$DELAY" --min-delay "$MIN_DELAY" --timeout 20 --out "$out" \
        >> "data/logs/rdap_pool_sweep.log" 2>&1
    # nothing left to query, or the run could not start: stop rather than spin
    [ -s "$out" ] || { echo "no journal written, stopping"; break; }
done

echo "sweep finished. Ingest with:"
echo "  uv run ark ingest rdap_snapshot data/raw/rdap/rdap_pool_*.jsonl.gz"
