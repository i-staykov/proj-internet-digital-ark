#!/usr/bin/env bash
# Split and ingest `data/raw/usenet_new/`, which no pass has ever looked at.
#
# **Why this exists: a one-word directory mismatch hid 50 GB for weeks.**
# `ingest_new_usenet.sh` reads `DIR="data/raw/usenet"` and marks work done in
# `data/raw/usenet/.processed`. The archives here are in `data/raw/usenet_new/`,
# so the pipeline could not see them: 7,531 archives, 50 GB, and **zero of them
# appear in the .processed list that holds 19,231 other groups.**
#
# **It is worth doing and it is not worth much**, and both halves matter. Three
# samples over 4,052 MB and five hierarchies: bit and linux gave 0 net-new pairs
# over 207 MB; us, gov and lucky gave 3 over 1,866 MB; the twelve largest
# microsoft archives gave 63 over 1,979 MB. Combined that is **57,913 dated
# pairs of which 57,847 are already held, 99.89% saturation, 66 net-new pairs
# and 35.8 EE**, a density of 0.0088 EE per MB. Over the full 50 GB that
# projects to **roughly 450 to 850 EE**, the range depending on whether you
# weight by hierarchy or pool the samples.
#
# So this is below the 1,000 EE bar for a source needing a DECISION, but it
# needs no decision: `usenet_dated` and `usenet_candidates` are already master
# and candidate-only respectively. The only cost is CPU on bytes already
# downloaded, which makes it worth running and not worth hurrying.
#
# **Six workers, not the ten `ingest_new_usenet.sh` uses.** The two CDX engines
# are latency-bound rather than CPU-bound, so they have headroom, but they are
# worth more per hour than this is and must not be starved to finish it faster.
#
# Batched so a kill loses one batch rather than the run, and each batch marks
# its archives only after a clean ingest, which is the rule the Usenet pipeline
# learned on 1 August when 92 archives were marked processed after a failed
# ingest and the work was silently lost.
#
#     bash scripts/work_usenet_new.sh <deadline_epoch> [batch] [workers]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:-0}"
BATCH="${2:-250}"
WORKERS="${3:-6}"
# **The directory is a parameter now, because a second 53 GB pool turned up.**
# `data/raw/usenet_bulk` holds 9,266 archives with ZERO filename overlap with
# `usenet_new`, no journals, no progress marker and no script referencing it. It is
# also far denser: two disjoint samples over 135.1 MB of its non-`alt.sex` stratum
# gave 231 net-new pairs and 130.63 equivalent-English, a pooled 0.9669 EE per MB
# against the 0.0088 measured on `usenet_new`, with the two samples 2.9x apart
# (1.3950 and 0.4842) so the estimate is noisy. The likely reason for the gap is
# population: `usenet_new` was bit, linux, microsoft and gov, whose domains the
# store already holds, and this is consumer `alt.*` naming small businesses,
# fan sites and ISPs it does not.
#
#     ARK_USENET_SRC=data/raw/usenet_bulk bash scripts/work_usenet_new.sh <deadline>
SRC="${ARK_USENET_SRC:-data/raw/usenet_new}"
JOURNALS="data/raw/usenet"
DONE="$SRC/.processed"
LOG="data/logs/$(basename "$SRC").log"

mkdir -p data/logs "$JOURNALS"
touch "$DONE"
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" >> "$LOG"; }

if [ "$DEADLINE" -le "$(date +%s)" ]; then
    note "deadline $DEADLINE is not in the future; refusing to start"
    exit 1
fi
if [ "$(pgrep -fc 'work_usenet_new.sh')" -gt 2 ]; then
    note "another copy is already running; refusing to start a second"
    exit 1
fi

note "start: until $DEADLINE, batch=$BATCH workers=$WORKERS"

while :; do
    if [ "$(date +%s)" -ge "$DEADLINE" ]; then
        note "deadline reached, stopping cleanly"
        break
    fi

    pending=()
    for archive in "$SRC"/*.mbox.zip; do
        [ -e "$archive" ] || continue
        grep -qxF "$(basename "$archive")" "$DONE" && continue
        pending+=("$archive")
        [ "${#pending[@]}" -ge "$BATCH" ] && break
    done
    if [ "${#pending[@]}" -eq 0 ]; then
        note "nothing left unprocessed"
        break
    fi

    tag="$(basename "$SRC" | sed 's/usenet_//')$(date '+%H%M%S')"
    note "batch of ${#pending[@]} as $tag"
    if ! uv run python scripts/split_usenet.py "${pending[@]}" --tag "$tag" \
            --write --workers "$WORKERS" >> "$LOG" 2>&1; then
        note "split failed for $tag, leaving archives unmarked"
        continue
    fi

    ingested=1
    for half in dated candidates; do
        journal="$JOURNALS/usenet_${half}_${tag}.jsonl.gz"
        [ -f "$journal" ] || continue
        if ! uv run ark ingest "usenet_${half}" "$journal" >> "$LOG" 2>&1; then
            note "ingest of $journal FAILED"
            ingested=0
        fi
    done
    if [ "$ingested" -eq 0 ]; then
        note "leaving $tag archives unmarked so the next pass retries"
        continue
    fi

    printf '%s\n' "${pending[@]##*/}" >> "$DONE"
    note "marked ${#pending[@]} archives, $(grep -c . "$DONE") done in total"
done

note "exit"
