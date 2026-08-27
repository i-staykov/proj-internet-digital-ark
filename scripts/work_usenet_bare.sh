#!/usr/bin/env bash
# Run the bare-hostname extractor over the Usenet pools that are still on disk.
#
# Sibling of `work_usenet_addresses.sh` and it exists for the same reason:
# `collect_usenet_bare.py` read `data/raw/usenet`, which was reclaimed once
# processed and now holds zero archives, so the extractor had become a no-op over
# the 16,797 archives that are on disk.
#
# What it reads that nothing else does: the plain `foo.com` written in running
# prose, with no scheme, no `www.` label and no `@`. The corroboration split is
# the evidence wall rather than the pattern, so a string that is not a registered
# domain lands in the candidate pool and asserts nothing.
#
# Banks every eighth batch, for the same quadratic reason as the address runner.
#
#     bash scripts/work_usenet_bare.sh <deadline_epoch> [batch] [workers]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:?usage: work_usenet_bare.sh <deadline_epoch> [batch] [workers]}"
BATCH="${2:-400}"
WORKERS="${3:-4}"
LOG="data/logs/usenet_bare_work.log"
mkdir -p data/logs data/raw/usenet_bare
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

bank() {
    local tag="$1" lane src
    note "banking after ${tag}"
    # The same splitter as the address lane, with a prefix: there is no separate
    # bare splitter and writing one would have duplicated it.
    if ! uv run python scripts/split_usenet_addresses.py \
            --in-dir data/raw/usenet_bare --out-prefix usenet_bare --write >> "$LOG" 2>&1; then
        note "split failed, nothing banked; the journals keep the work"
        return 1
    fi
    for lane in dated candidates; do
        src="data/raw/usenet_bare/usenet_bare_${lane}.jsonl.gz"
        [ -f "$src" ] || continue
        mv "$src" "data/raw/usenet_bare/usenet_bare_${lane}_${tag}.jsonl.gz"
        uv run ark ingest "usenet_bare_${lane}" \
            "data/raw/usenet_bare/usenet_bare_${lane}_${tag}.jsonl.gz" >> "$LOG" 2>&1 \
            || note "ingest of ${lane} ${tag} failed"
    done
    note "banked ${tag}"
}

note "start: until ${DEADLINE}, batch=${BATCH} workers=${WORKERS}"
round=0
for SRC in data/raw/usenet_bulk data/raw/usenet_new; do
    MARK="${SRC}/.bare_processed"
    touch "$MARK"
    while [ "$(date +%s)" -lt "$DEADLINE" ]; do
        left=$(comm -23 \
            <(cd "$SRC" && ls -1 *.mbox.zip 2>/dev/null | sort) \
            <(sort "$MARK") | head -n "$BATCH")
        [ -z "$left" ] && { note "$SRC: nothing left"; break; }
        n=$(printf '%s\n' "$left" | wc -l | tr -d ' ')
        round=$((round + 1))
        tag="bare$(date -u +%H%M%S)"
        note "$SRC: batch ${round}, ${n} archives as ${tag}"
        stage="data/raw/usenet_bare_stage"
        rm -rf "$stage" && mkdir -p "$stage"
        while IFS= read -r f; do
            [ -n "$f" ] && ln -s "../../../$SRC/$f" "$stage/$f" 2>/dev/null
        done <<< "$left"
        if ! ARK_USENET_SRC="$stage" uv run python scripts/collect_usenet_bare.py \
                --workers "$WORKERS" --tag "$tag" >> "$LOG" 2>&1; then
            note "$SRC: extractor failed, stopping this pool"
            break
        fi
        printf '%s\n' "$left" >> "$MARK"
        sort -u "$MARK" -o "$MARK"
        note "$SRC: extracted ${n}, $(wc -l < "$MARK" | tr -d ' ') done in this pool"
        if [ $((round % 8)) -eq 0 ]; then bank "$tag"; fi
    done
done
rm -rf data/raw/usenet_bare_stage
bank "final$(date -u +%H%M%S)"
note "exit"
