"""The score reproduces his quoted figures to the digit, and every round figure reads files."""

import importlib.util
import json
import re
import sys
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import Mock

import duckdb
import pytest
from his_release import WEB_METHOD, capture, text

from ark import figures as fig
from ark import held
from ark.baseline import SUBMITTED_ROUNDS, awarded_score_of
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence

ROOT = Path(__file__).resolve().parents[1]
ROWS = {r[0]: r for r in SUBMITTED_ROUNDS}
YEARS = range(1996, 2002)
POOL = "candidate_unverified.txt"
REFUSE = Mock(side_effect=AssertionError("a default figure opened the store"))


def _script(name: str, monkeypatch, **attrs):
    rel = f"scripts/round/{name}.py"
    spec = importlib.util.spec_from_file_location(name + "_under_test", ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for attr, value in attrs.items():
        monkeypatch.setattr(module, attr, value)
    return module


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)


def test_his_scores_reproduce_under_the_benchmark_rule_and_the_assignment_rule() -> None:
    """Benchmark: whole days rounded up from the release, in his clock. Assignment: t_i =
    max(1, receipt date - 2026-08-02), the origin his round 8 divisor implies."""
    for label, t, s in (("6", 6, "6.884530"), ("7", 12, "6.302372")):
        assert fig.t_days(ROWS[label][6], ROWS[label][7]) == t
        assert fig.score(ROWS[label][5], t) == D(s)
    assert round(fig.elapsed_days("2026-08-21 11:19", "2026-08-26 15:51"), 4) == D("5.1889")
    assert fig.t_days("2026-09-02 10:31", "2026-09-02 10:31") == 1
    assert fig.t_days_assignment(fig.TASK_ASSIGNED_DATE + " 23:00") == 1
    assert fig.t_days_assignment("2026-09-02 05:50") == 31
    assert fig.score(ROWS["7"][5], 31) == D("2.439628")
    assert fig.t_days_assignment("2026-09-02 23:59") == fig.t_days_assignment("2026-09-02 00:01")
    assert fig.t_days_assignment("2026-08-17 03:03") == 15  # the origin never moves
    his = awarded_score_of("8")
    assert fig.t_days_assignment(ROWS["8"][7]) == his.divisor
    assert fig.score(his.percent, his.divisor) == his.score
    assert [r[0] for r in SUBMITTED_ROUNDS if fig.scored_under_rule(r[7])] == ["6", "7", "8", "9"]
    assert fig.cumulative([D("6.884530"), D("6.302372")]) == D("13.186902")


def test_fill_report_quotes_his_sum_and_holds_no_day_arithmetic(his_files, tmp_path, monkeypatch):
    """Its sum is of his own scores; its pool counts read the files that shipped and `held`."""
    _write(tmp_path, {POOL: "a.edu\nb.com\nc.gov\nd.mil\ne.edu.au\n"})
    now = {"now_in_his_clock": lambda: "2026-09-03 10:00", "CANDIDATES_PATH": tmp_path / POOL}
    report = _script("fill_report", monkeypatch, **now)
    source = Path(report.__file__).read_text(encoding="utf-8")
    assert [t for t in ("date.today", "fromisoformat", "timedelta", ".days") if t in source] == []
    sentence = report.cumulative_sentence({}, D("1.5"))
    assert "score 6.88 + 6.302372 + 5.687792 + 0.944228 = 19.814392" in sentence
    assert "Domain-Year Score: S = 10 x (1.500000 / 32) = 0.468750" in sentence
    assert "Candidate-Pool Score: S = 10 x (" in sentence and "?" not in sentence, sentence
    assert report.pool_restricted() == "3"
    conn = connect(tmp_path / "store.duckdb")
    init_db(conn)
    isc = ensure_source(conn, "isc_survey", "timestamped")
    for name in ("already-his.com", "new.com"):
        add_candidate(conn, name, isc)
        record_evidence(conn, name, isc, 1997, "artifact_listing", f"isc {name}")
    conn.close()
    reopen = lambda *_a, **_k: duckdb.connect(str(tmp_path / "store.duckdb"), read_only=True)  # noqa: E731
    monkeypatch.setattr("ark.db.connect_read_only_patiently", reopen)
    assert report.isc_registrables_he_holds() == 1  # already-his.com, by exact name


def test_the_default_figures_read_files_and_never_the_store(tmp_path, monkeypatch, capsys) -> None:
    """Field 5 from files alone; a `www.` host is an alias only when its bare name is held."""
    netnew, his = tmp_path / "output/netnew", tmp_path / "his"
    _write(his, {f"{y}.txt": "" for y in YEARS} | {"2000.txt": "b.com\n", "2001.txt": "a.com\n"})
    _write(netnew, {f"{y}{s}.txt": "" for y in YEARS for s in ("", "_hostnames")})
    hosts = {"2001_hostnames.txt": "www.a.com\nwww.b.com\nwww.c.net\n", "2001.txt": "d.com\n"}
    _write(netnew, hosts | {"attested_registrables.txt": "2000\tb.com\n2001\tc.net\n"})
    monkeypatch.setattr(duckdb, "connect", REFUSE)
    monkeypatch.setattr(sys, "argv", ["round_figures.py"])
    rf = _script("round_figures", monkeypatch, open_store=REFUSE, REPO=tmp_path)
    monkeypatch.setattr(rf, "english_weights", lambda: {"com": D("0.5"), "net": D("0.25")})
    monkeypatch.setattr(rf, "his_year", lambda year: his / f"{year}.txt")
    monkeypatch.setattr(rf, "NETNEW", netnew)
    monkeypatch.setattr(rf, "ATTESTED", netnew / "attested_registrables.txt")
    rf.main()
    out = capsys.readouterr().out
    field = dict(re.findall(r"^([345])\. .*: (.+)$", out, re.M))
    assert field == {"3": "4 records", "4": "1.7500", "5": f"{D('1.75') / rf.BASELINE_EE:.6%}"}
    assert "| 2001 | 4 | 1.7500 |" in out
    # a.com is his 2001 and c.net is attested 2001; b.com is held only in 2000
    assert ": 2 records  0.7500  (60.0% of the hostname half)" in out
    (netnew / "1996.txt").unlink()
    with pytest.raises(SystemExit, match="lacks 1996.txt: run ark export --claim"):
        rf.main()
    # `--verify` refuses the round when a shipped line is his for that year, by exact name
    assert rf.already_in_his_files() == 0
    _write(netnew, {"2000.txt": "b.com\n", "2001.txt": "A.com\nd.com\n"})
    assert rf.already_in_his_files() == 1


def _store_beside_his_release(folder: Path):
    """new.com and old.com are net-new, already-his.com is his that year, rested.com his in 1997
    only, nocapture.com has no capture, and u.com and gone.com (his) wait to be dated."""
    (folder / "1997.txt").write_bytes(text(["already-his.com", "gone.com", "rested.com"]))
    held.prepare(folder)
    conn = connect(":memory:")
    init_db(conn)
    cdx, usenet = (ensure_source(conn, n, "timestamped") for n in ("ia_cdx", "usenet_mention"))

    def dated(name: str, year: int, kind: str, value: str, method=None) -> None:
        add_candidate(conn, name, cdx)
        assign_year(conn, record_evidence(conn, name, cdx, year, kind, value, None, method))

    for name, year in (("new.com", 1999), ("old.com", 2000), ("already-his.com", 1999)):
        dated(name, year, "cdx_timestamp", capture(name, year), WEB_METHOD)
    dated("rested.com", 1999, "cdx_timestamp", capture("rested.com", 1999), WEB_METHOD)
    dated("nocapture.com", 1999, "whois_creation", "1999-03-01")
    for name in ("u.com", "gone.com"):
        add_candidate(conn, name, usenet)
    for name in ("u.com", "gone.com", "new.com"):
        record_evidence(conn, name, usenet, 1998, "artifact_listing", f"news {name}")
    since = "TIMESTAMPTZ '1999-06-01 00:00:00+00'"
    conn.execute(f"UPDATE domain_year SET verified_at = {since} WHERE domain = 'old.com'")
    return conn


def test_the_round_and_report_figures_count_only_what_ships_and_he_lacks(
    his_files, tmp_path, monkeypatch
) -> None:
    """A pair counts only when the export ships it: an exact-name capture he lacks that year."""
    _write(tmp_path, {POOL: "a.edu\nb.com\nc.org\n"})
    common = {"DB_TEMP_DIR": str(tmp_path / "tmp"), "english_weights": lambda: {"com": D("0.5")}}
    rf = _script("round_figures", monkeypatch, SINCE="2000-01-01 00:00:00+00", **common)
    report = _script("report_figures", monkeypatch, **common)
    monkeypatch.setattr(report, "CANDIDATES_PATH", tmp_path / POOL)
    m = rf.increment(_store_beside_his_release(his_files))
    # new.com and rested.com in 1999; old.com was verified before the round; u.com is held
    assert (m["pairs"], m["ee"], m["domains"], m["held"]) == (2, D("1.0"), 2, 1)
    assert m["by_source"] == {"ia_cdx": [2, D("1.0")]}
    f = report.figures(_store_beside_his_release(his_files))
    assert (f["netnew_pairs"], f["netnew_unique_domains"], f["ee_netnew"]) == (3, 3, D("1.5"))
    assert f["netnew_by_year"] == f["capture_backed_by_year"] == {1999: 2, 2000: 1}
    assert f["netnew_domains_absent_from_baseline"] == 2  # rested.com is his in 1997
    assert [(s["source"], s["master"], s["pairs"]) for s in f["by_source"]] == [("ia_cdx", 1, 3)]
    assert f["baseline_by_year"] == {1996: 2, 1997: 3, 1998: 1, 1999: 2, 2000: 1, 2001: 2}
    assert set(f["hostname_lines_by_year"]) == set(f["baseline_by_year"])
    assert f["candidate_pool"] == 3
    assert f["store"] == dict(pairs_total=5, domains_total=7, evidence_rows=8, ingested_files=0)
    (tmp_path / POOL).unlink()
    with pytest.raises(SystemExit, match=f"{POOL} is missing"):
        report.figures(connect(":memory:"))


def test_the_round_state_quotes_field_5_from_files_and_never_opens_the_store(
    tmp_path, monkeypatch, capsys
) -> None:
    figures = "3. Increment : 1,234 records\n4. EE : 3,456.7800\n5. EE growth : 0.252350%\n"
    calls = []
    paths = dict(ROOT=tmp_path, OUT=tmp_path / "ROUND.md", BRIEF=tmp_path / "brief.json")
    run = lambda cmd, timeout: calls.append(cmd) or figures  # noqa: E731
    brs = _script("build_round_state", monkeypatch, run=run, **paths)
    monkeypatch.setattr(brs, "pending_approvals", lambda: [])
    monkeypatch.setattr("ark.db.connect_read_only_patiently", REFUSE)
    monkeypatch.setattr(duckdb, "connect", REFUSE)
    stamp = json.dumps({"baseline": brs.CURRENT_BASELINE_MARKER})
    _write(tmp_path / "output/netnew", {"2001.txt": "d.com\n", "export_stamp.json": stamp})
    monkeypatch.setattr(sys, "argv", ["build_round_state.py"])
    brs.main()
    page, brief = brs.OUT.read_text(), json.loads(brs.BRIEF.read_text())
    assert calls == [["uv", "run", "python", "scripts/round/round_figures.py"]]
    assert (brief["field5_percent"], brief["waiting_on_human"]) == ("0.252350", {"approvals": 0})
    assert re.search(r"^5\. .*: (.+)$", page, re.M).group(1) == "0.252350%"
    monkeypatch.setattr(sys, "argv", ["build_round_state.py", "--check"])
    brs.main()
    assert "is current" in capsys.readouterr().out
    _write(tmp_path / "output/netnew", {"2001.txt": "e.com\n"})
    with pytest.raises(SystemExit, match="is stale"):
        brs.main()
    assert "netnew/2001.txt: changed" in capsys.readouterr().out
    (tmp_path / "output/netnew/export_stamp.json").unlink()  # an unstamped export is not quoted
    monkeypatch.setattr(sys, "argv", ["build_round_state.py"])
    with pytest.raises(SystemExit, match="no export stamp"):
        brs.main()
    assert "field5_percent" not in json.loads(brs.BRIEF.read_text())
