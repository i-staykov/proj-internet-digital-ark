"""The drain, the schema check and the second pricing `just sync` runs over a finding.

The properties worth a test are the ones that fail quietly. A drain that loses the items
beside a sidecar makes every FIND unpriceable and says nothing; a validator that passes a
sidecar the fleet would reject lets prose into a row that reads like a measurement; a
re-price that cannot find the pricer's own answer in its output would report zero, which is
the one wrong answer that looks like a result.
"""

import importlib.util
import json
import os
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


def run(*args: str, items_remote: str = "") -> subprocess.CompletedProcess:
    # Never the real box: `reprice` fetches items over rsync, and a test suite that reaches
    # a host is a test suite that fails on a train.
    env = {**os.environ, "ARK_ITEMS_REMOTE": items_remote or str(ROOT / "tests" / "no-such-dir")}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT, env=env
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


def artifact(
    incoming: Path,
    run_id: str,
    slug: str,
    doc: dict,
    items: str | None = None,
    lead_file: dict | None = None,
) -> Path:
    lead = incoming / f"run_{run_id}" / "findings-1" / "leads" / slug
    lead.mkdir(parents=True)
    (lead / "finding.json").write_text(json.dumps(doc), encoding="utf-8")
    (lead / "finding.md").write_text(f"# {slug}\nverdict: FIND\nee: 4786\n", encoding="utf-8")
    if items is not None:
        (lead / "items.jsonl").write_text(items, encoding="utf-8")
    if lead_file is not None:
        (lead.parent / f"{slug}.json").write_text(json.dumps(lead_file), encoding="utf-8")
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
    done = run("reprice", str(incoming))
    assert "disputed" in done.stdout
    assert json.loads((lead / "store_price.json").read_text())["ee"] is None


def test_a_confirmed_find_with_no_items_says_so_instead_of_pricing_nothing(tmp_path):
    incoming = tmp_path / "incoming"
    lead = incoming / "a-lead"
    lead.mkdir(parents=True)
    (lead / "finding.json").write_text(json.dumps(finding()), encoding="utf-8")
    done = run(
        "reprice",
        str(incoming),
    )
    assert "NOT re-priced" in done.stdout
    assert "no items" in json.loads((lead / "store_price.json").read_text())["status"]


def test_the_grain_decides_which_pricer_answers(tmp_path):
    lead_dir = tmp_path / "a-lead"
    lead_dir.mkdir()
    (lead_dir / "lead.json").write_text(json.dumps({"grain": "registrable"}), "utf-8")
    assert module.grain_of("a-lead", finding(), lead_dir) == "registrable"
    # No lead file: the track is the only thing left that tells the two units apart, and
    # the fallback is the general pricer rather than the hostname one, which refuses a file
    # of bare registrable names.
    gone = tmp_path / "gone"
    gone.mkdir()
    assert module.grain_of("gone", finding(), gone) == "registrable"
    doc = finding()
    doc["pricing"]["track"] = "candidate"
    assert module.grain_of("gone", doc, gone) == "candidate"


def test_both_pricers_net_new_lines_are_read_the_way_they_are_printed():
    items = "net-new AFTER the split    : 1,234 pairs, 4,786.2 EE"
    hosts = "NET-NEW hostname years 9,001  12,345.6789 EE   (quote this)"
    assert module._ITEMS_EE.search(items).group(2) == "4,786.2"
    assert module._HOST_EE.search(hosts).group(2) == "12,345.6789"


def test_the_artifacts_lead_file_moves_into_the_lead_directory(tmp_path):
    # The clone on this laptop is never pulled by the sync, so the grain and the stamp have
    # to come from the copy that travelled with the finding.
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    artifact(incoming, "1", "a-lead", finding(), lead_file={"slug": "a-lead", "grain": "hostname"})
    assert run("drain", str(incoming)).returncode == 0
    assert json.loads((incoming / "a-lead" / "lead.json").read_text())["grain"] == "hostname"
    assert not (incoming / "a-lead.json").exists()


def test_the_settled_copy_of_a_slug_wins_over_the_pending_one(tmp_path):
    # A price wave and the verify wave that answers it are drained together. Keeping
    # whichever arrived first threw away the only copy the standing rule can act on.
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    pending = finding(run_id="10", verify={"status": "pending", "reason": "not yet"})
    confirmed = finding(run_id="11", verify={"status": "confirmed", "reason": "re-ran it"})
    artifact(incoming, "1", "a-lead", pending)
    artifact(incoming, "2", "a-lead", confirmed)
    run("drain", str(incoming))
    kept = json.loads((incoming / "a-lead" / "finding.json").read_text())
    assert kept["verify"]["status"] == "confirmed"


def test_two_settled_copies_keep_the_later_run(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    artifact(incoming, "1", "a-lead", finding(run_id="90", verdict="CLOSED"))
    artifact(incoming, "2", "a-lead", finding(run_id="91", verdict="CLOSED"))
    run("drain", str(incoming))
    assert json.loads((incoming / "a-lead" / "finding.json").read_text())["run_id"] == "91"


def test_every_leg_gets_a_ledger_row_not_the_wrapper(tmp_path, monkeypatch):
    # The artifact's telemetry is {"legs": [...]}. Read as one row it logged a zero a wave.
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    lead = artifact(incoming, "3", "a-lead", finding())
    (lead.parent.parent / "telemetry.json").write_text(
        json.dumps(
            {
                "legs": [
                    {"tokens_in_plus_out": 111, "seven_day_pct": 4},
                    {"tokens_in_plus_out": 222, "seven_day_pct": 5},
                ]
            }
        ),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.tsv"
    monkeypatch.setattr(module, "LEDGER", ledger)
    module.drain(incoming)
    rows = [line.split("\t") for line in ledger.read_text().splitlines()]
    assert [r[1] for r in rows] == ["111", "222"]


def test_the_items_come_from_the_box_that_has_them(tmp_path, monkeypatch):
    # The artifact carries no data: a price leg leaves its items on the VPS so the verify
    # leg's re-run finds them. rsync over a local path is the same code path as over ssh.
    remote = tmp_path / "items"
    remote.mkdir()
    (remote / "a-lead.jsonl").write_text('{"item": "x", "year": 1998, "text": "x.com"}\n', "utf-8")
    monkeypatch.setenv("ARK_ITEMS_REMOTE", str(remote))
    lead = tmp_path / "incoming" / "a-lead"
    lead.mkdir(parents=True)
    got = module.fetch_items(lead)
    assert got is not None and got.read_text().startswith('{"item"')


def test_items_nobody_can_reach_are_loud_and_price_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ARK_ITEMS_REMOTE", str(tmp_path / "nowhere"))
    lead = tmp_path / "incoming" / "a-lead"
    lead.mkdir(parents=True)
    assert module.fetch_items(lead) is None
    assert "is not at" in capsys.readouterr().out


def test_a_laptop_with_no_vps_says_so_rather_than_reporting_a_missing_file(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.delenv("ARK_ITEMS_REMOTE", raising=False)
    monkeypatch.setattr(module, "REPO", tmp_path)  # no local.env here
    lead = tmp_path / "incoming" / "a-lead"
    lead.mkdir(parents=True)
    assert module.fetch_items(lead) is None
    assert "no ARK_VPS in local.env" in capsys.readouterr().out


def test_a_leg_directory_called_findings_is_keyed_on_its_slug(tmp_path):
    # A leg artifact's root is `findings/`, holding a copy of the same finding as the lead
    # directory beside it. Keyed on the directory name, both were drained and the register
    # took the same slug twice (measured 2026-09-09).
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    run = incoming / "run_1" / "leg-1"
    (run / "findings").mkdir(parents=True)
    (run / "findings" / "finding.json").write_text(json.dumps(finding()), encoding="utf-8")
    artifact(incoming, "2", "a-lead", finding(run_id="99"))
    module.drain(incoming)
    assert sorted(p.name for p in incoming.iterdir() if p.is_dir()) == ["a-lead"]


def test_an_unrecognised_file_is_kept_rather_than_deleted_with_the_run(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    lead = artifact(incoming, "1", "a-lead", finding())
    (lead.parent / "_rejected").mkdir()
    (lead.parent / "_rejected" / "bad.lead.json").write_text("{}", encoding="utf-8")
    module.drain(incoming)
    kept = list((incoming / "_unread").rglob("bad.lead.json"))
    assert kept, "an unrecognised file went with the run directory"
