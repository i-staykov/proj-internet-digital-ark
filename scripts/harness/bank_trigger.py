"""Say whether `just bank` has anything to do, and remember what it last banked.

The hourly tick opens no store and calls the bank only when `check` exits 0. Five things
count as arrived: a confirmed FIND in the drained findings (the ones `fleet_findings.py
reprice` prices) or a whole read's `read.json` there, a changed approvals page, a new
baseline marker, the fold globs moved in count, bytes or newest mtime, or an approved journal
the last bank could not find or fetch. Journals land all day, so a move or a retry alone
waits until the last bank is ARK_BANK_JOURNAL_HOURS old (default 3). When the bank runs for
another reason it folds them anyway, because the stamp it writes afterwards records them as
seen.

A red bank writes `data/logs/bank_red.json`, and nothing banks until someone reads it and runs
`clear`. Stdlib only, so the tick never imports `ark`.

    uv run python scripts/harness/bank_trigger.py check [--find]   exit 0 names why, 1 nothing
    uv run python scripts/harness/bank_trigger.py stamp            after a green bank
    uv run python scripts/harness/bank_trigger.py red --step b|c [--ingested ..] [--failed ..] \\
        [--check FILE]
    uv run python scripts/harness/bank_trigger.py clear            by hand, after the red is read
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INCOMING = "data/fleet_findings/incoming"
APPROVALS = "docs/registers/approved-sources-list.md"
BASELINE = "data/baseline.json"
STAMP = "data/logs/bank_stamp.json"
RED = "data/logs/bank_red.json"
# Written by the bank while an approved journal is absent or its refetch failed; paced like
# the journals.
RETRY = "data/logs/bank_approvals_retry"
# What the bank's journal step reads, as its readers glob it. A new ingest line in the bank
# adds its glob here in the same commit, or its journals wait for an unrelated trigger.
FOLD = (
    "data/raw/usenet/*.mbox.zip",
    "data/raw/usenet/usenet_dated_*.jsonl.gz",
    "data/raw/usenet/usenet_candidates_*.jsonl.gz",
    "data/raw/cdx/*.jsonl.gz.part",
    "data/raw/rdap/*.jsonl.gz.part",
    "data/raw/cdx/cdx_*.jsonl.gz",
    "data/raw/cdx_gap_hostgrain/*.jsonl.gz",
    "data/raw/cdx_suffix/*.jsonl.gz",
    "data/raw/usenet_*_items/*.jsonl.gz",
    "data/raw/usenet_*_items/*.jsonl",
    "data/raw/maillists_items/*.jsonl.gz",
    "data/raw/maillists_items/*.jsonl",
    "data/raw/enron_items/*.jsonl.gz",
    "data/raw/enron_items/*.jsonl",
    "data/raw/rdap/rdap_*.jsonl.gz",
)
CHECK_TAIL = 40


def _json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def confirmed_finds(root: Path = ROOT) -> list[str]:
    """Lead directories whose FIND its verify lane confirmed: exactly what reprice prices."""
    incoming = root / INCOMING
    if not incoming.is_dir():
        return []
    out = []
    for lead in sorted(incoming.iterdir()):
        finding = _json(lead / "finding.json")
        if finding.get("verdict") != "FIND":
            continue
        if (finding.get("verify") or {}).get("status") == "confirmed":
            out.append(lead.name)
    return out


def drained_reads(root: Path = ROOT) -> list[str]:
    """Lead directories the drain brought in with a whole read's `read.json`."""
    incoming = root / INCOMING
    if not incoming.is_dir():
        return []
    return [lead.name for lead in sorted(incoming.iterdir()) if (lead / "read.json").is_file()]


def approvals_sha(root: Path = ROOT) -> str | None:
    try:
        return hashlib.sha256((root / APPROVALS).read_bytes()).hexdigest()
    except OSError:
        return None


def marker(root: Path = ROOT) -> str | None:
    return (_json(root / BASELINE).get("current") or {}).get("marker")


def fold_digest(root: Path = ROOT) -> dict[str, list[int]]:
    """Per FOLD glob: file count, total bytes, newest mtime in ns."""
    digest = {}
    for pattern in FOLD:
        count = size = newest = 0
        for rel in glob.glob(pattern, root_dir=root):
            try:
                st = os.stat(root / rel)
            except OSError:  # renamed between the glob and the stat
                continue
            count += 1
            size += st.st_size
            newest = max(newest, st.st_mtime_ns)
        digest[pattern] = [count, size, newest]
    return digest


def journal_hours() -> float:
    raw = os.environ.get("ARK_BANK_JOURNAL_HOURS", "3")
    try:
        return float(raw)
    except ValueError:
        raise SystemExit(f"bank: ARK_BANK_JOURNAL_HOURS={raw!r} is not a number of hours") from None


def check(root: Path = ROOT, find_only: bool = False) -> tuple[int, str]:
    """The exit code and the lines naming why the bank should run, or why not."""
    finds = confirmed_finds(root)
    reasons = [f"bank: find {', '.join(finds)}"] if finds else []
    if find_only:
        return (0, reasons[0]) if finds else (1, "")
    if (root / RED).exists():
        doc = _json(root / RED)
        return 1, (
            f"bank: BANK RED since {doc.get('at', 'unknown')}, step {doc.get('step', 'unknown')}: "
            f"read {RED}, then bank_trigger.py clear"
        )

    reads = drained_reads(root)
    if reads:
        reasons.append(f"bank: read {', '.join(reads)}")
    # No stamp means no bank has run on this machine yet, so every reason fires.
    seen = _json(root / STAMP)
    if not seen or approvals_sha(root) != seen.get("approvals_sha256"):
        reasons.append("bank: approvals changed")
    current = marker(root)
    if not seen or current != seen.get("marker"):
        reasons.append(f"bank: baseline {current}")

    moved = []
    if (root / RETRY).exists():
        moved.append("bank: approvals not yet banked, retried")
    if not seen:
        moved.append("bank: journals, no stamp yet")
    else:
        before = seen.get("fold") or {}
        for pattern, cur in fold_digest(root).items():
            was = before.get(pattern) or [0, 0, 0]
            if cur != was:
                files, size = cur[0] - was[0], cur[1] - was[1]
                moved.append(f"bank: journals {pattern} ({files:+,} files, {size:+,} bytes)")
    if moved:
        try:
            last = datetime.fromisoformat(seen["at"])
        except (KeyError, TypeError, ValueError):
            last = None
        due = last + timedelta(hours=journal_hours()) if last else None
        if reasons or due is None or datetime.now(UTC) >= due:
            reasons += moved
        else:
            what = "journals moved" if moved[-1].startswith("bank: journals") else "a retry"
            return 1, f"bank: {what}, held until {due:%H:%MZ}"
    if reasons:
        return 0, "\n".join(reasons)
    return 1, "bank: nothing arrived"


def stamp(root: Path = ROOT) -> dict:
    """What the bank has seen. Measured after its journal step, so its own output never counts."""
    doc = {
        "at": _now(),
        "approvals_sha256": approvals_sha(root),
        "marker": marker(root),
        "fold": fold_digest(root),
    }
    _write(root / STAMP, doc)
    return doc


def red(
    root: Path = ROOT,
    step: str = "c",
    ingested: str = "",
    failed: str = "",
    check_log: Path | None = None,
) -> dict:
    """Record a red bank. The stamp is left alone, so what arrived still counts after `clear`."""
    tail: list[str] = []
    if check_log is not None:
        try:
            tail = check_log.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            pass
    doc = {
        "at": _now(),
        "step": step,
        "ingested": ingested.split(),
        "failed": failed.split(),
        "check": tail[-CHECK_TAIL:],
    }
    _write(root / RED, doc)
    return doc


def clear(root: Path = ROOT) -> str:
    path = root / RED
    if not path.exists():
        return "bank: nothing to clear"
    doc = _json(path)
    lines = [
        f"bank: cleared the red of {doc.get('at', 'unknown')}, step {doc.get('step', 'unknown')}",
        f"  ingested: {' '.join(doc.get('ingested') or []) or 'nothing'}",
        f"  failed: {' '.join(doc.get('failed') or []) or 'nothing'}",
        *(f"  | {line}" for line in doc.get("check") or []),
    ]
    path.unlink()
    return "\n".join(lines)


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ck = sub.add_parser("check", help="exit 0 naming why the bank should run, else 1")
    ck.add_argument("--find", action="store_true", help="only a confirmed FIND, ignoring a red")
    sub.add_parser("stamp", help="record what a green bank has seen")
    rd = sub.add_parser("red", help="stop the bank until clear")
    rd.add_argument("--step", choices=("b", "c"), required=True)
    rd.add_argument("--ingested", default="", help="spec keys, space separated")
    rd.add_argument("--failed", default="", help="failed steps, space separated")
    rd.add_argument("--check", type=Path, help="the ark check log; its tail is kept")
    sub.add_parser("clear", help="print the red and lift it")
    args = ap.parse_args(argv)

    if args.cmd == "check":
        code, text = check(root, find_only=args.find)
        if text:
            print(text)
        return code
    if args.cmd == "stamp":
        print(f"bank: stamped at {stamp(root)['at']}")
    elif args.cmd == "red":
        red(root, args.step, args.ingested, args.failed, args.check)
        print(f"bank: red at step {args.step}, recorded in {RED}")
    else:
        print(clear(root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
