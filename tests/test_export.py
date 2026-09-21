"""Exports: net-new files, manifest, candidates, and merged masters."""

import csv
import json
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
        conn,
        record_evidence(
            conn,
            "new.com",
            cdx,
            1997,
            "cdx_timestamp",
            "19970101000000",
            acquisition_method="ia_cdx_domain_sweep",
        ),
    )
    add_candidate(conn, "cand.org", cdx)
    return conn


def _fake_baseline(tmp_path: Path) -> Path:
    """A baseline directory holding only what the export diffs against. The export reads HIS
    annual files and candidate pool at export time, so a test on the real ones would pass
    or fail on whether a fixture name like `new.com` is in his 1997 file. It is.
    """
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    for year in range(1996, 2002):
        (baseline / f"{year}.txt").write_text("already-his.com\n")
    (baseline / "candidate_pool.txt").write_text("already-his-candidate.com\n")
    return baseline


def test_export_all(tmp_path: Path) -> None:
    conn = _populated_db()
    stats = export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        masters_dir=tmp_path / "masters",
        report_dir=tmp_path / "reports",
        provenance_dir=tmp_path / "provenance",
        baseline=_fake_baseline(tmp_path),
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
        baseline=_fake_baseline(tmp_path),
        with_provenance=True,
    )

    # the contribution tables were the one destination not under the caller's
    # control, so running the tests overwrote the real ones with this two-row
    # store; a shipping artifact must not be reachable from a test run
    assert (tmp_path / "reports" / "source_contribution.csv").exists()
    assert (tmp_path / "reports" / "year_growth.csv").exists()
    assert (tmp_path / "provenance" / "evidence.parquet").exists()
    conn.close()


def test_no_export_destination_can_be_missed_by_a_test() -> None:
    """Every Path parameter of `export_all` must be redirectable, and redirected: a new
    destination defaulting to the real delivery tree lets the tests overwrite a shipping
    artifact. This compares the signature against what the test above overrides.
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
    """ADR-008 supersedes ADR-007: `www.<a name already held that year>` SHIPS. His merges
    hold all 1,313,547 `www.` forms we sent, the bare name beside 1,106,188 of them, and
    section XI says a base hostname and a distinct subdomain hostname may each be annual
    records. This keeps the reversal from being undone and proves the two filters that DO
    still bite were never part of it.
    """
    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    add_candidate(conn, "held.com", cdx)
    eid = record_evidence(
        conn,
        "held.com",
        cdx,
        1999,
        "cdx_timestamp",
        "19990101000000",
        acquisition_method="ia_cdx_domain_sweep",
    )
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
        baseline=_fake_baseline(tmp_path),
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
    """Packaging compares these two, so a mismatch refuses a current export for ever. Each
    time the export learned a new filter and the guard did not, a fresh export read as
    stale: 726,344 against 726,336, then 91,168 written against 91,472 counted.
    """
    from ark.export import netnew_shipped_pairs

    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    add_candidate(conn, "real.com", cdx)
    assign_year(
        conn,
        record_evidence(
            conn,
            "real.com",
            cdx,
            1998,
            "cdx_timestamp",
            "19980101000000",
            acquisition_method="ia_cdx_domain_sweep",
        ),
    )
    # .biz was delegated in 2001, so a 1998 pair under it can never ship.
    add_candidate(conn, "impossible.biz", cdx)
    assign_year(
        conn,
        record_evidence(
            conn,
            "impossible.biz",
            cdx,
            1998,
            "cdx_timestamp",
            "19980101000000",
            acquisition_method="ia_cdx_domain_sweep",
        ),
    )
    # and one he already holds for that year, which the export drops and the guard must too
    add_candidate(conn, "already-his.com", cdx)
    assign_year(
        conn,
        record_evidence(
            conn,
            "already-his.com",
            cdx,
            1998,
            "cdx_timestamp",
            "19980101000000",
            acquisition_method="ia_cdx_domain_sweep",
        ),
    )

    baseline = _fake_baseline(tmp_path)
    stats = export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        masters_dir=tmp_path / "masters",
        report_dir=tmp_path / "reports",
        provenance_dir=tmp_path / "provenance",
        baseline=baseline,
    )
    written = sum(v for k, v in stats.items() if k.startswith("netnew_"))
    assert written == 1, "neither the impossible pair nor his own record may reach an annual file"
    assert netnew_shipped_pairs(conn, baseline) == written


def test_candidate_additions_are_one_pool_and_exclude_what_he_holds(tmp_path: Path) -> None:
    """The candidate track is scored like the annual one, so its claim is net-new too. One
    pool, not one file per collection: registrable candidates and ISC survey hostnames land
    in the same list, and the provenance lives in `provenance/` and
    `isc_survey_provenance.csv`. `candidates.txt` is the whole working pool and a different
    number: 2,279,755 names of which 29,327 were absent from his files, so shipping the
    pool as the contribution overstates the registrable half 78x.
    """
    conn = _populated_db()
    baseline = _fake_baseline(tmp_path)
    # a candidate he already lists, in each of the two places he can list it
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    add_candidate(conn, "already-his.com", cdx)
    add_candidate(conn, "already-his-candidate.com", cdx)
    export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        masters_dir=tmp_path / "masters",
        report_dir=tmp_path / "reports",
        provenance_dir=tmp_path / "provenance",
        baseline=baseline,
    )
    pool = (tmp_path / "candidates.txt").read_text().split()
    additions = (tmp_path / "netnew" / "candidate_additions.txt").read_text().split()
    assert "cand.org" in pool and "cand.org" in additions
    # neither of the two he already has survives into the claim
    assert "already-his.com" not in additions
    assert "already-his-candidate.com" not in additions
    # and nothing that earned a year is a candidate at all
    assert "new.com" not in pool and "new.com" not in additions
    summary = json.loads((tmp_path / "netnew" / "candidate_additions_summary.json").read_text())
    assert summary["candidates"] == len(additions)
    assert summary["track"] == "candidate"


def test_a_name_whose_every_year_fails_xiii_is_a_candidate(tmp_path: Path) -> None:
    """C-90: a row the annual screen refuses is a candidate, not a loss. A registry list is
    `artifact_listing` by type and so earns a `domain_year`, and XIII then keeps it out of the
    annual file by METHOD; until 2026-09-21 the candidate pool took only names with no year
    at all, so 251,114 `.dk` rows shipped in neither file."""
    conn = _populated_db()
    baseline = _fake_baseline(tmp_path)
    registry = ensure_source(conn, "dk_zone_list", "timestamped")
    add_candidate(conn, "zone-only.dk", registry)
    assign_year(
        conn,
        record_evidence(
            conn,
            "zone-only.dk",
            registry,
            2001,
            "artifact_listing",
            "20011217: DK Zonen header",
            acquisition_method="registry_zone_list_wayback_capture",
        ),
    )
    export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        masters_dir=tmp_path / "masters",
        report_dir=tmp_path / "reports",
        provenance_dir=tmp_path / "provenance",
        baseline=baseline,
    )
    additions = (tmp_path / "netnew" / "candidate_additions.txt").read_text().split()
    assert "zone-only.dk" in additions
    assert "zone-only.dk" not in (tmp_path / "netnew" / "2001.txt").read_text().split()
    # a name that earned a WEB year is still an annual record and never a candidate
    assert "new.com" not in additions
    # and his own baseline names never enter the pool by the back door
    assert "base.com" not in additions


def test_a_hostname_whose_only_years_are_headers_is_a_candidate_with_provenance(
    tmp_path: Path,
) -> None:
    """XIII: a mail or Usenet delivery header is hostname-in-use evidence, stored as a
    source-specific candidate asset with provenance; a host with a web-method year stays an
    annual record, and a host he already lists is reconciled out."""
    conn = _populated_db()
    baseline = _fake_baseline(tmp_path)
    (baseline / "1999.txt").write_text("already-his.com\nrelay.example.org\n")
    news = ensure_source(conn, "usenet_header_fqdn_hostnames", "timestamped")
    add_candidate(conn, "example.org", news)

    def header(host: str, year: int) -> int:
        return record_evidence(
            conn,
            "example.org",
            news,
            year,
            "artifact_listing",
            f"alt.test.mbox.zip#7 {host}",
            "https://archive.org/download/usenet-alt/alt.test.mbox.zip",
            acquisition_method="usenet_server_written_header",
        )

    web = record_evidence(
        conn,
        "example.org",
        news,
        2000,
        "cdx_timestamp",
        "20000101000000",
        acquisition_method="ia_cdx_domain_sweep",
    )
    for host, year, eid in (
        ("news.example.org", 2000, header("news.example.org", 2000)),
        ("news.example.org", 2001, header("news.example.org", 2001)),
        ("relay.example.org", 1999, header("relay.example.org", 1999)),
        ("capture-ark-test.example.org", 2000, web),
    ):
        # the parent is dated in that year by the same row, as the ingest does it
        assign_year(conn, eid)
        conn.execute(
            "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
            "VALUES (?, 'example.org', ?, ?)",
            [host, year, eid],
        )
    export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        masters_dir=tmp_path / "masters",
        report_dir=tmp_path / "reports",
        provenance_dir=tmp_path / "provenance",
        baseline=baseline,
    )
    netnew = tmp_path / "netnew"
    additions = (netnew / "candidate_additions.txt").read_text().split()
    assert "news.example.org" in additions
    assert "relay.example.org" not in additions
    assert "capture-ark-test.example.org" not in additions
    assert "capture-ark-test.example.org" in (netnew / "2000_hostnames.txt").read_text().split()
    assert (netnew / "header_candidates.txt").read_text().split() == ["news.example.org"]
    with (netnew / "header_candidates_provenance.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [(r["hostname"], r["target_year"]) for r in rows] == [
        ("news.example.org", "2000"),
        ("news.example.org", "2001"),
    ]
    assert rows[0]["acquisition_method"] == "usenet_server_written_header"
    assert rows[0]["source_url"].endswith("alt.test.mbox.zip")
    summary = json.loads((netnew / "header_candidates_summary.json").read_text())
    assert summary["candidates"] == 1
    assert summary["by_source"] == {"usenet_header_fqdn_hostnames": 1}
    assert summary["hostname_years"] == 2
    ledger = (netnew / "header_candidates_exclusions.csv").read_text().splitlines()
    assert ledger[0].split(",")[:2] == ["hostname", "scope"]


def test_the_annual_additions_never_repeat_a_line_he_already_has(tmp_path: Path) -> None:
    """Diffed against HIS files at export time, not against our ingested copy of them: our
    baseline evidence is whatever release was ingested, and his current release can add
    names after it. That gap once put 303 names already in `merged260908` into the 2001
    additions.
    """
    conn = _populated_db()
    baseline = _fake_baseline(tmp_path)
    # he lists this one for 1997; we hold a capture of it for the same year
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    add_candidate(conn, "already-his.com", cdx)
    assign_year(
        conn,
        record_evidence(
            conn,
            "already-his.com",
            cdx,
            1997,
            "cdx_timestamp",
            "19970101000000",
            acquisition_method="ia_cdx_domain_sweep",
        ),
    )
    export_all(
        conn,
        netnew_dir=tmp_path / "netnew",
        candidates_path=tmp_path / "candidates.txt",
        masters_dir=tmp_path / "masters",
        report_dir=tmp_path / "reports",
        provenance_dir=tmp_path / "provenance",
        baseline=baseline,
    )
    shipped = (tmp_path / "netnew" / "1997.txt").read_text().split()
    assert "new.com" in shipped
    assert "already-his.com" not in shipped
    # and the manifest cannot describe a line that does not ship
    manifest = (tmp_path / "netnew" / "evidence_manifest.csv").read_text()
    assert "already-his.com" not in manifest


def test_the_provenance_graph_is_off_unless_asked_for() -> None:
    """It was 229 of `ark export`'s 444 seconds and 2,319 MB, written on every hourly
    sync, and read in exactly two places: `package_delivery.sh` and `just rebuild`.
    Neither runs hourly, so the default must stay off.
    """
    import inspect

    import ark.export as ex

    assert inspect.signature(ex.export_all).parameters["with_provenance"].default is False
