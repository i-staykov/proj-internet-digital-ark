#!/usr/bin/env bash
# What launchd starts for the collector lane: `caffeinate -s`, then the supervisor.
#
# `caffeinate -s` is the point of this wrapper. The lane is hours of two-second-delayed
# requests, and an idle-sleeping laptop stops it silently: the sweep does not die, it just
# stops being scheduled, and the round loses the window without a single error line. The
# assertion is held for the lifetime of the command it wraps, so it covers the whole
# supervisor rather than one sweep. On battery macOS may still sleep, which is correct: the
# lane is worth a plugged-in machine, not a flat one.
#
# It re-execs ITSELF under caffeinate rather than naming caffeinate in the plist, so the
# plist stays the same two-element shape as the other jobs and the template test can read it.
#
# Usage: bash scripts/harness/scheduled_collectors.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

if [ "${ARK_CAFFEINATED:-}" != "1" ]; then
    export ARK_CAFFEINATED=1
    exec caffeinate -s /bin/bash "$0" "$@"
fi

mkdir -p data/logs
{
    printf '\n===== scheduled collectors %s =====\n' "$(date -u '+%F %T UTC')"
    bash scripts/harness/collectors.sh run
    printf '===== supervisor exited %s =====\n' "$(date -u '+%F %T UTC')"
} >> data/logs/collectors.log 2>&1
