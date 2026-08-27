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
PAR="${2:-4}"
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

    # Open hypotheses: a `## slug | title` heading whose block has no `result:` line yet.
    SLUGS=""
    while IFS= read -r slug; do
        [ -n "$slug" ] && SLUGS="$SLUGS $slug"
    done < <(uv run python scripts/pick_hypotheses.py "$HYPO" "$PAR" 2>/dev/null)
    SLUGS="${SLUGS# }"
    if [ -z "$SLUGS" ]; then
        note "no open hypotheses left in ${HYPO}. Stopping so a human can add more."
        break
    fi
    started=$(date -u '+%F %T'); before=$(ee_now); before="${before:-0}"
    note "round ${round}: ${left}s left, launching: ${SLUGS}"

    pids=()
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
        ( claude -p "$(cat "$PFILE")" --permission-mode auto --output-format text \
            > "data/logs/fanout_${round}_${slug}.log" 2>&1 < /dev/null ) &
        pids+=($!)
    done
    for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null; done
    note "round ${round}: researchers done, harvesting"

    HFILE="data/logs/prompt_${round}_harvest.txt"
    cat > "$HFILE" <<EOP
You are the harvester for one parallel research round. Read CLAUDE.md first.

private/findings/ holds one file per hypothesis just tested. For each file:
1. Add a row to the "Evaluated and rejected" table in docs/sources.md carrying its
   verdict, its numbers and its method, so nobody re-tests it. Positive or negative.
2. Record the outcome on that hypothesis's block in ${HYPO} as a single
   "result: <verdict>, <figure>, <one clause why>" line.
3. If a verdict is FIND and the class is master-eligible, write an approval request into
   docs/approved-sources-list.md with the measurement and a "- potential:" score, and
   leave "Decision: pending". Do NOT ingest it.
4. Then: uv run python scripts/rank_triage.py
5. Gate, never through a pipe:
   uv run ruff check . && uv run ruff format --check . && uv run pytest -q
   then uv run ark export && uv run ark check
6. Commit on the current branch. Never push. No AI attribution. No em-dashes or en-dashes.
7. Move the harvested files to private/findings/banked/ so the next round starts clean.

Be brief in the commit body: what was tested, what each measured, what the method was.
EOP
    claude -p "$(cat "$HFILE")" --permission-mode auto --output-format text \
        > "data/logs/fanout_${round}_harvest.log" 2>&1 < /dev/null
    after=$(ee_now); after="${after:-$before}"
    delta=$(python3 -c "print(f'{float('${after}') - float('${before}'):.4f}')" 2>/dev/null || echo 0)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$round" "$started" "$(date -u '+%F %T')" "$SLUGS" "$before" "$after" "$delta" >> "$LEDGER"
    note "round ${round} banked: EE delta ${delta}"
done
note "fanout finished after ${round} rounds"
