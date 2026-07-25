"""Bracketed-gap selection and its priority ordering."""

from ark.db import assign_year, connect, ensure_source, init_db, record_evidence
from ark.gaps import sandwich_gap_domains, write_gap_candidates


def _hold(conn, source_id, domain, year):
    conn.execute(
        "INSERT OR IGNORE INTO domain (domain, tld, discovered_source) VALUES (?, ?, ?)",
        [domain, domain.split(".", 1)[1], source_id],
    )
    assign_year(
        conn,
        record_evidence(conn, domain, source_id, year, "cdx_timestamp", f"{year}0101000000"),
    )


def _store():
    conn = connect(":memory:")
    init_db(conn)
    return conn, ensure_source(conn, "t", "timestamped")


def test_only_bracketed_gaps_are_selected() -> None:
    conn, source_id = _store()
    # bracketed: held 1997 and 1999, missing 1998
    _hold(conn, source_id, "gap.com", 1997)
    _hold(conn, source_id, "gap.com", 1999)
    # adjacent but not bracketed: held 1997 only, so 1998 is speculative
    _hold(conn, source_id, "edge.com", 1997)
    # complete: nothing missing between its held years
    _hold(conn, source_id, "full.com", 1997)
    _hold(conn, source_id, "full.com", 1998)

    domains = [row[0] for row in sandwich_gap_domains(conn)]
    assert domains == ["gap.com"]
    conn.close()


def test_thinnest_gap_year_is_queried_first() -> None:
    conn, source_id = _store()
    # a 1997 gap (our densest year) and a 1998 gap (our thinnest)
    _hold(conn, source_id, "dense.com", 1996)
    _hold(conn, source_id, "dense.com", 1998)
    _hold(conn, source_id, "thin.com", 1997)
    _hold(conn, source_id, "thin.com", 1999)

    domains = [row[0] for row in sandwich_gap_domains(conn)]
    # 1998 outranks 1997, so the thin-year domain comes first
    assert domains == ["thin.com", "dense.com"]
    conn.close()


def test_write_gap_candidates_reports_what_it_wrote(tmp_path) -> None:
    conn, source_id = _store()
    _hold(conn, source_id, "gap.com", 1997)
    _hold(conn, source_id, "gap.com", 1999)
    out = tmp_path / "nested" / "gaps.txt"

    summary = write_gap_candidates(conn, out)

    assert summary == {"domains": 1, "gap_pairs": 1}
    assert out.read_text(encoding="utf-8").split() == ["gap.com"]
    conn.close()
