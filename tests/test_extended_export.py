"""The 2002 to 2015 additions: only his same-year file's complement, only by a capture stamped
in that year, and a package whose merged files are his plus ours and nothing else."""

import csv
import gzip
import hashlib
import json
import subprocess
from decimal import Decimal as D

import pytest
from conftest import ROOT, script
from his_release import stage, text

HIS = {2002: ["already.com", "his.org"], 2003: ["his.org"]}


def _journal(rows: list[dict]) -> bytes:
    return gzip.compress("".join(json.dumps(r) + "\n" for r in rows).encode())


ROWS = [
    {"url": "http://already.com/", "timestamp": "20020601000000", "status": "200"},
    {"url": "http://new.com/a", "timestamp": "20020301000000", "status": "200"},
    {"url": "http://new.com/", "timestamp": "20020101000000"},  # the earliest: the one quoted
    {"url": "http://old.com/", "timestamp": "20010601000000"},  # the core window, not ours here
    {"url": "http://late.com/", "timestamp": "20160601000000"},
    {"url": "http://err.com/", "timestamp": "20020601000000", "status": "404"},
    {"url": "http://under_score.com/", "timestamp": "20020601000000"},
    {"url": "http://early.eu/", "timestamp": "20030601000000"},  # .eu was delegated in 2005
    {"url": "http://fine.info/", "timestamp": "20030601000000"},  # not the 1996-2001 allowlist
]


@pytest.fixture
def exported(tmp_path, monkeypatch):
    his = stage(tmp_path, {f"{y}.txt": text(names) for y, names in HIS.items()})
    ext = script("round/extended_export.py")
    monkeypatch.setattr(ext, "baseline_dir", lambda: his)
    monkeypatch.setattr(ext, "REVIEWER_EXTENDED_EE_BY_YEAR", {2002: D(4), 2003: D(2)})
    monkeypatch.setattr(ext, "english_weights", lambda: {"com": D("0.5"), "info": D("0.25")})
    journal = tmp_path / "raw/ia_cdx_domain_sweep/a.jsonl.gz"
    journal.parent.mkdir(parents=True)
    journal.write_bytes(_journal(ROWS))
    (tmp_path / "raw/not_a_web_method").mkdir()
    (tmp_path / "raw/not_a_web_method/b.jsonl").write_text(json.dumps(ROWS[1]) + "\n")
    globs = {"*": str(tmp_path / "raw/*/*.jsonl*")}
    with pytest.raises(SystemExit, match="not_a_web_method is not in WEB_METHODS"):
        ext.export(globs, tmp_path / "out")
    (tmp_path / "raw/not_a_web_method/b.jsonl").unlink()
    manifest = ext.export(globs, tmp_path / "out")
    return ext, his, tmp_path / "out", manifest, journal, globs


def test_only_his_same_year_complement_ships_and_each_by_its_own_year(exported):
    ext, _, out, manifest, journal, _ = exported
    assert sorted(manifest["years"]) == ["2002", "2003"]
    assert sorted(p.name for p in out.glob("*.txt")) == ["2002.txt", "2003.txt"]
    for year, added in ((2002, "new.com"), (2003, "fine.info")):
        adds = (out / f"additions/{year}.txt").read_text().split()
        assert adds == [added] and not set(adds) & set(HIS[year])
        assert (out / f"{year}.txt").read_bytes() == text(sorted(HIS[year] + adds))
        entry = manifest["years"][str(year)]
        assert entry["already_in_baseline"] + entry["accepted_new"] == entry["submitted_unique"]
        assert entry["baseline_unique"] + entry["accepted_new"] == entry["merged_unique"]
    assert manifest["years"]["2002"]["already_in_baseline"] == 1
    assert manifest["increment_ee"] == "0.7500"
    assert manifest["years"]["2003"]["growth_pct"] == "12.500000"
    drop = manifest["dropped"]
    assert (drop["outside_2002_2015"], drop["error_status"], drop["duplicate"]) == (2, 1, 1)
    assert (drop["invalid_host"], drop["tld_not_yet_delegated"]) == (1, 1)
    with (out / "evidence_ledger.csv").open() as fh:
        row = next(r for r in csv.DictReader(fh) if r["host"] == "new.com")
    assert (row["year"], row["method"], row["line"]) == ("2002", "ia_cdx_domain_sweep", "3")
    assert row["source_sha256"] == hashlib.sha256(journal.read_bytes()).hexdigest()
    assert row["evidence_url"] == "https://web.archive.org/web/20020101000000/http://new.com/"
    assert ext.stale(out) == []
    journal.write_bytes(_journal(ROWS[:2]))
    assert ext.stale(out), "a changed input makes the export stale"


def _cut(script_name: str, start: str, end: str) -> str:
    body = (ROOT / "scripts/round" / script_name).read_text(encoding="utf-8")
    return "set -euo pipefail\n" + start + body.split(start, 1)[1].split(end, 1)[0]


def test_the_package_ships_his_file_plus_ours_and_verify_proves_it(exported, tmp_path):
    out = exported[2]
    pack = _cut("package_delivery.sh", "# extended_years/: his", "# ISC candidates must stay")
    check = _cut("verify_delivery.sh", "# --- the extended years", "# --- 5 to 8")
    (tmp_path / "output").mkdir()
    out.rename(tmp_path / "output/extended_years")
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin/uv").write_text("#!/bin/sh\nexit 0\n")  # `--check` is the test above's
    (tmp_path / "bin/uv").chmod(0o755)
    env = {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin", "STAGE": "stage"}
    run = lambda body, cwd: subprocess.run(  # noqa: E731
        ["bash", "-c", body], cwd=cwd, env=env, capture_output=True, text=True
    )
    done = run(pack, tmp_path)
    assert done.returncode == 0, done.stderr
    shipped = tmp_path / "stage/extended_years"
    done = run(check, tmp_path / "stage")
    assert "PASS  2 additions" in done.stdout, done.stdout + done.stderr
    # one line of his slipped into the additions: merged minus additions is no longer his file
    (shipped / "additions/2003.txt").write_bytes(text(["fine.info", "his.org"]))
    done = run(check, tmp_path / "stage")
    assert "FAIL" in done.stdout and "is not his 2003.txt" in done.stdout, done.stdout
