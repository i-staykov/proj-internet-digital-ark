#!/usr/bin/env bash
# The one lock a sync holds, whoever started it.
#
# The hourly wrapper held a lock and a hand-run `just sync` held nothing, so the two ran
# together: measured 2026-09-09, a terminal recovering two waves and the launchd job at :05
# were in the store at the same time, one of them lost `ark export` to a lock conflict, and
# the journal ACK was skipped. Both paths now take THIS lock, inside the recipe, so the lock
# is where the work is rather than around one of the two ways of starting it.
#
# mkdir is the atomic primitive macOS has without flock: the directory either appears for us
# or exists already. The pid inside says who holds it, so a lock left by a killed run is
# stale and taken over rather than blocking the lane until someone notices.
#
#   bash scripts/harness/sync_lock.sh take $$   0 taken, 3 held by a live sync, 1 broken
#   bash scripts/harness/sync_lock.sh drop      always 0
#
# ARK_SYNC_LOCK moves the lock, for the tests.

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

LOCK="${ARK_SYNC_LOCK:-data/logs/.sync.lock}"

case "${1:-}" in
take)
    pid="${2:?take needs the pid that will hold it}"
    mkdir -p "$(dirname "$LOCK")"
    if ! mkdir "$LOCK" 2>/dev/null; then
        holder=$(cat "$LOCK/pid" 2>/dev/null || true)
        if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
            since=$(ps -o etime= -p "$holder" 2>/dev/null | tr -d ' ')
            echo "a sync is already running as pid $holder, ${since:-unknown} in. This one stops"
            echo "  here: two syncs in the store is how an export loses its lock and an ingest"
            echo "  half finishes. Nothing was changed. Run it again when that one is done."
            exit 3
        fi
        rm -rf "$LOCK" && mkdir "$LOCK" || exit 1
        echo "took over a lock left by pid ${holder:-unknown}, which is no longer running"
    fi
    echo "$pid" > "$LOCK/pid"
    exit 0
    ;;
drop)
    rm -rf "$LOCK"
    exit 0
    ;;
holder)
    # Who has it, for a status line. Prints nothing and exits 1 when it is free.
    holder=$(cat "$LOCK/pid" 2>/dev/null || true)
    [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null || exit 1
    echo "$holder"
    ;;
*)
    echo "sync_lock: take <pid> | drop | holder" >&2
    exit 2
    ;;
esac
