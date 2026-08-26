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


def test_the_rates_are_the_ones_the_pilot_measured(store) -> None:
    """Pinned to the pilot, not to the journal conditional it replaced.

    The conditional said 0.600 and 0.944 and was labelled a ceiling. The pilot measured the
    population itself at 0 of 186 for 1996 and 111 of 186 for 2001, so a future edit cannot
    quietly restore the flattering pair.
    """
    assert EDGE_RATE == {1996: "0.000", 2001: "0.597"}
    assert float(EDGE_RATE[1996]) == 0.0, "1996 measured 0 of 186 and must score nothing"
    assert float(EDGE_RATE[2001]) < 0.944, "the pilot must not be replaced by the conditional"


def test_a_1996_only_domain_scores_nothing_while_still_being_selected(store) -> None:
    """The selector describes the population; the ranking prices it. Keeping 1996 in the
    selector at rate zero means a later pilot can revive it by changing one constant."""
    add(store, "held1997.com", 1997)
    assert edge_gap_domains(store) == [("held1997.com", 1996)]
    assert float(EDGE_RATE[1996]) == 0.0
