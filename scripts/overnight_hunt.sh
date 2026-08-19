#!/usr/bin/env bash
# The overnight hunt: the unattended half of discovery, on its own deadline.
#
# The collectors bank captures all night without help. This is the other half: the
# mechanical parts of *finding sources*, which until now only ran when an agent was
# awake to type them. It performs one pass of each, sleeps, and repeats until an
# absolute epoch, so it survives the agent going away and cannot outlive its window.
#
# **What it does, and why only these.** Each step is autonomous by construction:
# it needs judgement neither to generate its input nor to decide whether an answer
# is interesting.
#
#   1. `reprobe_closed.py`  A source closed on a *measurement* is finished, but one
#      closed on *availability* is not, and the register already holds the URLs. A
#      dead host that now answers 200 is interesting without anyone deciding so.
#      It skips `web.archive.org` internally, which is what makes it safe to run
#      beside two collectors: see SKIP_HOSTS in that script.
#   2. `just cycle`  Everything mechanical, ending with what needs a human.
#
# **What it deliberately does not do.** It does not fetch a candidate's payload, it
# does not ingest, and it cannot promote anything to master. Those need a human at
# the approval gate, and an unattended loop is exactly the thing that gate bounds.
# It also starts no collector: if one has died, the log says so and a person decides,
# because a loop that restarts a collector would eventually restart it with settings
# that had since been retuned. `extend_engines.sh` gives that reasoning at length.
#
# **It is a third client at nobody's door.** The reprobe is one request per URL with
# an honest User-Agent, spread across the whole register's hosts, and the two hosts
# that matter here are excluded from it.
#
# Usage: bash scripts/overnight_hunt.sh <deadline_epoch> [sleep_seconds]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:?usage: overnight_hunt.sh <deadline_epoch> [sleep_seconds]}"
SLEEP="${2:-3600}"
NOW="$(date +%s)"

if [ "$DEADLINE" -le "$NOW" ]; then
    echo "deadline $DEADLINE is not in the future" >&2
    exit 1
fi

mkdir -p data/logs data/reports
LOG="data/logs/overnight_hunt.log"

# One at a time. `mkdir` is atomic where a test-then-write is not, and a second copy
# of this loop would double every request it makes.
LOCK="data/logs/overnight_hunt.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    echo "another overnight_hunt holds $LOCK (pid $(cat "$LOCK/pid" 2>/dev/null || echo unknown))" >&2
    exit 1
fi
echo "$$" > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT INT TERM

note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

note "overnight hunt starting, deadline $(date -u -r "$DEADLINE" '+%F %T UTC'), sleep ${SLEEP}s"

pass=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    pass=$((pass + 1))
    note "===== pass $pass ====="

    note "-- reprobe: sources closed because something could not be reached --"
    uv run python scripts/reprobe_closed.py \
        --json "data/reports/reprobe_$(date -u +%Y%m%dT%H%M%SZ).json" >> "$LOG" 2>&1
    note "-- reprobe done (exit $?) --"

    note "-- cycle --"
    just cycle >> "$LOG" 2>&1
    note "-- cycle done (exit $?) --"

    # Sleep in short hops so the deadline is honoured to the minute rather than to
    # the sleep interval, and so a TERM lands promptly.
    remaining=$((DEADLINE - $(date +%s)))
    [ "$remaining" -le 0 ] && break
    hop=$SLEEP
    [ "$hop" -gt "$remaining" ] && hop=$remaining
    slept=0
    while [ "$slept" -lt "$hop" ]; do
        sleep 30
        slept=$((slept + 30))
    done
done

note "overnight hunt reached its deadline after $pass pass(es)"
