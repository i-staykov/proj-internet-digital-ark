"""Stage A rebuilds the store without his superseded rows and our duplicates, and the rebuilt
file exports byte for byte what the old one did. `deltas` gives every line two exports differ by
its reason."""

import hashlib
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest
from his_release import MARKER, WEB_METHOD, capture, stage, text

from ark import held
from ark.baseline import CURRENT_BASELINE_MARKER
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.evidence_types import HIS_SOURCE, HIS_TYPE
from ark.hostnames import ISC_METHOD, ISC_SOURCE_NAME
from ark.hostnames import SOURCE_NAME as HOST_SOURCE
from ark.ingest import YEARS
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


def his_rows(conn, path: Path, year: int, prefix: str) -> None:
    """His year file as his release is loaded into a store: one row per registrable, marked
    with the file, and the year for every pair nothing dated first."""
    sid = ensure_source(conn, HIS_SOURCE, "timestamped")
    marker = f"{prefix}/{path.name}" if prefix else path.name
    names = {add_candidate(conn, line.strip(), sid) for line in path.read_text().splitlines()}
    for domain in sorted(n for n in names if n):
        eid = record_evidence(conn, domain, sid, year, HIS_TYPE, marker, None, HIS_SOURCE)
        assign_year(conn, eid)


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
            his_rows(conn, folder / f"{year}.txt", year, prefix)
    (folder / "candidate_pool.txt").write_text("already-his-candidate.com\n")
    # both exports diff against the current release, prepared as `ark intake` does
    held.prepare(folder)
    monkeypatch.setattr(held, "his_dir", lambda: folder)

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
    store.parent.mkdir()
    conn = connect(store)
    init_db(conn)
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    whois = ensure_source(conn, "domain_creation_bulk", "timestamped")
    hosts = ensure_source(conn, HOST_SOURCE, "timestamped")
    his_source = ensure_source(conn, HIS_SOURCE, "timestamped")

    def ours(domain, year, value, method=WEB_METHOD, kind="cdx_timestamp", source=cdx):
        add_candidate(conn, domain, source)
        return record_evidence(conn, domain, source, year, kind, value, None, method)

    def his(domain, year, marker):
        add_candidate(conn, domain, his_source)
        eid = record_evidence(conn, domain, his_source, year, HIS_TYPE, marker, None, HIS_SOURCE)
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
    # nothing dates the first; his 2000.txt and his pool hold the others by exact name
    case = deltas_case(
        tmp_path, monkeypatch, ["planted.com", "already-his.com"], ["held-candidate.com"]
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
    pool = ["known.com", "mx.hd.com", "roll.com", "sub.com"]
    (case["after"] / "2000.txt").write_text(names("keep.com", "keep2.com", "sup.com"))
    (case["after"] / "candidate_additions.txt").write_text(names(*pool))
    (case["after"] / "candidate_additions_summary.json").write_text(json.dumps({"candidates": 4}))
    assert migrate.deltas_main(argv, root=tmp_path) == 0
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
    store.parent.mkdir()
    conn = connect(store)
    init_db(conn)
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    his_source = ensure_source(conn, HIS_SOURCE, "timestamped")
    add_candidate(conn, "ours.com", cdx)
    value = capture("ours.com", 1999)
    assign_year(
        conn, record_evidence(conn, "ours.com", cdx, 1999, "cdx_timestamp", value, None, SWEEP)
    )
    # his rows as his releases were loaded: rolled.com from his www.rolled.com, old.com from an
    # older release alone, already-his.com in each year his files hold it
    his = [("rolled.com", 1999, MARKER), ("old.com", 1998, OLDER)]
    his += [("already-his.com", year, MARKER) for year in YEARS]
    for domain, year, marker in his:
        add_candidate(conn, domain, his_source)
        value = f"{marker}/{year}.txt"
        eid = record_evidence(conn, domain, his_source, year, HIS_TYPE, value, None, HIS_SOURCE)
        assign_year(conn, eid)
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
