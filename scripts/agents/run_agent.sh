#!/usr/bin/env bash
# One run of the resident agent: `ark-agent.timer` calls it at :38 every hour as `auto`,
# `just agent <mode>` runs one by hand. Each run is a fresh `claude -p` on the mode's prompt
# (`agent/prompts/common.md` then `<mode>.md`) inside the mode's caps (`agent/policy.json`), and ends as one
# row of `data/logs/agent_runs.tsv` whatever happened, so the heartbeat reads the ledger and
# never the stream.
#
# Before any model call: the tick's hold holds this too (`hold.sh holds ark-sync.timer`); one
# run at a time under a lock; the OAuth token in `~/.config/ark/agent.env` is the only
# credential the run inherits (every other ANTHROPIC_* and CLAUDE_* variable is dropped, and
# `billing_guard.py` refuses a settings file that could bill another); a pre-flight call with
# no tools proves the token answers and reads the account's windows, which the row carries and
# `pacer.py` judges: at the five-hour stop, over the seven-day pace line or inside a back-off
# the run ends as a `paced` row, no model call.
# A work run takes the queue's top item (`work_queue.py`), one attempt; parked after three. A
# run that hit its cap keeps its session on the item, and the next work run resumes it once,
# then starts fresh from the item's note.
# A failed step is a row with its reason, not a silent hour. The token is in the environment
# of every child the run spawns, so the rails (#521) refuse printing it, and the streams stay
# under data/, unshipped.
#
# Usage: bash scripts/agents/run_agent.sh [auto|triage|work|review|hunt]
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
MODE="${1:-auto}"
# `auto`, the timer's: work when the queue holds an item and the last run was not work (the
# umbrella's next open issue is queued when it is empty), else triage; the review and the hunt
# take their hours with their own issues.
UMBRELLA="${ARK_AGENT_UMBRELLA:-517}"
if [ "$MODE" = auto ]; then
    MODE=triage
    python3 scripts/agents/work_queue.py top > /dev/null 2>&1 \
        || python3 scripts/agents/work_queue.py queue-umbrella "$UMBRELLA" > /dev/null 2>&1 || true
    if python3 scripts/agents/work_queue.py top > /dev/null 2>&1 \
        && [ "$(python3 scripts/agents/agent_ledger.py last "${ARK_AGENT_LEDGER:-data/logs/agent_runs.tsv}" \
            | python3 -c "import json,sys; print(json.load(sys.stdin).get('mode',''))")" != work ]; then
        MODE=work
    fi
fi
POLICY=agent/policy.json
LEDGER="${ARK_AGENT_LEDGER:-data/logs/agent_runs.tsv}"
LOG_DIR="${ARK_AGENT_LOG_DIR:-data/logs/agent}"
STAMP=$(date -u +%Y%m%dT%H%MZ)
T0=$(date +%s)
mkdir -p "$LOG_DIR" "$(dirname "$LEDGER")"

MODEL=$(python3 -c "import json,sys; print(json.load(open('$POLICY'))['modes'][sys.argv[1]]['model'])" "$MODE" 2>/dev/null) \
    || { echo "run_agent: $POLICY has no mode $MODE" >&2; exit 2; }

MAXTOK=0
row() {  # row OUTCOME [STREAM] [WINDOWS]
    python3 scripts/agents/agent_ledger.py row "$LEDGER" --stamp "$STAMP" --mode "$MODE" \
        --model "$MODEL" --seconds $(( $(date +%s) - T0 )) --outcome "$1" --max-tokens "$MAXTOK" \
        ${2:+--stream "$2"} ${3:+--windows "$3"}
}

# A ceiling is a ceiling: TERM, then KILL $1 s later; macOS has no `timeout` and runs no agent.
bound() { if command -v timeout > /dev/null; then timeout -k "$1" "$2" "${@:3}"; else "${@:3}"; fi; }

if bash scripts/harness/hold.sh holds ark-sync.timer; then row held; exit 0; fi

# Descriptor 9 is the lock; both claude runs close it (9>&-) so no child keeps it past the run.
exec 9> "$LOG_DIR/.lock"
if command -v flock > /dev/null && ! flock -n 9; then row busy; exit 0; fi  # no flock on macOS, where no agent runs

# The token, and nothing else that Claude Code reads a credential or a provider from.
OAUTH="${CLAUDE_CODE_OAUTH_TOKEN:-}"
if [ -z "$OAUTH" ] && [ -f "$HOME/.config/ark/agent.env" ]; then
    OAUTH=$(awk -F= '/^CLAUDE_CODE_OAUTH_TOKEN=/ {print $2}' "$HOME/.config/ark/agent.env")
fi
for v in $(compgen -e); do case "$v" in ANTHROPIC_* | CLAUDE_*) unset "$v" ;; esac; done
[ -n "$OAUTH" ] || { row no-token; exit 1; }
export CLAUDE_CODE_OAUTH_TOKEN="$OAUTH"
if ! python3 -I scripts/agents/billing_guard.py --home "$HOME" --workdir "$PWD" > "$LOG_DIR/$STAMP.guard.log"; then
    row billing-guard; exit 1
fi
export PATH="$HOME/.local/bin:$PATH"
command -v claude > /dev/null || { row no-claude; exit 1; }

# The run's author, so CI and the hook can tell its commits from a session's.
export GIT_AUTHOR_NAME=ark-agent GIT_COMMITTER_NAME=ark-agent
export GIT_AUTHOR_EMAIL=ark-agent@invalid GIT_COMMITTER_EMAIL=ark-agent@invalid

[ -f "agent/prompts/$MODE.md" ] || { row no-prompt; exit 2; }
RESUME=""; ITEM=""
if [ "$MODE" = work ]; then
    ITEM=$(python3 scripts/agents/work_queue.py top --field id 2>/dev/null) || { row no-item; exit 0; }
    ATTEMPTS=$(python3 scripts/agents/work_queue.py start "$ITEM")
    if [ "$ATTEMPTS" -gt 3 ]; then
        python3 scripts/agents/work_queue.py park "$ITEM" "parked after three attempts" > /dev/null
        row "parked:$ITEM"; exit 0
    fi
    SESSION=$(python3 scripts/agents/work_queue.py top --field session)
    [ -z "$SESSION" ] || RESUME="--resume $SESSION"
fi
VARS=$(python3 - "$POLICY" "$MODE" <<'PY'
import json, shlex, sys
p = json.load(open(sys.argv[1])); m = p["modes"][sys.argv[2]]
print(f"PRE_MODEL={shlex.quote(p['preflight_model'])}")
print(f"TURNS={int(m['max_turns'])} BUDGET={float(m['max_budget_usd'])} WALL={int(m['timeout_seconds'])}")
print(f"MAXTOK={int(m['max_tokens'])} DISALLOWED={shlex.quote(p['disallowed_tools'])}")
PY
) || { row bad-policy; exit 2; }
eval "$VARS"

PRE="$LOG_DIR/$STAMP.preflight.jsonl"
# A back-off is read before any call; the windows after the pre-flight.
pace() {
    WHY=$(python3 scripts/agents/pacer.py check "$PRE" --mode "$MODE")
    local rc=$?
    [ "$rc" = 0 ] && return 0
    [ "$rc" = 3 ] || { row pacer-failed "$PRE" "$PRE"; exit 1; }
    row "paced:$WHY" "$PRE" "$PRE"; exit 0
}
pace
bound 10 120 claude -p "reply with the single word ok" --tools "" --model "$PRE_MODEL" \
    --output-format stream-json --verbose > "$PRE" 2> "$PRE.err" 9>&-
if ! python3 scripts/agents/agent_ledger.py ok "$PRE"; then
    if BACK=$(python3 scripts/agents/pacer.py backoff "$PRE") && [ -n "$BACK" ]; then
        row "rate-limited:$BACK" "$PRE" "$PRE"; exit 0
    fi
    row "preflight-failed:$(tail -c 120 "$PRE.err" | tr '\n\t' '  ')" "$PRE" "$PRE"; exit 1
fi
pace

STREAM="$LOG_DIR/$STAMP.$MODE.jsonl"
bound 60 "$WALL" claude -p "$(cat agent/prompts/common.md "agent/prompts/$MODE.md")" $RESUME --permission-mode auto \
    --model "$MODEL" --max-turns "$TURNS" --max-budget-usd "$BUDGET" \
    --disallowedTools "$DISALLOWED" --output-format stream-json --verbose \
    > "$STREAM" 2> "$STREAM.err" 9>&-
RC=$?
# The result's subtype names a cap that ended the run; the exit code alone would not; a
# refusal for the limit outranks both.
OUT=$(python3 scripts/agents/agent_ledger.py subtype "$STREAM")
case "$RC" in 124 | 137) OUT=timeout ;; *) [ "$OUT" != none ] || OUT="failed:$RC" ;; esac
if BACK=$(python3 scripts/agents/pacer.py backoff "$STREAM") && [ -n "$BACK" ]; then OUT="rate-limited:$BACK"; fi
# The session: kept once after a cap, cleared after its one resume.
if [ -n "$ITEM" ]; then
    if [ -n "$RESUME" ]; then
        python3 scripts/agents/work_queue.py session "$ITEM" ""
    else
        case "$OUT" in error_max_turns* | error_max_budget* | timeout*)
            python3 scripts/agents/work_queue.py session "$ITEM" "$(python3 scripts/agents/agent_ledger.py session "$STREAM")" ;;
        esac
    fi
fi
row "$OUT" "$STREAM" "$PRE"
# The streams are a noticeboard: the ledger is the record.
ls -t "$LOG_DIR" | tail -n +601 | sed "s|^|$LOG_DIR/|" | xargs -r rm -f
[ "$RC" = 0 ]
