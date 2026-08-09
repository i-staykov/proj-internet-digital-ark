#!/usr/bin/env bash
# Assemble the delivery archive: one compressed file plus its checksum, holding
# the results, the evidence behind them, the code that produced them, and the
# documentation. Run from anywhere; paths resolve relative to the repo root.
# Regenerate the data first with `ark export`.
#
# Usage: bash scripts/package_delivery.sh [round-label]
#
# The finished archive lands in `submissions/<round>/`, one folder per round, so
# a new round no longer destroys the one before it. This staging directory is
# rebuilt from scratch every run (`rm -rf` below), which for three rounds meant
# the only copy of a submission was whatever had been emailed out. The round
# label defaults to the current git branch, since a round and a branch have been
# the same thing on this project since phase 1.
set -euo pipefail
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"

ROUND="${1:-$(git rev-parse --abbrev-ref HEAD)}"
if [ "$ROUND" = "HEAD" ] || [ -z "$ROUND" ]; then
    echo "refusing to package: detached HEAD gives no round name. Pass one:" >&2
    echo "  bash scripts/package_delivery.sh phase-4" >&2
    exit 1
fi
ROUND_DIR="submissions/$ROUND"

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

# The same argument once more, applied to the REPORT. The two guards above keep
# the code and the data in step with each other, and neither of them looks at the
# document that describes both. So the report drifted: it was regenerated against
# a store that the collectors had grown by 10,000 pairs since the archive was
# cut, and the two shipped side by side quoting different totals. A reviewer
# checking the headline against `additions/` would have found it wrong, which is
# the single most likely thing for them to check first.
#
# Regenerating is cheap and idempotent, so this rebuilds the report and refuses
# if that changed anything. A report that is already current is a no-op here.
# The retry loop is not optional. DuckDB allows many readers or one writer, so a
# read-only connection still fails while the maintain loop holds the write lock,
# and this guard went in without one and refused to package for that reason
# alone. Swallowing the error made it look like the report was broken when the
# store was merely busy, so the failure is printed now rather than hidden.
REPORT_BEFORE=$(shasum -a 256 docs/report.md 2>/dev/null | cut -d' ' -f1)
FILL_OUT=""
for _ in $(seq 1 60); do
    if FILL_OUT=$(uv run python scripts/fill_report.py 2>&1); then
        break
    fi
    case "$FILL_OUT" in
        *"Conflicting lock"*) sleep 5 ;;
        *) echo "refusing to package: scripts/fill_report.py failed" >&2
           echo "$FILL_OUT" >&2
           exit 1 ;;
    esac
done
if ! printf '%s' "$FILL_OUT" | grep -q "filled cleanly"; then
    echo "refusing to package: the report could not be regenerated" >&2
    echo "$FILL_OUT" >&2
    exit 1
fi
REPORT_AFTER=$(shasum -a 256 docs/report.md | cut -d' ' -f1)
if [ "$REPORT_BEFORE" != "$REPORT_AFTER" ]; then
    echo "refusing to package: docs/report.md was stale against the store and has been" >&2
    echo "regenerated. Review the change, commit it, then re-run." >&2
    git --no-pager diff --stat docs/report.md >&2
    exit 1
fi

# The unpacked folder is named for what it holds, so a reviewer who extracts it
# among other downloads can still tell what it is.
RELEASE="internet-digital-ark-1996-2001"
STAGE="output/$RELEASE"
ARCHIVE="$ROUND_DIR/$RELEASE.tar.gz"
mkdir -p "$ROUND_DIR"
rm -rf "$STAGE"
mkdir -p "$STAGE"/{masters,additions,audit,logs,source,seeds,journals,provenance,baseline}

# The Word report is generated from the markdown, never maintained separately:
# a hand-made copy silently went 18 hours stale once, so the two disagreed.
# One report, `docs/report.md`, generated from `docs/report.template.md` by
# `scripts/fill_report.py`. Dated report filenames meant this line had to be
# repointed every round, and the round it was not repointed shipped the previous
# round's figures beside this round's data.
REPORT="docs/report.md"
if command -v pandoc >/dev/null 2>&1; then
    pandoc "$REPORT" -o "$STAGE/report.docx" --standalone
else
    echo "warning: pandoc not installed, shipping the report as markdown only" >&2
fi
cp "$REPORT" "$STAGE/report.md"
# the reviewer's own check, runnable from inside the unpacked folder
cp scripts/verify_delivery.sh "$STAGE/verify.sh"
chmod +x "$STAGE/verify.sh"
cp docs/delivery_readme.md "$STAGE/README.md"
cp docs/sources.md "$STAGE/sources.md"

# merged master year lists + net-new additions + provenance
cp data/exports/199[6-9].txt data/exports/200[01].txt "$STAGE/masters/" 2>/dev/null || true
cp output/netnew/199[6-9].txt output/netnew/200[01].txt "$STAGE/additions/" 2>/dev/null || true
cp output/netnew/evidence_manifest.csv "$STAGE/additions/" 2>/dev/null || true

# No `|| true` here: the candidate pool is a named deliverable, and swallowing a
# missing result file shipped an archive without it once, silently. `ark export`
# writes it, so a failure here means the export was not run.
cp output/candidate_unverified.txt "$STAGE/candidates.txt"

# `additions_english/` and `additions_unverified/` are NOT shipped any more, and
# neither is the language rejection register. They implemented the page-level
# English verification standard of the phase-3 feedback, which the reviewer has
# since retired in favour of the equivalent-English metric. The pipeline can still
# produce them, and `ark lang-report` still writes them under `output/`, so this
# is a change to what the delivery asserts rather than a loss of capability.
#
# Shipping them was worse than useless once the standard went: the folders came
# out empty, `verify.sh` printed three vacuous WARN lines about a partition of
# nothing, and the archive loudly documented a rule nobody is applying. The
# deliverable is `additions/`, and `candidates.txt` beside it holds the names that
# have not earned a year.
cp output/legacy_review/dropped_domains.txt "$STAGE/dropped_domains.txt" 2>/dev/null || true

# the auxiliary seed pool: hostnames and URLs, the granularity the registered
# domain counting unit necessarily drops
cp output/seeds/download_seeds.txt output/seeds/download_seeds.csv "$STAGE/seeds/" 2>/dev/null || true

# the raw responses of every archive and registry query, so both network stages
# replay from bytes rather than from a service whose answers change. `find`, not
# a flat glob: a ledgered CDX journal once sat one directory down and was matched
# by neither the packaging glob nor the ingest glob, so the evidence behind a
# headline result was the evidence that did not ship.
# **One rule, used by both the copy and the check below.** This was a list of
# `find` calls naming one source directory each, so every new source needed a
# line here that nobody remembered to add. It failed exactly that way three
# times: a ledgered CDX journal one directory down matched neither the packaging
# glob nor the ingest glob; expansion rounds 1 to 3 shipped while round 4 was
# silently dropped; and Usenet, Tucows and the language verdicts were simply
# never listed, which removed the evidence behind most of a round's additions
# from the tier-3 replay the README documents.
#
# On 8 August it would have failed a fourth time, for five sources at once, and
# the count guard at the bottom is what caught it. So the copy now takes the
# whole tree under exactly the same expression the guard uses. If the two ever
# disagree again, they disagree in one place instead of a dozen.
#
# `superseded/` is the one exclusion, and it is handled separately below: those
# are verdicts from earlier engine versions and they must not sit beside the
# current ones.
find data/raw -name '*.jsonl.gz' -not -path '*/superseded/*' \
    -exec cp {} "$STAGE/journals/" \; 2>/dev/null || true

# Superseded language journals go in their own folder, clearly named. They are
# the verdicts produced by earlier versions of the classifier, kept so that a
# discarded verdict is auditable rather than merely deleted. They must not sit
# beside the current ones: the README tells the reader to ingest
# `lang_*.jsonl.gz`, and although the engine-version gate would keep these out
# of any annual file, a folder named `superseded` says so without relying on it.
if compgen -G "data/raw/lang/superseded/*.jsonl.gz" > /dev/null; then
    mkdir -p "$STAGE/journals/lang_superseded"
    cp data/raw/lang/superseded/*.jsonl.gz "$STAGE/journals/lang_superseded/"
    cat > "$STAGE/journals/lang_superseded/README.txt" <<'SUPERSEDED'
Language verdicts produced by superseded versions of the classifier.

They are here for audit, not for use. Each was discarded after a defect was
found in the engine that produced it, and they are kept so that a discarded
verdict remains reproducible rather than simply deleted.

Every record carries no `engine_version` field, or one below the current
ENGINE_VERSION in src/ark/language.py. The exporter admits a verdict to an
annual file only at the current version, so ingesting these cannot put a
superseded verdict into a result file. They will, correctly, be re-judged.

What was wrong with them, in order of discovery:

  v1  The CDX index limit was passed the page-fetch count, so the engine asked
      the index for two rows and reported that as the whole archive. 75.4% of
      pairs with any capture were censored this way. Captures were also taken in
      URL-key order, so framesets and redirect stubs dominated the sample, and
      registrar parking pages scored English at confidence 1.000.

  v2  A replay request could be answered with a capture from a different year
      and reported as success, so a verdict could be dated wrongly while its
      recorded URL made the error invisible. Selection preferred robots.txt and
      vendor webmail pages over site content. The placeholder test skipped any
      page over 1,000 characters, admitting keyword link farms. A verdict could
      be settled on a truncated sample after a fetch failure.
SUPERSEDED
fi

# the seed lists those page fetches ran against, so page expansion is repeatable
mkdir -p "$STAGE/seeds/expansion"
cp seeds/expansion/*.txt "$STAGE/seeds/expansion/" 2>/dev/null || true

# BOTH baselines, in separate folders, because conflating them made the shipped
# archive wrong about its own scoring reference.
#
# `original/` is the first baseline supplied to this project. It is what
# `ark ingest-legacy` reads, so tier 3 needs it.
#
# The second folder is the reference this round's additions are COUNTED against,
# and it was once not shipped at all. A reviewer following tier 3 would have
# rebuilt against `original/` and scored against a much smaller baseline, which
# cannot reproduce any headline in the report. Worse, the archive looked
# self-contained while being unable to reproduce its own central figure.
#
# Ding supplies that baseline, so this ships his own file back to him. That is the
# point: the archive should be checkable without reference to anything outside it.
#
# **Both the folder name and the source directory come from `ark.baseline`, not
# from this script.** They were hardcoded to `merged260730` and stayed there after
# the store moved to `merged260802`, so the archive would have shipped a
# superseded baseline while asserting in `baseline/README.txt` that it was the one
# the figures mean. Scoring these additions against it gives a different answer
# than the report claims, and nothing in the archive would have revealed why.
eval "$(uv run python -c "
from ark.baseline import CURRENT_BASELINE_DIR, CURRENT_BASELINE_MARKER
print(f'MERGED={CURRENT_BASELINE_DIR}')
print(f'MARKER={CURRENT_BASELINE_MARKER}')
")"
mkdir -p "$STAGE/baseline/original" "$STAGE/baseline/$MARKER"
cp legacy-data/199[6-9].txt legacy-data/200[01].txt "$STAGE/baseline/original/" 2>/dev/null || true
cp legacy-data/merge_stats_new0714.csv "$STAGE/baseline/original/" 2>/dev/null || true
cp legacy-data/deduplicated_urls_2001-2002.txt "$STAGE/baseline/original/" 2>/dev/null || true

if [ -d "$MERGED" ]; then
    cp "$MERGED"/199[6-9].txt "$MERGED"/200[01].txt "$STAGE/baseline/$MARKER/"
    cp "$MERGED/merge_stats_new0714.csv" "$STAGE/baseline/$MARKER/" 2>/dev/null || true
else
    echo "refusing to package: $MARKER not found at $MERGED, so the archive could not" >&2
    echo "ship the baseline its own figures are measured against." >&2
    exit 1
fi

MERGED_LINES=$(cat "$STAGE/baseline/$MARKER"/199[6-9].txt "$STAGE/baseline/$MARKER"/200[01].txt \
    | wc -l | tr -d ' ')
cat > "$STAGE/baseline/README.txt" <<BASELINES
Two baselines, and they are not interchangeable.

original/
    The first baseline supplied to this project. \`ark ingest-legacy\` reads these
    six year files, so the tier-3 rebuild starts here. 8,224,963 raw lines.

$MARKER/
    The shared reference THIS ROUND'S ADDITIONS ARE COUNTED AGAINST, as reissued
    by the reviewer. $MERGED_LINES raw lines, collapsed to registered domains
    under SPEC III.8. Every "net-new" figure in report.md means "not present in
    these files".

    The pipeline ingests these under a marker namespace so their rows stay
    distinguishable from this project's evidence, which is what makes the net-new
    calculation possible at all.

If you score these additions against original/ instead of $MARKER/ you will get a
larger number than the report claims, because $MARKER already contains the
previous rounds of additions.
BASELINES

# the provenance graph as Parquet: which source saw which domain in which year,
# so any shipped line can be traced without the source data or the database
# everything the export wrote, not a hand-listed subset: naming the files here
# once shipped the data without trace.py, the tool the README tells them to run
cp -R output/provenance/. "$STAGE/provenance/" 2>/dev/null || true

# audit CSVs + execution logs
cp data/reports/*.csv "$STAGE/audit/" 2>/dev/null || true
# The engine review, so the process behind the report's audit section can be
# inspected rather than credited. A report that says "two adversarial reviews
# were run" and ships no record of them is asking to be believed.
# The English-engine review is no longer shipped: it documents the page-level
# verification standard the reviewer has retired, and an audit of a rule nobody
# applies reads as a rule still in force. It stays in the repo under docs/.
cp data/logs/* "$STAGE/logs/" 2>/dev/null || true

# source-code snapshot (tracked files at HEAD) + the commit it came from
git archive --format=tar HEAD | gzip -c > "$STAGE/source/source.tar.gz"
git rev-parse HEAD > "$STAGE/source/COMMIT.txt"

# Every journal on disk must be in the archive. Naming source directories by hand
# has now failed twice: once a ledgered CDX journal sat one directory down and
# matched neither the packaging glob nor the ingest glob, and once Usenet, Tucows
# and the language verdicts were simply never added, which silently removed the
# evidence behind most of a round's additions from the tier-3 replay the README
# documents. Counting is cheap and catches the next one.
ON_DISK=$(find data/raw -name '*.jsonl.gz' -not -path '*/superseded/*' | wc -l | tr -d ' ')
SHIPPED_JOURNALS=$(find "$STAGE/journals" -maxdepth 1 -name '*.jsonl.gz' | wc -l | tr -d ' ')
if [ "$ON_DISK" != "$SHIPPED_JOURNALS" ]; then
    echo "refusing to package: $ON_DISK journals on disk, $SHIPPED_JOURNALS in the archive" >&2
    echo "a source's journals are missing, so tier 3 cannot replay it. Compare:" >&2
    find data/raw -name '*.jsonl.gz' -not -path '*/superseded/*' -exec basename {} \; \
        | sort > /tmp/ark_on_disk.txt
    find "$STAGE/journals" -maxdepth 1 -name '*.jsonl.gz' -exec basename {} \; \
        | sort > /tmp/ark_shipped.txt
    comm -23 /tmp/ark_on_disk.txt /tmp/ark_shipped.txt >&2
    exit 1
fi
echo "journals: $SHIPPED_JOURNALS shipped, matching what is on disk"

# per-file checksums, then the archive, then the archive's own checksum
( cd "$STAGE" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 shasum -a 256 > SHA256SUMS )
tar -czf "$ARCHIVE" -C output "$RELEASE"
# The checksum file records the bare filename, not the build path: a reviewer
# who downloads only the archive runs `shasum -c` beside it, and a stored path
# of `submissions/...` makes that fail before they have checked anything.
( cd "$ROUND_DIR" && shasum -a 256 "$RELEASE.tar.gz" > "$RELEASE.tar.gz.sha256" )

# What stays in git after the tarball is git-ignored: the report as sent, the
# checksum, and a manifest naming the commit and the baseline. Together those are
# enough to say later exactly what was claimed in a given round and to prove a
# recovered tarball is the one that was sent, without keeping gigabytes in the
# repository. Rebuilding a superseded round is `git checkout <commit>` then
# `just deliver && just package`.
cp docs/report.md "$ROUND_DIR/report.md"
cp docs/sources.md "$ROUND_DIR/sources.md"
{
    echo "round        $ROUND"
    echo "built        $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "commit       $(git rev-parse HEAD)"
    echo "baseline     $MARKER"
    echo "archive      $RELEASE.tar.gz"
    echo "sha256       $(shasum -a 256 "$ARCHIVE" | cut -d' ' -f1)"
    echo "bytes        $(wc -c < "$ARCHIVE" | tr -d ' ')"
    echo "files        $(find "$STAGE" -type f | wc -l | tr -d ' ')"
    echo "netnew_pairs $STORED"
} > "$ROUND_DIR/MANIFEST.txt"

# Everything needed to hand the archive over by link, in one block to copy.
cat <<EOF

Delivery archive ready, in $ROUND_DIR/

  filename   $(basename "$ARCHIVE")
  size       $(du -h "$ARCHIVE" | cut -f1) ($(wc -c < "$ARCHIVE" | tr -d ' ') bytes)
  format     tar + gzip (extract: tar -xzf $(basename "$ARCHIVE"))
  sha256     $(shasum -a 256 "$ARCHIVE" | cut -d' ' -f1)
  contents   $(find "$STAGE" -type f | wc -l | tr -d ' ') files, unpacking to $RELEASE/

Tracked beside it: report.md, sources.md, MANIFEST.txt, and the .sha256.
The tarball itself is git-ignored. Add a row to submissions/README.md.
EOF
