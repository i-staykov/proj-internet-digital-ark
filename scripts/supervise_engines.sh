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
END=$(( $(date +%s) + RUN_FOR_SECONDS ))

while [ "$(date +%s)" -lt "$END" ]; do
    if ! pgrep -f "bin/ark cdx" >/dev/null; then
        echo "$(date +%H:%M:%S) dispatching cdx batch"
        ( uv run ark cdx data/raw/cdx/gap_candidates.txt \
            -n 1200 --workers 8 --timeout 70 >> data/logs/cdx_longrun.log 2>&1 & )
    fi
    if ! pgrep -f "bin/ark rdap" >/dev/null; then
        echo "$(date +%H:%M:%S) dispatching rdap batch"
        ( uv run ark rdap data/raw/rdap/creation_candidates.txt \
            -n 2500 --delay 0.05 >> data/logs/rdap_longrun.log 2>&1 & )
    fi
    sleep 120
done
echo "$(date +%H:%M:%S) supervisor window closed"
