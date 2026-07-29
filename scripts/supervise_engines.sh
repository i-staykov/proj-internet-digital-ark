#!/usr/bin/env bash
# Keep both verification engines fed for an unattended stretch.
#
# Each engine runs as a bounded batch, so a batch loop eventually exhausts its
# count and the engine goes idle. This re-dispatches whichever is idle, which
# matters because collection is the scored work and idle hours are lost pairs.
#
# The pgrep patterns match "bin/ark <cmd>", the real venv process, rather than
# "ark <cmd>", which would also match this script's own command line and make
# every engine look permanently busy.
set -uo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"

RUN_FOR_SECONDS="${1:-47000}"
CDX_WORKERS="${2:-4}"
# Seconds between RDAP requests. 0.05 (20/s) drew 7,895 rate-limit responses on
# 2026-07-28 and the registries then refused connections outright for hours, so
# the pace is now a parameter with a defensible default. Registry notices state
# that bulk query access from a single source is detected and limited.
RDAP_DELAY="${3:-0.5}"
END=$(( $(date +%s) + RUN_FOR_SECONDS ))

# Only dispatch against a service that is actually answering. Section VI treats
# rate limits and gateway errors as signals to adapt rather than to abandon a
# route, and the adaptation that matters at this level is not queuing more work
# against a host that has stopped accepting connections: on 2026-07-26
# web.archive.org began refusing us outright while rdap.org stayed healthy, and
# without this check the loop would have spent hours generating pure failures.
reachable() {
    curl -sS -o /dev/null --max-time 15 --head "$1" 2>/dev/null
}

while [ "$(date +%s)" -lt "$END" ]; do
    if ! pgrep -f "bin/ark cdx" >/dev/null; then
        if reachable https://web.archive.org/; then
            echo "$(date +%H:%M:%S) dispatching cdx batch (${CDX_WORKERS} workers)"
            ( uv run ark cdx data/raw/cdx/gap_candidates.txt \
                -n 1200 --workers "$CDX_WORKERS" --timeout 70 >> data/logs/cdx_longrun.log 2>&1 & )
        else
            echo "$(date +%H:%M:%S) web.archive.org unreachable, holding cdx"
        fi
    fi
    if ! pgrep -f "bin/ark rdap" >/dev/null; then
        echo "$(date +%H:%M:%S) dispatching rdap batch (delay ${RDAP_DELAY}s)"
        ( uv run ark rdap data/raw/rdap/creation_candidates.txt \
            -n 2500 --delay "$RDAP_DELAY" >> data/logs/rdap_longrun.log 2>&1 & )
    fi
    sleep 120
done
echo "$(date +%H:%M:%S) supervisor window closed"
