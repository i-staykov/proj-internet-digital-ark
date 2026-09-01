#!/usr/bin/env bash
# chain of sweep queues behind a running sweep pid: chain.sh <pid> <queue>...
cd "$(dirname "$0")"; while [ ! -d data/raw ] && [ "$PWD" != "/" ]; do cd ..; done
D=1790812800
WAIT="$1"; shift
while kill -0 "$WAIT" 2>/dev/null; do sleep 60; done
for q in "$@"; do
    case "$q" in s1|s2) f="data/raw/cdx/suffix_queue_$q.txt";; *) f="data/raw/cdx/platform_queue_$q.txt";; esac
    bash scripts/platform_sweep.sh "$D" "$f" >> "data/logs/sweep_$q.log" 2>&1
done
