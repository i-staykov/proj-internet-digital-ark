"""The cycle and what it hands the owner: its checks, the residual audit it calls, the
approvals it files and the queue page it writes. A staleness parse error crashes the cycle, two
rebuilds of one path truncate a list, and an ask filed twice or not at all is a decision lost."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import pytest

from ark.db import add_candidate, connect, ensure_source, init_db

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/round"))
import lead_queue  # noqa: E402


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = sys.modules[name] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cycle = _load("discover_cycle", "scripts/harness/discover_cycle.py")
audit = _load("audit_residual", "scripts/harness/audit_residual.py")
sa = _load("sync_approvals", "scripts/harness/sync_approvals.py")


def test_a_rebuild_reads_hours_and_only_a_live_holder_blocks_it(tmp_path, monkeypatch):
    """`float("0.9h")` raises and took the whole cycle down, and no hours field reads as zero.
    A crashed cycle must not stop every later rebuild: a gone or stale holder is none."""
    lock = tmp_path / "rebuild.lock"
    monkeypatch.setattr(cycle, "REBUILD_LOCK", lock)
    said = (
        "  [STALE] data/raw/rdap/pool_targets_measured.txt  2026-08-11T13:54:15Z  0.9h behind\n"
        "  [STALE] some/path.txt  2026-08-11T13:54:15Z  behind\n"
    )
    monkeypatch.setattr(cycle, "run", lambda *a, **k: (said, True))
    assert cycle.rebuild_derived()[0] == [
        "derived: pool_targets_measured.txt 0.9h behind, under the threshold",
        "derived: path.txt 0.0h behind, under the threshold",
    ]
    assert cycle.rebuild_lock_holder() is None
    lock.write_text(str(os.getpid()))
    assert cycle.rebuild_lock_holder() == str(os.getpid())
    ancient = lock.stat().st_mtime - cycle.REBUILD_LOCK_STALE_S - 60
    os.utime(lock, (ancient, ancient))
    assert cycle.rebuild_lock_holder() is None
    lock.write_text("999999")
    assert cycle.rebuild_lock_holder() is None


def test_an_idle_slot_is_reported_never_dispatched_the_ask_bounded(tmp_path, monkeypatch, capsys):
    """`leg.yaml`'s schedule is the watchdog that starts an idle slot, so the check only
    reports. Inside the hourly sync, which calls `--slots-only`, `STEP_TIMEOUT`, an hour,
    would hold the bank the whole window, so every call it makes is bounded."""
    asked = []
    monkeypatch.setattr(cycle, "run", lambda cmd, timeout: asked.append((cmd, timeout)) or said)
    (fleet := tmp_path / "fleet").mkdir()
    # Only a title that is exactly `Leg slot N` holds slot N.
    runs = [("Leg watchdog", "in_progress"), ("Leg slot 0", "completed"), ("Leg slot 2", "queued")]
    runs += [("Leg slot 01", "in_progress"), ("Leg slot 10", "waiting"), ("Leg slot 5", "waiting")]
    idle = "leg slots: 2 of 3 idle (slot 0, 1), for leg.yaml's watchdog to start"
    one, gone = [{"displayTitle": "Leg slot 0", "status": "waiting"}], "HTTP 404: not found"
    for bound, answer, want in (
        (3, [{"displayTitle": t, "status": s} for t, s in runs], idle),
        (1, one, "leg slots: all 1 held by a run"),
        (0, [], "leg slots: policy.json wave.max_parallel is 0, so no slot runs"),
        (1, gone, "leg slots: COULD NOT CHECK, gh said: HTTP 404"),
    ):
        (fleet / "policy.json").write_text(json.dumps({"wave": {"max_parallel": bound}}))
        said = (answer if isinstance(answer, str) else json.dumps(answer), True)
        findings, attention = cycle.check_leg_slots(fleet)
        assert findings[0].startswith(want) and attention == [], (bound, findings)
    assert cycle.check_leg_slots(tmp_path / "none")[0][0].startswith("leg slots: COULD NOT CHECK")
    assert len(asked) == 3, "a zero bound asks GitHub nothing"
    for cmd, timeout in asked:
        assert cmd[:3] == ["gh", "run", "list"] and "leg.yaml" in cmd and timeout <= 120, cmd
    # The flag runs the check alone, on the fleet it is given.
    seen = []
    monkeypatch.setattr(cycle, "check_leg_slots", lambda f: seen.append(f) or (["all 1 held"], []))
    monkeypatch.setattr(cycle, "cycle", lambda *a, **k: pytest.fail("the whole cycle ran"))
    monkeypatch.setattr(sys, "argv", ["cycle", "--slots-only", "--fleet", str(tmp_path)])
    cycle.main()
    assert seen == [tmp_path] and "all 1 held" in capsys.readouterr().out


def test_the_residual_checks_fire_on_a_real_defect(tmp_path, monkeypatch, capsys):
    (raw := tmp_path / "data/raw").joinpath("demo").mkdir(parents=True)
    for name in ("a.gz", "b.gz", "wb_nw_9607_org.gz"):
        (raw / "demo" / name).write_text("x")
    for name, value in {"ROOT": tmp_path, "JUSTFILE": tmp_path / "justfile", "RAW": raw}.items():
        monkeypatch.setattr(audit, name, value)

    def found(glob: str, check: str, *held: str) -> tuple[int, str]:
        (tmp_path / "justfile").write_text(f"demo:\n    uv run ark ingest isc_survey {glob}\n")
        count = getattr(audit, f"check_{check}")({"isc_survey": set(held)}, verbose=True)
        return count, capsys.readouterr().out

    count, out = found("data/raw/demo/*.gz", "unread", "a.gz")
    assert count == 2 and "demo/b.gz" in out and "demo/a.gz" not in out
    assert found("data/raw/demo/*.gz", "unread", "a.gz", "b.gz", "wb_nw_9607_org.gz")[0] == 0
    (tmp_path / "justfile").write_text(
        "demo:\n    # uv run ark ingest isc_survey data/raw/demo/*.gz\n"
    )
    assert audit.check_unread({"isc_survey": set()}, verbose=True) == 0, "a comment is no glob"
    count, out = found("data/raw/demo/[ab].gz", "glob_too_narrow", "a.gz", "wb_nw_9607_org.gz")
    assert count == 1 and "wb_nw_9607_org.gz" in out
    conn = connect(":memory:")
    init_db(conn)
    add_candidate(conn, "fresh.com", ensure_source(conn, "demo", "candidate_only"))
    rel = audit.DERIVED[0][0]
    (tmp_path / rel).parent.mkdir(parents=True)
    (tmp_path / rel).write_text("a.com\n")
    os.utime(tmp_path / rel, (0, 0))
    assert audit.check_stale_derived(conn) == 1
    assert f"[STALE] {rel}" in capsys.readouterr().out


def test_a_locked_store_exits_with_an_explanation_and_a_corrupt_one_raises(tmp_path, monkeypatch):
    lock = 'IO Error: Could not set lock on file "x": Conflicting lock is held in py (PID 73793)'
    monkeypatch.setattr(audit.duckdb, "connect", MagicMock(side_effect=duckdb.IOException(lock)))
    with pytest.raises(SystemExit, match="PID 73793.*waits for the writer"):
        audit.read_only_store(tmp_path / "store.duckdb", patience_s=0)
    corrupt = duckdb.IOException("not a valid DuckDB database")
    monkeypatch.setattr(audit.duckdb, "connect", MagicMock(side_effect=corrupt))
    with pytest.raises(duckdb.IOException, match="valid DuckDB database"):
        audit.read_only_store(tmp_path / "store.duckdb", patience_s=60)


TERMS = "### hostlist / artifact_listing\n- potential: 40000\n"
TERMS += (
    "- **condition 3 of the standing rule fails: the terms are not held.**\nDecision: pending\n"
)
# Conditions 1 to 3 hold and 4 is a missing ingest: work for a collector, not a decision.
WORK = "### bigcorpus / cdx_timestamp\n- potential: 88700\n- **condition 4 of the standing rule"
WORK += " cannot be evaluated: nothing has been ingested.**\n  Conditions 1 to 3 hold (approved"
WORK += " class, machine stamp, terms read).\nDecision: pending\n"
SMALL = "### tiny / artifact_listing\n- **condition 1 fails**\n- potential: 900\nDecision: pending"
DECIDED = "### donelist / artifact_listing\n- potential: 50000\nDecision: master\n"
ROBOTS = "the robots clause is not ok: robots.txt disallows /data/"
PARKED = (
    f"### robots / artifact_listing\n- parked: {ROBOTS}\n- potential: 7000\nDecision: pending\n"
)
# As `just approve` writes it: the potential among the head lines, then a table and reasons.
WRITTEN = "### sampled / artifact_listing\n- potential: 12345\n\n| class | EE |\n|---|---|\n"
WRITTEN += (
    "| master | **12,345.0** |\n\n- reasons: the terms page names no licence\nDecision: pending\n"
)
PR, TITLE = {"number": 11, "headRefName": "approve/hostlist"}, "Approve hostlist? 40,000 EE"


def register(monkeypatch, tmp_path, *blocks: str) -> str:
    text = "# Approvals\n\n" + "\n".join(blocks)
    (path := tmp_path / "approved-sources-list.md").write_text(text)
    monkeypatch.setattr(sa, "REGISTER", path)
    return text


def fake_gh(monkeypatch, prs=(), issues=()) -> list[list[str]]:
    calls = []

    def gh(args, check=True):
        calls.append(args)
        listed = {"pr list": prs, "issue list": issues}.get(" ".join(args[:2]))
        return json.dumps(list(listed)) if listed is not None else "#1"

    monkeypatch.setattr(sa, "gh", gh)
    return calls


def test_pending_classes_are_reported_and_only_owner_calls_filed(monkeypatch, tmp_path):
    """The register's pending block is the ask, so the cycle's check writes no file."""
    text = register(monkeypatch, tmp_path, TERMS, WORK, SMALL, DECIDED, PARKED, WRITTEN)
    monkeypatch.setattr(cycle, "APPROVALS", sa.REGISTER)
    before = sorted(tmp_path.rglob("*"))
    findings, attention = cycle.check_approvals()
    assert "approvals: 5 priced class(es) awaiting classification" in findings
    assert len(attention) == 1 and "bigcorpus/cdx_timestamp" in attention[0]
    assert sorted(tmp_path.rglob("*")) == before and sa.REGISTER.read_text() == text
    assert sa.failed_conditions(WORK) == {"4"}
    wanted = {r.source: r for r in sa.requests(floor=5_000)}
    assert list(wanted) == ["hostlist", "robots", "sampled"]
    assert "tiny" in [r.source for r in sa.requests(floor=100)]
    assert wanted["robots"].failed == f"parked by the standing rule: {ROBOTS}"
    assert wanted["sampled"].failed == "not stated in the block"
    assert wanted["sampled"].potential == 12345
    assert "terms are not held" in wanted["hostlist"].failed
    assert (wanted["hostlist"].branch, wanted["hostlist"].title) == ("approve/hostlist", TITLE)


def test_an_ask_is_one_needs_owner_issue_and_a_one_line_pr(monkeypatch, tmp_path, capsys):
    before = register(monkeypatch, tmp_path, TERMS, DECIDED)
    (request,) = sa.requests(floor=5_000)
    after = sa.approve_line(request, before).splitlines()
    changed = [(a, b) for a, b in zip(before.splitlines(), after, strict=True) if a != b]
    assert changed == [("Decision: pending", "Decision: master")]
    calls = fake_gh(monkeypatch, prs=[PR])
    assert sa.main([]) == 0
    (filed,) = [args for args in calls if args[:2] == ["issue", "create"]]
    assert (filed[filed.index("--label") + 1], filed[filed.index("--title") + 1]) == (
        "needs-owner",
        TITLE,
    )
    body = filed[filed.index("--body") + 1]
    assert "Blocked on: " in body and "Merge 11" in body
    # Re-priced since its issue was filed, the ask is found by its source and not filed again.
    calls = fake_gh(monkeypatch, issues=[{"number": 5, "title": "Approve hostlist? 38,500 EE"}])
    assert sa.main([]) == 0 and "open already: Approve hostlist? 38,500" in capsys.readouterr().out
    # Until live holds the block there is no one line to flip: no branch, no issue.
    calls += fake_gh(monkeypatch)
    monkeypatch.setattr(sa, "live_register", lambda: "# Approvals\n\n" + DECIDED)
    monkeypatch.setattr(sa.subprocess, "run", lambda *a, **k: pytest.fail(f"ran {a}"))
    assert sa.main([]) == 0 and f"not on live yet: {TITLE}" in capsys.readouterr().out
    assert not [args for args in calls if args[:2] in (["pr", "create"], ["issue", "create"])]
    # A dry run asks gh nothing and names the label the issue would carry.
    monkeypatch.setattr(sa, "gh", lambda args, check=True: pytest.fail(f"a dry run ran gh {args}"))
    assert sa.main(["--dry-run"]) == 0
    assert f"issue: would file, labelled needs-owner: {TITLE}" in capsys.readouterr().out


def test_only_its_own_titles_are_closed_under_the_shared_label(monkeypatch, tmp_path) -> None:
    """A title that begins like an approval but is not one this script writes stays open."""
    register(monkeypatch, tmp_path, TERMS, DECIDED)
    listed = [
        {"number": 3, "title": "Approve donelist? 50,000 EE"},
        {"number": 5, "title": TITLE},
        {"number": 8, "title": "Approve donelist? The terms page names no licence"},
        {"number": 9, "title": "Rules: asks carry needs-owner"},
    ]
    calls = fake_gh(monkeypatch, prs=[PR], issues=listed)
    assert sa.main([]) == 0
    listing = next(args for args in calls if args[:2] == ["issue", "list"])
    assert listing[listing.index("--label") + 1] == "needs-owner"
    assert [args[2] for args in calls if args[:2] == ["issue", "close"]] == ["3"]
    assert not [args for args in calls if args[:2] == ["issue", "create"]]


HOSTS = {"grain": "hostname", "evidence_class": "artifact_listing"}
LEADS = {
    **dict.fromkeys("t-line t-string t-false ipac spacekookie relay-hosts usenet-hops".split(), {}),
    "t-status": {"status": "banked"},
    "t-class": {"blocked_on": "two rule decisions: (1) a new evidence class for targets"},
    "t-download": {"blocked_on": "download decision: 57.6 GB, over the 1 GB fetch cap"},
    "stranded": HOSTS,
    "guessed": {**HOSTS, "size_estimate": {"ee_low": 80000, "ee_high": 90000}},
}
REGISTERS = {
    "sources.md": """| source | date | net-new EE (date) | verdict |
|---|---|---|---|
| ipac | d | fleet 35,429.9 EE, store 3,681.7 EE | FIND |
| spacekookie | d | fleet 1,450.5 EE | FIND (pending) |
| spacekookie-reprice | d | 120 host-years, 93.9 EE | CLOSED |
| usenet | d | 0 EE | CLOSED |
| t-class | d | 9,000 EE | FIND |
| stranded | d | 445.1 EE | FIND |
""",
    "sources-closed.md": """| source | date | measured | reason |
|---|---|---|---|
| relay-hosts / received | d | 445.1 EE | RETIRED. Under the floor. |
""",
}


def test_the_queue_asks_a_class_or_the_send_never_the_store(tmp_path, monkeypatch, capsys):
    for blocked, ask in (
        ("download decision: 57.6 GB, over the 1 GB fetch cap", ""),
        ("a download decision admitting content type application/x-rpm", ""),
        ("a terms answer and a download decision", ""),
        ("approval: RIPE NCC permission to read the files", ""),
        ("a re-run of the pricing cmd", ""),
        ("download decision. Then a rule on author_mail_host as an evidence class.", "class"),
        ("rule: whether a hostname in a FAQ body is master-eligible", "class"),
        ("ask whether to send the round under the 5% gate", "send"),
    ):
        assert lead_queue.ask_of(blocked) == ask, blocked  # only a class or the send is asked
    banked = {"t-line": True, "t-string": "true", "t-false": False}
    lines = [json.dumps({"kind": "outcome", "slug": s, "banked": b}) for s, b in banked.items()]
    past = {"round": "Round 11", "baseline": "b1", "field5_percent": 5.2, "gate_pct": 5.0}
    files = {**REGISTERS, "brief.json": json.dumps(past), "ledger/2026-09.jsonl": "\n".join(lines)}
    for slug, extra in LEADS.items():
        doc = {"slug": slug, "status": "scouted", "evidence_class": "cdx_x", "grain": "registrable"}
        doc |= {"artifact": {"url": f"https://e.org/{slug}"}}
        files[f"leads/{slug}.json"] = json.dumps(doc | extra)
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(exist_ok=True)
        (tmp_path / name).write_text(text + "\n")
    reg = lead_queue.measured(tuple(tmp_path / name for name in REGISTERS))
    monkeypatch.setitem(sys.modules, "duckdb", store := MagicMock())
    monkeypatch.setattr(lead_queue, "BRIEF", tmp_path / "brief.json")
    monkeypatch.setattr(lead_queue, "measured", lambda *a, **k: reg)
    assert (held := lead_queue.banked(tmp_path)) == {"t-line", "t-status"}, "only JSON true banks"
    rows = {r["slug"]: r for r in lead_queue.leads(tmp_path, held)}
    assert not {"spacekookie", "relay-hosts", "t-line", "t-status"} & set(rows), "closed or banked"
    assert {"t-false", "t-string", "usenet-hops"} <= set(rows), "unbanked, and no prefix closes"
    assert (rows["ipac"]["low"], rows["ipac"]["high"]) == (3681.7, 3681.7), "the store's figure"
    assert lead_queue.main(["--fleet", str(tmp_path)]) == 0
    page = capsys.readouterr().out
    assert "crossed the 5% gate** at 5.2000% against `b1`" in page
    assert "### Admit `cdx_x`" in page and "[`t-class`](https://e.org/t-class)" in page
    assert "`t-download`" not in page and "80,000" not in page
    outlet, _, foot = page.partition("### Give the XIII-excluded")[2].partition("estimate alone")
    assert "**445 EE**" in outlet and "| 445.1 | [`stranded`](https://e.org/stranded)" in outlet
    assert "guessed" not in outlet and "`guessed`" in foot, "an estimate is not a row"
    gone = {"round": "10", "round_percent": 6.0, "percent": 6.0, "round_distance_to_gate_ee": 1}
    (brief := tmp_path / "brief.json").write_text(json.dumps(gone))
    assert "Not known here" in lead_queue.send_line(brief), "a key the bank stopped writing"
    assert "Not known here" in lead_queue.send_line(tmp_path / "none.json"), "never guessed"
    under = {"round": "9", "baseline": "m", "field5_percent": 0.3823, "distance_to_gate_ee": 9876.4}
    brief.write_text(json.dumps(under))
    assert lead_queue.send_line(brief) == (
        "Nothing to send: Round 9 stands at 0.3823% against `m`, under the 5% gate, 9,876 EE short."
    )
    assert store.mock_calls == [], "the queue opened the store"
