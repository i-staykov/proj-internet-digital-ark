"""The annual claim is website evidence: the method decides it, an error capture never does, and
a record's row captures exactly the name it dates."""

import gzip
import json
from pathlib import Path

import duckdb
import pytest

from ark.bulk import ingest_files
from ark.checks import collect_checks
from ark.db import init_db
from ark.evidence_types import MASTER_TYPES, WEB_METHODS, qualifies_sql, web_evidence_sql
from ark.export import export_all
from ark.hostnames import ingest_hostname_journal, retract_error_captures, writes_hostname_years
from ark.sources import SOURCES

WAYBACK = "https://web.archive.org/web"
MIRROR = "https://github.com/attrition-org/web-hack-mirror/blob/main/mirror/1999/05/01"
T1, T2, SITE = "19990412235959", "20010704120000", "http://example.com/"
# registry, zone, WHOIS, ISC DNS, mail, Usenet, a textual mention, a per-year capture count,
# his own baseline, one admitted by status alone, and a method invented tomorrow
CANDIDATE_METHODS = """usenet_server_written_header published_registry_creation_dates
isc_domain_survey registry_zone_list_wayback_capture registry_listing_capture ia_domain_year_census
ncsa_whats_new_pages prior_task nypw_timemap_non_200 a_method_invented_tomorrow""".split()
JUDGED_WEB = """attrition_defacement_mirror_index nypw_first_capture_index nypw_firstcdx_hostgrain
nypw_timemap ukwa_host_link_graph""".split()


def wayback(stamp: str, original: str) -> str:
    return f"{WAYBACK}/{stamp}/{original}"


def test_the_allowlist_fails_closed_and_the_predicate_is_one_bracketed_whole() -> None:
    assert not WEB_METHODS & set(CANDIDATE_METHODS)
    assert set(JUDGED_WEB) <= WEB_METHODS and "prior_reused" not in MASTER_TYPES
    # on the alias it was given, so a caller may AND it into any query without parenthesising
    sql = web_evidence_sql("w")
    assert sql.startswith("(w.acquisition_method IN (") and sql.count("(") == sql.count(")")


# One row per value format a web method writes, each dating `example.com`: naming exactly that
# name on a 2xx or 3xx passes; another host, an error status or no host fails.
FORMATS = [
    # a capture names its host last, with the status of a non-200 before it
    ("ia_cdx_domain_sweep", f"cdx capture {T1} example.com", None, True),
    ("ia_cdx_domain_sweep", f"cdx capture {T1} www.example.com", None, False),
    ("early_web_hostgrain", f"cdx capture {T1} status 302 example.com", None, True),
    ("nypw_timemap_hostgrain", f"cdx capture {T1} status 404 example.com", None, False),
    ("bulk_cdx_file", f"cdx capture {T1} status 503 example.com", None, False),
    # a link graph names its target last; its source form names none
    ("ukwa_host_link_graph", "host_link_graph:1999 example.com", None, True),
    ("ukwa_host_link_graph", "host_link_graph:1999 other.com", None, False),
    ("ukwa_host_link_graph", "host_link_graph:1999", None, False),
    # a bare stamp takes its URL's host, without case, port, user or trailing dot, and only
    # when the URL carries the same stamp
    ("bulk_cdx_file", T1, wayback(T1, "http://Example.COM:80/"), True),
    ("arquivo_cdxj", T1, f"https://arquivo.pt/wayback/{T1}/http://u@example.com./x", True),
    ("bl_geoindex_extract", T1, wayback(T1, "http://www.example.com/"), False),
    ("bulk_cdx_file", T1, wayback(T2, SITE), False),
    ("bulk_cdx_file", T1, None, False),
    # a TimeMap stamp the same way; the method admitted by its status takes 2xx and 3xx alone
    ("nypw_first_capture_index", f"nypw first capture {T1}", wayback(T1, SITE), True),
    ("nypw_timemap", f"nypw timemap capture {T1}", wayback(T1, "http://other.com/"), False),
    *(
        (
            "nypw_timemap_non_200",
            f"nypw timemap capture status {s} {T1}",
            wayback(T1, SITE),
            s < "4",
        )
        for s in ("206", "301", "302", "404", "500")
    ),
    ("isc_domain_survey", f"nypw timemap capture status 301 {T1}", wayback(T1, SITE), False),
    # a defacement mirror names its host in its path
    ("attrition_defacement_mirror_index", "attrition", f"{MIRROR}/example.com/", True),
    ("attrition_defacement_mirror_index", "attrition", f"{MIRROR}/www.example.com/", False),
    # a year alone names no host, and an untaught format fails closed beside a URL naming it
    ("ia_cdx_collapsed_query", "cdx capture 1999", None, False),
    ("wayback_availability", "available 19990101", wayback(T1, SITE), False),
    # the exact host under a method that is not web, or under none
    ("internic_zone_ns_target", f"cdx capture {T1} example.com", None, False),
    (None, f"cdx capture {T1} example.com", None, False),
]


def test_a_record_ships_only_on_a_2xx_or_3xx_capture_of_exactly_its_own_name() -> None:
    """Driven through DuckDB, and never unknown, so `NOT (...)` in a caller keeps every row that
    fails. A wildcard vhost answers 404 for any name pointed at it."""
    conn = duckdb.connect()
    text = " VARCHAR, ".join(("domain", "acquisition_method", "evidence_value", "evidence_url"))
    conn.execute(f"CREATE TABLE evidence (evidence_id INT, {text} VARCHAR)")
    rows = [(n, "example.com", *row[:3]) for n, row in enumerate(FORMATS)]
    conn.executemany("INSERT INTO evidence VALUES (?, ?, ?, ?, ?)", rows)
    sql = f"SELECT {qualifies_sql('e', 'e.domain')} FROM evidence e ORDER BY evidence_id"
    for (passes,), row in zip(conn.execute(sql).fetchall(), FORMATS, strict=True):
        assert passes is row[3], row


def _q(conn: duckdb.DuckDBPyConnection, sql: str) -> list[tuple]:
    return conn.execute(sql).fetchall()


def _failing(conn: duckdb.DuckDBPyConnection, **kw) -> list[str]:
    return [r["name"] for r in collect_checks(conn, Path("no-such-export"), **kw) if not r["ok"]]


def test_only_a_bare_link_target_ships_and_the_rest_are_candidates(tmp_path, his_files) -> None:
    """A dated link-graph record dates its target; a `www.` or deeper target dates that host."""
    bare = SOURCES["ukwa_link_target_bare"]
    assert bare.evidence_type in MASTER_TYPES and bare.acquisition_method in WEB_METHODS
    assert SOURCES["ukwa_link_target"].is_candidate_only, "its collapsed rows name no host"
    targets = (
        "1999 bare-ark-test.com,1999 www.www-ark-test.com,2000 deep.sub-ark-test.org,1997 www.il"
    )
    graph = tmp_path / "host-linkage.tsv"
    graph.write_text("".join(f"{t}\t1\n".replace(" ", "|www.src.uk|") for t in targets.split(",")))
    init_db(conn := duckdb.connect())
    for key in ("ukwa_link_target", "ukwa_link_target_bare"):
        ingest_files(conn, SOURCES[key], [graph], report_dir=tmp_path / "reports")
    assert _q(conn, "SELECT domain, assigned_year FROM domain_year") == [
        ("bare-ark-test.com", 1999)
    ]
    netnew = tmp_path / "netnew"
    export_all(conn, netnew, tmp_path / "cand.txt", tmp_path / "reports", tmp_path / "prov")
    assert (netnew / "1999.txt").read_text().split() == ["bare-ark-test.com"]
    claim = set((netnew / "candidate_additions.txt").read_text().split())
    assert {"sub-ark-test.org", "www-ark-test.com"} <= claim and "bare-ark-test.com" not in claim
    assert all(r["ok"] for r in collect_checks(conn, netnew, baseline=his_files))


ERR, OK, Y2K, WWW = "19990101000000", "19990601000000", "20000601000000", "http://www.example.com/"
YEARS = (1999, 2000, 2001)
CAPTURES = [
    ("http://www.example.com/", "19980301000000"),
    ("http://shop.example.com/x", "19980415120000"),
    ("http://example.com/", "19980102000000"),
    ("http://www.example.com/a", "19990101000000"),
]


def _journal(directory: Path, rows: list[tuple[str, ...]], name: str) -> Path:
    """One capture journal; a row is `(url, ts)` or `(url, ts, status)`."""
    lines = (json.dumps(dict(zip(("url", "timestamp", "status"), r, strict=False))) for r in rows)
    (path := directory / name).write_bytes(gzip.compress("\n".join(lines).encode() + b"\n"))
    return path


def _read(conn, directory: Path, rows, name: str = "sweep_test.jsonl.gz") -> dict:
    return ingest_hostname_journal(conn, _journal(directory, rows, name))


def _values(conn: duckdb.DuckDBPyConnection) -> dict[str, str]:
    join = "hostname_year JOIN evidence USING (evidence_id)"
    return dict(_q(conn, f"SELECT hostname, evidence_value FROM {join}"))


def _shipped(conn: duckdb.DuckDBPyConnection) -> list[tuple[str, int]]:
    join = "hostname_year hy JOIN evidence e USING (evidence_id)"
    screen = qualifies_sql("e", "hy.hostname")
    return _q(conn, f"SELECT hostname, assigned_year FROM {join} WHERE {screen} ORDER BY ALL")


@pytest.mark.parametrize("backwards", [False, True], ids=["error-read-first", "ok-read-first"])
def test_an_error_capture_is_a_candidate_and_a_2xx_or_3xx_of_the_year_wins(tmp_path, backwards):
    """A 4xx or 5xx keeps its status in the row, a candidate; a 2xx or 3xx of the host-year is
    quoted instead, from any journal; an error lane refuses a 200."""
    shop, www, d, g, c = (f"http://{h}.example.com/" for h in ("shop", "www", "d", "g", "c"))
    journals = [
        ("nypw_status_t", [(shop, ERR, "404"), (shop, OK, "302"), (d, ERR, "500")]),
        ("early_web_nonok_status_t", [(www, ERR, "404")]),
        ("early_web_3xx_status_t", [(www, OK, "302")]),
        ("hostcdx_t_4xx", [(g, ERR, "403"), (c, ERR, "200")]),
    ]
    init_db(conn := duckdb.connect())
    order = journals[::-1] if backwards else journals
    stats = [_read(conn, tmp_path, rows, f"{name}.jsonl.gz") for name, rows in order]
    assert sum(s.get("status_mismatch", 0) for s in stats) == 1
    assert _values(conn) == {
        "shop.example.com": f"cdx capture {OK} shop.example.com",
        "www.example.com": f"cdx capture {OK} www.example.com",
        "d.example.com": f"cdx capture {ERR} status 500 d.example.com",
        "g.example.com": f"cdx capture {ERR} status 403 g.example.com",
    }
    assert _shipped(conn) == [("shop.example.com", 1999), ("www.example.com", 1999)]
    assert not _q(conn, "FROM domain_year") and not _failing(conn)


def test_a_status_lane_without_statuses_is_refused_whole(tmp_path) -> None:
    """NYPW and Early Web rows are cut from CDX holding a status; a sweep asked for 2xx and 3xx."""
    init_db(conn := duckdb.connect())
    for name in ("nypw_t_hostgrain", "early_web_t_hostgrain", "x_4xx"):
        assert _read(conn, tmp_path, CAPTURES, f"{name}.jsonl.gz")["refused"] is True, name
    for table in ("hostname_year", "evidence", "ingested_file"):
        assert not _q(conn, f"FROM {table}"), table
    assert _read(conn, tmp_path, CAPTURES)["hostname_year_rows"] == 3


def test_a_host_capture_dates_that_host_alone_and_a_dns_lane_writes_no_record(tmp_path) -> None:
    """Neither `www.<parent>` nor a host beneath it dates the parent, and a lane keeps its own
    row beside Early Web's registrable-grain one. A DNS lane sees no host serving web content."""
    init_db(conn := duckdb.connect())
    stats = _read(conn, tmp_path, CAPTURES)
    assert (stats["hostname_year_candidates"], stats["hostname_year_rows"]) == (3, 3)
    (cdx := tmp_path / "ew.cdx").write_text(f"com,example,www)/ {Y2K} {WWW} text/html 200 X 1\n")
    banked = ingest_files(conn, SOURCES["early_web"], [cdx], report_dir=tmp_path)
    lane = _read(conn, tmp_path, [(WWW, Y2K, "200")], "early_web_t.jsonl.gz")
    assert (banked["evidence_rows"], lane["evidence_rows"], lane["hostname_year_rows"]) == (1, 1, 1)
    www = [("www.example.com", year) for year in (1998, 1999, 2000)]
    assert _shipped(conn) == [("shop.example.com", 1998), *www]
    assert not _q(conn, "FROM domain_year") and not _failing(conn)
    lanes = ("isc_survey_hostnames", "ripe_nserver_hostnames", "internic_zone_hostnames")
    assert not any(map(writes_hostname_years, lanes)) and writes_hostname_years("ia_cdx_hostnames")


def test_every_row_names_its_journal_and_line_and_a_repeat_adds_no_row(tmp_path) -> None:
    """The line is the journal's own, and one row per host-year whichever file or source repeats
    it; 1995 is outside the window."""
    init_db(conn := duckdb.connect())
    rows = [*CAPTURES, ("http://old.example.com/", "19950101000000")]
    first = _read(conn, tmp_path, rows)
    conn.execute("DELETE FROM ingested_file")
    repeats = [_read(conn, tmp_path, rows, n) for n in ("sweep_t.gz", "arquivo_ia_0.gz")]
    assert [s["evidence_rows"] for s in (first, *repeats)] == [3, 0, 0]
    assert first["out_of_window"] == 1
    cited = "SELECT evidence_value, source_file, record_location FROM evidence ORDER BY 1"
    assert _q(conn, cited) == [
        ("cdx capture 19980301000000 www.example.com", "sweep_test.jsonl.gz", "line 1"),
        ("cdx capture 19980415120000 shop.example.com", "sweep_test.jsonl.gz", "line 2"),
        ("cdx capture 19990101000000 www.example.com", "sweep_test.jsonl.gz", "line 4"),
    ]


def _store_on_error_captures(tmp_path: Path, repoint: tuple[str, ...]) -> tuple:
    """Host-years and parent years banked before rows carried a status; the audit lists the 1999
    and 2000 captures as errors and names `repoint`, an error host-year's earliest 2xx."""
    init_db(conn := duckdb.connect())
    rows = [
        (f"http://{h}.example.com/", f"{y}0101000000", "200")
        for h, y in zip("abc", YEARS, strict=True)
    ]
    _read(conn, tmp_path, rows, "nypw_status_t.jsonl.gz")
    dated = "SELECT domain, evidence_year, evidence_id FROM evidence"
    conn.execute(f"INSERT INTO domain_year (domain, assigned_year, evidence_id) {dated}")
    errors = [("a.example.com", ERR, "404"), ("b.example.com", "20000101000000", "503")]
    for name, header, lines in (
        ("status_errors", "hostname\tts\tstatus\tfamily", [(*e, "nypw") for e in errors]),
        ("status_repoint", "hostname\tyear\tts\tfamily", [repoint]),
    ):
        text = "\n".join([header, *("\t".join(r) for r in lines)]) + "\n"
        (tmp_path / f"{name}.tsv.gz").write_bytes(gzip.compress(text.encode()))
    return conn, tmp_path / "status_errors.tsv.gz"


def _parent_years(conn: duckdb.DuckDBPyConnection) -> list[tuple[int]]:
    join = "domain_year dy JOIN evidence e USING (evidence_id)"
    return _q(conn, f"SELECT assigned_year FROM {join} WHERE {web_evidence_sql('e')} ORDER BY 1")


def test_a_record_on_an_error_capture_is_repointed_or_retracted_and_a_rerun_restores(tmp_path):
    """A host-year with a 2xx in the audited raw moves to it, the rest keep their row with its
    error status; a rerun restores a year another web family captured."""
    conn, audit = _store_on_error_captures(tmp_path, ("a.example.com", "1999", OK, "nypw"))
    checks = {r["name"]: r for r in collect_checks(conn, Path("no-such-export"), audit=audit)}
    assert checks["no_master_record_points_to_an_error_capture"]["offending"] == 4
    counted = retract_error_captures(conn, audit, write=False, netnew_dir=tmp_path)
    assert counted == {f"{t}_hit_{a}_nypw": 1 for t in ("hy", "dy") for a in ("repoint", "retract")}
    assert len(_shipped(conn)) == 3, "a dry run changes nothing"
    retract_error_captures(conn, audit, write=True, netnew_dir=tmp_path, journals=())
    cited = "SELECT source_file, record_location FROM evidence WHERE evidence_value = "
    repointed = [("status_repoint.tsv.gz", "hostname a.example.com year 1999")]
    assert _q(conn, f"{cited}'cdx capture {OK} a.example.com'") == repointed
    assert _values(conn) == {
        "a.example.com": f"cdx capture {OK} a.example.com",
        "b.example.com": "cdx capture 20000101000000 status 503 b.example.com",
        "c.example.com": "cdx capture 20010101000000 c.example.com",
    }
    assert _shipped(conn) == [("a.example.com", 1999), ("c.example.com", 2001)]
    assert _parent_years(conn) == [(1999,), (2001,)]
    exact = qualifies_sql("e", "dy.domain")
    assert not _q(conn, f"FROM domain_year dy JOIN evidence e USING (evidence_id) WHERE {exact}")
    assert not _failing(conn, audit=audit)
    (other := tmp_path / "other").mkdir()
    _journal(other, [("http://b.example.com/x", "20000301000000")], "suffix_example_com_t.jsonl.gz")
    stats = retract_error_captures(conn, audit, write=True, netnew_dir=tmp_path, journals=(other,))
    assert (stats["restored_by_another_web_family"], stats["left_on_an_error_capture"]) == (1, 0)
    assert ("b.example.com", 2000) in _shipped(conn)
    assert _parent_years(conn) == [(1999,), (2001,)], "2000 stays on its error row, a candidate"
    restored = [("suffix_example_com_t.jsonl.gz", "line 1")]
    assert _q(conn, f"{cited}'cdx capture 20000301000000 b.example.com'") == restored


def test_a_parent_year_moves_only_onto_a_master_row_and_a_same_second_capture_repoints(tmp_path):
    """A link target is candidate-only however web its method, so a retracted parent year stays
    on its error row; an Early Web 200 at the second NYPW answered 404 is a capture of its own."""
    conn, audit = _store_on_error_captures(tmp_path, ("a.example.com", "1999", ERR, "early_web"))
    conn.execute(
        "INSERT INTO evidence (domain, source_id, evidence_year, evidence_type, evidence_value, "
        "acquisition_method, source_file, record_location) SELECT 'example.com', min(source_id), "
        "2000, 'link_target', 'host_link_graph:2000', 'ukwa_host_link_graph', 'l.tsv', 'line 1' "
        "FROM source"
    )
    retract_error_captures(conn, audit, write=True, netnew_dir=tmp_path, journals=())
    assert _parent_years(conn) == [(1999,), (2001,)]
    method = "SELECT acquisition_method FROM hostname_year JOIN evidence USING (evidence_id)"
    assert _q(conn, f"{method} WHERE hostname = 'a.example.com'") == [("early_web_hostgrain",)]
    assert ("a.example.com", 1999) in _shipped(conn) and not _failing(conn, audit=audit)
