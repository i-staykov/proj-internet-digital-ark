#!/usr/bin/env bash
# Assemble the delivery archive: one compressed file plus its checksum, holding
# the results, the evidence behind them, the code that produced them, and the
# documentation. Run from anywhere; paths resolve relative to the repo root.
# Regenerate the data first with `ark export`.
set -euo pipefail
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"

# The source snapshot below comes from `git archive HEAD`, so an uncommitted or
# stale tree ships code that does not match the shipped data and report. This
# has happened: an archive once paired post-narrowing data with pre-narrowing
# code, and a reviewer running it would have regenerated the withdrawn rows.
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "refusing to package: tracked files are modified, so source/ would not match the results" >&2
    echo "commit (or stash) first, then re-run." >&2
    git status --short --untracked-files=no >&2
    exit 1
fi

# The same argument as the clean-tree guard, applied to the data: output/ is a
# snapshot taken by `ark export`, and every ingest since then makes it older than
# the store. Shipping a stale one understates the result and contradicts the
# report, which quotes the store. Caught this way once, 1,513 pairs behind.
SHIPPED=$(cat output/netnew/199[6-9].txt output/netnew/200[01].txt 2>/dev/null | wc -l | tr -d ' ')
STORED=$(uv run python -c "
import duckdb
from ark.stats import collect_stats
print(collect_stats(duckdb.connect('data/ark.duckdb', read_only=True))['netnew_pairs_total'])
" 2>/dev/null | tail -1)
if [ "$SHIPPED" != "$STORED" ]; then
    echo "refusing to package: output/ holds $SHIPPED net-new pairs, the store holds $STORED" >&2
    echo "run 'uv run ark export' first, then re-run." >&2
    exit 1
fi

# The unpacked folder is named for what it holds, so a reviewer who extracts it
# among other downloads can still tell what it is.
RELEASE="internet-digital-ark-1996-2001"
STAGE="output/$RELEASE"
ARCHIVE="output/$RELEASE.tar.gz"
rm -rf "$STAGE"
mkdir -p "$STAGE"/{masters,additions,audit,logs,source,seeds,journals,provenance}

# The Word report is generated from the markdown, never maintained separately:
# a hand-made copy silently went 18 hours stale once, so the two disagreed.
if command -v pandoc >/dev/null 2>&1; then
    pandoc docs/report.md -o "$STAGE/report.docx" --toc --standalone
else
    echo "warning: pandoc not installed, shipping the report as markdown only" >&2
fi
cp docs/report.md "$STAGE/report.md"
# the reviewer's own check, runnable from inside the unpacked folder
cp scripts/verify_delivery.sh "$STAGE/verify.sh"
chmod +x "$STAGE/verify.sh"
cp docs/delivery_readme.md "$STAGE/README.md"
cp docs/sources.md "$STAGE/sources.md"

# merged master year lists + net-new additions + provenance
cp data/exports/199[6-9].txt data/exports/200[01].txt "$STAGE/masters/" 2>/dev/null || true
cp output/netnew/199[6-9].txt output/netnew/200[01].txt "$STAGE/additions/" 2>/dev/null || true
cp output/netnew/evidence_manifest.csv "$STAGE/additions/" 2>/dev/null || true
cp output/candidate_unverified.txt "$STAGE/candidates.txt" 2>/dev/null || true
cp output/legacy_review/dropped_domains.txt "$STAGE/dropped_domains.txt" 2>/dev/null || true

# the auxiliary seed pool: hostnames and URLs, the granularity the registered
# domain counting unit necessarily drops
cp output/seeds/download_seeds.txt output/seeds/download_seeds.csv "$STAGE/seeds/" 2>/dev/null || true

# the raw responses of every archive and registry query, so both network stages
# replay from bytes rather than from a service whose answers change
cp data/raw/cdx/cdx_*.jsonl.gz "$STAGE/journals/" 2>/dev/null || true
cp data/raw/rdap/rdap_*.jsonl.gz "$STAGE/journals/" 2>/dev/null || true
# every expansion journal, whatever round subdirectory it landed in. Enumerating
# rounds by hand shipped rounds 1 to 3 and silently dropped round 4, while the
# archive readme still told the reader to restore it.
find data/raw/expand -name '*.jsonl.gz' -exec cp {} "$STAGE/journals/" \; 2>/dev/null || true

# the seed lists those page fetches ran against, so section VII is repeatable
mkdir -p "$STAGE/seeds/expansion"
cp seeds/expansion/*.txt "$STAGE/seeds/expansion/" 2>/dev/null || true

# the provenance graph as Parquet: which source saw which domain in which year,
# so any shipped line can be traced without the source data or the database
cp output/provenance/*.parquet output/provenance/LOAD.sql "$STAGE/provenance/" 2>/dev/null || true

# audit CSVs + execution logs
cp data/reports/*.csv "$STAGE/audit/" 2>/dev/null || true
cp data/logs/* "$STAGE/logs/" 2>/dev/null || true

# source-code snapshot (tracked files at HEAD) + the commit it came from
git archive --format=tar HEAD | gzip -c > "$STAGE/source/source.tar.gz"
git rev-parse HEAD > "$STAGE/source/COMMIT.txt"

# per-file checksums, then the archive, then the archive's own checksum
( cd "$STAGE" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 shasum -a 256 > SHA256SUMS )
tar -czf "$ARCHIVE" -C output "$RELEASE"
shasum -a 256 "$ARCHIVE" > "$ARCHIVE.sha256"

# Everything needed to hand the archive over by link, in one block to copy.
cat <<EOF

Delivery archive ready.

  filename   $(basename "$ARCHIVE")
  size       $(du -h "$ARCHIVE" | cut -f1) ($(wc -c < "$ARCHIVE" | tr -d ' ') bytes)
  format     tar + gzip (extract: tar -xzf $(basename "$ARCHIVE"))
  sha256     $(shasum -a 256 "$ARCHIVE" | cut -d' ' -f1)
  contents   $(find "$STAGE" -type f | wc -l | tr -d ' ') files, unpacking to $RELEASE/
EOF
