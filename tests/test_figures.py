"""The ranking score reproduces the two figures the reviewer has quoted, to the digit.

He quotes S_6 = 6.88 and S_7 = 6.302372. Exactly one rule fits both: t_i is the elapsed time
from the release of the benchmark package to receipt, in his clock, rounded up to whole days.
These pin that rule and record why the alternatives were rejected.
"""

import importlib.util
import re
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest
from his_release import WEB_METHOD, capture, text

from ark import held
from ark.baseline import CURRENT_BASELINE_RELEASED, SUBMITTED_ROUNDS, awarded_score_of
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.figures import (
    TASK_ASSIGNED_DATE,
    cumulative,
    elapsed_days,
    now_in_his_clock,
    parse_stamp,
    score,
    scored_under_rule,
    t_days,
    t_days_assignment,
)

ROOT = Path(__file__).resolve().parents[1]
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
ROWS = {r[0]: r for r in SUBMITTED_ROUNDS}


def _score(label: str) -> tuple[int, Decimal]:
    _, _, _, _, _, p, released, received = ROWS[label]
    t = t_days(released, received)
    return t, score(p, t)


def test_round_6_reproduces_his_6_88() -> None:
    t, s = _score("6")
    assert t == 6
    assert s == Decimal("6.884530")
    assert s.quantize(Decimal("0.01")) == Decimal("6.88")


def test_round_7_reproduces_his_6_302372_exactly() -> None:
    t, s = _score("7")
    assert t == 12
    assert s == Decimal("6.302372")


def test_elapsed_is_fractional_and_t_rounds_up() -> None:
    e = elapsed_days("2026-08-21 11:19", "2026-08-26 15:51")
    assert e.quantize(Decimal("0.0001")) == Decimal("5.1889")
    assert t_days("2026-08-21 11:19", "2026-08-26 15:51") == 6
    assert elapsed_days("2026-08-21 11:19", "2026-09-02 05:50").quantize(
        Decimal("0.01")
    ) == Decimal("11.77")


def test_calendar_days_were_rejected_because_they_miss_round_6() -> None:
    """Calendar days from the release give t = 5 and S = 8.26, not the 6.88 he quotes."""
    _, _, _, _, _, p, released, received = ROWS["6"]
    calendar = (date.fromisoformat(received[:10]) - date.fromisoformat(released[:10])).days
    assert calendar == 5
    assert score(p, calendar) == Decimal("8.261436")
    assert score(p, calendar).quantize(Decimal("0.01")) != Decimal("6.88")


def test_a_clock_from_the_brief_update_was_rejected_because_it_misses_round_7() -> None:
    """Counting from the 2026-08-20 03:37 update gives round 7 t = 14 (or 13 by calendar)."""
    p = ROWS["7"][5]
    assert t_days("2026-08-20 03:37", "2026-09-02 05:50") == 14
    assert score(p, 14) != Decimal("6.302372")
    assert score(p, 13) != Decimal("6.302372")


def test_cumulative_is_the_sum_of_the_rounds_he_scored() -> None:
    scored = [_score(label)[1] for label in ("6", "7")]
    assert cumulative(scored) == Decimal("13.186902")
    assert cumulative([]) == Decimal(0)


def test_the_rule_covers_rounds_6_to_9() -> None:
    assert [r[0] for r in SUBMITTED_ROUNDS if scored_under_rule(r[7])] == ["6", "7", "8", "9"]


def test_a_receipt_inside_the_release_minute_still_divides_by_one() -> None:
    assert t_days("2026-09-02 10:31", "2026-09-02 10:31") == 1


def test_rows_carry_minute_stamps_in_his_clock() -> None:
    for r in SUBMITTED_ROUNDS:
        assert STAMP.match(r[6]) and STAMP.match(r[7]), r[0]
        assert parse_stamp(r[7]) > parse_stamp(r[6]), r[0]
    assert ROWS["6"][6] == "2026-08-21 11:19"
    assert ROWS["7"][6] == "2026-08-21 11:19"
    assert STAMP.match(CURRENT_BASELINE_RELEASED)
    assert STAMP.match(now_in_his_clock())


def test_fill_report_has_no_day_arithmetic_of_its_own() -> None:
    source = (ROOT / "scripts/round/fill_report.py").read_text(encoding="utf-8")
    for token in ("date.today", "fromisoformat", "timedelta", ".days"):
        assert token not in source, token


def test_fill_report_quotes_his_sum_and_both_scores(monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location(
        "fill_report_for_figures", ROOT / "scripts/round/fill_report.py"
    )
    fill_report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fill_report)
    monkeypatch.setattr(fill_report, "now_in_his_clock", lambda: "2026-09-03 10:00")
    sentence = fill_report.cumulative_sentence({}, Decimal("1.5"))
    # The addends are his own scores, not our model of them (round 6 is 6.884530 by the
    # benchmark clock, round 8 187.697140), so the sum is one he can check in his head.
    assert "score 6.88 + 6.302372 + 5.687792 + 0.944228 = 19.814392" in sentence
    assert "your own scores for rounds 6, 7, 8 and 9" in sentence
    assert "whole days since the 2 August assignment" in sentence
    assert "this round is t = 32" in sentence
    assert "Domain-Year Score: S = 10 x (1.500000 / 32) = 0.468750" in sentence
    assert "Candidate-Pool Score: S = 10 x (" in sentence
    assert "?" not in sentence


def test_the_assignment_rule_of_2026_09_03_is_whole_calendar_days_from_one_origin() -> None:
    """His 0903 update: t_i = max(1, receipt_date_i - task_assignment_date_member). Dates, not
    stamps, and the origin never moves. Round 7 was received 31 days after 2026-08-02, so it
    scores 2.439 rather than the 6.302372 he awarded under the benchmark rule.
    """
    p = ROWS["7"][5]
    assert t_days_assignment("2026-09-02 05:50") == 31
    assert score(p, 31) == Decimal("2.439628")
    # the time of day cannot change a whole-calendar-day count
    assert t_days_assignment("2026-09-02 23:59") == t_days_assignment("2026-09-02 00:01")
    # and the clock does not reset on a later benchmark: round 5 went out two days after
    # a release and 15 days after assignment
    assert t_days("2026-08-15 10:27", "2026-08-17 03:03") == 2
    assert t_days_assignment("2026-08-17 03:03") == 15


def test_the_assignment_origin_is_the_one_his_own_divisor_implies() -> None:
    """One day of error here moves every S_i, so the origin is derived, not guessed. He scored
    round 8 with a divisor of 33 and received it on 2026-09-04, so whole calendar days back
    from that receipt is the origin and it must reproduce his 33 exactly.
    """
    assert TASK_ASSIGNED_DATE == "2026-08-02"
    his = awarded_score_of("8")
    assert his is not None
    received = next(r[7] for r in SUBMITTED_ROUNDS if r[0] == "8")
    assert t_days_assignment(received) == his.divisor
    assert score(his.percent, his.divisor) == his.score


def test_a_receipt_on_the_assignment_date_still_divides_by_one() -> None:
    assert t_days_assignment(TASK_ASSIGNED_DATE + " 23:00") == 1


def test_the_benchmark_reading_still_flatters_us_against_his_own_rule() -> None:
    """Both totals, so nobody quotes the friendlier one by accident. Rounds 6 and 7 were
    awarded under the benchmark rule and those awards stand; from his 0903 update the
    assignment rule governs, and round 8's divisor of 33 counts back from its 2026-09-04
    receipt to 2026-08-02. Rounds received before that origin divide by the rule's floor of
    1, so the totals below are properties of the two formulas, not claims about the rounds.
    """
    bench = cumulative([score(r[5], t_days(r[6], r[7])) for r in SUBMITTED_ROUNDS])
    assign = cumulative([score(r[5], t_days_assignment(r[7])) for r in SUBMITTED_ROUNDS])
    assert bench == Decimal("346.398332")
    assert assign == Decimal("226.456659")
    assert bench > assign


def test_the_round_since_total_is_bound_once_in_main() -> None:
    """`mean weight` is the round-since registrable EE over its own record count, so anything
    that rebinds either name between their assignment and that line prints a different
    quantity under the same label. The candidate claim did exactly that: round 10 printed
    0.3075, which is 77,497.7487 / 252,019, the CANDIDATE EE over the ANNUAL records, and it
    passed unnoticed because the two tracks were the same order of magnitude. merged260922
    made the same expression read 26.4712, above the 1.0 that any English share can be.
    """
    import ast

    source = (ROOT / "scripts/round/round_figures.py").read_text()
    main = next(
        n
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.FunctionDef) and n.name == "main"
    )
    bound: list[str] = []
    for node in ast.walk(main):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                bound += [x.id for x in ast.walk(target) if isinstance(x, ast.Name)]
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name):
            bound.append(node.target.id)
    for name in ("ee", "pairs"):
        assert bound.count(name) == 1, (
            f"{name} is bound {bound.count(name)} times in main(); the mean weight line "
            "reads whatever was assigned last"
        )


def test_the_default_figures_read_files_and_never_the_store(tmp_path, monkeypatch, capsys) -> None:
    """The bank quotes field 5 while it may hold the writer, so the default mode reads only
    files. A `www.` host counts as an alias only when its bare name is held that same year.
    """
    spec = importlib.util.spec_from_file_location(
        "round_figures_default", ROOT / "scripts/round/round_figures.py"
    )
    rf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rf)

    def refuse(*_args, **_kwargs):
        raise AssertionError("the default figures opened the store")

    netnew, his = tmp_path / "output/netnew", tmp_path / "his"
    netnew.mkdir(parents=True)
    his.mkdir()
    for year in range(1996, 2002):
        for path in (netnew / f"{year}.txt", netnew / f"{year}_hostnames.txt", his / f"{year}.txt"):
            path.write_text("")
    (netnew / "2001.txt").write_text("d.com\n")
    (netnew / "2001_hostnames.txt").write_text("www.a.com\nwww.b.com\nwww.c.net\n")
    (netnew / "attested_registrables.txt").write_text("2000\tb.com\n2001\tc.net\n")
    (his / "2000.txt").write_text("b.com\n")
    (his / "2001.txt").write_text("a.com\n")
    monkeypatch.setattr(rf, "open_store", refuse)
    monkeypatch.setattr(duckdb, "connect", refuse)
    monkeypatch.setattr(
        rf, "english_weights", lambda: {"com": Decimal("0.5"), "net": Decimal("0.25")}
    )
    monkeypatch.setattr(rf, "REPO", tmp_path)
    monkeypatch.setattr(rf, "NETNEW", netnew)
    monkeypatch.setattr(rf, "ATTESTED", netnew / "attested_registrables.txt")
    monkeypatch.setattr(rf, "his_year", lambda year: his / f"{year}.txt")
    monkeypatch.setattr(sys, "argv", ["round_figures.py"])

    rf.main()
    out = capsys.readouterr().out
    field = dict(re.findall(r"^([345])\. .*: (.+)$", out, re.M))
    assert field["3"] == "4 records"
    assert field["4"] == "1.7500"
    assert field["5"] == f"{Decimal('1.75') / rf.BASELINE_EE * 100:.6f}%"
    assert "| 2001 | 4 | 1.7500 |" in out
    # a.com is his 2001 and c.net is attested 2001; b.com is held only in 2000
    assert ": 2 records  0.7500  (60.0% of the hostname half)" in out

    (netnew / "attested_registrables.txt").unlink()
    rf.main()
    assert "not measured, output/netnew lacks attested_registrables.txt" in capsys.readouterr().out
    (netnew / "1996.txt").unlink()
    with pytest.raises(SystemExit, match="lacks 1996.txt: run ark export --claim"):
        rf.main()

    # `--verify` refuses the round when a shipped line is his for that year, by exact name
    assert rf.already_in_his_files() == 0
    (netnew / "2000.txt").write_text("b.com\n")
    (netnew / "2001.txt").write_text("A.com\nd.com\n")
    assert rf.already_in_his_files() == 1


def _script(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _store_beside_his_release(folder: Path):
    """Our pairs beside his files: new.com and old.com are net-new, already-his.com is his that
    year, rested.com his in 1997 only, and nocapture.com has no capture. Three usenet names
    wait to be dated."""
    (folder / "1997.txt").write_bytes(text(["already-his.com", "gone.com", "rested.com"]))
    held.prepare(folder)
    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    usenet = ensure_source(conn, "usenet_mention", "timestamped")
    for name in ("new.com", "old.com", "already-his.com", "rested.com", "nocapture.com"):
        add_candidate(conn, name, cdx)
    for name in ("u.com", "gone.com"):
        add_candidate(conn, name, usenet)

    def dated(name: str, source: int, year: int, kind: str, value: str, method=None) -> None:
        assign_year(conn, record_evidence(conn, name, source, year, kind, value, None, method))

    for name, year in (("new.com", 1999), ("old.com", 2000), ("already-his.com", 1999)):
        dated(name, cdx, year, "cdx_timestamp", capture(name, year), WEB_METHOD)
    dated("rested.com", cdx, 1999, "cdx_timestamp", capture("rested.com", 1999), WEB_METHOD)
    dated("nocapture.com", cdx, 1999, "whois_creation", "1999-03-01")
    for name in ("u.com", "gone.com", "new.com"):
        record_evidence(conn, name, usenet, 1998, "artifact_listing", f"news {name}")
    conn.execute(
        "UPDATE domain_year SET verified_at = TIMESTAMPTZ '1999-06-01 00:00:00+00' "
        "WHERE domain = 'old.com'"
    )
    return conn


def test_the_round_so_far_counts_only_what_would_ship_and_he_lacks(
    his_files, tmp_path, monkeypatch
) -> None:
    """`--full` counts a pair verified this round only when the export would ship it: a
    capture of exactly its name, and not in his file for its year. A held-back name his files
    hold in any year is his, not ours to hold back."""
    rf = _script("round_figures_full", "scripts/round/round_figures.py")
    monkeypatch.setattr(rf, "DB_TEMP_DIR", str(tmp_path / "scratch"))
    monkeypatch.setattr(rf, "SINCE", "2000-01-01 00:00:00+00")
    monkeypatch.setattr(rf, "english_weights", lambda: {"com": Decimal("0.5")})
    m = rf.increment(_store_beside_his_release(his_files))
    # new.com and rested.com in 1999; old.com was verified before the round opened
    assert (m["pairs"], m["ee"], m["domains"]) == (2, Decimal("1.0"), 2)
    assert m["by_source"] == {"ia_cdx": [2, Decimal("1.0")]}
    # u.com; gone.com is his, new.com is dated
    assert m["held"] == 1


def test_the_report_figures_are_the_shipped_net_new_and_our_own_store(
    his_files, tmp_path, monkeypatch
) -> None:
    """Every net-new figure reads the pairs the year files hold, the completeness table divides
    by his own line counts, and the store counts its own tables, which hold only ours."""
    rf = _script("report_figures_for_test", "scripts/round/report_figures.py")
    candidates = tmp_path / "candidate_unverified.txt"
    candidates.write_text("a.edu\nb.com\nc.org\n")
    monkeypatch.setattr(rf, "CANDIDATES_PATH", candidates)
    monkeypatch.setattr(rf, "DB_TEMP_DIR", str(tmp_path / "scratch"))
    monkeypatch.setattr(rf, "english_weights", lambda: {"com": Decimal("0.5")})
    f = rf.figures(_store_beside_his_release(his_files))
    assert f["netnew_by_year"] == {1999: 2, 2000: 1}
    assert (f["netnew_pairs"], f["netnew_unique_domains"]) == (3, 3)
    # rested.com is his in 1997
    assert f["netnew_domains_absent_from_baseline"] == 2
    assert f["capture_backed_by_year"] == {1999: 2, 2000: 1}
    assert f["by_source"] == [
        {
            "source": "ia_cdx",
            "kind": "timestamped",
            "evidence_type": "cdx_timestamp",
            "master": True,
            "pairs": 3,
            "domains": 3,
            "ee": Decimal("1.5"),
        }
    ]
    assert f["ee_netnew"] == Decimal("1.5")
    assert f["baseline_by_year"] == {1996: 2, 1997: 3, 1998: 1, 1999: 2, 2000: 1, 2001: 2}
    # the completeness table sets both of our units against his lines
    assert set(f["hostname_lines_by_year"]) == set(f["baseline_by_year"])
    assert f["candidate_pool"] == 3
    assert f["store"] == {
        "pairs_total": 5,
        "domains_total": 7,
        "evidence_rows": 8,
        "ingested_files": 0,
    }
    candidates.unlink()
    with pytest.raises(SystemExit, match="candidate_unverified.txt is missing"):
        rf.figures(connect(":memory:"))


def test_the_report_counts_restricted_names_and_isc_names_he_holds_from_files(
    his_files, tmp_path, monkeypatch
) -> None:
    """The restricted share is of the pool that shipped, and the ISC names he holds are
    his exact names, read through `held`."""
    fill_report = _script("fill_report_for_counts", "scripts/round/fill_report.py")
    candidates = tmp_path / "candidate_unverified.txt"
    candidates.write_text("a.edu\nb.com\nc.gov\nd.mil\ne.edu.au\n")
    monkeypatch.setattr(fill_report, "CANDIDATES_PATH", candidates)
    assert fill_report.pool_restricted() == "3"

    store = tmp_path / "store.duckdb"
    conn = connect(store)
    init_db(conn)
    isc = ensure_source(conn, "isc_survey", "timestamped")
    for name in ("already-his.com", "new.com"):
        add_candidate(conn, name, isc)
        record_evidence(conn, name, isc, 1997, "artifact_listing", f"isc {name}")
    conn.close()
    monkeypatch.setattr(
        "ark.db.connect_read_only_patiently",
        lambda *_a, **_k: duckdb.connect(str(store), read_only=True),
    )
    assert fill_report.isc_registrables_he_holds() == 1


def test_the_round_state_quotes_field_5_from_files_and_never_opens_the_store(
    tmp_path, monkeypatch, capsys
) -> None:
    """The bank writes ROUND.md while it holds the writer, so the default build runs
    round_figures once, opens no store, and the brief carries the field 5 ROUND.md prints."""
    import json

    spec = importlib.util.spec_from_file_location(
        "build_round_state", ROOT / "scripts/round/build_round_state.py"
    )
    brs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(brs)

    def refuse(*_args, **_kwargs):
        raise AssertionError("the default build opened the store")

    figures = (
        "3. Increment                                  : 1,234 records\n"
        "4. Equivalent-English increment               : 3,456.7800\n"
        "5. Equivalent-English growth rate             : 0.252350%\n"
    )
    calls = []
    monkeypatch.setattr(brs, "run", lambda cmd, timeout: calls.append(cmd) or figures)
    monkeypatch.setattr("ark.db.connect_read_only_patiently", refuse)
    monkeypatch.setattr(duckdb, "connect", refuse)
    monkeypatch.setattr(brs, "pending_approvals", lambda: [])
    monkeypatch.setattr(brs, "ROOT", tmp_path)
    monkeypatch.setattr(brs, "OUT", tmp_path / "docs/ROUND.md")
    monkeypatch.setattr(brs, "BRIEF", tmp_path / "data/brief.json")
    (tmp_path / "docs").mkdir()
    netnew = tmp_path / "output/netnew"
    netnew.mkdir(parents=True)
    (netnew / "2001.txt").write_text("d.com\n")
    stamp = netnew / "export_stamp.json"
    stamp.write_text(json.dumps({"baseline": brs.CURRENT_BASELINE_MARKER}))

    monkeypatch.setattr(sys, "argv", ["build_round_state.py"])
    brs.main()
    text = brs.OUT.read_text()
    brief = json.loads(brs.BRIEF.read_text())
    assert calls == [["uv", "run", "python", "scripts/round/round_figures.py"]]
    assert brief["field5_percent"] == "0.252350"
    assert brief["waiting_on_human"] == {"approvals": 0}
    assert re.search(r"^5\. .*: (.+)$", text, re.M).group(1) == brief["field5_percent"] + "%"
    assert "## The scoreboard" not in text and "## What is on disk" not in text

    monkeypatch.setattr(sys, "argv", ["build_round_state.py", "--check"])
    brs.main()
    assert "is current" in capsys.readouterr().out
    (netnew / "2001.txt").write_text("e.com\n")
    with pytest.raises(SystemExit, match="is stale"):
        brs.main()
    assert "netnew/2001.txt: changed" in capsys.readouterr().out

    # An export with no stamp, crashed or older than stamps, is never quoted.
    stamp.unlink()
    monkeypatch.setattr(sys, "argv", ["build_round_state.py"])
    with pytest.raises(SystemExit, match="no export stamp"):
        brs.main()
    assert "field5_percent" not in json.loads(brs.BRIEF.read_text())
