#!/usr/bin/env bash
# One check-in for an unattended run: ingest whatever the collectors have
# finished, then print a single status line.
#
# Only finished journals are ingested. A collector still writing one has it
# named `.part`, which these globs do not match, so this can run at any time
# without racing a live run into the file ledger.
set -uo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"

for spec in "cdx_snapshot:data/raw/cdx/cdx_*.jsonl.gz" "rdap_snapshot:data/raw/rdap/rdap_*.jsonl.gz"; do
    key="${spec%%:*}"
    pattern="${spec#*:}"
    files=$(ls $pattern 2>/dev/null) || continue
    [ -z "$files" ] && continue
    # already-ledgered files are skipped by the loader itself, so this is cheap
    uv run ark ingest "$key" $files >> data/logs/maintain.log 2>&1
done

uv run python - <<'PY'
import subprocess
import duckdb
from pathlib import Path

conn = duckdb.connect("data/ark.duckdb", read_only=True)
# A net-new PAIR and a net-new DOMAIN are different tests: a baseline domain
# gaining a year it lacked is a new pair on an old domain. Counting distinct
# domains over the net-new pairs conflates them and reported 1,161,961 domains
# against a true 463,566, so the two predicates are kept apart here as well.
pairs = conn.execute(
    """
    SELECT count(*) FROM domain_year dy
    WHERE NOT EXISTS (
        SELECT 1 FROM evidence p WHERE p.domain = dy.domain
          AND p.evidence_year = dy.assigned_year AND p.evidence_type = 'prior_reused')
    """
).fetchone()[0]
domains = conn.execute(
    """
    SELECT count(*) FROM (SELECT DISTINCT domain FROM domain_year) d
    WHERE NOT EXISTS (
        SELECT 1 FROM evidence p WHERE p.domain = d.domain
          AND p.evidence_type = 'prior_reused')
    """
).fetchone()[0]
conn.close()

running = subprocess.run(
    ["pgrep", "-f", "bin/ark (cdx|rdap|download)"], capture_output=True, text=True
).stdout.split()
live = [p.name for p in Path("data/raw").glob("*/*.part")]
print(
    f"net-new {domains:,} domains / {pairs:,} pairs | "
    f"{len(running)} collector(s) up | {len(live)} journal(s) in flight"
)
PY
