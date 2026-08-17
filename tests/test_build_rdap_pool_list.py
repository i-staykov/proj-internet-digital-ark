"""The RDAP pool list's plausibility check.

Loaded by path, like the other script tests: `scripts/` is not a package.

This exists because the list is ranked by expected equivalent-English, which is
`P(in-window date) x English share`, and the project has already paid once for
ranking on that when the probability half was a guess: `.au` sorted first in the
whole queue on a 0.9904 share and returned zero in-window creation dates.

`.gov` is the same shape found on 2026-08-10. It holds 185,803 candidate-pool
names at a 0.9825 share, which ranks it fourth on volume times weight, and 182
pool names for every dated one. `.com` and `.uk` both sit at 0.3. The pool names
are invented (`wavohsdojde.gov`) or prose words a bare-host rule read as
hostnames (`empty.gov`, `dessert.gov`).
"""

import importlib.util
from decimal import Decimal
from pathlib import Path

import duckdb

from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence

_SPEC = importlib.util.spec_from_file_location(
    "build_rdap_pool_list",
    Path(__file__).resolve().parents[1] / "scripts" / "build_rdap_pool_list.py",
)
builder = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(builder)


def _store() -> duckdb.DuckDBPyConnection:
    """A plausible namespace and a fabricated one.

    `real.com` and `other.com` hold years and one `.com` sits in the pool, so
    `.com` reads 0.5. Four `.gov` names sit in the pool against one dated, so
    `.gov` reads 4.0.
    """
    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "wayback_cdx", "timestamped")
    seed = ensure_source(conn, "usenet_mention", "candidate_only")

    for name in ("real.com", "other.com", "agency.gov"):
        add_candidate(conn, name, cdx)
        assign_year(conn, record_evidence(conn, name, cdx, 1998, "cdx_timestamp", "19980101000000"))
    add_candidate(conn, "undated.com", seed)
    for name in ("wavohsdojde.gov", "empty.gov", "dessert.gov", "xkgnmoaeg.gov"):
        add_candidate(conn, name, seed)
    return conn


def test_ratio_separates_a_fabricated_namespace_from_a_real_one() -> None:
    rows = builder.pool_plausibility(_store(), ["com", "gov"])
    by_tld = {tld: (held, pool, ratio) for tld, held, pool, ratio in rows}
    assert by_tld["com"] == (2, 1, Decimal("0.5"))
    assert by_tld["gov"] == (1, 4, Decimal("4"))
    # sorted worst first, so the warning prints the suspect namespaces at the top
    assert rows[0][0] == "gov"


def test_a_tld_with_no_dated_names_at_all_does_not_divide_by_zero() -> None:
    conn = connect(":memory:")
    init_db(conn)
    seed = ensure_source(conn, "usenet_mention", "candidate_only")
    for name in ("a.ht", "b.ht"):
        add_candidate(conn, name, seed)
    (tld, held, pool, ratio) = builder.pool_plausibility(conn, ["ht"])[0]
    assert (tld, held, pool) == ("ht", 0, 2)
    assert ratio == Decimal(2)


def test_the_threshold_is_well_clear_of_a_real_namespace() -> None:
    """Measured store-wide: `.com` 0.3, `.uk` 0.3, `.gov` 182, `.mil` 2,624. A
    threshold anywhere between 1 and 100 separates them, so 10 is not tuned."""
    assert Decimal(1) < builder.IMPLAUSIBLE_POOL_RATIO < Decimal(100)
