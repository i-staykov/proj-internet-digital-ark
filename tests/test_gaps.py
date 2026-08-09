"""Bracketed-gap selection and its priority ordering."""

import pytest

from ark.db import assign_year, connect, ensure_source, init_db, record_evidence
from ark.gaps import (
    creation_addressable_domains,
    equivalent_english_order,
    sandwich_gap_domains,
    take_shard,
    take_weighted_shard,
    write_creation_candidates,
    write_gap_candidates,
    year_priority_order,
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


def test_the_legacy_order_still_puts_the_thinnest_gap_year_first() -> None:
    conn, source_id = _store()
    # a 1997 gap (the densest year) and a 1998 gap (the thinnest)
    _hold(conn, source_id, "dense.com", 1996)
    _hold(conn, source_id, "dense.com", 1998)
    _hold(conn, source_id, "thin.com", 1997)
    _hold(conn, source_id, "thin.com", 1999)

    ordered = [row[0] for row in year_priority_order(sandwich_gap_domains(conn))]
    # 1998 outranks 1997, so the thin-year domain comes first
    assert ordered == ["thin.com", "dense.com"]
    conn.close()


def test_english_share_outranks_the_gap_year_it_used_to_lose_to() -> None:
    """The whole point of the reorder: what an answer is worth beats which year it fills.

    `low.de` sits in the thinnest year (1998) and would lead under the legacy
    order. `high.uk` fills 1997, the densest year and last in YEAR_PRIORITY, but
    `.uk` is 98.1% English against `.de` at 13.2%, so it is worth 7x more.
    """
    conn, source_id = _store()
    _hold(conn, source_id, "low.de", 1997)
    _hold(conn, source_id, "low.de", 1999)  # bracketed gap at 1998, the top-priority year
    _hold(conn, source_id, "high.uk", 1996)
    _hold(conn, source_id, "high.uk", 1998)  # bracketed gap at 1997, the bottom-priority year

    rows = sandwich_gap_domains(conn)
    assert [r[0] for r in year_priority_order(rows)] == ["low.de", "high.uk"]
    assert [r[0] for r in equivalent_english_order(rows)] == ["high.uk", "low.de"]
    conn.close()


def test_more_fillable_years_outranks_a_higher_share_when_it_is_worth_more() -> None:
    """Share alone is not the key: a query answers every year at once.

    `two.de` can fill 1998 and 2000, worth 2 x 0.1324 = 0.2648. `one.net` can fill
    one year at 0.4530. So the higher-share domain wins here, and would lose if
    `two.*` had enough gaps to overtake it. This pins the product, not either factor.
    """
    conn, source_id = _store()
    _hold(conn, source_id, "two.de", 1997)
    _hold(conn, source_id, "two.de", 1999)
    _hold(conn, source_id, "two.de", 2001)  # gaps at 1998 and 2000
    _hold(conn, source_id, "one.net", 1997)
    _hold(conn, source_id, "one.net", 1999)  # gap at 1998 only

    rows = {row[0]: row[2] for row in sandwich_gap_domains(conn)}
    assert rows == {"two.de": 2, "one.net": 1}
    ordered = [r[0] for r in equivalent_english_order(sandwich_gap_domains(conn))]
    assert ordered == ["one.net", "two.de"]
    conn.close()


def test_shards_are_disjoint_and_jointly_complete() -> None:
    rows = [(f"d{i}.com", 0, 1) for i in range(500)]

    slices = [take_shard(rows, 4, i) for i in range(4)]
    names = [{row[0] for row in s} for s in slices]

    # no domain is queried twice, which would waste archive budget
    for i in range(4):
        for j in range(i + 1, 4):
            assert names[i].isdisjoint(names[j])
    # and none is dropped
    assert set().union(*names) == {row[0] for row in rows}


def test_a_shard_keeps_the_priority_order_it_was_given() -> None:
    """Slicing must not hand the whole high-value head to one machine."""
    rows = [(f"d{i}.com", 0, 1) for i in range(200)]
    ordered = equivalent_english_order(rows)

    mine = take_shard(ordered, 3, 1)

    assert mine == [row for row in ordered if row in mine]


def test_sharding_is_stable_across_processes() -> None:
    """PYTHONHASHSEED must not decide which machine owns a domain.

    `hash()` on a str is salted per interpreter run. If sharding used it, two
    machines would disagree about the split and would both query some domains
    while both skipped others.
    """
    import subprocess
    import sys

    code = (
        "import sys; sys.path.insert(0, 'src');"
        "from ark.gaps import spread;"
        "print(spread('stability.com').hex())"
    )
    first = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env={"PYTHONHASHSEED": "0"}
    ).stdout
    second = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env={"PYTHONHASHSEED": "1"}
    ).stdout
    assert first == second != ""


def test_take_shard_rejects_an_impossible_slice() -> None:
    with pytest.raises(ValueError):
        take_shard([("a.com", 0, 1)], 3, 3)


def test_weighted_shards_are_disjoint_and_jointly_complete() -> None:
    rows = [(f"d{i}.com", 0, 1) for i in range(4000)]

    slices = [take_weighted_shard(rows, [78, 22], i) for i in range(2)]
    names = [{row[0] for row in s} for s in slices]

    assert names[0].isdisjoint(names[1])
    assert names[0] | names[1] == {row[0] for row in rows}


def test_weighted_shards_are_sized_by_their_weight() -> None:
    """A machine four times as fast must be handed four times the queue."""
    rows = [(f"d{i}.com", 0, 1) for i in range(20000)]

    fast = take_weighted_shard(rows, [78, 22], 0)

    assert 0.76 < len(fast) / len(rows) < 0.80


def test_a_weighted_shard_is_a_sample_of_the_curve_not_a_block_of_it() -> None:
    """The slow machine must not be handed only the cheap tail.

    Hashing is independent of the ordering, so each share should carry close to
    its own fraction of the total value. Splitting by position instead would give
    one machine the entire high-value head, which is the failure this guards.
    """
    rows = [(f"d{i}.com", 0, 1 + i % 4) for i in range(20000)]
    ordered = equivalent_english_order(rows)
    total = sum(row[2] for row in ordered)

    slow = take_weighted_shard(ordered, [78, 22], 1)

    share_of_value = sum(row[2] for row in slow) / total
    assert 0.20 < share_of_value < 0.24


def test_weighted_sharding_keeps_the_order_it_was_given() -> None:
    rows = [(f"d{i}.com", 0, 1 + i % 3) for i in range(500)]
    ordered = equivalent_english_order(rows)

    mine = take_weighted_shard(ordered, [3, 1], 0)

    assert mine == [row for row in ordered if row in mine]


def test_weighted_shard_rejects_impossible_weights() -> None:
    with pytest.raises(ValueError):
        take_weighted_shard([("a.com", 0, 1)], [1, 1], 2)
    with pytest.raises(ValueError):
        take_weighted_shard([("a.com", 0, 1)], [0, 0], 0)
    with pytest.raises(ValueError):
        take_weighted_shard([("a.com", 0, 1)], [-1, 2], 0)


def test_write_gap_candidates_reports_what_it_wrote(tmp_path) -> None:
    conn, source_id = _store()
    _hold(conn, source_id, "gap.com", 1997)
    _hold(conn, source_id, "gap.com", 1999)
    out = tmp_path / "nested" / "gaps.txt"

    summary = write_gap_candidates(conn, out)

    assert summary["domains"] == 1
    assert summary["gap_pairs"] == 1
    assert summary["of_total_domains"] == 1
    assert summary["shards"] == 1
    assert out.read_text(encoding="utf-8").split() == ["gap.com"]
    conn.close()


def test_write_gap_candidates_writes_only_its_own_shard(tmp_path) -> None:
    conn, source_id = _store()
    for i in range(60):
        _hold(conn, source_id, f"d{i}.com", 1997)
        _hold(conn, source_id, f"d{i}.com", 1999)

    written = []
    for shard in range(3):
        out = tmp_path / f"s{shard}.txt"
        summary = write_gap_candidates(conn, out, shards=3, shard=shard)
        names = out.read_text(encoding="utf-8").split()
        assert summary["domains"] == len(names)
        assert summary["of_total_domains"] == 60
        written.append(set(names))

    assert set().union(*written) == {f"d{i}.com" for i in range(60)}
    assert sum(len(w) for w in written) == 60
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
