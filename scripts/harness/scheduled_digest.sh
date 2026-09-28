#!/usr/bin/env bash
# One digest a day, for launchd to call. `vacation_digest.py` does the work.
#
# The wrapper exists for the same reason the other two do: launchd needs one program with
# a working directory and a log, and the log is where a run that could not reach `gh`
# leaves its reason. It measures nothing and decides nothing.
#
# Usage: bash scripts/harness/scheduled_digest.sh

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

mkdir -p data/logs
LOG="data/logs/scheduled_digest.log"
{
    printf '\n===== digest %s =====\n' "$(date -u '+%F %T UTC')"
    uv run python scripts/harness/vacation_digest.py --write 2>&1
} >> "$LOG"

tail -n 500 "$LOG" > "$LOG.trim" && mv "$LOG.trim" "$LOG"
