"""The delivery audit must reject stale counts, overlaps and incomplete ISC provenance."""

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_isc_candidates", ROOT / "scripts/round/verify_isc_candidates.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


@pytest.fixture
def delivery(tmp_path):
    collection = tmp_path / "isc_survey_hostnames"
    baseline = tmp_path / "merged-test"
    annual = tmp_path / "annual"
    for directory in (collection, baseline, annual):
        directory.mkdir()
    for year in audit.YEARS:
        (collection / f"{year}-ISC.txt").write_text(
            "keep.example.com\n" if year in (1996, 1997) else ""
        )
        (baseline / f"{year}.txt").write_text("example.com\n")
        (annual / f"{year}.txt").write_text("")
    (baseline / "candidate_pool.txt").write_text("www.keep.example.com\n")
    (collection / "isc_candidates.txt").write_text("keep.example.com\n")
    summary = {
        "baseline": baseline.name,
        "track": "candidate",
        "candidates": 1,
        "equivalent_english": "0.6321",
        "hostname_years": 2,
        "provenance_rows": 2,
        "by_year": {str(y): int(y in (1996, 1997)) for y in audit.YEARS},
        "tld_counts": {"com": 1},
    }
    (collection / "isc_candidates_summary.json").write_text(json.dumps(summary))
    with (collection / "isc_survey_provenance.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "hostname",
                "target_year",
                "survey_edition",
                "source_file",
                "source_url",
                "record_location",
                "extraction_method",
            ]
        )
        for year in (1996, 1997):
            writer.writerow(
                [
                    "keep.example.com",
                    year,
                    f"{year}-07",
                    "com.gz",
                    f"http://nw.com/zone/{str(year)[2:]}07.hosts/com.gz",
                    f"isc survey {year}-07 host keep.example.com",
                    "isc_survey_host_listing",
                ]
            )
    weights = collection / "tld_english_share.json"
    weights.write_bytes((ROOT / "src/ark/data/tld_english_share.json").read_bytes())
    return collection, baseline, [annual], weights


def test_independent_file_audit_reproduces_unique_candidate_score(delivery):
    result = audit.verify(*delivery)
    assert result["candidates"] == 1
    assert result["hostname_years"] == result["provenance_rows"] == 2
    assert result["equivalent_english"] == "0.6321"


def test_file_audit_runs_without_installed_ark(delivery, monkeypatch):
    collection, *_ = delivery
    (collection / "english_share.py").write_bytes((ROOT / "src/ark/english_share.py").read_bytes())
    monkeypatch.syspath_prepend(str(collection.parent))
    monkeypatch.setitem(sys.modules, "ark", None)
    monkeypatch.setitem(sys.modules, "ark.english_share", None)
    standalone = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(standalone)
    assert standalone.verify(*delivery)["equivalent_english"] == "0.6321"


@pytest.mark.parametrize("target", ["reviewer_pool", "reviewer_annual", "local_annual"])
def test_any_year_exact_name_overlap_fails(delivery, target):
    _, baseline, annual, _ = delivery
    destination = {
        "reviewer_pool": baseline / "candidate_pool.txt",
        "reviewer_annual": baseline / "2001.txt",
        "local_annual": annual[0] / "2001.txt",
    }[target]
    destination.write_text("  KEEP.example.com  \n")
    with pytest.raises(ValueError, match="overlap"):
        audit.verify(*delivery)


@pytest.mark.parametrize("change", ["missing", "extra", "blank_field"])
def test_provenance_must_cover_exactly_the_shipped_keys(delivery, change):
    collection, *_ = delivery
    path = collection / "isc_survey_provenance.csv"
    with path.open() as fh:
        rows = list(csv.reader(fh))
    if change == "missing":
        rows.pop()
    elif change == "extra":
        row = rows[-1].copy()
        row[0] = "extra.example.com"
        rows.append(row)
    else:
        rows[-1][3] = ""
    with path.open("w", newline="") as fh:
        csv.writer(fh).writerows(rows)
    with pytest.raises(ValueError, match="provenance"):
        audit.verify(*delivery)


def test_stale_summary_is_not_accepted(delivery):
    collection, *_ = delivery
    path = collection / "isc_candidates_summary.json"
    summary = json.loads(path.read_text())
    summary["equivalent_english"] = "1.2642"
    path.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="does not reproduce"):
        audit.verify(*delivery)


@pytest.mark.parametrize("omit_provenance", [False, True])
def test_packaging_requires_and_copies_the_complete_collection(tmp_path, delivery, omit_provenance):
    collection, *_ = delivery
    source = tmp_path / "output/netnew"
    source.parent.mkdir()
    source.symlink_to(collection, target_is_directory=True)
    model = tmp_path / "src/ark/data"
    model.mkdir(parents=True)
    (model / "tld_english_share.json").symlink_to(collection / "tld_english_share.json")
    (model.parent / "english_share.py").symlink_to(ROOT / "src/ark/english_share.py")
    scripts = tmp_path / "scripts/round"
    scripts.mkdir(parents=True)
    (scripts / "verify_isc_candidates.py").symlink_to(
        ROOT / "scripts/round/verify_isc_candidates.py"
    )
    if omit_provenance:
        (collection / "isc_survey_provenance.csv").unlink()
    text = (ROOT / "scripts/round/package_delivery.sh").read_text()
    block = text.split("# ISC candidates must stay separate", 1)[1]
    block = block.split("\n", 1)[1].split("# The source-saturation ledger", 1)[0]
    result = subprocess.run(
        ["bash", "-e"],
        input='STAGE="stage"\n' + block,
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    if omit_provenance:
        assert result.returncode != 0
    else:
        assert result.returncode == 0, result.stderr
        shipped = tmp_path / "stage/isc_survey_hostnames"
        assert {p.name for p in shipped.iterdir()} == {
            *(p.name for p in collection.iterdir()),
            "english_share.py",
        }
        assert (tmp_path / "stage/verify_isc_candidates.py").is_file()
