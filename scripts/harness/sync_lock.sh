#!/usr/bin/env bash
# The one lock a sync holds, whoever started it.
#
# A lock around only one way of starting a sync lets a hand run and the hourly job meet in
# the store, where one loses `ark export` to a lock conflict and the journal ACK is skipped.
# Both paths take THIS lock, inside the recipe, so the lock is where the work is rather than
# around one of the two ways of starting it.
#
# mkdir is the atomic primitive macOS has without flock: the directory either appears for us
# or exists already. The pid and boot id inside say who holds it, so a lock left by a killed
# run or before a reboot (whose pid this boot may give anyone) is stale and taken over rather
# than blocking the lane until someone notices; one with no boot id is judged on its pid.
#
#   bash scripts/harness/sync_lock.sh take $$   0 taken, 3 held by a live sync, 1 broken
#   bash scripts/harness/sync_lock.sh drop      always 0
#
# ARK_SYNC_LOCK moves the lock, for the tests.

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

LOCK="${ARK_SYNC_LOCK:-data/logs/.sync.lock}"
BOOT=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)  # empty on macOS, as is every lock's

# The holder's pid while it runs in this boot.
live() {
    [ -n "$1" ] && kill -0 "$1" 2>/dev/null || return 1
    [ ! -f "$LOCK/boot" ] || [ "$(cat "$LOCK/boot")" = "$BOOT" ]
}

case "${1:-}" in
take)
    pid="${2:?take needs the pid that will hold it}"
    mkdir -p "$(dirname "$LOCK")"
    if ! mkdir "$LOCK" 2>/dev/null; then
        holder=$(cat "$LOCK/pid" 2>/dev/null || true)
        if live "$holder"; then
            since=$(ps -o etime= -p "$holder" 2>/dev/null | tr -d ' ')
            echo "a sync is already running as pid $holder, ${since:-unknown} in. This one stops"
            echo "  here: two syncs in the store is how an export loses its lock and an ingest"
            echo "  half finishes. Nothing was changed. Run it again when that one is done."
            exit 3
        fi
        rm -rf "$LOCK" && mkdir "$LOCK" || exit 1
        echo "took over a lock left by pid ${holder:-unknown}, which no longer runs in this boot"
    fi
    echo "$BOOT" > "$LOCK/boot"
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
    live "$holder" || exit 1
    echo "$holder"
    ;;
*)
    echo "sync_lock: take <pid> | drop | holder" >&2
    exit 2
    ;;
esac
