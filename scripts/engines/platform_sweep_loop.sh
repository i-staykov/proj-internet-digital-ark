#!/usr/bin/env bash
# Keep one archive client busy until the deadline, refilling its own queue, and
# never let one parent hold the slot.
#
# Why this exists, beside platform_sweep.sh: that script walks a fixed file and
# prints "queue walked". When the file runs out the process EXITS, and nothing
# notices. On 2026-09-05 that left one of the two client slots dead for 17 hours
# while the other ground a parent worth 211 capture rows per host. Half capacity
# on the worst target in the set.
#
# So the queue is refilled here rather than supplied once, and each parent runs
# under a time cap. The cap is the part that matters: the ranker divides by
# capture rows per host, but `rows_per_host.tsv` holds 339 parents out of
# thousands, so for most of the queue the divisor is unmeasured and the ranking
# degrades to "sub-hosts we lack" alone. That is precisely the metric that put
# `com.au` first at 210.98 rows per host. Depth cannot be known before asking,
# so it is bounded after: a parent over PARENT_CAP is parked, not finished, and
# the sweep's own state file means the work already done is kept.
#
# Parking measures the thing the ranker was missing, so parked parents are worth
# re-reading later with a real cost attached rather than being lost.
#
# **The cap is a yield test taken every 300 seconds, not a deadline.** It used to be a
# flat 300s, chosen because a 600s cap cut collection from 1.0 journals per minute to
# 0.33 over a run of institutional namespaces. That optimised journals per minute, which
# is a proxy for nothing: a journal is a file, and only distinct (host, year) pairs are
# records. Measured 2026-09-07, the parents the flat cap discarded were the ones
# returning most, `columbia.edu` at 885,968 capture rows and `utoronto.ca` at 634,104.
#
# So the parent is judged on capture rows per distinct host, read from its own journal
# while it runs, and it keeps the slot while that stays cheap. Expensive namespaces are
# parked to `platform_deep.txt` as before; a parent still cheap at PARENT_MAX is parked
# to `platform_rich.txt` instead, because it is a rich platform rather than a dud and
# should not be filed with the duds.
#
# The two-clients maximum is unchanged. This runs at most twice, once per queue
# half, and each instance holds one slot.
#
# Usage: bash scripts/engines/platform_sweep_loop.sh <deadline_epoch> <parents_file> <shard 0|1>
set -uo pipefail
cd "$(dirname "$0")"
while [ ! -d data/raw ] && [ "$PWD" != "/" ]; do cd ..; done

DEADLINE="${1:?absolute epoch deadline}"
PAUSE_FLAG="${ARK_STATE_DIR:-$HOME/ark/state}/pause"
PARENTS="${2:?parents file}"
SHARD="${3:-0}"
PARENT_CAP="${ARK_PARENT_CAP:-300}"
PARENT_MAX="${ARK_PARENT_MAX:-2700}"
RPH_MAX="${ARK_RPH_MAX:-8}"
SWEEP="scripts/engines/cdx_suffix_sweep.py"
[ -f "$SWEEP" ] || SWEEP="scripts/cdx_suffix_sweep.py"
RANKER="scripts/engines/rank_platform_parents.py"
COSTS="scripts/engines/build_rows_per_host.py"
DEEP="data/raw/cdx/platform_deep.txt"
RICH="data/raw/cdx/platform_rich.txt"

# Rows and distinct hosts in a parent's journal so far, as "ROWS HOSTS".
# The sweep flushes after every page, so a gzip read gets everything up to the last
# page boundary and a torn tail is simply skipped.
yield_of() {
    local journal
    journal=$(ls -t "data/raw/cdx_suffix/suffix_${1}_"*.jsonl.gz 2>/dev/null | head -1)
    [ -n "$journal" ] || { echo "0 0"; return; }
    gzip -cd "$journal" 2>/dev/null | python3 -c '
import sys, json
rows = 0
hosts = set()
for line in sys.stdin:
    try:
        url = json.loads(line)["url"]
    except Exception:
        continue
    rows += 1
    hosts.add(url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0].lower())
print(rows, len(hosts))
' 2>/dev/null || echo "0 0"
}

# The shard is a hash of the name, not a line ordinal: the two shards rank at different
# moments and see different lists, so an ordinal split converged both clients on one
# parent (2026-09-09).
SHARD_BYTES='abcdefghijklmnopqrstuvwxyz0123456789.-_'

# Print the half of a parent list that shard $1 owns. Remaining arguments are files,
# read in order, so the park lists and the ranked list split under one rule.
shard_split() {
    local want="$1"
    shift
    awk -v s="$want" -v bytes="$SHARD_BYTES" '
        function shard_of(name,   i, h) {
            # position-weighted, so two names holding the same letters can still differ.
            # `index` returns 0 for a byte outside the table, which hashes it as absent
            # rather than failing.
            h = length(name)
            for (i = 1; i <= length(name); i++) h += i * index(bytes, substr(name, i, 1))
            return h % 2
        }
        NF && $1 !~ /^#/ && shard_of(tolower($1)) == s { print $1 }
    ' "$@"
}

sweep_one() {
    local parent="$1" safe="${parent//./_}"
    [ -e "data/raw/cdx_suffix/suffix_${safe}.done" ] && return 0
    echo "=== $parent ==="
    uv run python "$SWEEP" "$parent" --deadline "$DEADLINE" --delay 2.0 &
    local pid=$! waited=0 rows=0 hosts=0 rph=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep 10
        # **Paused time is not time this parent has had.** The child idles on the flag
        # between pages while this monitor's clock ran on regardless, so a pause longer than
        # PARENT_CAP judged a parent that had fetched nothing since the pause, and a pause
        # past PARENT_MAX parked it as silent or as rich on the strength of it. A pause is
        # meant to cost the page in flight and nothing else, so the yield test does not tick
        # while the flag is there.
        [ -e "$PAUSE_FLAG" ] && continue
        waited=$(( waited + 10 ))
        [ $(( waited % PARENT_CAP )) -eq 0 ] || continue

        # **Park on measured cost per host, not on elapsed time.** A flat 300s cap parks
        # whatever is slow, and the slowest parents are the ones returning most: measured
        # 2026-09-07, `columbia.edu` had written 885,968 capture rows and `utoronto.ca`
        # 634,104 when the cap cut them. Time was standing in for value and ranking it
        # backwards.
        #
        # What actually decides a parent is capture rows per distinct host, because a page
        # costs the same whatever it holds and only distinct (host, year) pairs are records.
        # That ratio spans 42x across parents. The ranker already divides by it, but only
        # for the 339 parents in `rows_per_host.tsv`; here it is read off this parent's own
        # journal, so an unmeasured parent is judged on what it is doing rather than kept
        # at an assumed 1.0 and then killed by the clock.
        read -r rows hosts <<< "$(yield_of "$safe")"
        # **An empty journal is not an expensive parent.** With hosts at 0 the ratio was
        # forced to 9999, which reads as the worst possible namespace, so a parent whose
        # first page had not landed yet was parked among the duds. That is exactly what
        # happens while the archive is answering 503: the backoff eats the first cap window
        # and the highest-ranked parents are thrown away for being slow, which is the same
        # mistake the flat time cap made. Nothing is known yet, so keep waiting, and if it
        # is still silent at PARENT_MAX put it on the retry list rather than the dud list.
        if [ "${hosts:-0}" -eq 0 ]; then
            if [ "$waited" -lt "$PARENT_MAX" ]; then
                echo "$parent: ${waited}s, nothing written yet, waiting"
                continue
            fi
            echo "$parent: silent for ${PARENT_MAX}s, queued for retry"
            echo "$parent" >> data/raw/cdx/platform_retry.txt
            kill -TERM "$pid" 2>/dev/null
            pgrep -f "$SWEEP $parent " | while read -r child; do kill -TERM "$child" 2>/dev/null; done
            sleep 3
            return 0
        fi
        rph=$(( rows / hosts ))
        if [ "$rph" -le "$RPH_MAX" ] && [ "$waited" -lt "$PARENT_MAX" ]; then
            echo "$parent: ${waited}s, $rows rows over $hosts hosts, $rph rows/host, cheap, continuing"
            continue
        fi
        if [ "$rph" -gt "$RPH_MAX" ]; then
            echo "$parent: $rph rows/host over $RPH_MAX, expensive namespace, parked"
            echo "$parent" >> "$DEEP"
        else
            # cheap per host and still going: this is a rich platform, not a dud, so it is
            # parked where a dedicated long run can find it rather than among the duds
            echo "$parent: $rph rows/host but hit ${PARENT_MAX}s, parked as rich"
            echo "$parent" >> "$RICH"
        fi
        kill -TERM "$pid" 2>/dev/null
        # the wrapper is `uv run python`, so the python child needs killing too
        pgrep -f "$SWEEP $parent " | while read -r child; do kill -TERM "$child" 2>/dev/null; done
        sleep 3
        kill -KILL "$pid" 2>/dev/null
        pgrep -f "$SWEEP $parent " | while read -r child; do kill -KILL "$child" 2>/dev/null; done
        return 0
    done
    if wait "$pid" 2>/dev/null; then
        # **A clean exit that wrote nothing is not a walked parent.** Measured 2026-09-09:
        # 96 parents held a 0-byte journal with no state file and no done marker, among them
        # yahoo.com, aol.com and about forty universities on .edu and .ac.uk. The sweep
        # returns zero when its deadline passes before the first page lands, which is what
        # happens to whatever is in flight when a window closes, and nothing recorded that
        # the archive had never actually been asked. So nothing would ever ask again.
        read -r rows hosts <<< "$(yield_of "$safe")"
        if [ "${rows:-0}" -eq 0 ] && [ ! -e "data/raw/cdx_suffix/suffix_${safe}.done" ]; then
            echo "$parent: exited clean with an empty journal, queued for retry"
            echo "$parent" >> data/raw/cdx/platform_retry.txt
        fi
    else
        echo "$parent: sweep exited non-zero, moving on"
        echo "$parent" >> data/raw/cdx/platform_retry.txt
    fi
}

refill() {
    # Ask the ranker for parents this queue has not already burned. Sharded on the
    # name by `shard_split` so the two clients never converge on the same parent,
    # which would be worse than idling: it spends the scarce slot on rows the other
    # client is already fetching.
    #
    # **Read the ranker's --out FILE, never its stdout.** It prints only its top
    # 15 as a human summary and writes the ranked list to the file. Piping stdout
    # asked 20,000 parents' worth of ranking and got 15, all of them long since
    # swept, so refill reported "found nothing" and both clients sat idle with a
    # full pool on disk. That cost about an hour of collection on 2026-09-05.
    [ -f "$RANKER" ] || return 1
    # **The ranker's divisor is only as good as the table behind it, and nothing was
    # rebuilding that table.** It was written by hand on 2026-09-04 over 339 parents; by
    # 2026-09-10 the collectors had walked 3,543, so the cost term was live for a tenth of
    # the queue and everything else fell through to the fallback. Rebuilding is one pass over
    # the journals, minutes, and only shard 0 does it so the two clients do not both spend
    # them; `--max-age-hours` makes the call idempotent, so this can be blind.
    if [ "$SHARD" = "0" ] && [ -f "$COSTS" ]; then
        nice -n 10 uv run python "$COSTS" --max-age-hours 6 >/dev/null 2>&1 || true
    fi
    local ranked="data/raw/cdx/ranked_shard${SHARD}.txt"
    uv run python "$RANKER" --net-new --top 20000 --out "$ranked" >/dev/null 2>&1 || return 1
    [ -s "$ranked" ] || return 1
    # **A park list nothing reads is a leak, and these two were leaking the best parents.**
    # `platform_retry.txt` was written in three places and read in none. `platform_rich.txt`
    # holds the parents this loop judged CHEAP per host and still producing at PARENT_MAX,
    # which is the definition of a rich platform, and refill excluded it for good. So the
    # two lists naming work worth returning to were the two the queue could never reach.
    # Both are read here, ahead of the ranker and sharded the same way, and `platform_deep`
    # stays excluded because expensive per host is a measured reason to stay parked.
    : > "$PARENTS.parked"
    for parked in data/raw/cdx/platform_retry.txt "$RICH"; do
        [ -s "$parked" ] && awk 'NF && $1 !~ /^#/ {print $1}' "$parked" >> "$PARENTS.parked"
    done
    shard_split "$SHARD" "$PARENTS.parked" "$ranked" > "$PARENTS.refill" || return 1
    awk 'NR==FNR {seen[$0]=1; next} !seen[$0]' "$PARENTS" "$PARENTS.refill" \
        | while IFS= read -r p; do
            [ -e "data/raw/cdx_suffix/suffix_${p//./_}.done" ] \
                || grep -qxF "$p" "$DEEP" 2>/dev/null || echo "$p"
        done > "$PARENTS.new"
    if [ -s "$PARENTS.new" ]; then
        cat "$PARENTS.new" >> "$PARENTS"
        echo "refilled with $(wc -l < "$PARENTS.new" | tr -d ' ') parents"
        return 0
    fi
    return 1
}

# Sourced by the shard test, which wants `shard_split` and not a sweep.
[ -n "${ARK_SWEEP_LOOP_LIB:-}" ] && return 0

line=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    # **Since C-77 no fleet lane sets this flag.** The two-clients limit binds the CDX
    # channel, which is this loop's, and an agent using any other archive.org service is not
    # a third CDX client, so research waves and collectors now run at the same time. What
    # remains is a HUMAN pause and `probe_thin_parents.py`, which needs a free slot.
    #
    # It stays a HEARTBEAT with an expiry, because that is what makes a forgotten flag
    # survivable: a flag with no expiry once idled both clients for nearly three hours of a
    # night we needed, when a wave that set it ran 2h14m against a 50-minute cap. Anything
    # that wants a long pause refreshes the file while it holds it.
    #
    # **A pause a human asked for is the exception, and expiring it would be a bug.**
    # `just collectors pause` writes `human` on the flag's first line and is meant to hold
    # over travel and a reboot, so this loop leaves that one alone: only `resume` clears it.
    # `stat -c` is GNU and silently failed to macOS's `stat -f`, which made every flag read
    # as zero seconds old on the laptop; both are asked now.
    while [ -e "$PAUSE_FLAG" ]; do
        if [ "$(head -1 "$PAUSE_FLAG" 2>/dev/null)" = "human" ]; then
            echo "paused by hand, waiting for a resume"
            sleep 60
            continue
        fi
        mtime=$(stat -c %Y "$PAUSE_FLAG" 2>/dev/null || stat -f %m "$PAUSE_FLAG" 2>/dev/null || date +%s)
        age=$(( $(date +%s) - mtime ))
        if [ "$age" -gt 9000 ]; then
            echo "pause flag is ${age}s old, past any healthy wave: resuming"
            rm -f "$PAUSE_FLAG"
            break
        fi
        sleep 60
    done
    line=$(( line + 1 ))
    parent="$(sed -n "${line}p" "$PARENTS")"
    if [ -z "$parent" ]; then
        if refill; then continue; fi
        echo "queue empty and refill found nothing, waiting"
        line=$(( line - 1 ))
        sleep 300
        continue
    fi
    sweep_one "$parent"
done
echo "deadline reached"
