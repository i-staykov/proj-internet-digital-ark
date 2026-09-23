#!/usr/bin/env bash
# The availability engine on the VPS, the third archive client (C-88), in hourly chunks.
#
# Each chunk is one `wayback_availability.py` run to a one-hour deadline, so each hour closes
# its two journals; only then are they moved to `done/`, which is all `availability_home.sh`
# ever fetches, so the laptop never reads a journal still being written. The engine's own
# resume marker carries the queue position from chunk to chunk. Three chunks in a row that
# end inside five minutes mean something is wrong, and the loop stops rather than spinning.
#
# Runs from a standalone directory holding scripts/engines/wayback_availability.py:
#   nohup bash availability_vps_loop.sh <queue file> <end epoch> &
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

QUEUE="${1:?queue file}"
END="${2:?end epoch}"
RUN=data/raw/run
DONE=data/raw/done
mkdir -p "$RUN/exact" "$RUN/host" "$DONE/exact" "$DONE/host" data/logs
quick=0
while [ "$(date +%s)" -lt "$END" ]; do
    start=$(date +%s)
    deadline=$(( start + 3600 )); [ "$deadline" -gt "$END" ] && deadline="$END"
    python3 scripts/engines/wayback_availability.py --deadline "$deadline" \
        --queue-file "$QUEUE" --out "$RUN/exact" --host-out "$RUN/host"
    for kind in exact host; do
        for f in "$RUN/$kind"/*.jsonl.gz; do [ -e "$f" ] && mv "$f" "$DONE/$kind/"; done
    done
    if [ $(( $(date +%s) - start )) -lt 300 ]; then
        quick=$(( quick + 1 ))
        [ "$quick" -ge 3 ] && { echo "three short chunks running, stopping"; exit 1; }
        sleep 60
    else
        quick=0
    fi
done
echo "reached the end epoch"
