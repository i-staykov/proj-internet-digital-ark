"""One row per agent run in `data/logs/agent_runs.tsv`, read off the run's stream-json.

The ledger is what the heartbeat, the pacer and a person read about the agent; the stream
is kept beside it only as a noticeboard. A row carries the stamp, the mode, the model, the
turns, the tokens in (prompt, cache writes and cache reads) and out, the estimated cost, the
account's five-hour and seven-day window percent, the seconds and the outcome. The windows
come from the stream's `rate_limit_event` lines, merged per window so the row carries the
latest reading of each: the pre-flight stream's, then the run's own. A run past the mode's
`--max-tokens` cap gets `:over-cap` on its outcome, since no `claude -p` flag caps tokens. A
run killed
mid-write can end a stream inside a character; one bad line never loses the rest.

    python3 scripts/agents/agent_ledger.py row LEDGER --stamp S --mode M --model X \\
        --seconds N --outcome O [--stream RUN.jsonl] [--windows PREFLIGHT.jsonl]
    python3 scripts/agents/agent_ledger.py ok STREAM        exit 0 when its result succeeded
    python3 scripts/agents/agent_ledger.py subtype STREAM   the result's subtype, or none
    python3 scripts/agents/agent_ledger.py last LEDGER      the last row as JSON

Standard library only: the timer's shell calls it with the system python.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

COLUMNS = (
    "stamp",
    "mode",
    "model",
    "turns",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "five_hour_pct",
    "seven_day_pct",
    "seconds",
    "outcome",
)
IN_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def events(path: str | None):
    if not path:
        return
    try:
        lines = open(path, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return
    for line in lines:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if isinstance(d, dict):
            yield d


def windows(path: str | None) -> dict:
    raw: dict = {}
    for d in events(path):
        if d.get("type") == "rate_limit_event":
            info = d.get("rate_limit_info")
            w = info.get("unifiedWindows") if isinstance(info, dict) else None
            if isinstance(w, dict):
                raw.update(w)
    return raw


def pct(raw: dict, name: str) -> float:
    w = raw.get(name)
    return round(((w.get("utilization") if isinstance(w, dict) else None) or 0) * 100, 1)


def result(path: str | None) -> dict:
    """The stream's `result` event, or {}."""
    for d in events(path):
        if d.get("type") == "result":
            return d
    return {}


def usage(path: str | None) -> tuple[int, int, int, float]:
    """(turns, tokens in, tokens out, cost) from the result event, or from the messages."""
    r = result(path)
    u = r.get("usage") if isinstance(r.get("usage"), dict) else None
    if u is None:
        u = {}
        for d in events(path):
            msg = d.get("message")
            mu = msg.get("usage") if isinstance(msg, dict) else None
            if isinstance(mu, dict):
                for k, v in mu.items():
                    if isinstance(v, int):
                        u[k] = u.get(k, 0) + v
    tokens_in = sum(u.get(f) or 0 for f in IN_FIELDS)
    return (
        int(r.get("num_turns") or 0),
        tokens_in,
        int(u.get("output_tokens") or 0),
        float(r.get("total_cost_usd") or 0),
    )


def row(a) -> None:
    turns, tin, tout, cost = usage(a.stream)
    raw = windows(a.windows) | windows(a.stream)  # the run's own later readings win
    outcome = a.outcome + (":over-cap" if a.max_tokens and tin + tout > a.max_tokens else "")
    values = (
        a.stamp,
        a.mode,
        a.model,
        turns,
        tin,
        tout,
        f"{cost:.4f}",
        pct(raw, "five_hour"),
        pct(raw, "seven_day"),
        a.seconds,
        outcome,
    )
    path = Path(a.ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with open(path, "a", encoding="utf-8") as fh:
        if new:
            fh.write("\t".join(COLUMNS) + "\n")
        fh.write("\t".join(str(v).replace("\t", " ") for v in values) + "\n")


def last(ledger: str) -> dict:
    try:
        lines = Path(ledger).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}
    rows = [ln for ln in lines[1:] if ln.strip()]
    return dict(zip(COLUMNS, rows[-1].split("\t"), strict=False)) if rows else {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("row")
    r.add_argument("ledger")
    for k in ("stamp", "mode", "model", "outcome"):
        r.add_argument(f"--{k}", required=True)
    r.add_argument("--seconds", type=int, required=True)
    r.add_argument("--stream")
    r.add_argument("--windows")
    r.add_argument(
        "--max-tokens", type=int, default=0, help="the mode's cap; over it, the outcome says so"
    )
    sub.add_parser("ok").add_argument("stream")
    sub.add_parser("subtype").add_argument("stream")
    sub.add_parser("last").add_argument("ledger")
    a = ap.parse_args(argv)
    if a.cmd == "row":
        row(a)
    elif a.cmd == "ok":
        res = result(a.stream)
        return 0 if res.get("subtype") == "success" and not res.get("is_error") else 1
    elif a.cmd == "subtype":
        print(result(a.stream).get("subtype") or "none")
    else:
        print(json.dumps(last(a.ledger)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
