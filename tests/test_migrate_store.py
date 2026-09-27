"""Stage B rebuilds the store with only our rows from the provenance Parquet, the new file exports
byte for byte what the old one did, and the restore brings back the captures stage A dropped.
`deltas` and `lane-deltas` give every line two exports or two lane runs differ by its reason."""

import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest
from his_release import MARKER, WEB_METHOD, capture, stage, text

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
SWEEP = "ia_cdx_domain_sweep"

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
    # the diffs' own files beside the run are never cleared
    (s.work.parent / "before").mkdir(parents=True)
    (s.work.parent / "deltas.csv").write_text("kept\n")
    before = sha(s.store)
    report = migrate.stage_b_run(s)
    checks = report.get("verify", {}).get("checks", {})
    assert report["swap_ready"], (
        {k: v for k, v in checks.items() if not v["ok"]},
        report.get("restore"),
    )
    assert "ALL PASS" in checks["integrity_checks"]["report"]
    assert checks["exports_byte_identical"]["files"] > 20
    assert (s.work.parent / "deltas.csv").read_text() == "kept\n"
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


# His calculator, stubbed: one EE per distinct name in the file. Like `test_intake.py`'s stub, it
# writes no `invalid_records`.
CALCULATOR = """
import json, pathlib, sys
names = {n for n in pathlib.Path(sys.argv[1]).read_text().splitlines() if n.strip()}
out = pathlib.Path(sys.argv[sys.argv.index("--output-dir") + 1])
out.mkdir(parents=True, exist_ok=True)
(out / "summary.json").write_text(json.dumps({"equivalent_english_domains": f"{len(names)}.0000"}))
"""
MANIFEST = (
    "domain,assigned_year,evidence_type,evidence_value,source,acquisition_method,evidence_url"
)
HOST_MANIFEST = (
    "hostname,parent_domain,assigned_year,evidence_type,evidence_value,source,"
    "acquisition_method,evidence_url"
)
HEADER_PROVENANCE = (
    "hostname,target_year,source,acquisition_method,evidence_type,record_location,source_url"
)


def names(*lines: str) -> str:
    return "".join(f"{line}\n" for line in lines)


# the attested pairs both exports hold, as `year name` words
KEPT = "1998 recite.com 1999 rolled.com 2000 keep.com 2000 keep2.com 2000 sup.com 2001 roll.com"
KEPT += " 2001 sub.com"
GONE = "1998 gone.com"


def attested(*words: str) -> str:
    """`YYYY<TAB>name` lines in `LC_ALL=C` order, from `year name` words."""
    w = " ".join(words).split()
    return names(*sorted(f"{y}\t{d}" for y, d in zip(w[::2], w[1::2], strict=True)))


def row(domain: str, year: int, value: str, method: str = WEB_METHOD) -> str:
    return f"{domain},{year},cdx_timestamp,{value},ia_cdx,{method},"


def export(folder: Path, files: dict[str, str]) -> Path:
    """An export: `netnew/` with the files every export writes, and the list beside it."""
    netnew = folder / "netnew"
    netnew.mkdir(parents=True)
    empty = {f"{y}{s}.txt": "" for y in range(1996, 2002) for s in ("", "_hostnames", "-ISC")}
    common = {
        "isc_candidates.txt": "",
        "isc_candidates_summary.json": json.dumps({"candidates": 0}),
        "isc_survey_provenance.csv": names("hostname,target_year,survey_edition,source_file"),
        "header_candidates_exclusions.csv": names("hostname,scope,source_file"),
        "candidates_unparsed.txt": "unparsed.example\n",
        "export_stamp.json": json.dumps({"mode": "full", "written_at": str(folder)}),
    }
    for name, body in (empty | common | files).items():
        (folder / name if name == "candidate_unverified.txt" else netnew / name).write_text(body)
    for name in ("candidate_additions", "header_candidates"):
        count = len((netnew / f"{name}.txt").read_text().splitlines())
        (netnew / f"{name}_summary.json").write_text(json.dumps({"candidates": count}))
    return netnew


def deltas_case(tmp: Path, monkeypatch, planted=(), planted_candidates=()) -> dict:
    """His release, a store, and two exports of it that differ by a line of every reason. What
    each domain stands for:

    keep.com     our exact capture, in both exports
    keep2.com    cited a capture of shop.keep2.com, and now our exact capture: re-cited row
    recite.com   cited a WHOIS row, and now our exact capture: re-cited, out of the pool
    rolled.com   his www.rolled.com was loaded as it, and we capture it exactly: released
    sup.com      only his older release held it, and we capture it exactly: superseded-only
    gone.com     only his older release dated it: superseded-only, out of the attested list
    sub.com      only a capture of shop.sub.com dated it: withdrawn, into the pool
    roll.com     only `cdx capture 2001` dated it: converter roll-up, into the pool
    rollup.com   only his www.rollup.com dated it: his row only
    known.com    as rollup.com, and a source of ours filed it: into the pool and the list
    mx.hd.com    dated in 1999 by a capture of hd.com, in 2000 by a header: withdrawn, into
                 the pool and the header candidates
    """
    his_1997 = ["already-his.com", "www.known.com", "www.rollup.com"]
    folder = stage(tmp / "release", {"1997.txt": text(sorted(his_1997))})
    held.prepare(folder)
    calculator = tmp / "equivalent_english_domains.py"
    calculator.write_text(CALCULATOR)
    monkeypatch.setattr(migrate, "calculator_path", lambda: calculator)

    store = tmp / "store" / "ark.duckdb"
    conn = old_db(store)
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    whois = ensure_source(conn, "domain_creation_bulk", "timestamped")
    hosts = ensure_source(conn, HOST_SOURCE, "timestamped")
    his_source = ensure_source(conn, HIS_SOURCE, "timestamped")

    def ours(domain, year, value, method=WEB_METHOD, kind="cdx_timestamp", source=cdx):
        return ev(conn, domain, source, year, kind, value, None, method)

    def his(domain, year, marker):
        eid = ev(conn, domain, his_source, year, HIS_TYPE, marker, None, HIS_SOURCE)
        assign_year(conn, eid)
        return eid

    assign_year(conn, ours("keep.com", 2000, capture("keep.com", 2000)))
    assign_year(conn, ours("keep2.com", 2000, capture("shop.keep2.com", 2000)))
    ours("keep2.com", 2000, capture("keep2.com", 2000))
    assign_year(conn, ours("recite.com", 1998, "1998-03-01", "whois_bulk", "whois_creation", whois))
    ours("recite.com", 1998, capture("recite.com", 1998))
    his("rolled.com", 1999, f"{MARKER}/1999.txt")
    ours("rolled.com", 1999, capture("rolled.com", 1999))
    superseded = {
        "gone.com": (1998, his("gone.com", 1998, f"{OLDER}/1998.txt")),
        "sup.com": (2000, his("sup.com", 2000, f"{OLDER}/2000.txt")),
    }
    ours("sup.com", 2000, capture("sup.com", 2000))
    assign_year(conn, ours("sub.com", 2001, capture("shop.sub.com", 2001)))
    assign_year(conn, ours("roll.com", 2001, "cdx capture 2001", "ia_cdx_collapsed_query"))
    his("rollup.com", 1997, f"{MARKER}/1997.txt")
    add_candidate(conn, "known.com", cdx)
    his("known.com", 1997, f"{MARKER}/1997.txt")
    add_candidate(conn, "lonely.com", cdx)
    parent = ours("hd.com", 1999, capture("hd.com", 1999), source=hosts)
    header = ours("hd.com", 2000, "header 2000 mx.hd.com", "usenet", "artifact_listing", hosts)
    for year, eid in ((1999, parent), (2000, header)):
        conn.execute(
            "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
            "VALUES ('mx.hd.com', 'hd.com', ?, ?)",
            [year, eid],
        )
    conn.close()
    csv_path = tmp / "his_superseded_only.csv"
    csv_path.write_text(
        names("domain,year,marker,evidence_id,cited")
        + "".join(f"{d},{y},{OLDER}/{y}.txt,{i},true\n" for d, (y, i) in superseded.items())
    )

    before = export(
        tmp / "before",
        {
            "2000.txt": names("keep.com", "keep2.com"),
            "2001.txt": names("roll.com", "sub.com"),
            "1999_hostnames.txt": names("mx.hd.com"),
            "candidate_additions.txt": names("recite.com"),
            "header_candidates.txt": "",
            "attested_registrables.txt": attested("1997 known.com 1997 rollup.com", KEPT, GONE),
            "evidence_manifest.csv": names(
                MANIFEST,
                row("keep.com", 2000, capture("keep.com", 2000)),
                row("keep2.com", 2000, capture("shop.keep2.com", 2000)),
                row("roll.com", 2001, "cdx capture 2001", "ia_cdx_collapsed_query"),
                row("sub.com", 2001, capture("shop.sub.com", 2001)),
            ),
            "hostnames_evidence_manifest.csv": names(
                HOST_MANIFEST,
                f"mx.hd.com,hd.com,1999,cdx_timestamp,{capture('hd.com', 1999)},{HOST_SOURCE},"
                f"{WEB_METHOD},",
            ),
            "header_candidates_provenance.csv": names(HEADER_PROVENANCE),
            "SHA256SUMS": "stale\n",
            "candidate_unverified.txt": names("lonely.com"),
        },
    )
    after = export(
        tmp / "after",
        {
            "1998.txt": names("recite.com"),
            "1999.txt": names("rolled.com"),
            "2000.txt": names(*sorted(["keep.com", "keep2.com", "sup.com", *planted])),
            "candidate_additions.txt": names(
                *sorted(["known.com", "mx.hd.com", "roll.com", "sub.com", *planted_candidates])
            ),
            "header_candidates.txt": names("mx.hd.com"),
            "attested_registrables.txt": attested(KEPT),
            "evidence_manifest.csv": names(
                MANIFEST,
                row("keep.com", 2000, capture("keep.com", 2000)),
                row("keep2.com", 2000, capture("keep2.com", 2000)),
                row("recite.com", 1998, capture("recite.com", 1998)),
                row("rolled.com", 1999, capture("rolled.com", 1999)),
                row("sup.com", 2000, capture("sup.com", 2000)),
            ),
            "hostnames_evidence_manifest.csv": names(HOST_MANIFEST),
            "header_candidates_provenance.csv": names(
                HEADER_PROVENANCE,
                f"mx.hd.com,2000,{HOST_SOURCE},usenet,artifact_listing,header 2000 mx.hd.com,",
            ),
            "candidate_unverified.txt": names("known.com", "lonely.com"),
        },
    )
    return {
        "before": before,
        "after": after,
        "store": store,
        "out": tmp / "stage_b" / "deltas.csv",
        "superseded": csv_path,
        "baseline": folder,
    }


# What `deltas` writes for `deltas_case`, in its order: file, name, year, change, detail
c, NOW, OLD, K2 = capture, f"his row {MARKER}", f"his row {OLDER}", capture("keep2.com", 2000)
EXPECTED = f"""file,family,year,name,change,reason,detail
1998.txt,registrable,1998,recite.com,added,re-cited,own capture {c("recite.com", 1998)}
1999.txt,registrable,1999,rolled.com,added,released,{NOW}/1999.txt
1999_hostnames.txt,hostname,1999,mx.hd.com,removed,withdrawn,cited {c("hd.com", 1999)}
2000.txt,registrable,2000,sup.com,added,superseded-only,{OLD}/2000.txt only
2001.txt,registrable,2001,roll.com,removed,converter roll-up,cited cdx capture 2001
2001.txt,registrable,2001,sub.com,removed,withdrawn,cited {c("shop.sub.com", 2001)}
attested_registrables.txt,attested,1998,gone.com,removed,superseded-only,{OLD}/1998.txt only
attested_registrables.txt,attested,1997,known.com,removed,his row only,{NOW}/1997.txt
attested_registrables.txt,attested,1997,rollup.com,removed,his row only,{NOW}/1997.txt
candidate_additions.txt,candidate,,known.com,added,candidate,his roll-up only
candidate_additions.txt,candidate,,mx.hd.com,added,candidate,years withdrawn
candidate_additions.txt,candidate,,recite.com,removed,candidate,moved to 1998.txt
candidate_additions.txt,candidate,,roll.com,added,candidate,years withdrawn
candidate_additions.txt,candidate,,sub.com,added,candidate,years withdrawn
candidate_unverified.txt,unverified,,known.com,added,candidate,his roll-up only
evidence_manifest.csv,manifest,2000,keep2.com,added,re-cited,own capture {K2}
evidence_manifest.csv,manifest,2000,keep2.com,removed,re-cited,cited {c("shop.keep2.com", 2000)}
evidence_manifest.csv,manifest,1998,recite.com,added,re-cited,own capture {c("recite.com", 1998)}
evidence_manifest.csv,manifest,2001,roll.com,removed,converter roll-up,cited cdx capture 2001
evidence_manifest.csv,manifest,1999,rolled.com,added,released,{NOW}/1999.txt
evidence_manifest.csv,manifest,2001,sub.com,removed,withdrawn,cited {c("shop.sub.com", 2001)}
evidence_manifest.csv,manifest,2000,sup.com,added,superseded-only,{OLD}/2000.txt only
header_candidates.txt,header,,mx.hd.com,added,candidate,years withdrawn
header_candidates_provenance.csv,provenance,2000,mx.hd.com,added,candidate,years withdrawn
hostnames_evidence_manifest.csv,manifest,1999,mx.hd.com,removed,withdrawn,cited {c("hd.com", 1999)}
"""


def test_deltas_gives_every_changed_line_its_reason(tmp_path, monkeypatch):
    case = deltas_case(tmp_path, monkeypatch)
    store = sha(case["store"])
    summary = migrate.deltas(**case)

    assert case["out"].read_text() == EXPECTED
    assert summary["lines"] == 25 and summary["unexplained"] == 0
    one = Decimal("1.0000")
    assert summary["by_reason"]["withdrawn"]["removed"] == {"lines": 2, "ee": 2 * one}
    assert summary["by_reason"]["candidate"]["added"] == {"lines": 4, "ee": 4 * one}
    assert summary["by_reason"]["candidate"]["net_ee"] == 3 * one
    assert summary["by_reason"]["released"]["net_ee"] == one
    # the attested list is priced apart, and it is not a claim
    assert "his row only" not in summary["by_reason"]
    assert summary["by_family"]["attested"]["his row only"]["removed"] == {
        "lines": 2,
        "ee": 2 * one,
    }
    assert summary["by_family"]["manifest"]["re-cited"]["added"] == {"lines": 2, "ee": None}
    assert summary["invalid_records"] == 0
    assert summary["skipped"] == ["SHA256SUMS", "candidates_unparsed.txt", "export_stamp.json"]
    assert summary["summaries_consistent"] and len(summary["summaries"]) == 6
    assert summary["by_file"]["attested_registrables.txt"] == {
        "family": "attested",
        "added": 0,
        "removed": 3,
        "unexplained": 0,
    }
    listed = case["out"].parent / "deltas" / "candidate" / "added" / "candidate.txt"
    assert listed.read_text() == names("known.com", "mx.hd.com", "roll.com", "sub.com")
    assert json.loads(case["out"].with_suffix(".json").read_text())["unexplained"] == 0
    assert sorted(p.name for p in case["out"].parent.iterdir()) == [
        "deltas",
        "deltas.csv",
        "deltas.json",
    ]
    assert sha(case["store"]) == store


def test_an_unexplained_line_exits_1_and_a_refusal_2(tmp_path, monkeypatch):
    # nothing dates the first; his 2000.txt and his pool hold the others by exact name; only
    # his rolled-up row names rollup.com and no source of ours filed it, so the export keeps it out
    case = deltas_case(
        tmp_path,
        monkeypatch,
        ["planted.com", "already-his.com"],
        ["held-candidate.com", "rollup.com"],
    )
    monkeypatch.chdir(tmp_path)  # restored after the test; deltas_main chdirs into `root`
    argv = [str(case["before"]), str(case["after"]), "--store", str(case["store"])]
    argv += ["--out", str(case["out"]), "--superseded", str(case["superseded"])]
    argv += ["--baseline", str(case["baseline"])]
    assert migrate.deltas_main(argv, root=tmp_path) == 1
    written = case["out"].read_text().splitlines()
    assert "2000.txt,registrable,2000,planted.com,added,unexplained," in written
    assert "2000.txt,registrable,2000,already-his.com,added,unexplained,in his 2000.txt" in written
    held_line = (
        "candidate_additions.txt,candidate,,held-candidate.com,added,unexplained,in his files"
    )
    assert held_line in written
    assert "candidate_additions.txt,candidate,,rollup.com,added,unexplained," in written
    pool = ["known.com", "mx.hd.com", "roll.com", "sub.com"]
    (case["after"] / "2000.txt").write_text(names("keep.com", "keep2.com", "sup.com"))
    (case["after"] / "candidate_additions.txt").write_text(names(*pool))
    (case["after"] / "candidate_additions_summary.json").write_text(json.dumps({"candidates": 4}))
    assert migrate.deltas_main(argv, root=tmp_path) == 0
    # the calculator lists go in the folder named like --out, never one deltas did not write
    no_csv = [*argv]
    no_csv[no_csv.index("--out") + 1] = str(tmp_path / "deltas_out")
    assert migrate.deltas_main(no_csv, root=tmp_path) == 2
    mark = case["out"].with_suffix("") / migrate.PRICED_MARK
    mark.unlink()
    assert migrate.deltas_main(argv, root=tmp_path) == 2
    mark.write_text("")
    (held.HELD_ROOT / MARKER / "held.json").unlink()
    assert migrate.deltas_main(argv, root=tmp_path) == 2


# A lane in miniature: it asks held about five names, writes the attested ones as a journal and
# the rest as a list, as the splitters do.
TOY_LANE = """
import argparse
from pathlib import Path

import duckdb

from ark import held
from ark.journal import journal_writer, write_journal_line


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    out = ap.parse_args().out
    names = {"ours.com", "rolled.com", "old.com", "already-his.com", "novel.net"}
    conn = duckdb.connect("data/ark.duckdb", read_only=True)
    attested, known = held.attested(conn, names), held.known_years(conn, names)
    conn.close()
    with journal_writer(out / "toy_dated.jsonl.gz") as fh:
        for name in sorted(attested):
            write_journal_line(fh, {"domain": name, "year": 1999})
    (out / "toy_cand.txt").write_text("".join(f"{n}\\n" for n in sorted(names - attested)))
    print(f"{len(known)} pairs already dated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def test_lane_deltas_explains_a_rolled_up_name(tmp_path, monkeypatch, his_files):
    monkeypatch.setattr(migrate, "loaded_jobs", lambda: [])
    monkeypatch.setattr(migrate, "holders", lambda path: [])
    monkeypatch.setenv("ARK_DB_TEMP_DIR", str(tmp_path / "duckdb_tmp"))  # the children's spill
    store = tmp_path / "data" / "ark.duckdb"
    conn = old_db(store)
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    his_source = ensure_source(conn, HIS_SOURCE, "timestamped")
    value = capture("ours.com", 1999)
    assign_year(conn, ev(conn, "ours.com", cdx, 1999, "cdx_timestamp", value, None, SWEEP))
    # his rows as his releases were loaded: rolled.com from his www.rolled.com, old.com from an
    # older release alone, already-his.com in each year his files hold it
    his = [("rolled.com", 1999, MARKER), ("old.com", 1998, OLDER)]
    his += [("already-his.com", year, MARKER) for year in YEARS]
    for domain, year, marker in his:
        value = f"{marker}/{year}.txt"
        assign_year(conn, ev(conn, domain, his_source, year, HIS_TYPE, value, None, HIS_SOURCE))
    conn.close()
    (tmp_path / "toy_input.txt").write_text("five names\n")
    (tmp_path / "toy_split.py").write_text(TOY_LANE)
    # what it wrote last time, against an older store
    (tmp_path / "prev").mkdir()
    (tmp_path / "prev" / "toy_cand.txt").write_text("novel.net\nstale.org\n")
    lanes = {
        "toy": migrate.Lane(
            "toy_split.py", ("--out", "{out}"), ("toy_input.txt",), previous="prev"
        ),
        "gone": migrate.Lane("gone_split.py", ("--out", "{out}"), ("data/raw/gone.zip",)),
    }
    monkeypatch.setattr(migrate, "LANES", lanes)
    monkeypatch.chdir(tmp_path)  # restored after the test; lane_deltas_main chdirs into `root`
    assert migrate.lane_deltas_main(["--only", "toy,gone", "--witness-lines"], root=tmp_path) == 0

    moved = f"toy_split.py,{{}},{migrate.weight_of('x.com')},1,dated,candidate"
    assert (tmp_path / migrate.LANE_CSV).read_text().splitlines() == [
        ",".join(migrate.LANE_COLUMNS),
        "gone,gone_split.py,,,,,,input_absent,data/raw/gone.zip",
        f"toy,{moved.format('old.com')},his_superseded_release,{OLDER}/1998.txt",
        f"toy,{moved.format('rolled.com')},his_rolled_up_hostname,{MARKER}/1999.txt www.rolled.com",
    ]
    report = json.loads((tmp_path / migrate.LANE_JSON).read_text())
    assert report["unexplained"] == report["pairs_unexplained"] == 0 and not report["failed"]
    toy = report["lanes"]["toy"]
    assert [run["exit"] for run in toy["runs"].values()] == [0, 0]
    assert toy["pairs"]["lost_by_reason"] == {
        "his_rolled_up_hostname": 1,
        "his_superseded_release": 1,
    }
    # already-his.com is his exact name, so it stays dated
    assert toy["files"] == {
        "toy_cand.txt": {"before": 1, "after": 3, "only_before": 0, "only_after": 2},
        "toy_dated.jsonl.gz": {"before": 4, "after": 2, "only_before": 2, "only_after": 0},
    }
    assert toy["previous"] == {
        "toy_cand.txt": {"previous_only": 1, "before_only": 0},
        "toy_dated.jsonl.gz": "absent",
    }
    # each run's output goes once diffed; its log and record stay
    assert sorted(p.name for p in (tmp_path / migrate.LANE_ROOT / "toy").iterdir()) == [
        "after.json",
        "after.log",
        "before.json",
        "before.log",
    ]
