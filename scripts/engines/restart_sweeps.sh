#!/usr/bin/env bash
# Restart the two archive collectors on a new deadline, reusing the queue shards on disk.
#
# **It does not rank anything**, despite what this line said until 2026-09-09: it takes the
# shard files as they are, and re-ranking is `rank_platform_parents.py` run deliberately
# beforehand. The title claimed otherwise for a day, which is exactly the kind of comment
# that gets believed instead of read.
#
# Why this exists as a script rather than three commands: the two-clients rule is the one
# invariant that must hold across the restart, so the stop is verified before either start
# and the count is verified after. Run it on the VPS as the collector user.
#
# **Expect it to start ONE loop, not two, and that is the correct outcome.** A sweep whose
# loop has been stopped keeps its journal open until its current parent is walked, so it is
# still one of the two clients the rule allows. Measured 2026-09-09: the stop left `dal.ca`
# running, the budget was therefore 1, and one loop was started. The orphan then finishes
# with nothing behind it, so the freed slot has to be refilled or the fleet quietly runs at
# half capacity for the rest of the window. Re-run this, or wait for the slot and start the
# missing shard directly.
#
# Usage:  bash scripts/engines/restart_sweeps.sh [deadline_epoch] [queue_prefix]
# Default deadline is 04:00Z tomorrow, which outlives any run planned tonight.
set -uo pipefail

DEADLINE="${1:-$(date -u -d 'tomorrow 04:00' +%s 2>/dev/null || python3 -c 'import datetime;d=datetime.datetime.now(datetime.UTC).replace(hour=4,minute=0,second=0,microsecond=0)+datetime.timedelta(days=1);print(int(d.timestamp()))')}"
PREFIX="${2:-data/raw/cdx/queue_shard}"
REPO="${ARK_REPO:-/projects/proj-internet-digital-ark}"
cd "$REPO" || { echo "no $REPO" >&2; exit 1; }

for shard in 0 1; do
    [ -s "${PREFIX}${shard}.txt" ] || { echo "missing ${PREFIX}${shard}.txt" >&2; exit 1; }
done

# One client is `uv run` PLUS its python child, so a process count doubles it. A client is
# identified by the journal it holds open, which is also how `just engines` counts.
clients() {
    for p in $(pgrep -f cdx_suffix_sweep.py 2>/dev/null); do
        ls -l /proc/"$p"/fd 2>/dev/null | grep -o "suffix_[^ /]*jsonl.gz"
    done | sort -u
}

echo "stopping both collectors"
systemctl --user stop ark-sweep0.service ark-sweep1.service 2>/dev/null

# **Give the children time, then count CLIENTS, not processes.** The first version of this
# slept 5 s and counted processes: measured 2026-09-08, the healthy pair read as "4 sweep
# processes after the stop", the script refused to start anything, and one sweep was left
# orphaned with no loop to continue it. Half capacity, silently.
waited=0
while [ "$waited" -lt 60 ]; do
    [ -z "$(clients)" ] && break
    sleep 10
    waited=$(( waited + 10 ))
done

# **An orphan does not have to cost the whole restart.** A sweep whose loop is gone keeps
# its journal until its parent is walked, and it is still one of the two clients the rule
# allows. So start only as many loops as the budget leaves, and say which parent is holding
# the other slot, rather than refusing everything.
surviving=$(clients | wc -l | tr -d ' ')
budget=$(( 2 - surviving ))
if [ "$surviving" -gt 0 ]; then
    echo "surviving after the stop, holding a slot each:"
    clients | sed 's/^/  /'
fi
if [ "$budget" -le 0 ]; then
    echo "no room under the two-client rule; nothing started. Re-run when one finishes" >&2
    exit 1
fi

started=0
for shard in 0 1; do
    [ "$started" -ge "$budget" ] && break
    systemd-run --user --unit="ark-sweep${shard}" --quiet \
        --working-directory="$REPO" \
        /usr/bin/env bash scripts/engines/platform_sweep_loop.sh \
        "$DEADLINE" "${PREFIX}${shard}.txt" "$shard" \
        || { echo "could not start ark-sweep${shard}" >&2; exit 1; }
    started=$(( started + 1 ))
    sleep 2
done
echo "started $started of the two loops"

sleep 20
clients=$(clients | wc -l | tr -d ' ')
echo "deadline $(date -u -d "@$DEADLINE" '+%F %HZ' 2>/dev/null || echo "$DEADLINE")"
echo "archive clients with a journal open: ${clients:-0} (the rule allows 2)"
systemctl --user list-units 'ark-sweep*' --no-legend 2>/dev/null | head -3
