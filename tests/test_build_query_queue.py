"""The queue builder's round-window query.

Loaded by path, like the other script tests: `scripts/` is not a package.

This exists because the query was once written `TIMESTAMPTZ ?`, which DuckDB's
parser rejects, and nothing ran it until a queue was needed. The builder is the
only consumer, so a parse error there disables `just query-queue` and
`just query-queue-preview` together and leaves the shards on disk as the newest
ones anybody can have.
"""

import importlib.util
from decimal import Decimal
from pathlib import Path

import duckdb

from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence

_SPEC = importlib.util.spec_from_file_location(
    "build_query_queue",
    Path(__file__).resolve().parents[1] / "scripts" / "build_query_queue.py",
)
build_query_queue = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_query_queue)


def _store() -> duckdb.DuckDBPyConnection:
    """One baseline pair and two net-new pairs, stamped either side of a window."""
    conn = connect(":memory:")
    init_db(conn)
    prior = ensure_source(conn, "prior_task", "timestamped")
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")

    add_candidate(conn, "base.com", prior)
    assign_year(conn, record_evidence(conn, "base.com", prior, 1997, "prior_reused", "1997.txt"))
    add_candidate(conn, "early.net", cdx)
    assign_year(
        conn, record_evidence(conn, "early.net", cdx, 1998, "cdx_timestamp", "19980101000000")
    )
    add_candidate(conn, "inside.uk", cdx)
    assign_year(
        conn, record_evidence(conn, "inside.uk", cdx, 1999, "cdx_timestamp", "19990101000000")
    )

    # Stamped rather than left on now(), so the assertions do not move with the
    # wall clock.
    stamps = {
        "base.com": "2026-08-10 09:00:00+00",
        "early.net": "2026-08-01 09:00:00+00",
        "inside.uk": "2026-08-10 09:00:00+00",
    }
    for domain, stamp in stamps.items():
        conn.execute(
            "UPDATE domain_year SET verified_at = CAST(? AS TIMESTAMPTZ) WHERE domain = ?",
            [stamp, domain],
        )
    return conn


def test_round_window_query_parses_and_runs() -> None:
    """A bound parameter for the window, which is what the parser refused."""
    rows = build_query_queue.round_netnew_by_tld(_store(), "2026-08-05 00:00:00+00")
    assert dict(rows) == {"uk": 1}


def test_baseline_pairs_are_excluded_and_the_window_is_honoured() -> None:
    conn = _store()
    # widened past every stamp: the baseline pair still does not count, because
    # the round measures what the reviewer has not already credited
    assert dict(build_query_queue.round_netnew_by_tld(conn, "2026-07-01 00:00:00+00")) == {
        "net": 1,
        "uk": 1,
    }
    # a window ahead of every stamp counts nothing at all
    assert build_query_queue.round_netnew_by_tld(conn, "2026-09-01 00:00:00+00") == []


def test_reverse_dns_zones_are_not_query_targets() -> None:
    """They are not websites and never were, so a capture query is wasted by
    construction. 57 reached the pool queue on 2026-08-11 and 41 sorted into its first
    3,000 rows, because `arpa` is an in-window gTLD carrying a high English share."""
    assert build_query_queue.is_reverse_dns("212.in-addr.arpa")
    assert build_query_queue.is_reverse_dns("66-119-170-195.in-addr.arpa")
    assert build_query_queue.is_reverse_dns("0.1.2.ip6.arpa")
    # A real domain that merely ends in .arpa is not a reverse zone and stays.
    assert not build_query_queue.is_reverse_dns("decwrl.arpa")
    assert not build_query_queue.is_reverse_dns("example.com")


def test_plausibility_separates_a_real_namespace_from_a_fabricated_one() -> None:
    """The factor whose absence put 2,675 `.mil` names in the queue's first 3,000 and
    returned zero captures from 1,200 queries.

    Ratios are the ones measured against the live store on 2026-08-11, so this pins the
    separation rather than an arbitrary threshold: real namespaces sit far above the
    fabricated ones and no TLD has to be named for it to work.
    """
    pool = {}
    for i in range(913_012):
        pool[f"c{i}.com"] = "src"
    for i in range(186_278):
        pool[f"m{i}.mil"] = "src"
    attested = {"com": 3_239_150, "mil": 71}
    factor = build_query_queue.pool_plausibility(pool, attested)
    assert factor["com"] > Decimal("0.75")
    assert factor["mil"] < Decimal("0.001")
    # The whole point: the gap between them dwarfs any English-share difference, which
    # for these two TLDs is about 0.63 against 0.98, i.e. under 2x.
    assert factor["com"] / factor["mil"] > 1000


def test_a_tld_with_no_pool_names_is_not_penalised() -> None:
    """There is nothing to rank, so the factor must not read as zero and bury it."""
    factor = build_query_queue.pool_plausibility({"a.com": "src"}, {"com": 10, "uk": 500})
    assert factor["com"] > 0
    assert "uk" not in factor


def test_plausibility_survives_a_tld_nothing_has_dated_yet() -> None:
    """Unproven is not impossible: it should rank low, not be excluded, because the
    only way a namespace ever gets its first dated domain is by being queried."""
    factor = build_query_queue.pool_plausibility({"x.zz": "src", "y.zz": "src"}, {})
    assert factor["zz"] == Decimal(0)
