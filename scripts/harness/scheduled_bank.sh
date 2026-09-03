#!/usr/bin/env bash
# One unattended bank, for launchd to call every hour.
#
# `just bank` is the thing that moves the round without a session open: approvals
# merged from a phone, fleet findings, the collectors' journals, the brief, the gate
# issue. It is already idempotent and refuses a dirty or diverged clone, so all this
# adds is a lock, a log and the one channel that lets a phone ask for a package.
#
# The `ship-now` label on any open ark-fleet issue (the gate issue is the natural one)
# runs `just ship all` once: bank, report, package, verify, the mail draft, and stop.
# Nothing is sent; C-63 keeps sending in Ivo's hands. The label is removed BEFORE the
# ship runs, so a failed ship does not retry every hour, and the outcome is written
# back on the issue where the label was.
#
# Usage: bash scripts/harness/scheduled_bank.sh

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

FLEET_REPO="i-staykov/ark-fleet"
mkdir -p data/logs
LOG="data/logs/scheduled_bank.log"
LOCK="data/logs/.scheduled_bank.lock"
STAMP=$(date -u +%Y%m%dT%H%MZ)

# mkdir is the atomic primitive macOS has without flock. A lock whose holder is
# dead is stale and taken over; a live holder means a long rsync, and we leave.
if ! mkdir "$LOCK" 2>/dev/null; then
    holder=$(cat "$LOCK/pid" 2>/dev/null || true)
    if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
        printf '%s bank still running as pid %s, skipped\n' "$STAMP" "$holder" >> "$LOG"
        exit 0
    fi
    rm -rf "$LOCK" && mkdir "$LOCK" || exit 1
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

ship_now() {
    local n body
    n=$(gh issue list --repo "$FLEET_REPO" --state open --label ship-now \
        --json number --jq '.[0].number // empty' 2>/dev/null) || return 0
    [ -n "$n" ] || return 0
    echo "ship-now on $FLEET_REPO#$n: packaging"
    gh issue edit "$n" --repo "$FLEET_REPO" --remove-label ship-now >/dev/null 2>&1 || true
    if just ship all > "data/logs/ship_$STAMP.log" 2>&1; then
        body="Packaged by the hourly bank at $STAMP. Nothing was sent: the mail draft is on the laptop, under private/."
    else
        body="The hourly bank tried to package at $STAMP and \`just ship all\` failed. Label removed so it does not retry; the log is data/logs/ship_$STAMP.log on the laptop."
    fi
    # the log tail, without anything shaped like an address
    body="$body"$'\n\n```\n'"$(grep -vE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+|@' "data/logs/ship_$STAMP.log" | tail -15)"$'\n```'
    gh issue comment "$n" --repo "$FLEET_REPO" --body "$body" >/dev/null 2>&1 || true
    echo "ship-now: done, see $FLEET_REPO#$n"
}

{
    printf '\n===== scheduled bank %s =====\n' "$(date -u '+%F %T UTC')"
    just bank 2>&1
    printf -- '----- ship-now -----\n'
    ship_now 2>&1
} >> "$LOG"

# Keep the log readable rather than complete: the ledger and the store are the
# record, this is a noticeboard.
tail -n 2000 "$LOG" > "$LOG.trim" && mv "$LOG.trim" "$LOG"
