#!/usr/bin/env bash
# One unattended pass of the health check, for a scheduler to call.
#
# `just cycle` is the thing that notices what a program cannot decide: an idle
# collector, an unbanked journal, a stale queue, a yield that has gone to zero.
# Nothing here acts on what it finds, deliberately. This is a scheduled *reporter*,
# not a watchdog: a loop that restarted collectors on its own would eventually
# restart one with settings that had since been retuned, which is the failure the
# supervisor/watchdog collapse in `extend_engines.sh` exists to prevent.
#
# It appends to `data/logs/scheduled_cycle.log` and keeps the last 2,000 lines, so
# an agent returning after a day away reads one file to learn what happened while
# it was gone.
#
# Usage: bash scripts/harness/scheduled_cycle.sh

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

mkdir -p data/logs
LOG="data/logs/scheduled_cycle.log"

{
    printf '\n===== scheduled cycle %s =====\n' "$(date -u '+%F %T UTC')"
    just cycle 2>&1
    printf -- '----- engines -----\n'
    bash scripts/engines/engine_status.sh 2>&1
} >> "$LOG"

# Keep the log readable rather than complete: the store and the journals are the
# record, this is a noticeboard.
tail -n 2000 "$LOG" > "$LOG.trim" && mv "$LOG.trim" "$LOG"
