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
PAR="${2:-2}"
# Seconds a single researcher may run before it is asked to stop.
RESEARCH_CAP="${RESEARCH_CAP:-2400}"
# Do not start a round when the machine is this tight.
MIN_FREE_PCT="${MIN_FREE_PCT:-25}"
# Seconds to idle between rounds. This is a TOKEN budget, not politeness: a 56-hour
# weekend at back-to-back rounds is roughly 300 headless invocations. The collectors
# carry equivalent-English growth meanwhile, so a paused researcher slot costs nothing
# that matters.
ROUND_PAUSE="${ROUND_PAUSE:-1800}"
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
- Do not repeat anything already closed in docs/sources.md. Grep before writing.
- Name a concrete host or corpus, not a category.
Ask what kind of artifact nobody has looked for yet. Machine-written records that
happen to name websites are the seam: registries, blocklists, catalogues, member
directories, mail logs, package metadata, court and regulatory filings, standards
documents, bibliographies, award rosters, sponsor and member lists.

Write ONLY to ${HYPO}. Do not run git. Do not ingest. Do not edit docs/.
EOG
        claude -p "$(cat "$GFILE")" --permission-mode auto --output-format text \
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
   stop; that is a complete and useful result.
2. Read the WHOLE robots.txt of any host before the first request. Honour Retry-After.
   Do NOT touch web.archive.org/cdx: two collectors are metering against it. Other
   archive.org services and other hosts are fine.
3. Price it against the live store: distinct domains, fraction ALREADY HELD, and the
   pairs that are held AND missing the artifact's own year. Quote net-new post-split EE
   against merged260827. Sample distinct domains, never domain_year rows.

Write your result to private/findings/${slug}.md, in this shape and nothing else:
  # ${slug}
  verdict: FIND | CLOSED | BLOCKED
  ee: <net-new post-split EE, a number, 0 if none>
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
            > "data/logs/fanout_${round}_${slug}.log" 2>&1 < /dev/null ) &
        rpid=$!
        ( sleep "$RESEARCH_CAP"; kill -TERM "$rpid" 2>/dev/null ) &
        killers+=($!)
        pids+=($rpid)
    done
    for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null; done
    for k in "${killers[@]:-}"; do kill "$k" 2>/dev/null; done
    note "round ${round}: researchers done, harvesting"

    HFILE="data/logs/prompt_${round}_harvest.txt"
    cat > "$HFILE" <<EOP
You are the harvester for one parallel research round. Read CLAUDE.md first.

private/findings/ holds one file per hypothesis just tested. For each file:
1. Add a row to the "Evaluated and rejected" table in docs/sources.md carrying its
   verdict, its numbers and its method, so nobody re-tests it. Positive or negative.
2. Record the outcome on that hypothesis's block in ${HYPO} as a single
   "result: <verdict>, <figure>, <one clause why>" line.
3. If a verdict is FIND, apply THE STANDING APPROVAL RULE in CLAUDE.md. When all four
   conditions hold, write the entry into docs/approved-sources-list.md, quote the
   machine-written stamp, add "- admitted under the standing rule of 2026-08-29 (Ivo)",
   set "Decision: master", register an ingest spec if one is needed, ingest it, and
   confirm ark check still passes. If ANY condition fails, leave "Decision: pending" with
   the measurement and a "- potential:" score, and name the condition that failed.
   Never invent a new evidence class to fit a source.
3b. Keep it SHORT for small sources. Under 5,000 EE gets ONE line in docs/sources.md:
   the link, the sentence saying what dates one item, and the figure. Nothing else.
4. Then: uv run python scripts/rank_triage.py
5. Gate, never through a pipe:
   uv run ruff check . && uv run ruff format --check . && uv run pytest -q
   then uv run ark export && uv run ark check
6. Commit on the current branch. Never push. No AI attribution. No em-dashes or en-dashes.
7. Move the harvested files to private/findings/banked/ so the next round starts clean.

Be brief in the commit body: what was tested, what each measured, what the method was.
EOP
    # Backgrounded so the next round of researchers starts immediately. Only the
    # harvester touches git and docs/, and researchers touch neither, so the overlap is
    # safe and it removes the serial harvest gap from the wall clock.
    claude -p "$(cat "$HFILE")" --permission-mode auto --output-format text \
        > "data/logs/fanout_${round}_harvest.log" 2>&1 < /dev/null &
    HARVEST_PID=$!
    # One harvester at a time: wait for the PREVIOUS one before starting the next.
    if [ -n "${LAST_HARVEST:-}" ]; then wait "$LAST_HARVEST" 2>/dev/null; fi
    LAST_HARVEST="$HARVEST_PID"
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
