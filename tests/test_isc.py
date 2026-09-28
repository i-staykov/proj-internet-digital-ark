"""ISC survey candidates: exact names no annual year holds, each traced, and the file audit."""

import csv
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from ark import export, held
from ark.baseline import CURRENT_BASELINE_MARKER
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.english_share import weight_of
from ark.ingest import YEARS

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts/round/verify_isc_candidates.py"
SPEC = importlib.util.spec_from_file_location("verify_isc_candidates", AUDIT)
SPEC.loader.exec_module(audit := importlib.util.module_from_spec(SPEC))
PROV, SUMMARY = "isc_survey_provenance.csv", "isc_candidates_summary.json"
SHARE, WEIGHTS = ROOT / "src/ark/english_share.py", ROOT / "src/ark/data/tld_english_share.json"
FIELDS = ("evidence_url", "acquisition_method", "evidence_value")
MISSING = [(f, "run uv run ark intake") for f in ("candidate_pool.txt", "1998.txt")]
MISSING += [(f, "incomplete provenance") for f in FIELDS]
TAMPER = [  # (file, pattern, replacement, the refusal, id): any year's exact name, any key, a count
    ("b/candidate_pool.txt", r"\A", "  KEEP.example.com  \n", "overlap", "reviewer_pool"),
    ("b/2001.txt", r"\A", "  KEEP.example.com  \n", "overlap", "reviewer_annual"),
    ("a/2001.txt", r"\A", "  KEEP.example.com  \n", "overlap", "local_annual"),
    (f"c/{PROV}", r"keep\.example\.com,1997,.*\n", "", "provenance", "provenance-missing"),
    (f"c/{PROV}", r"\Z", "extra.example.com,1997,e,x,u,r,m\n", "provenance", "provenance-extra"),
    (f"c/{PROV}", r"com\.gz,(http://nw\.com/zone/9707)", r",\1", "provenance", "provenance-blank"),
    (f"c/{SUMMARY}", "0.6321", "1.2642", "does not reproduce", "stale_summary"),
]  # fmt: skip


@pytest.fixture
def collection(tmp_path):
    (baseline := tmp_path / CURRENT_BASELINE_MARKER).mkdir()
    files = {f"{y}.txt": "" for y in YEARS} | {"2001.txt": "  ANNUAL.example.com  \nexample.com\n"}
    files["candidate_pool.txt"] = " POOL.example.com \npool.example.com\nwww.alias.example.com\n"
    for name, text in files.items():
        (baseline / name).write_text(text)
    held.prepare(baseline)
    init_db(conn := connect(":memory:"))
    source = ensure_source(conn, export.ISC_SOURCE, "timestamped")
    web = ensure_source(conn, "web", "timestamped")
    for parent in ("example.com", "example.uk", "example.site", "other.com"):
        add_candidate(conn, parent, source)
    eid = record_evidence(conn, "example.com", web, 2000, "cdx_timestamp", "20000101000000")
    assign_year(conn, eid)
    sql = "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) VALUES"
    conn.execute(sql + " ('local.example.com', 'example.com', 2000, ?)", [eid])
    sql = "INSERT INTO domain (domain, tld, discovered_source) VALUES"
    conn.execute(sql + " ('annual.other.com', 'com', ?)", [web])
    eid = record_evidence(conn, "annual.other.com", web, 2001, "cdx_timestamp", "20010101000000")
    assign_year(conn, eid)
    return conn, source, baseline, tmp_path / "isc_survey_hostnames"


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


def test_reconciles_all_years_exact_names_and_leaves_every_annual_output_alone(collection):
    conn, source, baseline, out = collection
    ann = out.parent / "annual_export"
    paths = [ann / f"{y}{suffix}.txt" for y in YEARS for suffix in ("", "_hostnames")]
    paths += [ann / "evidence_manifest.csv", ann / "hostnames_evidence_manifest.csv"]
    cast = "SELECT * REPLACE (verified_at::VARCHAR AS verified_at) FROM {} ORDER BY ALL"
    dirs = {"netnew_dir": ann, "report_dir": ann / "reports", "provenance_dir": ann / "provenance"}

    def annual():
        export.export_all(conn, candidates_path=ann / "candidates.txt", baseline=baseline, **dirs)
        tables = [conn.execute(cast.format(t)).fetchall() for t in ("domain_year", "hostname_year")]
        return {p: p.read_bytes() for p in paths}, tables

    annual_before, empty = annual(), write_collection(conn, baseline, out)
    assert empty["isc_candidates"] == empty["isc_provenance_rows"] == 0
    assert json.loads((out / SUMMARY).read_text())["equivalent_english"] == "0.0000"
    labels = ("keep", "pool", "annual", "local", "alias", "www.alias", "www", "bad_name")
    for host in [f"{n}.example.com" for n in labels] + ["example.com", "outside.other.com"]:
        observe(conn, source, host)
    observe(conn, source, "annual.other.com", parent="other.com")
    for year, month in ((1997, "07"), (1996, "01"), (1996, "01")):
        observe(conn, source, "keep.example.com", year, month)
    observe(conn, source, "keep.example.uk", parent="example.uk")
    observe(conn, source, "future.example.site", parent="example.site")
    stats = write_collection(conn, baseline, out)
    names = ["alias.example.com", "keep.example.com", "keep.example.uk", "www.example.com"]
    assert (out / "isc_candidates.txt").read_text().splitlines() == names
    assert (out / "1996-ISC.txt").read_text().splitlines() == names
    assert (out / "1997-ISC.txt").read_text() == "keep.example.com\n"
    assert (stats["isc_candidates"], stats["isc_provenance_rows"]) == (4, 6)
    rows = list(csv.DictReader((out / PROV).open()))
    want = {*((host, 1996) for host in names), ("keep.example.com", 1997)}
    assert {(r["hostname"], int(r["target_year"])) for r in rows} == want
    assert {r["survey_edition"] for r in rows} == {"1996-01", "1996-07", "1997-07"}
    assert all(r["source_file"] == "com.gz" and all(r.values()) for r in rows)
    summary = json.loads((out / SUMMARY).read_text())
    assert (summary["hostname_years"], summary["candidates"]) == (5, 4)
    assert Decimal(summary["equivalent_english"]) == sum(weight_of(h) for h in names)
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    assert write_collection(conn, baseline, out) == stats
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    assert annual() == annual_before


@pytest.mark.parametrize("broken,refusal", MISSING)
def test_a_missing_input_of_his_or_provenance_refuses_the_export(collection, broken, refusal):
    conn, source, baseline, out = collection
    eid = observe(conn, source, "keep.example.com")
    if broken.endswith(".txt"):
        (baseline / broken).unlink()
    else:
        value = "host keep.example.com" if broken == "evidence_value" else ""
        conn.execute(f"UPDATE evidence SET {broken} = ? WHERE evidence_id = ?", [value, eid])
    with pytest.raises(held.HeldError if broken.endswith(".txt") else ValueError, match=refusal):
        write_collection(conn, baseline, out)
    assert not (out / SUMMARY).exists()


@pytest.fixture
def delivery(collection):
    conn, source, baseline, out = collection
    for year in (1996, 1997):
        observe(conn, source, "keep.example.com", year)
    write_collection(conn, baseline, out)
    (out / WEIGHTS.name).write_bytes(WEIGHTS.read_bytes())
    (annual := out.parent / "annual").mkdir()
    for year in YEARS:
        (annual / f"{year}.txt").write_text("")
    return out, baseline, [annual], out / WEIGHTS.name


@pytest.mark.parametrize("installed", [True, False], ids=["with_ark", "without_ark"])
def test_independent_file_audit_reproduces_the_candidate_score(delivery, monkeypatch, installed):
    module = audit
    if not installed:
        (delivery[0] / "english_share.py").write_bytes(SHARE.read_bytes())
        monkeypatch.syspath_prepend(str(delivery[0].parent))
        for name in ("ark", "ark.english_share"):
            monkeypatch.setitem(sys.modules, name, None)
        SPEC.loader.exec_module(module := importlib.util.module_from_spec(SPEC))
    got = module.verify(*delivery)
    assert [got[k] for k in ("candidates", "hostname_years", "provenance_rows")] == [1, 2, 2]
    assert got["equivalent_english"] == "0.6321"


@pytest.mark.parametrize("file,old,new,refusal", [pytest.param(*t[:4], id=t[4]) for t in TAMPER])
def test_the_audit_refuses_a_delivery_that_drifted(delivery, file, old, new, refusal):
    path = dict(zip("cba", (*delivery[:2], delivery[2][0]), strict=True))[file[0]] / file[2:]
    path.write_text(re.sub(old, new, path.read_text()))
    with pytest.raises(ValueError, match=refusal):
        audit.verify(*delivery)


@pytest.mark.parametrize("omit_provenance", [False, True])
def test_packaging_requires_and_copies_the_complete_collection(tmp_path, delivery, omit_provenance):
    collection, root = delivery[0], tmp_path / "root"
    links = {"output/netnew": collection, "src/ark/data/" + WEIGHTS.name: delivery[3]}
    links |= {"src/ark/english_share.py": SHARE, "scripts/round/verify_isc_candidates.py": AUDIT}
    for link, target in links.items():
        (root / link).parent.mkdir(parents=True, exist_ok=True)
        (root / link).symlink_to(target)
    if omit_provenance:
        (collection / PROV).unlink()
    text = (ROOT / "scripts/round/package_delivery.sh").read_text()
    cut = r"# ISC candidates must stay separate.*?\n(.*?)# The source-saturation ledger"
    block = 'STAGE="stage"\n' + re.search(cut, text, re.S)[1]
    run = subprocess.run(["bash", "-e"], input=block, cwd=root, text=True, capture_output=True)
    assert (run.returncode != 0) is omit_provenance, run.stderr
    if not omit_provenance:
        shipped = {p.name for p in (root / "stage/isc_survey_hostnames").iterdir()}
        assert shipped == {*(p.name for p in collection.iterdir()), "english_share.py"}
        assert (root / "stage/verify_isc_candidates.py").is_file()
