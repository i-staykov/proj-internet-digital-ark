#!/usr/bin/env bash
# Download and bank the unheld English-facing Usenet hierarchies.
#
# **Why this can run without asking anyone.** `usenet_announce / dated_directory`
# and its siblings are already `master` in `docs/approved-sources-list.md`, decided
# by Ivo in phase 4, and the corroboration split is applied by `split_usenet.py`
# rather than by anything here. So this is collection under an existing decision,
# not a new source class.
#
# **What it is worth, measured rather than assumed.** C-29 sampled two hierarchies
# through `measure_usenet_yield.py`: `bit.listserv` gave 1.13 net-new post-split
# pairs per MB and 0.68 EE/MB, `microsoft.public` gave 5.66 and 3.25. The register's
# older figure of 15.5 pairs/MB is 3x to 14x optimistic and should not be used. On
# the measured rates the roughly 52 GB that is English-facing is worth about
# 104,000 equivalent-English, and it is an upper bound because saturation falls
# hardest on the largest hierarchy.
#
# **Which host this touches, which is the question the register says to ask of any
# new source.** `archive.org/download/`, not `web.archive.org`. That is a different
# service from the CDX endpoint the collectors meter against, so this runs beside
# them rather than competing. Nothing here should ever be pointed at web.archive.org.
#
# **National hierarchies are excluded deliberately.** `de`, `it`, `tw`, `fido7`,
# `pl`, `fr` and the rest are about 135 GB and an English-weighted metric discounts
# them to near nothing, so taking them would cost four times the bytes for a small
# fraction of the score.
#
# Usage: bash scripts/fetch_usenet_hierarchies.sh <deadline_epoch> [hierarchy ...]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:?usage: fetch_usenet_hierarchies.sh <deadline_epoch> [hierarchy ...]}"
shift
HIERARCHIES=("$@")
if [ ${#HIERARCHIES[@]} -eq 0 ]; then
    # Ordered by measured equivalent-English per byte, best first, so an
    # interrupted run has taken the valuable part.
    HIERARCHIES=(microsoft linux bit free us mailing fa lucky borland macromedia ott gov)
fi

DEST="data/raw/usenet_new"
LOG="data/logs/usenet_fetch.log"
UA="InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
mkdir -p "$DEST" data/logs
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

LOCK="data/logs/usenet_fetch.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    note "another fetch holds $LOCK; refusing to start a second"
    exit 1
fi
echo "$$" > "$LOCK/pid"
# **The handler must exit, and the first version did not.** A bare `trap 'rm -rf
# "$LOCK"'` on TERM runs the handler and then carries on with the loop, so a TERM
# released the lock while leaving the process downloading. A second copy could then
# start, and did: two fetchers ran against archive.org for two minutes, duplicating
# every request. INT and TERM therefore clean up and leave.
cleanup() { rm -rf "$LOCK"; }
trap 'cleanup' EXIT
trap 'cleanup; exit 143' TERM
trap 'cleanup; exit 130' INT

note "deadline $(date -u -r "$DEADLINE" '+%F %T UTC'), hierarchies: ${HIERARCHIES[*]}"

# **Several passes, not one.** archive.org returns a 500 for individual objects
# often enough to matter: 55 groups failed that way in the first hour, about 2% of
# the list, and a single pass loses every one of them. A later pass costs nothing
# for files already on disk, because the loop skips anything non-empty, so the only
# question is whether the deadline has room. It usually does, since the fetch is
# bandwidth-bound and the failures are instant.
pass=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
pass=$((pass + 1))
note "===== pass $pass ====="
missing_before=0

for h in "${HIERARCHIES[@]}"; do
    [ "$(date +%s)" -ge "$DEADLINE" ] && { note "deadline reached"; break; }
    note "== usenet-$h =="

    meta="$DEST/.meta-$h.json"
    if [ ! -s "$meta" ]; then
        curl -sSL -A "$UA" --max-time 300 "https://archive.org/metadata/usenet-$h" -o "$meta"
    fi

    # Largest groups first: within a hierarchy, size does track post count, and an
    # interrupted run should have taken the big ones. The register's warning that
    # size does not predict YIELD is about choosing between hierarchies, which is
    # what the ordering above already handles.
    files=$(uv run python -c "
import json, sys
try:
    d = json.load(open('$meta'))
except Exception:
    sys.exit()
fs = [f for f in d.get('files', []) if f.get('name', '').endswith('.mbox.zip')]
fs.sort(key=lambda f: -int(f.get('size', 0) or 0))
for f in fs:
    print(f['name'])
")

    for name in $files; do
        [ "$(date +%s)" -ge "$DEADLINE" ] && { note "deadline reached"; break 2; }
        out="$DEST/$name"
        [ -s "$out" ] && continue
        missing_before=$((missing_before + 1))
        curl -sSL -A "$UA" --max-time 1800 --retry 3 --retry-delay 20 \
            -o "$out.part" "https://archive.org/download/usenet-$h/$name"
        if [ -s "$out.part" ]; then
            mv "$out.part" "$out"
        else
            rm -f "$out.part"
            note "  $name: nothing arrived"
        fi
    done
    note "== usenet-$h done: $(ls -1 "$DEST"/*.mbox.zip 2>/dev/null | wc -l | tr -d ' ') archives on disk =="
done

if [ "$missing_before" -eq 0 ]; then
    note "pass $pass found nothing missing; every listed archive is on disk"
    break
fi
note "pass $pass finished with $missing_before archive(s) attempted"
# A pass that attempted nothing new would spin, and the guard above catches that.
# A pass that attempted some and failed all of them should not retry instantly.
sleep 120
done

note "fetch finished after $pass pass(es)"
