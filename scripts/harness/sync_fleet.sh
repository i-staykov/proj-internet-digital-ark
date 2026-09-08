#!/usr/bin/env bash
# Push the pricing snapshot the fleet prices against: the current reviewer baseline
# (from data/baseline.json, so it can never name a stale marker) and the last exported
# net-new. Superseded baselines on the VPS are removed once the new one holds all six
# year files. Runs inside `just bank` and after every non-dry `just intake`.
set -euo pipefail

[ -f local.env ] && . local.env
: "${ARK_VPS:?set ARK_VPS in local.env}"

MARKER=$(uv run python -c "import json; print(json.load(open('data/baseline.json'))['current']['marker'])")
DIR=$(uv run python -c "import json; print(json.load(open('data/baseline.json'))['current']['directory'])")
for y in 1996 1997 1998 1999 2000 2001; do
    [ -f "$DIR/$y.txt" ] || { echo "sync_fleet: $DIR/$y.txt is missing" >&2; exit 1; }
done

rsync -a "$DIR"/{1996,1997,1998,1999,2000,2001}.txt "$ARK_VPS":/projects/ark-data/"$MARKER"/
rsync -a --delete output/netnew/ "$ARK_VPS":/projects/ark-data/netnew/
# The receipt that lets the host remove a journal this store has already ingested. Its
# authority is the sha256 the ingest itself recorded, so a name collision cannot free bytes.
uv run python scripts/harness/ack_journals.py --out output/journal_acks.tsv >/dev/null
rsync -a output/journal_acks.tsv "$ARK_VPS":/projects/ark-data/journal_acks.tsv
ssh "$ARK_VPS" "cd /projects/ark-data && [ \$(ls '$MARKER' | grep -c '\\.txt\$') -eq 6 ] \
    && for d in merged*; do [ \"\$d\" = '$MARKER' ] || rm -rf -- \"\$d\"; done; ls -d merged*"
echo "fleet prices against $MARKER"
