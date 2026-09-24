#!/usr/bin/env bash
# The hold: every laptop job, both pause flags and the fleet's scheduled workflows stop, stay
# stopped across a reboot, and start again only when a human lifts them. `just hold` is the
# interface.
#
# A reboot undoes a bootout, because launchd loads every plist in ~/Library/LaunchAgents at
# login. `launchctl disable` is what persists, so `on` disables a job before booting it out and
# `off` enables it before bootstrapping it. The hold file names what is held, one name per line
# under `human` and a UTC stamp: `just sync` and the collector supervisor exit `held` while it
# lists their job, and `just schedule install` refuses while it exists.
#
# The VPS and GitHub are asked, never relied on: without them the jobs and the local flags
# still go, and what could not be confirmed is printed, not fatal.
#
# Usage:
#   bash scripts/harness/hold.sh on             hold every name
#   bash scripts/harness/hold.sh off [name]     lift one name, or all of them and the file
#   bash scripts/harness/hold.sh status         HELD or NOT HELD, one line per name
#   bash scripts/harness/hold.sh holds [name]   exit 0 while the file lists the name, or exists
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

# ARK_VPS lives in local.env, assigned without export, so it reaches no child environment.
[ -f local.env ] && . ./local.env
STATE_DIR="${ARK_STATE_DIR:-$HOME/ark/state}"
HOLD="$STATE_DIR/hold"
AGENTS="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"
JOBS="com.ark.sync com.ark.collectors com.ark.cycle com.ark.digest"
FLAGS="pause pause-platform"
WORKFLOWS="wave.yaml improver.yaml"
# The fleet repo is named once, where the hourly job reads it.
FLEET_REPO=$(sed -n 's/^FLEET_REPO="\(.*\)"$/\1/p' scripts/harness/scheduled_sync.sh)
# On the VPS the flags follow that machine's own ARK_STATE_DIR.
REMOTE_DIR='d="${ARK_STATE_DIR:-$HOME/ark/state}"; mkdir -p "$d"'

in_list() { case " $2 " in *" $1 "*) return 0 ;; esac; return 1; }

listed() { [ -f "$HOLD" ] && grep -qx -- "$1" "$HOLD"; }

names() { sed -n '3,$p' "$HOLD" 2>/dev/null; }

drop() { grep -vx -- "$1" "$HOLD" > "$HOLD.tmp"; mv "$HOLD.tmp" "$HOLD"; }

loaded() { launchctl list 2>/dev/null | awk -v j="$1" '$3 == j { f = 1 } END { exit !f }'; }

running() { launchctl list 2>/dev/null | awk -v j="$1" '$3 == j && $1 ~ /^[0-9]+$/ { print $1 }'; }

vps() { ssh -o ConnectTimeout=15 -o BatchMode=yes "$ARK_VPS" "$1" < /dev/null 2>/dev/null; }

# Write or remove flags on the VPS; 0 only once it has said it did.
vps_flags() {
    local verb=$1 cmd=$REMOTE_DIR f
    shift
    for f in "$@"; do
        if [ "$verb" = write ]; then
            cmd="$cmd && printf 'human\\n%s\\n' '$STAMP' > \"\$d/$f\""
        else
            cmd="$cmd && rm -f \"\$d/$f\""
        fi
    done
    [ "$(vps "$cmd && echo done")" = done ]
}

# The state only when gh answered: on an HTTP error it prints the error body instead.
wf_state() {
    local s
    s=$(gh api "repos/$FLEET_REPO/actions/workflows/$1" --jq .state 2>/dev/null) && echo "$s"
}

cmd_on() {
    local rc=0 job f wf was waited
    mkdir -p "$STATE_DIR" || exit 1
    # The file goes first, so a job that starts while this runs already reads it, and the
    # flags next, so the sweeps idle after the page in flight before their job goes.
    { printf 'human\n%s\n' "$STAMP"; printf '%s\n' $JOBS $FLAGS $WORKFLOWS; } > "$HOLD" || exit 1
    echo "hold: $HOLD written"
    for f in $FLAGS; do
        printf 'human\n%s\n' "$STAMP" > "$STATE_DIR/$f" || rc=1
    done
    echo "flags: $FLAGS written here"
    for job in $JOBS; do
        if ! launchctl disable "$DOMAIN/$job"; then
            echo "$job: FAILED to disable"
            rc=1
            continue
        fi
        # A sync in flight finishes: no new one starts past the file, and a bootout would end
        # an ingest mid-write.
        waited=0
        while [ "$job" = com.ark.sync ] && [ -n "$(running "$job")" ] &&
            [ "$waited" -lt "${ARK_HOLD_WAIT:-3600}" ]; do
            [ "$waited" = 0 ] && echo "$job: a sync is running, waiting for it to finish"
            sleep 10
            waited=$((waited + 10))
        done
        was="was not loaded"
        loaded "$job" && was="booted out"
        launchctl bootout "$DOMAIN/$job" 2>/dev/null || true
        if loaded "$job"; then
            echo "$job: disabled, FAILED to boot out"
            rc=1
        else
            echo "$job: disabled, $was"
        fi
    done
    if [ -z "${ARK_VPS:-}" ]; then
        echo "VPS: unconfirmed, ARK_VPS is not set; the walker there may still run"
    elif vps_flags write $FLAGS; then
        echo "VPS: $FLAGS written"
    else
        echo "VPS: unconfirmed, it did not answer; the walker there may still run"
    fi
    for wf in $WORKFLOWS; do
        case "$(wf_state "$wf")" in
        disabled*) echo "$wf: already disabled" ;;
        active)
            if gh workflow disable "$wf" --repo "$FLEET_REPO" > /dev/null 2>&1; then
                echo "$wf: disabled"
            else
                echo "$wf: unconfirmed, the disable was refused"
            fi
            ;;
        *) echo "$wf: unconfirmed, gh did not answer" ;;
        esac
    done
    return $rc
}

# Lift one name; 0 once it is lifted.
lift() {
    local name=$1
    if in_list "$name" "$JOBS"; then
        launchctl enable "$DOMAIN/$name" || { echo "$name: FAILED to enable"; return 1; }
        if [ ! -f "$AGENTS/$name.plist" ]; then
            echo "$name: enabled, no plist to load"
            return 0
        fi
        launchctl bootstrap "$DOMAIN" "$AGENTS/$name.plist" 2>/dev/null
        if ! loaded "$name"; then
            # It goes back in the file, so it goes back to disabled: a login must not load it.
            launchctl disable "$DOMAIN/$name"
            echo "$name: FAILED to bootstrap, disabled again"
            return 1
        fi
        echo "$name: enabled, bootstrapped"
    elif in_list "$name" "$FLAGS"; then
        rm -f "$STATE_DIR/$name"
        if [ -n "${ARK_VPS:-}" ] && ! vps_flags remove "$name"; then
            echo "$name: removed here, unconfirmed on the VPS"
            return 1
        fi
        echo "$name: removed"
    else
        case "$(wf_state "$name")" in
        active) echo "$name: already active" ;;
        disabled*)
            gh workflow enable "$name" --repo "$FLEET_REPO" > /dev/null 2>&1 ||
                { echo "$name: unconfirmed, the enable was refused"; return 1; }
            echo "$name: enabled"
            ;;
        *)
            echo "$name: unconfirmed, gh did not answer"
            return 1
            ;;
        esac
    fi
}

cmd_off() {
    local todo name rc=0
    [ -f "$HOLD" ] || { echo "hold: nothing is held"; return 0; }
    if [ -n "${1:-}" ]; then
        if ! in_list "$1" "$JOBS $FLAGS $WORKFLOWS"; then
            echo "hold: no such name $1, one of: $JOBS $FLAGS $WORKFLOWS" >&2
            return 2
        fi
        listed "$1" || { echo "$1: not held"; return 0; }
        todo=$1
    else
        todo=$(names)
    fi
    for name in $todo; do
        # The line goes first, so a job started by its own bootstrap does not read it as held.
        drop "$name"
        lift "$name" || { echo "$name" >> "$HOLD"; rc=1; }
    done
    if [ -z "$(names)" ]; then
        rm -f "$HOLD"
        echo "hold: lifted, $HOLD removed"
    else
        echo "hold: still held: $(names | tr '\n' ' ')"
    fi
    return $rc
}

cmd_status() {
    local disabled remote="" name why rc=0
    disabled=$(launchctl print-disabled "$DOMAIN" 2>/dev/null)
    if [ -n "${ARK_VPS:-}" ]; then
        remote=$(vps 'd="${ARK_STATE_DIR:-$HOME/ark/state}"; for f in '"$FLAGS"'; do
            [ "$(head -1 "$d/$f" 2>/dev/null)" = human ] && echo "$f"; done; echo answered')
    fi
    for name in $JOBS $FLAGS $WORKFLOWS; do
        why=""
        if ! listed "$name"; then
            why="not in the hold file"
        elif in_list "$name" "$JOBS"; then
            printf '%s\n' "$disabled" | grep -qE "\"$name\" => (disabled|true)" || why="not disabled"
            loaded "$name" && why="${why:+$why, }loaded"
        elif in_list "$name" "$FLAGS"; then
            [ "$(head -1 "$STATE_DIR/$name" 2>/dev/null)" = human ] || why="no flag here"
            if [ -z "${ARK_VPS:-}" ]; then
                why="${why:+$why, }ARK_VPS is not set"
            elif ! printf '%s\n' "$remote" | grep -qx answered; then
                why="${why:+$why, }the VPS did not answer"
            elif ! printf '%s\n' "$remote" | grep -qx -- "$name"; then
                why="${why:+$why, }no flag on the VPS"
            fi
        else
            case "$(wf_state "$name")" in
            disabled*) ;;
            "") why="gh did not answer" ;;
            *) why="active" ;;
            esac
        fi
        if [ -z "$why" ]; then
            echo "HELD      $name"
        else
            echo "NOT HELD  $name: $why"
            rc=1
        fi
    done
    return $rc
}

STAMP=$(date -u '+%FT%TZ')
case "${1:-status}" in
on) cmd_on ;;
off) cmd_off "${2:-}" ;;
status) cmd_status ;;
holds) if [ -n "${2:-}" ]; then listed "$2"; else [ -f "$HOLD" ]; fi ;;
*)
    echo "hold: on off status" >&2
    exit 2
    ;;
esac
