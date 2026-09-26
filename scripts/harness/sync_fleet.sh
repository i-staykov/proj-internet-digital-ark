#!/usr/bin/env bash
# Push the pricing snapshot the fleet prices against: the current reviewer baseline
# (from data/baseline.json, so it can never name a stale marker), the last exported
# net-new, the candidate pools, and a manifest of every file with its line count and
# sha256. `ark price-snapshot` refuses a snapshot whose files disagree with the manifest,
# so the manifest goes as soon as its files are there, ahead of the ack and the prune, and
# a torn push fails a wave instead of mispricing it. The prune removes superseded baselines
# on the VPS once the new one holds all six year files.
# Runs at the end of `just bank`, from the tick with --no-ack while data/logs/.push_pending
# exists, and after every non-dry `just intake`. Exit 3: the VPS did not answer, nothing pushed.
set -euo pipefail

NO_ACK=0
for a in "$@"; do
    case "$a" in
        --no-ack) NO_ACK=1 ;;
        *) echo "sync_fleet: unknown argument $a" >&2; exit 2 ;;
    esac
done

[ -f local.env ] && . local.env
: "${ARK_VPS:?set ARK_VPS in local.env}"
# Probe first, so an unreachable VPS neither restages nor rehashes the snapshot. Every
# remote call below is bounded the same way, so a drop mid-push fails in seconds.
ssh -o ConnectTimeout=15 -o BatchMode=yes "$ARK_VPS" true </dev/null 2>/dev/null \
    || { echo "sync_fleet: the VPS did not answer, nothing pushed"; exit 3; }

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
    ssh -o ConnectTimeout=15 -o BatchMode=yes "$ARK_VPS" "mkdir -p /projects/ark-data/'$sub'"
    rsync -a --delete --timeout=120 -e "ssh -o ConnectTimeout=15 -o BatchMode=yes" \
        "$STAGE/$sub"/ "$ARK_VPS":/projects/ark-data/"$sub"/
done
# Everything optional goes after the manifest, so a locked store or a failed prune never
# leaves the VPS holding files no manifest lists, which the pricer refuses.
rsync -a --timeout=120 -e "ssh -o ConnectTimeout=15 -o BatchMode=yes" \
    "$STAGE"/manifest.json "$ARK_VPS":/projects/ark-data/manifest.json

# The receipt that lets the host remove a journal this store has already ingested, and the
# only store read here. Its authority is the sha256 the ingest itself recorded, so a name
# collision cannot free bytes. Never fatal: a delayed ACK costs the box disk, a missing
# manifest costs a wave.
if [ "$NO_ACK" = 1 ]; then
    echo "ack skipped: --no-ack"
elif uv run python scripts/harness/ack_journals.py --out output/journal_acks.tsv >/dev/null; then
    rsync -a --timeout=120 -e "ssh -o ConnectTimeout=15 -o BatchMode=yes" \
        output/journal_acks.tsv "$ARK_VPS":/projects/ark-data/journal_acks.tsv
else
    echo "ack skipped: store locked. The snapshot is pushed; the box keeps its journals."
fi
ssh -o ConnectTimeout=15 -o BatchMode=yes "$ARK_VPS" \
    "cd /projects/ark-data && [ \$(ls '$MARKER' | grep -c '\\.txt\$') -eq 6 ] \
    && for d in merged*; do [ \"\$d\" = '$MARKER' ] || rm -rf -- \"\$d\"; done; ls -d merged*"
echo "fleet prices against $MARKER"
