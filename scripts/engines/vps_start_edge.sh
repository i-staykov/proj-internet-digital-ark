#!/usr/bin/env bash
# Start the VPS collector so it survives the SSH session that launched it.
#
# **Why this is a file on the VPS rather than a long ssh one-liner.** Three
# attempts to start it inline failed in three different ways: the process died
# with the session, `setsid ... & disown` inside a quoted remote command started
# something that `ps` never showed, and a `pkill -TERM` released the supervisor's
# own lock without stopping it, so the old shard kept being worked while the new
# one sat unread. A script on the far side is started the same way every time and
# can be read afterwards to see what it actually did.
#
# **The target list is fixed at startup**, which is the property that made the
# stale-shard bug possible: `supervise_cdx_pool.sh` resolves `ARK_TARGETS` once.
# So changing the queue means restarting, and this script always restarts rather
# than trying to be clever about it.
#
# Usage, on the VPS:
#   bash scripts/engines/vps_start_edge.sh <deadline_epoch> [targets] [batch] [workers]

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

DEADLINE="${1:?usage: vps_start_edge.sh <deadline_epoch> [targets] [batch] [workers]}"
TARGETS="${2:-data/raw/cdx/queue_edge_vps.txt}"
BATCH="${3:-600}"
WORKERS="${4:-8}"
LOG="data/logs/vps_start.log"
mkdir -p data/logs

note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

if [ ! -s "$TARGETS" ]; then
    note "target list $TARGETS is missing or empty; refusing to start"
    exit 1
fi

# SIGKILL rather than TERM, deliberately. The supervisor's TERM handler releases
# its lock and keeps running, which is how two collectors ended up on one list.
# A killed batch loses only its `.part`, and `ark cdx` is resumable, so the cost
# is the queries already in flight and nothing else.
pkill -9 -f 'supervise_cdx_pool[.]sh' 2>/dev/null
pkill -9 -f '[a]rk cdx' 2>/dev/null
sleep 5
rm -f data/raw/cdx/*.part

note "starting on $TARGETS ($(wc -l < "$TARGETS" | tr -d ' ') targets), deadline $(date -u -d "@$DEADLINE" '+%F %T UTC' 2>/dev/null || echo "$DEADLINE")"

setsid env ARK_TARGETS="$TARGETS" ARK_PREFIX=cdx_vedge \
    nohup bash scripts/engines/supervise_cdx_pool.sh "$DEADLINE" "$BATCH" "$WORKERS" 900 \
    >> data/logs/cdx_vedge_supervisor.log 2>&1 < /dev/null &

sleep 20
if pgrep -f 'supervise_cdx_poo[l]' > /dev/null; then
    note "running: $(pgrep -f 'supervise_cdx_poo[l]' | tr '\n' ' ')"
else
    note "FAILED to start; see data/logs/cdx_vedge_supervisor.log"
    exit 1
fi
