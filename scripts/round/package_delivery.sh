#!/usr/bin/env bash
# Assemble the delivery archive: one compressed file plus its checksum, holding
# the results, the evidence behind them, the code that produced them, and the
# documentation. Run from anywhere; paths resolve relative to the repo root.
# Regenerate the data first with `ark export`.
#
# Usage: bash scripts/round/package_delivery.sh [round-label]
#
# The finished archive lands in `submissions/<round>/`, one folder per round, so
# a new round no longer destroys the one before it. This staging directory is
# rebuilt from scratch every run (`rm -rf` below), which for three rounds meant
# the only copy of a submission was whatever had been emailed out. The round
# label defaults to the current git branch, since a round and a branch have been
# the same thing on this project since phase 1.
set -euo pipefail
PROJ="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJ"

ROUND="${1:-$(git rev-parse --abbrev-ref HEAD)}"
if [ "$ROUND" = "HEAD" ] || [ -z "$ROUND" ]; then
    echo "refusing to package: detached HEAD gives no round name. Pass one:" >&2
    echo "  bash scripts/round/package_delivery.sh phase-4" >&2
    exit 1
fi
ROUND_DIR="submissions/$ROUND"

# The source snapshot below comes from `git archive HEAD`, so an uncommitted or
# stale tree ships code that does not match the shipped data and report. This
# has happened: an archive once paired post-narrowing data with pre-narrowing
# code, and a reviewer running it would have regenerated the withdrawn rows.
#
# `submissions/` is excluded because it is this script's own OUTPUT, not an input
# to the source snapshot. Every run rewrites the round's MANIFEST, checksum and
# report copy, so including it made the second packaging run refuse on the first
# run's results, which is a guard tripping over its own footprints.
DIRTY=$(git status --porcelain --untracked-files=no -- . ':(exclude)submissions')
if [ -n "$DIRTY" ]; then
    echo "refusing to package: tracked files are modified, so source/ would not match the results" >&2
    echo "commit (or stash) first, then re-run." >&2
    printf '%s\n' "$DIRTY" >&2
    exit 1
fi

# The same argument as the clean-tree guard, applied to the data: output/ is a
# snapshot taken by `ark export`, and every ingest since then makes it older than
# the store. Shipping a stale one understates the result and contradicts the
# report, which quotes the store. Caught this way once, 1,513 pairs behind.
SHIPPED=$(cat output/netnew/199[6-9].txt output/netnew/200[01].txt 2>/dev/null | wc -l | tr -d ' ')
# Retried, and not silenced. `2>/dev/null` here turned a busy store into an empty
# STORED, which then failed the comparison below and told the operator the export
# was stale when it was current. A guard that misreports why it fired is worse
# than no guard: it sends you to fix the wrong thing.
# `|| true` is load-bearing. `set -e` is on, so a bare `STORED=$(cmd)` whose
# command fails aborts the script instantly: the retry below never ran, the
# diagnostic below never printed, and packaging exited 1 in silence. That went
# unnoticed while nothing else held the store, and surfaced the moment the ingest
# loop began running continuously beside two collectors.
STORED=""
for _ in $(seq 1 60); do
    # Counted through the SAME shipping filter the export applies, not the raw
    # store total. Those two were equal until the export learned to drop a pair
    # whose TLD did not exist in its year, and from then on the guard compared a
    # pre-filter number with a post-filter one and refused a perfectly current
    # export forever: 726,344 in the store against 726,336 on disk, a difference
    # that is the filter working rather than the export being stale.
    STORED=$(uv run python -c "
import duckdb
from ark.export import netnew_shipped_pairs
print(netnew_shipped_pairs(duckdb.connect('data/ark.duckdb', read_only=True)))
" 2>&1 | tail -1) || true
    case "$STORED" in
        ''|*[!0-9]*) sleep 5 ;;
        *) break ;;
    esac
done
case "$STORED" in
    ''|*[!0-9]*)
        echo "refusing to package: could not read the store's net-new count" >&2
        echo "$STORED" >&2
        exit 1 ;;
esac
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
# D3: the merge, the overlap counts, the accepted increment and the reconciliation
# checks, produced here rather than described. It scores every baseline and merged
# annual file with the reviewer's own calculator, so this is his arithmetic on our
# data, and it emits HIS column names so his audit and ours can be diffed directly.
#
# **A failure here stops the packaging.** The reconciliation includes two checks that
# compare a freshly measured baseline against `src/ark/baseline.py`, so a round being
# measured against a release he has already replaced fails loudly instead of shipping.
# That exact drift went unnoticed for five days in August 2026 and overstated net-new
# by 151,949 records he had already credited.
echo "merging against the baseline and reconciling (D3)"
if ! uv run python scripts/round/merge_against_baseline.py --stamp "$(date -u +%Y%m%d)" \
        --out output/merge > output/merge/merge_run.log 2>&1; then
    echo "refusing to package: the merge reconciliation failed. Its log:" >&2
    cat output/merge/merge_run.log >&2
    exit 1
fi
cat output/merge/merge_run.log

# **Before the report is filled, not after.** `fill_report.py` reads the newest
# `output/merge/merge_audit_ark*.json` for section 8, so running the merge afterwards
# shipped a report whose merge figures were one packaging run behind the audit beside
# it. Found on 2026-08-18 by auditing the delivery, hours after the ordering was
# introduced. The fill guard below now sees this run's audit.
REPORT_BEFORE=$(shasum -a 256 docs/report.md 2>/dev/null | cut -d' ' -f1)
FILL_OUT=""
for _ in $(seq 1 60); do
    if FILL_OUT=$(uv run python scripts/round/fill_report.py 2>&1); then
        break
    fi
    case "$FILL_OUT" in
        *"Conflicting lock"*) sleep 5 ;;
        *) echo "refusing to package: scripts/round/fill_report.py failed" >&2
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
# `scripts/round/fill_report.py`. Dated report filenames meant this line had to be
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
cp scripts/round/verify_delivery.sh "$STAGE/verify.sh"
chmod +x "$STAGE/verify.sh"
cp docs/delivery_readme.md "$STAGE/README.md"
cp docs/sources.md "$STAGE/sources.md"

# D2 and D4 of the submission standard, at the archive ROOT rather than inside
# `source/source.tar.gz`. He asked for a CONCISE experience summary and a clear
# explanation of the metric, and a document a reader has to untar first is neither.
# `sources.md` above is the full register those two distil; both are needed, because
# 91 rejected families with their measurements is the evidence and two pages is the
# summary.
cp docs/experience-summary.md "$STAGE/experience-summary.md"
cp docs/metric-explained.md "$STAGE/metric-explained.md"

# The D3 audit, produced before the report was filled so the two agree. Copied by
# exact stamp rather than by glob: `output/merge/` is never pruned, and a glob plus
# the consumers' `sorted()[-1]` would ship every past stamp and then pick by filename.
MERGE_STAMP="$(date -u +%Y%m%d)"
cp "output/merge/merge_stats_ark_${MERGE_STAMP}.csv" "$STAGE/audit/"
cp "output/merge/merge_audit_ark_${MERGE_STAMP}.json" "$STAGE/audit/"
cp output/merge/merge_run.log "$STAGE/audit/merge_run.log"


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
# since retired in favour of the equivalent-English metric. The engine now lives in
# the retired English-verification engine, and nothing writes those folders any more.
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
# **Structure preserved, not flattened.** This copied every journal into one flat
# directory, and `just journals` addresses them by nested path: `data/raw/cdx/cdx_*`,
# `data/raw/expand/round2/...`, `data/raw/usenet/...`. So tier 3's replay stage matched
# nothing for every source while the archive README claimed "this is what tier 3 replays,
# so every network stage reproduces offline". Found 2026-08-18 by running the layout
# against the globs rather than reading it.
#
# The tar pipe rather than `cp --parents`, which is GNU-only, and `--strip-components=2`
# to drop the `data/raw` prefix so `cp -R journals/. data/raw/` restores the tree exactly.
#
# **The RDAP query logs are the second exclusion, and it is a SIZE decision and nothing
# else.** They are 387 files and 3.67 GB against 1.18 GB for every other source combined,
# and shipping them makes the archive 6.5 GB against the 1.86 GB the reviewer received last
# round. State the cost honestly rather than dressing it up: `rdap_snapshot` is the round's
# second-largest source at 581,458 net-new pairs, so this is the one source whose tier-3
# replay the archive cannot offer. Tier 2 is unaffected and covers every one of those pairs,
# which is what `verify.sh` check 4 tests. Available on request. Ivo, 2026-08-26.
#
# ARK_SLIM=1 omits ALL raw journals and is not what a submission uses. They exist for
# tier-3 replay, re-parsing the raw sources offline; tier 2, which reproduces every shipped
# assignment from the provenance Parquet, is unaffected.
#
# One expression for the copy and for the count guard at the bottom, so the two cannot
# disagree about what should be present.
journal_paths() {
    find data/raw -name '*.jsonl.gz' \
        -not -path '*/superseded/*' \
        -not -path 'data/raw/rdap/*' \
        -not -path 'data/raw/rdap_pool/*' "$@"
}
if [ -z "${ARK_SLIM:-}" ]; then
    journal_paths -print0 \
        | tar -cf - --null -T - 2>/dev/null \
        | ( cd "$STAGE/journals" && tar xf - --strip-components=2 2>/dev/null ) || true
    cat > "$STAGE/journals/README.txt" <<'EXCL'
One collector's raw logs are deliberately not here: the RDAP walks, under rdap/ and
rdap_pool/. The reason is size and nothing else. They are 3.67 GB against 1.18 GB for every
other source combined, and including them would triple this archive.

Stated plainly, because it is a real limitation: rdap_snapshot is this round's second-largest
source at 581,458 net-new pairs, so it is the one source whose tier-3 replay this archive
cannot offer. Everything it evidenced still ships and is still checkable: each (domain, year)
resolves to its evidence row in provenance/, which is what verify.sh check 4 tests over every
assignment, and the target queues are under seeds/. Ask and the logs will be sent separately.
EXCL
fi

# The retired English engine's superseded verdict journals are no longer shipped.
# They were kept beside the current ones under `journals/lang_superseded/` so a
# discarded verdict stayed auditable, which mattered while the standard was live.
# The standard is retired and its engine is deleted, so an
# archive carrying them would document a rule nobody applies. The journals stay on
# disk under `data/raw/lang/` and are no longer read.

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
# `shlex.quote`, because the reviewer's own directory names contain spaces:
# `feedback-phase-6/Domain_Data_Collection_Task 2/merged260821`. Unquoted, `eval` split
# that into three words and ran `2/merged260821` as a command, so the baseline never
# reached the archive and packaging died at the copy with "No such file or directory".
eval "$(uv run python -c "
import shlex
from ark.baseline import CURRENT_BASELINE_DIR, CURRENT_BASELINE_MARKER
print(f'MERGED={shlex.quote(str(CURRENT_BASELINE_DIR))}')
print(f'MARKER={shlex.quote(CURRENT_BASELINE_MARKER)}')
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

# The FULL evidence table ships, baseline rows included, and the 429 MB they cost is
# not optional. Dropping `prior_reused` was tried on 2026-08-17 and shipped once. It
# looked free: those rows are the reviewer's own data returning to him, and
# `verify.sh` passed because it reads the additions manifest rather than the parquet.
#
# Running the archive's own tier-2 reproduction against a freshly extracted copy is
# what caught it. Without the baseline rows, 11,316,960 of 16,619,832 `domain_year`
# rows point at an `evidence_id` that no longer exists, so `ark check` fails on
# `evidence_wall_intact` and `every_pair_has_master_evidence`. Worse, net-new is
# DEFINED as "no baseline evidence for this (domain, year)", so with those rows gone
# the rebuild re-claims the entire corpus: 712,927 additions for 1996 against a true
# 63,162. That is the exact failure `notes.md` records from phase 2, where shipping
# would have claimed 1,339,783 pairs instead of 17,418.
#
# The lesson is not "keep the rows", it is that a size cut which no guard covers is
# an unmeasured change. `verify_delivery.sh` now checks the evidence wall directly.

# The reviewer's own scorer, so the archive can re-derive its headline figure without
# reference to anything outside itself. `round_figures.py --verify` is named in the
# report as the way to re-score the increment, and running it inside an unpacked
# archive failed with "calculator not found": it lived only in the repository. Found
# by running the report's own instructions in a fresh extraction, 2026-08-17.
#
# It is his file coming back to him, which is the same argument as `baseline/`: a
# reviewer should be able to check the arithmetic without fetching anything, and the
# whole thing is a few tens of kilobytes.
mkdir -p "$STAGE/equivalent_english_domain_calculator"
CALC_SRC="$(dirname "$MERGED")/equivalent_english_domain_calculator"
if [ -d "$CALC_SRC" ]; then
    # A tar pipe rather than `cp -R`, to drop `__pycache__`: shipping compiled
    # bytecode of somebody else's script is noise, and it changes on every run so the
    # archive checksum would never settle. `--exclude` works in both BSD and GNU tar,
    # unlike `cp --parents`, which is GNU only and would have failed on this machine.
    ( cd "$CALC_SRC" && tar cf - --exclude '__pycache__' . ) \
        | ( cd "$STAGE/equivalent_english_domain_calculator" && tar xf - )
else
    echo "warning: no calculator beside $MERGED, archive will not self-score" >&2
fi

# audit CSVs + execution logs
cp data/reports/*.csv "$STAGE/audit/" 2>/dev/null || true
# The engine review, so the process behind the report's audit section can be
# inspected rather than credited. A report that says "two adversarial reviews
# were run" and ships no record of them is asking to be believed.
# The English-engine review is no longer shipped: it documents the page-level
# verification standard the reviewer has retired, and an audit of a rule nobody
# applies reads as a rule still in force. It stays in the repo under docs/.
# Tailed, not copied whole. `maintain.log` alone was 123 MB of one line per ingest
# pass, repeated every 150 seconds for a fortnight. What a reader wants from a log
# is the shape of the run and its most recent state, and the last 20,000 lines give
# both; the full files stay in the repo under `data/logs/`.
for log in data/logs/*; do
    [ -f "$log" ] || continue
    tail -n 20000 "$log" > "$STAGE/logs/$(basename "$log")" 2>/dev/null || true
done

# source-code snapshot (tracked files at HEAD) + the commit it came from
git archive --format=tar HEAD | gzip -c > "$STAGE/source/source.tar.gz"
git rev-parse HEAD > "$STAGE/source/COMMIT.txt"

# Every journal on disk must be in the archive. Naming source directories by hand
# has now failed twice: once a ledgered CDX journal sat one directory down and
# matched neither the packaging glob nor the ingest glob, and once Usenet, Tucows
# and the language verdicts were simply never added, which silently removed the
# evidence behind most of a round's additions from the tier-3 replay the README
# documents. Counting is cheap and catches the next one.
ON_DISK=$(journal_paths | wc -l | tr -d ' ')
SHIPPED_JOURNALS=$(find "$STAGE/journals" -name '*.jsonl.gz' | wc -l | tr -d ' ')
if [ -n "${ARK_SLIM:-}" ]; then
    if [ "$SHIPPED_JOURNALS" != "0" ]; then
        echo "refusing to package: ARK_SLIM set but $SHIPPED_JOURNALS journals staged" >&2
        exit 1
    fi
    cat > "$STAGE/journals/README.txt" <<'SLIM'
The raw per-source journals are deliberately not in this archive.

They are 4.85 GB and exist only for tier-3 reproduction, which re-parses the raw sources
offline. Tier 2 is unaffected and is the route this archive documents: every shipped
(domain, year) resolves to its evidence row in provenance/, and verify.sh checks that
for all of them. Ask if you want the journals and they will be sent separately.
SLIM
    echo "journals: omitted deliberately (ARK_SLIM), $ON_DISK on disk"
elif [ "$ON_DISK" != "$SHIPPED_JOURNALS" ]; then
    echo "refusing to package: $ON_DISK journals on disk, $SHIPPED_JOURNALS in the archive" >&2
    echo "a source's journals are missing, so tier 3 cannot replay it. Compare:" >&2
    journal_paths -exec basename {} \; \
        | sort > /tmp/ark_on_disk.txt
    find "$STAGE/journals" -name '*.jsonl.gz' -exec basename {} \; \
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
