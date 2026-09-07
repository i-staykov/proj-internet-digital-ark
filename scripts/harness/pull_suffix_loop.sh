#!/usr/bin/env bash
# Bring the VPS sweep's journals home and fold them, on a loop.
#
# **The gap this closes.** `maintain.sh` rsyncs `cdx_*` and `rdap_*` and not
# `cdx_suffix_*`, which is the one thing the platform sweep actually writes. That
# pull lives inside `just bank`, a long episodic recipe nobody runs on a loop, so
# on 2026-09-07 the VPS held 1,093 sweep journals that no local pass could see
# and the store's EE could not move however hard the VPS worked.
#
# Collection that never reaches the store is not collection. This is the smallest
# loop that fixes it: pull, ingest, sleep.
#
# **Journals a sweep still holds open are excluded**, by reading the sweeper's own
# open file descriptors on the VPS. A half-copied journal was once ledgered at a
# third of its rows and had to be re-ingested by hand, and the content-hash ledger
# only helps if the file it hashed was complete.
#
# Usage: bash scripts/harness/pull_suffix_loop.sh [iterations] [sleep_seconds]
set -uo pipefail
cd "$(dirname "$0")"
while [ ! -d data/raw ] && [ "$PWD" != "/" ]; do cd ..; done

ITERATIONS="${1:-200}"
SLEEP="${2:-600}"
LOG="data/logs/pull_suffix.log"
mkdir -p "$(dirname "$LOG")" data/raw/cdx_suffix

[ -f local.env ] && . ./local.env
: "${ARK_VPS:?set ARK_VPS (user@host) in local.env}"
VPS_REPO="${ARK_VPS_REPO:-/projects/proj-internet-digital-ark}"

say() { echo "$(date '+%H:%M:%S') | $*" >> "$LOG"; }

for i in $(seq 1 "$ITERATIONS"); do
    before=$(ls data/raw/cdx_suffix/*.jsonl.gz 2>/dev/null | wc -l | tr -d ' ')

    # the journals the remote sweepers currently have open, by fd, not by guesswork
    BUSY=$(ssh -o ConnectTimeout=15 -o BatchMode=yes "$ARK_VPS" \
        'for p in $(pgrep -f cdx_suffix_sweep.py); do ls -l /proc/$p/fd 2>/dev/null | grep -o "suffix_[^ /]*jsonl.gz"; done; true' \
        2>/dev/null | sort -u)

    rsync -a --ignore-existing --timeout=180 \
        -e "ssh -o ConnectTimeout=15 -o BatchMode=yes" \
        $(for b in $BUSY; do echo "--exclude=$b"; done) \
        "$ARK_VPS:$VPS_REPO/data/raw/cdx_suffix/suffix_*.jsonl.gz" data/raw/cdx_suffix/ \
        >> "$LOG" 2>&1 || say "pass $i: vps unreachable, will retry"

    # **Pull the markers too, not only the journals.** A `.done` marker and a line in
    # `platform_deep.txt` are how the ranker knows a parent has already been asked
    # domain-wide. They live only on the VPS, so the laptop's ranking treated 6,937
    # already-swept parents as fresh on 2026-09-07 and queued a head that resolved to
    # "already walked" in under a minute. The markers are empty files; copying them is free.
    rsync -a --ignore-existing --timeout=120 \
        -e "ssh -o ConnectTimeout=15 -o BatchMode=yes" \
        "$ARK_VPS:$VPS_REPO/data/raw/cdx_suffix/suffix_*.done" data/raw/cdx_suffix/ \
        >> "$LOG" 2>&1 || true
    rsync -a --timeout=120 \
        -e "ssh -o ConnectTimeout=15 -o BatchMode=yes" \
        "$ARK_VPS:$VPS_REPO/data/raw/cdx/platform_deep.txt" data/raw/cdx/vps_deep.txt \
        >> "$LOG" 2>&1 || true

    after=$(ls data/raw/cdx_suffix/*.jsonl.gz 2>/dev/null | wc -l | tr -d ' ')
    say "pass $i: journals $before -> $after (held open remotely: $(echo "$BUSY" | grep -c . || echo 0))"

    if [ "$after" -gt "$before" ]; then
        uv run ark ingest-hostnames data/raw/cdx_suffix/ 2>&1 | tail -1 >> "$LOG"
    fi
    sleep "$SLEEP"
done
say "pull loop finished after $ITERATIONS passes"
