#!/usr/bin/env bash
# Start the RDAP run on the VPS so that it survives the SSH session ending.
#
# **Why a script on the machine rather than a long ssh command.** Three attempts to
# launch a background job through `ssh ... "setsid nohup ... & disown"` produced a
# process that was alive while the connection lasted and gone a minute later. The
# pattern that works is: ship a script, run the script, let the script do its own
# detaching, and verify from a SECOND connection rather than from the one that
# started it. `vps_start_edge.sh` records the same finding for the CDX collector.
#
# Usage, on the VPS: bash scripts/vps_start_rdap.sh <deadline_epoch> [targets] [workers]
#
# **The default target list is Verisign-only and disjoint from the local queue, and
# both halves of that are load-bearing.** This defaulted to `store_vps.txt`, which is
# 8.2 million domains across every registry the store has seen, and on 2026-08-22 it
# was measured running at **1.92 queries a second against the 65 a second the same
# code gets from `.com` alone**: one round had made no progress in thirteen hours.
# That is the failure the runner's own header describes, a slow or dead registry
# blocking the queue, and it is invisible because the job looks alive throughout.
# `vps_disjoint.txt` is `.com` and `.net` only, with the local machine's queue
# subtracted, so the two machines never spend a query on the same name.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

UNTIL="${1:?usage: vps_start_rdap.sh <deadline_epoch> [targets] [workers]}"
TARGETS="${2:-data/raw/rdap/vps_disjoint.txt}"
# Eight rather than sixteen because the local machine is now querying the same
# registry: the runner's header records an accidental 32 concurrent workers at
# Verisign as something to avoid, and 8 plus 16 keeps the pair under that.
WORKERS="${3:-8}"

pkill -9 -f 'rdap_novel_ru[n]' 2>/dev/null
pkill -9 -f '[a]rk rdap' 2>/dev/null
sleep 3
rm -rf data/logs/rdap_novel.lock

setsid env ARK_RDAP_NOVEL="$TARGETS" \
    nohup bash scripts/rdap_novel_run.sh "$UNTIL" 200000 "$WORKERS" \
    > data/logs/rdap_boot.log 2>&1 < /dev/null &

sleep 20
echo "targets $TARGETS, workers $WORKERS"
echo "supervisors: $(pgrep -f 'rdap_novel_ru[n]' | wc -l)"
tail -3 data/logs/rdap_novel.log 2>/dev/null || tail -5 data/logs/rdap_boot.log 2>/dev/null
