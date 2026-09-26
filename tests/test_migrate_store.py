"""Stage A rebuilds the store without his superseded rows and our duplicates, and the rebuilt
file exports byte for byte what the old one did."""

import hashlib
import importlib.util
import sys
from pathlib import Path

import duckdb
import pytest

from ark.baseline import CURRENT_BASELINE_MARKER
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.hostnames import ISC_METHOD, ISC_SOURCE_NAME
from ark.hostnames import SOURCE_NAME as HOST_SOURCE
from ark.ingest import ingest_year_file
from ark.provenance import write_provenance

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "migrate_store", ROOT / "scripts/round/migrate_store.py"
)
migrate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = migrate
SPEC.loader.exec_module(migrate)

OLDER = "merged260101"
SWEEP = "ia_cdx_domain_sweep"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def release(tmp: Path, name: str, files: dict[int, list[str]]) -> Path:
    folder = tmp / "releases" / name
    folder.mkdir(parents=True)
    for year, names in files.items():
        (folder / f"{year}.txt").write_text("".join(f"{n}\n" for n in names))
    return folder


def old_store(tmp: Path, monkeypatch) -> tuple:
    """Three releases of his and our rows around them. What each domain stands for:

    a.com, e.com, w.com  held by an older release and the current one: re-pointed
    b.com                only an older release holds it, and domain_year cites it
    c.com                only older releases hold it, and domain_year cites our row
    f.com                only older releases hold it, and domain_year cites the lower id
    d0/d1/d2.com         three duplicate rows each, cited 0, 1 and 2 times
    w.com                a www-only row with a lower id than the row provenance re-points to
    isc.net              ISC rows for hosts that differ only in case
    """
    monkeypatch.setattr(migrate, "loaded_jobs", lambda: [])
    monkeypatch.setattr(migrate, "holders", lambda path: [])
    monkeypatch.setattr(migrate, "newest_credited_day", lambda: None)
    store = tmp / "data" / "ark.duckdb"
    store.parent.mkdir(parents=True)
    conn = connect(store)
    init_db(conn)
    report = tmp / "mismatches.txt"
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    hosts = ensure_source(conn, HOST_SOURCE, "timestamped")
    whois = ensure_source(conn, "domain_creation_bulk", "timestamped")
    isc = ensure_source(conn, ISC_SOURCE_NAME, "timestamped")

    def ours(domain, year, value, source=cdx, kind="cdx_timestamp", assign=False, url=None):
        add_candidate(conn, domain, source)
        method = ISC_METHOD if source == isc else SWEEP
        eid = record_evidence(conn, domain, source, year, kind, value, url, method)
        if assign:
            assign_year(conn, eid)
        return eid

    ours("c.com", 1999, "cdx capture 19990505 c.com", assign=True)
    ours("new.com", 1997, "cdx capture 19970101 new.com", assign=True)
    for prefix, files in (
        ("", {1998: ["f.com"], 1999: ["c.com"]}),
        (
            OLDER,
            {1997: ["a.com"], 1998: ["b.com", "f.com"], 1999: ["c.com"], 2001: ["e.com", "w.com"]},
        ),
        (
            CURRENT_BASELINE_MARKER,
            {
                1996: ["q96.com"],
                1997: ["a.com"],
                1998: ["q98.com"],
                1999: ["q99.com"],
                2000: ["z.com"],
                2001: ["e.com", "w.com"],
            },
        ),
    ):
        folder = release(tmp, prefix or "first", files)
        for year in files:
            ingest_year_file(conn, folder / f"{year}.txt", year, report, prefix)
    (folder / "candidate_pool.txt").write_text("already-his-candidate.com\n")
    # the hostname half of the export reads baseline_dir(), not its `baseline` argument
    monkeypatch.setattr("ark.export.baseline_dir", lambda: folder)

    ours("d0.com", 1999, "1999-05-01", whois, "whois_creation", assign=True)
    for day in (1, 2, 3):
        ours("d0.com", 1999, f"cdx capture 1999010{day} d0.com")
    d1 = [ours("d1.com", 2000, f"cdx capture 2000010{day} d1.com") for day in (1, 2, 3)]
    assign_year(conn, d1[1])
    d2 = [ours("d2.com", 2001, f"cdx capture 2001010{d} shop.d2.com", hosts) for d in (1, 2, 3)]
    assign_year(conn, d2[2])
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES ('shop.d2.com', 'd2.com', 2001, ?)",
        [d2[1]],
    )
    www_only = ours("w.com", 2001, "cdx capture 20010101 www.w.com")
    repointed_to = ours("w.com", 2001, "wayback 20010202 www.w.com")
    zone = "http://nw.com/zone/WWW/0001/isc.hosts/net.gz"
    for host in ("Mail.isc.net", "mail.isc.net"):
        value = f"isc survey 2000-01 host {host}"
        ours("isc.net", 2000, value, isc, "artifact_listing", assign=True, url=zone)
    conn.close()

    stage = migrate.Stage(
        store=store,
        new=tmp / "data" / "ark.stage_a.duckdb",
        bak=tmp / "data" / "ark.duckdb.pre-stage-a.bak",
        work=tmp / "data" / "migrate",
        superseded=tmp / "data" / "migrate" / "his_superseded_only.csv",
        baseline=folder,
        temp=tmp / "duckdb_tmp",
        floor_gib=0,
        footprint_gib=0,
    )
    return stage, {"www_only": www_only, "repointed_to": repointed_to}


def rows(path: Path, query: str) -> list:
    conn = duckdb.connect(str(path), read_only=True)
    try:
        return conn.execute(query).fetchall()
    finally:
        conn.close()


def test_the_rebuilt_store_exports_what_the_old_one_did_and_rolls_back(tmp_path, monkeypatch):
    stage, ids = old_store(tmp_path, monkeypatch)
    before = sha(stage.store)
    report = migrate.stage_a_run(stage)
    checks = report.get("verify", {}).get("checks", {})
    assert report["swap_ready"], {k: v for k, v in checks.items() if not v["ok"]}
    assert "ALL PASS" in checks["integrity_checks"]["report"]
    assert checks["exports_byte_identical"]["files"] > 20

    census = report["census"]
    assert census["current_rows"] == 7 and census["orphan_pairs"] == 3
    assert census["orphan_cited"] == 2 and census["his_rows_after"] == 10
    assert census["repointed"] == 3  # a.com, e.com and w.com move to the current release
    assert census["ours_dropped"] == 3  # two of d0's three rows and one of d1's
    kept = {r[0] for r in rows(stage.new, "SELECT evidence_id FROM evidence")}
    assert {ids["www_only"], ids["repointed_to"]} <= kept
    his = dict(
        rows(
            stage.new,
            "SELECT domain || ' ' || evidence_value, evidence_id FROM evidence "
            "WHERE evidence_type = 'prior_reused'",
        )
    )
    # the cited row, else the highest id: f.com keeps its first release's row
    assert stage.superseded.read_text().splitlines()[1:] == [
        f"b.com,1998,{OLDER}/1998.txt,{his[f'b.com {OLDER}/1998.txt']},true",
        f"c.com,1999,{OLDER}/1999.txt,{his[f'c.com {OLDER}/1999.txt']},false",
        f"f.com,1998,1998.txt,{his['f.com 1998.txt']},true",
    ]

    # the provenance export re-points domain_year to the same rows from either store
    shipped = {}
    for name, path in (("old", stage.store), ("new", stage.new)):
        conn = duckdb.connect(str(path), read_only=True)
        write_provenance(conn, tmp_path / name)
        conn.close()
        parquet = tmp_path / name / "domain_year.parquet"
        query = f"SELECT domain, assigned_year, evidence_id FROM '{parquet}' ORDER BY ALL"
        shipped[name] = duckdb.sql(query).fetchall()
    assert shipped["old"] == shipped["new"]

    assert sha(stage.store) == before
    migrate.write(stage.record("swap"), migrate.swap(stage))
    assert sha(stage.bak) == before and sha(stage.store) == report["verify"]["new_sha256"]
    assert migrate.rollback(stage) == {"rollback_restored": True}
    assert sha(stage.store) == before and not stage.bak.exists() and stage.new.exists()


@pytest.mark.parametrize("fault", ["job", "wal", "baseline"])
def test_the_preflight_refuses_a_busy_or_wrong_store(tmp_path, monkeypatch, fault):
    stage, _ = old_store(tmp_path, monkeypatch)
    if fault == "job":
        monkeypatch.setattr(migrate, "loaded_jobs", lambda: ["123 0 com.ark.sync"])
    elif fault == "wal":
        stage.store.with_name("ark.duckdb.wal").write_bytes(b"")
    else:
        stage = migrate.replace(stage, marker=OLDER)
    with pytest.raises(migrate.Refused):
        migrate.preflight(stage)
