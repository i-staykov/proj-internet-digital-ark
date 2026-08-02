"""Bracketed-gap selection and its priority ordering."""

from ark.db import assign_year, connect, ensure_source, init_db, record_evidence
from ark.gaps import (
    creation_addressable_domains,
    sandwich_gap_domains,
    write_creation_candidates,
    write_gap_candidates,
)


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
    # a 1997 gap (the densest year) and a 1998 gap (the thinnest)
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


def test_creation_pool_includes_missing_years_after_held_ones() -> None:
    conn, source_id = _store()
    # held 1997 and 2001: 1998 and 2000 are adjacent-and-missing. A creation date
    # can legitimately land on either, because it resets on re-registration.
    _hold(conn, source_id, "gappy.com", 1997)
    _hold(conn, source_id, "gappy.com", 2001)

    rows = dict(creation_addressable_domains(conn))

    # adjacent to a held year and missing: 1996 and 1998 (beside 1997), 2000
    # (beside 2001). All three are years a creation date could still evidence.
    assert rows == {"gappy.com": 3}
    conn.close()


def test_creation_pool_orders_most_missing_first() -> None:
    conn, source_id = _store()
    _hold(conn, source_id, "one-gap.com", 1997)
    _hold(conn, source_id, "one-gap.com", 1999)  # missing 1998 only... plus 1996, 2000
    _hold(conn, source_id, "middle.com", 1999)  # missing 1998 and 2000

    ordered = [d for d, _n in creation_addressable_domains(conn)]

    # the domain with more adjacent-and-missing years is queried first
    counts = dict(creation_addressable_domains(conn))
    assert counts[ordered[0]] >= counts[ordered[-1]]
    conn.close()


def test_write_creation_candidates_counts_addressable_years(tmp_path) -> None:
    conn, source_id = _store()
    _hold(conn, source_id, "a.com", 1999)  # adjacent-and-missing: 1998, 2000
    out = tmp_path / "creation.txt"

    summary = write_creation_candidates(conn, out)

    assert summary == {"domains": 1, "addressable_years": 2}
    assert out.read_text(encoding="utf-8").split() == ["a.com"]
    conn.close()
