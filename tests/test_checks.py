"""Integrity checks: a clean store passes; a planted violation is caught."""

from pathlib import Path

import duckdb
import pytest
from his_release import WEB_METHOD, capture, stage, text

from ark import held
from ark.checks import collect_checks, format_checks
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence

# where a fixture row says it was read from, as every row the store writes does
AT = {"source_file": "fixture.txt", "record_location": "record 1"}


def _clean_store() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    art = ensure_source(conn, "isc_survey", "timestamped")
    add_candidate(conn, "example.com", cdx)
    assign_year(
        conn,
        record_evidence(conn, "example.com", cdx, 1998, "cdx_timestamp", "19980101000000", **AT),
    )
    add_candidate(conn, "sub.co.uk", art)
    assign_year(
        conn, record_evidence(conn, "sub.co.uk", art, 2000, "artifact_listing", "isc-2000", **AT)
    )
    return conn


def _results_by_name(
    conn: duckdb.DuckDBPyConnection,
    netnew_dir: Path | None = None,
    baseline: Path | None = None,
) -> dict[str, dict]:
    # Never the real output/: a check that reads files must be pointed at a
    # fixture, or the suite asserts against the actual deliverable. Every
    # file-reading directory needs its own override, and a new check that adds
    # one without threading it here will quietly start doing exactly that.
    results = collect_checks(conn, netnew_dir or Path("no-such-export"), baseline=baseline)
    return {r["name"]: r for r in results}


def test_clean_store_passes_all_checks() -> None:
    results = collect_checks(_clean_store(), Path("no-such-export"))
    # Pinned, not counted loosely: a check silently dropped
    # from the gate is the failure this assertion exists to catch.
    assert len(results) == 23, [r["name"] for r in results]
    assert all(r["ok"] for r in results), [r["name"] for r in results if not r["ok"]]


def test_detects_an_internationalised_tld() -> None:
    """No `xn--` TLD existed before 2010, so none can hold a 1996-2001 year.

    Seventeen shipped: `domain_creation_bulk` carries `.xn--fiqs8s` and `.xn--fiqz9s`
    names with registry creation dates in 2000 and 2001, CNNIC having run
    Chinese-character domains before ICANN delegated the TLD. What caught them was the
    reviewer's validator, whose hostname regexp requires a letters-only TLD: they scored
    zero for him and full weight for us, and `round_figures.py --verify` refused the round
    over the 0.3150 discrepancy.
    """
    conn = _clean_store()
    src = ensure_source(conn, "domain_creation_bulk", "timestamped")
    idn = "xn--tfrxfu2p.xn--fiqs8s"
    add_candidate(conn, idn, src)
    assign_year(
        conn, record_evidence(conn, idn, src, 2000, "whois_creation", "registry created 2000-11-06")
    )
    results = _results_by_name(conn)
    assert results["no_idn_tld_in_window"]["ok"] is False
    assert results["no_idn_tld_in_window"]["offending"] == 1


def test_a_hyphenated_ascii_domain_is_not_mistaken_for_an_idn() -> None:
    """The check keys on the TLD, not on `xn--` appearing anywhere in the name."""
    conn = _clean_store()
    src = ensure_source(conn, "isc_survey", "timestamped")
    for name in ("xn--not-a-tld.com", "some-xn--thing.org"):
        add_candidate(conn, name, src)
        assign_year(conn, record_evidence(conn, name, src, 1999, "artifact_listing", "isc-1999"))
    assert _results_by_name(conn)["no_idn_tld_in_window"]["ok"] is True


def test_detects_candidate_backed_assignment() -> None:
    conn = _clean_store()
    # a candidate-only (link_target) evidence row, then a domain_year that
    # references it directly, bypassing assign_year's guard
    add_candidate(conn, "leak.net", ensure_source(conn, "ukwa_link", "candidate_only"))
    link = ensure_source(conn, "ukwa_link", "candidate_only")
    ev = record_evidence(conn, "leak.net", link, 1999, "link_target", "graph-row")
    conn.execute(
        "INSERT INTO domain_year (domain, assigned_year, evidence_id) VALUES (?, ?, ?)",
        ["leak.net", 1999, ev],
    )
    results = _results_by_name(conn)
    assert results["no_candidate_leakage"]["ok"] is False
    assert results["no_candidate_leakage"]["offending"] == 1
    # and the pair has no master-eligible evidence either
    assert results["every_pair_has_master_evidence"]["ok"] is False


def test_detects_evidence_year_disagreeing_with_its_value() -> None:
    conn = _clean_store()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "mislabelled.com", cdx)
    # the timestamp says 1997 but the row is filed under 1999
    assign_year(
        conn,
        record_evidence(conn, "mislabelled.com", cdx, 1999, "cdx_timestamp", "19970101000000"),
    )
    results = _results_by_name(conn)
    assert results["evidence_year_matches_its_value"]["ok"] is False
    assert results["evidence_year_matches_its_value"]["offending"] == 1


def test_registration_spans_are_exempt_from_the_year_match() -> None:
    conn = _clean_store()
    # AFNIC states a span, so its value names two years and neither need equal
    # the year it evidences; that is the documented mechanism, not a defect
    afnic = ensure_source(conn, "afnic_fr", "timestamped")
    add_candidate(conn, "span.fr", afnic)
    for year in (1999, 2000, 2001):
        assign_year(
            conn,
            record_evidence(
                conn, "span.fr", afnic, year, "whois_creation", "registered 16-03-1998..active"
            ),
        )
    results = _results_by_name(conn)
    assert results["evidence_year_matches_its_value"]["ok"] is True

    # the same shape from any other source is NOT exempt
    rdap = ensure_source(conn, "rdap", "timestamped")
    add_candidate(conn, "notexempt.com", rdap)
    assign_year(
        conn,
        record_evidence(conn, "notexempt.com", rdap, 2001, "whois_creation", "rdap creation 1998"),
    )
    assert _results_by_name(conn)["evidence_year_matches_its_value"]["ok"] is False


def _his_release(tmp_path: Path) -> Path:
    """His release, with `both.com` in his 1998 file beside the names he already holds."""
    folder = stage(tmp_path / "release", {"1998.txt": text(["already-his.com", "both.com"])})
    held.prepare(folder)
    return folder


def test_detects_an_addition_his_file_holds(tmp_path: Path) -> None:
    """Held by him is the exact name in his file for the year. We may date a name he holds,
    and the store keeps our row; what must never happen is that name in our exported file for
    the same year, where it would be counted a second time. Hostname files are held alike.
    """
    his = _his_release(tmp_path)
    netnew = tmp_path / "netnew"
    netnew.mkdir()
    (netnew / "1998.txt").write_text("example.com\n", encoding="utf-8")
    # his other years do not count against 1998: `early.his.org` is his in 1996 only
    (netnew / "1998_hostnames.txt").write_text("early.his.org\n", encoding="utf-8")
    conn = _clean_store()
    assert _results_by_name(conn, netnew, his)["additions_not_double_counted"]["ok"] is True

    # shipping his name as an addition is the violation, in either file
    (netnew / "1998.txt").write_text("both.com\nexample.com\n", encoding="utf-8")
    (netnew / "1996_hostnames.txt").write_text("early.his.org\n", encoding="utf-8")
    results = _results_by_name(conn, netnew, his)
    assert results["additions_not_double_counted"]["ok"] is False
    assert results["additions_not_double_counted"]["offending"] == 2


def test_the_double_count_check_fails_closed_and_the_others_still_report(tmp_path: Path) -> None:
    """His files not prepared, or a file of ours `comm` would misread, is a failure carrying
    its reason, never a pass, and the rest of the gate still runs."""
    netnew = tmp_path / "netnew"
    netnew.mkdir()
    (netnew / "1998_hostnames.txt").write_text("www.example.com\n", encoding="utf-8")
    results = collect_checks(_clean_store(), netnew)
    assert len(results) == 23
    by_name = {r["name"]: r for r in results}
    missing = by_name.pop("additions_not_double_counted")
    assert missing["ok"] is False
    assert "run uv run ark intake" in missing["error"]
    assert all(r["ok"] for r in by_name.values()), [n for n, r in by_name.items() if not r["ok"]]
    report = format_checks(results)
    assert f"[FAIL] additions_not_double_counted: {missing['error']}" in report
    assert report.endswith("FAILED: additions_not_double_counted")

    his = _his_release(tmp_path)
    (netnew / "1998.txt").write_text("example.com\nboth.com\n", encoding="utf-8")
    unsorted = _results_by_name(_clean_store(), netnew, his)["additions_not_double_counted"]
    assert unsorted["ok"] is False
    assert "not LC_ALL=C sorted" in unsorted["error"]


def test_a_registrable_line_needs_a_web_row_of_ours_capturing_that_exact_name(
    tmp_path: Path,
) -> None:
    """A registrable line ships on a capture of exactly that name in that year. A capture of
    `www.` or of any host beneath it dates that host, not the registrable; neither does a
    capture that names no host, an error capture, or a row of another year."""
    conn = _clean_store()
    web = ensure_source(conn, "cdx_sweep", "timestamped")
    rows = [
        ("exact.com", 1998, capture("exact.com", 1998), WEB_METHOD),
        ("www-only.com", 1998, capture("www.www-only.com", 1998), WEB_METHOD),
        ("deep.com", 1998, capture("shop.deep.com", 1998), WEB_METHOD),
        ("yearless.com", 1998, "cdx capture 1998", "ia_cdx_collapsed_query"),
        ("error.com", 1998, "cdx capture 19980601120000 status 404 error.com", WEB_METHOD),
        ("elsewhen.com", 1997, capture("elsewhen.com", 1997), WEB_METHOD),
    ]
    for domain, year, value, method in rows:
        add_candidate(conn, domain, web)
        record_evidence(conn, domain, web, year, "cdx_timestamp", value, acquisition_method=method)
    netnew = tmp_path / "netnew"
    netnew.mkdir()
    (netnew / "1998.txt").write_text("exact.com\n", encoding="utf-8")
    check = "a_registrable_record_has_its_own_capture"
    assert _results_by_name(conn, netnew)[check]["ok"] is True
    shipped = sorted(domain for domain, *_ in rows)
    (netnew / "1998.txt").write_text("".join(f"{d}\n" for d in shipped), encoding="utf-8")
    assert _results_by_name(conn, netnew)[check]["offending"] == len(rows) - 1


def test_missing_export_is_skipped_not_silently_passed(tmp_path: Path) -> None:
    result = _results_by_name(_clean_store(), tmp_path / "absent")
    assert result["additions_not_double_counted"]["skipped"]
    assert "ark export" in result["additions_not_double_counted"]["skipped"]


def test_empty_export_is_skipped_not_an_internal_error(tmp_path: Path) -> None:
    """The day a new baseline lands, every annual file exports empty. DuckDB 1.5 reports a
    `read_csv` over files with no rows as an internal error ("must return at least one
    column"). That reads as skipped, never as a crash and never as a pass.
    """
    for year in range(1996, 2002):
        (tmp_path / f"{year}.txt").write_text("", encoding="utf-8")
    results = _results_by_name(_clean_store(), tmp_path)
    for name in ("additions_not_double_counted", "no_arpa_in_the_shipped_files"):
        assert "empty" in results[name]["skipped"], name


def test_detects_master_evidence_left_unassigned() -> None:
    conn = _clean_store()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "orphan.com", cdx)
    # evidence recorded but assign_year never called: the domain would sit in the
    # candidate pool while already holding proof of 1996
    record_evidence(conn, "orphan.com", cdx, 1996, "cdx_timestamp", "19960303000000", **AT)
    # a row naming a host beneath its domain dates that host, never the domain, whatever its
    # lane writes before the host
    isc = ensure_source(conn, "isc_survey_hostnames", "timestamped")
    add_candidate(conn, "x.net", isc)
    for value in ("isc survey 1997-01 host Mail.X.net", "cdx capture 19970101000000 www.x.net"):
        record_evidence(conn, "x.net", isc, 1997, "artifact_listing", value, **AT)
    results = _results_by_name(conn)
    assert results["nothing_earned_is_left_unassigned"]["ok"] is False
    assert results["nothing_earned_is_left_unassigned"]["offending"] == 1


def _planted(conn: duckdb.DuckDBPyConnection, check: str) -> dict:
    """The one failing check's result, every other check still passing."""
    results = _results_by_name(conn)
    assert [n for n, r in results.items() if not r["ok"]] == [check]
    return results[check]


SERVING, OWN = "hostname_observed_serving_web", "a_www_record_has_its_own_evidence"


@pytest.mark.parametrize(
    "source,method,named,failing",
    [
        ("isc_survey_hostnames", None, "www.x.com", [SERVING]),
        ("fleet_x_hostnames", "internic_zone_ns_target", "www.x.com", [SERVING]),
        ("fleet_x_hostnames", "bulk_cdx_file", "www.x.com", []),
        ("ia_cdx_hostnames", None, "x.com", [OWN]),
    ],
    ids=["dns-lane", "fleet-read-not-web", "fleet-read-web", "www-on-its-parent"],
)
def test_a_host_record_needs_a_web_lane_and_evidence_naming_it(source, method, named, failing):
    """A DNS lane or a fleet read of a method that is not web never shows a host in use, and a
    `www.<parent>` record on its parent's capture never stands for a capture of `www.`."""
    conn = _clean_store()
    src = ensure_source(conn, source, "timestamped")
    add_candidate(conn, "x.com", src)
    value = f"cdx capture 19990101000000 {named}"
    row = record_evidence(conn, "x.com", src, 1999, "cdx_timestamp", value, None, method, **AT)
    if named == "x.com":  # the parent's own capture, which dates the parent
        assign_year(conn, row)
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES ('www.x.com', 'x.com', 1999, ?)",
        [row],
    )
    assert [n for n, r in _results_by_name(conn).items() if not r["ok"]] == failing


def test_detects_two_evidence_rows_sharing_an_id() -> None:
    """`evidence` has no key, so nothing but this check refuses a second row under an id an
    assignment points at: it would stop naming one row."""
    conn = _clean_store()
    conn.execute(
        "INSERT INTO evidence (evidence_id, domain, source_id, evidence_year, evidence_type, "
        "evidence_value, source_file, record_location) "
        "SELECT evidence_id, domain, source_id, evidence_year, evidence_type, evidence_value, "
        "source_file, record_location FROM evidence WHERE domain = 'example.com'"
    )
    assert _planted(conn, "evidence_id_unique")["offending"] == 1


def test_detects_a_row_naming_a_domain_the_store_does_not_hold() -> None:
    conn = _clean_store()
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    eid = record_evidence(conn, "gone.com", cdx, 1999, "cdx_timestamp", "19990101000000", **AT)
    assign_year(conn, eid)
    hosts = ensure_source(conn, "ia_cdx_hostnames", "timestamped")
    value = "cdx capture 19990101000000 shop.gone.com"
    host = record_evidence(conn, "gone.com", hosts, 1999, "cdx_timestamp", value, **AT)
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES ('shop.gone.com', 'gone.com', 1999, ?)",
        [host],
    )
    conn.execute(
        "INSERT INTO domain_language (domain, assigned_year, verdict) "
        "VALUES ('gone.com', 1999, 'english')"
    )
    # two evidence rows, the assignment, the hostname record and the verdict
    assert _planted(conn, "domain_wall_intact")["offending"] == 5


def test_detects_a_row_or_a_domain_naming_a_source_the_store_does_not_hold() -> None:
    conn = _clean_store()
    conn.execute("INSERT INTO domain (domain, discovered_source) VALUES ('stray.com', 404)")
    assign_year(
        conn,
        record_evidence(conn, "stray.com", 404, 1999, "cdx_timestamp", "19990101000000", **AT),
    )
    assert _planted(conn, "source_wall_intact")["offending"] == 2


def test_a_row_this_store_wrote_names_its_file_and_its_place() -> None:
    """A row the store wrote itself names both; a row from before its first own id, loaded
    from an older store, may name neither."""
    conn = connect(":memory:")
    # as `load_provenance` leaves a rebuilt store
    conn.execute("CREATE SEQUENCE evidence_seq START WITH 100")
    conn.execute("CREATE SEQUENCE located_from START WITH 100")
    init_db(conn)
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "example.com", cdx)
    conn.execute(
        "INSERT INTO evidence (evidence_id, domain, source_id, evidence_year, evidence_type, "
        "evidence_value) VALUES (42, 'example.com', ?, 1998, 'cdx_timestamp', '19980101000000')",
        [cdx],
    )
    assign_year(conn, 42)
    assert all(r["ok"] for r in _results_by_name(conn).values())
    for located in ({"source_file": "f.txt"}, {"record_location": "line 3"}, {}):
        eid = record_evidence(
            conn, "example.com", cdx, 1999, "cdx_timestamp", "19990101000000", **located
        )
        assign_year(conn, eid)
    assert _planted(conn, "new_rows_have_location")["offending"] == 3


def test_a_row_without_its_place_is_still_found_after_the_store_is_reopened(
    tmp_path: Path,
) -> None:
    """DuckDB writes a used sequence back with its next id as its start, so the check reads the
    store's first own id from `located_from`, which nothing draws from; a later `ark check`
    process must see a row an ingest wrote before it."""
    path = tmp_path / "ark.duckdb"
    conn = connect(str(path))
    init_db(conn)
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "example.com", cdx)
    assign_year(
        conn, record_evidence(conn, "example.com", cdx, 1999, "cdx_timestamp", "19990101000000")
    )
    conn.close()
    conn = connect(str(path))
    assert _planted(conn, "new_rows_have_location")["offending"] == 1


def test_a_store_made_before_the_location_sequence_counts_only_rows_written_after_it(
    tmp_path: Path,
) -> None:
    """An older store gains `located_from` past its own rows, so its unlocated history passes
    and a row it writes next does not."""
    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "example.com", cdx)
    assign_year(
        conn, record_evidence(conn, "example.com", cdx, 1998, "cdx_timestamp", "19980101000000")
    )
    conn.execute("DROP SEQUENCE located_from")
    init_db(conn)
    assert all(r["ok"] for r in _results_by_name(conn).values())
    assign_year(
        conn, record_evidence(conn, "example.com", cdx, 1999, "cdx_timestamp", "19990101000000")
    )
    assert _planted(conn, "new_rows_have_location")["offending"] == 1


def test_a_store_lacking_a_column_fails_the_check_that_reads_it_by_name(tmp_path: Path) -> None:
    """A store made before a column, never migrated, fails the check reading it and says which
    column; only a check reading the exported files skips on a query that cannot bind."""
    conn = _clean_store()
    conn.execute("ALTER TABLE evidence DROP COLUMN record_location")
    result = _results_by_name(conn)["new_rows_have_location"]
    assert result["ok"] is False and "skipped" not in result
    assert "record_location" in result["error"] and "ark init" in result["error"]
    assert f"[FAIL] new_rows_have_location: {result['error']}" in format_checks([result])
    conn.execute("DROP TABLE domain_language")
    result = _results_by_name(conn)["domain_wall_intact"]
    assert result["ok"] is False and "table domain_language" in result["error"]
