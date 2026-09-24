#!/usr/bin/env bash
# One unattended sync, for launchd to call every hour.
#
# `just sync` is the tick that moves the round without a session open: it books the
# fleet's findings and calls `just bank` when approvals, a confirmed FIND, a baseline or
# journals arrived. It is idempotent, takes the sync lock and refuses a dirty or diverged
# clone, so all this adds is a log and the one channel that lets a phone ask for a package.
#
# The `ship-now` label on any open ark-fleet issue (the gate issue is the natural one)
# runs `just ship all` once: sync, report, package, verify, the mail draft, and stop.
# Nothing is sent, and sending stays with the owner. The label is removed BEFORE the
# ship runs, so a failed ship does not retry every hour, and the outcome is written
# back on the issue where the label was.
#
# Usage: bash scripts/harness/scheduled_sync.sh

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

# **Machine-local config, the same file `collectors.sh` and `maintain.sh` read.** Without
# it this wrapper ran on the packaged defaults, and `build_round_state.py` died on
# 2026-09-19 at the 40% cap: `Out of Memory Error: could not allocate block of size
# 256.0 KiB (13.0 GiB/13.0 GiB used)` inside `stats.py::_corroboration`. That cap was
# measured right when the store was 52 GB and it is 61 GB now, so the laptop sets
# ARK_DB_MEMORY_LIMIT here rather than raising a default the 7 GB VPS also reads.
# Sourcing alone is not enough: `local.env` assigns without `export`, so the value is a
# shell variable this wrapper can read and every `uv run` child still gets the default.
# Only this one is exported, so the VPS address stays out of child environments.
[ -f local.env ] && . ./local.env
[ -n "${ARK_DB_MEMORY_LIMIT:-}" ] && export ARK_DB_MEMORY_LIMIT

FLEET_REPO="i-staykov/ark-fleet"
mkdir -p data/logs
LOG="data/logs/scheduled_sync.log"
STAMP=$(date -u +%Y%m%dT%H%MZ)

# **No lock here.** This wrapper used to hold its own, which protected it from itself and
# from nothing else: a hand-run `just sync` took no lock at all and the two met in the store.
# The lock moved into the recipe (`sync_lock.sh`), so both paths take the same one; a run
# that finds it held prints why and stops, and that line lands in this log like any other.

ship_now() {
    local n body
    n=$(gh issue list --repo "$FLEET_REPO" --state open --label ship-now \
        --json number --jq '.[0].number // empty' 2>/dev/null) || return 0
    [ -n "$n" ] || return 0
    echo "ship-now on $FLEET_REPO#$n: packaging"
    gh issue edit "$n" --repo "$FLEET_REPO" --remove-label ship-now >/dev/null 2>&1 || true
    if just ship all > "data/logs/ship_$STAMP.log" 2>&1; then
        body="Packaged by the hourly sync at $STAMP. Nothing was sent: the mail draft is on the laptop, under private/."
    else
        body="The hourly sync tried to package at $STAMP and \`just ship all\` failed. Label removed so it does not retry; the log is data/logs/ship_$STAMP.log on the laptop."
    fi
    # the log tail, without anything shaped like an address
    body="$body"$'\n\n```\n'"$(grep -vE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+|@' "data/logs/ship_$STAMP.log" | tail -15)"$'\n```'
    gh issue comment "$n" --repo "$FLEET_REPO" --body "$body" >/dev/null 2>&1 || true
    echo "ship-now: done, see $FLEET_REPO#$n"
}

{
    printf '\n===== scheduled sync %s =====\n' "$(date -u '+%F %T UTC')"
    # the per-file skip lines of an idempotent ingest would fill the whole log; line
    # buffering so a reader mid-run sees where the sync is, not a stale block
    just sync 2>&1 | grep --line-buffered -vE 'already ingested, skipping|\| INFO +\| \[[0-9]+/[0-9]+\]'
    printf -- '----- ship-now -----\n'
    ship_now 2>&1
} >> "$LOG"

# Keep the log readable rather than complete: the ledger and the store are the
# record, this is a noticeboard.
tail -n 2000 "$LOG" > "$LOG.trim" && mv "$LOG.trim" "$LOG"
