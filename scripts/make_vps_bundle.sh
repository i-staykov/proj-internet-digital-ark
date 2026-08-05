#!/usr/bin/env bash
# Pack what a second collecting machine needs, so the copy over the VPN is one file.
#
# Two things, and only two: the shard's target list, and the journal history the
# resume scan reads. The repository itself comes from git; the database is not
# needed at all, because collection never opens it.
#
# The journal history is what stops the remote machine re-asking the ~9,500
# domains in its shard that were already settled before the split. Without it the
# run spends about sixteen hours rediscovering answers already on this disk.
#
# Usage: bash scripts/make_vps_bundle.sh [shard_file] [out]
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"

SHARD="${1:-data/raw/cdx/gap_shard1.txt}"
OUT="${2:-/tmp/ark-bundle.tar.gz}"

[ -f "$SHARD" ] || { echo "no such shard list: $SHARD (run: just gap-shards 2)"; exit 1; }

# Only finished journals. A live `.part` would arrive truncated, and the ledger
# keys on content, so shipping one would make its finished form unreachable later.
tar -czf "$OUT" \
    "$SHARD" \
    $(find data/raw/cdx -maxdepth 1 -name 'cdx_*.jsonl.gz' -type f)

echo "wrote $OUT ($(du -h "$OUT" | cut -f1))"
echo "  target list : $(wc -l < "$SHARD" | tr -d ' ') domains"
echo "  journals    : $(find data/raw/cdx -maxdepth 1 -name 'cdx_*.jsonl.gz' -type f | wc -l | tr -d ' ')"
echo
echo "next, with the VPN up:"
echo "  scp $OUT <vps>:~/ark-bundle.tar.gz"
echo "  ssh <vps>"
echo "  tmux new -s ark"
echo "  git clone <repo> proj-internet-digital-ark && cd proj-internet-digital-ark"
echo "  bash scripts/vps_bootstrap.sh 1786276800"
echo "  # Ctrl-B then D to detach, then drop the VPN"
