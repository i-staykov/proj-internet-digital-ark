#!/usr/bin/env bash
# Fetch Arquivo.pt's `IA.cdxj` in parallel byte ranges, then assemble it in order.
#
# **Why this exists as a script.** The file is 50,930,113,941 bytes and the lane was ruled in
# (C-81, Ivo 2026-09-08), so the fetch has to be restartable and its provenance has to be
# reproducible. A single stream measured 1.7 MB/s on a domestic link and 13.6 MB/s on a fast one;
# three parallel ranges measured 15.6, 11.4 and 9.0 MB/s at once, so the server does not cap a
# client at one stream and the whole file is about 25 minutes rather than 8 hours.
#
# **Why ranges rather than `curl -C -`.** Resuming a stream twice into the same output file left
# 4.27M NUL bytes of holes on 2026-09-08 and a stalled resume left an 900 MB prefix of unknown
# contiguity. A part covers a stated byte range, is retried on its own, and is verified by size
# before assembly, so the failure mode is a missing part rather than a silently holed file.
# Arquivo's own file legitimately contains NUL runs, so NULs cannot be used to detect corruption.
#
# **Terms.** `arquivo.pt/robots.txt` has a `User-agent: *` group disallowing `/datasets` and
# `/cdxj`, and the terms page permits educational, scientific and research use with a citation
# while forbidding distribution of accessed content. Ivo ruled the lane in anyway on the precedent
# that `arquivo_ia` is already in the ingest ledger with 14,819,170 record rows (C-81, issue #115).
# Cite as "[fonte: Arquivo.pt, dd/mm/aaaa]" wherever the derived records are described.
#
# Usage: bash scripts/sources/arquivo/fetch_ia_cdxj.sh [parallel] [part_gb]

set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1

PARALLEL="${1:-5}"
PART_GB="${2:-2}"
UA="ark-research/1.0 (+historical domain census; ivaylo.staykov@taktile.com)"
URL="https://arquivo.pt/datasets/cdxj/IA.cdxj"
OUT="data/raw/arquivo/IA.cdxj"
PARTS="data/raw/arquivo/parts"
TOTAL=50930113941
PART=$(( PART_GB * 1000000000 ))

mkdir -p "$PARTS"
rm -f "$OUT"

# One line per part: index, first byte, last byte. Written first so a restart repeats it exactly.
python3 - "$TOTAL" "$PART" > "$PARTS/plan.tsv" <<'PY'
import sys
total, part = int(sys.argv[1]), int(sys.argv[2])
i = 0
start = 0
while start < total:
    end = min(start + part - 1, total - 1)
    print(f"{i:04d}\t{start}\t{end}")
    start = end + 1
    i += 1
PY
echo "plan: $(wc -l < "$PARTS/plan.tsv" | tr -d ' ') parts of ${PART_GB} GB, ${PARALLEL} at a time"

fetch_part() {
    local idx="$1" first="$2" last="$3"
    local want=$(( last - first + 1 ))
    local path="$PARTS/part_$idx"
    for attempt in 1 2 3 4 5; do
        [ -f "$path" ] && [ "$(wc -c < "$path" | tr -d ' ')" = "$want" ] && return 0
        curl -sS -f -r "${first}-${last}" -A "$UA" -o "$path" "$URL" \
            && [ "$(wc -c < "$path" | tr -d ' ')" = "$want" ] && return 0
        echo "part $idx attempt $attempt short or failed, retrying"
        sleep $(( attempt * 5 ))
    done
    echo "::error::part $idx never completed"
    return 1
}
export -f fetch_part 2>/dev/null || true

# xargs cannot see a bash function, so each part is its own small curl invocation with the same
# verify-and-retry loop inline.
awk '{print $1" "$2" "$3}' "$PARTS/plan.tsv" | xargs -P "$PARALLEL" -n 3 bash -c '
    idx="$0"; first="$1"; last="$2"
    want=$(( last - first + 1 ))
    path="'"$PARTS"'/part_$idx"
    for attempt in 1 2 3 4 5; do
        if [ -f "$path" ] && [ "$(wc -c < "$path" | tr -d " ")" = "$want" ]; then exit 0; fi
        curl -sS -f -r "${first}-${last}" -A "'"$UA"'" -o "$path" "'"$URL"'"
        if [ "$(wc -c < "$path" 2>/dev/null | tr -d " ")" = "$want" ]; then exit 0; fi
        echo "part $idx attempt $attempt short, retrying"
        sleep $(( attempt * 5 ))
    done
    echo "::error::part $idx never completed"
    exit 1
'

# Assemble in plan order and verify the total before anything reads it.
missing=0
while IFS=$'\t' read -r idx first last; do
    want=$(( last - first + 1 ))
    path="$PARTS/part_$idx"
    if [ ! -f "$path" ] || [ "$(wc -c < "$path" | tr -d ' ')" != "$want" ]; then
        echo "::error::part $idx missing or short, not assembling"
        missing=$(( missing + 1 ))
    fi
done < "$PARTS/plan.tsv"
if [ "$missing" -gt 0 ]; then
    echo "$missing part(s) incomplete; rerun this script, completed parts are kept"
    exit 1
fi

while IFS=$'\t' read -r idx first last; do
    cat "$PARTS/part_$idx" >> "$OUT"
done < "$PARTS/plan.tsv"

GOT=$(wc -c < "$OUT" | tr -d ' ')
if [ "$GOT" != "$TOTAL" ]; then
    echo "::error::assembled $GOT bytes, expected $TOTAL"
    exit 1
fi
rm -rf "$PARTS"
echo "assembled $GOT bytes into $OUT"
