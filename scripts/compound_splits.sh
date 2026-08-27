#!/usr/bin/env bash
# Re-split the mention corpora on a loop, because the split gets more valuable as the
# store grows and every master ingest can unlock names the previous pass could not admit.
#
# **Measured 2026-08-27, and this is the largest lever in the round.** The corroboration
# split promotes a mention to a dated record only when some OTHER source already places
# that domain in a year, and that test is re-evaluated every time the split runs. On one
# morning: re-splitting the address journals paid 30,645.6 EE against roughly 700 pairs
# from the 60 new archives that triggered it, and re-splitting the bare journals paid
# 11,447.7 EE against 128.17 EE for its 400 new archives. Ratios of about 40:1 and 90:1
# in favour of re-splitting over reading.
#
# `maintain.sh` already MEASURES the promotion tranche every pass and deliberately does
# not bank it, because banking is a judgement. The judgement is made: these classes are
# all already `master` or `candidate-only`, so the tranche is a re-derivation of evidence
# we hold rather than a new source, and it needs no further decision.
#
# One pass at a time, and it skips a pass rather than queueing if the store is busy: the
# store takes a single writer and the collectors' ingests matter more than this does.
#
#     bash scripts/compound_splits.sh <deadline_epoch> [pause_seconds]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:?usage: compound_splits.sh <deadline_epoch> [pause_seconds]}"
PAUSE="${2:-1500}"
LOG="data/logs/compound_splits.log"
mkdir -p data/logs
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

note "start: until ${DEADLINE}, pause ${PAUSE}s"
pass=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    pass=$((pass + 1))
    tag="cmp$(date -u +%Y%m%dT%H%M%SZ)"
    note "pass ${pass} as ${tag}"

    # the cross-source tranche: a mention promoted because another source dated its domain
    if uv run python scripts/build_promotion_journals.py --tag "$tag" --write >> "$LOG" 2>&1; then
        bash scripts/bank_promotion.sh "$tag" >> "$LOG" 2>&1 \
            || note "  promotion bank failed this pass"
    else
        note "  promotion build failed this pass"
    fi

    # the two corpora whose journals hold their own raw recovered rows, so a re-split
    # reconsiders every row rather than only the mention rows already in the store
    for pair in "usenet_addr:data/raw/usenet_addr" "usenet_bare:data/raw/usenet_bare"; do
        prefix="${pair%%:*}"; dir="${pair##*:}"
        [ -d "$dir" ] || continue
        if ! uv run python scripts/split_usenet_addresses.py --in-dir "$dir" \
                --out-prefix "$prefix" --write >> "$LOG" 2>&1; then
            note "  ${prefix} split failed this pass"
            continue
        fi
        for lane in dated candidates; do
            f="${dir}/${prefix}_${lane}.jsonl.gz"
            [ -f "$f" ] || continue
            mv "$f" "${dir}/${prefix}_${lane}_${tag}.jsonl.gz"
            uv run ark ingest "usenet_addr_${lane}" "${dir}/${prefix}_${lane}_${tag}.jsonl.gz" \
                >> "$LOG" 2>&1 || note "  ingest ${prefix} ${lane} failed"
        done
    done
    note "pass ${pass} done"
    sleep "$PAUSE"
done
note "exit"
