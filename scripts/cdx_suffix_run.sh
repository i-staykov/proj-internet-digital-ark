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

# Round 1 walked the list above. These are the unswept high-weight namespaces,
# ordered by English share times expected in-window volume: .au 0.9904,
# .nz 0.9895, .uk 0.9813, .za 0.9682, .us 0.9261. The `.us` locality tree is the
# long one, and it is schools, towns and libraries rather than authorities, which
# is the population the store is least saturated on.
SUFFIXES_R2=(
    org.uk net.uk
    co.nz org.nz school.nz
    org.au net.au edu.au
    co.za org.za ac.za
    k12.wa.us k12.ga.us k12.nj.us k12.mn.us k12.mo.us k12.wi.us k12.in.us
    k12.tn.us k12.az.us k12.co.us k12.md.us k12.sc.us k12.ky.us k12.al.us
    state.ca.us state.wa.us state.oh.us state.mi.us state.va.us state.nc.us
    lib.tx.us lib.fl.us lib.oh.us lib.pa.us cc.ca.us cc.tx.us
)

# ARK_SUFFIXES overrides the list, space separated. Fixed at startup like every
# other collector target, so editing it mid-run changes nothing.
if [ -n "${ARK_SUFFIXES:-}" ]; then
    # shellcheck disable=SC2206
    SUFFIXES=(${ARK_SUFFIXES})
elif [ -n "${ARK_SUFFIX_ROUND2:-}" ]; then
    SUFFIXES=("${SUFFIXES_R2[@]}")
fi

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
        # The archive refuses connections in bursts, so a failed control means
        # "not this second", not "not this namespace". Without this retry a
        # 3-second refusal costs the suffix its whole slice and the next attempt
        # is a full round away, which is how `org.uk` and `co.nz`, the two
        # biggest, went unswept for a day. Three tries, then move on.
        for try_n in 1 2 3; do
            uv run python scripts/cdx_suffix_sweep.py "$s" --deadline "$end" \
                --page-size 200 --delay 2.0 >> "$LOG" 2>&1
            tail -1 "$LOG" | grep -q "control failed" || break
            [ "$(date +%s)" -ge "$end" ] && break
            note "  control refused, retry $try_n in 45s"
            sleep 45
        done
    done
done

note "suffix sweep finished after $round round(s)"
