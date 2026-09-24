#!/usr/bin/env bash
# The laptop's CDX parent sweep lane and the three commands that steer it. The lane is
# closed: its sweep loop is deleted, so `run` (what launchd calls) starts nothing and exits.
# `just collectors pause|resume|status` is the whole interface.
#
# The pause is a flag FILE, which is what makes it survive sleep and reboot: the sweep
# checks it between pages (`cdx_suffix_sweep.py`), so a pause costs at most the page in
# flight and loses nothing, since the journal is written under its final name and flushed
# every page. Resume is removing the file; the per-parent state files mean the queue
# continues from its marker with no other step.
#
# Usage:
#   bash scripts/harness/collectors.sh run       launchd calls this; the lane is closed
#   bash scripts/harness/collectors.sh pause     stop after the current page
#   bash scripts/harness/collectors.sh resume    continue from the marker
#   bash scripts/harness/collectors.sh status    running or paused, parent, journal, hit rate
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

# local.env is the machine-local config (gitignored): the VPS address lives there, and so
# does any knob this laptop wants different from the default. The environment still wins.
[ -f local.env ] && . ./local.env
: "${ARK_STATE_DIR:=$HOME/ark/state}"
: "${ARK_CDX_BUDGET:=2}"

STATE_DIR="$ARK_STATE_DIR"
FLAG="$STATE_DIR/pause"
# A pause a human asked for must not expire. The sweep loop expires a flag left behind by
# a fleet wave after 9,000 s, which is right for a forgotten heartbeat and wrong here, so
# this one says who wrote it on its first line and the loop leaves it alone.
FLAG_MARK="human"
# The archive-client cap binds the CDX channel, not the machine, so `status` counts every
# client on it, this laptop's and the VPS's, against ARK_CDX_BUDGET.
BUDGET="$ARK_CDX_BUDGET"
LOCK="data/logs/.collectors.lock"

note() { printf '%s %s\n' "$(date -u '+%FT%TZ')" "$*"; }

paused() { [ -e "$FLAG" ]; }

# A client is the journal it holds open, not a process: one client is a `uv run` wrapper
# plus its python child, so counting processes doubles it.
local_clients() {
    for pid in $(pgrep -f cdx_suffix_sweep.py 2>/dev/null); do
        if [ -d "/proc/$pid/fd" ]; then
            ls -l "/proc/$pid/fd" 2>/dev/null | grep -oE "(suffix|cdx)_[^ /]*jsonl\.gz"
        else
            lsof -p "$pid" 2>/dev/null | grep -oE "(suffix|cdx)_[^ /]*jsonl\.gz"
        fi
    done | sort -u
}

count() { printf '%s\n' "$1" | grep -c . ; }

# What the OTHER machine on the channel is spending, which is the number that decides
# whether this laptop may start anything at all (C-77 binds the channel, not the machine).
#
# Two subtleties, both learned the hard way in this repository. **A loop between parents is
# still a client**: it holds no journal for the seconds it spends refilling, and a laptop
# that started a sweep in that gap would put three clients on the channel, so the answer is
# the LARGER of its open journals and its running loops. And **a paused client spends
# nothing**: once the VPS is paused its sweeps idle with their journals still open, so
# counting those would keep this laptop out for ever. Paused is therefore read as zero, but
# only once the journals have actually gone quiet, which is the honest test for "the page in
# flight has finished" and the one thing a flag file cannot tell us.
#
# **An unanswered question is not an answer of zero**, which is the way this could have put
# four clients on the channel: the VPS holds two whether or not the link is up, so a failed
# ssh once read as "the channel is free" and would have started both laptop sweeps beside
# them. Unknown is therefore worth ONE remote client here, which leaves this laptop one
# slot rather than none, until S8 stops the VPS sweeps and the answer is a real zero.
#
# ARK_NO_REMOTE skips the question outright, for a machine with no link and for the tests,
# which must not spend eight seconds on an ssh timeout to decide a local invariant; it is
# not a claim that the VPS is idle, so it costs the same one client.
vps_clients() (
    # **0, not "unknown".** The caller counts an unreadable answer as one client, which is
    # the safe default against the cap, so "not asked" silently cost this laptop half the
    # channel every window. Under C-88 all three archive clients are here and the VPS runs
    # none, so a machine that says it has no remote is stating a fact, not declining to look.
    [ "${ARK_NO_REMOTE:-0}" = "1" ] && { echo 0; return; }
    [ -n "${ARK_VPS:-}" ] || { echo "unknown"; return; }
    local out
    out=$(ARK_VPS_REPO="${ARK_VPS_REPO:-/projects/proj-internet-digital-ark}" \
        ssh -o ConnectTimeout=8 -o BatchMode=yes -o SendEnv=ARK_VPS_REPO "$ARK_VPS" \
        "REPO='${ARK_VPS_REPO:-/projects/proj-internet-digital-ark}' QUIET=${ARK_VPS_QUIET:-300} bash -s" \
        <<'REMOTE' 2>/dev/null
cd "$REPO" 2>/dev/null || exit 1
flag="${ARK_STATE_DIR:-$HOME/ark/state}/pause"
if [ -e "$flag" ]; then
    # Quiet is measured on any journal, not on a `.part`: the other machine's sweep writes
    # its final name directly, so a `.part` glob found nothing and read every paused machine
    # as quiet the instant the flag appeared, grace included. `ls -t` and `stat` rather than
    # `find -newermt`, because the relative timestamp that syntax needs is GNU find's and
    # this laptop's `find` is bfs, which refuses it: the probe has to read the same on both.
    newest=$(ls -t data/raw/cdx_suffix/*.jsonl.gz* data/raw/cdx/*.jsonl.gz* 2>/dev/null | head -1)
    if [ -z "$newest" ]; then echo 0; exit 0; fi
    mtime=$(stat -c %Y "$newest" 2>/dev/null || stat -f %m "$newest" 2>/dev/null || echo 0)
    if [ $(( $(date +%s) - mtime )) -ge "$QUIET" ]; then echo 0; exit 0; fi
fi
journals=$(for pid in $(pgrep -f cdx_suffix_sweep.py 2>/dev/null); do
    ls -l /proc/$pid/fd 2>/dev/null | grep -oE '(suffix|cdx)_[^ /]*jsonl[.]gz'
done | sort -u | grep -c .)
loops=$(pgrep -fc 'platform_sweep_loop[.]sh' 2>/dev/null || echo 0)
[ "$loops" -gt "$journals" ] && echo "$loops" || echo "$journals"
REMOTE
    )
    case "$out" in
    "" | *[!0-9]*) echo "unknown" ;;
    *) echo "$out" ;;
    esac
)

# Newest journal the sweeps are writing or have just written, and what it holds. **No `.part`
# in this lane**: `cdx_suffix_sweep.py` opens its final name and flushes after every page, so
# the file being written and the file that is finished have the same name, and a glob for
# `.part` here matched nothing. Reading a journal still being written has no gzip trailer, so
# python's reader returns everything up to the last flush and then raises EOFError, which is
# the normal case.
newest_journal() {
    ls -t data/raw/cdx_suffix/suffix_*.jsonl.gz 2>/dev/null | head -1
}

hit_rate() {
    ARK_JOURNAL="$1" python3 - <<'PY'
import gzip, json, os
rows = 0
hosts = set()
years = 0
try:
    with gzip.open(os.environ["ARK_JOURNAL"], "rt") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            rows += 1
            url = rec.get("url") or ""
            hosts.add(url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0].lower())
            if rec.get("timestamp"):
                years += 1
except Exception:
    pass
hosts.discard("")
if not rows:
    print("   hit rate: nothing readable in it yet")
else:
    print(f"   hit rate: {rows:,} capture rows, {len(hosts):,} distinct hosts, "
          f"{rows / max(len(hosts), 1):.1f} rows per host, {years:,} dated")
PY
}

cmd_pause() {
    mkdir -p "$STATE_DIR"
    printf '%s\n%s\n' "$FLAG_MARK" "$(date -u '+%FT%TZ')" > "$FLAG"
    echo "paused: $FLAG written, no expiry"
    echo "  the sweeps finish the page in flight and idle; launchd stays loaded"
    echo "  it survives sleep and reboot. 'just collectors resume' is the only step back"
}

cmd_resume() {
    if bash scripts/harness/hold.sh holds pause; then
        echo "collectors: the hold lists pause; 'just hold off pause' lifts it" >&2
        exit 1
    fi
    if [ -e "$FLAG" ]; then
        rm -f "$FLAG"
        echo "resumed: $FLAG removed"
    else
        echo "resumed: no pause flag was set"
    fi
    echo "  each parent continues from its own state file, so nothing is re-fetched"
}

cmd_status() {
    local job clients n parent journal
    job=$(launchctl list 2>/dev/null | awk '$3 == "com.ark.collectors" { print "pid " $1 ", last exit " $2 }')
    echo "launchd: ${job:-com.ark.collectors not loaded}"

    if paused; then
        echo "state:   PAUSED since $(sed -n 2p "$FLAG" 2>/dev/null || echo unknown)"
    elif [ -d "$LOCK" ]; then
        echo "state:   running, supervisor pid $(cat "$LOCK/pid" 2>/dev/null || echo unknown)"
    else
        echo "state:   no supervisor here"
    fi

    clients=$(local_clients)
    n=$(count "$clients")
    echo "clients: $n here holding a journal open (the channel allows $BUDGET)"
    [ "$n" -gt 0 ] && printf '%s\n' "$clients" | sed 's/^/     /'
    # The same channel, another machine: four clients is over budget, and S8 is the fix.
    # An unanswered question is worth one client to the supervisor, so say that here too
    # rather than printing a word the reader has to translate.
    there=$(vps_clients)
    case "$there" in
    "" | *[!0-9]*) echo "         VPS: $there, so counted as 1 client on the same channel" ;;
    *) echo "         VPS: $there on the same channel" ;;
    esac

    parent=$(ls -t data/logs/collectors_shard*.log 2>/dev/null | head -1)
    if [ -n "$parent" ]; then
        echo "parent:  $(grep -h '^=== ' "$parent" | tail -1 | sed 's/^=== //; s/ ===$//')"
    else
        echo "parent:  no shard log yet"
    fi

    journal=$(newest_journal)
    if [ -n "$journal" ]; then
        echo "journal: $(basename "$journal") last written $(date -r "$journal" '+%F %H:%M:%S %Z')"
        hit_rate "$journal"
    else
        echo "journal: none written yet"
    fi
}

cmd_run() {
    # A KeepAlive restart under a hold does nothing: only `just hold off` brings the lane back.
    if bash scripts/harness/hold.sh holds com.ark.collectors; then echo held; exit 0; fi
    note "the CDX parent sweep lane is closed, nothing starts"
    exit 0
}

case "${1:-status}" in
run) cmd_run ;;
pause) cmd_pause ;;
resume) cmd_resume ;;
status) cmd_status ;;
*)
    echo "collectors: run pause resume status" >&2
    exit 2
    ;;
esac
