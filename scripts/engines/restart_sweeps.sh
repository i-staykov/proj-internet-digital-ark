#!/usr/bin/env bash
# Restart the two archive collectors with a new deadline and a freshly ranked queue.
#
# Why this exists as a script rather than three commands: the two-clients rule is the one
# invariant that must hold across the restart, so the stop is verified before either start
# and the count is verified after. Run it on the VPS as the collector user.
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

echo "stopping both collectors"
systemctl --user stop ark-sweep0.service ark-sweep1.service 2>/dev/null
sleep 5

# **Verify the stop before starting anything.** Three clients on the archive breaches the
# hard rule, and a stale sweep child under a stopped unit is how that happened on
# 2026-09-07. Count DISTINCT parents, not processes: one client is `uv run` plus its child.
left=$(pgrep -f cdx_suffix_sweep.py 2>/dev/null | wc -l | tr -d ' ')
if [ "${left:-0}" -ne 0 ]; then
    echo "still $left sweep processes after the stop; not starting anything" >&2
    exit 1
fi

for shard in 0 1; do
    systemd-run --user --unit="ark-sweep${shard}" --quiet \
        --working-directory="$REPO" \
        /usr/bin/env bash scripts/engines/platform_sweep_loop.sh \
        "$DEADLINE" "${PREFIX}${shard}.txt" "$shard" \
        || { echo "could not start ark-sweep${shard}" >&2; exit 1; }
    sleep 2
done

sleep 20
clients=$(for p in $(pgrep -f cdx_suffix_sweep.py 2>/dev/null); do
    ls -l /proc/"$p"/fd 2>/dev/null | grep -o "suffix_[^ /]*jsonl.gz"
done | sort -u | wc -l | tr -d ' ')
echo "deadline $(date -u -d "@$DEADLINE" '+%F %HZ' 2>/dev/null || echo "$DEADLINE")"
echo "archive clients with a journal open: ${clients:-0} (the rule allows 2)"
systemctl --user list-units 'ark-sweep*' --no-legend 2>/dev/null | head -3
