#!/usr/bin/env bash
# Assemble the Phase-7 delivery archive: one compressed archive + checksum
# containing everything Prof. Ding enumerated. Run from anywhere; paths are
# resolved relative to the repo root. Regenerate the data first with `ark export`.
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

STAGE="output/delivery"
ARCHIVE="output/internet-digital-ark-delivery.tar.gz"
rm -rf "$STAGE"
mkdir -p "$STAGE"/{masters,additions,audit,logs,source,seeds,journals}

# report + docs
cp docs/report.md "$STAGE/report.md"
[ -f output/report.docx ] && cp output/report.docx "$STAGE/report.docx"
cp docs/delivery_readme.md "$STAGE/README.md"
cp docs/notes.md "$STAGE/notes.md"
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

# audit CSVs + execution logs
cp data/reports/*.csv "$STAGE/audit/" 2>/dev/null || true
cp data/logs/* "$STAGE/logs/" 2>/dev/null || true

# source-code snapshot (tracked files at HEAD) + the commit it came from
git archive --format=tar HEAD | gzip -c > "$STAGE/source/source.tar.gz"
git rev-parse HEAD > "$STAGE/source/COMMIT.txt"

# per-file checksums, then the archive, then the archive's own checksum
( cd "$STAGE" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 shasum -a 256 > SHA256SUMS )
tar -czf "$ARCHIVE" -C output delivery
shasum -a 256 "$ARCHIVE" | tee "$ARCHIVE.sha256"
echo "archive: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1)); staged files: $(find "$STAGE" -type f | wc -l | tr -d ' ')"
