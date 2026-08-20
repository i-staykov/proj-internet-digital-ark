#!/usr/bin/env bash
# Split and bank the newly downloaded Usenet hierarchies, in batches, on a deadline.
#
# **Why batches.** The download runs for hours and the split reads the store to
# apply the corroboration split, so processing everything at the end would idle the
# store and then hammer it. Batching also means an interrupted run has banked most
# of its work rather than none.
#
# **Why it can run at all without asking anyone**: `usenet_announce /
# dated_directory` and its siblings have been `master` since phase 4, so this is
# collection under an existing decision. The split itself is applied by
# `split_usenet.py` and is not this script's to weaken.
#
# **The store takes one writer**, and `maintain.sh` holds it for minutes at a time,
# so every ingest here retries rather than treating a lock as a failure. A
# measurement or an ingest that dies on the lock looks exactly like one that found
# nothing.
#
# **macOS ships bash 3.2, so no `mapfile`.** The first version of this used it and
# exited 0 after doing nothing, which is the worst possible failure: a banker that
# reports success and banks nothing is indistinguishable from one that had nothing
# to do. The list is therefore built into a temp file and read with `while read`,
# and the run refuses to end quietly if it banked nothing while archives waited.
#
# **Two populations, one banker.** By default it works whatever the fetcher has
# downloaded into `data/raw/usenet_new`. Given `ARK_USENET_LIST`, it works the
# archives named in that file instead, which is how the 110.8 GB of phase-4
# downloads whose groups the store never named gets read: those are already on
# local disk, so they cost no bandwidth at all. Build the list with
# `scripts/usenet_unworked.py`.
#
# Usage: bash scripts/bank_usenet_new.sh <deadline_epoch> [batch_size]
#        ARK_USENET_LIST=data/raw/usenet/unworked.txt bash scripts/bank_usenet_new.sh <epoch>

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:?usage: bank_usenet_new.sh <deadline_epoch> [batch]}"
BATCH="${2:-40}"
LIST="${ARK_USENET_LIST:-}"
SRC="data/raw/usenet_new"
DONE="$SRC/.banked"
LOG="data/logs/usenet_bank.log"
mkdir -p "$DONE" data/logs
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

LOCK="data/logs/usenet_bank${LIST:+_list}.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    note "another banker holds $LOCK"
    exit 1
fi
echo "$$" > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT INT TERM

retry_ingest() {
    local spec="$1" file="$2"
    for attempt in $(seq 1 40); do
        if uv run ark ingest "$spec" "$file" >> "$LOG" 2>&1; then
            return 0
        fi
        if ! tail -3 "$LOG" | grep -q "Conflicting lock"; then
            note "  $spec $file failed for a reason that is not the write lock"
            return 1
        fi
        sleep 45
    done
    note "  $spec $file: gave up waiting for the write lock"
    return 1
}

note "banking from $SRC in batches of $BATCH, deadline $(date -u -r "$DEADLINE" '+%F %T UTC')"

round=0
PENDING="$SRC/.pending${LIST:+_list}.list"
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    : > "$PENDING"
    if [ -n "$LIST" ]; then
        # The list is ordered largest first, so taking the head takes the valuable
        # part; an interrupted run has banked the big groups.
        while read -r f; do
            [ -s "$f" ] || continue
            [ -e "$DONE/$(basename "$f").ok" ] || echo "$f"
        done < "$LIST" | head -n "$BATCH" > "$PENDING"
    else
        find "$SRC" -maxdepth 1 -name '*.mbox.zip' -type f | sort | while read -r f; do
            [ -e "$DONE/$(basename "$f").ok" ] || echo "$f"
        done | head -n "$BATCH" > "$PENDING"
    fi

    count=$(wc -l < "$PENDING" | tr -d ' ')
    if [ "$count" -eq 0 ]; then
        if [ -z "$LIST" ] && pgrep -f 'fetch_usenet_hierarchie[s]' > /dev/null; then
            note "nothing new yet; the fetcher is still running, waiting"
            sleep 300
            continue
        fi
        note "nothing left to bank"
        break
    fi

    round=$((round + 1))
    tag="new$(date -u +%Y%m%dT%H%M%SZ)"
    note "round $round: $count archive(s), tag $tag"

    # xargs rather than an array expansion, for the same bash 3.2 reason.
    tr '\n' '\0' < "$PENDING" | xargs -0 uv run python scripts/split_usenet.py \
        --write --tag "$tag" --out-dir "$SRC" >> "$LOG" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
        note "round $round: split failed (exit $rc), stopping rather than marking these done"
        break
    fi

    for f in "$SRC"/usenet_dated_"$tag"*.jsonl.gz; do
        [ -e "$f" ] || continue
        retry_ingest usenet_dated "$f"
    done
    for f in "$SRC"/usenet_candidates_"$tag"*.jsonl.gz; do
        [ -e "$f" ] || continue
        retry_ingest usenet_candidates "$f"
    done

    while read -r f; do
        touch "$DONE/$(basename "$f").ok"
    done < "$PENDING"
    note "round $round banked"
done

note "banker finished after $round round(s)"
if [ "$round" -eq 0 ] && [ -z "$LIST" ]; then
    waiting=$(find "$SRC" -maxdepth 1 -name '*.mbox.zip' -type f | wc -l | tr -d ' ')
    if [ "$waiting" -gt 0 ]; then
        note "REFUSING TO EXIT 0: $waiting archive(s) on disk and none banked"
        exit 1
    fi
fi
