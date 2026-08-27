#!/usr/bin/env bash
# Bring VPS journals home and bank them, on a loop, until a deadline.
#
# **Why this exists.** On 2026-08-27 the residual audit reported "rsync 2 VPS journals
# home". Diffing the two machines' file lists directly found 125, worth 40,893.6
# equivalent-English, which was more than every query sent from this machine that night
# put together. Those queries had already been paid for on the other box; the only thing
# missing was the copy. The audit counts what a documented glob matches ON THIS MACHINE,
# so work finished elsewhere is invisible to it, and a number that small reads as
# "nothing to do" rather than as "I cannot see the other machine".
#
# So the diff is the job, and it runs on a timer rather than when somebody remembers.
#
# Three journal shapes, three destinations:
#   data/raw/cdx/cdx_*        -> ingest as `cdx_snapshot` directly
#   data/raw/cdx_suffix/*     -> convert first, which collapses capture rows into
#                                per-domain year sets, then ingest as `cdx_snapshot`
#   data/raw/rdap/rdap_*      -> ingest as `rdap_snapshot`
#
# A live `.part` on the VPS is copied under a `_snap<time>` name rather than its own,
# because the ingest ledger keys on (source, file name) and the real file will publish
# under the plain name when its round ends. Both ingest; the overlap dedups on
# (domain, year), and this is the pattern the local snapshots already use.
#
# Usage: bash scripts/pull_vps_journals.sh <deadline_epoch> [interval_seconds]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:?usage: pull_vps_journals.sh <deadline_epoch> [interval]}"
INTERVAL="${2:-1200}"
VPS="${ARK_VPS:-digga@10.1.0.6}"
VPS_REPO="${ARK_VPS_REPO:-/projects/proj-internet-digital-ark}"
LOG="data/logs/pull_vps.log"
mkdir -p data/logs
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

LOCK="data/logs/pull_vps.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    holder=$(cat "$LOCK/pid" 2>/dev/null || echo "")
    if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
        note "another puller is live (pid $holder); refusing to start a second"
        exit 1
    fi
    rm -rf "$LOCK"; mkdir "$LOCK" 2>/dev/null || exit 1
fi
echo "$$" > "$LOCK/pid"
cleanup() { rm -rf "$LOCK"; }
trap 'cleanup' EXIT
trap 'cleanup; exit 143' TERM
trap 'cleanup; exit 130' INT

note "pulling from $VPS every ${INTERVAL}s until $(date -r "$DEADLINE" '+%F %T %Z' 2>/dev/null || echo "$DEADLINE")"

round=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    round=$((round + 1))
    note "round $round"

    remote=$(mktemp); local_list=$(mktemp); want=$(mktemp)
    if ! ssh -o BatchMode=yes -o ConnectTimeout=15 "$VPS" \
        "cd '$VPS_REPO' && find data/raw -name '*.jsonl.gz' -printf '%p\n'" 2>/dev/null | sort > "$remote"; then
        note "  ssh failed; will retry next round"
        rm -f "$remote" "$local_list" "$want"; sleep "$INTERVAL"; continue
    fi
    find data/raw -name '*.jsonl.gz' 2>/dev/null | sort > "$local_list"
    comm -23 "$remote" "$local_list" > "$want"
    n=$(wc -l < "$want" | tr -d ' ')
    note "  VPS has $(wc -l < "$remote" | tr -d ' '), we have $(wc -l < "$local_list" | tr -d ' '), missing $n"

    if [ "$n" != "0" ]; then
        rsync -a --files-from="$want" "$VPS:$VPS_REPO/" . >> "$LOG" 2>&1 \
            && note "  pulled $n" || note "  rsync failed"

        if grep -q '^data/raw/cdx/cdx_' "$want"; then
            # shellcheck disable=SC2046
            uv run ark ingest cdx_snapshot $(grep '^data/raw/cdx/cdx_' "$want" | tr '\n' ' ') >> "$LOG" 2>&1 \
                && note "  banked the cdx journals" || note "  cdx ingest failed"
        fi
        if grep -q '^data/raw/cdx_suffix/' "$want"; then
            tag="vps$(date -u +%Y%m%dT%H%M%SZ)"
            uv run python scripts/cdx_suffix_convert.py --tag "$tag" >> "$LOG" 2>&1
            journal="data/raw/cdx/cdx_suffix_${tag}.jsonl.gz"
            [ -s "$journal" ] && uv run ark ingest cdx_snapshot "$journal" >> "$LOG" 2>&1 \
                && note "  banked the converted suffix sweep"
        fi
        if grep -q '^data/raw/rdap/rdap_' "$want"; then
            # shellcheck disable=SC2046
            uv run ark ingest rdap_snapshot $(grep '^data/raw/rdap/rdap_' "$want" | tr '\n' ' ') >> "$LOG" 2>&1 \
                && note "  banked the rdap journals" || note "  rdap ingest failed"
        fi
    fi
    rm -f "$remote" "$local_list" "$want"

    # A live `.part` holds work that cannot publish until its round ends, and those
    # rounds run for hours. Snapshot it under a name of its own so it can be banked now.
    ssh -o BatchMode=yes -o ConnectTimeout=15 "$VPS" \
        "cd '$VPS_REPO' && find data/raw/rdap -name 'rdap_*.jsonl.gz.part' -newermt '-6 hours' -printf '%p\n'" 2>/dev/null \
    | while read -r part; do
        [ -z "$part" ] && continue
        base=$(basename "$part" .jsonl.gz.part)
        snap="data/raw/rdap/${base}_snap$(date -u +%Y%m%dT%H%MZ).jsonl.gz"
        scp -o BatchMode=yes -o ConnectTimeout=15 -q "$VPS:$VPS_REPO/$part" "$snap" 2>/dev/null || continue
        uv run ark ingest rdap_snapshot "$snap" >> "$LOG" 2>&1 && note "  snapshotted and banked $base"
    done

    sleep "$INTERVAL"
done
note "deadline reached after $round round(s)"
