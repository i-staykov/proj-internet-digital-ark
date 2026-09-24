"""The tick calls the bank only when something arrived, and a red bank stays red until cleared."""

from __future__ import annotations

import fnmatch
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "bank_trigger", ROOT / "scripts/harness/bank_trigger.py"
)
bt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bt)


def _tree(root: Path) -> Path:
    """A repo with an approvals page, a baseline marker and one folded journal, then stamped."""
    (root / "docs/registers").mkdir(parents=True)
    (root / bt.APPROVALS).write_text("### a / cdx_snapshot\nDecision: master\n")
    (root / "data/raw/cdx").mkdir(parents=True)
    (root / bt.BASELINE).write_text(json.dumps({"current": {"marker": "merged260922"}}))
    (root / "data/raw/cdx/cdx_a.jsonl.gz").write_bytes(b"one")
    bt.stamp(root)
    return root


def _finding(root: Path, slug: str, status: str) -> None:
    lead = root / bt.INCOMING / slug
    lead.mkdir(parents=True)
    doc = {"slug": slug, "verdict": "FIND", "verify": {"status": status}}
    (lead / "finding.json").write_text(json.dumps(doc))


def test_an_unchanged_tree_is_nothing_arrived(tmp_path):
    assert bt.check(_tree(tmp_path)) == (1, "bank: nothing arrived")


def test_a_new_journal_waits_out_the_window_unless_the_bank_runs_anyway(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    (root / "data/raw/cdx/cdx_b.jsonl.gz").write_bytes(b"two!")
    monkeypatch.delenv("ARK_BANK_JOURNAL_HOURS", raising=False)
    code, text = bt.check(root)
    assert code == 1 and text.startswith("bank: journals moved, held until ")

    # A bank that runs for another reason folds them, or its stamp would swallow them.
    (root / bt.APPROVALS).write_text("### a / cdx_snapshot\nDecision: master\n\n### b\n")
    code, text = bt.check(root)
    assert code == 0 and "bank: journals data/raw/cdx/cdx_*.jsonl.gz (+1 files, +4 bytes)" in text

    bt.stamp(root)
    (root / "data/raw/cdx/cdx_c.jsonl.gz").write_bytes(b"3")
    monkeypatch.setenv("ARK_BANK_JOURNAL_HOURS", "0")
    assert bt.check(root) == (0, "bank: journals data/raw/cdx/cdx_*.jsonl.gz (+1 files, +1 bytes)")


def test_an_edited_approvals_page_is_a_reason(tmp_path):
    root = _tree(tmp_path)
    with (root / bt.APPROVALS).open("a") as page:
        page.write("\n### b / rdap_snapshot\nDecision: master\n")
    assert bt.check(root) == (0, "bank: approvals changed")


def test_only_a_confirmed_find_is_a_reason(tmp_path):
    root = _tree(tmp_path)
    _finding(root, "pending-lead", "pending")
    assert bt.check(root) == (1, "bank: nothing arrived")
    assert bt.check(root, find_only=True) == (1, "")

    _finding(root, "good-lead", "confirmed")
    assert bt.check(root) == (0, "bank: find good-lead")
    assert bt.check(root, find_only=True) == (0, "bank: find good-lead")


def test_a_red_bank_blocks_every_reason_until_cleared(tmp_path, capsys):
    root = _tree(tmp_path)
    _finding(root, "good-lead", "confirmed")
    stamp_before = (root / bt.STAMP).read_bytes()
    log = tmp_path / "check.log"
    log.write_text("".join(f"line {n}\n" for n in range(60)))

    argv = ["red", "--step", "b", "--ingested", "k1 k2", "--check", str(log)]
    assert bt.main(argv, root=root) == 0
    red = json.loads((root / bt.RED).read_text())
    assert red["ingested"] == ["k1", "k2"] and len(red["check"]) == 40
    assert (root / bt.STAMP).read_bytes() == stamp_before

    code, text = bt.check(root)
    assert code == 1 and text.startswith("bank: BANK RED since ") and "step b" in text
    # The tick still splits its findings branch while the bank is red.
    assert bt.check(root, find_only=True) == (0, "bank: find good-lead")

    capsys.readouterr()
    assert bt.main(["clear"], root=root) == 0
    assert "step b" in capsys.readouterr().out and not (root / bt.RED).exists()
    assert bt.check(root) == (0, "bank: find good-lead")
    assert bt.clear(root) == "bank: nothing to clear"


def test_fold_covers_every_glob_the_bank_ingests():
    """A journal whose glob FOLD misses is folded only when something unrelated triggers."""
    recipe = re.search(
        r"^bank\b[^\n]*:\n((?:[ \t][^\n]*\n|\n)*)",
        (ROOT / "justfile").read_text(encoding="utf-8"),
        re.M,
    )
    assert recipe, "the justfile has no bank recipe"
    texts = [recipe.group(1)]

    # A directory is read with its reader's globs, and these readers take plain `.jsonl` too.
    both = ("ingest-usenet-hostnames", "ingest-maillist-hostnames", "ingest-enron-hostnames")
    checked, missed = [], []
    for text in texts:
        loops = dict(re.findall(r"\bfor (\w+) in ([^\s;]+)", text))
        for cmd, args in re.findall(
            r"(?:uv run ark (ingest\S*)|^\s*ingest_all)\s+(.*)", text, re.M
        ):
            for word in args.split():
                word = word.strip("\"'")
                word = loops.get(word.lstrip("$").strip("{}"), word).rstrip("/")
                if not word.startswith("data/raw/"):
                    continue
                exts = (".jsonl.gz", ".jsonl") if cmd in both else (".jsonl.gz",)
                is_dir = "." not in word.rsplit("/", 1)[-1]
                checked.append(word)
                for sample in [f"{word}/x{e}" for e in exts] if is_dir else [word]:
                    sample = sample.replace("*", "x")
                    if not any(fnmatch.fnmatchcase(sample, glob) for glob in bt.FOLD):
                        missed.append(sample)
    assert checked, "no ingest line names a data/raw path"
    assert not missed, f"FOLD misses what the bank ingests: {missed}"
