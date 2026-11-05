#!/usr/bin/env bash
# One run of the resident agent: `ark-agent.timer` calls it at :38 every hour as `auto`,
# `just agent <mode>` runs one by hand. Each run is a fresh `claude -p` on the mode's prompt
# (`agent/prompts/<mode>.md`) inside the mode's caps (`agent/policy.json`), and ends as one
# row of `data/logs/agent_runs.tsv` whatever happened, so the heartbeat reads the ledger and
# never the stream.
#
# Before any model call: the tick's hold holds this too (`hold.sh holds ark-sync.timer`); one
# run at a time under a lock; the OAuth token in `~/.config/ark/agent.env` is the only
# credential the run inherits (every other ANTHROPIC_* and CLAUDE_* variable is dropped, and
# `billing_guard.py` refuses a settings file that could bill another); a pre-flight call with
# no tools proves the token answers and reads the account's windows, which the row carries.
# A failed step is a row with its reason, not a silent hour.
#
# Usage: bash scripts/agents/run_agent.sh [auto|triage|work|review|hunt]
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
MODE="${1:-auto}"
[ "$MODE" = auto ] && MODE=triage  # the clock table comes with the review and the hunt
POLICY=agent/policy.json
LEDGER="${ARK_AGENT_LEDGER:-data/logs/agent_runs.tsv}"
LOG_DIR="${ARK_AGENT_LOG_DIR:-data/logs/agent}"
STAMP=$(date -u +%Y%m%dT%H%MZ)
T0=$(date +%s)
mkdir -p "$LOG_DIR" "$(dirname "$LEDGER")"

MODEL=$(python3 -c "import json,sys; print(json.load(open('$POLICY'))['modes'][sys.argv[1]]['model'])" "$MODE" 2>/dev/null) \
    || { echo "run_agent: $POLICY has no mode $MODE" >&2; exit 2; }

row() {  # row OUTCOME [STREAM] [WINDOWS]
    python3 scripts/agents/agent_ledger.py row "$LEDGER" --stamp "$STAMP" --mode "$MODE" \
        --model "$MODEL" --seconds $(( $(date +%s) - T0 )) --outcome "$1" \
        ${2:+--stream "$2"} ${3:+--windows "$3"}
}

if bash scripts/harness/hold.sh holds ark-sync.timer; then row held; exit 0; fi

exec 9> "$LOG_DIR/.lock"
if ! flock -n 9; then row busy; exit 0; fi

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

eval "$(python3 - "$POLICY" "$MODE" <<'PY'
import json, shlex, sys
p = json.load(open(sys.argv[1])); m = p["modes"][sys.argv[2]]
print(f"PRE_MODEL={shlex.quote(p['preflight_model'])}")
print(f"TURNS={int(m['max_turns'])} BUDGET={float(m['max_budget_usd'])} WALL={int(m['timeout_seconds'])}")
print(f"DISALLOWED={shlex.quote(p['disallowed_tools'])}")
PY
)"

PRE="$LOG_DIR/$STAMP.preflight.jsonl"
timeout -k 10 120 claude -p "reply with the single word ok" --tools "" --model "$PRE_MODEL" \
    --output-format stream-json --verbose > "$PRE" 2> "$PRE.err"
if ! python3 scripts/agents/agent_ledger.py ok "$PRE"; then
    row "preflight-failed:$(tail -c 120 "$PRE.err" | tr '\n\t' '  ')" "$PRE" "$PRE"; exit 1
fi

STREAM="$LOG_DIR/$STAMP.$MODE.jsonl"
timeout -k 60 "$WALL" claude -p "$(cat "agent/prompts/$MODE.md")" --permission-mode auto \
    --model "$MODEL" --max-turns "$TURNS" --max-budget-usd "$BUDGET" \
    --disallowedTools "$DISALLOWED" --output-format stream-json --verbose \
    > "$STREAM" 2> "$STREAM.err"
RC=$?
case "$RC" in 0) OUT=$(python3 scripts/agents/agent_ledger.py subtype "$STREAM") ;; 124 | 137) OUT=timeout ;; *) OUT="failed:$RC" ;; esac
row "$OUT" "$STREAM" "$PRE"
# The streams are a noticeboard: the ledger is the record.
ls -t "$LOG_DIR" | tail -n +601 | sed "s|^|$LOG_DIR/|" | xargs -r rm -f
[ "$RC" = 0 ]
