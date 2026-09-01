#!/usr/bin/env bash
# Bank a promotion tranche, retrying each ingest around the store's single writer.
#
# `build_promotion_journals.py` deliberately prints the ingest commands rather than
# running them, because whether to bank a tranche is a judgement. This runs them
# once that judgement is made, and exists because typing seven commands by hand
# while `maintain.sh` holds the write lock produces seven silent failures.
#
# Usage: bash scripts/harness/bank_promotion.sh <tag>

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

TAG="${1:?usage: bank_promotion.sh <tag>}"
DIR="data/staging/promotion"
LOG="data/logs/promotion_bank.log"
mkdir -p data/logs
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

# The journal name says which spec it belongs to, so the mapping is derived rather
# than repeated: a table here would drift from the writer's own naming.
for f in "$DIR"/*_promoted_"$TAG".jsonl.gz; do
    [ -e "$f" ] || { note "no journals for tag $TAG"; exit 1; }
    spec=$(basename "$f" | sed "s/_promoted_${TAG}\.jsonl\.gz//")
    note "ingest $spec $(basename "$f")"
    ok=0
    for attempt in $(seq 1 40); do
        if uv run ark ingest "$spec" "$f" >> "$LOG" 2>&1; then
            ok=1
            break
        fi
        if ! tail -3 "$LOG" | grep -q "Conflicting lock"; then
            note "  $spec failed for a reason that is not the write lock"
            break
        fi
        sleep 45
    done
    [ "$ok" -eq 1 ] || note "  $spec NOT banked"
done
note "promotion tranche $TAG done"
