"""The drain, the schema check, the second pricing and the outcome line over a finding.

The quiet failures. A drain that loses the items beside a sidecar makes every FIND
unpriceable and says nothing; a validator that passes a sidecar the fleet would reject lets
prose into a row that reads like a measurement; a re-price that cannot find the pricer's own
answer would report zero, the one wrong answer that looks like a result; a conversion that
deletes the old ledger before every row is in the fleet's loses the spend record for good; an
outcome line that says banked before the store holds the rows can never be taken back.
"""

import gzip
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest
from test_fleet_ledger import STAND_IN

from ark.db import init_db

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/harness/fleet_findings.py"
FLEET = Path.home() / "Documents/GitHub/ark-fleet"
# Where the fleet's own ledger script may be, for the one test that runs it: copied out and
# run over a scratch root, never inside the clone. `ARK_FLEET` names a clone ahead of main.
LEDGER_CLONES = (os.environ.get("ARK_FLEET"), FLEET)
REAL_FLEET = next(
    (
        Path(root)
        for root in LEDGER_CLONES
        if root and all((Path(root) / f"scripts/{n}").is_file() for n in ("ledger.py", "pacer.py"))
    ),
    None,
)
# The old ledger's shape, identical rows included: the drain's minute, tokens, the window.
ROWS = (
    "20260901T1037Z\t432\t68.0\n"
    "20260901T1037Z\t432\t68.0\n"
    "20260923T0706Z\t0\t?\n"
    "20260923T0706Z\t0\t?\n"
)
REGISTER = """## Pending requests

### a_find / artifact_listing
Decision: master

### b_find / artifact_listing
Decision: candidate-only
"""

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


def test_the_telemetry_dies_with_the_run_and_the_old_ledger_takes_no_row(tmp_path):
    # Each leg's spend is its leg line in the fleet ledger, written by the fleet's collect.
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    lead = artifact(incoming, "3", "a-lead", finding())
    (lead.parent.parent / "telemetry.json").write_text('{"legs": [{"tokens_in_plus_out": 5}]}')
    assert run("drain", str(incoming)).returncode == 0
    assert not list(incoming.glob("run_*"))
    assert not (incoming / "_unread").exists()
    assert not Path(os.environ["ARK_FLEET_LEDGER"]).exists()


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


# --- the old ledger -----------------------------------------------------------


def stand_in(tmp_path: Path) -> Path:
    """A fleet clone whose `scripts/ledger.py` keys and keeps lines as the real one does."""
    root = tmp_path / "fleet"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts/ledger.py").write_text(STAND_IN, encoding="utf-8")
    return root


def drained(tmp_path: Path, *flags: str) -> subprocess.CompletedProcess:
    incoming = tmp_path / "incoming"
    incoming.mkdir(exist_ok=True)
    done = run("drain", str(incoming), *flags)
    assert done.returncode == 0, done.stderr
    return done


def test_the_old_tsv_becomes_one_legacy_line_per_row_and_goes(tmp_path):
    # The old ledger repeats identical rows: keyed on the text alone, it would keep one of each.
    root = stand_in(tmp_path)
    tsv = Path(os.environ["ARK_FLEET_LEDGER"])
    tsv.write_text(ROWS, encoding="utf-8")
    drained(tmp_path, "--fleet", str(root))
    lines = module.fleet_ledger.lines(root, "legacy")
    assert [(line["row"], line["line"]) for line in lines] == list(enumerate(ROWS.splitlines(), 1))
    assert [line["at"] for line in lines[1:3]] == ["2026-09-01T10:37:00Z", "2026-09-23T07:06:00Z"]
    assert not tsv.exists()
    tsv.write_text(ROWS, encoding="utf-8")
    drained(tmp_path, "--fleet", str(root))
    assert len(module.fleet_ledger.lines(root, "legacy")) == 4, "a rerun adds none"
    assert not tsv.exists()


def test_a_drain_with_no_fleet_ledger_to_write_keeps_the_tsv(tmp_path):
    # The tick runs under `set -e`, and the laptop's clone gains the script only when pulled.
    tsv = Path(os.environ["ARK_FLEET_LEDGER"])
    tsv.write_text(ROWS, encoding="utf-8")
    assert "no --fleet" in drained(tmp_path).stdout
    old = tmp_path / "old-clone"
    old.mkdir()
    assert "has no scripts/ledger.py" in drained(tmp_path, "--fleet", str(old)).stdout
    (old / "scripts").mkdir()
    (old / "scripts/ledger.py").write_text("raise SystemExit('ledger: refused')\n")
    assert "refused" in drained(tmp_path, "--fleet", str(old)).stdout
    assert tsv.read_text(encoding="utf-8") == ROWS


def test_a_row_with_no_stamp_keeps_the_tsv_and_appends_nothing(tmp_path):
    root = stand_in(tmp_path)
    tsv = Path(os.environ["ARK_FLEET_LEDGER"])
    tsv.write_text(ROWS + "2026092T1000Z\t5\t?\n", encoding="utf-8")
    assert "row 5 has no stamp" in drained(tmp_path, "--fleet", str(root)).stdout
    assert tsv.read_text(encoding="utf-8").startswith(ROWS)
    assert module.fleet_ledger.lines(root, "legacy") == []


def test_a_test_drains_row_keeps_the_tsv_until_its_drop_has_run(tmp_path):
    """Five tokens and no window is the row a test drain wrote into the live file. Converted,
    it would stand in the append-only fleet ledger for good."""
    root = stand_in(tmp_path)
    tsv = Path(os.environ["ARK_FLEET_LEDGER"])
    body = ROWS + "20260924T2058Z\t5\t?\n20260925T1254Z\t5\t?\n"
    tsv.write_text(body, encoding="utf-8")
    said = drained(tmp_path, "--fleet", str(root)).stdout
    assert "2 rows are a test drain's" in said and "#171's drop must run" in said
    assert tsv.read_text(encoding="utf-8") == body
    assert module.fleet_ledger.lines(root, "legacy") == []
    tsv.write_text(ROWS, encoding="utf-8")
    drained(tmp_path, "--fleet", str(root))
    assert len(module.fleet_ledger.lines(root, "legacy")) == 4, "once dropped, it converts"


@pytest.mark.skipif(REAL_FLEET is None, reason="no fleet clone with scripts/ledger.py here")
def test_the_fleets_own_ledger_script_takes_both_kinds_of_line(tmp_path):
    root = tmp_path / "fleet"
    (root / "scripts").mkdir(parents=True)
    for name in ("ledger.py", "pacer.py"):
        shutil.copy(REAL_FLEET / "scripts" / name, root / "scripts" / name)

    def count(kind: str) -> str:
        script = str(root / "scripts/ledger.py")
        done = subprocess.run(
            [sys.executable, script, "count", "--kind", kind, "--root", str(root)],
            capture_output=True,
            text=True,
            env={**os.environ, "ARK_TELEMETRY_DIR": "/nonexistent"},
        )
        return done.stdout.strip()

    tsv = Path(os.environ["ARK_FLEET_LEDGER"])
    for _ in range(2):
        tsv.write_text(ROWS, encoding="utf-8")
        drained(tmp_path, "--fleet", str(root))
        assert (count("legacy"), tsv.exists()) == ("4", False)
    confirmed(tmp_path / "incoming", "a-find", {"ee": 1000.0, "fleet_program_ee": 995.0})
    (tmp_path / "approved.md").write_text(REGISTER, encoding="utf-8")
    done = run(
        "outcome",
        str(tmp_path / "incoming"),
        "--fleet",
        str(root),
        "--register",
        str(tmp_path / "approved.md"),
        "--db",
        str(store(tmp_path / "ark.duckdb", "a_find")),
    )
    assert "1 appended" in done.stdout, done.stdout + done.stderr
    assert count("outcome") == "1"


# --- scout leads --------------------------------------------------------------


def scout(incoming: Path, run_id: str, slug: str) -> None:
    """A lead closed at filing, as the fleet ships it: prose and a lead file, no finding."""
    leads = incoming / f"run_{run_id}" / f"findings-{run_id}" / "leads"
    (leads / slug).mkdir(parents=True)
    (leads / slug / "scout.md").write_text(f"# {slug}, a roster\nverdict: CLOSED\n", "utf-8")
    lead = {"slug": slug, "status": "closed", "artifact": {"url": f"http://{slug}.invalid/"}}
    (leads / f"{slug}.json").write_text(json.dumps(lead), encoding="utf-8")


def test_three_scout_leads_closed_at_filing_arrive_as_three_lead_directories(tmp_path):
    # Moved by bare name, all three would collide on `incoming/scout.md`.
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    slugs = ["about-com-roster", "dmoz-dump-1998", "weblogs-changes"]
    for slug in slugs:
        scout(incoming, "5", slug)
    (incoming / "run_5/findings-5/telemetry.json").write_text('{"legs": []}', encoding="utf-8")
    assert run("drain", str(incoming)).returncode == 0
    for slug in slugs:
        assert sorted(p.name for p in (incoming / slug).iterdir()) == ["lead.json", "scout.md"]
        assert json.loads((incoming / slug / "lead.json").read_text())["slug"] == slug
    assert not (incoming / "scout.md").exists()
    assert not (incoming / "_unread").exists()


def test_a_scout_copy_never_replaces_a_copy_with_a_finding(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    # The least settled finding there is: pending, and no run id to rank it by.
    artifact(incoming, "1", "a-lead", finding(run_id="", verify={"status": "pending"}))
    scout(incoming, "2", "a-lead")
    module.drain(incoming)
    assert sorted(p.name for p in (incoming / "a-lead").iterdir()) == ["finding.json", "finding.md"]
    # The other way round, the finding replaces the scout copy.
    scout(incoming, "3", "b-lead")
    artifact(incoming, "4", "b-lead", finding("b-lead", run_id="10", verify={"status": "pending"}))
    module.drain(incoming)
    assert (incoming / "b-lead" / "finding.json").is_file()
    assert not (incoming / "b-lead" / "scout.md").exists()


# --- outcome ------------------------------------------------------------------


def confirmed(incoming: Path, slug: str, store: dict | None, **over) -> None:
    lead = incoming / slug
    lead.mkdir(parents=True)
    (lead / "finding.json").write_text(json.dumps(finding(slug, **over)), encoding="utf-8")
    lead_doc = {"slug": slug, "evidence_class": "artifact_listing"}
    (lead / "lead.json").write_text(json.dumps(lead_doc), encoding="utf-8")
    if store is not None:
        (lead / "store_price.json").write_text(json.dumps(store), encoding="utf-8")


def store(path: Path, *sources: str) -> Path:
    """A tiny store whose ingest has written one file under each of `sources`."""
    conn = duckdb.connect(str(path))
    init_db(conn)
    for n, source in enumerate(sources):
        conn.execute(
            "INSERT INTO ingested_file (source_name, file_name, sha256, record_rows)"
            " VALUES (?, ?, ?, 1)",
            [source, f"{source}_{n}.jsonl.gz", "0" * 64],
        )
    conn.close()
    return path


def booked(
    tmp_path: Path, fleet: Path, *roots: Path, ingested: tuple[str, ...] = ()
) -> tuple[subprocess.CompletedProcess, dict[str, dict]]:
    """What `outcome` did, and the outcome lines it leaves, by slug and banked. Never the
    live store: `--db` is a tiny one that has ingested `ingested`."""
    incoming = tmp_path / "incoming"
    if not incoming.exists():
        confirmed(incoming, "a-find", {"status": "priced", "ee": 1000.0, "fleet_program_ee": 995.0})
        confirmed(incoming, "b-find", {"status": "no items to price", "ee": None})
        confirmed(incoming, "c-find", {"status": "priced", "ee": 50.0})
        confirmed(incoming, "unconfirmed", {"ee": None}, verify={"status": "pending"})
        confirmed(incoming, "unpriced", None)
        confirmed(incoming, "negative", {"ee": 5.0}, verdict="CLOSED")
    register = tmp_path / "approved.md"
    register.write_text(REGISTER, encoding="utf-8")
    db = tmp_path / "ark.duckdb"
    db.unlink(missing_ok=True)
    store(db, *ingested)
    done = run(
        "outcome",
        str(incoming),
        *map(str, roots),
        "--fleet",
        str(fleet),
        "--register",
        str(register),
        "--db",
        str(db),
    )
    lines = module.fleet_ledger.lines(fleet, "outcome")
    return done, {f"{line['slug']}:{line['banked']}": line for line in lines}


def test_each_confirmed_find_with_a_store_price_books_one_outcome_line(tmp_path):
    root = stand_in(tmp_path)
    done, lines = booked(tmp_path, root)
    assert done.returncode == 0, done.stderr
    assert sorted(lines) == ["a-find:False", "b-find:False", "c-find:False"]
    a = lines["a-find:False"]
    assert (a["store_ee"], a["program_ee"], a["agreement_pct"]) == (1000.0, 995.0, 99.5)
    assert a["decision"] == "master", "not banked until the store holds its rows"
    b, c = lines["b-find:False"], lines["c-find:False"]
    assert (b["store_ee"], b["agreement_pct"], b["decision"]) == (None, None, "candidate-only")
    assert (c["program_ee"], c["decision"]) == (None, "pending"), "no block is pending"
    assert len(booked(tmp_path, root)[1]) == 3, "a rerun adds none"


def test_banked_is_the_stores_ingested_files_and_a_json_bool(tmp_path):
    """No bank's commit makes a line banked, only the source's rows in the store, under a
    decision that admits them. A pending source's name in the store banks nothing."""
    root = stand_in(tmp_path)
    done, lines = booked(tmp_path, root, ingested=("a_find", "b_find", "c_find"))
    assert done.returncode == 0, done.stderr
    assert sorted(lines) == ["a-find:True", "b-find:True", "c-find:False"]
    assert lines["a-find:True"]["banked"] is True
    assert lines["b-find:True"]["decision"] == "candidate-only"
    assert '"banked": true' in (root / "ledger/2026-09.jsonl").read_text()
    assert "2 banked in the store" in done.stdout


def test_a_master_decision_the_store_holds_no_rows_for_is_not_banked(tmp_path):
    """The standing rule decides a source with no ingest spec master, and the bank ingests
    nothing. A banked line then would stand for good; a later ingest adds the banked one."""
    root = stand_in(tmp_path)
    _, lines = booked(tmp_path, root, ingested=("some_other_source",))
    assert "a-find:False" in lines and "a-find:True" not in lines
    _, lines = booked(tmp_path, root, ingested=("a_find",))
    assert {"a-find:False", "a-find:True"} <= set(lines), "the ingest books its banked line"


def test_a_store_that_cannot_be_read_banks_nothing_and_says_so(tmp_path):
    root = stand_in(tmp_path)
    incoming = tmp_path / "incoming"
    confirmed(incoming, "a-find", {"ee": 1000.0})
    (tmp_path / "approved.md").write_text(REGISTER, encoding="utf-8")
    done = run(
        "outcome",
        str(incoming),
        "--fleet",
        str(root),
        "--register",
        str(tmp_path / "approved.md"),
        "--db",
        str(tmp_path / "no-store.duckdb"),
    )
    assert "could not be opened" in done.stdout, done.stdout + done.stderr
    assert [line["banked"] for line in module.fleet_ledger.lines(root, "outcome")] == [False]


def test_the_drains_banked_before_are_booked_too_from_their_most_settled_copy(tmp_path):
    """A find whose drain left `incoming/` gains its banked line whenever the store holds it."""
    root = stand_in(tmp_path)
    old = tmp_path / "banked" / "20260920T0105Z"
    later = tmp_path / "banked" / "20260921T0105Z"
    confirmed(old, "d-find", {"ee": 70.0}, run_id="5")
    confirmed(later, "d-find", {"ee": 80.0}, run_id="6")
    done, lines = booked(tmp_path, root, old, later, tmp_path / "banked/*/", ingested=("a_find",))
    assert done.returncode == 0, done.stderr
    assert lines["d-find:False"]["store_ee"] == 80.0, "the later run's copy"
    assert "a-find:True" in lines


def test_an_outcome_that_did_not_land_exits_1_and_says_so(tmp_path):
    done, lines = booked(tmp_path, tmp_path / "old-clone")
    assert done.returncode == 1
    assert "not booked" in done.stdout
    assert lines == {}
    assert booked(tmp_path, stand_in(tmp_path))[0].returncode == 0


def _remote_read(root, slug="a-lead", complete=True, tamper=False, extra="", rename=""):
    """A read as `read.yaml` leaves it on the VPS: parts plus the receipt that lists them."""
    directory = root / "journals" / slug
    directory.mkdir(parents=True)
    parts, whole = [], hashlib.sha256()
    for n in (1, 2):
        name = f"fleetread_bulk_cdx_file__{slug}_000{n}.jsonl.gz"
        body = gzip.compress(
            f'{{"url": "http://h{n}.example.com/", "timestamp": "1999"}}\n'.encode()
        )
        (directory / name).write_bytes(body)
        parts.append({"name": name, "sha256": hashlib.sha256(body).hexdigest(), "rows": 1})
        whole.update(body)
    if tamper:
        (directory / parts[0]["name"]).write_bytes(b"changed on the way")
    if extra:
        (directory / extra).write_bytes(b"not the read's")
    if rename:
        parts[1]["name"] = rename
    receipt = {"complete": complete, "parts": parts, "journal_sha256": whole.hexdigest()}
    (directory / "receipt.json").write_text(json.dumps(receipt))
    return root / "journals"


def test_a_complete_read_is_pulled_whole_and_verified(tmp_path, monkeypatch):
    monkeypatch.setenv("ARK_READ_REMOTE", str(_remote_read(tmp_path)))
    monkeypatch.setattr(module, "FLEET_READ", tmp_path / "fleet_read")
    lead = tmp_path / "incoming" / "a-lead"
    lead.mkdir(parents=True)
    got = module.fetch_read(lead)
    assert got == tmp_path / "fleet_read" / "a-lead"
    assert sorted(p.name for p in got.glob("fleetread_*")) == [
        "fleetread_bulk_cdx_file__a-lead_0001.jsonl.gz",
        "fleetread_bulk_cdx_file__a-lead_0002.jsonl.gz",
    ]
    assert module.verify_read(got) == ""
    monkeypatch.setenv("ARK_READ_REMOTE", str(tmp_path / "nowhere"))
    assert module.fetch_read(lead) == got, "a verified read here is not pulled again"


def test_an_incomplete_or_mismatched_read_pulls_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(module, "FLEET_READ", tmp_path / "fleet_read")
    lead = tmp_path / "incoming" / "a-lead"
    lead.mkdir(parents=True)
    cases = (
        ("incomplete", {"complete": False}),
        ("tampered", {"tamper": True}),
        ("unlisted", {"extra": "notes.jsonl.gz"}),
        ("escaping", {"rename": "../fleetread_bulk_cdx_file__a-lead_0002.jsonl.gz"}),
    )
    for case, kwargs in cases:
        remote = _remote_read(tmp_path / case, **kwargs)
        monkeypatch.setenv("ARK_READ_REMOTE", str(remote))
        assert module.fetch_read(lead) is None, case
        assert not (tmp_path / "fleet_read" / "a-lead").exists(), case
        assert list((tmp_path / "fleet_read").iterdir()) == [], f"{case}: staging left behind"
    out = capsys.readouterr().out
    assert "does not say complete" in out and "does not match its sha256" in out
    assert "notes.jsonl.gz is not in the receipt" in out
    assert "is not a fleet read part name" in out


def test_a_banked_read_part_is_acked_by_its_sha256(tmp_path, monkeypatch):
    """The VPS frees a part once `journal_acks.tsv` holds its sha256, which the ingest wrote."""
    import duckdb

    from ark import approvals
    from ark.db import init_db
    from ark.hostnames import ingest_hostname_journal

    spec = importlib.util.spec_from_file_location(
        "ack_journals", ROOT / "scripts/harness/ack_journals.py"
    )
    ack = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ack)
    register = tmp_path / "approved.md"
    register.write_text(
        "## Decided\n\n### fleet_a_lead_hostnames / cdx_timestamp\n\nDecision: master\n"
    )
    monkeypatch.setattr(approvals, "DEFAULT_APPROVALS_PATH", register)
    part = _remote_read(tmp_path) / "a-lead" / "fleetread_bulk_cdx_file__a-lead_0001.jsonl.gz"
    part.write_bytes(
        gzip.compress(
            json.dumps(
                {
                    "url": "http://www.h1.example.com/",
                    "timestamp": "19990101000000",
                    "status": "200",
                }
            ).encode()
            + b"\n"
        )
    )
    store = tmp_path / "store.duckdb"
    conn = duckdb.connect(str(store))
    init_db(conn)
    assert ingest_hostname_journal(conn, part)["hostname_year_rows"] == 1
    conn.close()
    assert (part.name, hashlib.sha256(part.read_bytes()).hexdigest()) in ack.acks(store)


def test_a_read_lead_is_priced_on_its_pulled_parts_at_hostname_grain(tmp_path, monkeypatch):
    lead = tmp_path / "incoming" / "a-lead"
    lead.mkdir(parents=True)
    (lead / "read.json").write_text("{}")
    parts = tmp_path / "fleet_read" / "a-lead"
    monkeypatch.setattr(module, "fetch_read", lambda _lead: parts)
    ran = []

    def fake_run(cmd, **_kwargs):
        ran.append(cmd)
        out = "NET-NEW hostname years 1,234  567.8 EE\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    result = module.price(lead, {"verdict": "FIND"})
    assert ran == [["uv", "run", "python", "scripts/pricing/price_hostnames.py", str(parts)]]
    assert (result["status"], result["grain"], result["netnew"]) == ("priced", "hostname", 1234)
    monkeypatch.setattr(module, "fetch_read", lambda _lead: None)
    assert module.price(lead, {"verdict": "FIND"})["ee"] is None
