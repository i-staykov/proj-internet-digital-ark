#!/usr/bin/env bash
# Query RDAP for novel domains and bank the creation dates, until a deadline.
#
# **Why this is the fast route, stated once so it is not re-litigated.** The
# constraint on this project has never been finding candidates; it is dating them.
# The archive CDX endpoint gives about 17,500 queries a day and the suffix sweep
# about 15,000 equivalent-English a day. RDAP is a different service, it returns the
# registry's own creation date, and a creation date is `whois_creation`:
# **master-eligible, self-dating, no corroboration split**. `rdap_snapshot /
# whois_creation` has been approved since phase 4, so nothing here waits on anyone.
#
# **Throughput is a property of the registry, not of the query.** A mixed-TLD list
# ran at 0.55 queries a second because slow and dead registries block the queue. The
# same code against Verisign alone did 3,000 queries in 46 seconds, **65 q/s**, which
# is 5.6 million a day. That is why the target list is `.com` and `.net` only.
#
# **Measured yield**, on 3,000 raw `.com` queries: 36.4% carried an in-window
# creation date, 11.4% of those were net-new, so 25.7 net equivalent-English per
# thousand. The target list here is filtered to domains the store has never seen, so
# almost none of that 88.6% waste should remain; `rdap_journal_value.py` re-measures
# it per journal rather than assuming the improvement.
#
# It never touches `web.archive.org`, so it runs beside both CDX sweeps.
#
# Usage: bash scripts/rdap_novel_run.sh <deadline_epoch> [batch] [workers]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:?usage: rdap_novel_run.sh <deadline_epoch> [batch] [workers]}"
BATCH="${2:-150000}"
WORKERS="${3:-16}"
TARGETS="${ARK_RDAP_NOVEL:-data/raw/rdap/novel_com.txt}"
LOG="data/logs/rdap_novel.log"
mkdir -p data/logs
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

LOCK="data/logs/rdap_novel.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    note "another run holds $LOCK (pid $(cat "$LOCK/pid" 2>/dev/null || echo unknown))"
    exit 1
fi
echo "$$" > "$LOCK/pid"
# The handler must exit, not just clean up: a bare EXIT/INT/TERM trap releases the
# lock and lets the loop carry on, which has started a second copy twice in this
# project already.
cleanup() { rm -rf "$LOCK"; }
trap 'cleanup' EXIT
trap 'cleanup; exit 143' TERM
trap 'cleanup; exit 130' INT

[ -s "$TARGETS" ] || { note "no targets at $TARGETS"; exit 1; }
note "targets $TARGETS ($(wc -l < "$TARGETS" | tr -d ' ') domains)"
note "deadline $(date -u -r "$DEADLINE" '+%F %T UTC'), batch $BATCH, workers $WORKERS"

round=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    round=$((round + 1))
    before=$(ls data/raw/rdap/rdap_*.jsonl.gz 2>/dev/null | wc -l | tr -d ' ')
    note "round $round: querying up to $BATCH"
    uv run ark rdap "$TARGETS" --limit "$BATCH" --workers "$WORKERS" >> "$LOG" 2>&1
    after=$(ls data/raw/rdap/rdap_*.jsonl.gz 2>/dev/null | wc -l | tr -d ' ')
    if [ "$after" -le "$before" ]; then
        note "round $round produced no new journal; the list is exhausted or the API refused"
        break
    fi

    newest=$(ls -t data/raw/rdap/rdap_*.jsonl.gz | head -1)
    note "banking $newest"
    for attempt in $(seq 1 40); do
        if uv run ark ingest rdap_snapshot "$newest" >> "$LOG" 2>&1; then
            break
        fi
        if ! tail -3 "$LOG" | grep -q "Conflicting lock"; then
            note "  ingest failed for a reason that is not the write lock"
            break
        fi
        sleep 45
    done
    note "round $round banked"
done

note "rdap novel run finished after $round round(s)"
