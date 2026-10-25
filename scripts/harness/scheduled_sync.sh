#!/usr/bin/env bash
# One unattended sync, for the hourly timer (`ark-sync.timer`) to call.
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
# The bank host follows `live`: a merged PR reaches it before the tick runs, since the
# recipe refuses a diverged clone and nobody pulls here by hand. A dirty tree is left alone.
git diff --quiet && git pull -q --ff-only origin live

# The recipes' own `local.env`: without its ARK_DB_MEMORY_LIMIT the bank dies at DuckDB's 40%
# cap. It assigns without `export`, so that one value is exported and the hosts stay out of
# child environments.
[ -f local.env ] && . ./local.env
[ -n "${ARK_DB_MEMORY_LIMIT:-}" ] && export ARK_DB_MEMORY_LIMIT

FLEET_REPO="i-staykov/ark-fleet"
mkdir -p data/logs
LOG="data/logs/scheduled_sync.log"
STAMP=$(date -u +%Y%m%dT%H%MZ)

# No lock here: the recipe's `sync_lock.sh` is the one this and a hand-run `just sync` share.

ship_now() {
    local n body
    n=$(gh issue list --repo "$FLEET_REPO" --state open --label ship-now \
        --json number --jq '.[0].number // empty' 2>/dev/null) || return 0
    [ -n "$n" ] || return 0
    echo "ship-now on $FLEET_REPO#$n: packaging"
    gh issue edit "$n" --repo "$FLEET_REPO" --remove-label ship-now >/dev/null 2>&1 || true
    if just ship all > "data/logs/ship_$STAMP.log" 2>&1; then
        body="Packaged by the hourly sync at $STAMP. Nothing was sent: \`just ship report <archive>\` fills the report and the mail draft."
    else
        body="The hourly sync tried to package at $STAMP and \`just ship all\` failed. Label removed so it does not retry; the log is data/logs/ship_$STAMP.log on the bank host."
    fi
    # the log tail, without anything shaped like an address
    body="$body"$'\n\n```\n'"$(grep -vE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+|@' "data/logs/ship_$STAMP.log" | tail -15)"$'\n```'
    gh issue comment "$n" --repo "$FLEET_REPO" --body "$body" >/dev/null 2>&1 || true
    echo "ship-now: done, see $FLEET_REPO#$n"
}

{
    printf '\n===== scheduled sync %s =====\n' "$(date -u '+%F %T UTC')"
    login="login ok" && gh auth status > /dev/null 2>&1 || login="LOGIN DEAD"
    expiry=$(gh api -i user 2> /dev/null | tr -d '\r' | sed -n 's/^github-authentication-token-expiration: //Ip')
    echo "$login, token expiry: ${expiry:-no expiry header}"
    # the per-file skip lines of an idempotent ingest would fill the whole log; line
    # buffering so a reader mid-run sees where the sync is, not a stale block
    just sync 2>&1 | grep --line-buffered -vE 'already ingested, skipping|\| INFO +\| \[[0-9]+/[0-9]+\]'
    printf -- '----- ship-now -----\n'
    ship_now 2>&1
} >> "$LOG"

# Keep the log readable rather than complete: the ledger and the store are the
# record, this is a noticeboard.
tail -n 2000 "$LOG" > "$LOG.trim" && mv "$LOG.trim" "$LOG"
