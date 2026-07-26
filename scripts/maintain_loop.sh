#!/usr/bin/env bash
# Run the check-in every 20 minutes for an unattended stretch, logging each line.
# Pairs with supervise_engines.sh: that one keeps the collectors busy, this one
# folds their finished journals into the store so the scoreboard stays current.
set -uo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"
END=$(( $(date +%s) + ${1:-18000} ))
while [ "$(date +%s)" -lt "$END" ]; do
    echo "$(date +%H:%M:%S) $(bash scripts/maintain.sh 2>/dev/null | tail -1)"
    sleep 1200
done
echo "$(date +%H:%M:%S) maintain loop finished"
