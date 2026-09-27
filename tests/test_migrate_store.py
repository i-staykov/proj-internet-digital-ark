"""Stage B rebuilds the store with only our rows from the provenance Parquet, the new file exports
byte for byte what the old one did, and the restore brings back the captures stage A dropped."""

import hashlib
import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from his_release import MARKER, WEB_METHOD, capture, stage

from ark import held
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db
from ark.hostnames import ISC_METHOD, ISC_SOURCE_NAME
from ark.hostnames import SOURCE_NAME as HOST_SOURCE
from ark.ingest import YEARS

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "migrate_store", ROOT / "scripts/round/migrate_store.py"
)
migrate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = migrate
SPEC.loader.exec_module(migrate)

HIS_TYPE, HIS_SOURCE = migrate.HIS_TYPE, migrate.HIS_SOURCE
OLDER = "merged260101"

# The schema of a store stage B has not rebuilt: his rows' type in the CHECK, a key on
# `evidence` and foreign keys. The code no longer makes it, so the fixtures do.
STAGE_A_DDL = """
CREATE SEQUENCE IF NOT EXISTS source_seq START 1;
CREATE TABLE source (
    source_id  INTEGER PRIMARY KEY DEFAULT nextval('source_seq'),
    name       TEXT NOT NULL UNIQUE,
    kind       TEXT NOT NULL CHECK (kind IN ('timestamped', 'candidate_only')),
    notes      TEXT
);
CREATE TABLE domain (
    domain            TEXT PRIMARY KEY,
    tld               TEXT,
    discovered_source INTEGER NOT NULL REFERENCES source(source_id),
    discovered_round  INTEGER NOT NULL DEFAULT 0,
    first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE SEQUENCE IF NOT EXISTS evidence_seq START 1;
CREATE TABLE evidence (
    evidence_id        BIGINT PRIMARY KEY DEFAULT nextval('evidence_seq'),
    domain             TEXT NOT NULL REFERENCES domain(domain),
    source_id          INTEGER NOT NULL REFERENCES source(source_id),
    evidence_year      INTEGER NOT NULL CHECK (evidence_year BETWEEN 1996 AND 2001),
    evidence_type      TEXT NOT NULL CHECK (evidence_type IN ('artifact_listing',
        'cdx_timestamp', 'dated_directory', 'link_source', 'link_target', 'prior_reused',
        'whois_creation')),
    evidence_value     TEXT NOT NULL,
    evidence_url       TEXT,
    acquisition_method TEXT,
    captured_at        TIMESTAMPTZ,
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE domain_year (
    domain        TEXT    NOT NULL REFERENCES domain(domain),
    assigned_year INTEGER NOT NULL CHECK (assigned_year BETWEEN 1996 AND 2001),
    evidence_id   BIGINT  NOT NULL REFERENCES evidence(evidence_id),
    verified_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (domain, assigned_year)
);
CREATE TABLE hostname_year (
    hostname      TEXT    NOT NULL,
    parent_domain TEXT    NOT NULL REFERENCES domain(domain),
    assigned_year INTEGER NOT NULL CHECK (assigned_year BETWEEN 1996 AND 2001),
    evidence_id   BIGINT  NOT NULL REFERENCES evidence(evidence_id),
    verified_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (hostname, assigned_year)
);
CREATE TABLE ingested_file (
    source_name TEXT NOT NULL,
    file_name   TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    record_rows BIGINT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_name, file_name)
);
CREATE TABLE domain_language (
    domain        TEXT    NOT NULL REFERENCES domain(domain),
    assigned_year INTEGER NOT NULL CHECK (assigned_year BETWEEN 1996 AND 2001),
    verdict       TEXT    NOT NULL CHECK (verdict IN ('english', 'other', 'undetermined')),
    english_share DOUBLE,
    samples       INTEGER NOT NULL DEFAULT 0,
    top_other     TEXT,
    evidence_urls TEXT    NOT NULL DEFAULT '',
    reason        TEXT,
    engine_version INTEGER DEFAULT 0,
    classified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (domain, assigned_year)
);
"""
T0 = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def old_db(path: Path, starts: dict[str, int] | None = None) -> duckdb.DuckDBPyConnection:
    """An empty store of the shape stage B reads, its sequences starting at `starts`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    for name, start in (starts or {}).items():
        conn.execute(f"CREATE SEQUENCE {name} START WITH {start}")
    for statement in STAGE_A_DDL.split(";"):
        if statement.strip():
            conn.execute(statement)
    conn.execute(migrate.METRICS_TABLE)
    return conn


def ev(conn, domain, source, year, kind, value, url=None, method=WEB_METHOD, when=T0) -> int:
    """One evidence row as the old store took it, filed under its domain."""
    add_candidate(conn, domain, source)
    return conn.execute(
        "INSERT INTO evidence (domain, source_id, evidence_year, evidence_type, evidence_value, "
        "evidence_url, acquisition_method, ingested_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "RETURNING evidence_id",
        [domain, source, year, kind, value, url, method, when],
    ).fetchone()[0]


def ledger(conn, source: str, file: str, rows: int, when: datetime) -> None:
    conn.execute("INSERT INTO ingested_file VALUES (?, ?, 'sha', ?, ?)", [source, file, rows, when])


def rows(path: Path, query: str) -> list:
    conn = duckdb.connect(str(path), read_only=True)
    try:
        return conn.execute(query).fetchall()
    finally:
        conn.close()


def wayback(stamp: str, host: str) -> str:
    return f"https://web.archive.org/web/{stamp}/http://{host}/"


LOST_200 = "nypw timemap capture 19990505120000"


def stage_a_store(tmp: Path, monkeypatch) -> tuple:
    """The store before stage A, the stage-A store stage B reads, and his release. What each
    name stands for:

    a.com         his current row dates it and its record cites it; we capture it too: the
                  record moves to our row
    z.com         only his rows name it, and his release filed it: record and name go
    q.com         only his row dates it, but a source of ours filed it: the record goes
    seed.com      a source of ours filed it and no row names it: it stays
    keep.com      our capture, from a bulk file whose ledger row shares its timestamp
    shop.d2.com   a lane's capture, its ledger row five minutes on: a hostname record
    zone.com      a zone listing, whose ledger row counts no rows by design
    mail.new.com  a lane's capture after which only a file that added nothing was ledgered
    lost.com      stage A kept our 404 TimeMap capture, which its record cites, and dropped
                  our 200 one: the restore brings it back and dates the pair
    """
    monkeypatch.setattr(migrate, "loaded_jobs", lambda: [])
    monkeypatch.setattr(migrate, "holders", lambda path: [])
    monkeypatch.setattr(migrate, "newest_credited_day", lambda: None)
    folder = stage(tmp / "release")
    held.prepare(folder)
    monkeypatch.setattr(held, "his_dir", lambda: folder)
    data = tmp / "data"
    pre = data / "ark.duckdb.pre-stage-a.bak"
    conn = old_db(pre)
    his = ensure_source(conn, HIS_SOURCE, "timestamped")
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    hosts = ensure_source(conn, HOST_SOURCE, "timestamped")
    zone = ensure_source(conn, "internic_zone_hostnames", "timestamped")
    isc = ensure_source(conn, ISC_SOURCE_NAME, "timestamped")
    nypw = ensure_source(conn, "nypw_timemap", "timestamped")
    seed = ensure_source(conn, "seed", "timestamped")
    dropped = []

    def his_row(domain, year, marker):
        eid = ev(conn, domain, his, year, HIS_TYPE, f"{marker}/{year}.txt", None, HIS_SOURCE)
        assign_year(conn, eid)
        return eid

    his_row("a.com", 1997, MARKER)
    dropped.append(ev(conn, "a.com", his, 1997, HIS_TYPE, f"{OLDER}/1997.txt", None, HIS_SOURCE))
    his_row("z.com", 2000, MARKER)
    add_candidate(conn, "q.com", cdx)
    his_row("q.com", 1999, MARKER)
    add_candidate(conn, "seed.com", seed)

    stamp = "19970601120000"
    ev(
        conn,
        "a.com",
        cdx,
        1997,
        "cdx_timestamp",
        f"cdx capture {stamp} a.com",
        wayback(stamp, "a.com"),
    )
    keep = capture("keep.com", 1998)
    assign_year(
        conn,
        ev(
            conn,
            "keep.com",
            cdx,
            1998,
            "cdx_timestamp",
            keep,
            "https://web.archive.org/web/1998/keep.com",
        ),
    )
    again = "cdx capture 19980701120000 keep.com"
    dropped.append(ev(conn, "keep.com", cdx, 1998, "cdx_timestamp", again))
    assign_year(conn, ev(conn, "new.com", cdx, 1999, "cdx_timestamp", capture("new.com", 1999)))
    ledger(conn, "ia_cdx", "cdx_1999.txt", 3, T0)

    shop = ev(
        conn, "d2.com", hosts, 2001, "cdx_timestamp", capture("shop.d2.com", 2001), when=at(60)
    )
    ledger(conn, HOST_SOURCE, "hosts_1.jsonl.gz", 1, at(65))
    listing = "internic zone 19970420 ns1.zone.com"
    assign_year(
        conn,
        ev(conn, "zone.com", zone, 1997, "artifact_listing", listing, None, "zone_ns", at(120)),
    )
    ledger(conn, "internic_zone_hostnames", "zone_1997.txt", 0, at(122))
    mail = ev(
        conn, "new.com", hosts, 1999, "cdx_timestamp", capture("mail.new.com", 1999), when=at(180)
    )
    ledger(conn, HOST_SOURCE, "hosts_2.jsonl.gz", 0, at(181))
    survey = "http://nw.com/zone/WWW/0001/isc.hosts/net.gz"
    isc_row = ev(
        conn,
        "isc.net",
        isc,
        2000,
        "artifact_listing",
        "isc survey 2000-01 host mail.isc.net",
        survey,
        ISC_METHOD,
        at(240),
    )
    assign_year(conn, isc_row)
    ledger(conn, ISC_SOURCE_NAME, "net.gz", 0, at(241))

    def timemap(status: str, stamp: str) -> int:
        """A TimeMap capture of lost.com; a status in its value marks an error capture."""
        method = "nypw_timemap_non_200" if status else "nypw_timemap"
        value = f"nypw timemap capture {status}{stamp}"
        url = wayback(stamp, "lost.com")
        return ev(conn, "lost.com", nypw, 1999, "cdx_timestamp", value, url, method, at(300))

    lost_404 = timemap("status 404 ", "19990101000000")
    assign_year(conn, lost_404)
    lost_200 = timemap("", "19990505120000")
    lost_500 = timemap("status 500 ", "19990202000000")
    dropped += [lost_200, lost_500]
    ledger(conn, "nypw_timemap", "nypw_1999.tsv", 3, at(300))

    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES ('shop.d2.com', 'd2.com', 2001, ?), ('mail.new.com', 'new.com', 1999, ?)",
        [shop, mail],
    )
    conn.execute(
        "INSERT INTO domain_language (domain, assigned_year, verdict) "
        "VALUES ('a.com', 1997, 'english'), ('z.com', 2000, 'other')"
    )
    conn.execute(
        "INSERT INTO run_metrics (command, source, metrics_json) VALUES ('collect', 'ia_cdx', '{}')"
    )
    conn.execute("CREATE TABLE prior_merge_stats AS SELECT 'his' AS source, 1 AS merged")
    top = conn.execute(
        "SELECT (SELECT max(evidence_id) FROM evidence), (SELECT max(source_id) FROM source)"
    ).fetchone()
    conn.close()

    # stage A: every row but the dropped ones, the sequences past every id the old store held,
    # then one row a later retraction wrote, with no ledger row
    store = data / "ark.duckdb"
    conn = old_db(store, {"evidence_seq": top[0] + 100, "source_seq": top[1] + 1})
    conn.execute(f"ATTACH '{pre}' AS pre (READ_ONLY)")
    for table in migrate.TABLES:
        kept = f"WHERE evidence_id NOT IN ({', '.join(map(str, dropped))})"
        conn.execute(
            f"INSERT INTO {table} SELECT * FROM pre.{table} {kept if table == 'evidence' else ''}"
        )
    conn.execute("CREATE TABLE prior_merge_stats AS SELECT * FROM pre.prior_merge_stats")
    conn.execute("DETACH pre")
    retraction = "cdx capture 20010101120000 status 404 shop.d2.com"
    late = ev(conn, "d2.com", hosts, 2001, "cdx_timestamp", retraction, when=at(600))
    conn.close()

    s = migrate.Stage(
        store=store,
        new=data / "ark.stage_b.duckdb",
        bak=data / "ark.duckdb.pre-stage-b.bak",
        pre_a=pre,
        work=data / "migrate" / "stage_b" / "run",
        baseline=folder,
        temp=tmp / "duckdb_tmp",
        audit=tmp / "no-audit.tsv.gz",
        live_out=tmp / "output" / "netnew",
        floor_gib=0,
        footprint_gib=0,
    )
    return s, {"lost_200": lost_200, "late": late, "start": top[0] + 100}


def test_the_new_store_holds_our_rows_alone_exports_the_same_and_rolls_back(tmp_path, monkeypatch):
    s, ids = stage_a_store(tmp_path, monkeypatch)
    assert migrate.Stage.load(s.save()) == s
    # files beside the run are never cleared
    (s.work.parent / "before").mkdir(parents=True)
    (s.work.parent / "other.csv").write_text("kept\n")
    before = sha(s.store)
    report = migrate.stage_b_run(s)
    checks = report.get("verify", {}).get("checks", {})
    assert report["swap_ready"], (
        {k: v for k, v in checks.items() if not v["ok"]},
        report.get("restore"),
    )
    assert "ALL PASS" in checks["integrity_checks"]["report"]
    assert checks["exports_byte_identical"]["files"] > 20
    assert (s.work.parent / "other.csv").read_text() == "kept\n"
    assert (s.work.parent / "before").is_dir()

    planned = report["plan"]
    assert planned["domain_year_repointed_from_his"] == 1  # a.com moves to our capture
    assert planned["domain_year_dropped"] == 2  # z.com and q.com, which only his rows date
    assert planned["his_only_domains_dropped"] == 1  # z.com
    assert planned["seed_only_domains_kept"] == 2  # seed.com and q.com
    assert planned["domain_language_dropped"] == 1  # the verdict on z.com
    assert planned["next_ids"]["evidence_seq"] == ids["late"] + 1
    assert planned["tightened"] == {"domain_language.engine_version": 0}

    # no row of his, no key on evidence, no foreign key, and the other keys kept
    assert rows(s.new, f"SELECT count(*) FROM evidence WHERE evidence_type = '{HIS_TYPE}'") == [
        (0,)
    ]
    assert rows(
        s.new,
        "SELECT table_name, constraint_type FROM duckdb_constraints() "
        "WHERE constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY') ORDER BY ALL",
    ) == [
        ("domain", "PRIMARY KEY"),
        ("domain_language", "PRIMARY KEY"),
        ("domain_year", "PRIMARY KEY"),
        ("hostname_year", "PRIMARY KEY"),
        ("ingested_file", "PRIMARY KEY"),
        ("source", "PRIMARY KEY"),
        ("source", "UNIQUE"),
    ]
    assert rows(
        s.new, "SELECT start_value FROM duckdb_sequences() WHERE sequence_name = 'evidence_seq'"
    ) == [(ids["late"] + 1,)]
    assert report["figures"]["prior_reused_rows"] == 0 and report["figures"]["netnew_identical"]

    # every row of ours as the old store held it, `ingested_at` included, and the restored one
    # as the store before stage A held it
    cols = "evidence_id, domain, source_id, evidence_year, evidence_type, evidence_value, "
    cols += "evidence_url, acquisition_method, captured_at::VARCHAR, ingested_at::VARCHAR"
    ours = rows(s.store, f"SELECT {cols} FROM evidence WHERE evidence_type <> '{HIS_TYPE}'")
    lost = rows(s.pre_a, f"SELECT {cols} FROM evidence WHERE evidence_id = {ids['lost_200']}")
    assert rows(s.new, f"SELECT {cols} FROM evidence ORDER BY 1") == sorted(ours + lost)

    # the file each row was read from, where a ledger row alone matches its batch, and the
    # capture URL naming its place
    located = {
        v: (f, loc)
        for v, f, loc in rows(
            s.new, "SELECT evidence_value, source_file, record_location FROM evidence"
        )
    }
    assert located == {
        "cdx capture 19970601120000 a.com": ("cdx_1999.txt", wayback("19970601120000", "a.com")),
        capture("keep.com", 1998): ("cdx_1999.txt", None),
        capture("new.com", 1999): ("cdx_1999.txt", None),
        capture("shop.d2.com", 2001): ("hosts_1.jsonl.gz", None),
        "internic zone 19970420 ns1.zone.com": ("zone_1997.txt", None),
        capture("mail.new.com", 1999): (None, None),
        "isc survey 2000-01 host mail.isc.net": ("net.gz", None),
        "nypw timemap capture status 404 19990101000000": (
            "nypw_1999.tsv",
            wayback("19990101000000", "lost.com"),
        ),
        LOST_200: ("nypw_1999.tsv", wayback("19990505120000", "lost.com")),
        "cdx capture 20010101120000 status 404 shop.d2.com": (None, None),
    }
    assert report["figures"]["nulls_by_source"][HOST_SOURCE] == {
        "rows": 3,
        "source_file_null": 2,
        "record_location_null": 3,
    }

    # the restore dates exactly one pair, and its line is the only one it adds
    restored = report["restore"]
    assert restored["rows"] == 1 and restored["repointed"] == 1
    figures = report["figures"]
    assert figures["evidence_rows_restored"] == figures["evidence_rows"] + 1
    assert figures["restored_rows"] == 1 and figures["checks_failed"] == []
    assert {int(y): n for y, n in restored["added_by_year"].items()} == {
        **dict.fromkeys(YEARS, 0),
        1999: 1,
    }
    assert rows(s.new, "SELECT evidence_id FROM domain_year WHERE domain = 'lost.com'") == [
        (ids["lost_200"],)
    ]
    assert "lost.com" not in (s.work / "after" / "netnew" / "1999.txt").read_text().split()
    assert "lost.com" in (s.work / "restored" / "netnew" / "1999.txt").read_text().split()

    assert sha(s.store) == before
    migrate.write(s.record("swap"), migrate.swap(s))
    assert sha(s.bak) == before and sha(s.store) == report["new_sha256"]
    assert migrate.rollback(s) == {"rollback_restored": True}
    assert sha(s.store) == before and not s.bak.exists() and s.new.exists()


def test_a_failed_verification_restores_nothing_and_cannot_swap(tmp_path, monkeypatch):
    s, _ = stage_a_store(tmp_path, monkeypatch)
    real = migrate._verify
    monkeypatch.setattr(migrate, "_verify", lambda *a: real(*a) | {"planted": {"ok": False}})
    report = migrate.stage_b_run(s)
    assert not report["swap_ready"] and "restore" not in report
    assert report["steps"][-1]["step"] == "verify"
    assert report["figures"]["checks_failed"] == ["planted"]
    with pytest.raises(migrate.Refused, match="swap_ready"):
        migrate.swap(s)


def test_a_rehearsal_runs_every_step_on_a_sample_and_leaves_the_store(tmp_path, monkeypatch):
    s, _ = stage_a_store(tmp_path, monkeypatch)
    before = sha(s.store)
    report = migrate.stage_b_rehearse(s, 100)
    assert report["swap_ready"] and report["rollback_restored"] and report["live_store_unchanged"]
    assert report["figures"]["restored_rows"] == 1
    sample = s.sample()
    left = [sample.store, sample.new, sample.bak, sample.work / "plan.duckdb"]
    assert not any(p.exists() for p in left) and sample.record("report").is_file()
    assert sha(s.store) == before


@pytest.mark.parametrize(
    ("fault", "says"),
    [("job", "launchd"), ("wal", "wal"), ("rebuilt", "no key"), ("backup", "restore")],
)
def test_the_preflight_refuses_a_busy_or_wrong_store(tmp_path, monkeypatch, fault, says):
    s, _ = stage_a_store(tmp_path, monkeypatch)
    if fault == "job":
        monkeypatch.setattr(migrate, "loaded_jobs", lambda: ["123 0 com.ark.sync"])
    elif fault == "wal":
        s.store.with_name("ark.duckdb.wal").write_bytes(b"")
    elif fault == "rebuilt":
        s.store.unlink()
        conn = connect(s.store)
        init_db(conn)
        conn.execute(migrate.METRICS_TABLE)
        conn.close()
    else:
        s.pre_a.unlink()
    with pytest.raises(migrate.Refused, match=says):
        migrate.preflight(s)


def test_the_new_ids_start_past_every_id_a_closed_store_issued(tmp_path):
    """A sequence never used keeps the start stage A set past the ids it dropped; one used is
    read back with the id it would issue next, past rows deleted since."""
    path = tmp_path / "ark.duckdb"
    conn = old_db(path, {"evidence_seq": 500})
    src = ensure_source(conn, "ia_cdx", "timestamped")
    add_candidate(conn, "a.com", src)
    conn.execute(
        "INSERT INTO evidence (evidence_id, domain, source_id, evidence_year, evidence_type, "
        "evidence_value) VALUES (20, 'a.com', ?, 1999, 'cdx_timestamp', 'v')",
        [src],
    )
    conn.close()

    def planned() -> dict[str, int]:
        conn = duckdb.connect()
        conn.execute(f"ATTACH '{path}' AS old (READ_ONLY)")
        try:
            return migrate.next_ids(conn, "old")
        finally:
            conn.close()

    assert planned() == {"evidence_seq": 500, "source_seq": 2}
    conn = duckdb.connect(str(path))
    conn.execute("SELECT nextval('evidence_seq') FROM range(3)").fetchall()
    conn.close()
    assert planned()["evidence_seq"] == 503


def test_the_plan_refuses_a_null_the_new_schema_would_refuse(tmp_path, monkeypatch):
    s, _ = stage_a_store(tmp_path, monkeypatch)
    conn = duckdb.connect(str(s.store))
    conn.execute("UPDATE domain_language SET engine_version = NULL WHERE domain = 'a.com'")
    conn.close()
    with pytest.raises(migrate.Refused, match="engine_version.: 1"):
        migrate.plan(s)


def test_the_restore_explains_only_the_lines_of_the_pairs_it_dated(tmp_path):
    def export_of(name: str, dated: list[str], pool: list[str]) -> Path:
        root = tmp_path / name
        (root / "reports").mkdir(parents=True)
        (root / "netnew").mkdir()
        (root / "netnew" / "1999.txt").write_text(names(*dated))
        (root / "netnew" / "candidate_additions.txt").write_text(names(*pool))
        manifest = [row(d, 1999, capture(d, 1999)) for d in dated]
        (root / "netnew" / "evidence_manifest.csv").write_text(names(MANIFEST, *manifest))
        for rel in ("reports/year_growth.csv", "reports/source_contribution.csv"):
            (root / rel).write_text(f"{name}\n")  # a tally follows the lines
        (root / "candidate_unverified.txt").write_text("undated.com\n")
        return root

    was = export_of("was", ["keep.com"], ["lost.com", "other.com"])
    now = export_of("now", ["keep.com", "lost.com"], ["other.com"])
    conn = duckdb.connect()
    conn.execute("CREATE TEMP TABLE dated_pair AS SELECT 'lost.com' AS domain, 1999 AS year")
    changes = migrate.restore_changes(conn, was, now)
    assert changes["unexplained"] == 0
    assert changes["added_by_year"] == {**dict.fromkeys(YEARS, 0), 1999: 1}
    assert changes["files"]["netnew/candidate_additions.txt"]["removed"] == 1

    # a line no restored pair dates, and a file the restore has no reason to touch
    now = export_of("stray", ["keep.com", "lost.com", "stray.com"], ["other.com"])
    (now / "candidate_unverified.txt").write_text("")
    changes = migrate.restore_changes(conn, was, now)
    assert changes["files"]["netnew/1999.txt"]["unexplained"] == 1
    assert changes["files"]["netnew/evidence_manifest.csv"]["unexplained"] == 1
    assert changes["files"]["candidate_unverified.txt"] == {"unexplained": 1, "why": "changed"}
    assert changes["unexplained"] == 3


MANIFEST = (
    "domain,assigned_year,evidence_type,evidence_value,source,acquisition_method,evidence_url"
)


def names(*lines: str) -> str:
    return "".join(f"{line}\n" for line in lines)


def row(domain: str, year: int, value: str, method: str = WEB_METHOD) -> str:
    return f"{domain},{year},cdx_timestamp,{value},ia_cdx,{method},"
