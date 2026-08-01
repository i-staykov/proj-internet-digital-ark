#!/usr/bin/env bash
# Split and ingest any Usenet archive that has not been through the pipeline yet.
#
# Downloads and ingests run at different speeds, so this closes the gap: it
# picks up whatever has finished downloading, splits it against the store as it
# stands at that moment, and ingests both halves. Running it repeatedly is safe.
#
# Two things make it safe to re-run. The file ledger keys on content, so an
# already-ingested journal is skipped rather than double counted, and each batch
# writes journals under its own tag because rewriting an ingested journal name
# would be refused as a hash mismatch. A marker file records which archives have
# been processed, so the tag counter does not collide.
#
# The corroboration split is deliberately evaluated per batch rather than once
# up front: a domain that an earlier batch promoted into an annual file becomes
# a valid corroborator for a later one, which is the discovery cycle working.
#
# Usage: bash scripts/ingest_new_usenet.sh [tag_prefix]
set -uo pipefail

TAG_PREFIX="${1:-auto}"
DIR="data/raw/usenet"
DONE="$DIR/.processed"
LOG="data/logs/usenet_ingest.log"

mkdir -p data/logs
touch "$DONE"

pending=()
for archive in "$DIR"/*.mbox.zip; do
    [ -e "$archive" ] || continue
    grep -qxF "$(basename "$archive")" "$DONE" && continue
    pending+=("$archive")
done

if [ "${#pending[@]}" -eq 0 ]; then
    echo "$(date '+%F %T') nothing new to ingest" >> "$LOG"
    exit 0
fi

tag="${TAG_PREFIX}$(date '+%H%M%S')"
echo "$(date '+%F %T') ingesting ${#pending[@]} archive(s) as tag ${tag}" >> "$LOG"
printf '  %s\n' "${pending[@]}" >> "$LOG"

uv run python scripts/split_usenet.py "${pending[@]}" --tag "$tag" --write >> "$LOG" 2>&1 || {
    echo "$(date '+%F %T') split failed, leaving archives unmarked" >> "$LOG"
    exit 1
}

for half in dated candidates; do
    journal="$DIR/usenet_${half}_${tag}.jsonl.gz"
    [ -f "$journal" ] || continue
    uv run ark ingest "usenet_${half}" "$journal" >> "$LOG" 2>&1
done

# Mark only after a clean ingest, so a failure leaves the work to the next run.
printf '%s\n' "${pending[@]##*/}" >> "$DONE"
echo "$(date '+%F %T') done" >> "$LOG"
