#!/usr/bin/env bash
# What both CDX engines are doing right now, in one screen.
#
# Two machines run the same collector against disjoint shards of the same queue,
# and a second machine's output is invisible to every measurement taken on the
# first. That asymmetry has already cost this project once: the VPS ran for a day
# and a half with 5,793 year-records sitting on its disk and absent from the store,
# because nothing here ever looked. So this asks both.
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
# Usage: bash scripts/engine_status.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

VPS="${ARK_VPS:-digga@10.1.0.6}"
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

section() { printf '\n== %s ==\n' "$1"; }

section "local"
if pgrep -f "supervise_cdx_pool.sh" > /dev/null; then
    ps -eo etime,command | grep "[s]upervise_cdx_pool.sh" | head -1 | sed 's/^/   up /'
else
    echo "   NOT RUNNING"
fi
part=$(ls -t data/raw/cdx/cdx_gap_*.jsonl.gz.part 2>/dev/null | head -1)
[ -n "$part" ] && echo "   journal $(basename "$part")"
ARK_PART="$part" python3 -c "$TALLY"
echo "   last finished batch:"
grep -hoE "cdx: \{[^}]*\}" data/logs/cdx_gap.log 2>/dev/null | tail -1 | sed 's/^/     /'

section "VPS ($VPS)"
ssh -o ConnectTimeout=8 -o BatchMode=yes "$VPS" "
cd '$VPS_REPO' || exit 1
if pgrep -f supervise_cdx_pool.sh > /dev/null; then
    ps -eo etime,command | grep '[s]upervise_cdx_pool.sh' | head -1 | sed 's/^/   up /'
else
    echo '   NOT RUNNING'
fi
part=\$(ls -t data/raw/cdx/cdx_gap_vps_*.jsonl.gz.part 2>/dev/null | head -1)
[ -n \"\$part\" ] && echo \"   journal \$(basename \"\$part\")\"
ARK_PART=\"\$part\" python3 -c '$TALLY'
echo '   last finished batch:'
grep -hoE 'cdx: \{[^}]*\}' data/logs/cdx_gap_vps.log 2>/dev/null | tail -1 | sed 's/^/     /'
" 2>&1 | grep -v "^Warning: Permanently added" || echo "   unreachable (VPN down?)"

section "journals on the VPS not yet copied here"
remote=$(ssh -o ConnectTimeout=8 -o BatchMode=yes "$VPS" \
    "ls '$VPS_REPO'/data/raw/cdx/cdx_gap_vps_*.jsonl.gz 2>/dev/null | xargs -n1 basename 2>/dev/null" 2>/dev/null)
missing=0
for f in $remote; do
    [ -e "data/raw/cdx/$f" ] || { echo "   $f"; missing=$((missing + 1)); }
done
if [ "$missing" -eq 0 ]; then
    echo "   none, everything is home"
else
    echo "   $missing missing. Bring them home with:"
    echo "     rsync -av --ignore-existing '$VPS:$VPS_REPO/data/raw/cdx/cdx_gap_vps_*.jsonl.gz' data/raw/cdx/"
fi

section "power"
pmset -g batt 2>/dev/null | head -1 | sed 's/^/   /'
pgrep -q caffeinate && echo "   caffeinate is holding idle sleep off" \
    || echo "   NO caffeinate: the machine can idle-sleep and stop the run"
