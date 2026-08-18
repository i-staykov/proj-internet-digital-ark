"""The window's two edge years, which no queue could express until 2026-08-18.

`sandwich_gap_domains` requires a year held at Y-1 AND Y+1, so 1996 needs 1995 and 2001
needs 2002. Both are outside 1996-2001, so those two years were never gap targets at all,
and a domain that already carries a year is not a pool candidate either. 5,358,097 slots sat
in that blind spot, 99.8% of them never asked of the archive.

`gaps.py` justified the restriction as "17.5x larger and far more speculative". The 17.5x is
right; the speculation is not. Measured off 725 journals: given a 2000 capture the archive
also holds 2001 for 94.4% of 140,924 answers, against 98.2% for a bracketed year measured
the same way, which is the control that validates the method. 1996 is the thin one at 60.0%.

See ADR-006. These tests pin the selection rule and the measured rates, not the allocation
decision, which is Ivo's.
"""

import duckdb
import pytest

from ark.gaps import EDGE_RATE, edge_gap_domains, sandwich_gap_domains


@pytest.fixture
def store() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE domain_year (domain VARCHAR, assigned_year INTEGER)")
    return conn


def add(conn, domain: str, *years: int) -> None:
    conn.executemany("INSERT INTO domain_year VALUES (?, ?)", [(domain, y) for y in years])


def test_a_2000_only_domain_is_an_edge_target_and_not_a_gap_target(store) -> None:
    """The exact shape that was invisible: held in 2000, missing 2001, no 2002 to bracket it."""
    add(store, "held2000.com", 2000)
    assert edge_gap_domains(store) == [("held2000.com", 2001)]
    assert sandwich_gap_domains(store) == []


def test_a_1997_only_domain_is_a_1996_edge_target(store) -> None:
    add(store, "held1997.com", 1997)
    assert edge_gap_domains(store) == [("held1997.com", 1996)]
    assert sandwich_gap_domains(store) == []


def test_a_domain_missing_both_edges_yields_both_slots(store) -> None:
    """One query answers both, which is why the queue builder sums their scores per domain."""
    add(store, "both.com", 1997, 2000)
    assert sorted(edge_gap_domains(store)) == [("both.com", 1996), ("both.com", 2001)]


def test_a_domain_already_holding_the_edge_year_is_not_a_target(store) -> None:
    add(store, "complete.com", 2000, 2001)
    assert ("complete.com", 2001) not in edge_gap_domains(store)


def test_a_bracketed_gap_is_still_a_bracketed_gap(store) -> None:
    """The edge selector must not disturb the population the engines already work."""
    add(store, "sandwich.com", 1998, 2000)
    assert sandwich_gap_domains(store) == [("sandwich.com", 2, 1)]


def test_a_domain_with_no_adjacent_year_is_not_an_edge_target(store) -> None:
    """1998 alone says nothing about 1996 or 2001, and no inference is allowed."""
    add(store, "middle.com", 1998)
    assert edge_gap_domains(store) == []


def test_the_measured_rates_are_the_measured_rates(store) -> None:
    """Pinned so a future edit cannot quietly substitute the bracketed 96-97.5% here.
    2001 is 3.8 points behind a bracketed year; 1996 is 38 points behind."""
    assert EDGE_RATE == {1996: "0.600", 2001: "0.944"}
    assert float(EDGE_RATE[2001]) < 0.982, "the edge rate must stay below the bracketed control"
