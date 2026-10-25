"""The 2002 to 2013 additions: only his same-year file's complement, only by a capture stamped
in that year, and a package of ours alone that verify proves disjoint from his files."""

import csv
import gzip
import hashlib
import json
import os
import subprocess
from decimal import Decimal as D

import pytest
from conftest import ROOT, script
from his_release import stage, text

from ark import approvals

HIS = {2002: ["already.com", "his.org"], 2003: ["his.org"]}


def _journal(rows: list[dict]) -> bytes:
    return gzip.compress("".join(json.dumps(r) + "\n" for r in rows).encode())


ROWS = [
    {"url": "http://already.com/", "timestamp": "20020601000000", "status": "200"},
    {"url": "http://new.com/a", "timestamp": "20020301000000", "status": "200"},
    {"url": "http://new.com/", "timestamp": "20020101000000"},  # the earliest: the one quoted
    {"url": "http://old.com/", "timestamp": "20010601000000"},  # the core window, not ours here
    {"url": "http://late.com/", "timestamp": "20140601000000"},  # 2014 on is not hunted
    {"url": "http://err.com/", "timestamp": "20020601000000", "status": "404"},
    {"url": "http://under_score.com/", "timestamp": "20020601000000"},
    {"url": "http://early.eu/", "timestamp": "20030601000000"},  # .eu was delegated in 2005
    {"url": "http://fine.info/", "timestamp": "20030601000000"},  # not the 1996-2001 allowlist
    {"url": "http://www.gone.yu/", "timestamp": "20130601000000"},  # .yu left the root in 2010
]
# Refused whole, as the core refuses them: a status-less row in a family that must carry one,
# after a row that would ship, and an error lane.
REFUSED = {
    "nypw_b.jsonl.gz": [
        {"url": "http://kept.com/", "timestamp": "20020601000000", "status": "200"},
        {"url": "http://nostatus.com/", "timestamp": "20020601000000"},
    ],
    "early_web_nonok_part1.jsonl.gz": [
        {"url": "http://errorpage.com/", "timestamp": "20020601000000"}
    ],
}


@pytest.fixture
def exported(tmp_path, monkeypatch):
    his = stage(tmp_path, {f"{y}.txt": text(names) for y, names in HIS.items()})
    ext = script("round/extended_export.py")
    monkeypatch.setattr(ext, "baseline_dir", lambda: his)
    monkeypatch.setattr(ext, "REVIEWER_EXTENDED_EE_BY_YEAR", {2002: D(4), 2003: D(2)})
    monkeypatch.setattr(ext, "english_weights", lambda: {"com": D("0.5"), "info": D("0.25")})
    monkeypatch.setattr(ext, "CACHE", tmp_path / "cache")
    journal = tmp_path / "raw/ia_cdx_hostnames/a.jsonl.gz"
    journal.parent.mkdir(parents=True)
    journal.write_bytes(_journal(ROWS))
    for name, rows in REFUSED.items():
        (journal.parent / name).write_bytes(_journal(rows))
    globs = {"*": str(tmp_path / "raw/*/*.jsonl*")}
    # a folder that is no capture source in SOURCES, and an approved one awaiting its decision
    other = tmp_path / "raw/ukwa_host_link_graph/law_uk_2014_host.jsonl"
    other.parent.mkdir()
    other.write_text(json.dumps(ROWS[1]) + "\n")
    with pytest.raises(SystemExit, match="ukwa_host_link_graph: not a capture source"):
        ext.export(globs, tmp_path / "out")
    other.unlink()

    def awaiting(source: str, evidence_type: str) -> None:
        raise approvals.NotApproved("awaiting classification")

    monkeypatch.setattr(approvals, "check", awaiting)
    with pytest.raises(SystemExit, match="ia_cdx_hostnames: awaiting classification"):
        ext.export(globs, tmp_path / "out")
    monkeypatch.setattr(approvals, "check", lambda *a: None)
    manifest = ext.export(globs, tmp_path / "out")
    return ext, his, tmp_path / "out", manifest, journal, globs


def test_only_his_same_year_complement_ships_and_each_by_its_own_year(exported):
    ext, _, out, manifest, journal, _ = exported
    assert sorted(manifest["years"]) == ["2002", "2003"]
    assert not list(out.glob("*.txt")), "the export writes additions only"
    for year, added in ((2002, "new.com"), (2003, "fine.info")):
        adds = (out / f"additions/{year}.txt").read_text().split()
        assert adds == [added] and not set(adds) & set(HIS[year])
        entry = manifest["years"][str(year)]
        assert entry["already_in_baseline"] + entry["accepted_new"] == entry["submitted_unique"]
        assert entry["baseline_unique"] + entry["accepted_new"] == entry["merged_unique"]
    assert manifest["years"]["2002"]["already_in_baseline"] == 1
    assert manifest["increment_ee"] == "0.7500"
    assert manifest["years"]["2003"]["growth_pct"] == "12.500000"
    drop = manifest["dropped"]
    assert (drop["outside_window"], drop["error_status"], drop["duplicate"]) == (2, 1, 1)
    assert (drop["invalid_host"], drop["tld_did_not_exist"], drop["journal_refused"]) == (1, 2, 2)
    with (out / "evidence_ledger.csv").open() as fh:
        row = next(r for r in csv.DictReader(fh) if r["host"] == "new.com")
    assert (row["year"], row["method"], row["line"]) == ("2002", "ia_cdx_domain_sweep", "3")
    assert row["timestamp"] == "20020101000000"
    source = next(i for i in manifest["inputs"] if i["path"] == row["source_file"])
    assert source["sha256"] == hashlib.sha256(journal.read_bytes()).hexdigest()
    assert source["replay"] == "https://web.archive.org/web/{ts}/{url}"
    assert ext.stale(out) == []
    journal.write_bytes(_journal(ROWS[:2]))
    assert ext.stale(out), "a changed input makes the export stale"


def test_a_second_export_reads_only_the_inputs_that_moved(exported, monkeypatch):
    ext, _, out, manifest, journal, globs = exported
    torn = ext.cache_entry(journal)
    torn.write_bytes(torn.read_bytes()[:20])  # a torn entry is a miss, read again
    (ext.CACHE / "gone.gz").write_bytes(b"")  # no file's: a release run prunes it
    monkeypatch.setattr(ext, "INPUTS", globs)
    assert ext.export(globs, out)["years"] == manifest["years"]
    assert not (ext.CACHE / "gone.gz").exists()
    st = journal.stat()
    journal.write_bytes(b"x" * st.st_size)  # same size and mtime: its cached rows stand
    os.utime(journal, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert ext.export(globs, out)["years"] == manifest["years"]
    journal.write_bytes(_journal(ROWS[:1]))
    assert ext.export(globs, out)["years"] != manifest["years"]


def test_a_decided_fleet_read_joins_and_an_undecided_one_waits(exported, monkeypatch):
    ext, _, out, _, _, _ = exported
    raw = out.parent / "fleet_read"
    for slug, host in (("deep-read", "fleet.com"), ("pending-read", "wait.com")):
        part = raw / slug / f"fleetread_bulk_cdx_file__{slug}_0001.jsonl.gz"
        part.parent.mkdir(parents=True)
        row = {"url": f"http://{host}/", "timestamp": "20030501000000", "status": "200"}
        part.write_bytes(_journal([row]))

    def decided(source: str, evidence_type: str) -> None:
        if source == "fleet_pending_read_hostnames":
            raise approvals.NotApproved("awaiting classification")

    monkeypatch.setattr(approvals, "check", decided)
    manifest = ext.export({"fleetread": str(raw / "*/fleetread_*.jsonl.gz")}, out / "fleet")
    assert (out / "fleet/additions/2003.txt").read_text().split() == ["fleet.com"]
    with (out / "fleet/evidence_ledger.csv").open() as fh:
        (row,) = csv.DictReader(fh)
    assert (row["method"], row["timestamp"]) == ("bulk_cdx_file", "20030501000000")
    (source,) = manifest["inputs"]
    assert (source["source"], source["replay"]) == (
        "fleet_deep_read_hostnames",
        "https://web.archive.org/web/{ts}/{url}",
    )


def _cut(script_name: str, start: str, end: str) -> str:
    body = (ROOT / "scripts/round" / script_name).read_text(encoding="utf-8")
    return "set -euo pipefail\n" + start + body.split(start, 1)[1].split(end, 1)[0]


def test_the_package_ships_ours_alone_and_verify_checks_it_against_his(exported, tmp_path):
    his, out = exported[1], exported[2]
    pack = _cut("package_delivery.sh", "# extended_years/: the", "# ISC candidates must stay")
    check = _cut("verify_delivery.sh", "# --- the extended years", "# --- 5 to 8")
    (tmp_path / "output").mkdir()
    out.rename(tmp_path / "output/extended_years")
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin/uv").write_text("#!/bin/sh\n")  # `--check` is the test above's
    (tmp_path / "bin/uv").chmod(0o755)
    env = {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin", "STAGE": "stage"}
    run = lambda body, cwd, **more: subprocess.run(  # noqa: E731
        ["bash", "-c", body], cwd=cwd, env=env | more, capture_output=True, text=True
    )
    done = run(pack, tmp_path)
    assert done.returncode == 0, done.stderr
    shipped = tmp_path / "stage/extended_years"
    for f in (tmp_path / "output/extended_years/additions").glob(
        "*.txt"
    ):  # once, as the brief names it
        assert f.read_bytes() == (shipped / f.name).read_bytes()
    assert list(shipped.glob("*.txt")) and not (shipped / "additions").exists()
    done = run(check, tmp_path / "stage")
    assert "SKIP  2 additions" in done.stdout and "HIS" in done.stdout, done.stdout + done.stderr
    done = run(check, tmp_path / "stage", HIS=str(his))
    assert "PASS  2 additions" in done.stdout, done.stdout + done.stderr
    # one line of his slipped into the additions
    (shipped / "2003.txt").write_bytes(text(["fine.info", "his.org"]))
    done = run(check, tmp_path / "stage", HIS=str(his))
    assert "FAIL" in done.stdout and "repeats 1 lines of" in done.stdout, done.stdout
    (his / "2002.txt").write_bytes(text(HIS[2002] + ["zzz.com"]))
    done = run(check, tmp_path / "stage", HIS=str(his))
    assert "is not the file manifest.json names" in done.stdout, done.stdout


def test_the_end_of_term_reader_keeps_the_earliest_capture_a_host_year_in_the_window():
    eot = script("sources/eot/eot_cdxj.py")
    lines = [
        b'gov,a)/ 20080102000000 {"url": "http://Example.COM:80/", "status": "301"}',
        b'gov,a)/x 20080101000000 {"url": "http://example.com/x", "status": "200"}',
        b'gov,a)/ 20010101000000 {"url": "http://old.gov/", "status": "200"}',
        b'gov,b)/ 20090101000000 {"url": "http://b.gov/", "status": "-"}',
        b'gov,c)/ 20090101000000 {"url": "http://c.gov/\\q", "status": "200"}',
    ]
    keep, broken = eot.earliest(lines)
    assert keep == {("example.com", "2008"): ("20080101000000", "http://example.com/x", "200")}
    assert broken == 1
