"""The scoreboard, the contribution tables and the round figures count what the export ships, net
of his files by exact name; corroboration counts distinct master sources of distinct lineages;
his quoted scores reproduce to the digit. One store is scored and exported once per module."""

import csv
import json
import re
import sys
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import duckdb
import pytest
from conftest import script
from his_release import HIS_YEARS, MARKER, WEB_METHOD, capture, stage, text

from ark import db, held
from ark import figures as fig
from ark.baseline import SUBMITTED_ROUNDS, awarded_score_of
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.english_share import weight_of
from ark.export import export_all
from ark.sources import SOURCES
from ark.stats import PROVENANCE_LINEAGE, collect_stats, format_stats

ROOT = Path(__file__).resolve().parents[1]
ROWS = {r[0]: r for r in SUBMITTED_ROUNDS}
YEARS = range(1996, 2002)
POOL = "candidate_unverified.txt"
REFUSE = Mock(side_effect=AssertionError("a default figure opened the store"))
# the names his files hold beyond the staged release's own
HIS = {1996: ["foo.com", "mixed.com"], 1997: ["base.com"]}
SOURCE_OF = {
    "cdx": "wayback_cdx", "bulk": "ia_cdx_bulk", "isc": "isc_survey", "zone": "registry_zone",
    "link": "ukwa_link_target", "a": "ia_cdx", "b": "early_web_cdx", "c": "arquivo_ia",
    "afnic": "afnic_fr", "new": "brand_new_source",
}  # fmt: skip
# (domain, year, source, type, value, method, dates), the tail defaulting to an exact-name web
# capture of `wayback_cdx` that dates its year; `bulk` fills years on names he holds
DEFAULT = ("cdx", "cdx_timestamp", None, WEB_METHOD, True)
OURS = [
    # his 1997 pair, on two rows of one source and one of another
    ("base.com", 1997, "cdx", "cdx_timestamp", "19970101000000", None, True),
    ("base.com", 1997, "cdx", "cdx_timestamp", "19970202000000", None, False),
    ("base.com", 1997, "isc", "artifact_listing", "isc-1997", None, False),
    ("base.com", 1998, "bulk"),
    ("mixed.com", 1999, "bulk"),
    *((name, 1998) for name in ("new.com", "real.com", "web.com", "exact.com")),
    ("new.com", 1998, "link", "link_target", "graph-row", None, False),
    ("corr.com", 2000),
    ("corr.com", 2000, "isc", "artifact_listing", "isc-2000", None, False),
    *(("found.com", year) for year in (1998, 1999)),
    ("rolled.com", 1999),
    ("exact.com", 1998, "cdx", "cdx_timestamp", capture("www.exact.com", 1998), WEB_METHOD, False),
    # what ships nowhere: `.info` before 2001, `.arpa`, a capture of another host, a zone list
    ("early.info", 1996),
    ("x.arpa", 1999),
    ("alias.com", 1998, "cdx", "cdx_timestamp", capture("www.alias.com", 1998)),
    ("zone.com", 1998, "zone", "artifact_listing", "zone", "registry_zone_list_wayback_capture"),
    # three sources of one lineage, then two lineages, one of them a source nobody mapped
    *(("ia-only.com", 1998, s, "cdx_timestamp", "19980101000000", None, True) for s in "abc"),
    ("two-lineage.fr", 1997, "isc", "artifact_listing", "1997-07", None, True),
    ("two-lineage.fr", 1997, "afnic", "whois_creation", "registered 01-01-1997..", None, False),
    ("unmapped.com", 1999, "new", "cdx_timestamp", "19990101000000", None, True),
    ("unmapped.com", 1999, "isc", "artifact_listing", "1999-07", None, False),
    # a hostname capture, which the year table counts beside the registrables
    ("found.com", 1998, "cdx", "cdx_timestamp", capture("shop.found.com", 1998), WEB_METHOD, False),
]  # fmt: skip


def _store() -> duckdb.DuckDBPyConnection:
    init_db(conn := connect(":memory:"))
    kind = {"link": "candidate_only"}
    sid = {k: ensure_source(conn, n, kind.get(k, "timestamped")) for k, n in SOURCE_OF.items()}
    for row in OURS:
        domain, year, source, etype, value, method, dates = row + DEFAULT[len(row) - 2 :]
        add_candidate(conn, domain, sid[source])
        value = capture(domain, year) if value is None else value
        eid = record_evidence(conn, domain, sid[source], year, etype, value, None, method)
        if dates:
            assign_year(conn, eid)
    shop = "SELECT 'shop.found.com', 'found.com', 1998, evidence_id FROM evidence WHERE"
    cols = "hostname, parent_domain, assigned_year, evidence_id"
    conn.execute(f"INSERT INTO hostname_year ({cols}) {shop} evidence_value LIKE '% shop.%'")
    # found and never dated: `.sucks` never existed in the window, and he holds the last two
    for name in ("cand.org", "never.sucks", "maybe.org", "held-candidate.com", "already-his.com"):
        add_candidate(conn, name, sid["cdx"])
    add_candidate(conn, "linked-only.com", sid["link"])
    record_evidence(conn, "linked-only.com", sid["link"], 1999, "link_target", "graph-row")
    return conn


@pytest.fixture(scope="module")
def scored(tmp_path_factory):
    root = tmp_path_factory.mktemp("stats")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(held, "HELD_ROOT", root / "held")
        for module in (db, held):
            patch.setattr(module, "DB_TEMP_DIR", str(root / "duckdb_tmp"))
        his = stage(root, {f"{y}.txt": text(sorted(HIS_YEARS[y] + n)) for y, n in HIS.items()})
        held.prepare(his)
        conn = _store()
        stats = collect_stats(conn, his)
        dirs = {"netnew_dir": root / "netnew", "report_dir": root / "reports"}
        export_all(conn, candidates_path=root / "c", provenance_dir=root, baseline=his, **dirs)
    return SimpleNamespace(root=root, his=his, stats=stats, **dirs)


def test_the_scoreboard_counts_only_what_the_export_ships(scored) -> None:
    """A pair counts when it ships: a web capture of exactly its name his file for that year lacks,
    and his `www.rolled.com` holds no `rolled.com`. Discovery and completeness partition it."""
    s = scored.stats
    shipped = {y: len((scored.netnew_dir / f"{y}.txt").read_text().split()) for y in YEARS}
    assert s["netnew_pairs_by_year"] == {y: n for y, n in shipped.items() if n}
    assert s["netnew_pairs_by_year"] == {1998: 6, 1999: 3, 2000: 1}
    assert (s["discovery_pairs"], s["completeness_pairs"], s["netnew_domains"]) == (8, 2, 7)
    assert s["ee_discovery_pairs"] + s["ee_completeness_pairs"] == s["ee_netnew"]
    # found.com earns two years and is one discovery
    assert s["ee_discovery_pairs"] - s["ee_netnew_domains"] == weight_of("found.com")
    # the store still holds every row; only the scored figures narrow, and the pool holds
    # none of his and no name whose TLD never existed in the window
    assert (s["total_domains"], s["total_pairs"], s["evidence_rows"]) == (22, 18, 29)
    assert (s["his_release"], s["baseline_domains"], s["candidate_pool"]) == (MARKER, 7, 3)
    # every pair the TLD filter ships, his or ours: early.info and x.arpa weigh nothing
    assert s["ee_assigned"] == 15 * weight_of("x.com") + weight_of("x.fr")
    out = format_stats(s)  # `ark stats` and ROUND.md show the per-year counts and the release
    assert "    1998: 6\n" in out and f"(measured against {MARKER}, so" in out


def test_corroboration_counts_distinct_master_sources_of_distinct_lineages(scored) -> None:
    """Candidate-only rows and a second row of one source add no source, and sources of one
    lineage confirm nothing independently; an unmapped source is a lineage of its own."""
    keys = ("avg_sources_per_pair", "corroborated_pairs", "baseline_corroborated")
    keys += ("independently_corroborated_pairs", "independently_corroborated_netnew")
    assert [scored.stats[k] for k in keys] == [1.3333, 5, 1, 4, 3]
    assert scored.stats["evidence_rows_by_lineage"]["internet_archive"] == 5
    by_type = {"cdx_timestamp": 21, "artifact_listing": 5, "link_target": 2, "whois_creation": 1}
    assert list(scored.stats["evidence_rows_by_type"].items()) == list(by_type.items())


def test_every_source_has_an_explicit_provenance_lineage() -> None:
    """An unclassified source counts as independent of everything and inflates the headline."""
    unclassified = {s.source_name for s in SOURCES.values()} - set(PROVENANCE_LINEAGE)
    assert not unclassified, f"classify these in PROVENANCE_LINEAGE: {sorted(unclassified)}"


def test_the_contribution_tables_reconcile_with_the_scoreboard(scored) -> None:
    """Conflating a net-new pair with a net-new domain zeroes every gap-filling source, a
    candidate-only row backs no pair, and a survey listing earns no annual year."""
    table = (scored.report_dir / "source_contribution.csv").read_text().splitlines()
    rows = {r["source"]: r for r in csv.DictReader(table)}
    pick = ("netnew_pairs", "netnew_domains", "pairs_backed", "candidate_domains")
    assert [rows["ia_cdx_bulk"][k] for k in pick] == ["2", "0", "2", "0"]
    assert [rows["wayback_cdx"][k] for k in pick[:2]] == ["8", "7"]
    assert [rows["ukwa_link_target"][k] for k in pick[2:]] == ["0", "1"]
    total = sum(int(r["netnew_pairs"]) for r in rows.values())
    assert total == scored.stats["netnew_pairs_total"] == 10
    table = (scored.report_dir / "year_growth.csv").read_text().splitlines()
    years = {r["year"]: r for r in csv.DictReader(table)}
    want = dict(base_unique="1", added_unique="7", merged_unique="8", growth_percent="700.0")
    assert years["1998"] == years["1998"] | want
    assert (years["1997"]["base_unique"], years["1997"]["added_unique"]) == ("2", "0")


def _script(name: str, monkeypatch, **attrs):
    module = script(f"round/{name}.py")
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
    scored = [r[0] for r in SUBMITTED_ROUNDS if fig.scored_under_rule(r[7])]
    assert scored == ["6", "7", "8", "9", "11"]
    assert fig.cumulative([D("6.884530"), D("6.302372")]) == D("13.186902")


def test_fill_report_quotes_his_sum_and_holds_no_day_arithmetic(scored, tmp_path, monkeypatch):
    """Its sum is of his own scores; its pool counts read the files that shipped and `held`."""
    monkeypatch.setattr(held, "HELD_ROOT", scored.root / "held")
    monkeypatch.setattr(held, "his_dir", lambda: scored.his)
    _write(tmp_path, {POOL: "a.edu\nb.com\nc.gov\nd.mil\ne.edu.au\n"})
    now = {"now_in_his_clock": lambda: "2026-09-03 10:00", "CANDIDATES_PATH": tmp_path / POOL}
    report = _script("fill_report", monkeypatch, **now)
    source = Path(report.__file__).read_text(encoding="utf-8")
    assert [t for t in ("date.today", "fromisoformat", "timedelta", ".days") if t in source] == []
    sentence = report.cumulative_sentence({}, D("1.5"))
    assert "score 6.88 + 6.302372 + 5.687792 + 0.944228 + 0.036881677 = 19.851273677" in sentence
    assert "Domain-Year Score: S = 10 x (1.500000 / 32) = 0.468750" in sentence
    assert "Candidate-Pool Score: S = 10 x (" in sentence and "?" not in sentence, sentence
    assert report.pool_restricted() == "3"
    init_db(conn := connect(tmp_path / "store.duckdb"))
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
    monkeypatch.setattr(rf, "EXTENDED", tmp_path / "missing")
    rf.main()
    assert "GATE. Core plus extended, 1996-2015           : 1.7500 = " in capsys.readouterr().out
    _write(tmp_path / "x/additions", {"2002.txt": "www.x.com\nx.com\n"})
    monkeypatch.setattr(rf, "EXTENDED", tmp_path / "x")
    rf.main()
    out = capsys.readouterr().out
    field = dict(re.findall(r"^([345])\. .*: (.+)$", out, re.M))
    assert field == {"3": "4 records", "4": "1.7500", "5": f"{D('1.75') / rf.BASELINE_EE:.6%}"}
    assert "| 2001 | 4 | 1.7500 |" in out and "| 2002 | 2 | 1.0000 |" in out
    # registrable domains first, then the hostnames beneath them, as in the core
    units = re.findall(r"^     (\w+) .*: 1 records  0\.5000$", out, re.M)
    assert units == ["registrable", "hostnames"]
    # The gate is core plus extended over his 1996 to 2015 total, the core alone never.
    gate = re.search(r"^GATE\. .*: 2\.7500 = ([0-9.]+)% of", out, re.M).group(1)
    assert gate == f"{D('2.75') / (rf.BASELINE_EE + rf.REVIEWER_EXTENDED_EE) * 100:.6f}"
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
    init_db(conn := connect(":memory:"))
    cdx, usenet = (ensure_source(conn, n, "timestamped") for n in ("ia_cdx", "usenet_mention"))
    for name, year in (("new.com", 1999), ("old.com", 2000), ("already-his.com", 1999),
                       ("rested.com", 1999), ("nocapture.com", 1999)):  # fmt: skip
        add_candidate(conn, name, cdx)
        kind, value, method = "cdx_timestamp", capture(name, year), WEB_METHOD
        if name == "nocapture.com":
            kind, value, method = "whois_creation", "1999-03-01", None
        assign_year(conn, record_evidence(conn, name, cdx, year, kind, value, None, method))
    for name in ("u.com", "gone.com", "new.com"):
        add_candidate(conn, name, usenet)
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
    conn = _store_beside_his_release(his_files)
    m = rf.increment(conn)
    # new.com and rested.com in 1999; old.com was verified before the round; u.com is held
    assert (m["pairs"], m["ee"], m["domains"], m["held"]) == (2, D("1.0"), 2, 1)
    assert m["by_source"] == {"ia_cdx": [2, D("1.0")]}
    f = report.figures(conn)
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
    figures += "GATE. Core plus extended : 4,000.0000 = 0.001944% of 205,789,506.8739, gate 5%\n"
    calls = []
    paths = dict(ROOT=tmp_path, OUT=tmp_path / "ROUND.md", BRIEF=tmp_path / "brief.json")
    run = lambda cmd, timeout: calls.append(cmd) or figures  # noqa: E731
    brs = _script("build_round_state", monkeypatch, run=run, **paths)
    monkeypatch.setattr(brs, "pending_approvals", lambda: [])
    monkeypatch.setattr(brs.extended, "INPUTS", {"*": str(tmp_path / "raw/*/*.jsonl*")})
    monkeypatch.setattr("ark.db.connect_read_only_patiently", REFUSE)
    monkeypatch.setattr(duckdb, "connect", REFUSE)
    stamp = json.dumps({"baseline": brs.CURRENT_BASELINE_MARKER})
    _write(tmp_path / "output/netnew", {"2001.txt": "d.com\n", "export_stamp.json": stamp})
    monkeypatch.setattr(sys, "argv", ["build_round_state.py"])
    brs.main()
    page, brief = brs.OUT.read_text(), json.loads(brs.BRIEF.read_text())
    assert calls == [["uv", "run", "python", "scripts/round/round_figures.py"]]
    assert (brief["field5_percent"], brief["waiting_on_human"]) == ("0.252350", {"approvals": 0})
    assert (brief["gate_percent"], brief["gate_ee"]) == ("0.001944", 4000.0)
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
    assert "gate_percent" not in json.loads(brs.BRIEF.read_text())
    # nor is an extended export written against another release
    manifest = json.dumps({"baseline": "merged-other", "inputs": [], "globs": {}})
    _write(
        tmp_path / "output",
        {"netnew/export_stamp.json": stamp, "extended_years/manifest.json": manifest},
    )
    with pytest.raises(SystemExit, match="extended_years is stale, written against merged-other"):
        brs.main()
    assert "gate_percent" not in json.loads(brs.BRIEF.read_text())
