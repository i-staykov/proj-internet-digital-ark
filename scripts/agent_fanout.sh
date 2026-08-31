#!/usr/bin/env bash
# Run N independent hypotheses at once, then bank them in ONE serial step.
#
# **Why fan out at all.** EE and speed are a proxy; the deliverable is demonstrated
# research (Ivo, 2026-08-27). Breadth of hypothesis is therefore part of the product, and
# independent hypotheses have no reason to wait for each other. Serial iteration also
# spends most of its wall clock on ONE guess, which is the wrong bet when the aim is to
# find a high-yield outlier among many candidates.
#
# **Why the write barrier.** Several `claude -p` processes editing `docs/sources.md` and
# committing to one branch produce conflicts and a failed gate, which is how parallelism
# usually loses more than it gains. So the split is strict:
#
#   researchers  read anything, fetch anything, measure against the store, and write ONLY
#                to their own `private/findings/<slug>.md`. No git. No shared docs.
#   harvester    one process, after they finish: reads every new findings file, merges
#                them into `docs/sources.md` and the triage queue, gates, commits once.
#
# That makes the parallel part read-mostly and the mutating part serial, which is the only
# shape that is safe without a worktree per agent.
#
# Each round re-reads the hypothesis file, so a hypothesis added mid-run is picked up.
#
#     bash scripts/agent_fanout.sh <deadline_epoch> [parallel] [hypothesis_file]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:?usage: agent_fanout.sh <deadline_epoch> [parallel] [hypothesis_file]}"
# **Two, not four, and the reason is not throughput.** Four concurrent researchers plus an
# 8-worker CDX collector plus DuckDB ingests against a 23 GB store filled 5.4 GB of a 7 GB
# swap on the night of 2026-08-27, on a machine somebody else is also using. Ivo asked
# afterwards whether the run had killed his editor and his chat client, and the honest
# answer was that it could not be ruled out. A research loop that squeezes its operator
# out of his own desktop is not worth the extra hypothesis per hour.
#
# **Revised to 3 on 2026-08-31**, after Ding asked for parallelism explicitly and confirmed
# the 5% trigger is firm. Three, not four, because the swap incident above was real and the
# machine is still shared; the extra slot is paid for by moving the harvest off Opus rather
# than by spending more. MIN_FREE_PCT still refuses a round when memory is tight.
PAR="${2:-3}"
# Seconds a single researcher may run before it is asked to stop.
RESEARCH_CAP="${RESEARCH_CAP:-2400}"
# Do not start a round when the machine is this tight.
MIN_FREE_PCT="${MIN_FREE_PCT:-25}"
# Seconds to idle between rounds. This is a TOKEN budget, not politeness. 1800 was set for
# an unattended 56-hour weekend; 900 is for a supervised daytime window, where the operator
# is watching and wall-clock matters more. The collectors carry equivalent-English growth
# meanwhile at ZERO token cost, so a paused researcher slot is never idle time overall.
ROUND_PAUSE="${ROUND_PAUSE:-900}"

# **Model and effort per ROLE, and this is a token-efficiency decision, not a cosmetic one**
# (Ivo, 2026-08-31: "maximize speed and token-efficiency of domain acquisition ... if we use
# my whole weekly limit, we were too fast and should have been more efficient instead").
#
# The roles are not equally worth an expensive model:
#
#   researcher  CREATIVE. Forms a hypothesis, finds an artifact nobody has looked for, and
#               judges evidence. This is where the outlier comes from and where the whole
#               return sits, so it gets the best model at high effort. Never economise here.
#   scribe      MECHANICAL and runs EVERY round: append a row per finding, record a result
#               line, re-sort the queue, gate, commit. No judgement, no new code, and it is
#               append-only. Sonnet at low effort does this correctly and much cheaper.
#   admitter    RARE and EXPENSIVE TO GET WRONG: applies the standing approval rule, writes
#               an ingest spec, ingests, and must leave `ark check` passing. It only runs
#               when a researcher reported a FIND, which most rounds do not, so paying for
#               a strong model on the uncommon path costs little and a bad ingest costs a
#               lot. Opus at medium effort.
#   generator   CREATIVE but infrequent: proposes hypotheses when the queue empties.
#
# The collectors and the watchdog use NO model at all, which is why they are the most
# token-efficient equivalent-English in the project and should never be throttled to make
# room for an agent.
RESEARCH_MODEL="${RESEARCH_MODEL:-opus}"
RESEARCH_EFFORT="${RESEARCH_EFFORT:-high}"
SCRIBE_MODEL="${SCRIBE_MODEL:-sonnet}"
SCRIBE_EFFORT="${SCRIBE_EFFORT:-low}"
ADMIT_MODEL="${ADMIT_MODEL:-opus}"
ADMIT_EFFORT="${ADMIT_EFFORT:-medium}"
GEN_MODEL="${GEN_MODEL:-opus}"
GEN_EFFORT="${GEN_EFFORT:-high}"
HYPO="${3:-private/agent-hypotheses.md}"
LOG="data/logs/agent_fanout.log"
LEDGER="data/logs/agent_fanout.tsv"
FIND=private/findings
mkdir -p data/logs "$FIND"
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

LOCK="data/logs/agent_fanout.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    holder=$(cat "$LOCK/pid" 2>/dev/null || echo unknown)
    if [ "$holder" != unknown ] && kill -0 "$holder" 2>/dev/null; then
        echo "already running as pid $holder" >&2; exit 1
    fi
    rm -rf "$LOCK" && mkdir "$LOCK" || exit 1
fi
printf '%s\n' "$$" > "$LOCK/pid"
trap 'rm -rf "$LOCK"; note "fanout exit"' EXIT

# Free memory as a percentage, from the same source Activity Monitor reads.
free_pct() {
    memory_pressure 2>/dev/null \
        | sed -n 's/^System-wide memory free percentage: *\([0-9]*\)%.*/\1/p' | head -1
}

# Wait until the machine has room. Called before every round, so a heavy DuckDB ingest or
# a browser the operator just opened delays research rather than competing with it.
wait_for_memory() {
    local waited=0 pct
    while :; do
        pct=$(free_pct); pct="${pct:-100}"
        [ "$pct" -ge "$MIN_FREE_PCT" ] && break
        [ "$waited" -ge 900 ] && { note "memory still at ${pct}% free after 15m, proceeding anyway"; break; }
        note "only ${pct}% memory free, waiting 60s before the next round"
        sleep 60
        waited=$((waited + 60))
    done
}

ee_now() {
    uv run python scripts/round_figures.py 2>/dev/null \
        | sed -n 's/^4\. Equivalent-English increment *: *//p' | tr -d ', ' | head -1
}

[ -f "$LEDGER" ] || printf 'round\tstarted\tended\tslugs\tee_before\tee_after\tdelta\n' > "$LEDGER"
note "start: until $(date -r "$DEADLINE" '+%F %T' 2>/dev/null || echo "$DEADLINE"), parallel=${PAR}"
# Log the model tiering, so a later reading of the ledger can attribute token spend to a
# configuration rather than guessing which run was the expensive one.
note "models: research=${RESEARCH_MODEL}/${RESEARCH_EFFORT} scribe=${SCRIBE_MODEL}/${SCRIBE_EFFORT} admit=${ADMIT_MODEL}/${ADMIT_EFFORT} gen=${GEN_MODEL}/${GEN_EFFORT} pause=${ROUND_PAUSE}s"

round=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    round=$((round + 1))
    left=$(( DEADLINE - $(date +%s) ))
    # Not enough time to research AND harvest is not enough time. Stop cleanly.
    if [ "$left" -lt 600 ]; then note "under 10 minutes left, not starting another round"; break; fi
    if [ "$round" -gt 1 ]; then note "pausing ${ROUND_PAUSE}s between rounds"; sleep "$ROUND_PAUSE"; fi

    # Open hypotheses: a `## slug | title` heading whose block has no `result:` line yet.
    SLUGS=""
    while IFS= read -r slug; do
        [ -n "$slug" ] && SLUGS="$SLUGS $slug"
    done < <(uv run python scripts/pick_hypotheses.py "$HYPO" "$PAR" --pending-dir "$FIND" 2>/dev/null)
    SLUGS="${SLUGS# }"
    # **An empty queue is a prompt to think, not a reason to stop.** On the night of
    # 2026-08-27 this branch said `break` and the loop sat idle for six and a half hours
    # while the collectors ran on without it. A research loop that can run out of
    # hypotheses is a research loop that will.
    if [ -z "$SLUGS" ]; then
        note "queue empty: generating more hypotheses rather than stopping"
        GFILE="data/logs/prompt_${round}_generate.txt"
        cat > "$GFILE" <<EOG
Read CLAUDE.md, then docs/discovery.md, then skim the "Evaluated and rejected" table in
docs/sources.md to see what SHAPES have already been tried.

Then read the LAST 15 \`result:\` lines in ${HYPO}. Those are the hypotheses that just
died and the reason each one died. You are being asked for hypotheses that do not die the
same way.

**THE ROSTER LAW, and it forbids a whole class of proposal.** 37 hypotheses were priced
on the night of 2026-08-27 and nearly every one died on the same unit: an artifact whose
row is "one organisation with a homepage URL" prices at 0.0069 to 0.1097 EE per listed
domain, so 1,000 EE needs about 20,000 listed rows and the largest in-window roster found
was 1,550. Do NOT propose another seal roster, member list, exhibitor database, trade
directory, entity register, supplier profile, publisher roster or store registry. A high
fill rate does not rescue it: several passed the year screen at 100% and still died,
because 100% of 41 pairs is 41 pairs.

**Propose a different UNIT.** Ask what ONE ROW of the artifact is. A row that is a
machine's own observation of a name at an instant is what has paid every time: a registry
event, a blocklist entry, a crawl fetch, a mail header, a zone delegation, a package
index. Every five-figure source this project holds has that shape. If you cannot name
what machine wrote the row and when, do not propose it.

Append 6 to 10 NEW hypotheses to ${HYPO}, in the existing format:
  ## <slug_with_underscores> | <one-line title>
  <a paragraph: what the artifact is, what would date one item, why its held fraction
  might be high, and the cheapest screen that would kill it>

Rules for a good hypothesis here:
- Differ in SHAPE, not in host. Ding asks for breadth and grades method.
- Aim at a year the store lacks. Adjacent-year headroom is largest at 2001 and 2000.
- Prefer artifacts whose names are ALREADY HELD: novelty is a cost under the split.
- Name a concrete host or corpus, not a category.

**MEASURED QUALITY BAR, from 85 hypotheses actually run.** Their median was 3.5 net-new
EE and their sum was 7,499, against a single artifact found by the same loop that paid
14,229. Small is admitted, but proposing small is a waste of a slot. So every block you
write MUST carry these three lines, and you must drop any candidate that cannot fill them:

  floor: <why this could plausibly clear 1,000 EE. Roughly: expected rows x expected
         held-fraction x P(store lacks that year | held) x TLD weight. Show the product.
         P(lacks 2001 | held) is 0.611 com, 0.653 net, 0.568 org, 0.309 uk.>
  nearest closed: <the closest family in docs/sources.md and the ONE property that makes
         this different. Grep sources.md BEFORE writing the block, not after.>
  kill screen: <the single cheapest observation that would end it, costing one request>

**Twelve of those 85 runs discovered mid-flight that the family was already closed.**
That is a seventh of the budget spent re-testing, and it is your job to prevent, not the
researcher's to discover. If you cannot name the nearest closed family, you have not
grepped.

**Bias hard toward the two shapes that have actually paid five figures here.** First, a
SECOND ATTRIBUTE of an artifact already on disk: the RIPE snapshot was read once for the
domain name and re-read for its per-object `changed:` lines, which paid 58,398 EE with no
new download and no new permission. Ask what else the files in data/raw/ say. Second, a
machine-written bulk list with a per-item stamp and a high held-fraction: the 2001
blocklists paid 14,229 and 10,377 because 94% of their names were already held and simply
lacked that year. Both shapes beat any directory of hand-typed links by two orders of
magnitude.

Write ONLY to ${HYPO}. Do not run git. Do not ingest. Do not edit docs/.
EOG
        claude -p "$(cat "$GFILE")" --permission-mode auto --output-format text \
            --model "$GEN_MODEL" --effort "$GEN_EFFORT" \
            > "data/logs/fanout_${round}_generate.log" 2>&1 < /dev/null
        SLUGS=""
        while IFS= read -r slug; do
            [ -n "$slug" ] && SLUGS="$SLUGS $slug"
        done < <(uv run python scripts/pick_hypotheses.py "$HYPO" "$PAR" --pending-dir "$FIND" 2>/dev/null)
        SLUGS="${SLUGS# }"
        if [ -z "$SLUGS" ]; then
            note "generation produced nothing; retrying next round after a short pause"
            sleep 120
            continue
        fi
        note "generated: ${SLUGS}"
    fi
    wait_for_memory
    started=$(date -u '+%F %T'); before=$(ee_now); before="${before:-0}"
    note "round ${round}: ${left}s left, launching: ${SLUGS}"

    pids=()
    killers=()
    for slug in $SLUGS; do
        budget=$(( left - 420 ))
        PFILE="data/logs/prompt_${round}_${slug}.txt"
        cat > "$PFILE" <<EOP
You are ONE researcher in a parallel fan-out. Budget: about ${budget} seconds. Nobody
reads a status update; your output is a file.

Read CLAUDE.md first, it is binding. Your hypothesis is the block headed
"## ${slug} |" in ${HYPO}. Read that block and only that block.

Test it:
1. Grep docs/sources.md for the family FIRST. If it is already closed there, say so and
   stop; that is a complete and useful result. **GREP it, never read it whole: it is over
   600 KB and reading it costs more than most hypotheses are worth.** The same goes for
   docs/approved-sources-list.md at ~150 KB. Read CLAUDE.md and your own hypothesis block
   in full; grep everything else.
2. Read the WHOLE robots.txt of any host before the first request. Honour Retry-After.
   Do NOT touch web.archive.org/cdx: two collectors are metering against it. Other
   archive.org services and other hosts are fine.
3. **PROBE BEFORE YOU COMMIT.** Fetch the SMALLEST representative piece, one page or one
   file, and measure three numbers on it: distinct registrable domains, the fraction
   ALREADY HELD, and the fraction held AND missing the artifact's own year. Extrapolate
   to the whole artifact and write that estimate down.
   Then decide, and say which branch you took:
   - projected under 200 EE: STOP. Report it as CLOSED with the probe numbers. Do not
     fetch the rest. A small source is worth admitting when we already hold it, never
     worth an hour of fetching to confirm it is small.
   - projected 200 to 1,000 EE: take it only if the remaining fetch is cheap, minutes
     rather than an hour.
   - projected over 1,000 EE: do the full measurement carefully, this is the case that
     matters.
   **The probe is the deliverable even when the answer is no.** Across 85 prior runs the
   median was 3.5 EE and the mean fetch was far larger than that justified.
4. Price the full artifact only if the probe cleared. Quote net-new post-split EE against
   merged260827-2. Sample distinct domains, never domain_year rows.
5. If the artifact is on disk already under data/raw/, there is no fetch and no probe
   budget to save: read it properly. Those have been the highest-paying runs.

Write your result to private/findings/${slug}.md, in this shape and nothing else:
  # ${slug}
  verdict: FIND | CLOSED | BLOCKED
  ee: <net-new post-split EE, a number, 0 if none>
  probe: <the smallest piece measured, its domains, held fraction, held-and-missing-year
         fraction, and the projection to the whole artifact>
  what dates one item: <one line, or "nothing" if it cannot date a year>
  artifact: <URL and byte size, or why unreachable>
  measurement: <the numbers, including what you sampled>
  method: <the reusable part, if any>
  next: <what you would do with more time, or "closed">

HARD RULES: do NOT run git. Do NOT edit any file except your own findings file. Do NOT
ingest anything. Do NOT edit docs/. Another process banks your result.
A measured negative is a RESULT: fill the file either way.
EOP
        # **A per-researcher cap, because one hang stalls the whole round.** On
        # 2026-08-27 a researcher wrote its findings file and then never exited; the
        # round waited on it for 1h13m while the other three sat finished. macOS ships
        # no `timeout`, so the cap is a watcher process per researcher.
        ( claude -p "$(cat "$PFILE")" --permission-mode auto --output-format text \
            --model "$RESEARCH_MODEL" --effort "$RESEARCH_EFFORT" \
            > "data/logs/fanout_${round}_${slug}.log" 2>&1 < /dev/null ) &
        rpid=$!
        ( sleep "$RESEARCH_CAP"; kill -TERM "$rpid" 2>/dev/null ) &
        killers+=($!)
        pids+=($rpid)
    done
    for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null; done
    for k in "${killers[@]:-}"; do kill "$k" 2>/dev/null; done
    note "round ${round}: researchers done, harvesting"

    # **The harvest is split in two, and the split is a token decision.** Banking a round
    # is two different jobs wearing one hat. Appending a row per finding, recording a
    # result line, re-sorting the queue, gating and committing is MECHANICAL, append-only,
    # and happens every single round. Admitting a source is RARE, needs the standing rule
    # applied to real evidence, may need an ingest spec written, and must leave `ark check`
    # passing. Paying Opus for the first job every round to be ready for the second job
    # occasionally is the most expensive habit this loop had.
    #
    # So: a cheap SCRIBE always runs, and an expensive ADMITTER runs only when some
    # findings file actually says FIND. Most rounds never wake the admitter.
    grep -rlE '^\s*verdict:\s*(FIND|find)' "$FIND"/*.md >/dev/null 2>&1 && FOUND=1 || FOUND=0

    SFILE="data/logs/prompt_${round}_scribe.txt"
    cat > "$SFILE" <<EOP
You are the scribe for one research round. This is bookkeeping, not judgement: do exactly
these steps and nothing more. Do NOT ingest anything, do NOT write an ingest spec, and do
NOT edit docs/approved-sources-list.md.

Read CLAUDE.md for the commit rules only. **Do not read docs/sources.md whole: it is over
600 KB. Append to it, and grep it if you need to check something.**

private/findings/ holds one file per hypothesis just tested. For each file:
1. Append a row to the "Evaluated and rejected" table in docs/sources.md carrying its
   verdict, its numbers and its method, so nobody re-tests it. Positive or negative.
   Under 5,000 EE gets ONE line: the link, the sentence saying what dates one item, the
   figure. Nothing else.
2. Record the outcome on that hypothesis's block in ${HYPO} as a single
   "result: <verdict>, <figure>, <one clause why>" line.
3. uv run python scripts/rank_triage.py
4. Gate, never through a pipe:
   uv run ruff check . && uv run ruff format --check . && uv run pytest -q
   then uv run ark export && uv run ark check
5. Commit on the current branch. Never push. No AI attribution. No em-dashes or en-dashes.
   Be brief in the body: what was tested, what each measured, what the method was.
6. Move the harvested files to private/findings/banked/ so the next round starts clean.
EOP
    # Backgrounded so the next round of researchers starts immediately. Only the scribe and
    # the admitter touch git and docs/, and researchers touch neither, so the overlap is
    # safe and it removes the serial harvest gap from the wall clock.
    # **Exactly one writer at a time, and the previous ordering did not guarantee it.**
    # This block used to start the new harvester and only THEN wait for the previous one,
    # so two `claude -p` processes could be committing to the same branch at once. The
    # comment claimed "one harvester at a time" and the code did not deliver it. Waiting
    # first costs nothing in practice, because the previous scribe has had a whole round to
    # finish, and it still overlaps the scribe with the NEXT round's researchers.
    if [ -n "${LAST_HARVEST:-}" ]; then wait "$LAST_HARVEST" 2>/dev/null; fi

    if [ "$FOUND" -eq 1 ]; then
        note "round ${round}: a findings file reports FIND, waking the admitter (${ADMIT_MODEL}/${ADMIT_EFFORT})"
        AFILE="data/logs/prompt_${round}_admit.txt"
        cat > "$AFILE" <<EOP
You are the admitter. One or more files in private/findings/ report a FIND. Read CLAUDE.md
first, it is binding, and read THE STANDING APPROVAL RULE in it carefully.

For each findings file whose verdict is FIND, and only those:
1. Re-check the four conditions of the standing rule against what the file actually says.
   When all four hold: write the entry into docs/approved-sources-list.md, QUOTE the
   machine-written stamp that dates one item, add
   "- admitted under the standing rule of 2026-08-29 (Ivo)", set "Decision: master",
   register an ingest spec if one is needed, ingest it, and confirm ark check still passes.
2. If ANY condition fails, leave "Decision: pending" with the measurement and a
   "- potential:" score, and name the condition that failed. Never invent a new evidence
   class to fit a source, and never widen what counts as evidence to make a source fit.
3. Every source gets its LINK into docs/sources.md before it is ingested, next to the
   sentence saying what dates one item. Two approved sources became unrefetchable because
   only their bytes were kept.
4. Quote net-new POST-SPLIT equivalent-English, never gross. They differ by more than 10x.
5. Then gate, never through a pipe:
   uv run ruff check . && uv run ruff format --check . && uv run pytest -q
   then uv run ark export && uv run ark check
6. Commit on the current branch. Never push. No AI attribution. No dashes.

The scribe handles the register rows and the result lines for every finding, so do not
duplicate that work. Your job is only the admission and the ingest.
EOP
        claude -p "$(cat "$AFILE")" --permission-mode auto --output-format text \
            --model "$ADMIT_MODEL" --effort "$ADMIT_EFFORT" \
            > "data/logs/fanout_${round}_admit.log" 2>&1 < /dev/null
    fi
    claude -p "$(cat "$SFILE")" --permission-mode auto --output-format text \
        --model "$SCRIBE_MODEL" --effort "$SCRIBE_EFFORT" \
        > "data/logs/fanout_${round}_scribe.log" 2>&1 < /dev/null &
    LAST_HARVEST=$!
    note "round ${round}: scribe running (${SCRIBE_MODEL}/${SCRIBE_EFFORT})"
    after=$(ee_now); after="${after:-$before}"
    delta=$(python3 -c "print(f'{float('${after}') - float('${before}'):.4f}')" 2>/dev/null || echo 0)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$round" "$started" "$(date -u '+%F %T')" "$SLUGS" "$before" "$after" "$delta" >> "$LEDGER"
    note "round ${round} banked: EE delta ${delta}"
    # A round that produced nothing usually means a rate limit or a transient API
    # failure, neither of which is a reason to stop for the night.
    if [ "$(ls -1 "$FIND"/*.md 2>/dev/null | wc -l)" -eq 0 ] && [ "${delta}" = "0.0000" ]; then
        FAILS=$(( ${FAILS:-0} + 1 ))
        if [ "$FAILS" -ge 2 ]; then
            note "two barren rounds: backing off 300s in case this is a rate limit"
            sleep 300
            FAILS=0
        fi
    else
        FAILS=0
    fi
done
note "fanout finished after ${round} rounds"
