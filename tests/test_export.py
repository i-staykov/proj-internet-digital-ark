"""Exports: the annual files, the candidate claim and the ISC collection, each net of his files
by exact name. One store holds every case, exported as the bank's claim, in full, and in full
again with its rows laid down in reverse; each test reads those files."""

import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from conftest import script
from his_release import WEB_METHOD, capture

from ark import db, export, held
from ark.baseline import CURRENT_BASELINE_MARKER
from ark.canonical import reject_reason, to_registrable
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.english_share import weight_of
from ark.evidence_types import MASTER_TYPES
from ark.export import claim_files, export_all, netnew_shipped_pairs, stamp_problems
from ark.ingest import YEARS
from ark.sources import SOURCES

ROOT = Path(__file__).resolve().parents[1]
NEWS = "https://archive.org/download/usenet-alt/alt.test.mbox.zip"
ZONE = "http://nw.com/zone/WWW/9901/isc.hosts/net.gz"
STAMP, ATTESTED, ISC = "export_stamp.json", "attested_registrables.txt", "isc_survey_hostnames"
# his release: `www.rolled.com` holds no `rolled.com`, his README is not a list of names, and a
# padded upper-case line of his is the name it spells
HIS = {f"{year}.txt": "already-his.com\n" for year in YEARS} | {
    "1999.txt": "already-his.com\nrelay.example.org\nwww.rolled.com\n",
    "candidate_pool.txt": "already-his-candidate.com\n",
    "candidate_pool_unparsed_format.txt": "mail.org\nrelay.mail.org\n",
    "isc_survey_hostnames/1996-ISC.txt": "isc-his.org\nhis.survey.net\n",
    "isc_survey_hostnames/1997-ISC.txt": " SURVEY.net \n",
    "isc_survey_hostnames/README.md": "cand.org\n",
}
SHIPS = {
    "1997.txt": ["new.com"],
    "1998.txt": ["real.com"],
    "1999.txt": ["both.com", "held.com", "rolled.com", "web.com"],
    "1999_hostnames.txt": ["deep.held.com", "mail.held.com", "www.deep.held.com", "www2.web.com"],
    "2000_hostnames.txt": ["capture-ark-test.example.org", "www.deep.held.com"],
}


def _write(root: Path, files: dict[str, str]) -> Path:
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    return root


def _web(conn, domain: str, year: int, host="", dates=True, kind="cdx_timestamp", value="", **by):
    """A capture of `host` (the domain by default) filed under `domain`, by `source`, `method`,
    read from `url`."""
    by = {"source": "ia_cdx", "method": WEB_METHOD, "url": f"https://x.test/{year}.cdx"} | by
    add_candidate(conn, domain, sid := ensure_source(conn, by["source"], "timestamped"))
    value = value or capture(host or domain, year)
    eid = record_evidence(conn, domain, sid, year, kind, value, by["url"], by["method"])
    if dates:
        assign_year(conn, eid)
    return eid


def _host(conn, parent: str, year: int, host: str, eid: int | None = None) -> None:
    """`host` in `year`, on `eid` or else on a capture of itself filed under `parent`."""
    eid = eid or _web(conn, parent, year, host, dates=False)
    sql = "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) VALUES"
    conn.execute(f"{sql} (?, ?, ?, ?)", [host, parent, year, eid])


def _header(conn, parent: str, host: str, year: int, source="usenet_header_fqdn_hostnames"):
    """A Usenet delivery header naming `host`, dating the parent's year as the ingest does."""
    sid = ensure_source(conn, source, "timestamped")
    add_candidate(conn, parent, sid)
    value, method = f"alt.test.mbox.zip#7 {host}", "usenet_server_written_header"
    eid = record_evidence(conn, parent, sid, year, "artifact_listing", value, NEWS, method)
    assign_year(conn, eid)
    _host(conn, parent, year, host, eid)


def _isc(conn, parent: str, host: str, edition: str) -> None:
    sid = ensure_source(conn, ISC, "timestamped")
    add_candidate(conn, parent, sid)
    value, year = f"isc survey {edition} host {host}", int(edition[:4])
    record_evidence(conn, parent, sid, year, "artifact_listing", value, ZONE, ISC)


def _arpa(conn) -> None:
    """The funnel refuses the reverse tree, so its parent goes in as the store's old rows did."""
    sql = "INSERT INTO domain (domain, tld, discovered_source) VALUES ('1.in-addr.arpa', 'arpa', ?)"
    conn.execute(sql, [ensure_source(conn, "ia_cdx", "timestamped")])
    _host(conn, "1.in-addr.arpa", 1999, "host.1.in-addr.arpa")


def _store(reverse: bool) -> duckdb.DuckDBPyConnection:
    """Every case, in either insertion order, as a store rewrite lays the rows down again."""
    init_db(conn := connect(":memory:"))
    web, host, header = partial(_web, conn), partial(_host, conn), partial(_header, conn)
    cdx = partial(ensure_source, conn, "ia_cdx", "timestamped")
    steps = [
        partial(web, "new.com", 1997),
        # `.biz` was delegated in 2001, `.arpa` is never a website, and he holds the third
        *(partial(web, name, 1998) for name in ("real.com", "impossible.biz", "already-his.com")),
        *(partial(web, n, 1999) for n in ("rolled.com", "held.com", "web.com", "ignore.arpa")),
        # a capture of a host beneath a registrable dates that host, never the registrable
        partial(web, "sub.com", 1999, "a.sub.com"),
        partial(web, "both.com", 1999, "www.both.com", dates=False),
        partial(web, "both.com", 1999),
        # a registry list earns a year by its type that XIV refuses by its method
        partial(web, "zone-only.dk", 2001, kind="artifact_listing", value="20011217: DK Zonen",
                source="dk_zone_list", method="registry_zone_list_wayback_capture"),
        # the same, read from no file a reader can open, ships in neither set
        partial(web, "no-file.dk", 2001, kind="artifact_listing", value="20011217: DK Zonen",
                source="dk_zone_list", method="registry_zone_list_wayback_capture", url=""),
        # `www.<a name held that year>` is a record of its own; `.site` was delegated in 2015
        *(partial(host, "held.com", y, h) for h, y in (("www.deep.held.com", 1999),
          ("deep.held.com", 1999), ("www.deep.held.com", 2000), ("mail.held.com", 1999))),
        partial(host, "web.site", 1996, "bust.web.site"),
        partial(host, "web.com", 1999, "www2.web.com"),
        partial(_arpa, conn),
        # header-only hosts are candidates, and a host with a web year is an annual record
        *(partial(header, "example.org", h, y) for h, y in (("news.example.org", 2000),
          ("news.example.org", 2001), ("relay.example.org", 1999))),
        partial(host, "example.org", 2000, "capture-ark-test.example.org"),
        partial(header, "mail.org", "news.mail.org", 1999),
        partial(header, "mail.org", "relay.mail.org", 2000),
        # a name only a message body types ships in neither arm (`mach1.domain.com`)
        partial(header, "typed-body.com", "www.typed-body.com", 1999, "usenet_body_url_hostnames"),
        partial(header, "your-domain.pt", "www.your-domain.pt", 2000, "usenet_mention"),
        *(partial(header, "example.net", h, y, "usenet") for h, y in (("news.example.net", 2000),
          ("news.example.net", 2001), ("mail.example.net", 1998))),
        # a PTR record whose zone lost its final dot names no host
        partial(header, "example.net", "4.3.2.1.in-addr.arpa.example.net", 1998, "usenet"),
        *(partial(_isc, conn, "survey.net", h, "1996-07") for h in ("keep.survey.net",
          "his.survey.net")),
        partial(_isc, conn, "isc.net", "Mail.isc.net", "1999-01"),
        partial(_isc, conn, "isc.net", "mail.isc.net", "1999-07"),
        # a second type for one source, first of its rows only when they are laid down reversed
        partial(web, "dir.com", 1998, kind="dated_directory", value="1998/05 dir.com"),
        *(partial(lambda n: add_candidate(conn, n, cdx()), name)
          for name in ("cand.org", "isc-his.org", "already-his-candidate.com")),
    ]  # fmt: skip
    for step in steps[::-1] if reverse else steps:
        step()
    return conn


def _export(conn, out: Path, his: Path, **mode) -> dict:
    """Every destination redirected under `out`, so no test run reaches a shipping artifact."""
    dirs = {f"{name}_dir": out / name for name in ("netnew", "report", "provenance")}
    return export_all(conn, candidates_path=out / "candidates.txt", baseline=his, **dirs, **mode)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    root = tmp_path_factory.mktemp("export")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(held, "HELD_ROOT", root / "held")
        for module in (db, held):
            patch.setattr(module, "DB_TEMP_DIR", str(root / "duckdb_tmp"))
        held.prepare(baseline := _write(root / "release", HIS))
        conn = _store(reverse=False)
        _export(conn, root / "claim", baseline, claim_only=True)
        stats = _export(conn, root / "full", baseline, with_provenance=True)
        _export(_store(reverse=True), root / "reversed", baseline)
        _export(conn, root / "over", baseline, claim_only=True)
        over = _export(conn, root / "over", baseline)
        shipped = netnew_shipped_pairs(conn, baseline)
    (bank := root / "bank").mkdir()
    for name in ("candidate_additions.txt", STAMP):
        shutil.copy(root / "claim/netnew" / name, bank)
    return SimpleNamespace(root=root, conn=conn, stats=stats, over=over, shipped=shipped, bank=bank)


def _words(run, rel: str) -> list[str]:
    return (run.root / "full" / rel).read_text().split()


def _rows(run, rel: str) -> list[dict]:
    return list(csv.DictReader((run.root / "full" / rel).read_text().splitlines()))


def test_the_annual_files_ship_net_of_his_and_the_guard_counts_what_they_write(run) -> None:
    """Packaging compares this count to the files: a filter the guard lacks refuses the export."""
    for name in (f"{year}{suffix}.txt" for year in YEARS for suffix in ("", "_hostnames")):
        assert _words(run, f"netnew/{name}") == SHIPS.get(name, []), name
    assert sum(run.stats[f"netnew_{year}"] for year in YEARS) == 6 == run.shipped
    assert _words(run, "candidates.txt") == ["cand.org", "isc.net"]
    # the manifests carry exactly the shipped lines, or they read as additions they are not
    registrables = [r["domain"] for r in _rows(run, "netnew/evidence_manifest.csv")]
    assert registrables == sorted(SHIPS["1997.txt"] + SHIPS["1998.txt"] + SHIPS["1999.txt"])
    hosts = [r["hostname"] for r in _rows(run, "netnew/hostnames_evidence_manifest.csv")]
    assert sorted(hosts) == sorted(SHIPS["1999_hostnames.txt"] + SHIPS["2000_hostnames.txt"])
    # and each names its evidence kind
    for name in ("evidence_manifest.csv", "hostnames_evidence_manifest.csv"):
        assert {r["evidence_kind"] for r in _rows(run, f"netnew/{name}")} == {"capture"}


def test_a_record_ships_only_on_a_capture_of_exactly_its_name(run) -> None:
    """A capture of `www.` or any host beneath a registrable dates that host, never the
    registrable, and a name whose every year fails XIV ships as a candidate, never in neither."""
    rows = _rows(run, "netnew/evidence_manifest.csv")
    cited = {r["domain"]: (r["source"], r["evidence_value"]) for r in rows}
    assert cited["both.com"] == ("ia_cdx", capture("both.com", 1999))
    additions = set(_words(run, "netnew/candidate_additions.txt"))
    assert {"sub.com", "zone-only.dk", "dir.com", "example.org"} <= additions
    assert not {"new.com", "both.com", "no-file.dk"} & additions
    # every pair of ours is attested, whatever its row captured
    attested = (run.root / "full/netnew" / ATTESTED).read_text().splitlines()
    assert {"1999\tboth.com", "1999\tsub.com", "2001\tzone-only.dk"} <= set(attested)


def test_a_www_alias_of_a_held_name_ships_and_the_filters_still_bite(run) -> None:
    """`www.<a name held that year>` is a record of its own; `.site` and `.arpa` ship nowhere."""
    for year in (1999, 2000):
        assert "www.deep.held.com" in _words(run, f"netnew/{year}_hostnames.txt")
    for r in _rows(run, "netnew/hostnames_evidence_manifest.csv"):
        cited = capture(r["hostname"], int(r["assigned_year"]))
        assert (r["source"], r["evidence_value"]) == ("ia_cdx", cited), r
    names = _words(run, "candidates.txt") + _words(run, "netnew/candidate_additions.txt")
    assert not [
        name for name in names if name.endswith((".arpa", ".site")) or ".in-addr.arpa." in name
    ]


def test_the_candidate_claim_is_one_pool_net_of_every_name_his_release_holds(run) -> None:
    """Registrable candidates, ISC survey hosts and header-only hosts in one list, each arm losing
    what any `.txt` list of his names; header-only hosts ship with their provenance."""
    # `cand.org` is found with no dated record, so no file to open: it ships in neither set
    registrable = ["dir.com", "example.net", "example.org", "isc.net", "sub.com"]
    headers = ["mail.example.net", "news.example.net", "news.example.org", "news.mail.org"]
    isc = ["keep.survey.net", "mail.isc.net"]
    claim = sorted([*registrable, "zone-only.dk", *headers, *isc])
    assert _words(run, "netnew/candidate_additions.txt") == claim
    assert _words(run, "netnew/isc_candidates.txt") == isc
    assert _words(run, "netnew/header_candidates.txt") == headers
    summary = json.loads((run.root / "full/netnew/candidate_additions_summary.json").read_text())
    assert (summary["candidates"], summary["track"]) == (12, "candidate")
    assert {u: v["names"] for u, v in summary["by_unit"].items()} == dict(hostname=6, registrable=6)
    assert Decimal(summary["equivalent_english"]) == sum(weight_of(name) for name in claim)
    # one provenance row a name, whose classes partition the claim and its EE
    rows = _rows(run, "netnew/candidate_provenance.csv")
    assert [r["name"] for r in rows] == claim
    assert all(r["position"] and r["source_file"] for r in rows)
    classes = {r["name"]: r["class"] for r in rows}
    assert classes["news.example.org"] == "Usenet server header host"
    assert {classes[n] for n in isc} == {"ISC Internet Domain Survey host"}
    by_class = summary["by_class"]
    assert sum(c["names"] for c in by_class.values()) == len(claim)
    total = sum(Decimal(c["equivalent_english"]) for c in by_class.values())
    assert total == Decimal(summary["equivalent_english"])
    his = ["candidate_pool.txt", "candidate_pool_unparsed_format.txt"]
    his += [f"isc_survey_hostnames/{year}-ISC.txt" for year in (1996, 1997)]
    assert summary["held_by_him"] == {"names": 6, "files": his}
    rows = _rows(run, "netnew/header_candidates_provenance.csv")
    years = [(r["hostname"], r["target_year"]) for r in rows if r["hostname"] == "news.example.org"]
    assert years == [("news.example.org", "2000"), ("news.example.org", "2001")]
    assert {r["acquisition_method"] for r in rows} == {"usenet_server_written_header"}
    assert all(r["source_url"].endswith("alt.test.mbox.zip") for r in rows)
    summary = json.loads((run.root / "full/netnew/header_candidates_summary.json").read_text())
    assert (summary["candidates"], summary["hostname_years"]) == (4, 6)
    assert summary["by_source"] == {"usenet": 2, "usenet_header_fqdn_hostnames": 2}
    # one file per class, so a declined class drops alone; these two share no host
    assert {k: v["names"] for k, v in summary["by_class"].items()} == summary["by_source"]
    assert all(v["exclusive_names"] == v["names"] for v in summary["by_class"].values())
    by_class = run.root / "full/netnew/header_candidates_by_class"
    assert sorted(n for p in by_class.glob("*.txt") for n in p.read_text().split()) == headers
    ledger = (run.root / "full/netnew/header_candidates_exclusions.csv").read_text()
    assert ledger.split(",")[:2] == ["hostname", "scope"]
    # one row per host-year and survey edition
    assert len(_rows(run, "netnew/isc_survey_provenance.csv")) == 3


def test_two_exports_of_one_store_are_byte_identical(run) -> None:
    """A store swaps in only when its export matches the old one byte for byte, so the files
    depend on the rows and never on their physical order. The stamp carries its write time."""
    full, reversed_ = (
        {str(p.relative_to(top)): hashlib.sha256(p.read_bytes()).digest() for p in top.rglob("*")
         if p.is_file() and p.name != STAMP and "provenance" not in p.parts}
        for top in (run.root / "full", run.root / "reversed")
    )  # fmt: skip
    assert full == reversed_ and len(full) > 20


def test_a_full_export_over_the_claims_store_keeps_its_files(run) -> None:
    """The ship's full export after the bank's claim on one store skips the claim's phases and
    leaves what a full export from nothing writes."""
    assert "candidate_additions" in run.stats and "candidate_additions" not in run.over
    full, over = (
        {str(p.relative_to(top)): p.read_bytes() for p in top.rglob("*")
         if p.is_file() and p.name != STAMP and "provenance" not in p.parts}
        for top in (run.root / "full", run.root / "over")
    )  # fmt: skip
    assert full == over


def test_a_claim_export_writes_the_full_exports_claim_and_nothing_else(run) -> None:
    """The bank writes only the claim and ROUND.md quotes it, so the full export that ships
    must write the same bytes, with the ISC reduction run in both modes."""
    claim, full = (
        claim_files(run.root / m / "netnew", run.root / m / "candidates.txt")
        for m in ("claim", "full")
    )
    assert [p.read_bytes() for p in claim] == [p.read_bytes() for p in full]
    # no manifests, ISC files, reports or provenance, and no scratch left behind
    written = {p for p in (run.root / "claim").rglob("*") if p.is_file()}
    assert written == {*claim, run.root / "claim/netnew" / STAMP}
    stamps = [json.loads((run.root / m / "netnew" / STAMP).read_text()) for m in ("claim", "full")]
    assert [stamp.pop("mode") for stamp in stamps] == ["claim", "full"]
    assert {**stamps[0], "written_at": "", "provenance": True} == {**stamps[1], "written_at": ""}
    # example.org is dated only by headers, which the annual files refuse and this does not
    assert (run.root / "claim/netnew" / ATTESTED).read_text() == (
        "1997\tnew.com\n1998\tdir.com\n1998\texample.net\n1998\timpossible.biz\n1998\treal.com\n"
        "1999\tboth.com\n1999\texample.org\n1999\theld.com\n1999\tignore.arpa\n1999\tmail.org\n"
        "1999\trolled.com\n1999\tsub.com\n1999\ttyped-body.com\n1999\tweb.com\n2000\texample.net\n"
        "2000\texample.org\n2000\tmail.org\n2000\tyour-domain.pt\n2001\texample.net\n"
        "2001\texample.org\n2001\tno-file.dk\n2001\tzone-only.dk\n"
    )


def test_packaging_refuses_a_claim_export_or_one_the_store_moved_past(run, tmp_path) -> None:
    """Only a full export of the store as it stands ships, and the bank's candidate claim set
    aside before it must equal the full export's byte for byte."""
    claim, full = run.root / "claim/netnew", run.root / "full/netnew"
    assert "evidence_manifest.csv" in stamp_problems(netnew_dir=claim, claim_dir=run.bank)[0]
    assert stamp_problems(run.conn, full, run.bank) == []
    other = shutil.copytree(run.bank, tmp_path / "bank")
    (other / "candidate_additions.txt").write_text("other.com\n")
    assert any("differ" in p for p in stamp_problems(run.conn, full, other))
    # a seed moves neither ingested files nor evidence, only candidates
    run.conn.execute("BEGIN TRANSACTION")
    try:
        seed = "SELECT 'seeded.com', min(source_id) FROM source"
        run.conn.execute(f"INSERT INTO domain (domain, discovered_source) {seed}")
        assert any("the store moved" in p for p in stamp_problems(run.conn, full, run.bank))
    finally:
        run.conn.execute("ROLLBACK")


def test_an_export_without_his_held_sets_writes_nothing(tmp_path: Path) -> None:
    """Held sets `ark intake` did not write for his current release, or a file of his gone
    since, fail the export closed, and the last export's stamp goes first."""
    baseline = _write(tmp_path / "release", HIS)
    netnew = _write(tmp_path / "netnew", {STAMP: "{}\n"})
    init_db(conn := connect(":memory:"))
    with pytest.raises(held.HeldError, match="run uv run ark intake"):
        _export(conn, tmp_path, baseline)
    assert list(netnew.iterdir()) == []
    assert not (tmp_path / "candidates.txt").exists()
    held.prepare(baseline)
    (baseline / "1998.txt").unlink()
    with pytest.raises(held.HeldError, match="run uv run ark intake"):
        _export(conn, tmp_path, baseline)


# The ISC survey collection, written once over its own release and store
AUDIT = ROOT / "scripts/round/verify_isc_candidates.py"
audit = script("round/verify_isc_candidates.py")
PROV, SUMMARY = "isc_survey_provenance.csv", "isc_candidates_summary.json"
SHARE, WEIGHTS = ROOT / "src/ark/english_share.py", ROOT / "src/ark/data/tld_english_share.json"
NAMES = ["alias.example.com", "keep.example.com", "keep.example.uk", "www.example.com"]
TAMPER = [  # (file, pattern, replacement, the refusal, id): any year's exact name, any key, a count
    ("b/candidate_pool.txt", r"\A", "  KEEP.example.com  \n", "overlap", "reviewer_pool"),
    ("b/2001.txt", r"\A", "  KEEP.example.com  \n", "overlap", "reviewer_annual"),
    ("a/2001.txt", r"\A", "  KEEP.example.com  \n", "overlap", "local_annual"),
    (f"c/{PROV}", r"keep\.example\.com,1997,.*\n", "", "differs", "provenance-missing"),
    (f"c/{PROV}", r"\Z", "extra.example.com,1997,1997-07,f,u,r,m\n", "differs", "provenance-extra"),
    (f"c/{PROV}", r"com\.gz,(http://nw\.com/zone/9707)", r",\1", "incomplete", "provenance-blank"),
    (f"c/{SUMMARY}", r'english": "\d', 'english": "9', "does not reproduce", "stale_summary"),
]  # fmt: skip


def _isc_store():
    """We date example.com, local.example.com and annual.other.com; four parents are surveyed."""
    init_db(conn := connect(":memory:"))
    source = ensure_source(conn, ISC, "timestamped")
    web = ensure_source(conn, "web", "timestamped")
    for parent in ("example.com", "example.uk", "example.site", "other.com"):
        add_candidate(conn, parent, source)
    eid = record_evidence(conn, "example.com", web, 2000, "cdx_timestamp", "20000101000000")
    assign_year(conn, eid)
    _host(conn, "example.com", 2000, "local.example.com", eid)
    sql = "INSERT INTO domain (domain, tld, discovered_source) VALUES"
    conn.execute(sql + " ('annual.other.com', 'com', ?)", [web])
    eid = record_evidence(conn, "annual.other.com", web, 2001, "cdx_timestamp", "20010101000000")
    assign_year(conn, eid)
    return conn, source


def observe(conn, source, host, year=1996, month="07", parent="example.com"):
    value, url = f"isc survey {year}-{month} host {host}", f"http://nw.com/zone/{year % 100}{month}"
    url, method = url + ".hosts/com.gz", "isc_survey_host_listing"
    return record_evidence(conn, parent, source, year, "artifact_listing", value, url, method)


def write_collection(conn, baseline: Path, out: Path) -> dict:
    with tempfile.TemporaryDirectory(dir=out.parent) as work:
        export.reduce_isc(conn, held.load(baseline), Path(work))
    export.export_isc_hostnames(conn, out, stats := {})
    export.export_isc_provenance(conn, out, stats)
    return stats


def _annual(conn) -> list:
    cast = "SELECT * REPLACE (verified_at::VARCHAR AS verified_at) FROM {}_year ORDER BY ALL"
    return [conn.execute(cast.format(t)).fetchall() for t in ("domain", "hostname")]


@pytest.fixture(scope="module")
def isc(tmp_path_factory):
    """The collection written empty, then over every case twice, and the delivery beside it; a
    test that tampers with it works on a copy."""
    root = tmp_path_factory.mktemp("isc")
    files = {f"{y}.txt": "" for y in YEARS} | {"2001.txt": "  ANNUAL.example.com  \nexample.com\n"}
    files["candidate_pool.txt"] = " POOL.example.com \npool.example.com\nwww.alias.example.com\n"
    baseline = _write(root / CURRENT_BASELINE_MARKER, files)
    run = SimpleNamespace(root=root, out=root / "isc_survey_hostnames")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(held, "HELD_ROOT", root / "held")
        for module in (db, held):
            patch.setattr(module, "DB_TEMP_DIR", str(root / "duckdb_tmp"))
        held.prepare(baseline)
        conn, source = _isc_store()
        run.empty = write_collection(conn, baseline, run.out)
        run.empty_ee = json.loads((run.out / SUMMARY).read_text())["equivalent_english"]
        labels = ("keep", "pool", "annual", "local", "alias", "www.alias", "www", "bad_name")
        for host in [f"{n}.example.com" for n in labels] + ["example.com", "outside.other.com"]:
            observe(conn, source, host)
        observe(conn, source, "annual.other.com", parent="other.com")
        for year, month in ((1997, "07"), (1996, "01"), (1996, "01")):
            observe(conn, source, "keep.example.com", year, month)
        observe(conn, source, "keep.example.uk", parent="example.uk")
        observe(conn, source, "future.example.site", parent="example.site")
        before = _annual(conn)
        files = lambda: {p.name: p.read_bytes() for p in run.out.iterdir()}  # noqa: E731
        run.stats, run.written = write_collection(conn, baseline, run.out), files()
        run.again, run.rewritten = write_collection(conn, baseline, run.out), files()
        run.untouched = _annual(conn) == before
    (run.out / WEIGHTS.name).write_bytes(WEIGHTS.read_bytes())
    _write(root / "annual", {f"{year}.txt": "" for year in YEARS})
    return run


@pytest.fixture
def delivery(isc, tmp_path):
    """A copy of the delivery: the collection, his release, our annual files and the weights."""
    root = shutil.copytree(isc.root, tmp_path / "d", ignore=shutil.ignore_patterns("held"))
    out = root / "isc_survey_hostnames"
    return out, root / CURRENT_BASELINE_MARKER, [root / "annual"], out / WEIGHTS.name


def test_reconciles_all_years_exact_names_and_leaves_every_annual_output_alone(isc):
    assert (isc.empty["isc_candidates"], isc.empty["isc_provenance_rows"]) == (0, 0)
    assert isc.empty_ee == "0.0000"
    for name in ("isc_candidates.txt", "1996-ISC.txt"):
        assert (isc.out / name).read_text().splitlines() == NAMES
    assert (isc.out / "1997-ISC.txt").read_text() == "keep.example.com\n"
    assert (isc.stats["isc_candidates"], isc.stats["isc_provenance_rows"]) == (4, 6)
    rows = list(csv.DictReader((isc.out / PROV).open()))
    want = {*((host, 1996) for host in NAMES), ("keep.example.com", 1997)}
    assert {(r["hostname"], int(r["target_year"])) for r in rows} == want
    assert {r["survey_edition"] for r in rows} == {"1996-01", "1996-07", "1997-07"}
    assert all(r["source_file"] == "com.gz" and all(r.values()) for r in rows)
    summary = json.loads((isc.out / SUMMARY).read_text())
    assert (summary["hostname_years"], summary["candidates"]) == (5, 4)
    assert Decimal(summary["equivalent_english"]) == sum(weight_of(h) for h in NAMES)
    assert isc.again == isc.stats and isc.rewritten == isc.written
    assert isc.untouched, "the reduction changed an annual table"


@pytest.mark.parametrize("broken", ["evidence_url", "acquisition_method", "evidence_value"])
def test_incomplete_provenance_refuses_the_export(isc, tmp_path, monkeypatch, broken):
    monkeypatch.setattr(held, "HELD_ROOT", isc.root / "held")
    conn, source = _isc_store()
    eid = observe(conn, source, "keep.example.com")
    value = "host keep.example.com" if broken == "evidence_value" else ""
    conn.execute(f"UPDATE evidence SET {broken} = ? WHERE evidence_id = ?", [value, eid])
    (out := tmp_path / "isc").mkdir()
    with pytest.raises(ValueError, match="incomplete provenance"):
        write_collection(conn, isc.root / CURRENT_BASELINE_MARKER, out)
    assert not (out / SUMMARY).exists()


@pytest.mark.parametrize("installed", [True, False], ids=["with_ark", "without_ark"])
def test_independent_file_audit_reproduces_the_candidate_score(delivery, monkeypatch, installed):
    module = audit
    if not installed:
        (delivery[0] / "english_share.py").write_bytes(SHARE.read_bytes())
        monkeypatch.syspath_prepend(str(delivery[0].parent))
        for name in ("ark", "ark.english_share"):
            monkeypatch.setitem(sys.modules, name, None)
        module = script("round/verify_isc_candidates.py")
    got = module.verify(*delivery)
    assert [got[k] for k in ("candidates", "hostname_years", "provenance_rows")] == [4, 5, 6]
    assert Decimal(got["equivalent_english"]) == sum(weight_of(h) for h in NAMES)


@pytest.mark.parametrize("file,old,new,refusal", [pytest.param(*t[:4], id=t[4]) for t in TAMPER])
def test_the_audit_refuses_a_delivery_that_drifted(delivery, file, old, new, refusal):
    path = dict(zip("cba", (*delivery[:2], delivery[2][0]), strict=True))[file[0]] / file[2:]
    path.write_text(re.sub(old, new, path.read_text(), count=1))
    with pytest.raises(ValueError, match=refusal):
        audit.verify(*delivery)


@pytest.mark.parametrize("omit_provenance", [False, True])
def test_packaging_ships_the_candidates_with_their_provenance_and_class_table(
    tmp_path, omit_provenance
):
    """Candidates ship as one list and one provenance file; the README's class table sums to
    the export's summary, and a missing provenance file refuses."""
    netnew, stage = tmp_path / "output/netnew", tmp_path / "stage"
    netnew.mkdir(parents=True)
    (stage / "candidates").mkdir(parents=True)
    (stage / "README.md").write_text("top\n[CLASS TABLE]\nend\n")
    (netnew / "candidate_additions.txt").write_text("a.com\nb.de\n")
    if not omit_provenance:
        (netnew / "candidate_provenance.csv").write_text(
            "name,year,class\na.com,1999,x\nb.de,2000,y\n"
        )
    summary = {"candidates": 2, "equivalent_english": "1.5",
               "by_class": {"x": {"names": 1, "equivalent_english": "1"},
                            "y": {"names": 1, "equivalent_english": "0.5"}}}  # fmt: skip
    (netnew / "candidate_additions_summary.json").write_text(json.dumps(summary))
    (tmp_path / "docs/round").mkdir(parents=True)
    (tmp_path / "docs/round/candidate_classes.tsv").write_text("class\tsentence\nx\this rule\n")
    text = (ROOT / "scripts/round/package_delivery.sh").read_text()
    cut = r"(# THE CANDIDATE SET.*?)# `additions_english/`"
    block = "STAGE=stage C=stage/candidates\n" + re.search(cut, text, re.S)[1]
    run = subprocess.run(["bash", "-e"], input=block, cwd=tmp_path, text=True, capture_output=True)
    assert (run.returncode != 0) is omit_provenance, run.stderr
    if not omit_provenance:
        assert (stage / "candidates/candidates.txt").read_text() == "a.com\nb.de\n"
        readme = (stage / "README.md").read_text()
        assert (
            "| x | his rule | 1 | 1.0 |" in readme and "| **all** | | **2** | **1.5** |" in readme
        )
        assert "no sentence of his for ['y']" in run.stderr


def test_the_arpa_export_filter_names_the_whole_tld_and_costs_nothing_outside_it() -> None:
    """`.arpa` scores 1.0, the top weight; the narrow reverse-DNS rule let `ignore.arpa` through,
    and the funnel refuses every reverse-DNS name."""
    reverse = ("206.in-addr.arpa", "129-109-170-195.in-addr.arpa", "8.b.d.0.1.0.0.2.ip6.arpa")
    assert [to_registrable(name) for name in (*reverse, "in-addr.arpa", "ip6.arpa")] == [None] * 5
    assert reject_reason("206.in-addr.arpa") == "reverse-dns zone, not a website"
    assert [to_registrable(n) for n in ("foo.com", "206.example.com")] == ["foo.com", "example.com"]
    assert weight_of("x.arpa") == 1 and weight_of("x.arpa") > weight_of("x.mil")


# Rejected, so no recipe ingests them: `nypw_firstcdx` on measurement, `jpnic_register` by him.
ALLOWED_UNDOCUMENTED = {"nypw_firstcdx", "jpnic_register"}


def test_every_spec_that_dates_a_year_is_ingested_by_a_recipe_that_exists() -> None:
    """The justfile recipes are the documented reproduction the submission standard asks for."""
    documented = set(re.findall(r"ark ingest\s+([a-z0-9_]+)", (ROOT / "justfile").read_text()))
    dating = {key for key, spec in SOURCES.items() if spec.evidence_type in MASTER_TYPES}
    missing = sorted(dating - documented - ALLOWED_UNDOCUMENTED)
    assert not missing, f"no justfile recipe ingests these, though they date a year: {missing}"
    unknown = sorted(documented - set(SOURCES))
    assert not unknown, f"the justfile ingests specs that are not in the registry: {unknown}"


def test_a_suffix_written_twice_never_ships() -> None:
    """The brief's quarantines, `x.example.com.example.com` and a bare `www.cz`, in the claim."""
    import duckdb

    from ark.delegation import shipping_filter_for

    conn = duckdb.connect()
    conn.execute("CREATE TABLE t (h VARCHAR, y INTEGER)")
    names = ["host.example.org.example.org", "x.com.com", "a.b.co.uk.b.co.uk", "ph.org.ph.org"]
    names += ["com.com", "a.b.c.a.b.c", "www.example.com", "example.co.uk", "www.cz"]
    conn.executemany("INSERT INTO t VALUES (?, 1999)", [[n] for n in names])
    kept = conn.execute(f"SELECT h FROM t WHERE {shipping_filter_for('h', 'y')} ORDER BY 1")
    assert kept.fetchall() == [("example.co.uk",), ("www.example.com",)]


def test_a_repoint_moves_the_store_ledger() -> None:
    """A full export reuses the claim only on an equal ledger, and a repoint adds no row."""
    import duckdb

    from ark.db import init_db
    from ark.export import store_ledger

    init_db(conn := duckdb.connect())
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES ('a.example.com', 'example.com', 1999, 1)"
    )
    before = store_ledger(conn)
    conn.execute("UPDATE hostname_year SET evidence_id = 2")
    assert store_ledger(conn) != before


def test_a_candidate_takes_the_class_of_its_rows_method_and_a_news_report_its_folders() -> None:
    """A staged row's folder name never decides its class (debbugs_received holds body URLs),
    except a news server's report, filed under the visitor field."""
    from ark.export import _class_sql

    cases = {
        ("msg_debbugs_received__body_url", "msg_body_url", "x"): "message body URL or mention",
        ("msg_debbugs_received__header_more", "msg_header_more_host", "x"): (
            "other server-written header host"
        ),
        ("msg_debbugs_received__news_header", "msg_news_header_host", "x"): (
            "Usenet server header host"
        ),
        ("msg_debbugs_received__received_by", "msg_received_by", "x"): "mail Received header host",
        ("received_rdns_hostnames", "received_from_rdns", "x"): "mail Received header host",
        ("msg_innreport_hosts__visitor_rdns", "msg_visitor_rdns_host", "x"): (
            "news-server report host"
        ),
        ("msg_web_host_reports__visitor_rdns", "msg_visitor_rdns_host", "x"): (
            "web usage report: visitor host"
        ),
        ("usenet_header_fqdn_hostnames", "usenet_server_written_header", "x"): (
            "Usenet server header host"
        ),
        ("ia_cdx", "ia_cdx_domain_sweep", "cdx capture 19990101000000 status 404 a.com"): (
            "web capture with an error status"
        ),
        ("ia_cdx", "ia_cdx_domain_sweep", "cdx capture 19990101000000 replay failed a.com"): (
            "web capture that does not replay"
        ),
    }
    conn = duckdb.connect()
    for (source, method, value), want in cases.items():
        sql = _class_sql("$s", "$m", "$v", "false")
        got = conn.execute(f"SELECT {sql}", {"s": source, "m": method, "v": value}).fetchone()[0]
        assert got == want, (source, got)


def test_a_candidate_leaves_when_its_row_cannot_stand_for_the_name() -> None:
    from ark.export import NO_FILE

    rows = [  # name, year, class, source, source_file
        ("dk.example.dk", 2001, "nameserver host", "dk_zone", ""),
        ("spammidway.uchicago.edu", 1999, "mail or news From or Message-ID host", "list", "f"),
        ("nospamhowl.demon.co.uk", 1998, "mail or news From or Message-ID host", "usenet", "f"),
        ("main.gmane.org", 1997, "mail or news From or Message-ID host", "msg_gmane_lists__x", "f"),
        ("spam.example.com", 1999, "Usenet server header host", "usenet", "f"),
        ("news.gmane.org", 2003, "mail Received header host", "msg_gmane_lists__x", "f"),
        ("found.example.org", None, "discovered name, no dated record", "list", None),
        ("host.mydomain.com", 1999, "Usenet server header host", "usenet", "f"),
        ("www.example.com", 2000, "mail or news From or Message-ID host", "usenet", "f"),
    ]
    conn = duckdb.connect()
    conn.execute(
        "CREATE TABLE candidate_row "
        "(name VARCHAR, year INT, class VARCHAR, source VARCHAR, source_file VARCHAR)"
    )
    conn.executemany("INSERT INTO candidate_row VALUES (?, ?, ?, ?, ?)", rows)
    left = [
        n for (n,) in conn.execute(f"SELECT name FROM candidate_row WHERE {NO_FILE}").fetchall()
    ]
    assert left == [
        "dk.example.dk",
        "spammidway.uchicago.edu",
        "nospamhowl.demon.co.uk",
        "main.gmane.org",
        "found.example.org",
        "host.mydomain.com",
    ]
