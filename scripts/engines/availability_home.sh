#!/usr/bin/env bash
# Bring the VPS availability engine's finished journals home, where the fold loop and the
# sync already ingest.
#
# Exact-host rows are the `cdx_snapshot` shape and land as `data/raw/cdx/cdx_availvps_*`.
# Rows about another host, almost always the `www.` form, are `{url, timestamp}` hostname
# rows and land in `data/raw/cdx_gap_hostgrain/` as `availability_host_vps_*`, which the fold
# ingests as hostnames under `wayback_availability`, never as the bare name (spec XIII).
# Idempotent: a file already home is skipped. The VPS writes only closed journals to `done/`.
#
# Usage: bash scripts/engines/availability_home.sh    (ARK_VPS from local.env)
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
[ -f local.env ] && . ./local.env
: "${ARK_VPS:?set ARK_VPS}"
REMOTE="${ARK_AVAIL_DIR:-/projects/ark-yearfill}/data/raw/done"
STAGE=data/raw/availability_vps
mkdir -p "$STAGE/exact" "$STAGE/host" data/raw/cdx data/raw/cdx_gap_hostgrain
for kind in exact host; do
    rsync -a --ignore-existing --timeout=120 -e "ssh -o ConnectTimeout=15 -o BatchMode=yes" \
        "$ARK_VPS:$REMOTE/$kind/" "$STAGE/$kind/" || { echo "vps unreachable"; exit 1; }
done
new=0
for f in "$STAGE"/exact/availability_*.jsonl.gz; do
    [ -e "$f" ] || continue
    dest="data/raw/cdx/cdx_availvps_$(basename "$f" | sed 's/^availability_//')"
    [ -e "$dest" ] || { cp "$f" "$dest.part" && mv "$dest.part" "$dest" && new=$((new + 1)); }
done
for f in "$STAGE"/host/availability_host_*.jsonl.gz; do
    [ -e "$f" ] || continue
    dest="data/raw/cdx_gap_hostgrain/availability_host_vps_$(basename "$f" | sed 's/^availability_host_//')"
    [ -e "$dest" ] || { cp "$f" "$dest.part" && mv "$dest.part" "$dest" && new=$((new + 1)); }
done
echo "$new journal(s) filed"
