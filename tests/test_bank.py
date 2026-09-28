"""The bank: only a `master` class banks, a red gate takes back only this bank's rows, a red bank
blocks every reason until cleared, and the preflight refuses a clone it must not write in."""

import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from functools import partial
from pathlib import Path
from unittest.mock import ANY, Mock

import duckdb
import pytest

from ark.approvals import load
from ark.baseline import CURRENT_BASELINE_MARKER
from ark.db import SCHEMA_SQL

ROOT = Path(__file__).resolve().parents[1]
RECIPE = (ROOT / "justfile").read_text(encoding="utf-8")


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/harness/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # its dataclasses resolve their annotations through sys.modules
    spec.loader.exec_module(module)
    return module


NAMES = ("bank_approved", "unbank_source", "bank_hygiene", "bank_trigger")
bank, unbank, hyg, bt = map(_module, NAMES)

# --- bank_approved: what an approval banks ----------------------------------------------

SPECS = {f"{n}_spec": Mock(source_name=f"{n}_source") for n in ("foo", "bar")}
JOURNAL, URL = "data/raw/foo/foo.jsonl.gz", "https://example.org/foo.jsonl.gz"
SPEC, JLINE, REFETCH = "ingest spec: `foo_spec`", f"journal: `{JOURNAL}`", f"refetch: {URL}"
FOO, BAR, READ = (f"{s} / cdx_timestamp" for s in ("foo_source", "bar_source", "fleet_x_hostnames"))
PARTS = [f"fleetread_bulk_cdx_file__x_000{n}.jsonl.gz" for n in (1, 2)]
TAG, READ_DIR = "fleetread_bulk_cdx_file__x_abababababab", "data/raw/fleet_read/x"
REGISTRABLES = f"data/raw/cdx/cdx_suffix_{TAG}.jsonl.gz"
READ_BLOCK = f"### {READ}\n\n- ingest: ark ingest-hostnames {READ_DIR}/\n\nDecision: master\n"
WHOIS = "fleetread_whois_dump__x_0002.jsonl.gz"


def _block(*lines: str, heading: str = FOO, decision: str = "master") -> str:
    return f"### {heading}\n\n" + "".join(f"- {s}\n" for s in lines) + f"\nDecision: {decision}\n\n"


def _approved(root: Path, *blocks: str, journal: bool = False):
    """The bank's planner, given what is banked, over the blocks the real approvals parser read."""
    text = "# approvals\n\n## Priced\n\n" + "".join(blocks)
    (root / "approved-sources-list.md").write_text(text, encoding="utf-8")
    if journal:
        (root / JOURNAL).parent.mkdir(parents=True)
        (root / JOURNAL).write_bytes(b"rows")
    approvals = load(root / "approved-sources-list.md")
    return lambda banked=(): bank.plan_bank(
        text, approvals, root=root, read=lambda _: set(banked), specs=SPECS
    )


def _outcomes(plan, root: Path) -> dict[str, list[tuple]]:
    """Every non-empty list of the plan, its paths relative to the root."""
    rel = lambda v: str(v.relative_to(root)) if isinstance(v, Path) else v  # noqa: E731
    out = {"blocked": plan.blocked, "waiting": [(r.label,) for r in plan.waiting]}
    for name in ("ready", "done", "refetch", "reads"):
        out[name] = [tuple(map(rel, row)) for row in getattr(plan, name)]
    return {name: rows for name, rows in out.items() if rows}


def _read_dir(root: Path, parts=PARTS, extra=(), complete=True) -> None:
    """A pulled read: `parts` named by its receipt, `extra` on disk beside them."""
    (root / READ_DIR).mkdir(parents=True)
    for name in [*parts, *extra]:
        (root / READ_DIR / name).write_bytes(b"rows")
    named = [{"name": name, "sha256": "cd" * 32} for name in parts]
    receipt = {"complete": complete, "journal_sha256": "ab" * 32, "parts": named}
    (root / READ_DIR / "receipt.json").write_text(json.dumps(receipt))


@pytest.mark.parametrize(
    "block,disk,banked,expected",
    [
        (_block(SPEC, JLINE), "journal", (), {"ready": [("foo_spec", JOURNAL)]}),
        (_block(SPEC, JLINE, decision="pending"), "journal", (), {"waiting": [(FOO,)]}),
        (_block(SPEC, JLINE, decision="rejected"), "journal", (), {}),
        (_block(SPEC, JLINE, REFETCH), None, (), {"refetch": [("foo_spec", URL, JOURNAL)]}),
        (_block(SPEC, JLINE, REFETCH), None, ["foo.jsonl.gz"],
         {"done": [("foo_spec", "foo.jsonl.gz")]}),
        (_block(SPEC, JLINE), None, (), (FOO, f"journal {JOURNAL} is not on this machine and the"
         " block carries no `- refetch:` line")),
        (_block(SPEC, "journal: `../../etc/passwd`", REFETCH), None, (),
         (FOO, "journal path escapes the repository: ../../etc/passwd")),
        (READ_BLOCK, {}, (), {"reads": [(READ, READ_DIR)]}),
        (READ_BLOCK, {}, PARTS, {"done": [(READ, "2 part(s) of x")]}),
        (READ_BLOCK, {}, (Path(REGISTRABLES).name, PARTS[0]), {"reads": [(READ, READ_DIR)]}),
        (READ_BLOCK, {"complete": False}, (), "no complete read"),
        (READ_BLOCK, None, (), "no complete read"),
        (READ_BLOCK, {"extra": ["fleetread_bulk_cdx_file__x_0003.jsonl.gz"]}, (),
         "a part on disk is not the receipt's, or a named part is not a part"),
        (READ_BLOCK, {"parts": [PARTS[0], "fleetread_bulk_cdx_file__y_0001.jsonl.gz"]}, (),
         "its parts are not all fleet_x_hostnames's"),
        (READ_BLOCK, {"parts": [PARTS[0], WHOIS]}, (),
         f"{WHOIS}: whois_dump is not a web method, so it dates no host"),
    ],
    ids=["master-banks", "pending-never-banks", "rejected-never-banks", "absent-is-refetched",
         "ingested-is-not-refetched", "no-bytes-no-refetch-is-blocked", "path-escapes-repo",
         "read-banks", "read-every-part-banked-is-done", "read-stopped-part-way-runs-again",
         "read-incomplete-receipt", "read-never-arrived", "read-stray-part",
         "read-another-leads-part", "read-not-a-web-method"],
)  # fmt: skip
def test_each_approved_class_plans_to_one_outcome(tmp_path, block, disk, banked, expected):
    plan = _approved(tmp_path, block, journal=disk == "journal")
    if isinstance(disk, dict):
        _read_dir(tmp_path, **disk)
    if isinstance(expected, str):
        expected = (READ, f"{expected} in {READ_DIR} on this machine")
    expected = {"blocked": [expected]} if isinstance(expected, tuple) else expected
    assert _outcomes(plan(banked), tmp_path) == expected


def test_an_absent_journal_is_reported_refetched_and_then_banked(tmp_path, capsys) -> None:
    """A block ends at a heading, keys are backticked, planning writes nothing, unbanked is loud."""
    bar = _block("ingest spec: `bar_spec`", "journal: `data/raw/bar/bar.gz`", heading=BAR)
    foo = _block("ingest spec: `foo_spec`, reading `*dn:` and nothing else", JLINE, REFETCH)
    plan_of = _approved(tmp_path, bar, foo)
    tree = lambda: {p: p.is_file() and p.read_bytes() for p in tmp_path.rglob("*")}  # noqa: E731
    before, plan = tree(), plan_of()
    assert plan_of() == plan and tree() == before
    printed = bank.report(plan) or capsys.readouterr().out
    assert f"refetching from {URL}" in printed and f"NOT BANKED: 1\n!!   {BAR}: journal" in printed
    fetch = partial(bank.download, opener=lambda *a, **k: io.BytesIO(b"rows"))
    assert "refetched foo.jsonl.gz for foo_spec" in bank.run_refetches(plan.refetch, fetch)[0]
    assert plan_of().ready == [("foo_spec", tmp_path / JOURNAL)]


@pytest.mark.parametrize(
    "opener,said",
    [
        (lambda *a, **k: io.BytesIO(b"<!DOCTYPE html><title>Sign in</title>" + b"x" * 4000),
         "the response is a page, not the artifact"),
        (Mock(side_effect=urllib.error.HTTPError(URL, 503, "busy", {"Retry-After": "600"}, None)),
         "HTTP 503, Retry-After 600"),
    ],
    ids=["html-page", "throttled-503"],
)  # fmt: skip
def test_a_refetch_that_is_not_the_artifact_fails_and_leaves_nothing(tmp_path, opener, said):
    with pytest.raises(bank.RefetchFailed, match=re.escape(said)):
        bank.download(URL, tmp_path / "foo.jsonl.gz", opener=opener)
    assert {p.name for p in tmp_path.iterdir()} <= {"approvals.md"}  # the conftest register


def test_a_red_gate_unbanks_only_this_banks_source(tmp_path, monkeypatch, capsys) -> None:
    """Every ingest of a read names its own source, and the recipe's awk hands those names to
    the unbank. A source holding a row older than the bank is refused whole; the rest go from
    every grain, and their domain and source rows stay. Without `--write` it only counts."""
    found = re.search(r"INGESTED=\$\(awk '([^']+)' \"\$BANK_LOG\"\)", RECIPE)
    begun = re.search(r"B_START=\$\(date -u \+(\S+)\)", RECIPE)
    assert found and begun and begun.start() < RECIPE.index("bank_approved.py --write")
    assert re.search(r'unbank_source\.py \$INGESTED --write \\\s+--run-start "\$B_START"', RECIPE)
    start = subprocess.run(["date", "-u", f"+{begun.group(1)}"], capture_output=True, text=True)
    _approved(tmp_path, READ_BLOCK)
    _read_dir(tmp_path)
    ran = []

    def run(command, **_):
        if bank.CONVERTER in command:  # the converter found one exact-host registrable
            (tmp_path / REGISTRABLES).parent.mkdir(parents=True)
            (tmp_path / REGISTRABLES).write_bytes(b"{}")
        return ran.append(command) or Mock(returncode=0)

    with monkeypatch.context() as patch:
        patch.setattr(bank, "ROOT", tmp_path)
        patch.setattr(bank, "APPROVALS", tmp_path / "approved-sources-list.md")
        patch.setattr(bank, "files_read", lambda _: set())
        patch.setattr(bank.subprocess, "run", run)
        patch.setattr(sys, "argv", ["bank_approved.py", "--write"])
        bank.main()
    log = capsys.readouterr().out + "== uv run ark ingest cdx_snapshot data/raw/cdx/a.jsonl.gz\n"
    glob, ingest = f"{READ_DIR}/{bank.READ_PARTS}", "uv run ark ingest fleet_x_hostnames".split()
    assert ran[0][3:] == [bank.CONVERTER, "--glob", glob, "--tag", TAG, "--state", ANY]
    assert ran[1:] == [[*ingest, REGISTRABLES], [*ingest, *(f"{READ_DIR}/{p}" for p in PARTS)]]
    awk = subprocess.run(["awk", found.group(1)], input=log, capture_output=True, text=True)
    assert awk.stdout.split() == ["fleet_x_hostnames", "fleet_x_hostnames", "cdx_snapshot"]
    with duckdb.connect(db := str(tmp_path / "ark.duckdb")) as conn:
        conn.execute(
            SCHEMA_SQL + ";INSERT INTO source VALUES (1, 'ia_cdx_bulk', 'timestamped', NULL),"
            " (2, 'fleet_x_hostnames', 'timestamped', NULL); INSERT INTO domain"
            " (domain, discovered_source) VALUES ('o.com', 1), ('n.com', 1), ('r.com', 2);"
            "INSERT INTO evidence (domain, source_id, evidence_year, evidence_type, evidence_value,"
            " ingested_at) SELECT domain, discovered_source, 1998, 'cdx_timestamp', 'x',"
            " if(domain = 'o.com', '2026-01-01'::TIMESTAMPTZ, now()) FROM domain;"
            "INSERT INTO domain_year SELECT domain, 1998, evidence_id, now() FROM evidence;"
            "INSERT INTO hostname_year SELECT 'www.' || domain, domain, 1998, evidence_id, now()"
            " FROM evidence; INSERT INTO ingested_file SELECT s.name, domain, 'abc', 1,"
            " ingested_at FROM evidence JOIN source s USING (source_id)"
        )
        held = {name: unbank.counts(conn, name) for name in ("ia_cdx_bulk", "fleet_x_hostnames")}
    names = [*awk.stdout.split(), "never_ingested", "--db", db]
    assert unbank.main(names) == 0 and "holds" in capsys.readouterr().out
    args = [*names, "--write", "--run-start", start.stdout.strip()]
    assert unbank.main(args) == 1
    said = capsys.readouterr()
    assert "REFUSED ia_cdx_bulk" in said.err and "never_ingested is not in the store" in said.out
    with duckdb.connect(db, read_only=True) as conn:
        assert (
            unbank.counts(conn, "ia_cdx_bulk")
            == held["ia_cdx_bulk"]
            == dict.fromkeys(held["ia_cdx_bulk"], 2)
        )
        assert held["fleet_x_hostnames"] == dict.fromkeys(held["fleet_x_hostnames"], 1)
        assert not any(unbank.counts(conn, "fleet_x_hostnames").values()), "every grain"
        kept = "SELECT count(*) FROM domain WHERE domain = 'r.com' UNION ALL SELECT count(*)"
        kept += " FROM source WHERE name = 'fleet_x_hostnames'"
        assert conn.execute(kept).fetchall() == [(1,), (1,)]


# --- bank_hygiene: the clone, the disk, the staging and the gate --------------------------

_ENV = hyg.clean_env()  # a hook's GIT_INDEX_FILE would stage these fixture clones into ours
BRIEF = {"field5_percent": "5.010400", "gate_pct": 5.0, "round": "8", "baseline": "m1"}


def _git(cwd: Path, *args: str) -> str:
    who = ["-c", "user.name=t", "-c", "user.email=t@example.org"]
    kw = {"cwd": cwd, "env": _ENV, "capture_output": True, "text": True, "timeout": 60}
    return subprocess.run(["git", *who, *args], check=True, **kw).stdout.strip()


@pytest.fixture(scope="module")
def behind(tmp_path_factory) -> Path:
    """A clone of `theirs` one commit behind it; each test works on its own copy of the clone."""
    root = tmp_path_factory.mktemp("clones")
    _git(root, "init", "-b", "live", "theirs")
    for text in ("one\n", "two\n"):
        for rel in ("src/page.txt", "docs/registers/page.txt"):
            (root / "theirs" / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / "theirs" / rel).write_text(text, encoding="utf-8")
        _git(root / "theirs", "add", ".")
        _git(root / "theirs", "commit", "-m", text)
        if text == "one\n":
            _git(root, "clone", str(root / "theirs"), "ours")
    return root / "ours"


@pytest.mark.parametrize(
    "files,commit,code,said,page",
    [
        ({"scratch.txt": "notes\n", "src/new.txt": "draft\n"}, False, 0,
         "untracked, not staged by the bank", "two\n"),
        ({"docs/registers/new.txt": "draft\n"}, False, 2, "docs/registers/new.txt", "one\n"),
        ({"src/page.txt": "mine\n"}, False, 2, "REFUSED: the clone is dirty", "mine\n"),
        ({"src/other.txt": "ours\n"}, True, 2, "diverged", "one\n"),
    ],
    ids=["untracked-warns-and-pulls", "untracked-staged-refuses", "dirty-refuses", "diverged"],
)  # fmt: skip
def test_only_a_clean_clone_is_pulled(
    tmp_path, monkeypatch, behind, files, commit, code, said, page
):
    """A refusal comes before the pull, and a hook's git variables never reach its git."""
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nowhere"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "nowhere/index"))
    ours = Path(shutil.copytree(behind, tmp_path / "ours"))
    for rel, text in files.items():
        (ours / rel).write_text(text, encoding="utf-8")
    if commit:
        _git(ours, "add", *files)
        _git(ours, "commit", "-m", "ours")
    head = _git(ours, "rev-parse", "HEAD")
    got, lines = hyg.preflight(root=ours)
    assert got == code and any(said in line for line in lines), lines
    assert said != "untracked, not staged by the bank" or sum(said in ln for ln in lines) == 2
    assert (ours / "src/page.txt").read_text(encoding="utf-8") == page
    assert (_git(ours, "rev-parse", "HEAD") != head) == (code == 0)


@pytest.mark.parametrize(
    "head,free,asked",
    [("main", 100, ["rev-parse"]), ("live", 1, ["rev-parse", "status"])],
    ids=["on-main", "low-space-on-either-filesystem"],
)
def test_preflight_refuses_main_and_low_space_before_the_pull(
    tmp_path, monkeypatch, head, free, asked
):
    """Low space is `data/` or `output/` below the floor plus the write budget."""
    for name in ("data", "output"):
        (tmp_path / name).mkdir()
    by_name = {"data": 100, "output": free}
    monkeypatch.setattr(hyg.shutil, "disk_usage", lambda p: Mock(free=by_name[p.name] * hyg.GIB))
    calls = []
    run = lambda args, cwd: calls.append(args[0]) or (0, head if args[0] == "rev-parse" else "")  # noqa: E731
    code, lines = hyg.preflight(root=tmp_path, run=run)
    assert code == 2 and lines[-1].startswith("REFUSED") and calls == asked


@pytest.mark.parametrize(
    ("floor", "free", "code"),
    [("10", 14, 2), ("10", 15, 0), ("0", 1000, 2), ("-1", 1000, 2)],
    ids=["below-floor-plus-budget", "at-floor-plus-budget", "setting-0", "setting-negative"],
)
def test_space_is_the_floor_plus_the_budget_and_a_setting_not_positive_fails_closed(
    tmp_path, monkeypatch, floor, free, code
):
    monkeypatch.setenv("ARK_FREE_SPACE_GIB", floor)
    monkeypatch.setenv("ARK_WRITE_BUDGET_GIB", "5")
    monkeypatch.setattr(hyg.shutil, "disk_usage", lambda p: Mock(free=free * hyg.GIB))
    code_got, lines = hyg.space(root=tmp_path)
    assert code_got == code and (code == 0 or lines[-1].startswith("REFUSED")), lines


def test_prune_takes_only_old_staging_with_a_verified_copy(tmp_path, monkeypatch) -> None:
    """Dry by default, age alone deletes nothing, and a second run changes nothing."""
    staging, was = tmp_path / "data/fleet_findings", time.time() - 30 * 86400
    (staging / "incoming/run_1").mkdir(parents=True)
    for rel in ("incoming/run_2", "banked/old", "banked/new"):
        (staging / rel).mkdir(parents=True)
        (staging / rel / "finding.md").write_text("f", encoding="utf-8")
    os.utime(staging / "banked/old", (was, was))
    tree = lambda: {p: p.is_file() and p.read_bytes() for p in tmp_path.rglob("*")}  # noqa: E731
    before = tree()
    for write in (False, True):
        lines = hyg.prune(root=tmp_path, days=14, write=write)
        assert any("banked/old" in s for s in lines) and any("HELD" in s for s in lines)
        assert tree() == before
    offsite, path = hyg.round_prune().sibling("offsite"), staging / "banked/old/finding.md"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    record = {"stat": offsite.signature(tmp_path, path), "kind": "sha256", "digest": digest}
    offsite.write_receipt(tmp_path, offsite.REMOTE, {str(path.relative_to(tmp_path)): record})
    listed = json.dumps({"Size": path.stat().st_size, "Hashes": {"sha256": digest}})
    monkeypatch.setattr(offsite, "rclone", lambda *a, **k: Mock(returncode=0, stdout=listed))
    hyg.prune(root=tmp_path, days=14, write=True)
    assert not (staging / "banked/old").exists() and (staging / "banked/new/finding.md").is_file()
    after, lines = tree(), hyg.prune(root=tmp_path, days=14, write=True)
    assert lines == ["staging directories: nothing to prune"] and tree() == after


@pytest.mark.parametrize(
    "brief,listed,said,asked",
    [
        ({"percent": 5.3597, "round_percent": 5.3597, "field5_percent": "0.252400"}, "",
         "at 0.252400%, gate at 5%: not crossed", 0),
        ({}, "12", "gate issue #12 is already open: latched, not re-notifying", 1),
        ({}, "", "opened the gate issue: Round 8 at 5.010400% against m1 (released 2026-09-02)"
         " at 14:03 UTC", 2),
    ],
    ids=["quotes-field-5-only", "open-issue-is-latched", "crossing-opens-one-issue"],
)  # fmt: skip
def test_the_gate_opens_one_issue_per_crossing(tmp_path, brief, listed, said, asked):
    """The second run of each is latched or not crossed, and asks `gh` nothing."""
    calls, now = [], datetime(2026, 9, 3, 14, 3, tzinfo=UTC)
    call = lambda args: calls.append(args) or (0, listed if args[1] == "list" else "issue #7")  # noqa: E731
    kw = {"released": "2026-09-02", "latch_path": tmp_path / "l.tsv", "now": now, "call": call}
    assert hyg.gate({**BRIEF, **brief}, write=True, **kw)[0] == said
    again = said if asked == 0 else "gate already notified against m1: nothing to do"
    assert hyg.gate({**BRIEF, **brief}, write=True, **kw) == [again] and len(calls) == asked
    labels = [args[args.index("--label") + 1] for args in calls if args[1] == "create"]
    assert labels == ["needs-owner"] * (asked == 2)


def test_a_brief_without_field_5_is_refused(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(hyg, "BRIEF", tmp_path / "brief.json")
    hyg.BRIEF.write_text(json.dumps({"percent": 5.5, "baseline": CURRENT_BASELINE_MARKER}))
    assert hyg._brief() is None and "no field5_percent" in capsys.readouterr().out


# --- bank_trigger: when the tick calls the bank ------------------------------------------


def test_fold_covers_every_glob_the_bank_ingests():
    """A journal whose glob FOLD misses is folded only when something unrelated triggers."""
    recipe = re.search(r"^bank\b[^\n]*:\n((?:[ \t][^\n]*\n|\n)*)", RECIPE, re.M).group(1)
    loops = dict(re.findall(r"\bfor (\w+) in ([^\s;]+)", recipe))
    # A directory is read with its reader's globs, and these readers take plain `.jsonl` too.
    both = ("ingest-usenet-hostnames", "ingest-maillist-hostnames", "ingest-enron-hostnames")
    checked, missed = [], []
    for cmd, args in re.findall(r"(?:uv run ark (ingest\S*)|^\s*ingest_all)\s+(.*)", recipe, re.M):
        for word in (word.strip("\"'") for word in args.split()):
            word = loops.get(word.lstrip("$").strip("{}"), word).rstrip("/")
            if word.startswith("data/raw/"):
                checked.append(word)
                exts = (".jsonl.gz", ".jsonl") if cmd in both else (".jsonl.gz",)
                is_dir = "." not in word.rsplit("/", 1)[-1]
                for sample in [f"{word}/x{e}" for e in exts] if is_dir else [word]:
                    if not any(fnmatchcase(sample.replace("*", "x"), g) for g in bt.FOLD):
                        missed.append(sample)
    assert checked and not missed, f"FOLD misses what the bank ingests: {missed}"


def _tree(root: Path) -> Path:
    """A repo with an approvals page, a baseline marker and one folded journal, then stamped."""
    (root / "docs/registers").mkdir(parents=True)
    (root / bt.APPROVALS).write_text("### a / cdx_snapshot\nDecision: master\n")
    (root / "data/raw/cdx").mkdir(parents=True)
    (root / bt.BASELINE).write_text(json.dumps({"current": {"marker": "merged260922"}}))
    (root / "data/raw/cdx/cdx_a.jsonl.gz").write_bytes(b"one")
    bt.stamp(root)
    return root


def _drained(root: Path, slug: str, name: str, doc: dict) -> None:
    (lead := root / bt.INCOMING / slug).mkdir(parents=True)
    (lead / name).write_text(json.dumps(doc))


def test_only_a_confirmed_find_or_a_drained_read_is_a_reason(tmp_path):
    root = _tree(tmp_path)
    _drained(
        root, "pending-lead", "finding.json", {"verdict": "FIND", "verify": {"status": "pending"}}
    )
    assert bt.check(root) == (1, "bank: nothing arrived")
    assert bt.check(root, find_only=True) == (1, "")
    _drained(
        root, "good-lead", "finding.json", {"verdict": "FIND", "verify": {"status": "confirmed"}}
    )
    assert bt.check(root) == (0, "bank: find good-lead")
    assert bt.check(root, find_only=True) == (0, "bank: find good-lead")
    _drained(root, "a-read", "read.json", {})
    assert bt.check(root) == (0, "bank: find good-lead\nbank: read a-read")


def test_journals_and_a_retry_wait_out_the_window_unless_the_bank_runs_anyway(
    tmp_path, monkeypatch
):
    """A bank that runs for another reason folds them, or its stamp would swallow them."""
    root = _tree(tmp_path)
    monkeypatch.delenv("ARK_BANK_JOURNAL_HOURS", raising=False)
    (root / "data/raw/cdx/cdx_b.jsonl.gz").write_bytes(b"two!")
    code, text = bt.check(root)
    assert code == 1 and text.startswith("bank: journals moved, held until ")
    (root / bt.APPROVALS).write_text("### a / cdx_snapshot\nDecision: master\n\n### b\n")
    moved = "bank: journals data/raw/cdx/cdx_*.jsonl.gz (+1 files, +4 bytes)"
    assert bt.check(root) == (0, f"bank: approvals changed\n{moved}")
    bt.stamp(root)
    (root / bt.RETRY).write_text("  refetch FAILED for b: HTTP 503\n")
    assert bt.check(root)[1].startswith("bank: a retry, held until ")
    monkeypatch.setenv("ARK_BANK_JOURNAL_HOURS", "0")
    assert bt.check(root) == (0, "bank: approvals not yet banked, retried")


def test_a_red_bank_blocks_every_reason_until_cleared(tmp_path, capsys):
    """The red leaves the stamp alone, so what arrived before it still counts after `clear`."""
    root = _tree(tmp_path)
    _drained(
        root, "good-lead", "finding.json", {"verdict": "FIND", "verify": {"status": "confirmed"}}
    )
    (root / "data/raw/cdx/cdx_b.jsonl.gz").write_bytes(b"two!")
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
    moved = "bank: journals data/raw/cdx/cdx_*.jsonl.gz (+1 files, +4 bytes)"
    assert bt.check(root) == (0, f"bank: find good-lead\n{moved}")
    assert bt.clear(root) == "bank: nothing to clear"
