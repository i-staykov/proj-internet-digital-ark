"""The drain, the schema check and the second pricing `just sync` runs over a finding.

The properties worth a test are the ones that fail quietly. A drain that loses the items
beside a sidecar makes every FIND unpriceable and says nothing; a validator that passes a
sidecar the fleet would reject lets prose into a row that reads like a measurement; a
re-price that cannot find the pricer's own answer in its output would report zero, which is
the one wrong answer that looks like a result.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/harness/fleet_findings.py"
FLEET = Path.home() / "Documents/GitHub/ark-fleet"

_SPEC = importlib.util.spec_from_file_location("fleet_findings", SCRIPT)
module = importlib.util.module_from_spec(_SPEC)
sys.modules["fleet_findings"] = module
_SPEC.loader.exec_module(module)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT
    )


def finding(slug: str = "a-lead", **over) -> dict:
    doc = {
        "slug": slug,
        "lane": "price",
        "run_id": "1741",
        "verdict": "FIND",
        "pricing": {
            "snapshot_marker": "merged260908",
            "manifest_sha": "abc",
            "cmd": "uv run ark price-snapshot",
            "netnew_pairs": 10,
            "ee": 4786.0,
            "track": "annual",
        },
        "verify": {"status": "confirmed", "reason": "re-ran the command"},
    }
    doc.update(over)
    return doc


def artifact(incoming: Path, run_id: str, slug: str, doc: dict, items: str | None = None) -> Path:
    lead = incoming / f"run_{run_id}" / "findings-1" / "leads" / slug
    lead.mkdir(parents=True)
    (lead / "finding.json").write_text(json.dumps(doc), encoding="utf-8")
    (lead / "finding.md").write_text(f"# {slug}\nverdict: FIND\nee: 4786\n", encoding="utf-8")
    if items is not None:
        (lead / "items.jsonl").write_text(items, encoding="utf-8")
    return lead


def test_a_lead_directory_moves_whole_so_the_items_stay_beside_it(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    artifact(incoming, "1", "a-lead", finding(), items='{"item": "x", "year": 1998}\n')
    assert run("drain", str(incoming)).returncode == 0
    assert (incoming / "a-lead" / "finding.json").is_file()
    assert (incoming / "a-lead" / "items.jsonl").is_file()
    assert not (incoming / "run_1").exists()


def test_a_slug_already_drained_is_dropped_rather_than_rebooked(tmp_path):
    # A run is re-downloaded until it completes, so the same lead arrives twice. The copy
    # already here is the one the register rows were written from.
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "a-lead").mkdir()
    (incoming / "a-lead" / "finding.json").write_text(json.dumps(finding()), encoding="utf-8")
    artifact(incoming, "2", "a-lead", finding(verdict="CLOSED"))
    run("drain", str(incoming))
    kept = json.loads((incoming / "a-lead" / "finding.json").read_text())
    assert kept["verdict"] == "FIND"


def test_telemetry_becomes_a_ledger_row_and_the_run_directory_goes(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    lead = artifact(incoming, "3", "a-lead", finding())
    (lead.parent.parent / "telemetry.json").write_text('{"tokens_in_plus_out": 5}', "utf-8")
    assert run("drain", str(incoming)).returncode == 0
    assert not list(incoming.glob("run_*"))


@pytest.mark.skipif(not (FLEET / "scripts/contract.py").is_file(), reason="no fleet clone here")
def test_a_sidecar_the_fleet_would_reject_becomes_a_blocked_fallback(tmp_path):
    incoming = tmp_path / "incoming"
    lead = incoming / "a-lead"
    lead.mkdir(parents=True)
    # A FIND with no pricing block: the fleet's own semantic rule refuses it.
    (lead / "finding.json").write_text(
        json.dumps({"slug": "a-lead", "lane": "price", "run_id": "9", "verdict": "FIND"}), "utf-8"
    )
    done = run("validate", str(incoming), "--fleet", str(FLEET))
    assert done.returncode == 0, done.stderr
    replaced = json.loads((lead / "finding.json").read_text())
    assert replaced["verdict"] == "BLOCKED"
    assert replaced["slug"] == "a-lead"
    assert (lead / "finding.json.rejected").is_file()


@pytest.mark.skipif(not (FLEET / "scripts/contract.py").is_file(), reason="no fleet clone here")
def test_a_sidecar_that_validates_is_left_alone(tmp_path):
    incoming = tmp_path / "incoming"
    lead = incoming / "a-lead"
    lead.mkdir(parents=True)
    (lead / "finding.json").write_text(json.dumps(finding()), encoding="utf-8")
    assert run("validate", str(incoming), "--fleet", str(FLEET)).returncode == 0
    assert json.loads((lead / "finding.json").read_text())["verdict"] == "FIND"
    assert not (lead / "finding.json.rejected").exists()


def test_a_find_nobody_confirmed_is_not_repriced(tmp_path):
    incoming = tmp_path / "incoming"
    lead = incoming / "a-lead"
    lead.mkdir(parents=True)
    doc = finding(verify={"status": "disputed", "reason": "the stamp dates the file"})
    (lead / "finding.json").write_text(json.dumps(doc), encoding="utf-8")
    done = run("reprice", str(incoming), "--fleet", str(tmp_path / "no-fleet"))
    assert "disputed" in done.stdout
    assert json.loads((lead / "store_price.json").read_text())["ee"] is None


def test_a_confirmed_find_with_no_items_says_so_instead_of_pricing_nothing(tmp_path):
    incoming = tmp_path / "incoming"
    lead = incoming / "a-lead"
    lead.mkdir(parents=True)
    (lead / "finding.json").write_text(json.dumps(finding()), encoding="utf-8")
    done = run("reprice", str(incoming), "--fleet", str(tmp_path / "no-fleet"))
    assert "NOT re-priced" in done.stdout
    assert json.loads((lead / "store_price.json").read_text())["status"] == "no items shipped"


def test_the_grain_decides_which_pricer_answers(tmp_path):
    fleet = tmp_path / "fleet"
    (fleet / "leads").mkdir(parents=True)
    (fleet / "leads" / "a-lead.json").write_text(json.dumps({"grain": "registrable"}), "utf-8")
    assert module.grain_of("a-lead", finding(), fleet) == "registrable"
    # No lead file: the track is the only thing left that tells the two units apart, and
    # the fallback is the general pricer rather than the hostname one, which refuses a file
    # of bare registrable names.
    assert module.grain_of("gone", finding(), fleet) == "registrable"
    doc = finding()
    doc["pricing"]["track"] = "candidate"
    assert module.grain_of("gone", doc, fleet) == "candidate"


def test_both_pricers_net_new_lines_are_read_the_way_they_are_printed():
    items = "net-new AFTER the split    : 1,234 pairs, 4,786.2 EE"
    hosts = "NET-NEW hostname years 9,001  12,345.6789 EE   (quote this)"
    assert module._ITEMS_EE.search(items).group(2) == "4,786.2"
    assert module._HOST_EE.search(hosts).group(2) == "12,345.6789"
