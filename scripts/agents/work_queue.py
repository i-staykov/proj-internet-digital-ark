"""The agent's work queue: `data/queue/agent_work.jsonl`, one item a line, under 20 KB.

What persists between runs is here, in the repo's docs and in the run ledger; a run's own
context does not. An item is an alert to fix (priority 1), an issue of the umbrella (2) or an
improvement the review filed (3), with its evidence and a resume note the run that could not
finish leaves for the next, which resumes that session once at most. Done items leave the file
after 30 days, so it stays small enough to read whole at the start of every run.

    python3 scripts/agents/work_queue.py add KIND TITLE [--evidence E] [--priority N] [--id ID]
    python3 scripts/agents/work_queue.py top [--field NAME]      the next open item, as JSON
    python3 scripts/agents/work_queue.py start ID                one more attempt
    python3 scripts/agents/work_queue.py note ID TEXT [--session S]
    python3 scripts/agents/work_queue.py done ID | park ID REASON | list

Standard library only; `ARK_AGENT_QUEUE` moves the file, for the tests.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

QUEUE = Path(os.environ.get("ARK_AGENT_QUEUE", "data/queue/agent_work.jsonl"))
PRIORITY = {"alert": 1, "issue": 2, "improvement": 3}
KEEP_DONE_DAYS = 30
MAX_BYTES = 20_000


def now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%MZ")


def load() -> list[dict]:
    try:
        lines = QUEUE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    items = []
    for ln in lines:
        try:
            items.append(json.loads(ln))
        except ValueError:
            continue
    return items


def save(items: list[dict]) -> None:
    cutoff = (dt.datetime.now(dt.UTC) - dt.timedelta(days=KEEP_DONE_DAYS)).strftime(
        "%Y-%m-%dT%H:%MZ"
    )
    items = [i for i in items if not (i.get("state") == "done" and i.get("updated", "") < cutoff)]
    text = "".join(json.dumps(i, sort_keys=True) + "\n" for i in items)
    while len(text.encode()) > MAX_BYTES and any(i.get("state") == "done" for i in items):
        items.remove(next(i for i in items if i.get("state") == "done"))
        text = "".join(json.dumps(i, sort_keys=True) + "\n" for i in items)
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE.write_text(text, encoding="utf-8")


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]


def find(items: list[dict], item_id: str) -> dict:
    for i in items:
        if i["id"] == item_id:
            return i
    raise SystemExit(f"no item {item_id}")


def add(a) -> None:
    items = load()
    item_id = a.id or f"{a.kind}-{slug(a.title)}"
    if any(i["id"] == item_id and i.get("state") == "open" for i in items):
        print(f"open already: {item_id}")
        return
    items.append(
        {
            "id": item_id,
            "kind": a.kind,
            "priority": a.priority or PRIORITY[a.kind],
            "title": a.title,
            "evidence": a.evidence or "",
            "note": "",
            "session": "",
            "attempts": 0,
            "state": "open",
            "created": now(),
            "updated": now(),
        }
    )
    save(items)
    print(item_id)


def top(items: list[dict]) -> dict | None:
    open_items = [i for i in items if i.get("state") == "open"]
    return (
        min(open_items, key=lambda i: (i.get("priority", 9), i.get("created", "")))
        if open_items
        else None
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("kind", choices=sorted(PRIORITY))
    p.add_argument("title")
    p.add_argument("--evidence", default="")
    p.add_argument("--priority", type=int)
    p.add_argument("--id")
    sub.add_parser("top").add_argument("--field")
    sub.add_parser("start").add_argument("id")
    p = sub.add_parser("note")
    p.add_argument("id")
    p.add_argument("text")
    p.add_argument("--session", default="")
    sub.add_parser("done").add_argument("id")
    p = sub.add_parser("park")
    p.add_argument("id")
    p.add_argument("reason")
    sub.add_parser("list")
    a = ap.parse_args(argv)
    if a.cmd == "add":
        add(a)
        return 0
    items = load()
    if a.cmd == "top":
        item = top(items)
        if item is None:
            return 1
        print(item.get(a.field, "") if a.field else json.dumps(item))
        return 0
    if a.cmd == "list":
        for i in items:
            print(f"{i['state']:6} p{i.get('priority')} {i['attempts']}x {i['id']}: {i['title']}")
        return 0
    item = find(items, a.id)
    if a.cmd == "start":
        item["attempts"] = item.get("attempts", 0) + 1
    elif a.cmd == "note":
        item["note"], item["session"] = a.text[:2000], a.session
    elif a.cmd == "done":
        item["state"] = "done"
    elif a.cmd == "park":
        item["state"], item["note"] = "parked", a.reason[:2000]
    item["updated"] = now()
    save(items)
    return 0


if __name__ == "__main__":
    sys.exit(main())
