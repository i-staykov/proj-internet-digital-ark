#!/usr/bin/env bash
# What both CDX engines are doing right now, in one screen.
#
# Two machines run the same collector against disjoint shards of the same queue,
# and a second machine's output is invisible to every measurement taken on the
# first. That asymmetry has already cost this project once: the VPS ran for a day
# and a half with 5,793 year-records sitting on its disk and absent from the store,
# because nothing here ever looked. So this asks both.
#
# **Everything here globs `cdx_*` rather than a named prefix, and that is not
# laziness.** The first version hardcoded `cdx_gap_vps_*` and `cdx_gap_*`. When the
# merged queue renamed the journals to `cdx_q0_*` and `cdx_q1_*` on 7 August, this
# script kept reporting "none, everything is home" while five VPS journals holding
# 1,500 queries sat unfetched, and kept printing a "last finished batch" line from a
# run that had ended hours earlier. A monitor that silently narrows to a stale name
# is worse than no monitor, because it answers the question confidently and wrongly.
# Match the whole family; the prefix is the collector's business, not the watcher's.
#
# **And it narrowed twice more, which cost a wrong answer on 2026-09-09.** It reported
# "NOT RUNNING" for a VPS that had two healthy collectors up for two and a half hours,
# because it looked for `supervise_cdx_pool.sh` while that machine runs
# `platform_sweep_loop.sh` as a systemd user unit; and it printed a "journal" line from
# 2026-09-01 because it globbed `cdx_*.jsonl.gz.part` while the platform sweep writes
# `suffix_<parent>_<stamp>.jsonl.gz`. Both are the same mistake as the one above, and
# acting on that answer cost a restart that threw away two parents mid-sweep. So the
# question asked here is no longer "is a named process alive" but the one the rule is
# actually about: **how many archive clients hold a journal open**, which is how
# `restart_sweeps.sh` counts and how the two-client limit is defined (C-77).
#
# **The two machines do not agree about what time it is, and their logs do not say
# so.** The MacBook writes CEST and the VPS writes UTC, so a log line reading
# "06:36" on one and "08:36" on the other is the same instant. On 8 August that cost
# a false stall report: the VPS looked three hours idle when its batch was 55 minutes
# old, and what caught it was the process `etime` disagreeing with the log timestamp.
# Both clocks are printed below so the comparison is possible at all, and elapsed
# time is preferred over wall-clock wherever one will do.
#
# Reads the in-flight `.part` journal, which has no gzip trailer, so `gzip -dc`
# refuses it outright while Python's reader returns every record up to the last
# flush and then raises EOFError. That EOFError is the normal case here.
#
# The tier mix is the useful column. `host` is the cheap query answering on its
# own, `root` is a domain so heavily archived that the server gave up and the
# apex and www root pages rescued it, `scan` is the wildcard fallback for a domain
# with nothing on its own host. A run drifting toward `root` is working through a
# clogged stretch of queue and will speed up; a run drifting toward failures is
# being refused and wants fewer workers, not more.
#
# Usage: bash scripts/engines/engine_status.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

# The VPS address is deliberately not in the repository: the repo is public and the
# address is private infrastructure. Set ARK_VPS in the environment or in local.env
# at the repo root (gitignored), e.g. ARK_VPS=user@host.
ROOT_FOR_ENV="$(cd "$(dirname "$0")" && git rev-parse --show-toplevel 2>/dev/null || pwd)"
[ -f "$ROOT_FOR_ENV/local.env" ] && . "$ROOT_FOR_ENV/local.env"
VPS="${ARK_VPS:?set ARK_VPS (user@host), in the environment or in local.env}"
VPS_REPO="${ARK_VPS_REPO:-/projects/proj-internet-digital-ark}"

read -r -d '' TALLY <<'PY' || true
import gzip, json, os, sys
p = os.environ.get("ARK_PART") or ""
n = ok = yr = h = r = sc = f = 0
try:
    with gzip.open(p, "rt") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            n += 1
            if d.get("status") == 200:
                ok += 1
                yr += len(d.get("years") or [])
                s = d.get("strategy")
                if s == "by_host":
                    h += 1
                elif s == "by_root":
                    r += 1
                else:
                    sc += 1
            else:
                f += 1
except Exception:
    pass
if not n:
    print("   no in-flight journal readable yet")
    sys.exit()
print(f"   {n:,} queried, {ok:,} answered, {yr:,} year-records")
print(f"   tiers: host={h:,} root={r:,} scan={sc:,}   failures={f:,} ({100*f/max(n,1):.0f}%)")
PY

# One client is a `uv run` wrapper PLUS its python child, so counting processes doubles
# it. A client is the JOURNAL it holds open, so that is what is counted. Linux has
# /proc; macOS does not, and falls back to lsof.
sweep_clients() {
    for pid in $(pgrep -f cdx_suffix_sweep.py 2>/dev/null); do
        if [ -d "/proc/$pid/fd" ]; then
            ls -l "/proc/$pid/fd" 2>/dev/null | grep -oE "(suffix|cdx)_[^ /]*jsonl\.gz"
        else
            lsof -p "$pid" 2>/dev/null | grep -oE "(suffix|cdx)_[^ /]*jsonl\.gz"
        fi
    done | sort -u
}

# Any collector LOOP, by family rather than by one name: the laptop runs the supervisor,
# the VPS runs the platform sweep loop under systemd, and both are collectors.
LOOPS="supervise_cdx_pool[.]sh|platform_sweep_loop[.]sh"

section() { printf '\n== %s ==\n' "$1"; }

section "clocks (both machines, so log timestamps can be compared at all)"
printf '   local %s   |   %s\n' "$(date '+%F %H:%M:%S %Z')" "$(date -u '+%H:%M:%SZ')"
ssh -o ConnectTimeout=8 -o BatchMode=yes "$VPS" \
    "printf '   VPS   %s   |   %s\\n' \"\$(date '+%F %H:%M:%S %Z')\" \"\$(date -u '+%H:%M:%SZ')\""\
    2>/dev/null || echo "   VPS   unreachable"

section "local"
if ps -eo etime,command | grep -qE "$LOOPS"; then
    ps -eo etime,command | grep -E "$LOOPS" | head -2 | sed 's/^/   up /'
else
    echo "   no collector loop"
fi
open_now=$(sweep_clients)
if [ -n "$open_now" ]; then
    printf '   archive clients holding a journal open: %s (the rule allows 2)\n' \
        "$(printf '%s\n' "$open_now" | wc -l | tr -d ' ')"
    printf '%s\n' "$open_now" | sed 's/^/     /'
else
    echo "   no archive client holds a journal open here"
fi
# **A stale `.part` is not an in-flight journal, and reading one is how this line lied.**
# On 2026-09-09 it printed a tally from a `.part` abandoned on 2026-09-01 while two
# collectors were live, because `ls -t` returns the newest file whether or not anything
# still holds it. Anything older than an hour is named and NOT read.
part=$(ls -t data/raw/cdx/cdx_*.jsonl.gz.part data/raw/cdx/suffix_*.jsonl.gz.part 2>/dev/null | head -1)
if [ -n "$part" ] && [ -n "$(find "$part" -mmin -60 2>/dev/null)" ]; then
    echo "   journal $(basename "$part")"
    ARK_PART="$part" python3 -c "$TALLY"
elif [ -n "$part" ]; then
    echo "   newest .part is STRANDED, not read: $(basename "$part")"
else
    echo "   no in-flight .part journal"
fi
echo "   last finished batch:"
grep -hoE "cdx: \{[^}]*\}" $(ls -t data/logs/cdx_*.log 2>/dev/null | head -1) 2>/dev/null \
    | tail -1 | sed 's/^/     /'

section "VPS ($VPS)"
# The remote half asks the same two questions in the same order, and must not narrow to
# one script name: this machine runs its loops as systemd user units, so `systemctl` is
# asked as well as the process table. Everything is single-quoted through ssh except the
# variables that have to expand here, because a bracketed pattern is what stops `pgrep`
# and `grep` from matching the command line of the probe itself.
ssh -o ConnectTimeout=8 -o BatchMode=yes "$VPS" "
cd '$VPS_REPO' || exit 1
if ps -eo etime,command | grep -qE '$LOOPS'; then
    ps -eo etime,command | grep -E '$LOOPS' | head -2 | sed 's/^/   up /'
else
    echo '   no collector loop'
fi
systemctl --user list-units 'ark-sweep*' --no-legend 2>/dev/null | sed 's/^/   unit /'
open_now=\$(for pid in \$(pgrep -f cdx_suffix_sweep.py 2>/dev/null); do
    ls -l /proc/\$pid/fd 2>/dev/null | grep -oE '(suffix|cdx)_[^ /]*jsonl[.]gz'
done | sort -u)
if [ -n \"\$open_now\" ]; then
    printf '   archive clients holding a journal open: %s (the rule allows 2)\n' \
        \"\$(printf '%s\n' \"\$open_now\" | wc -l | tr -d ' ')\"
    printf '%s\n' \"\$open_now\" | sed 's/^/     /'
else
    echo '   no archive client holds a journal open there'
fi
part=\$(ls -t data/raw/cdx/cdx_*.jsonl.gz.part data/raw/cdx/suffix_*.jsonl.gz.part 2>/dev/null | head -1)
if [ -n \"\$part\" ] && [ -n \"\$(find \"\$part\" -mmin -60 2>/dev/null)\" ]; then
    echo \"   journal \$(basename \"\$part\")\"
    ARK_PART=\"\$part\" python3 -c '$TALLY'
elif [ -n \"\$part\" ]; then
    echo \"   newest .part is STRANDED, not read: \$(basename \"\$part\")\"
else
    echo '   no in-flight .part journal'
fi
echo '   last finished batch:'
grep -hoE 'cdx: \{[^}]*\}' \$(ls -t data/logs/cdx_*.log data/logs/*sweep*.log 2>/dev/null | head -1) 2>/dev/null \
    | tail -1 | sed 's/^/     /'
" 2>&1 | grep -v "^Warning: Permanently added" || echo "   unreachable (VPN down?)"

section "journals on the VPS not yet copied here"
# The remote listing and the reachability check are separate facts, and conflating
# them is how this section lied. When ssh failed, `$remote` came back empty, the
# loop body never ran, `missing` stayed 0 and it printed "none, everything is home"
# about a machine it had not been able to ask. That is the exact failure this whole
# section exists to catch: the VPS once ran for a day and a half with 5,793
# year-records on its disk and absent from the store, because nothing here looked.
# So an unanswered question now reads as unanswered.
remote=$(ssh -o ConnectTimeout=8 -o BatchMode=yes "$VPS" \
    "ls '$VPS_REPO'/data/raw/cdx/cdx_*.jsonl.gz 2>/dev/null | xargs -n1 basename 2>/dev/null" 2>/dev/null)
ssh_status=$?
if [ "$ssh_status" -ne 0 ]; then
    echo "   UNKNOWN: could not reach $VPS to ask (ssh exit $ssh_status)"
    echo "   This is not 'nothing to fetch'. Bring the link up and re-run, then:"
    echo "     rsync -av --ignore-existing '$VPS:$VPS_REPO/data/raw/cdx/cdx_*.jsonl.gz' data/raw/cdx/"
elif [ -z "$remote" ]; then
    echo "   reachable, but it lists no journals at $VPS_REPO/data/raw/cdx/"
    echo "   Check ARK_VPS_REPO: an empty listing from a live host usually means"
    echo "   the repository is somewhere else on it."
else
    missing=0
    total=0
    for f in $remote; do
        total=$((total + 1))
        [ -e "data/raw/cdx/$f" ] || { echo "   $f"; missing=$((missing + 1)); }
    done
    if [ "$missing" -eq 0 ]; then
        echo "   none of its $total journals is missing, everything is home"
    else
        echo "   $missing of $total missing. Bring them home with:"
        echo "     rsync -av --ignore-existing '$VPS:$VPS_REPO/data/raw/cdx/cdx_*.jsonl.gz' data/raw/cdx/"
        echo "   then ingest them: uv run ark ingest cdx_snapshot data/raw/cdx/cdx_*.jsonl.gz"
    fi
fi

section "power"
pmset -g batt 2>/dev/null | head -1 | sed 's/^/   /'
pgrep -q caffeinate && echo "   caffeinate is holding idle sleep off" \
    || echo "   NO caffeinate: the machine can idle-sleep and stop the run"
