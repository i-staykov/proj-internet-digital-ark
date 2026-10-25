#!/usr/bin/env bash
# The hold: the bank host's hourly timer, the walkers' `pause-platform` flag and the fleet's Leg,
# Read and Improver workflows stop, stay stopped across a reboot, and start again only when a
# human lifts them. `just hold` is the interface.
#
# `systemctl --user disable --now` persists across a reboot and lets a tick in flight finish. The
# hold file names what is held, one name per line under `human` and a UTC stamp. While it lists
# `ark-sync.timer`, `just sync` and `just bank` exit `held` unless one hand run sets
# `ARK_HOLD_BYPASS=dry-run` inline. A listed name this script does not know is NOT HELD, and
# `off` only drops its line.
#
# The bank host (ARK_VM, or this machine where local.env names none), the collector hosts and
# GitHub are asked, never relied on: without them the file and the local flag still go, and
# what could not be confirmed is printed, not fatal.
#
# Usage:
#   bash scripts/harness/hold.sh on             hold every name
#   bash scripts/harness/hold.sh off [name]     lift one name, or all of them and the file
#   bash scripts/harness/hold.sh status         HELD or NOT HELD, one line per name
#   bash scripts/harness/hold.sh holds [name]   exit 0 while the file lists the name, or exists
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

# ARK_HOSTS (`target:lane` each) and ARK_VM, the bank host when there is one, live in
# local.env, assigned without export, so they reach no child environment.
[ -f local.env ] && . ./local.env
STATE_DIR="${ARK_STATE_DIR:-$HOME/ark/state}"
HOLD="$STATE_DIR/hold"
TIMER="ark-sync.timer"
FLAGS="pause-platform"
WORKFLOWS="leg.yaml read.yaml improver.yaml"
# The fleet repo is named once, where the hourly job reads it.
FLEET_REPO=$(sed -n 's/^FLEET_REPO="\(.*\)"$/\1/p' scripts/harness/scheduled_sync.sh)
# On a host the flag follows that machine's own ARK_STATE_DIR.
REMOTE_DIR='d="${ARK_STATE_DIR:-$HOME/ark/state}"; mkdir -p "$d"'

in_list() { case " $2 " in *" $1 "*) return 0 ;; esac; return 1; }

names() { sed -n '3,$p' "$HOLD" 2>/dev/null; }

listed() { names | grep -x -- "$1" > /dev/null; }

drop() { grep -vx -- "$1" "$HOLD" > "$HOLD.tmp"; mv "$HOLD.tmp" "$HOLD"; }

# A host by its lane in what is printed: its target is never echoed. A `local` lane walks here.
on_host() { ssh -o ConnectTimeout=15 -o BatchMode=yes "${1%:*}" "$2" < /dev/null 2>/dev/null; }
remote_hosts() { for h in ${ARK_HOSTS:-}; do [ "${h%:*}" = local ] || echo "$h"; done; }

# The bank host's tick is its timer, here when local.env names no ARK_VM; 0 only once it has
# said it did what was asked.
vm() {
    if [ -n "${ARK_VM:-}" ]; then
        ssh -o ConnectTimeout=15 -o BatchMode=yes "$ARK_VM" "$1" < /dev/null 2>/dev/null
    else
        bash -c "$1" < /dev/null 2>/dev/null
    fi
}
vm_timer() { [ "$(vm "systemctl --user $1 $TIMER >/dev/null 2>&1 && echo done")" = done ]; }

# Write or remove flags on one host; 0 only once it has said it did.
host_flags() {
    local host=$1 verb=$2 cmd=$REMOTE_DIR f
    shift 2
    for f in "$@"; do
        if [ "$verb" = write ]; then
            cmd="$cmd && printf 'human\\n%s\\n' '$STAMP' > \"\$d/$f\""
        else
            cmd="$cmd && rm -f \"\$d/$f\""
        fi
    done
    [ "$(on_host "$host" "$cmd && echo done")" = done ]
}

# The state only when gh answered: on an HTTP error it prints the error body instead.
wf_state() {
    local s
    s=$(gh api "repos/$FLEET_REPO/actions/workflows/$1" --jq .state 2>/dev/null) && echo "$s"
}

cmd_on() {
    local rc=0 f wf
    mkdir -p "$STATE_DIR" || exit 1
    # The file goes first, so a tick that starts while this runs already reads it, and the
    # flag next, so the walkers idle after the page in flight.
    { printf 'human\n%s\n' "$STAMP"; printf '%s\n' $TIMER $FLAGS $WORKFLOWS; } > "$HOLD" || exit 1
    echo "hold: $HOLD written"
    for f in $FLAGS; do
        printf 'human\n%s\n' "$STAMP" > "$STATE_DIR/$f" || rc=1
    done
    echo "flags: $FLAGS written here"
    if vm_timer "disable --now"; then
        echo "$TIMER: disabled"
    else
        echo "$TIMER: unconfirmed, the bank host did not answer; its tick may still run"
    fi
    [ -n "${ARK_HOSTS:-}" ] || echo "hosts: unconfirmed, ARK_HOSTS is not set"
    for h in $(remote_hosts); do
        if host_flags "$h" write $FLAGS; then
            echo "lane ${h##*:} host: $FLAGS written"
        else
            echo "lane ${h##*:} host: unconfirmed, it did not answer; its walker may still run"
        fi
    done
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
    if [ "$name" = "$TIMER" ]; then
        vm_timer "enable --now" || { echo "$TIMER: unconfirmed, the bank host did not answer"; return 1; }
        echo "$TIMER: enabled"
    elif in_list "$name" "$FLAGS"; then
        rm -f "$STATE_DIR/$name"
        local rc=0
        for h in $(remote_hosts); do
            host_flags "$h" remove "$name" && continue
            echo "$name: removed here, unconfirmed on the lane ${h##*:} host"
            rc=1
        done
        [ "$rc" = 0 ] && echo "$name: removed"
        return $rc
    elif in_list "$name" "$WORKFLOWS"; then
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
    else
        echo "$name: not a hold name, dropped"
    fi
}

cmd_off() {
    local todo name rc=0
    [ -f "$HOLD" ] || { echo "hold: nothing is held"; return 0; }
    if [ -n "${1:-}" ]; then
        if ! in_list "$1" "$TIMER $FLAGS $WORKFLOWS" && ! listed "$1"; then
            echo "hold: no such name $1, one of: $TIMER $FLAGS $WORKFLOWS" >&2
            return 2
        fi
        listed "$1" || { echo "$1: not held"; return 0; }
        todo=$1
    else
        todo=$(names)
    fi
    for name in $todo; do
        # The line goes first, so a tick the timer starts does not read it as held.
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
    local remote="" name why rc=0 h block
    # One block per host, `lane N` to `end`: the flags it holds, then `answered`; a silent
    # host's block is empty and borrows nothing from the next.
    for h in $(remote_hosts); do
        remote+="lane ${h##*:}"$'\n'$(on_host "$h" 'd="${ARK_STATE_DIR:-$HOME/ark/state}"
            for f in '"$FLAGS"'; do [ "$(head -1 "$d/$f" 2>/dev/null)" = human ] && echo "$f"
            done; echo answered')$'\nend\n'
    done
    for name in $TIMER $FLAGS $WORKFLOWS; do
        why=""
        if ! listed "$name"; then
            why="not in the hold file"
        elif [ "$name" = "$TIMER" ]; then
            case "$(vm "systemctl --user is-enabled $TIMER 2>/dev/null; echo answered")" in
            enabled*) why="enabled on the bank host" ;;
            *answered*) ;;
            *) why="the bank host did not answer" ;;
            esac
        elif in_list "$name" "$FLAGS"; then
            [ "$(head -1 "$STATE_DIR/$name" 2>/dev/null)" = human ] || why="no flag here"
            [ -n "${ARK_HOSTS:-}" ] || why="${why:+$why, }ARK_HOSTS is not set"
            for h in $(remote_hosts); do
                block=$(printf '%s\n' "$remote" | sed -n "/^lane ${h##*:}\$/,/^end\$/p")
                if ! printf '%s\n' "$block" | grep -qx answered; then
                    why="${why:+$why, }the lane ${h##*:} host did not answer"
                elif ! printf '%s\n' "$block" | grep -qx -- "$name"; then
                    why="${why:+$why, }no flag on the lane ${h##*:} host"
                fi
            done
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
    for name in $(names); do
        in_list "$name" "$TIMER $FLAGS $WORKFLOWS" && continue
        echo "NOT HELD  $name: not a hold name; 'just hold off $name' drops it"
        rc=1
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
