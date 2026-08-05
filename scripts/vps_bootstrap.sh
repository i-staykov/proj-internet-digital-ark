#!/usr/bin/env bash
# Bring a second collecting machine up, in one command, inside tmux.
#
# Run this on the REMOTE box after `git clone` and after the bundle from
# `scripts/make_vps_bundle.sh` has been copied to ~/ark-bundle.tar.gz. It syncs
# the environment, unpacks the shard list and the journal history, and starts the
# supervisor. Everything slow happens inside tmux, so the session can be detached
# and the VPN dropped immediately.
#
# The journal history is not optional. Roughly 9,500 domains in each shard were
# already answered before the split, and a machine that cannot see those journals
# re-asks every one of them: about sixteen hours of a week-long run spent
# rediscovering answers we already hold.
#
# Nothing here opens the database. Collection writes journals and never touches
# the store, which is the only reason a second machine needs no synchronisation
# at all: bring its journals home at the end and replay them.
#
# Usage, on the remote machine:
#   bash scripts/vps_bootstrap.sh <deadline_epoch> [shard_file] [workers]
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"

DEADLINE="${1:?need a deadline epoch, e.g. 1786276800 for Sun 9 Aug 12:00 UTC}"
SHARD="${2:-data/raw/cdx/gap_shard1.txt}"
# Deliberately below the 8 this project runs locally. A second address is a second
# rate-limit budget, not permission to double the load: the archive has refused
# this project outright three times, and section VI of the brief treats a rate
# limit as a signal to adapt. Start low, watch `failed_403`, raise it after a
# clean day.
WORKERS="${3:-4}"
BUNDLE="${BUNDLE:-$HOME/ark-bundle.tar.gz}"

echo "== syncing the environment =="
uv sync --quiet

echo "== unpacking the shard list and journal history =="
[ -f "$BUNDLE" ] || { echo "missing $BUNDLE; copy it over first"; exit 1; }
mkdir -p data/raw/cdx
tar -xzf "$BUNDLE" -C .
journals=$(find data/raw/cdx -name 'cdx_*.jsonl.gz' | wc -l | tr -d ' ')
targets=$(wc -l < "$SHARD" | tr -d ' ')
echo "   $journals journals for the resume scan, $targets domains in $SHARD"
[ "$journals" -gt 0 ] || { echo "no journals unpacked: the run would re-ask ~9,500 settled domains"; exit 1; }

echo "== starting the supervisor until $(date -u -d "@$DEADLINE" 2>/dev/null || date -u -r "$DEADLINE") =="
ARK_TARGETS="$SHARD" ARK_PREFIX=cdx_gap_vps \
    nohup bash scripts/supervise_cdx_pool.sh "$DEADLINE" 1200 "$WORKERS" 900 > /dev/null 2>&1 &
sleep 8

echo "== check =="
pgrep -fl "supervise_cdx_pool" || { echo "supervisor did not start"; exit 1; }
tail -3 data/logs/cdx_gap_vps.log
echo
echo "Running. Safe to detach (Ctrl-B then D) and drop the VPN."
echo "Journals accumulate at data/raw/cdx/cdx_gap_vps_*.jsonl.gz; nothing else needs doing here."
