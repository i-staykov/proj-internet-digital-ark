#!/usr/bin/env bash
# Drive the agent to an absolute deadline from OUTSIDE the agent.
#
# **Why this exists, measured on 2026-08-27.** A `/goal` stop hook kept the session
# alive for nine hours and the session still produced an idle hour: last commit 11:42,
# next real work 12:46. Three causes, and none of them is willpower.
#
# 1. **A stop hook is reactive.** It fires only when the agent tries to STOP, so it
#    cannot distinguish an hour of work from an hour of `sleep`. Between firings the
#    agent chooses its own next action, and a tiring agent chooses cheap actions.
# 2. **One long context degrades.** As the window fills the agent starts rationing it,
#    and rationing looks exactly like idling: short status checks instead of work. The
#    agent that decides how hard to work is the same agent that is running out of room
#    to think, which is the wrong incentive to leave in one place.
# 3. **No externalised work queue.** Re-deciding the next task from memory every turn
#    is expensive and drifts toward whatever was most recently in context.
#
# So the loop moves out of the agent and into this script, which is exactly the pattern
# the collection engines already use and the reason THEY never idle: an absolute epoch
# deadline, a progress marker on disk, and a journal per batch. The agent gets the same
# treatment it gives its own collectors.
#
# Each iteration is a FRESH `claude -p` process. Fresh context per iteration is the
# whole point: it cannot degrade, cannot ration, and cannot remember that it was tired.
# State passes between iterations only through files that already exist for that purpose
# (`docs/sources.md`, `docs/approved-sources-list.md`, `docs/ROUND.md`) plus this
# script's own ledger.
#
# **The ledger is the part that would have caught today.** Every iteration records the
# net-new equivalent-English before and after. An iteration that moves 0 EE and writes
# no commit is a no-op, is logged as one, and is counted; three in a row is a signal to
# a human that the queue is empty rather than that the agent is lazy.
#
#     bash scripts/agent_loop.sh <deadline_epoch> [task_file]
#     bash scripts/agent_loop.sh $(date -j -f '%Y-%m-%d %H:%M:%S' '2026-08-27 18:00:00' +%s)
#
# Stop it with `pkill -f agent_loo[p].sh`; the iteration in flight finishes first.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:?usage: agent_loop.sh <deadline_epoch> [task_file]}"
TASKS="${2:-private/agent-tasks.md}"
LOG="data/logs/agent_loop.log"
LEDGER="data/logs/agent_loop.tsv"
mkdir -p data/logs
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

# One instance only. Two agents editing the same docs is worse than none.
LOCK="data/logs/agent_loop.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    holder=$(cat "$LOCK/pid" 2>/dev/null || echo unknown)
    if [ "$holder" != unknown ] && kill -0 "$holder" 2>/dev/null; then
        echo "already running as pid $holder" >&2; exit 1
    fi
    rm -rf "$LOCK" && mkdir "$LOCK" || exit 1
fi
printf '%s\n' "$$" > "$LOCK/pid"
trap 'rm -rf "$LOCK"; note "loop exit"' EXIT

ee_now() {
    uv run python scripts/round_figures.py 2>/dev/null \
        | sed -n 's/^4\. Equivalent-English increment *: *//p' | tr -d ', ' | head -1
}

[ -f "$LEDGER" ] || printf 'started\tended\titer\tee_before\tee_after\tdelta\tcommits\tverdict\n' > "$LEDGER"
note "start: until $(date -r "$DEADLINE" '+%F %T' 2>/dev/null || echo "$DEADLINE"), tasks=$TASKS"

iter=0
noops=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    iter=$((iter + 1))
    left=$(( DEADLINE - $(date +%s) ))
    started=$(date -u '+%F %T')
    before=$(ee_now); before="${before:-0}"
    head_before=$(git rev-parse --short HEAD)
    note "iteration ${iter}: ${left}s left, EE ${before}"

    # The prompt is rebuilt every iteration so it always carries the CURRENT deadline and
    # the CURRENT state. It names ONE deliverable, because an iteration asked for two
    # produces neither.
    PROMPT=$(cat <<EOP
You are one iteration of an unattended loop with ${left} seconds left before its
absolute deadline. This is NOT a conversation and nobody will read a status update.

Read CLAUDE.md first. It is binding.

Do exactly one thing this iteration, and finish it:
1. Read ${TASKS} and pick the highest-value task that is not marked done.
2. Do it. If it is a hunt, grep docs/sources.md FIRST so you do not re-test a closed
   family, and price it against the store before proposing anything.
3. Log the outcome in docs/sources.md whether it paid or not, positive or negative.
4. Mark the task done in ${TASKS}, appending the measured figure.
5. Gate and commit on the current branch:
   uv run ruff check . && uv run ruff format --check . && uv run pytest -q
   then uv run ark export && uv run ark check
   Never push. No AI attribution. No em-dashes or en-dashes.

Quote net-new post-split equivalent-English against merged260827, never gross.
Never ingest a class without a human Decision: line in docs/approved-sources-list.md.
Do not sleep, do not poll, do not write a progress report. If a task is blocked, say so
in ${TASKS} in one line and move to the next one.
EOP
)
    # `< /dev/null` is mandatory, not tidiness: without it `claude -p` waits 3s for
    # stdin, warns, and on this version then fails with a bare "Execution error".
    # Found by dry-running this script rather than by reading the flag list.
    claude -p "$PROMPT" --permission-mode auto --output-format text \
        >> "data/logs/agent_iter_${iter}.log" 2>&1 < /dev/null
    rc=$?
    if [ "$rc" -ne 0 ]; then
        note "iteration ${iter}: claude exited ${rc}, see data/logs/agent_iter_${iter}.log"
    fi

    after=$(ee_now); after="${after:-$before}"
    head_after=$(git rev-parse --short HEAD)
    commits=$(git rev-list --count "${head_before}..${head_after}" 2>/dev/null || echo 0)
    delta=$(python3 -c "print(f'{float('${after}') - float('${before}'):.4f}')" 2>/dev/null || echo 0)
    verdict=worked
    if [ "$commits" = "0" ] && python3 -c "import sys; sys.exit(0 if abs(float('${delta}')) < 0.01 else 1)"; then
        verdict=NOOP; noops=$((noops + 1))
    else
        noops=0
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$started" "$(date -u '+%F %T')" "$iter" "$before" "$after" "$delta" "$commits" "$verdict" \
        >> "$LEDGER"
    note "iteration ${iter} ${verdict}: rc=${rc} commits=${commits} EE delta=${delta}"

    if [ "$noops" -ge 3 ]; then
        note "THREE NO-OP ITERATIONS IN A ROW: the task file is empty or every task is blocked."
        note "Not a reason to spin. Stopping so a human sees it."
        exit 0
    fi
done
note "deadline reached after ${iter} iterations"
