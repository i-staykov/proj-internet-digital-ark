#!/usr/bin/env bash
# Run the address/header extractors over the Usenet pools that are still on disk.
#
# **Why this exists: the extractors read `data/raw/usenet`, which is now empty.**
# That directory held the original 411 GB pool and was reclaimed once processed,
# so `collect_usenet_addresses.py` and `collect_usenet_bare.py` had silently
# become no-ops. The 16,797 archives that ARE on disk, 9,266 in `usenet_bulk`
# and 7,531 in `usenet_new`, had never been through either of them.
#
# **The larger half of the yield is the re-split, not the new archives.** The
# corroboration split promotes a mention to a dated record only when some other
# source already places that domain in a year, so re-splitting every address
# journal against a store that has since grown converts candidates into masters
# for no new reading at all. Measured 2026-08-27: one 60-archive pass plus a
# re-split of the 2026-08-08 journals gave 51,235 net-new pairs and 30,645.6
# equivalent-English, of which roughly 700 pairs are attributable to the 60 new
# archives and the rest to the re-split.
#
# Batched, so a kill loses one batch rather than the run, and the split and
# ingest run per batch rather than at the end.
#
#     bash scripts/work_usenet_addresses.sh <deadline_epoch> [batch] [workers]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:?usage: work_usenet_addresses.sh <deadline_epoch> [batch] [workers] [mode]}"
BATCH="${2:-400}"
WORKERS="${3:-5}"
# `addresses` reads ftp://, mailto: and typed body addresses; `headers` reads the
# message headers. Both feed usenet_address, both had the empty-directory bug, and
# both need running over the pools that are still on disk.
MODE="${4:-addresses}"
case "$MODE" in
    addresses) OUT_DIR=data/raw/usenet_addr; PREFIX=usenet_addr; MARK_NAME=addr ;;
    headers)   OUT_DIR=data/raw/usenet_hdr;  PREFIX=usenet_hdr;  MARK_NAME=hdr ;;
    *) echo "mode must be addresses or headers" >&2; exit 2 ;;
esac
LOG="data/logs/usenet_${MODE}_work.log"
mkdir -p data/logs "$OUT_DIR"
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

# Split every journal in the directory and ingest both lanes. Separate from the
# reading loop because it costs the same whether it follows one batch or eight.
bank() {
    local tag="$1"
    note "banking after ${tag}"
    if ! uv run python scripts/split_usenet_addresses.py \
            --in-dir "$OUT_DIR" --out-prefix "$PREFIX" --write >> "$LOG" 2>&1; then
        note "split failed, nothing banked this time; the journals keep the work"
        return 1
    fi
    local lane src
    for lane in dated candidates; do
        src="${OUT_DIR}/${PREFIX}_${lane}.jsonl.gz"
        [ -f "$src" ] || continue
        mv "$src" "${OUT_DIR}/${PREFIX}_${lane}_${tag}.jsonl.gz"
        uv run ark ingest "usenet_addr_${lane}" \
            "${OUT_DIR}/${PREFIX}_${lane}_${tag}.jsonl.gz" >> "$LOG" 2>&1 \
            || note "ingest of ${lane} ${tag} failed"
    done
    note "banked ${tag}"
}

note "start: until ${DEADLINE}, batch=${BATCH} workers=${WORKERS} mode=${MODE}"
round=0
for SRC in data/raw/usenet_bulk data/raw/usenet_new; do
    # The marker is per MODE, and headers uses `.hdr_processed` rather than
        # `.headers_processed` because that is the name already on disk from the first
        # header run. A marker rename silently redoes the whole pool.
        MARK="${SRC}/.${MARK_NAME}_processed"
    touch "$MARK"
    while [ "$(date +%s)" -lt "$DEADLINE" ]; do
        # what is left in this pool, in a stable order so a restart resumes
        left=$(comm -23 \
            <(cd "$SRC" && ls -1 *.mbox.zip 2>/dev/null | sort) \
            <(sort "$MARK") | head -n "$BATCH")
        [ -z "$left" ] && { note "$SRC: nothing left"; break; }
        n=$(printf '%s\n' "$left" | wc -l | tr -d ' ')
        round=$((round + 1))
        tag="addr$(date -u +%H%M%S)"
        note "$SRC: batch ${round}, ${n} archives as ${tag}"
        # a staging directory holding only this batch, by symlink so no bytes move
        stage="data/raw/usenet_${MODE}_stage"
        rm -rf "$stage" && mkdir -p "$stage"
        while IFS= read -r f; do
            [ -n "$f" ] && ln -s "../../../$SRC/$f" "$stage/$f" 2>/dev/null
        done <<< "$left"
        if ! ARK_USENET_SRC="$stage" uv run python scripts/collect_usenet_addresses.py \
                --mode "$MODE" --workers "$WORKERS" >> "$LOG" 2>&1; then
            note "$SRC: extractor failed, stopping this pool"
            break
        fi
        # **Marked on a clean EXTRACTION, not on a clean ingest, and that is the
        # opposite of the rule the Usenet pipeline learned on 1 August.** It is safe
        # here only because the journal is the durable artifact: the split reads every
        # journal in the directory and is idempotent, so a batch whose split never ran
        # is recovered by the next split rather than by re-reading 2.6 GB of archives.
        printf '%s\n' "$left" >> "$MARK"
        sort -u "$MARK" -o "$MARK"
        note "$SRC: extracted ${n}, $(wc -l < "$MARK" | tr -d ' ') done in this pool"
        # The split is O(all journals) and the extraction is O(this batch), so
        # splitting per batch is quadratic: measured at batch 1 it re-read 2.47M rows
        # and by batch 42 it would re-read forty times that, which is why the first
        # version of this script could not have finished. Every eighth batch instead,
        # and once more at exit.
        if [ $((round % 8)) -eq 0 ]; then
            bank "$tag"
        fi
    done
done
rm -rf "data/raw/usenet_${MODE}_stage"
bank "final$(date -u +%H%M%S)"
note "exit"
