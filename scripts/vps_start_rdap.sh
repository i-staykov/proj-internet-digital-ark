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
# Usage, on the VPS: bash scripts/vps_start_rdap.sh <deadline_epoch>

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

UNTIL="${1:?usage: vps_start_rdap.sh <deadline_epoch>}"
TARGETS="${2:-data/raw/rdap/store_vps.txt}"

pkill -9 -f 'rdap_novel_ru[n]' 2>/dev/null
pkill -9 -f '[a]rk rdap' 2>/dev/null
sleep 3
rm -rf data/logs/rdap_novel.lock

setsid env ARK_RDAP_NOVEL="$TARGETS" \
    nohup bash scripts/rdap_novel_run.sh "$UNTIL" 200000 16 \
    > data/logs/rdap_boot.log 2>&1 < /dev/null &

sleep 20
echo "supervisors: $(pgrep -f 'rdap_novel_ru[n]' | wc -l)"
tail -3 data/logs/rdap_novel.log 2>/dev/null || tail -5 data/logs/rdap_boot.log 2>/dev/null
