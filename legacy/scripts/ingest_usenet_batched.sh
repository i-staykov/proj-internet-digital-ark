#!/usr/bin/env bash
# Move probe archives into the ingest directory a batch at a time, and ingest each.
#
# Batching is not caution, it is what makes the corroboration split work. A name
# attested only by Usenet goes to the candidate pool; it is admitted to an annual
# file once something independent corroborates it. `split_usenet.py` evaluates that
# against the store **as it stands when the batch runs**, so a domain promoted by
# batch 3 becomes a valid corroborator for batch 4. Moving all 3,479 archives in at
# once collapses that to a single evaluation and admits strictly less.
#
# It also bounds the cost of a failure. `ingest_new_usenet.sh` marks archives
# processed only after a clean ingest, so a batch that hits the DuckDB write lock
# is retried rather than lost. One batch is a few minutes of rework; the whole
# corpus is an hour.
#
# Archives are moved rather than copied because `ingest_new_usenet.sh` globs
# `data/raw/usenet/*.mbox.zip`. Anything still in a probe directory is, by
# definition, not yet offered to the store, which is the property the research
# handback relied on to keep unjudged material out.
#
# Usage: bash scripts/ingest_usenet_batched.sh [batch_size]
set -uo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"

BATCH="${1:-400}"
DEST="data/raw/usenet"
LOG="data/logs/usenet_batched.log"
mkdir -p data/logs "$DEST"

note() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

# A basename already in `.processed` would be skipped after the move, so its work
# would silently never be ingested. Only one archive collides, but the check is
# cheap and the failure would be invisible.
#
# Built with a plain loop rather than `mapfile`, which is bash 4 and macOS ships
# 3.2. Same family of trap as the BSD `stat -f` and `date -r` that broke the
# supervisor on Linux: written on one platform, only exercised on the other.
queue=()
for f in data/raw/usenet_probe*/*.mbox.zip; do
    [ -e "$f" ] || continue
    base=$(basename "$f")
    grep -qxF "$base" "$DEST/.processed" 2>/dev/null && continue
    [ -e "$DEST/$base" ] && continue
    queue+=("$f")
done

total=${#queue[@]}
note "start: ${total} archives to ingest in batches of ${BATCH}"
[ "$total" -eq 0 ] && { note "nothing to do"; exit 0; }

failures=0
done_count=0
for ((i = 0; i < total; i += BATCH)); do
    slice=("${queue[@]:i:BATCH}")
    n=${#slice[@]}
    note "batch $((i / BATCH + 1)): moving ${n} archives"
    mv -n "${slice[@]}" "$DEST/" || { note "mv failed, stopping"; exit 1; }

    if bash scripts/ingest_new_usenet.sh probe; then
        done_count=$(( done_count + n ))
        failures=0
        note "batch $((i / BATCH + 1)) ingested; ${done_count}/${total} done"
    else
        failures=$(( failures + 1 ))
        note "batch $((i / BATCH + 1)) FAILED (consecutive: ${failures}); archives left unmarked"
        # Almost always the write lock. Give it room, then carry on: the failed
        # archives sit unmarked in DEST and the next `ingest_new_usenet.sh` call
        # picks them up along with the following batch.
        if [ "$failures" -ge 3 ]; then
            note "three consecutive failures, stopping rather than grinding"
            exit 1
        fi
        sleep 60
    fi
done

note "all batches offered; running one final pass for anything left unmarked"
bash scripts/ingest_new_usenet.sh probe || note "final pass failed; re-run this script to retry"
note "done: $(ls "$DEST"/*.mbox.zip 2>/dev/null | wc -l | tr -d ' ') archives in ${DEST}, $(wc -l < "$DEST/.processed" | tr -d ' ') marked processed"
