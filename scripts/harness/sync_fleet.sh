#!/usr/bin/env bash
# Push the pricing snapshot the fleet prices against: the current reviewer baseline
# (from data/baseline.json, so it can never name a stale marker), the last exported
# net-new, the candidate pools, and a manifest of every file with its line count and
# sha256. `ark price-snapshot` refuses a snapshot whose files disagree with the manifest,
# so the manifest is pushed LAST and a torn sync fails a wave instead of mispricing it.
# Superseded baselines on the VPS are removed once the new one holds all six year files.
# Runs inside `just sync` and after every non-dry `just intake`.
set -euo pipefail

[ -f local.env ] && . local.env
: "${ARK_VPS:?set ARK_VPS in local.env}"

STAGE=output/fleet_snapshot
# Stages hard links and refuses a zero-line held-set file, which would price every name
# as net-new. Line counts and digests are taken from the bytes this pushes.
uv run python scripts/harness/snapshot_manifest.py --out "$STAGE"
MARKER=$(uv run python -c "import json; print(json.load(open('data/baseline.json'))['current']['marker'])")

# --delete per subtree rather than at the root: /projects/ark-data also holds the journal
# ACKs and whatever else the fleet keeps there, and a root-level delete would take them.
# A subtree the staging step left out is skipped rather than failing the sync: all three
# candidate files are optional, so `candidates/` need not exist. Nothing stale survives
# that, because the pricer refuses a file the manifest does not list.
for sub in "$MARKER" netnew candidates; do
    if [ ! -d "$STAGE/$sub" ]; then
        echo "sync_fleet: $sub is not in the snapshot, not pushed"
        continue
    fi
    ssh "$ARK_VPS" "mkdir -p /projects/ark-data/'$sub'"
    rsync -a --delete "$STAGE/$sub"/ "$ARK_VPS":/projects/ark-data/"$sub"/
done
# **The manifest goes as soon as its files are there, and everything optional goes after
# it.** It went last of three under `set -e`, behind `ack_journals.py`, which opens the store
# read-only: one locked store and the snapshot the fleet had just been sent became unusable,
# because the pricer refuses files no manifest lists. Measured 2026-09-09, when today's
# manifest reached the box only because the rsyncs were run again by hand.
rsync -a "$STAGE"/manifest.json "$ARK_VPS":/projects/ark-data/manifest.json

# The receipt that lets the host remove a journal this store has already ingested. Its
# authority is the sha256 the ingest itself recorded, so a name collision cannot free bytes.
# Never fatal: a delayed ACK costs the box disk, a missing manifest costs a wave.
if uv run python scripts/harness/ack_journals.py --out output/journal_acks.tsv >/dev/null; then
    rsync -a output/journal_acks.tsv "$ARK_VPS":/projects/ark-data/journal_acks.tsv
else
    echo "ack skipped: store locked. The snapshot is pushed; the box keeps its journals."
fi
ssh "$ARK_VPS" "cd /projects/ark-data && [ \$(ls '$MARKER' | grep -c '\\.txt\$') -eq 6 ] \
    && for d in merged*; do [ \"\$d\" = '$MARKER' ] || rm -rf -- \"\$d\"; done; ls -d merged*"
echo "fleet prices against $MARKER"
