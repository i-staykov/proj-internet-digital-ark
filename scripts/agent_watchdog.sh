#!/usr/bin/env bash
# Restart the research loop and the collectors if any of them dies before the deadline.
#
# **Why: on the night of 2026-08-27 the fan-out exited at 17:17 and nothing noticed until
# 23:46.** Six and a half hours of idle research time, while the collectors ran on
# perfectly well beside it. The loop had a deadline and no keeper, which is the one
# failure mode the collection engines never have because `extend_engines.sh` hands them
# over. This is that keeper, for the agent rather than for the collectors.
#
# It is deliberately dumb. It checks every two minutes, starts anything missing, and
# writes a line when it does. It never tunes, never changes arguments, and never stops
# anything: a watchdog that makes decisions is a second agent with no supervision.
#
#     bash scripts/agent_watchdog.sh <deadline_epoch> [parallel]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
DEADLINE="${1:?usage: agent_watchdog.sh <deadline_epoch> [parallel]}"
PAR="${2:-4}"
COLLECTOR_DEADLINE="${3:-1787979600}"   # collectors outlive the agent, as always
LOG="data/logs/agent_watchdog.log"
mkdir -p data/logs
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

LOCK="data/logs/agent_watchdog.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    holder=$(cat "$LOCK/pid" 2>/dev/null || echo unknown)
    if [ "$holder" != unknown ] && kill -0 "$holder" 2>/dev/null; then
        echo "watchdog already running as pid $holder" >&2; exit 1
    fi
    rm -rf "$LOCK" && mkdir "$LOCK" || exit 1
fi
printf '%s\n' "$$" > "$LOCK/pid"
trap 'rm -rf "$LOCK"; note "watchdog exit"' EXIT

note "start: watching until $(date -r "$DEADLINE" '+%F %T' 2>/dev/null || echo "$DEADLINE")"
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    if ! pgrep -f "agent_fanou[t].sh" >/dev/null 2>&1; then
        rm -rf data/logs/agent_fanout.lock
        note "RESTART fan-out: it was not running"
        nohup bash scripts/agent_fanout.sh "$DEADLINE" "$PAR" private/agent-hypotheses.md \
            > /dev/null 2>&1 < /dev/null &
    fi
    if ! pgrep -f "supervise_cdx_poo[l].sh" >/dev/null 2>&1; then
        note "RESTART cdx collector: it was not running"
        ARK_TARGETS=data/raw/cdx/queue_gap_local_tail.txt ARK_PREFIX=cdx_gtail \
            nohup caffeinate -i bash scripts/supervise_cdx_pool.sh \
            "$COLLECTOR_DEADLINE" 600 8 900 0.5 0.15 3.0 70 > /dev/null 2>&1 < /dev/null &
    fi
    if ! pgrep -f "maintai[n].sh" >/dev/null 2>&1; then
        note "RESTART maintain: it was not running"
        nohup bash scripts/maintain.sh 900 150 > /dev/null 2>&1 < /dev/null &
    fi
    if ! pgrep -f "compound_split[s].sh" >/dev/null 2>&1; then
        note "RESTART compound_splits: it was not running"
        nohup bash scripts/compound_splits.sh "$COLLECTOR_DEADLINE" 1500 \
            > /dev/null 2>&1 < /dev/null &
    fi
    sleep 120
done
note "deadline reached"
