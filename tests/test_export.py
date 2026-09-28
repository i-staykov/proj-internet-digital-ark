"""Exports: net-new files, manifests and candidates, each net of his files by exact name."""

import csv
import hashlib
import inspect
import json
import re
import shutil
from decimal import Decimal
from functools import partial
from pathlib import Path

import duckdb
import pytest
from his_release import WEB_METHOD, capture

from ark import held
from ark.canonical import reject_reason, to_registrable
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.delegation import shipping_filter
from ark.english_share import weight_of
from ark.evidence_types import MASTER_TYPES
from ark.export import (
    ATTESTED_NAME,
    ISC_SOURCE,
    STAMP_NAME,
    claim_files,
    export_all,
    netnew_shipped_pairs,
    read_stamp,
    stamp_problems,
)
from ark.ingest import YEARS
from ark.sources import SOURCES

ROOT = Path(__file__).resolve().parents[1]
NEWS = "https://archive.org/download/usenet-alt/alt.test.mbox.zip"
ZONE = "http://nw.com/zone/WWW/9901/isc.hosts/net.gz"


def _store() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    return conn


def _web(
    conn: duckdb.DuckDBPyConnection,
    domain: str,
    year: int,
    host: str | None = None,
    dates: bool = True,
    kind: str = "cdx_timestamp",
    value: str | None = None,
) -> int:
    """An exact-host web capture of `host` (the domain itself by default) filed under `domain`,
    dating it unless `dates` is off."""
    sid = ensure_source(conn, "ia_cdx", "timestamped")
    add_candidate(conn, domain, sid)
    value = value or capture(host or domain, year)
    eid = record_evidence(conn, domain, sid, year, kind, value, acquisition_method=WEB_METHOD)
    if dates:
        assign_year(conn, eid)
    return eid


def _host(conn: duckdb.DuckDBPyConnection, host: str, parent: str, year: int, eid: int) -> None:
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES (?, ?, ?, ?)",
        [host, parent, year, eid],
    )


def _header(
    conn: duckdb.DuckDBPyConnection,
    parent: str,
    host: str,
    year: int,
    source: str = "usenet_header_fqdn_hostnames",
) -> None:
    """A Usenet delivery header naming `host`, dating the parent's year as the ingest does."""
    sid = ensure_source(conn, source, "timestamped")
    add_candidate(conn, parent, sid)
    value = f"alt.test.mbox.zip#7 {host}"
    eid = record_evidence(
        conn, parent, sid, year, "artifact_listing", value, NEWS, "usenet_server_written_header"
    )
    assign_year(conn, eid)
    _host(conn, host, parent, year, eid)


def _isc(conn: duckdb.DuckDBPyConnection, parent: str, host: str, edition: str) -> None:
    sid = ensure_source(conn, ISC_SOURCE, "timestamped")
    add_candidate(conn, parent, sid)
    value = f"isc survey {edition} host {host}"
    year = int(edition[:4])
    record_evidence(conn, parent, sid, year, "artifact_listing", value, ZONE, ISC_SOURCE)


def _populated_db() -> duckdb.DuckDBPyConnection:
    conn = _store()
    _web(conn, "new.com", 1997)
    add_candidate(conn, "cand.org", ensure_source(conn, "ia_cdx", "timestamped"))
    return conn


def _baseline(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    """A release of his holding only what the export diffs against, prepared as `ark intake`
    prepares his real one; `files` adds or replaces files of his."""
    baseline = tmp_path / "baseline"
    contents = {f"{year}.txt": "already-his.com\n" for year in YEARS}
    contents["candidate_pool.txt"] = "already-his-candidate.com\n"
    for rel, text in (contents | (files or {})).items():
        path = baseline / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    held.prepare(baseline)
    return baseline


def _export(conn: duckdb.DuckDBPyConnection, out: Path, baseline: Path, **mode) -> dict:
    """Every destination redirected under `out`, so no test run reaches a shipping artifact."""
    return export_all(
        conn,
        netnew_dir=out / "netnew",
        candidates_path=out / "candidates.txt",
        report_dir=out / "reports",
        provenance_dir=out / "provenance",
        baseline=baseline,
        **mode,
    )


def _words(path: Path) -> list[str]:
    return path.read_text().split()


def test_export_all(tmp_path: Path) -> None:
    stats = _export(_populated_db(), tmp_path, _baseline(tmp_path), with_provenance=True)
    netnew = tmp_path / "netnew"
    assert (netnew / "1997.txt").read_text() == "new.com\n"
    # the count is the written file's lines; packaging builds the masters, so no master here
    assert (stats["netnew_1997"], stats["netnew_1996"], "master_1997" in stats) == (1, 0, False)
    assert (tmp_path / "candidates.txt").read_text() == "cand.org\n"
    manifest = (netnew / "evidence_manifest.csv").read_text()
    assert "ia_cdx" in manifest and capture("new.com", 1997) in manifest
    for rel in ("reports/source_contribution.csv", "reports/year_growth.csv"):
        assert (tmp_path / rel).exists(), rel
    assert (tmp_path / "provenance" / "evidence.parquet").exists()


def test_every_export_destination_is_redirected_and_the_graph_is_off_by_default() -> None:
    """A Path parameter defaulting to the delivery tree lets a test overwrite a shipping
    artifact, so `_export` must name every one. The provenance graph is half an export's time."""
    params = inspect.signature(export_all).parameters
    source = inspect.getsource(_export)
    missed = {n for n, p in params.items() if isinstance(p.default, Path) and f"{n}=" not in source}
    assert not missed, f"_export must redirect these: {sorted(missed)}"
    assert params["with_provenance"].default is False
    assert params["claim_only"].default is False


def test_a_www_alias_of_a_held_name_ships_and_the_filters_still_bite(tmp_path: Path) -> None:
    """`www.<a name held that year>` is an annual record of its own (section XI); `.site` was
    delegated in 2015 and `.arpa` is never a website. Each hostname cites a capture of itself."""
    conn = _store()
    _web(conn, "held.com", 1999)
    # the funnel refuses `.arpa`, so this parent goes in as the store's old rows did
    conn.execute(
        "INSERT INTO domain (domain, tld, discovered_source) VALUES ('1.in-addr.arpa', 'arpa', ?)",
        [ensure_source(conn, "ia_cdx", "timestamped")],
    )
    for host, parent, year in (
        ("www.deep.held.com", "held.com", 1999),
        ("deep.held.com", "held.com", 1999),
        ("www.deep.held.com", "held.com", 2000),
        ("mail.held.com", "held.com", 1999),
        ("bust.web.site", "web.site", 1996),
        ("host.1.in-addr.arpa", "1.in-addr.arpa", 1999),
    ):
        _host(conn, host, parent, year, _web(conn, parent, year, host, dates=False))
    _export(conn, tmp_path, _baseline(tmp_path))
    netnew = tmp_path / "netnew"
    shipped = _words(netnew / "1999_hostnames.txt")
    assert shipped == ["deep.held.com", "mail.held.com", "www.deep.held.com"]
    assert _words(netnew / "2000_hostnames.txt") == ["www.deep.held.com"]
    assert _words(netnew / "1996_hostnames.txt") == []
    # the manifest carries the same rows as the files, or it reads as an addition it is not
    manifest = (netnew / "hostnames_evidence_manifest.csv").read_text()
    assert "www.deep.held.com" in manifest and "in-addr.arpa" not in manifest


def test_the_annual_files_ship_net_of_his_and_the_guard_counts_what_they_write(
    tmp_path: Path,
) -> None:
    """Diffed against HIS files at export time, not our ingested copy of them, and packaging
    compares the count to the files, so a filter the guard lacks refuses a current export."""
    conn = _store()
    # `.biz` was delegated in 2001, and he already holds the third
    for name in ("real.com", "impossible.biz", "already-his.com"):
        _web(conn, name, 1998)
    baseline = _baseline(tmp_path)
    stats = _export(conn, tmp_path, baseline)
    assert _words(tmp_path / "netnew" / "1998.txt") == ["real.com"]
    written = sum(v for k, v in stats.items() if k.startswith("netnew_"))
    assert written == 1 == netnew_shipped_pairs(conn, baseline)
    # the manifest cannot describe a line that does not ship
    assert "already-his.com" not in (tmp_path / "netnew" / "evidence_manifest.csv").read_text()


def test_the_candidate_claim_is_one_pool_net_of_every_name_his_release_holds(
    tmp_path: Path,
) -> None:
    """Scored like the annual track, so net-new too: registrable candidates, ISC survey hosts
    and header-only hosts in one list, each arm losing what any `.txt` list of his names."""
    conn = _populated_db()
    baseline = _baseline(
        tmp_path,
        {
            "isc_survey_hostnames/1996-ISC.txt": "isc-his.org\nhis.survey.net\n",
            "isc_survey_hostnames/1997-ISC.txt": " SURVEY.net \n",
            "isc_survey_hostnames/README.md": "cand.org\n",
            "candidate_pool_unparsed_format.txt": "mail.org\nrelay.mail.org\n",
        },
    )
    for name in ("isc-his.org", "already-his.com", "already-his-candidate.com"):
        add_candidate(conn, name, ensure_source(conn, "ia_cdx", "timestamped"))
    for host in ("keep.survey.net", "his.survey.net"):
        _isc(conn, "survey.net", host, "1996-07")
    for host in ("news.mail.org", "relay.mail.org"):
        _header(conn, "mail.org", host, 1999)
    _export(conn, tmp_path, baseline)
    netnew = tmp_path / "netnew"
    # the working pool ships beside the claim and names none of his either
    assert _words(tmp_path / "candidates.txt") == ["cand.org"]
    claim = ["cand.org", "keep.survey.net", "news.mail.org"]
    assert _words(netnew / "candidate_additions.txt") == claim
    assert _words(netnew / "isc_candidates.txt") == ["keep.survey.net"]
    assert _words(netnew / "header_candidates.txt") == ["news.mail.org"]
    summary = json.loads((netnew / "candidate_additions_summary.json").read_text())
    assert (summary["candidates"], summary["track"]) == (3, "candidate")
    assert summary["by_unit"]["registrable"]["names"] == 1
    assert summary["by_unit"]["hostname"]["names"] == 2
    assert Decimal(summary["equivalent_english"]) == sum(weight_of(name) for name in claim)
    assert summary["held_by_him"] == {
        "names": 6,
        "files": [
            "candidate_pool.txt",
            "candidate_pool_unparsed_format.txt",
            "isc_survey_hostnames/1996-ISC.txt",
            "isc_survey_hostnames/1997-ISC.txt",
        ],
    }


def test_a_name_whose_every_year_fails_xiii_is_a_candidate(tmp_path: Path) -> None:
    """A registry list earns a `domain_year` by type and XIII keeps it out of the annual file
    by method, so it ships as a candidate, never in neither file."""
    conn = _populated_db()
    registry = ensure_source(conn, "dk_zone_list", "timestamped")
    add_candidate(conn, "zone-only.dk", registry)
    value, method = "20011217: DK Zonen header", "registry_zone_list_wayback_capture"
    assign_year(
        conn,
        record_evidence(
            conn, "zone-only.dk", registry, 2001, "artifact_listing", value, None, method
        ),
    )
    _export(conn, tmp_path, _baseline(tmp_path))
    additions = _words(tmp_path / "netnew" / "candidate_additions.txt")
    assert "zone-only.dk" in additions
    assert "zone-only.dk" not in _words(tmp_path / "netnew" / "2001.txt")
    # a name that earned a WEB year is an annual record and never a candidate
    assert "new.com" not in additions


def test_a_record_ships_only_on_a_capture_of_exactly_its_name(tmp_path: Path) -> None:
    """A capture of `www.` or any host beneath a registrable dates that host, never the
    registrable. And held is the exact name: his `www.rolled.com` does not hold `rolled.com`."""
    conn = _populated_db()
    baseline = _baseline(tmp_path, {"1999.txt": "already-his.com\nwww.rolled.com\n"})
    # `both.com` is dated by a capture of itself, with a capture of `www.both.com` beside it
    _web(conn, "rolled.com", 1999)
    _web(conn, "sub.com", 1999, "a.sub.com")
    _web(conn, "both.com", 1999, "www.both.com", dates=False)
    _web(conn, "both.com", 1999)
    _export(conn, tmp_path, baseline)
    netnew = tmp_path / "netnew"
    assert _words(netnew / "1999.txt") == ["both.com", "rolled.com"]
    with (netnew / "evidence_manifest.csv").open(encoding="utf-8") as fh:
        cited = {r["domain"]: r["evidence_value"] for r in csv.DictReader(fh)}
    assert cited["both.com"] == capture("both.com", 1999)
    assert "sub.com" not in cited
    assert "sub.com" in _words(netnew / "candidate_additions.txt")
    # every pair of ours is attested, whatever its row captured
    attested = (netnew / ATTESTED_NAME).read_text().splitlines()
    assert {"1999\tboth.com", "1999\trolled.com", "1999\tsub.com"} <= set(attested)


def test_an_export_without_his_held_sets_writes_nothing(tmp_path: Path) -> None:
    """Held sets `ark intake` did not write for his current release fail the export closed."""
    baseline = _baseline(tmp_path)
    (baseline / "1997.txt").write_text("already-his.com\nnew.com\n")
    netnew = tmp_path / "netnew"
    netnew.mkdir()
    (netnew / STAMP_NAME).write_text("{}\n")
    with pytest.raises(held.HeldError, match="run uv run ark intake"):
        _export(_populated_db(), tmp_path, baseline)
    assert list(netnew.iterdir()) == []
    assert not (tmp_path / "candidates.txt").exists()


def test_a_hostname_whose_only_years_are_headers_is_a_candidate_with_provenance(
    tmp_path: Path,
) -> None:
    """XIII: a delivery header is hostname-in-use evidence, a candidate with provenance; a host
    with a web-method year stays an annual record, and one he already lists is reconciled out."""
    conn = _populated_db()
    baseline = _baseline(tmp_path, {"1999.txt": "already-his.com\nrelay.example.org\n"})
    for host, year in (("news.example.org", 2000), ("news.example.org", 2001)):
        _header(conn, "example.org", host, year)
    _header(conn, "example.org", "relay.example.org", 1999)
    web = "capture-ark-test.example.org"
    _host(conn, web, "example.org", 2000, _web(conn, "example.org", 2000, web))
    _export(conn, tmp_path, baseline)
    netnew = tmp_path / "netnew"
    additions = _words(netnew / "candidate_additions.txt")
    # the parent's only capture names a host beneath it, so the parent is a candidate
    assert "news.example.org" in additions and "example.org" in additions
    assert "relay.example.org" not in additions and web not in additions
    assert web in _words(netnew / "2000_hostnames.txt")
    assert _words(netnew / "header_candidates.txt") == ["news.example.org"]
    with (netnew / "header_candidates_provenance.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [(r["hostname"], r["target_year"]) for r in rows] == [
        ("news.example.org", "2000"),
        ("news.example.org", "2001"),
    ]
    assert rows[0]["acquisition_method"] == "usenet_server_written_header"
    assert rows[0]["source_url"].endswith("alt.test.mbox.zip")
    summary = json.loads((netnew / "header_candidates_summary.json").read_text())
    assert summary["candidates"] == 1 and summary["hostname_years"] == 2
    assert summary["by_source"] == {"usenet_header_fqdn_hostnames": 1}
    ledger = (netnew / "header_candidates_exclusions.csv").read_text().splitlines()
    assert ledger[0].split(",")[:2] == ["hostname", "scope"]


def _one_logical_store(reverse: bool) -> duckdb.DuckDBPyConnection:
    """The same rows in either insertion order, as a store rewrite lays them down again: pairs,
    a capture of a host beneath one, header-only hosts, a candidate and two ISC editions."""
    conn = _store()
    www2 = partial(_web, conn, "web.com", 1999, "www2.web.com", dates=False)
    steps = [
        partial(_web, conn, "new.com", 1997),
        partial(_web, conn, "web.com", 1999),
        # a capture of www2.web.com dates that host alone
        lambda: _host(conn, "www2.web.com", "web.com", 1999, www2()),
        # a second type for one source, whose reported type must not follow the row order
        partial(_web, conn, "dir.com", 1998, kind="dated_directory", value="1998/05 dir.com"),
        *(
            partial(_header, conn, "example.org", host, year, "usenet")
            for host, year in (("news.example.org", 2000), ("news.example.org", 2001))
        ),
        partial(_header, conn, "example.org", "mail.example.org", 1998, "usenet"),
        partial(_isc, conn, "isc.net", "Mail.isc.net", "1999-01"),
        partial(_isc, conn, "isc.net", "mail.isc.net", "1999-07"),
        partial(add_candidate, conn, "cand.org", ensure_source(conn, "ia_cdx", "timestamped")),
    ]
    for step in steps[::-1] if reverse else steps:
        step()
    return conn


def test_two_exports_of_one_store_are_byte_identical(tmp_path: Path) -> None:
    """A store swaps in only when its export matches the old one byte for byte, so the files
    depend on the rows and never on their physical order."""
    baseline = _baseline(tmp_path)

    def export(conn: duckdb.DuckDBPyConnection, name: str) -> dict[str, str]:
        _export(conn, tmp_path / name, baseline)
        # the stamp carries its own write time
        return {
            str(p.relative_to(tmp_path / name)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((tmp_path / name).rglob("*"))
            if p.is_file() and p.name != STAMP_NAME
        }

    forward = _one_logical_store(reverse=False)
    first = export(forward, "first")
    assert export(forward, "second") == first
    assert export(_one_logical_store(reverse=True), "reversed") == first
    netnew = tmp_path / "first" / "netnew"
    summary = json.loads((netnew / "candidate_additions_summary.json").read_text())
    assert list(summary["by_unit"]) == ["hostname", "registrable"]
    assert len((netnew / "header_candidates_provenance.csv").read_text().splitlines()) == 4
    assert len((netnew / "isc_survey_provenance.csv").read_text().splitlines()) == 3


@pytest.mark.parametrize("his_isc", [False, True], ids=["isc-name-ours", "isc-name-his"])
def test_a_claim_export_writes_the_full_exports_claim_and_nothing_else(
    tmp_path: Path, his_isc: bool
) -> None:
    """The bank writes only the claim and ROUND.md quotes it, so the full export that ships
    must write the same bytes, with the ISC reduction run in both modes."""
    isc = {"isc_survey_hostnames/1999-ISC.txt": "mail.isc.net\n"} if his_isc else {}
    baseline = _baseline(tmp_path, isc)
    conn = _one_logical_store(reverse=False)
    for mode in ("claim", "full"):
        _export(conn, tmp_path / mode, baseline, claim_only=mode == "claim")
    claim, full = (
        claim_files(tmp_path / m / "netnew", tmp_path / m / "candidates.txt")
        for m in ("claim", "full")
    )
    assert [p.read_bytes() for p in claim] == [p.read_bytes() for p in full]
    # no manifests, ISC files, reports or provenance, and no scratch left behind
    written = {p for p in (tmp_path / "claim").rglob("*") if p.is_file()}
    assert written == {*claim, tmp_path / "claim" / "netnew" / STAMP_NAME}
    claim_stamp, full_stamp = (read_stamp(tmp_path / m / "netnew") for m in ("claim", "full"))
    assert (claim_stamp.pop("mode"), full_stamp.pop("mode")) == ("claim", "full")
    assert {**claim_stamp, "written_at": ""} == {**full_stamp, "written_at": ""}

    netnew = tmp_path / "claim" / "netnew"
    attested = (netnew / ATTESTED_NAME).read_text()
    # example.org is dated only by headers, which the annual files refuse and this does not
    assert attested == (
        "1997\tnew.com\n1998\tdir.com\n1998\texample.org\n"
        "1999\tweb.com\n2000\texample.org\n2001\texample.org\n"
    )
    for year in YEARS:
        block = {line.split("\t")[1] for line in attested.splitlines() if line[:4] == str(year)}
        assert set(_words(netnew / f"{year}.txt")) <= block


def test_packaging_refuses_a_claim_export_or_one_the_store_moved_past(tmp_path: Path) -> None:
    """Only a full export of the store as it stands ships, and the bank's candidate claim set
    aside before it must equal the full export's byte for byte."""
    baseline = _baseline(tmp_path)
    conn = _populated_db()
    netnew, claim = tmp_path / "netnew", tmp_path / "claim"
    _export(conn, tmp_path, baseline, claim_only=True)
    assert "evidence_manifest.csv" in stamp_problems(netnew_dir=netnew, claim_dir=claim)[0]
    claim.mkdir()
    for name in ("candidate_additions.txt", STAMP_NAME):
        shutil.copy(netnew / name, claim)
    _export(conn, tmp_path, baseline, with_provenance=True)
    assert stamp_problems(conn, netnew, claim) == []
    (claim / "candidate_additions.txt").write_text("other.com\n")
    assert any("differ" in p for p in stamp_problems(conn, netnew, claim))
    # a seed moves neither ingested files nor evidence, only candidates
    conn.execute(
        "INSERT INTO domain (domain, discovered_source) "
        "SELECT 'seeded.com', min(source_id) FROM source"
    )
    assert any("the store moved" in p for p in stamp_problems(conn, netnew, claim))


@pytest.mark.parametrize(
    "name",
    [
        "206.in-addr.arpa",
        "129-109-170-195.in-addr.arpa",
        "8.b.d.0.1.0.0.2.ip6.arpa",
        "in-addr.arpa",
        "ip6.arpa",
    ],
)
def test_the_funnel_refuses_every_reverse_dns_name(name: str) -> None:
    assert to_registrable(name) is None


def test_the_arpa_export_filter_names_the_whole_tld_and_costs_nothing_outside_it() -> None:
    """`.arpa` scores 1.0, the top weight; the narrow reverse-DNS rule let `ignore.arpa` through."""
    assert reject_reason("206.in-addr.arpa") == "reverse-dns zone, not a website"
    assert to_registrable("foo.com") == "foo.com"
    assert to_registrable("206.example.com") == "example.com"
    assert weight_of("x.arpa") == 1 and weight_of("x.arpa") > weight_of("x.mil")
    assert "'%.arpa'" in shipping_filter() and "in-addr" not in shipping_filter()


# Specs run against a one-off input no recipe can name: `promotion` is written by
# `build_promotion_journals.py --write`; `nypw_firstcdx` was measured and rejected (sources.md).
ALLOWED_UNDOCUMENTED = {"promotion", "nypw_firstcdx"}


def test_every_spec_that_dates_a_year_is_ingested_by_a_recipe_that_exists() -> None:
    """The justfile recipes are the documented reproduction the submission standard asks for."""
    documented = set(re.findall(r"ark ingest\s+([a-z0-9_]+)", (ROOT / "justfile").read_text()))
    dating = {key for key, spec in SOURCES.items() if spec.evidence_type in MASTER_TYPES}
    missing = sorted(dating - documented - ALLOWED_UNDOCUMENTED)
    assert not missing, f"no justfile recipe ingests these, though they date a year: {missing}"
    unknown = sorted(documented - set(SOURCES))
    assert not unknown, f"the justfile ingests specs that are not in the registry: {unknown}"
