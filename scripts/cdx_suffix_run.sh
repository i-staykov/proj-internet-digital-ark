#!/usr/bin/env bash
# Sweep several public-suffix namespaces from the Wayback CDX index, on a deadline.
#
# **Why this exists and what it replaces.** Every archive route in this project
# asked about one domain at a time, capping it near 17,500 queries a day. A
# `matchType=domain` query on a public suffix returns captures for every domain
# under it and paginates, so one endpoint walks a whole namespace. Measured
# 2026-08-21: 23 pages in five minutes gave 96,343 capture rows, 1,437 in-window
# pairs, **600 net-new and 588.8 equivalent-English**, at 41.8% net-new.
#
# **Ordered by English weight**, because the metric is equivalent-English and a
# `.co.uk` hit is worth 7.4x a `.de` one. Suffixes below about 0.5 are not worth
# a request while high-weight ones remain.
#
# **One sweep at a time and a polite delay.** This is a heavy client at
# `web.archive.org`, the same host the CDX collectors meter against, so running it
# beside them competes for one rate budget. The engines should be stopped or this
# should be the only heavy client. The Internet Archive has refused this project
# three times.
#
# Usage: bash scripts/cdx_suffix_run.sh <deadline_epoch> [per-suffix seconds]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:?usage: cdx_suffix_run.sh <deadline_epoch> [per_suffix_seconds]}"
SLICE="${2:-3600}"
LOG="data/logs/cdx_suffix.log"
mkdir -p data/logs data/raw/cdx_suffix

# English share of the right-most TLD, which is what the metric pays for.
SUFFIXES=(
    on.ca qc.ca bc.ca sk.ca ns.ca mb.ca nb.ca nf.ca pe.ca nt.ca yk.ca
    k12.ca.us state.tx.us k12.il.us k12.oh.us k12.pa.us k12.mi.us
    k12.ny.us k12.tx.us state.fl.us k12.va.us k12.nc.us k12.ma.us
    lib.ny.us co.la.ca.us lib.ca.us state.ny.us state.pa.us cc.fl.us
    govt.nz asn.au com.ng ac.nz co.in net.nz me.uk id.au
    ie co.il
    com.pk com.ng co.ke
)

note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

LOCK="data/logs/cdx_suffix.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    note "another suffix sweep holds $LOCK; refusing to start a second"
    exit 1
fi
echo "$$" > "$LOCK/pid"
cleanup() { rm -rf "$LOCK"; }
trap 'cleanup' EXIT
trap 'cleanup; exit 143' TERM
trap 'cleanup; exit 130' INT

note "sweeping ${#SUFFIXES[@]} suffixes until $(date -u -r "$DEADLINE" '+%F %T UTC' 2>/dev/null || echo "$DEADLINE")"

round=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    round=$((round + 1))
    note "===== round $round ====="
    for s in "${SUFFIXES[@]}"; do
        now=$(date +%s)
        [ "$now" -ge "$DEADLINE" ] && break
        end=$((now + SLICE))
        [ "$end" -gt "$DEADLINE" ] && end=$DEADLINE
        note "-- $s until $(date -u -r "$end" '+%H:%M:%SZ' 2>/dev/null || echo "$end") --"
        uv run python scripts/cdx_suffix_sweep.py "$s" --deadline "$end" \
            --page-size 200 --delay 2.0 >> "$LOG" 2>&1
    done
done

note "suffix sweep finished after $round round(s)"
