#!/usr/bin/env bash
# Assemble the delivery archive: one 7z plus its checksum, holding
# the results, the evidence behind them, the code that produced them, and the
# documentation. Run from anywhere; paths resolve relative to the repo root.
# Regenerate the data first with `ark export --provenance`.
#
# Usage: bash scripts/round/package_delivery.sh [round-label]
#
# The archive lands in `submissions/<round>/`; the staging directory is rebuilt every
# run. The round label defaults to the git branch.
set -euo pipefail
PROJ="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJ"
# A foreign venv makes every `uv run` print its home path into the logs that ship.
unset VIRTUAL_ENV

# The fleet checkout ships as source/fleet.tar.gz and the open research questions are built
# from it, so it must be the fleet as it stands: the top of a git checkout (a worktree's
# `.git` is a file), its HEAD on the fleet's main, and no older than the newest drain the
# laptop banked, whose name is the drain's UTC minute.
FLEET="${ARK_FLEET:-$HOME/GitHub/ark-fleet}"
TOP=$(git -C "$FLEET" rev-parse --show-toplevel 2>/dev/null) || true
if [ -z "$TOP" ] || [ "$(cd "$TOP" && pwd -P)" != "$(cd "$FLEET" && pwd -P)" ]; then
    echo "refusing to package: $FLEET is not the top of a fleet checkout; set ARK_FLEET" >&2
    exit 1
fi
if ! git -C "$FLEET" merge-base --is-ancestor HEAD refs/remotes/origin/main 2>/dev/null; then
    echo "refusing to package: HEAD of $FLEET is not on the fleet's origin/main" >&2
    exit 1
fi
NEWEST=$(ls data/fleet_findings/banked 2>/dev/null | grep -E '^[0-9]{8}T[0-9]{4}Z' | cut -c1-14 | sort | tail -1) || true
HEAD_AT=$(TZ=UTC git -C "$FLEET" log -1 --format=%cd --date=format-local:%Y%m%dT%H%MZ HEAD)
if [ -n "$NEWEST" ] && [[ "$HEAD_AT" < "$NEWEST" ]]; then
    echo "refusing to package: the fleet at $FLEET was committed $HEAD_AT, before the newest banked drain $NEWEST; pull it" >&2
    exit 1
fi

if ! command -v 7z >/dev/null; then
    echo "refusing to package: no 7z command, and a submission is one 7z archive" >&2
    exit 1
fi

# The export stamp first, from files alone, so a wrong export refuses in seconds. A bank
# writes only the claim, so the manifests, ISC files and contribution tables beside it are
# whatever the last full export left; only a full export with provenance, against the current
# release and with the bank's claim set aside, ships.
PROBLEMS=$(uv run python -c 'from ark.export import stamp_problems; print("\n".join(stamp_problems()))')
if [ -n "$PROBLEMS" ]; then
    echo "refusing to package:" >&2
    printf '%s\n' "$PROBLEMS" >&2
    exit 1
fi

ROUND="${1:-$(git rev-parse --abbrev-ref HEAD)}"
if [ "$ROUND" = "HEAD" ] || [ -z "$ROUND" ]; then
    echo "refusing to package: detached HEAD gives no round name. Pass one:" >&2
    echo "  bash scripts/round/package_delivery.sh phase-4" >&2
    exit 1
fi
# On `live`, never a round name, the label is the store's round.
if [ "$ROUND" = live ]; then
    ROUND="phase-$(uv run python -c 'from ark.baseline import CURRENT_ROUND_LABEL
print(CURRENT_ROUND_LABEL)')"
fi
ROUND_DIR="submissions/$ROUND"

# The source snapshot below comes from `git archive HEAD`, so an uncommitted or
# stale tree ships code that does not match the shipped data and report.
#
# `submissions/` is excluded because it is this script's own OUTPUT, not an input
# to the source snapshot. Every run rewrites the round's MANIFEST and checksum, so
# including it made the second packaging run refuse on the first run's results,
# which is a guard tripping over its own footprints.
DIRTY=$(git status --porcelain --untracked-files=no -- . ':(exclude)submissions')
if [ -n "$DIRTY" ]; then
    echo "refusing to package: tracked files are modified, so source/ would not match the results" >&2
    echo "commit (or stash) first, then re-run." >&2
    printf '%s\n' "$DIRTY" >&2
    exit 1
fi

# The same argument as the clean-tree guard, applied to the data: output/ is a
# snapshot taken by `ark export`, and every ingest since then makes it older than
# the store. Shipping a stale one understates the result. Caught this way once,
# 1,513 pairs behind.
SHIPPED=$(cat output/netnew/199[6-9].txt output/netnew/200[01].txt 2>/dev/null | wc -l | tr -d ' ')
# Read-only and patient, so a bank holding the writer is a wait and never a refusal that
# names the wrong cause. The stamps' ledgers must equal the store's, the bank's claim must
# equal the full export's, and the count goes through the export's own shipping filter.
STORED=$(uv run python -c "
import sys
from ark.db import connect_read_only_patiently
from ark.export import netnew_shipped_pairs, stamp_problems
conn = connect_read_only_patiently('data/ark.duckdb')
conn.execute('SET enable_progress_bar = false')
problems = stamp_problems(conn)
if problems:
    print('\n'.join(problems), file=sys.stderr)
    sys.exit(3)
print(netnew_shipped_pairs(conn))
") || { echo "refusing to package: the export does not match the store (above)" >&2; exit 1; }
if [ "$SHIPPED" != "$STORED" ]; then
    echo "refusing to package: output/ holds $SHIPPED net-new pairs, the store holds $STORED" >&2
    echo "run 'uv run ark export --provenance' first, then re-run." >&2
    exit 1
fi

# The merge, the overlap counts, the accepted increment and the reconciliation
# checks, produced here rather than described. It scores every baseline and merged
# annual file with the reviewer's own calculator, so this is his arithmetic on our
# data, and it emits HIS column names so his audit and ours can be diffed directly.
#
# **A failure here stops the packaging.** The reconciliation includes two checks that
# compare a freshly measured baseline against `src/ark/baseline.py`, so a round being
# measured against a release he has already replaced fails loudly instead of shipping.
echo "merging against the baseline and reconciling"
# One read of the date: the copy below finds the merge by it, also across 00:00 UTC.
MERGE_STAMP="$(date -u +%Y%m%d)"
if ! uv run python scripts/round/merge_against_baseline.py --stamp "$MERGE_STAMP" \
        --out output/merge > output/merge/merge_run.log 2>&1; then
    echo "refusing to package: the merge reconciliation failed. Its log:" >&2
    cat output/merge/merge_run.log >&2
    exit 1
fi
cat output/merge/merge_run.log

# His name for the one archive, KnowledgeDiscoveryCompetition_Submission_{SubmissionTime}_{Name}.7z,
# also names the folder it unpacks to. His SubmissionTime is when he receives it; the packaging
# minute, UTC, stands in for it.
RELEASE="KnowledgeDiscoveryCompetition_Submission_$(date -u +%Y%m%d%H%M)_IvayloStaykov"
STAGE="output/$RELEASE"
ARCHIVE="$ROUND_DIR/$RELEASE.7z"
mkdir -p "$ROUND_DIR"
rm -rf "$STAGE"
# Two sets and a labelled third part at the top: additions/ (the year files, their provenance and
# every supporting file under support/), candidates/ (one list and one provenance file), and
# year_evidence/ (names his release holds, dated by our record in a year his file lacks).
A="$STAGE/additions" P="$STAGE/additions/provenance" S="$STAGE/additions/support" C="$STAGE/candidates"
mkdir -p "$P" "$C" "$S"/{audit,source,seeds,journals,baseline}

# The report's figures, from the store after this run's merge audit, so the two agree. The
# report itself is filled from them on the laptop and never ships here: a wording edit then
# needs no repackage. A bank holding the write lock is a wait, never a refusal.
FILL_OUT=""
for _ in $(seq 1 60); do
    if FILL_OUT=$(uv run python scripts/round/fill_report.py --write-figures "$S/audit/report_figures.json" 2>&1); then
        break
    fi
    case "$FILL_OUT" in
        *"Conflicting lock"*) sleep 5 ;;
        *) echo "refusing to package: scripts/round/fill_report.py failed" >&2
           echo "$FILL_OUT" >&2
           exit 1 ;;
    esac
done
[ -f "$S/audit/report_figures.json" ] || { echo "refusing to package: no report figures" >&2; echo "$FILL_OUT" >&2; exit 1; }
# the reviewer's own check, runnable from inside the unpacked folder
cp scripts/round/verify_delivery.sh "$S/verify.sh"
chmod +x "$S/verify.sh"
# The archive name carries the packaging minute, so the README's checksum command
# is filled in here; a hard-coded name went stale the round the name changed.
sed "s/\[ARCHIVE\]/$RELEASE/g" docs/round/delivery_readme.md > "$STAGE/README.md"
cp docs/registers/sources.md "$S/sources.md"
# The register is two pages: closed families moved to sources-closed.md and shipping
# sources.md alone would hand him an incomplete register.
cp docs/registers/sources-closed.md "$S/sources-closed.md"

# D2 and D4 of the submission standard, at the archive ROOT rather than inside
# `source/source.tar.gz`. He asked for a CONCISE experience summary and a clear
# explanation of the metric, and a document a reader has to untar first is neither.
# The two register pages above are the full register those two distil; both are
# needed, because the rejected families with their measurements are the evidence and
# two pages are the summary.
cp docs/round/experience-summary.md "$S/experience-summary.md"
cp docs/brief/metric-explained.md "$S/metric-explained.md"

# The research loop itself, from the fleet checkout checked at the top: workflows, prompts,
# policy and leads, tracked files only so no secret can ride along (the workflows name
# theirs by reference). The open research questions folder is built from that commit.
git -C "$FLEET" archive --format=tar HEAD | gzip -c > "$S/source/fleet.tar.gz"
git -C "$FLEET" rev-parse HEAD > "$S/source/FLEET_COMMIT.txt"
# The refused-values pool the research questions read (q2), no longer shipped. **Kept in
# `output/netnew/`, and only the journals newer than it are read and merged in**: the scan is
# exhaustive over 23 GB of gzip, and a journal is written once, so the merge is what a full scan
# would write. Only the three DEFAULT_DIRS of unparsed_pool.py can stale it, no walk journal.
UNPARSED="output/netnew/candidates_unparsed.txt"
if [ ! -f "$UNPARSED" ] || [ -n "$(find data/raw/cdx_suffix data/raw/cdx_gap_hostgrain data/raw/nypw_hostgrain \
        -name '*.jsonl.gz' ! -name 'walk_*' -newer "$UNPARSED" -print -quit 2>/dev/null)" ]; then
    uv run python scripts/round/unparsed_pool.py --incremental --out "$UNPARSED" || true
fi
if ! uv run python scripts/round/orq.py --stage "$S" --fleet "$FLEET"; then
    echo "refusing to package: the open research questions did not build" >&2
    exit 1
fi
if [ ! -f "$S/Open Research Questions/Open Research Questions.docx" ]; then
    echo "refusing to package: $S/Open Research Questions/Open Research Questions.docx is missing" >&2
    exit 1
fi

# The merge audit, produced before the report figures so the two agree. Copied by
# exact stamp rather than by glob: `output/merge/` is never pruned, and a glob plus
# the consumers' `sorted()[-1]` would ship every past stamp and then pick by filename.
cp "output/merge/merge_stats_ark_${MERGE_STAMP}.csv" "$S/audit/"
cp "output/merge/merge_audit_ark_${MERGE_STAMP}.json" "$S/audit/"
cp output/merge/merge_run.log "$S/audit/merge_run.log"

# Nothing ships that his baseline already holds. The export diffs every list against his
# own annual files, so a non-zero overlap here means that diff did not run or ran against
# a stale baseline directory, and the round would claim records he already has.
OVERLAP=$(python3 -c "import json,sys; print(int(json.load(open(sys.argv[1]))['totals']['already_in_baseline_records']))" \
    "output/merge/merge_audit_ark_${MERGE_STAMP}.json")
if [ "$OVERLAP" != 0 ]; then
    echo "refusing to package: $OVERLAP submitted records are already in the baseline." >&2
    echo "re-run \`uv run ark export\` against the current baseline, then the merge audit." >&2
    exit 1
fi


# The README's `sort -m -u` merge is silently wrong on unsorted input, so a year of his that
# `ark intake` had to copy sorted refuses.
uv run python -c '
import sys
from ark import held
try:
    his = held.load()
except held.HeldError as error:
    sys.exit(f"refusing to package: {error}")
bad = [y for y, path in his.years.items() if path != his.baseline / f"{y}.txt"]
sys.exit(f"refusing to package: his {bad} not sorted, unique and lowercase" if bad else 0)' || exit 1
# One file a year, as his: 1996 to 2001 the registrable and the hostname additions merged (the
# export keeps them disjoint), 2002 to 2013 the extended export's. Each manifest in provenance/.
for y in 1996 1997 1998 1999 2000 2001; do
    LC_ALL=C sort -m -u "output/netnew/$y.txt" "output/netnew/${y}_hostnames.txt" > "$A/$y.txt"
    [ "$(wc -l < "$A/$y.txt")" -eq "$(cat "output/netnew/$y.txt" "output/netnew/${y}_hostnames.txt" | wc -l)" ] \
        || { echo "refusing to package: $y registrable and hostname additions overlap" >&2; exit 1; }
done
cp output/netnew/evidence_manifest.csv output/netnew/hostnames_evidence_manifest.csv "$P/"
EXT=output/extended_years
if ls "$EXT"/additions/*.txt >/dev/null 2>&1; then
    uv run python scripts/round/extended_export.py --check --allow-added \
        || { echo "refusing to package: $EXT is stale" >&2; exit 1; }
    cp "$EXT"/additions/*.txt "$A/"
    cp "$EXT/evidence_ledger.csv" "$EXT/dedup_report.csv" "$EXT/manifest.json" "$P/"
else
    echo "no extended additions: packaging 1996 to 2001 only"
fi
# The source-saturation ledger his 0901 update requires, regenerated at packaging.
uv run python scripts/round/saturation_ledger.py --out "$S/audit/source_saturation_ledger.csv"

# THE CANDIDATE SET: every candidate collection we hold in one list, net of every name his
# release holds as a candidate or in any annual file, and one provenance row a name naming its
# class, its source file and the position in it. No `|| true`: the export writes both.
cp output/netnew/candidate_additions.txt "$C/candidates.txt"
cp output/netnew/candidate_provenance.csv "$C/provenance.csv"
# THE LABELLED THIRD PART, outside both sets and the growth figure: year_evidence.py's tiers.
if [ -f output/year_evidence/provenance.csv ]; then
    cp -R output/year_evidence "$STAGE/year_evidence"
else
    echo "no output/year_evidence: packaging the two sets only"
fi
# The README's one table of classes: names and EE from the export's summary, so its total is the
# bank's, and the sentence of his brief that makes each class a candidate.
python3 - "$STAGE/README.md" output/netnew/candidate_additions_summary.json \
    docs/round/candidate_classes.tsv <<'PY' || { echo "refusing to package: no class table" >&2; exit 1; }
import json
import sys
from decimal import Decimal
from pathlib import Path

readme, summary, rules = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text()), Path(sys.argv[3])
why = dict(line.split("\t", 1) for line in rules.read_text(encoding="utf-8").splitlines()[1:] if "\t" in line)
rows = ["| class | why it is a candidate, in your brief's words | names | equivalent-English |",
        "|---|---|---:|---:|"]
names, ee = 0, Decimal(0)
for label, entry in sorted(summary["by_class"].items(), key=lambda kv: -Decimal(kv[1]["equivalent_english"])):
    rows.append(f"| {label} | {why.get(label, '').strip()} | {entry['names']:,} | {Decimal(entry['equivalent_english']):,.1f} |")
    names, ee = names + entry["names"], ee + Decimal(entry["equivalent_english"])
if (names, ee) != (summary["candidates"], Decimal(summary["equivalent_english"])):
    sys.exit(f"the classes sum to {names} names and {ee} EE, the summary says otherwise")
rows.append(f"| **all** | | **{names:,}** | **{ee:,.1f}** |")
if missing := [label for label in summary["by_class"] if not why.get(label, "").strip()]:
    print(f"warning: no sentence of his for {missing}", file=sys.stderr)
text = readme.read_text(encoding="utf-8")
readme.write_text(text.replace("[CLASS TABLE]", "\n".join(rows)), encoding="utf-8")
PY

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

# the auxiliary seed pool: hostnames and URLs, the granularity the registered
# domain counting unit necessarily drops
cp output/seeds/download_seeds.csv "$S/seeds/" 2>/dev/null || true

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
# directory, and `just reproduce journals` addresses them by nested path: `data/raw/cdx/cdx_*`,
# `data/raw/expand/round2/...`, `data/raw/usenet/...`. So tier 3's replay stage matched
# nothing for every source while the archive README claimed "this is what tier 3 replays,
# so every network stage reproduces offline". Found 2026-08-18 by running the layout
# against the globs rather than reading it.
#
# The tar pipe rather than `cp --parents`, which is GNU-only, and `--strip-components=2`
# to drop the `data/raw` prefix so `cp -R journals/. data/raw/` restores the tree exactly.
#
# **Journal sets held out of the archive on size, on one three-part test**: the assignments
# they back are in the provenance Parquet, which `verify.sh` tests (tier 2); the source they
# parse is linked in `sources.md`; and the parser ships in `source/`, so they re-derive offline
# and only a tier-3 replay needs them. The RDAP logs fail the second part (the registries' terms
# forbid re-walking them) and are held out on size alone, sent on request. A set that fails the
# test ships whatever its size: the two bulk IA CDX reads at hostname grain, whose converter is
# not in `source/`, and the Usenet header extraction journals, which no register row names. The
# journals README below carries the sizes, so the archive states its own limitation.
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
        -not -path 'data/raw/rdap/*' -not -path 'data/raw/rdap_pool/*' \
        -not -path 'data/raw/usenet_addr/*' -not -path 'data/raw/usenet_bare/*' \
        -not -path 'data/raw/usenet/*' -not -path 'data/raw/usenet_hdr/*' \
        -not -path 'data/raw/usenet_new/*' -not -path 'data/raw/cdx_suffix/*' \
        -not -path 'data/raw/nypw_hostgrain/*' -not -path 'data/raw/nypw_firstcdx_hostgrain/*' \
        -not -path 'data/raw/ukwa_hostgrain/*' -not -path 'data/raw/arquivo_hostgrain/*' \
        -not -path 'data/raw/usenet_alt_items/*' -not -path 'data/raw/usenet_alt2_items/*' \
        -not -path 'data/raw/usenet_aus_items/*' -not -path 'data/raw/usenet_biz_items/*' \
        -not -path 'data/raw/usenet_bulk_items/*' -not -path 'data/raw/usenet_can_items/*' \
        -not -path 'data/raw/usenet_comp_items/*' -not -path 'data/raw/usenet_misc_items/*' \
        -not -path 'data/raw/usenet_new_items/*' -not -path 'data/raw/usenet_news_items/*' \
        -not -path 'data/raw/usenet_rec_items/*' -not -path 'data/raw/usenet_sci_items/*' \
        -not -path 'data/raw/usenet_soc_items/*' -not -path 'data/raw/usenet_talk_items/*' \
        -not -path 'data/raw/usenet_uk_items/*' -not -path 'data/raw/extended_spent/*'
}
# the provenance graph as Parquet: which source saw which domain in which year, so any shipped
# line can be traced without the source data or the database. Only the rows of the names the
# shipped lists hold (ark.provenance.write_shipped): the whole export is the store's authority
# and stays home. An empty output/provenance refuses the package.
if ! compgen -G "output/provenance/*.parquet" >/dev/null; then
    echo "refusing to package: output/provenance is empty" >&2
    echo "run 'uv run ark export --provenance' first, then re-run." >&2
    exit 1
fi
uv run python -c 'import sys
from pathlib import Path
from ark.provenance import write_shipped
print("provenance:", write_shipped(Path("output/provenance"), Path("output/netnew"),
      Path("output/candidate_unverified.txt"), Path(sys.argv[1])))' "$P"

# Of journal_paths, only those a shipped row cites by file name: a shipped evidence row's
# source_file or an extended ledger row's. The rest back nothing in the archive.
CITED=$(mktemp)
uv run python - "$P" > "$CITED" <<'PY' || { echo "refusing to package: the cited journals could not be read from the shipped provenance and the extended ledger" >&2; exit 1; }
import csv
import sys
from pathlib import Path

from ark.db import connect

query = f"SELECT DISTINCT source_file FROM read_parquet('{sys.argv[1]}/evidence.parquet')"
cited = {Path(row[0]).name for row in connect(":memory:").execute(query).fetchall() if row[0]}
with Path("output/extended_years/evidence_ledger.csv").open(newline="", encoding="utf-8") as fh:
    cited |= {Path(row["source_file"]).name for row in csv.DictReader(fh)}
print("\n".join(sorted(cited)))
PY
if [ ! -s "$CITED" ]; then
    echo "refusing to package: no shipped row cites a journal" >&2
    exit 1
fi
cited_journals() { journal_paths | awk -F/ 'NR == FNR { cited[$0]; next } $NF in cited' "$CITED" -; }
if [ -z "${ARK_SLIM:-}" ]; then
    cited_journals \
        | tar -cf - -T - 2>/dev/null \
        | ( cd "$S/journals" && tar xf - --strip-components=2 2>/dev/null ) || true
    cat > "$S/journals/README.txt" <<'EXCL'
Only the journals a shipped evidence row or extended_years/evidence_ledger.csv names are here.

Journal sets deliberately not here, on size and nothing else (.jsonl.gz bytes on disk,
2026-09-22): the RDAP walks (rdap/, 3.6 GB), the Usenet extraction and posting journals
(usenet_addr/ 9.9 GB, usenet_bare/ 2.1 GB, usenet/ 550 MB, usenet_hdr/ 180 MB, usenet_new/
123 MB), the raw platform-sweep capture journals (cdx_suffix/, 21.6 GB), the NYPW hostname-grain
conversions (nypw_hostgrain/ 353 MB, nypw_firstcdx_hostgrain/ 81 MB), the UK Web Archive geoindex
conversion (ukwa_hostgrain/, 196 MB), the Arquivo.pt CDXJ conversion (arquivo_hostgrain/, 102 MB)
the fifteen Usenet body-URL pools (usenet_*_items/ other than usenet_header_items/, 542 MB)
and the bulk capture-index journals an earlier round shipped, which back no record here
(extended_spent/, 3.9 GB). Together about 43 GB against about 0.9 GB for everything here.

Every assignment they back still ships and is still checkable: each (domain, year) and
(hostname, year) resolves to its evidence row in provenance/, which is what verify.sh tests
over every assignment. Each set re-derives from a linked public source named in sources.md
(archive.org mboxes for the Usenet sets, the NYPW first-capture and TimeMap items, the UK Web
Archive geoindex, the Arquivo.pt CDXJ dataset, the IA CDX API for cdx_suffix) with the parser
in source/, so tier 3 can rebuild them; the RDAP logs cannot be re-walked under the registries'
terms and will be sent on request.
EXCL
fi

# the seed lists those page fetches ran against, so page expansion is repeatable
mkdir -p "$S/seeds/expansion"
cp seeds/expansion/*.txt "$S/seeds/expansion/" 2>/dev/null || true

# His release does not ship back to him: baseline/README.txt names it and gives the sha256 and
# line count of each file of his the checks read, and verify.sh reads his copy from HIS.
eval "$(uv run python -c "
import shlex
from ark.baseline import CURRENT_BASELINE_DIR, CURRENT_BASELINE_MARKER
print(f'MERGED={shlex.quote(str(CURRENT_BASELINE_DIR))}')
print(f'MARKER={shlex.quote(CURRENT_BASELINE_MARKER)}')
")"
if [ ! -f "$MERGED/1996.txt" ]; then
    echo "refusing to package: $MARKER not found at $MERGED, the release the figures count against" >&2
    exit 1
fi

python3 - "$MERGED" "$MARKER" > "$S/baseline/README.txt" <<'PY'
import hashlib
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

root, marker = Path(sys.argv[1]), sys.argv[2]
names = [f"{y}.txt" for y in range(1996, 2014)]
# his candidate files as this release has them: merge261104 has no unparsed-format file
names += [n for n in ("candidate_pool.txt", "candidate_pool_unparsed_format.txt") if (root / n).is_file()]
names += sorted(f"isc_survey_hostnames/{p.name}" for p in (root / "isc_survey_hostnames").glob("*.txt"))


def measure(name):
    digest, lines = hashlib.sha256(), 0
    with (root / name).open("rb") as fh:
        while chunk := fh.read(1 << 22):
            digest.update(chunk)
            lines += chunk.count(b"\n")
    return f"{digest.hexdigest()}  {lines:>11}  {name}"


print(f"{marker}: your release, which every net-new figure counts against, not shipped back.")
print(f"The checks read it from HIS: HIS=/path/to/{marker} bash verify.sh")
print("sha256, lines and name of each file of it the checks read:")
with ThreadPoolExecutor(8) as pool:
    print("\n".join(pool.map(measure, names)))
PY


# The reviewer's own scorer, so the archive can re-derive its headline figure without
# reference to anything outside itself. `round_figures.py --verify` is named in the
# report as the way to re-score the increment, and running it inside an unpacked
# archive failed with "calculator not found": it lived only in the repository. Found
# by running the report's own instructions in a fresh extraction, 2026-08-17.
#
# It is his file coming back to him: a reviewer should be able to check the arithmetic
# without fetching anything, and the whole thing is a few tens of kilobytes.
mkdir -p "$S/equivalent_english_domain_calculator"
CALC_SRC="$(dirname "$MERGED")/equivalent_english_domain_calculator"
if [ -d "$CALC_SRC" ]; then
    # A tar pipe rather than `cp -R`, to drop `__pycache__`: shipping compiled
    # bytecode of somebody else's script is noise, and it changes on every run so the
    # archive checksum would never settle. `--exclude` works in both BSD and GNU tar,
    # unlike `cp --parents`, which is GNU only and would have failed on this machine.
    ( cd "$CALC_SRC" && tar cf - --exclude '__pycache__' . ) \
        | ( cd "$S/equivalent_english_domain_calculator" && tar xf - )
else
    echo "warning: no calculator beside $MERGED, archive will not self-score" >&2
fi

# audit CSVs, each once: only those written since the newest other round's archive was built.
# No file of data/logs ships: each can name a local or private/ path, and the execution logs the
# brief asks for ship inside Open Research Questions/ and audit/.
LAST_BUILT=$(awk -v own="$ROUND_DIR/MANIFEST.txt" 'FILENAME != own && $1 == "built" {print $2}' \
    submissions/*/MANIFEST.txt 2>/dev/null | sort | tail -1)
SINCE="$STAGE/.since"
TZ=UTC touch -t "$(printf '%s' "${LAST_BUILT:-1970-01-01T00:00:00Z}" | tr -d ':TZ-' | sed 's/\(..\)$/.\1/')" "$SINCE"
find data/reports -maxdepth 1 -name '*.csv' -newer "$SINCE" -exec cp {} "$S/audit/" \; 2>/dev/null || true
rm "$SINCE"

# source-code snapshot (tracked files at HEAD) + the commit it came from
git archive --format=tar HEAD | gzip -c > "$S/source/source.tar.gz"
git rev-parse HEAD > "$S/source/COMMIT.txt"

# Every cited journal on disk must be in the archive; the count catches a directory no glob names.
ON_DISK=$(cited_journals | wc -l | tr -d ' ')
SHIPPED_JOURNALS=$(find "$S/journals" -name '*.jsonl.gz' | wc -l | tr -d ' ')
if [ -n "${ARK_SLIM:-}" ]; then
    if [ "$SHIPPED_JOURNALS" != "0" ]; then
        echo "refusing to package: ARK_SLIM set but $SHIPPED_JOURNALS journals staged" >&2
        exit 1
    fi
    cat > "$S/journals/README.txt" <<'SLIM'
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
    cited_journals | sed 's|.*/||' | sort > /tmp/ark_on_disk.txt
    find "$S/journals" -name '*.jsonl.gz' -exec basename {} \; \
        | sort > /tmp/ark_shipped.txt
    comm -23 /tmp/ark_on_disk.txt /tmp/ark_shipped.txt >&2
    exit 1
fi
echo "journals: $SHIPPED_JOURNALS shipped, matching what is on disk"

# Nothing private ships: no staged path names `private`, no staged text names this home.
# A grep for `private/` alone would refuse archived URLs (`/_private/`) and passed round 12's
# logs, which named 1,259 `private/` files by their bare names.
LEAK=$( { find "$STAGE" -iname '*private*'; grep -rlIF -e "$HOME" "$STAGE" || true; } )
if [ -n "$LEAK" ]; then
    echo "refusing to package: private or local paths in:" >&2
    printf '%s\n' "$LEAK" | sed -n 1,10p >&2
    exit 1
fi

# per-file checksums, then the archive, then the archive's own checksum
( cd "$STAGE" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 shasum -a 256 > SHA256SUMS )
# On every core; `7z a` adds to an archive already there, so a rerun in the same minute starts clean.
rm -f "$ARCHIVE"
( cd output && 7z a -mmt=on "$PROJ/$ARCHIVE" "$RELEASE" > /dev/null )
# A mail transfer service refuses an archive over 5 GB, and the journals grow every round, so a
# round can reach that. Such an archive goes as a Drive link.
TRANSFER_BYTES=5000000000
ARCHIVE_BYTES=$(wc -c < "$ARCHIVE" | tr -d ' ')
if [ "$ARCHIVE_BYTES" -gt "$TRANSFER_BYTES" ]; then
    echo "WARNING: $ARCHIVE_BYTES bytes, over a transfer service's 5 GB: send it as a Drive link," >&2
    echo "         with its size, sha256 and the link in the mail" >&2
fi
# The checksum file records the bare filename, not the build path: a reviewer
# who downloads only the archive runs `shasum -c` beside it, and a stored path
# of `submissions/...` makes that fail before they have checked anything.
( cd "$ROUND_DIR" && shasum -a 256 "$RELEASE.7z" > "$RELEASE.7z.sha256" )
ARCHIVE_SHA=$(cut -d' ' -f1 "$ROUND_DIR/$RELEASE.7z.sha256")

# What stays in git after the archive is git-ignored: the checksum, and a manifest
# naming the commit and the baseline. The report and registers as sent are at that
# commit, and the checksum proves a recovered archive is the one that was sent, so no
# copy is kept. Rebuilding a superseded round is `git checkout <commit>` then
# `just reproduce deliver && just ship package`.
{
    echo "round        $ROUND"
    echo "built        $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "commit       $(git rev-parse HEAD)"
    echo "baseline     $MARKER"
    echo "archive      $RELEASE.7z"
    echo "sha256       $ARCHIVE_SHA"
    echo "bytes        $(wc -c < "$ARCHIVE" | tr -d ' ')"
    echo "files        $(find "$STAGE" -type f | wc -l | tr -d ' ')"
    echo "netnew_pairs $STORED"
    # The second output unit ships in its own files, so the manifest names it too:
    # netnew_pairs alone reads as the whole round and has not been since 2026-09-01.
    echo "netnew_hostnames $(cat output/netnew/199[6-9]_hostnames.txt output/netnew/200[01]_hostnames.txt | wc -l | tr -d ' ')"
    echo "candidates   $(wc -l < "$C/candidates.txt" | tr -d ' ')"
} > "$ROUND_DIR/MANIFEST.txt"

# Everything needed to hand the archive over by link, in one block to copy.
cat <<EOF

Delivery archive ready, in $ROUND_DIR/

  filename   $(basename "$ARCHIVE")
  size       $(du -h "$ARCHIVE" | cut -f1) ($(wc -c < "$ARCHIVE" | tr -d ' ') bytes)
  format     7z (extract: 7z x $(basename "$ARCHIVE"))
  sha256     $ARCHIVE_SHA
  contents   $(find "$STAGE" -type f | wc -l | tr -d ' ') files, unpacking to $RELEASE/

Tracked beside it: MANIFEST.txt and the .sha256.
The archive itself is git-ignored. Add the round's row to docs/registers/rounds.md.
EOF
