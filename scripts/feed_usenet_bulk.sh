#!/usr/bin/env bash
# Feed downloaded archives into the split-and-ingest pipeline a batch at a time.
#
# `ingest_new_usenet.sh` collects every unprocessed archive in data/raw/usenet/ and
# splits them in ONE call, which is right for the dozens a probe produces and wrong
# for the twelve thousand a bulk run produces: one pass would run for hours, hold the
# store's write lock at the end of it, and lose everything in flight if it died.
#
# So the bulk download lands somewhere else and this drip-feeds it. A batch is only
# released once the previous one has been consumed, which keeps each split short
# enough to finish inside a maintain cycle and makes the whole run resumable: kill it
# at any point and the archives already moved are either processed or still pending,
# never half of both.
#
#   bash scripts/feed_usenet_bulk.sh <deadline-epoch> [batch] [source-dir]

set -uo pipefail

DEADLINE="${1:?usage: feed_usenet_bulk.sh <deadline-epoch> [batch] [source-dir]}"
BATCH="${2:-800}"
SRC="${3:-data/raw/usenet_bulk}"
DEST="data/raw/usenet"
PROCESSED="$DEST/.processed"
LOG="data/logs/feed_usenet_bulk.log"
# Release the next batch once the queue has drained to about this much, so the
# splitter always has work but never a backlog it cannot finish.
LOW_WATER=150

mkdir -p "$DEST" "$(dirname "$LOG")"
touch "$PROCESSED"

# One grep per archive is O(archives x ledger) and the ledger passed 4,000 entries
# long ago, so the naive version spent minutes deciding whether to do 30 seconds of
# work. Two sorted lists and `comm` is the same answer in one pass.
pending_count() {
    comm -23 \
        <(cd "$DEST" && ls -1 ./*.mbox.zip 2>/dev/null | sed 's|^\./||' | sort) \
        <(sort -u "$PROCESSED") | wc -l | tr -d ' '
}

echo "$(date '+%F %T') feeder starting, batch=$BATCH source=$SRC" >> "$LOG"

while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    remaining=$(ls "$SRC"/*.mbox.zip 2>/dev/null | wc -l | tr -d ' ')
    if [ "$remaining" -eq 0 ]; then
        echo "$(date '+%F %T') source empty, feeder done" >> "$LOG"
        break
    fi
    pending=$(pending_count)
    if [ "$pending" -gt "$LOW_WATER" ]; then
        sleep 60
        continue
    fi
    moved=0
    for archive in "$SRC"/*.mbox.zip; do
        [ -e "$archive" ] || break
        mv "$archive" "$DEST/" && moved=$((moved + 1))
        [ "$moved" -ge "$BATCH" ] && break
    done
    free=$(df -g . | awk 'NR==2{print $4}')
    echo "$(date '+%F %T') released $moved archives ($((remaining - moved)) left, ${free}GB free)" >> "$LOG"
    sleep 30
done

echo "$(date '+%F %T') feeder exiting" >> "$LOG"
