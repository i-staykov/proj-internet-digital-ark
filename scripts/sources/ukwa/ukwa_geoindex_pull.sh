#!/usr/bin/env bash
# Pull the 1996-2001 prefix of every member of the British Library geoindex.
#
# Sortedness was verified to EOF on `postcode-ab`: 0 timestamp decreases over all
# 529,492,931 compressed bytes, with the in-window count flat for the last 470 MB.
# That is what makes the early abort sound, and it is the check the register asked
# for after its sibling `host-linkage.tsv.gz` cost the project 93% of a source by
# looking sorted and being fifteen concatenated shards.
#
# The margin is deliberately generous: each member reads 64 MB past the last
# in-window row before stopping, so a shard boundary just past the window would
# still be seen as a decrease and reported.
#
# This host is `bl.iro.bl.uk`, not `web.archive.org`, so it does not compete with
# the CDX collectors and can run beside them.
#
# Usage: bash scripts/sources/ukwa/ukwa_geoindex_pull.sh [margin_mb]

set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1

MARGIN="${1:-64}"
LOG="data/logs/ukwa_geoindex.log"
mkdir -p data/logs data/raw/ukwa
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

if [ ! -f data/raw/ukwa/geoindex_members.json ]; then
    note "mapping the archive first"
    uv run python scripts/sources/ukwa/ukwa_geoindex_map.py >> "$LOG" 2>&1
fi

members=$(uv run python -c "
import json
for m in json.load(open('data/raw/ukwa/geoindex_members.json')):
    if m['name'].endswith('.tsv'):
        print(m['name'])
")

for member in $members; do
    out="data/raw/ukwa/$(echo "$member" | tr '/' '_' | sed 's/\.tsv//')_inwindow.tsv.gz"
    if [ -s "$out" ]; then
        note "$member: already have $out, skipping"
        continue
    fi
    note "$member: streaming"
    uv run python scripts/sources/ukwa/ukwa_geoindex_stream.py "$member" \
        --stop-margin-mb "$MARGIN" >> "$LOG" 2>&1
    note "$member: done (exit $?)"
done

note "all members attempted"
ls -la data/raw/ukwa/*_inwindow.tsv.gz 2>/dev/null | tee -a "$LOG"
