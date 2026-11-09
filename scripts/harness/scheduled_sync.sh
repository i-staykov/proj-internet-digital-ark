#!/usr/bin/env bash
# One unattended sync, for the hourly timer (`ark-sync.timer`) to call.
#
# `just sync` is the tick that moves the round without a session open: it brings the
# lanes' journals home and calls `just bank` when approvals, a baseline or journals arrived.
# It is idempotent, takes the sync lock and refuses a dirty or diverged clone, so all this
# adds is a log and the two labels that let a phone ask for a hold or a package.
#
# The `hold` label on any open ark-fleet issue is `just hold` (scripts/harness/hold.sh): the
# hold file and the flags go, the timer stays, so this runs hourly, `just sync` exiting `held`,
# and lifts the hold once the label is gone. While gh does not answer, nothing moves.
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
# No pull here: the recipe's preflight pulls under the sync lock, so a merged PR never swaps
# scripts under a running bank.

# The recipes' own `local.env`: without its ARK_DB_MEMORY_LIMIT the bank dies at DuckDB's 40%
# cap, and the floor the collectors read is the bank's (src/ark/disk.py). It assigns without
# `export`, so those values are exported and the hosts stay out of child environments.
[ -f local.env ] && . ./local.env
FLOOR=()  # the reader units' share of them
for v in ARK_DB_MEMORY_LIMIT ARK_FREE_SPACE_GIB ARK_WRITE_BUDGET_GIB; do
    [ -n "${!v:-}" ] || continue
    export "$v"; [ "$v" = ARK_DB_MEMORY_LIMIT ] || FLOOR+=(-E "$v=${!v}")
done
# The tick's commits go public, so they name the tick, never a login or a machine (AGENTS.md).
export GIT_AUTHOR_NAME=ark-tick GIT_COMMITTER_NAME=ark-tick
export GIT_AUTHOR_EMAIL=ark-tick@invalid GIT_COMMITTER_EMAIL=ark-tick@invalid

FLEET_REPO="i-staykov/ark-fleet"
mkdir -p data/logs
LOG="data/logs/scheduled_sync.log"
STAMP=$(date -u +%Y%m%dT%H%MZ)
START=$(date +%s)
# what the sync and the check said, for the tick row and the alerts (heartbeat.py)
SYNC_OUT=data/logs/.tick_sync.out CHECK_OUT=data/logs/.tick_check.out

# The walk follows its code: once the walker, its cron or the runners' cadence or STOP (its lane
# count) changed since the last install, the cron is reinstalled and the walkers stopped (SIGTERM
# saves what they owe); cron restarts them.
WALK=$(git rev-parse HEAD:scripts/engines/cdx_walk_jobs.py HEAD:scripts/engines/cdx_extended_walk.py; git ls-tree HEAD docs/registers/runner/cadence docs/registers/runner/STOP)
if [ "$WALK" != "$(cat data/logs/.walk_code 2>/dev/null)" ] && just walk install >> "$LOG" 2>&1; then
    pkill -f '^/usr/bin/python3 .*cdx_extended_walk[.]py'; echo "$WALK" > data/logs/.walk_code
    # a draining walker still owns its lane's pending subpages: none restarts beside it
    for _ in $(seq 120); do pgrep -f '^/usr/bin/python3 .*cdx_extended_walk[.]py' >/dev/null || break; sleep 5; done
fi
# The hooks follow their code too: one added since the install guards the next push.
just hooks > /dev/null 2>&1 || true

# No lock here: the recipe's `sync_lock.sh` is the one this and a hand-run `just sync` share.

hold_label() {  # on: before the sync, so it exits held; off: after, so the forced bank has the lock
    local n
    n=$(gh issue list --repo "$FLEET_REPO" --state open --label hold \
        --json number --jq '.[0].number // empty' 2>/dev/null) || return 0
    if [ "$1" = on ] && [ -n "$n" ]; then
        bash scripts/harness/hold.sh holds || bash scripts/harness/hold.sh on label
    elif [ "$1" = off ] && [ -z "$n" ] && bash scripts/harness/hold.sh holds; then
        bash scripts/harness/hold.sh off label
    fi
}

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
    # the remote's last successful listing, for the heartbeat
    rclone lsf --max-depth 1 gdrive:ark-offsite > /dev/null 2>&1 && echo "$STAMP" > data/logs/.offsite_listed || echo "offsite: listing failed"
    hold_label on 2>&1
    # the per-file lines of an idempotent ingest would fill the whole log; line buffering so
    # a reader mid-run sees where the sync is, not a stale block
    just sync 2>&1 | grep --line-buffered -vE '\| INFO +\| \[[0-9]+/[0-9]+\]' \
        | tee "$SYNC_OUT"
    sync_rc=${PIPESTATUS[0]}
    hold_label off 2>&1
    printf -- '----- ship-now -----\n'
    ship_now 2>&1
} >> "$LOG"

# Yesterday's productivity rows (scripts/agents/lane_yield.py), once a day after the 06 UTC
# bank, the heartbeat's condition; a failure is one line here, never the tick's.
if [ "${STAMP:9:2}" -ge 6 ] && [ "$(cat data/logs/.yield_day 2>/dev/null)" != "${STAMP:0:8}" ]; then
    if uv run python scripts/agents/lane_yield.py >> "$LOG" 2>&1; then echo "${STAMP:0:8}" > data/logs/.yield_day
    else echo "lane yield: failed, its error is above" >> "$LOG"; fi
fi

# The End of Term indexes, an HTTP Archive year, the ClueWeb09 map where the lanes walk and the
# Usenet header lane, every part left after the bank, each its own unit so it outlives this one,
# never two at once, and started only while its reader has a part under three strikes left, so a
# finished reader costs no request (scripts/sources/eot/eot_cdxj.py, httparchive/har_year.py,
# crawl_lists/clueweb.py, usenet/run_usenet_header_items.py; the count is check_unattended.py's).
if grep -q 'local:' <<<"${ARK_HOSTS:-}"; then
    for reader in eot:eot/eot_cdxj.py:eot_cdxj har:httparchive/har_year.py:har \
        clueweb:crawl_lists/clueweb.py:clueweb \
        header:usenet/run_usenet_header_items.py:usenet_header; do
        IFS=: read -r name script log <<<"$reader"  # unit, script, log
        [ "$(uv run python scripts/harness/check_unattended.py left "ark-$name" 2>> "$LOG")" = 0 ] && continue
        systemd-run --user --unit "ark-$name" --collect --working-directory="$PWD" -E PATH="$PATH" ${FLOOR[@]+"${FLOOR[@]}"} \
            bash -c "uv run python scripts/sources/$script >> data/logs/$log.log 2>&1" \
            >/dev/null 2>&1 || true
    done
fi

# The tick's status is the sync's, else the check's (scripts/harness/check_unattended.py), so a
# failed tick fails its unit; its last line says which. Before it, the tick's row in ticks.tsv,
# the alerts and, at 06 UTC, the heartbeat (scripts/harness/heartbeat.py).
{
    printf -- '----- check unattended -----\n'
    just check unattended 2>&1 | tee "$CHECK_OUT"
    check_rc=${PIPESTATUS[0]}
    printf -- '----- heartbeat -----\n'
    uv run python scripts/harness/heartbeat.py "$STAMP" "$START" "$sync_rc" "$check_rc" \
        "$SYNC_OUT" "$CHECK_OUT" 2>&1 | tail -20
    echo "tick $STAMP sync=$sync_rc check=$check_rc"
} >> "$LOG"

# Keep the log readable rather than complete: the ledger and the store are the
# record, this is a noticeboard.
tail -n 2000 "$LOG" > "$LOG.trim" && mv "$LOG.trim" "$LOG"

# unattended-upgrades installs and leaves the flag, never rebooting itself: the tick reboots, last,
# once nothing a reboot would cut runs (its own bank is done by then). Walkers and readers keep
# what they wrote; cron's @reboot brings the walkers back at once, the next :05 tick the readers,
# the sync lock stale in the new boot (sync_lock.sh). Never in a boot's first hour, so a flag that
# comes back at once cannot loop. A tick that waits says why, for the heartbeat's 24 h alert.
FLAG="${ARK_REBOOT_FLAG:-/var/run/reboot-required}"
busy() {
    [ "$(cut -d. -f1 "${ARK_UPTIME:-/proc/uptime}" 2> /dev/null || echo 0)" -ge 3600 ] ||
        echo "up under an hour"
    bash scripts/harness/sync_lock.sh holder > /dev/null && echo "a sync"
    systemctl --user is-active -q ark-bank-force && echo "the forced bank"
    [ ! -e data/logs/agent/.lock ] || flock -n data/logs/agent/.lock true || echo "an agent run"
    { grep -qx 'activ.*' <<< "$(systemctl show -P ActiveState apt-daily.service \
        apt-daily-upgrade.service 2> /dev/null)" || pgrep -x dpkg > /dev/null; } && echo "an apt run"
    # an ssh login, not a user manager's own session (systemd 256 on)
    loginctl list-sessions --no-legend 2> /dev/null | grep -qvwE 'manager(-early)?' && echo "a login"
    pgrep -f Runner.Worker > /dev/null && echo "a fleet job"
}
if [ -f "$FLAG" ] && [ "$(tail -n 1 data/logs/ticks.tsv 2> /dev/null | cut -f1)" = "$STAMP" ]; then
    why=$(busy | paste -sd , -)
    if [ -n "$why" ]; then
        echo "tick $STAMP: reboot pending, not now: $why" >> "$LOG"
    else
        echo "tick $STAMP: rebooting" >> "$LOG"
        sudo -n /usr/sbin/reboot >> "$LOG" 2>&1 ||
            echo "reboot refused: sudo asks a password; 'just vm install' prints the line" >> "$LOG"
    fi
fi
[ "$sync_rc" -ne 0 ] && exit "$sync_rc"
exit "$check_rc"
