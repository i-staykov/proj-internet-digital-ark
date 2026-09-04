"""Exports: net-new files, manifest, candidates, and merged masters."""

from pathlib import Path

import duckdb

from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.export import export_all


def _populated_db() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    prior = ensure_source(conn, "prior_task", "timestamped")
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    add_candidate(conn, "base.com", prior)
    assign_year(conn, record_evidence(conn, "base.com", prior, 1997, "prior_reused", "1997.txt"))
    add_candidate(conn, "new.com", cdx)
    assign_year(
        conn, record_evidence(conn, "new.com", cdx, 1997, "cdx_timestamp", "19970101000000")
    )
    add_candidate(conn, "cand.org", cdx)
    return conn


def test_export_all(tmp_path: Path) -> None:
    conn = _populated_db()
    stats = export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        masters_dir=tmp_path / "masters",
        report_dir=tmp_path / "reports",
        provenance_dir=tmp_path / "provenance",
    )

    # net-new 1997 holds only the cdx-evidenced domain
    assert (tmp_path / "netnew" / "1997.txt").read_text() == "new.com\n"
    assert stats["netnew_1997"] == 1
    # the merged master holds baseline + addition, deduped and sorted
    assert (tmp_path / "masters" / "1997.txt").read_text() == "base.com\nnew.com\n"
    assert stats["master_1997"] == 2
    # unverified candidates are exported separately
    assert (tmp_path / "candidates.txt").read_text() == "cand.org\n"
    # the manifest carries provenance for net-new pairs only
    manifest = (tmp_path / "netnew" / "evidence_manifest.csv").read_text()
    assert "new.com" in manifest and "base.com" not in manifest
    assert "ia_cdx" in manifest


def test_every_export_destination_is_redirectable(tmp_path: Path) -> None:
    conn = _populated_db()
    export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        masters_dir=tmp_path / "masters",
        report_dir=tmp_path / "reports",
        provenance_dir=tmp_path / "provenance",
    )

    # the contribution tables were the one destination not under the caller's
    # control, so running the tests overwrote the real ones with this two-row
    # store; a shipping artifact must not be reachable from a test run
    assert (tmp_path / "reports" / "source_contribution.csv").exists()
    assert (tmp_path / "reports" / "year_growth.csv").exists()
    assert (tmp_path / "provenance" / "evidence.parquet").exists()
    conn.close()


def test_no_export_destination_can_be_missed_by_a_test() -> None:
    """Every Path parameter of `export_all` must be redirectable, and redirected.

    Checking the files this suite happens to know about is not enough: twice now
    a new destination was added with a default pointing at the real delivery
    tree, and the tests overwrote a shipping artifact because nobody passed it.
    First the contribution tables, then the 241 MB provenance export. This
    compares the signature against what the test above actually overrides, so
    the next destination fails here instead of in the archive.
    """
    import inspect

    from ark.export import export_all

    destinations = {
        name
        for name, param in inspect.signature(export_all).parameters.items()
        if isinstance(param.default, Path)
    }
    source = inspect.getsource(test_export_all)
    missed = {name for name in destinations if f"{name}=" not in source}
    assert not missed, f"test_export_all must redirect these: {sorted(missed)}"


def test_a_www_alias_of_a_held_name_ships_and_the_filter_still_bites(tmp_path: Path) -> None:
    """ADR-008 supersedes ADR-007: `www.<a name already held that year>` SHIPS.

    His merges hold all 1,313,547 `www.` forms we sent, the bare name beside 1,106,188 of
    them, and section XI says a base hostname and a distinct subdomain hostname may each be
    annual records. So the alias is no longer withheld, and this test exists to keep the
    reversal from being undone by accident, and to prove the two filters that DO still bite
    were never part of it.
    """
    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    add_candidate(conn, "held.com", cdx)
    eid = record_evidence(conn, "held.com", cdx, 1999, "cdx_timestamp", "19990101000000")
    assign_year(conn, eid)
    # the two parents the impossible hostnames hang off; `add_candidate` refuses `.arpa`
    # at the funnel, so that one goes in directly, exactly as the store's old rows did
    add_candidate(conn, "web.site", cdx)
    conn.execute(
        "INSERT INTO domain (domain, tld, discovered_source) VALUES ('1.in-addr.arpa', 'arpa', ?)",
        [cdx],
    )
    rows = [
        # www. of a hostname the store holds for that same year: SHIPS since ADR-008
        ("www.deep.held.com", "held.com", 1999),
        ("deep.held.com", "held.com", 1999),
        # www. of a name held only in another year: always shipped
        ("www.deep.held.com", "held.com", 2000),
        # not a www. form at all: ships
        ("mail.held.com", "held.com", 1999),
        # `www.<parent registrable>` is absent on purpose: the ingest refuses it and
        # `hostname_is_not_the_parent_www` forbids the row, so a fixture holding one would
        # be testing the export against a state `ark check` rejects. That rule is #101.
        # the hostname half applied neither the .arpa nor the delegation rule until
        # 2026-09-03, so 198 rows like these were shipping
        ("bust.web.site", "web.site", 1996),
        ("host.1.in-addr.arpa", "1.in-addr.arpa", 1999),
    ]
    for hostname, parent, year in rows:
        conn.execute(
            "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
            "VALUES (?, ?, ?, ?)",
            [hostname, parent, year, eid],
        )

    export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        masters_dir=tmp_path / "masters",
        report_dir=tmp_path / "reports",
        provenance_dir=tmp_path / "provenance",
    )
    shipped_1999 = (tmp_path / "netnew" / "1999_hostnames.txt").read_text().split()
    assert shipped_1999 == ["deep.held.com", "mail.held.com", "www.deep.held.com"]
    assert (tmp_path / "netnew" / "2000_hostnames.txt").read_text().split() == ["www.deep.held.com"]
    # `.site` was delegated in 2015 and `.arpa` is never a website. Both survive ADR-008:
    # the reversal was about the alias and touched neither.
    assert (tmp_path / "netnew" / "1996_hostnames.txt").read_text().split() == []
    assert "in-addr.arpa" not in (tmp_path / "netnew" / "1999_hostnames.txt").read_text()
    # the manifest carries the same rows as the files, or it reads as an addition it is not
    manifest = (tmp_path / "netnew" / "hostnames_evidence_manifest.csv").read_text()
    assert "www.deep.held.com" in manifest
    assert "deep.held.com" in manifest
    conn.close()


def test_shipped_pair_count_matches_what_the_export_writes(tmp_path: Path) -> None:
    """Packaging compares these two, so a mismatch refuses a current export forever.

    They were equal until the export learned to drop a pair whose TLD did not exist in
    its year. From then on the guard held a pre-filter number against a post-filter one
    and reported a fresh export as stale: 726,344 against 726,336.
    """
    from ark.export import netnew_shipped_pairs

    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    add_candidate(conn, "real.com", cdx)
    assign_year(
        conn, record_evidence(conn, "real.com", cdx, 1998, "cdx_timestamp", "19980101000000")
    )
    # .biz was delegated in 2001, so a 1998 pair under it can never ship.
    add_candidate(conn, "impossible.biz", cdx)
    assign_year(
        conn, record_evidence(conn, "impossible.biz", cdx, 1998, "cdx_timestamp", "19980101000000")
    )

    stats = export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        masters_dir=tmp_path / "masters",
        report_dir=tmp_path / "reports",
        provenance_dir=tmp_path / "provenance",
    )
    written = sum(v for k, v in stats.items() if k.startswith("netnew_"))
    assert written == 1, "the impossible pair must not reach an annual file"
    assert netnew_shipped_pairs(conn) == written
