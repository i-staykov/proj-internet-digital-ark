"""The capture-journal hostname lane, and what survives of the purpose rules.

One still stands: a record needs an observation of the host serving web content, so the DNS
lanes date the parent only. The other is gone, `www.<parent>` having been admitted by ADR-009
on his section XI and on a count of his own benchmark, where 1,221,065 names carry both forms
in one year file. What replaced it is weaker and more useful: a `www.<parent>` record must
point at evidence naming that exact host, so admitting the shape never became asserting it.
"""

import gzip
import json
from pathlib import Path

import duckdb

from ark.checks import collect_checks
from ark.db import init_db
from ark.evidence_types import web_evidence_exists
from ark.hostnames import (
    WEB_FACING_HOST_SOURCES,
    error_lane,
    ingest_hostname_journal,
    writes_hostname_years,
)

CAPTURES = [
    ("http://www.example.com/", "19980301000000"),
    ("http://shop.example.com/x", "19980415120000"),
    ("http://example.com/", "19980102000000"),
    ("http://www.example.com/a", "19990101000000"),
]


def write(tmp_path: Path, rows: list[tuple[str, ...]], name: str = "sweep_test.jsonl.gz") -> Path:
    """One journal; a row is `(url, ts)` or `(url, ts, status)`."""
    path = tmp_path / name
    with gzip.open(path, "wt") as fh:
        for url, ts, *status in rows:
            row = {"url": url, "timestamp": ts} | ({"status": status[0]} if status else {})
            fh.write(json.dumps(row) + "\n")
    return path


def _shipped(conn: duckdb.DuckDBPyConnection) -> list[tuple[str, int]]:
    """The hostname years whose evidence passes the XIII screen, as the export reads it."""
    return sorted(
        conn.execute(
            "SELECT hostname, assigned_year FROM hostname_year hy "
            f"WHERE {web_evidence_exists('hy.evidence_id')}"
        ).fetchall()
    )


def test_an_error_capture_is_a_candidate_and_a_2xx_or_3xx_of_the_year_wins(tmp_path) -> None:
    """A 4xx or 5xx keeps its status in the evidence row, so it dates no master year and
    no parent; a 2xx or 3xx of the same host-year is quoted instead, however much later."""
    conn = duckdb.connect(":memory:")
    init_db(conn)
    rows = [
        ("http://shop.example.com/", "19980101000000", "404"),
        ("http://shop.example.com/x", "19980601000000", "302"),
        ("http://dead.example.com/", "19990101000000", "500"),
        ("http://gone.example.com/", "19990301000000", "403"),
    ]
    stats = ingest_hostname_journal(conn, write(tmp_path, rows, "nypw_status_t.jsonl.gz"))
    assert stats["error_status"] == 3 and stats["error_hostname_years"] == 2
    values = dict(
        conn.execute(
            "SELECT hy.hostname, e.evidence_value FROM hostname_year hy "
            "JOIN evidence e USING (evidence_id)"
        ).fetchall()
    )
    assert values == {
        "shop.example.com": "cdx capture 19980601000000 shop.example.com",
        "dead.example.com": "cdx capture 19990101000000 status 500 dead.example.com",
        "gone.example.com": "cdx capture 19990301000000 status 403 gone.example.com",
    }
    # the error rows stay in the store as candidates; only the 302 reaches a master file
    assert _shipped(conn) == [("shop.example.com", 1998)]
    assert conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall() == [
        ("example.com", 1998)
    ]
    assert all(r["ok"] for r in collect_checks(conn, Path("no-such-export")))


def test_an_error_lane_dates_nothing_and_refuses_a_row_that_is_not_an_error(tmp_path) -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    rows = [
        ("http://a.example.com/", "20000101000000", "404"),
        ("http://b.example.com/", "20000101000000", "503"),
        ("http://c.example.com/", "20000101000000", "200"),
    ]
    stats = ingest_hostname_journal(conn, write(tmp_path, rows, "hostcdx_t_4xx.jsonl.gz"))
    assert stats["status_mismatch"] == 1 and stats["hostname_year_rows"] == 2
    assert _shipped(conn) == []
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 0
    assert error_lane(Path("early_web_nonok_status_x.jsonl.gz"))
    assert error_lane(Path("hostcdx_ia600702_4xx_status.jsonl.gz"))
    assert not error_lane(Path("hostcdx_ia600702_3xx_status.jsonl.gz"))
    # a swept domain's own name never makes its journal an error lane
    for name in ("suffix_mononoke_com_20260921T035207Z", "suffix_4xxx_nu_20260917T013008Z"):
        assert not error_lane(Path(f"{name}.jsonl.gz")), name


def test_a_later_2xx_or_3xx_takes_the_year_an_error_capture_held(tmp_path) -> None:
    """Journals are read one at a time, so the ok capture may arrive second. Either way round
    the 302 is quoted, the host-year ships and the parent is dated."""
    error = (
        "early_web_nonok_status_t.jsonl.gz",
        [("http://shop.example.com/", "19990101000000", "404")],
    )
    ok = (
        "early_web_3xx_status_t.jsonl.gz",
        [("http://shop.example.com/", "19990601000000", "302")],
    )
    for order in ((error, ok), (ok, error)):
        conn = duckdb.connect(":memory:")
        init_db(conn)
        for name, rows in order:
            ingest_hostname_journal(conn, write(tmp_path, rows, name))
        assert _shipped(conn) == [("shop.example.com", 1999)]
        assert conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall() == [
            ("example.com", 1999)
        ]


def test_a_journal_that_must_carry_a_status_and_does_not_is_refused(tmp_path) -> None:
    """NYPW and Early Web rows are cut from CDX that holds a status, so a journal of theirs
    without one cannot show which captures were errors. Nothing of it is written, and it is
    left off the ledger so its re-emission is read."""
    conn = duckdb.connect(":memory:")
    init_db(conn)
    for name in ("nypw_t_hostgrain.jsonl.gz", "early_web_t_hostgrain.jsonl.gz", "x_4xx.jsonl.gz"):
        stats = ingest_hostname_journal(conn, write(tmp_path, CAPTURES, name))
        assert stats["refused"] is True, name
    for table in ("hostname_year", "evidence", "ingested_file"):
        assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0, table
    # a sweep journal needs none: its query asked for 2xx and 3xx only
    assert ingest_hostname_journal(conn, write(tmp_path, CAPTURES))["hostname_year_rows"] == 3


def test_www_of_the_parent_is_a_record_but_no_longer_dates_the_registrable(tmp_path) -> None:
    """His ruling in ADR-010 runs in both directions. ADR-009 admitted `www.<parent>` as its own
    record and let the same capture date the parent as well; the second half is what he
    refused, "nor does the presence of www automatically establish the bare hostname". So
    1998 is still dated, by the bare capture and by `shop.example.com`, and 1999 is not.
    """
    conn = duckdb.connect(":memory:")
    init_db(conn)
    stats = ingest_hostname_journal(conn, write(tmp_path, CAPTURES))
    # three (host, year) candidates below the registrable, all three still records
    assert stats["hostname_year_candidates"] == 3
    assert stats["hostname_year_rows"] == 3
    assert sorted(conn.execute("SELECT hostname, assigned_year FROM hostname_year").fetchall()) == [
        ("shop.example.com", 1998),
        ("www.example.com", 1998),
        ("www.example.com", 1999),
    ]
    # 1998 survives on its own evidence; 1999 rested only on www and is gone
    assert sorted(conn.execute("SELECT assigned_year FROM domain_year").fetchall()) == [(1998,)]
    results = {r["name"]: r for r in collect_checks(conn, Path("no-such-export"))}
    assert results["a_www_record_has_its_own_evidence"]["ok"]
    assert results["hostname_observed_serving_web"]["ok"]
    assert results["a_bare_record_is_not_inferred_from_www"]["ok"]


def test_a_www_only_year_never_dates_the_parent_even_alone(tmp_path) -> None:
    """The exclusion is not an artefact of a sibling capture existing in the same year."""
    conn = duckdb.connect(":memory:")
    init_db(conn)
    ingest_hostname_journal(conn, write(tmp_path, [("http://www.example.com/", "19970601000000")]))
    assert conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 0
    results = {r["name"]: r for r in collect_checks(conn, Path("no-such-export"))}
    assert results["a_bare_record_is_not_inferred_from_www"]["ok"]


def test_a_forced_dns_row_and_a_www_row_without_its_own_evidence_are_both_caught() -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    conn.execute("INSERT INTO source (name, kind) VALUES ('isc_survey_hostnames', 'timestamped')")
    conn.execute("INSERT INTO domain (domain, tld, discovered_source) VALUES ('x.com', 'com', 1)")
    conn.execute(
        "INSERT INTO evidence (domain, source_id, evidence_year, evidence_type, evidence_value) "
        "VALUES ('x.com', 1, 1997, 'artifact_listing', 'isc survey 1997-01 host www.x.com')"
    )
    eid = conn.execute("SELECT evidence_id FROM evidence").fetchone()[0]
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES ('www.x.com', 'x.com', 1997, ?)",
        [eid],
    )
    results = {r["name"]: r for r in collect_checks(conn, Path("no-such-export"))}
    # the ISC lane is still not web-facing, so the row is refused on that ground
    assert results["hostname_observed_serving_web"]["offending"] == 1
    # and the value DOES name www.x.com, so the new invariant is satisfied: admitting the
    # shape is not the same as letting a parent's capture stand in for it
    assert results["a_www_record_has_its_own_evidence"]["offending"] == 0
    # a row whose evidence names only the parent is what that invariant is for
    conn.execute(
        "INSERT INTO evidence (domain, source_id, evidence_year, evidence_type, evidence_value) "
        "VALUES ('x.com', 1, 1998, 'artifact_listing', 'isc survey 1998-01 host x.com')"
    )
    bare = conn.execute("SELECT max(evidence_id) FROM evidence").fetchone()[0]
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES ('www.x.com', 'x.com', 1998, ?)",
        [bare],
    )
    results = {r["name"]: r for r in collect_checks(conn, Path("no-such-export"))}
    assert results["a_www_record_has_its_own_evidence"]["offending"] == 1


def test_dns_lanes_are_not_web_facing() -> None:
    for name in ("isc_survey_hostnames", "ripe_nserver_hostnames", "internic_zone_hostnames"):
        assert name not in WEB_FACING_HOST_SOURCES
        assert not writes_hostname_years(name)
    assert writes_hostname_years("ia_cdx_hostnames")


def test_a_journal_that_has_GROWN_is_read_again(tmp_path) -> None:
    """The sweep appends to its journal under the final name, for hours, so ledgering by name
    alone marks a live journal done at whatever length it had: one pass read a suffix journal
    at 391,684 rows and the next skipped all 500 files. The `.part`-then-rename convention
    does not cover an append-style collector; skipping on content does, for every lane.
    """
    conn = duckdb.connect(":memory:")
    init_db(conn)
    path = write(tmp_path, CAPTURES[:2])
    first = ingest_hostname_journal(conn, path)
    assert first["skipped"] is False
    before = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]

    # unchanged: skipped
    assert ingest_hostname_journal(conn, path)["skipped"] is True

    # grown: read again, and only the new rows land, because the insert ignores duplicates
    write(tmp_path, CAPTURES)
    again = ingest_hostname_journal(conn, path)
    assert again["skipped"] is False
    after = conn.execute("SELECT count(*) FROM hostname_year").fetchone()[0]
    assert after > before
    # one ledger row, updated to the new digest, with the rows of both passes summed
    ledger = conn.execute("SELECT count(*), sum(record_rows) FROM ingested_file").fetchone()
    assert ledger[0] == 1
    assert ledger[1] == first["hostname_year_rows"] + again["hostname_year_rows"]
    conn.close()


def test_arquivo_journals_get_their_own_source_row() -> None:
    """A hostname read from Arquivo.pt must not read as an Internet Archive capture. The lane is
    in under C-81 and Arquivo's terms require the citation "[fonte: Arquivo.pt, dd/mm/aaaa]",
    so its provenance has to be separable in the shipped contribution table. The dispatch is
    on the filename family, as for the Early Web and USFEDGOV indexes.
    """
    from ark.hostnames import (
        ARQUIVO_METHOD,
        ARQUIVO_SOURCE,
        SOURCE_NAME,
        SWEEP_METHOD,
        source_for,
    )

    assert source_for(Path("arquivo_ia_0000.jsonl.gz")) == (ARQUIVO_SOURCE, ARQUIVO_METHOD)
    from ark.hostnames import DARTMOUTH_ARCS_METHOD, DARTMOUTH_ARCS_SOURCE

    assert source_for(Path("dartmouth_arcs_00235-00278.jsonl.gz")) == (
        DARTMOUTH_ARCS_SOURCE,
        DARTMOUTH_ARCS_METHOD,
    )
    from ark.hostnames import HOSTCDX_METHOD, HOSTCDX_SOURCE

    assert source_for(Path("hostcdx_ia600702_000.jsonl.gz")) == (HOSTCDX_SOURCE, HOSTCDX_METHOD)
    assert source_for(Path("availability_host_vps_20260923T070000Z.jsonl.gz")) == (
        SOURCE_NAME,
        "wayback_availability",
    )
    assert ARQUIVO_SOURCE != SOURCE_NAME
    # A sweep journal is untouched by the new branch.
    assert source_for(Path("suffix_example_com_20260908T000000Z.jsonl.gz")) == (
        SOURCE_NAME,
        SWEEP_METHOD,
    )


def _audit(tmp_path: Path, errors: list[tuple[str, ...]], repoint: list[tuple[str, ...]]) -> Path:
    """A status audit's two files: error captures, and each error host-year's earliest 2xx."""
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    for name, header, rows in (
        ("status_errors.tsv.gz", "hostname\tts\tstatus\tfamily", errors),
        ("status_repoint.tsv.gz", "hostname\tyear\tts\tfamily", repoint),
    ):
        with gzip.open(audit / name, "wt") as fh:
            fh.write("\n".join([header, *("\t".join(r) for r in rows)]) + "\n")
    return audit / "status_errors.tsv.gz"


def _store_on_error_captures(tmp_path: Path) -> tuple[duckdb.DuckDBPyConnection, Path]:
    """Three host-years banked before rows carried a status. The audit says a 1999 and a
    2000 capture were errors; only the 1999 host-year has a 2xx elsewhere in the raw."""
    conn = duckdb.connect(":memory:")
    init_db(conn)
    rows = [
        ("http://a.example.com/", "19990101000000", "200"),
        ("http://b.example.com/", "20000101000000", "200"),
        ("http://c.example.com/", "20010101000000", "200"),
    ]
    ingest_hostname_journal(conn, write(tmp_path, rows, "nypw_status_t.jsonl.gz"))
    audit = _audit(
        tmp_path,
        [
            ("a.example.com", "19990101000000", "404", "nypw"),
            ("b.example.com", "20000101000000", "503", "nypw"),
        ],
        [("a.example.com", "1999", "19990601000000", "nypw")],
    )
    return conn, audit


def test_a_record_on_an_error_capture_is_repointed_or_retracted(tmp_path) -> None:
    from ark.hostnames import retract_error_captures

    conn, audit = _store_on_error_captures(tmp_path)
    results = {r["name"]: r for r in collect_checks(conn, Path("no-such-export"), audit=audit)}
    assert results["no_master_record_points_to_an_error_capture"]["offending"] == 4

    counted = retract_error_captures(conn, audit, write=False, netnew_dir=tmp_path)
    assert counted == {
        "hy_hit_repoint_nypw": 1,
        "hy_hit_retract_nypw": 1,
        "dy_hit_repoint_nypw": 1,
        "dy_hit_retract_nypw": 1,
    }
    assert len(_shipped(conn)) == 3, "a dry run changes nothing"

    retract_error_captures(conn, audit, write=True, netnew_dir=tmp_path, journals=())
    values = dict(
        conn.execute(
            "SELECT hy.hostname, e.evidence_value FROM hostname_year hy "
            "JOIN evidence e USING (evidence_id)"
        ).fetchall()
    )
    assert values == {
        "a.example.com": "cdx capture 19990601000000 a.example.com",
        "b.example.com": "cdx capture 20000101000000 status 503 b.example.com",
        "c.example.com": "cdx capture 20010101000000 c.example.com",
    }
    assert _shipped(conn) == [("a.example.com", 1999), ("c.example.com", 2001)]
    shipped_years = conn.execute(
        "SELECT assigned_year FROM domain_year dy "
        f"WHERE {web_evidence_exists('dy.evidence_id')} ORDER BY 1"
    ).fetchall()
    assert shipped_years == [(1999,), (2001,)]
    results = collect_checks(conn, Path("no-such-export"), audit=audit)
    assert all(r["ok"] for r in results), [r["name"] for r in results if not r["ok"]]


def test_a_retracted_year_another_web_family_captured_comes_back(tmp_path) -> None:
    from ark.hostnames import retract_error_captures

    conn, audit = _store_on_error_captures(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    write(other, [("http://b.example.com/x", "20000301000000")], "suffix_example_com_t.jsonl.gz")
    stats = retract_error_captures(conn, audit, write=True, netnew_dir=tmp_path, journals=(other,))
    assert stats["restored_by_another_web_family"] == 1
    assert stats["left_on_an_error_capture"] == 0
    assert ("b.example.com", 2000) in _shipped(conn)
    assert (2000,) in conn.execute(
        f"SELECT assigned_year FROM domain_year dy WHERE {web_evidence_exists('dy.evidence_id')}"
    ).fetchall()
    # read past the ledger for that key alone, and the ledger is left as it was
    names = [n for (n,) in conn.execute("SELECT file_name FROM ingested_file").fetchall()]
    assert names == ["nypw_status_t.jsonl.gz"]


def test_a_parent_year_never_moves_onto_a_candidate_only_row(tmp_path) -> None:
    """A link target is candidate-only however web its method is, so a retracted parent year
    stays on its error row rather than ship on one."""
    from ark.hostnames import retract_error_captures

    conn, audit = _store_on_error_captures(tmp_path)
    source = conn.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
    conn.execute(
        "INSERT INTO evidence (domain, source_id, evidence_year, evidence_type, evidence_value, "
        "acquisition_method) VALUES ('example.com', ?, 2000, 'link_target', "
        "'host_link_graph:2000', 'ukwa_host_link_graph')",
        [source],
    )
    retract_error_captures(conn, audit, write=True, netnew_dir=tmp_path, journals=())
    shipped = conn.execute(
        "SELECT assigned_year FROM domain_year dy "
        f"WHERE {web_evidence_exists('dy.evidence_id')} ORDER BY 1"
    ).fetchall()
    assert shipped == [(1999,), (2001,)]
    assert all(r["ok"] for r in collect_checks(conn, Path("no-such-export"), audit=audit))


def test_a_stopped_write_resumes_and_a_same_second_capture_of_another_family_repoints(
    tmp_path,
) -> None:
    from ark.hostnames import retract_error_captures

    conn, audit = _store_on_error_captures(tmp_path)
    retract_error_captures(conn, audit, write=True, netnew_dir=tmp_path, journals=())
    # the re-read of the other families stopped: a rerun finds the retracted row again
    other = tmp_path / "other"
    other.mkdir()
    write(other, [("http://b.example.com/x", "20000301000000")], "suffix_example_com_t.jsonl.gz")
    again = retract_error_captures(conn, audit, write=True, netnew_dir=tmp_path, journals=(other,))
    assert again["restored_by_another_web_family"] == 1
    assert ("b.example.com", 2000) in _shipped(conn)

    # an Early Web 200 at the very second NYPW answered 404 is a capture of its own
    (tmp_path / "second").mkdir()
    conn, _ = _store_on_error_captures(tmp_path / "second")
    same = _audit(
        tmp_path / "second",
        [("a.example.com", "19990101000000", "404", "nypw")],
        [("a.example.com", "1999", "19990101000000", "early_web")],
    )
    retract_error_captures(conn, same, write=True, netnew_dir=tmp_path, journals=())
    method = conn.execute(
        "SELECT e.acquisition_method FROM hostname_year hy JOIN evidence e USING (evidence_id) "
        "WHERE hy.hostname = 'a.example.com'"
    ).fetchone()[0]
    assert method == "early_web_hostgrain"
    assert ("a.example.com", 1999) in _shipped(conn)
    assert all(r["ok"] for r in collect_checks(conn, Path("no-such-export"), audit=same))


FLEET_APPROVAL = "## Decided\n\n### fleet_x_hostnames / cdx_timestamp\n\nDecision: master\n"


def test_a_fleet_read_part_maps_to_its_lead_and_writes_hostname_years(tmp_path, monkeypatch):
    """`fleetread_<method>__<slug>_NNNN.jsonl.gz` is one source per lead, by its web method,
    and its records pass every check the store runs."""
    from ark import approvals
    from ark.hostnames import source_for

    register = tmp_path / "approved.md"
    register.write_text(FLEET_APPROVAL)
    monkeypatch.setattr(approvals, "DEFAULT_APPROVALS_PATH", register)
    name = "fleetread_bulk_cdx_file__x_0001.jsonl.gz"
    assert source_for(Path(name)) == ("fleet_x_hostnames", "bulk_cdx_file")
    assert writes_hostname_years("fleet_x_hostnames")
    conn = duckdb.connect(":memory:")
    init_db(conn)
    rows = [
        ("http://www.example.com/", "19990301000000", "200"),
        ("http://shop.example.com/", "20000101000000", "404"),
        ("http://old.example.com/", "19950101000000", "200"),
    ]
    stats = ingest_hostname_journal(conn, write(tmp_path, rows, name))
    assert stats["hostname_year_rows"] == 2 and stats["out_of_window"] == 1
    method = conn.execute("SELECT DISTINCT acquisition_method FROM evidence").fetchall()
    assert method == [("bulk_cdx_file",)]
    assert _shipped(conn) == [("www.example.com", 1999)], "the 404 is a candidate only"
    assert all(r["ok"] for r in collect_checks(conn, Path("no-such-export")))


def test_a_fleet_read_of_a_non_web_method_or_without_status_is_refused(tmp_path, monkeypatch):
    from ark import approvals
    from ark.hostnames import source_for

    register = tmp_path / "approved.md"
    register.write_text(FLEET_APPROVAL)
    monkeypatch.setattr(approvals, "DEFAULT_APPROVALS_PATH", register)
    conn = duckdb.connect(":memory:")
    init_db(conn)
    dns = "fleetread_internic_zone_ns_target__x_0001.jsonl.gz"
    try:
        source_for(Path(dns))
    except ValueError as exc:
        assert "not a web method" in str(exc)
    else:
        raise AssertionError("a non-web method mapped to a source")
    rows = [("http://www.example.com/", "19990301000000", "200")]
    assert ingest_hostname_journal(conn, write(tmp_path, rows, dns))["refused"] is True
    bare = write(tmp_path, CAPTURES, "fleetread_bulk_cdx_file__x_0002.jsonl.gz")
    assert ingest_hostname_journal(conn, bare)["refused"] is True
    misnamed = write(tmp_path, rows, "fleetread_bulk_cdx_file_x.jsonl.gz")
    assert ingest_hostname_journal(conn, misnamed)["refused"] is True, "never the sweep's source"
    for table in ("hostname_year", "evidence", "ingested_file"):
        assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0, table


def test_a_fleet_read_banks_both_halves_under_its_own_source(tmp_path, monkeypatch):
    """`ark ingest fleet_x_hostnames` takes the converter's registrables and the parts, both
    under the read's source and method, so one unbank of that source takes the read back."""
    import importlib.util
    from functools import partial

    import pytest
    import typer

    from ark import approvals, cli
    from ark.bulk import ingest_files
    from ark.hostnames import fleet_read_registrables_tag

    register = tmp_path / "approved.md"
    register.write_text(FLEET_APPROVAL)
    monkeypatch.setattr(approvals, "DEFAULT_APPROVALS_PATH", register)
    read = tmp_path / "read"
    read.mkdir()
    rows = [
        ("http://example.com/", "19990301000000", "200"),
        ("http://www.example.com/", "19990301000000", "200"),
        ("http://shop.example.org/", "20000101000000", "200"),
        ("http://gone.com/", "19980101000000", "404"),
    ]
    part = write(read, rows, "fleetread_bulk_cdx_file__x_0001.jsonl.gz")
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "cdx_suffix_convert", root / "scripts/engines/cdx_suffix_convert.py"
    )
    convert = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(convert)
    tag = fleet_read_registrables_tag("bulk_cdx_file", "x", "ab" * 32)
    out = tmp_path / "cdx"
    convert.main(
        [
            "--glob",
            f"{read}/fleetread_*",
            "--tag",
            tag,
            "--out",
            str(out),
            "--state",
            str(tmp_path / "state.tsv"),
        ]
    )
    registrables = out / f"cdx_suffix_{tag}.jsonl.gz"
    conn = duckdb.connect(":memory:")
    init_db(conn)
    monkeypatch.setattr(cli, "connect_patiently", lambda **_: conn)
    monkeypatch.setattr(cli, "ingest_files", partial(ingest_files, report_dir=tmp_path))
    cli._ingest_fleet_read("fleet_x_hostnames", [registrables, part])
    by = conn.execute(
        "SELECT DISTINCT s.name, e.acquisition_method FROM evidence e"
        " JOIN source s USING (source_id)"
    ).fetchall()
    assert by == [("fleet_x_hostnames", "bulk_cdx_file")]
    years = conn.execute("SELECT domain, assigned_year FROM domain_year ORDER BY 1").fetchall()
    assert years == [("example.com", 1999), ("example.org", 2000)], "the 404 dates nothing"
    assert all(r["ok"] for r in collect_checks(conn, Path("no-such-export")))
    for source, files in (("fleet_y_hostnames", [part]), ("fleet_x_hostnames", [register])):
        with pytest.raises(typer.Exit) as refused:
            cli._ingest_fleet_read(source, files)
        assert refused.value.exit_code == 2


def test_a_fleet_source_record_from_a_non_web_method_fails_the_check() -> None:
    conn = duckdb.connect(":memory:")
    init_db(conn)
    from ark.ingest import ensure_source

    source_id = ensure_source(conn, "fleet_x_hostnames", "timestamped")
    conn.execute(
        "INSERT INTO domain (domain, tld, discovered_source) VALUES ('example.com', 'com', ?)",
        [source_id],
    )
    conn.execute(
        "INSERT INTO evidence (domain, source_id, evidence_year, evidence_type, evidence_value,"
        " acquisition_method) VALUES ('example.com', ?, 1999, 'cdx_timestamp',"
        " 'cdx capture 19990301000000 www.example.com', 'internic_zone_ns_target')",
        [source_id],
    )
    evidence_id = conn.execute("SELECT max(evidence_id) FROM evidence").fetchone()[0]
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id)"
        " VALUES ('www.example.com', 'example.com', 1999, ?)",
        [evidence_id],
    )
    results = {r["name"]: r for r in collect_checks(conn, Path("no-such-export"))}
    assert not results["hostname_observed_serving_web"]["ok"]
