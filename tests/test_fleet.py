"""The laptop's side of the fleet loop: drain, re-price, outcome line, lead status and request."""

import gzip
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import duckdb
import pytest
from test_fleet_ledger import STAND_IN

from ark import approvals
from ark.db import init_db
from ark.hostnames import ingest_hostname_journal

HARNESS = Path(__file__).resolve().parents[1] / "scripts/harness"
FLEET = Path(os.environ.get("ARK_FLEET") or "~/Documents/GitHub/ark-fleet").expanduser()
# The fleet's own validator, schemas and ledger script, copied out or run over scratch files.
CONTRACT = FLEET if (FLEET / "scripts/contract.py").is_file() else None
LEDGER = FLEET if all((FLEET / f"scripts/{n}.py").is_file() for n in ("ledger", "pacer")) else None


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HARNESS / f"{name}.py")
    module = sys.modules[name] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NAMES = ("fleet_findings", "fleet_leads", "fleet_request", "ack_journals")
findings, leads, request, ack = map(_load, NAMES)
import sync_approvals  # noqa: E402  fleet_request put scripts/harness on the path

PENDING = {"status": "pending"}
ROWS = "20260901T1037Z\t432\t68.0\n" * 2 + "20260923T0706Z\t0\t?\n" * 2  # identical rows too


@pytest.fixture(autouse=True)
def _no_real_box(tmp_path, monkeypatch):
    """Items and reads come from scratch remotes into a scratch pull, never from the VPS."""
    monkeypatch.setenv("ARK_ITEMS_REMOTE", str(tmp_path / "no-items"))
    monkeypatch.setenv("ARK_TELEMETRY_DIR", "/nonexistent")
    monkeypatch.delenv("ARK_READ_REMOTE", raising=False)
    for module in (findings, request):
        monkeypatch.setattr(module, "FLEET_READ", tmp_path / "fleet_read")


def ff(capsys, *args) -> tuple[int, str]:
    """`fleet_findings.py` in-process: its exit code and what it printed."""
    code = findings.main([str(arg) for arg in args])
    return code, capsys.readouterr().out


def finding(slug: str = "a-lead", **over) -> dict:
    pricing = {"snapshot_marker": "merged260908", "manifest_sha": "abc", "netnew_pairs": 10}
    pricing |= {"cmd": "uv run ark price-snapshot", "ee": 4786.0, "track": "annual"}
    doc = {"slug": slug, "lane": "price", "run_id": "1741", "verdict": "FIND", "pricing": pricing}
    return doc | {"verify": {"status": "confirmed", "reason": "re-ran the command"}} | over


def drop(root: Path, slug: str = "a-lead", doc: dict | None = None, **files) -> Path:
    """A drained lead directory: `doc`, else a confirmed FIND, and each of `files` as JSON."""
    (path := root / slug).mkdir(parents=True, exist_ok=True)
    for name, body in {"finding": finding(slug) if doc is None else doc, **files}.items():
        if body is not None:
            (path / f"{name}.json").write_text(json.dumps(body), encoding="utf-8")
    return path


def artifact(incoming: Path, run: int, slug: str, doc=None, items=None, lead=None) -> Path:
    """A downloaded run holding one lead: its finding, or a scout's prose when `doc` is None."""
    (path := incoming / f"run_{run}/findings-{run}/leads" / slug).mkdir(parents=True)
    if doc is None:
        (path / "scout.md").write_text(f"# {slug}, a roster\nverdict: CLOSED\n", "utf-8")
        lead = {"slug": slug, "status": "closed", "artifact": {"url": f"http://{slug}.invalid/"}}
    else:
        (path / "finding.json").write_text(json.dumps(doc), encoding="utf-8")
        (path / "finding.md").write_text(f"# {slug}\nverdict: FIND\nee: 4786\n", encoding="utf-8")
    if items is not None:
        (path / "items.jsonl").write_text(items, encoding="utf-8")
    if lead is not None:
        (path.parent / f"{slug}.json").write_text(json.dumps(lead), encoding="utf-8")
    return path


# slug: the copies that arrive, in run order (None is a scout's), and what the kept one says
COPIES = {
    "first": ({}, {"verdict": "CLOSED"}, {"verdict": "FIND"}),
    "settled": ({"run_id": "10", "verify": PENDING}, {"run_id": "11"}, {"run_id": "11"}),
    "later": ({"run_id": "90", "verdict": "CLOSED"}, {"run_id": "91"}, {"run_id": "91"}),
    "scout-last": ({"run_id": "", "verify": PENDING}, None, {"run_id": ""}),
    "scout-lost": (None, {"run_id": "10", "verify": PENDING}, {"run_id": "10"}),
}


def test_a_drain_moves_each_leads_most_settled_copy_whole_under_its_slug(tmp_path, capsys):
    """Settled beats pending, then the later run, and a scout copy ranks last."""
    incoming = tmp_path / "incoming"
    lead = artifact(incoming, 1, "a-lead", finding(), "{}\n", {"grain": "hostname"})
    (lead.parents[1] / "telemetry.json").write_text('{"legs": [{"tokens_in_plus_out": 5}]}')
    (lead.parent / "_rejected").mkdir()
    (lead.parent / "_rejected/bad.lead.json").write_text("{}", encoding="utf-8")
    # A leg's root is `findings/`, holding a copy of the lead: keyed on its name, booked twice.
    drop(incoming / "run_2/leg-1", "findings", finding(run_id="99"))
    for slug, (*docs, _) in COPIES.items():
        for run, over in enumerate(docs, 2):
            artifact(incoming, run, slug, None if over is None else finding(slug, **over))
    assert ff(capsys, "drain", incoming)[0] == 0
    assert sorted(p.name for p in incoming.iterdir()) == sorted(["_unread", "a-lead", *COPIES])
    assert [p.name for p in (incoming / "_unread").rglob("*") if p.is_file()] == ["bad.lead.json"]
    got = sorted(p.name for p in (incoming / "a-lead").iterdir())
    assert got == ["finding.json", "finding.md", "items.jsonl", "lead.json"]
    assert json.loads((incoming / "a-lead/lead.json").read_text())["grain"] == "hostname"
    for slug, (*_, kept) in COPIES.items():
        assert sorted(p.name for p in (incoming / slug).iterdir()) == ["finding.json", "finding.md"]
        doc = json.loads((incoming / slug / "finding.json").read_text())
        assert {key: doc[key] for key in kept} == kept, slug
    assert not Path(os.environ["ARK_FLEET_LEDGER"]).exists(), "the old ledger takes no row"


def clone(tmp_path: Path, real: bool = False) -> Path:
    """A scratch fleet clone with the fleet's own `ledger.py` and `pacer.py`, or the stand-in."""
    (scripts := tmp_path / "fleet/scripts").mkdir(parents=True)
    for name in ("ledger.py", "pacer.py") if real else ():
        shutil.copy(LEDGER / "scripts" / name, scripts / name)
    if not real:
        (scripts / "ledger.py").write_text(STAND_IN, encoding="utf-8")
    return scripts.parent


def pushed(root: Path) -> None:
    """The clone's ledger committed and taken as fleet main, out of reach of a hook's GIT_DIR."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    for who in ("AUTHOR", "COMMITTER"):
        env |= {f"GIT_{who}_NAME": "ark", f"GIT_{who}_EMAIL": "ark@localhost"}
    main = ["update-ref", "refs/remotes/origin/main", "HEAD"]
    for args in (["init", "-q"], ["add", "ledger"], ["commit", "-q", "-m", "ledger"], main):
        subprocess.run(["git", "-C", str(root), *args], check=True, env=env)


@pytest.mark.parametrize("real", [False, True], ids=["stand-in", "fleet-ledger-script"])
def test_the_old_tsv_becomes_legacy_lines_set_aside_once_fleet_main_holds_them(
    tmp_path, capsys, real
):
    if real and LEDGER is None:
        pytest.skip("no fleet clone with scripts/ledger.py here")
    root, tsv = clone(tmp_path, real), Path(os.environ["ARK_FLEET_LEDGER"])
    tsv.write_text(ROWS, encoding="utf-8")
    (incoming := tmp_path / "incoming").mkdir()
    assert "fleet main holds 0 of its 4 rows" in ff(capsys, "drain", incoming, "--fleet", root)[1]
    lines = findings.fleet_ledger.lines(root, "legacy")
    assert [(line["row"], line["line"]) for line in lines] == list(enumerate(ROWS.splitlines(), 1))
    assert [line["at"] for line in lines[1:3]] == ["2026-09-01T10:37:00Z", "2026-09-23T07:06:00Z"]
    assert tsv.read_text(encoding="utf-8") == ROWS, "kept until a push lands the lines"
    pushed(root)
    assert ff(capsys, "drain", incoming, "--fleet", root)[0] == 0
    assert len(findings.fleet_ledger.lines(root, "legacy")) == 4, "a rerun adds none"
    assert not tsv.exists() and tsv.with_name(f"{tsv.name}.converted").read_text() == ROWS
    tsv.write_text(ROWS, encoding="utf-8")
    ff(capsys, "drain", incoming, "--fleet", root)
    assert tsv.with_name(f"{tsv.name}.converted.2").is_file(), "an earlier aside stays"
    confirmed(incoming, "a-find", {"ee": 1000.0, "fleet_program_ee": 995.0})
    _, said, booked_lines = booked(capsys, tmp_path, ingested=("a_find",))
    assert "1 appended" in said and list(booked_lines) == ["a-find:True"]


@pytest.mark.parametrize(
    "body, script, said",
    [
        (ROWS, None, "no --fleet was given"),
        (ROWS, "", "has no scripts/ledger.py"),
        (ROWS, "raise SystemExit('ledger: refused')\n", "the fleet ledger refused it"),
        (ROWS, "print('ledger: appended 4')\n", "fleet main holds 0 of its 4 rows"),
        (ROWS + "2026092T1000Z\t5\t?\n", STAND_IN, "row 5 has no stamp"),
        (ROWS + "20260924T2058Z\t5\t?\n20260925T1254Z\t5\t?\n", STAND_IN, "2 rows are a test"),
    ],
    ids=["no-fleet", "no-ledger-script", "refused", "not-on-main", "no-stamp", "test-drain-rows"],
)
def test_the_tsv_stays_and_the_drain_goes_on_until_every_row_can_land(
    tmp_path, capsys, body, script, said
):
    (tsv := Path(os.environ["ARK_FLEET_LEDGER"])).write_text(body, encoding="utf-8")
    (fleet := tmp_path / "fleet").mkdir()
    if script:
        (fleet / "scripts").mkdir()
        (fleet / "scripts/ledger.py").write_text(script, encoding="utf-8")
    (tmp_path / "incoming").mkdir()
    flags = [] if script is None else ["--fleet", fleet]
    code, out = ff(capsys, "drain", tmp_path / "incoming", *flags)
    assert code == 0 and said in out
    assert tsv.read_text(encoding="utf-8") == body
    assert findings.fleet_ledger.lines(fleet, "legacy") == []


@pytest.mark.skipif(CONTRACT is None, reason="no fleet clone with a validator")
def test_a_sidecar_the_fleet_would_reject_becomes_its_blocked_fallback(tmp_path, capsys):
    no_pricing = {"slug": "a-lead", "lane": "price", "run_id": "9", "verdict": "FIND"}
    bad, good = drop(tmp_path, "a-lead", no_pricing), drop(tmp_path, "b-lead")
    assert ff(capsys, "validate", tmp_path, "--fleet", CONTRACT)[0] == 0
    got = [json.loads((lead / "finding.json").read_text()) for lead in (bad, good)]
    assert [(d["verdict"], d["slug"]) for d in got] == [("BLOCKED", "a-lead"), ("FIND", "b-lead")]
    assert [(lead / "finding.json.rejected").is_file() for lead in (bad, good)] == [True, False]


def test_only_a_confirmed_find_with_items_is_repriced_by_the_pricer_its_grain_names(
    tmp_path, monkeypatch, capsys
):
    disputed = drop(tmp_path / "incoming", "a-lead", finding(verify={"status": "disputed"}))
    bare = drop(tmp_path / "incoming", "b-lead")
    said = ff(capsys, "reprice", tmp_path / "incoming")[1]
    assert "a-lead is disputed, not re-priced" in said and "b-lead NOT re-priced" in said
    got = [json.loads((lead / "store_price.json").read_text()) for lead in (disputed, bare)]
    want = [("verify disputed", None), ("no items to price, see the run log", None)]
    assert [(price["status"], price["ee"]) for price in got] == want
    (disputed / "lead.json").write_text(json.dumps({"grain": "registrable"}), "utf-8")
    assert findings.grain_of("a-lead", finding(), disputed) == "registrable"
    # With no lead file the track decides, falling back to the general pricer.
    assert findings.grain_of("b-lead", finding(), bare) == "registrable"
    assert findings.grain_of("b-lead", finding(pricing={"track": "candidate"}), bare) == "candidate"
    items = findings._ITEMS_EE.search("net-new AFTER the split    : 1,234 pairs, 4,786.2 EE")
    hosts = findings._HOST_EE.search("NET-NEW hostname years 9,001  12,345.6789 EE   (quote)")
    assert (items.group(2), hosts.group(2)) == ("4,786.2", "12,345.6789")
    (tmp_path / "items").mkdir()
    (tmp_path / "items/b-lead.jsonl").write_text('{"item": "x", "year": 1998}\n', "utf-8")
    monkeypatch.setattr(findings, "REPO", tmp_path)  # no local.env naming a real box
    for remote, said in [("items", "fetched"), ("gone", "is not at"), ("", "no ARK_VPS")]:
        bare = drop(tmp_path / f"fetch-{remote}", "b-lead")
        monkeypatch.setenv("ARK_ITEMS_REMOTE", remote and str(tmp_path / remote))
        got = findings.fetch_items(bare)
        assert said in capsys.readouterr().out, remote
        assert (got is not None and got.read_text().startswith('{"item"')) == (remote == "items")


def remote_read(root: Path, complete=True, tamper=False, extra="", rename="") -> Path:
    """A read as `read.yaml` leaves it on the VPS: parts plus the receipt that lists them."""
    (directory := root / "journals/a-lead").mkdir(parents=True)
    parts, whole = [], hashlib.sha256()
    for n in (1, 2):
        row = {"url": f"http://www.h{n}.example.com/", "timestamp": "19990101000000"}
        body = gzip.compress(json.dumps(row | {"status": "200"}).encode() + b"\n")
        (directory / (name := f"fleetread_bulk_cdx_file__a-lead_000{n}.jsonl.gz")).write_bytes(body)
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


BAD_READS = [
    ({"complete": False}, "does not say complete"),
    ({"tamper": True}, "does not match its sha256"),
    ({"extra": "notes.jsonl.gz"}, "notes.jsonl.gz is not in the receipt"),
    ({"rename": "../fleetread_bulk_cdx_file__a-lead_0002.jsonl.gz"}, "not a fleet read part name"),
]
HOSTNAMES = "## Decided\n\n### fleet_a_lead_hostnames / cdx_timestamp\n\nDecision: master\n"


def test_only_a_read_matching_its_receipt_is_pulled_priced_and_acked(tmp_path, monkeypatch, capsys):
    """Priced on its pulled parts at hostname grain; the VPS frees a part its ingest acked."""
    lead = drop(tmp_path / "incoming", read={})
    for n, (kwargs, said) in enumerate(BAD_READS):
        monkeypatch.setenv("ARK_READ_REMOTE", str(remote_read(tmp_path / str(n), **kwargs)))
        assert findings.fetch_read(lead) is None and said in capsys.readouterr().out
        assert list((tmp_path / "fleet_read").iterdir()) == [], f"{said}: no read, no staging"
    monkeypatch.setenv("ARK_READ_REMOTE", str(remote_read(tmp_path / "whole")))
    assert (got := findings.fetch_read(lead)) == tmp_path / "fleet_read/a-lead"
    names = sorted(p.name for p in got.glob("fleetread_*"))
    assert names == [f"fleetread_bulk_cdx_file__a-lead_000{n}.jsonl.gz" for n in (1, 2)]
    assert findings.verify_read(got) == ""
    monkeypatch.setenv("ARK_READ_REMOTE", str(tmp_path / "nowhere"))
    assert findings.fetch_read(lead) == got, "a verified read here is not pulled again"
    (register := tmp_path / "approved.md").write_text(HOSTNAMES, encoding="utf-8")
    monkeypatch.setattr(approvals, "DEFAULT_APPROVALS_PATH", register)
    conn, part = duckdb.connect(str(db := store(tmp_path / "store.duckdb"))), got / names[0]
    assert ingest_hostname_journal(conn, part)["hostname_year_rows"] == 1
    conn.close()
    assert (part.name, hashlib.sha256(part.read_bytes()).hexdigest()) in ack.acks(db)
    said = subprocess.CompletedProcess([], 0, "NET-NEW hostname years 1,234  567.8 EE\n", "")
    monkeypatch.setattr(findings.subprocess, "run", run := Mock(return_value=said))
    result = findings.price(lead, {"verdict": "FIND"})
    cmd = ["uv", "run", "python", "scripts/pricing/price_hostnames.py", str(got)]
    assert [call.args[0] for call in run.call_args_list] == [cmd]
    assert (result["status"], result["grain"], result["netnew"]) == ("priced", "hostname", 1234)
    shutil.rmtree(got)
    assert findings.price(lead, {"verdict": "FIND"})["ee"] is None


DECIDED = "## Pending requests\n\n### a_find / artifact_listing\nDecision: master\n\n"
DECIDED += "### b_find / artifact_listing\nDecision: candidate-only\n\n"
DECIDED += "### fleet_e_read_hostnames / cdx_timestamp\nDecision: master\n"


def store(path: Path, *sources: str) -> Path:
    """A tiny store whose ingest has written one file under each of `sources`."""
    path.unlink(missing_ok=True)
    conn = duckdb.connect(str(path))
    init_db(conn)
    for n, source in enumerate(sources):
        sql = "INSERT INTO ingested_file (source_name, file_name, sha256, record_rows)"
        conn.execute(f"{sql} VALUES (?, ?, ?, 1)", [source, f"{source}_{n}.jsonl.gz", "0" * 64])
    conn.close()
    return path


def confirmed(root: Path, slug: str, price: dict | None, **over) -> Path:
    """A drained, confirmed FIND with its lead and, unless None, its store price."""
    lead = {"slug": slug, "evidence_class": "artifact_listing"}
    return drop(root, slug, finding(slug, **over), lead=lead, store_price=price)


def booked(capsys, tmp_path: Path, *roots, ingested=(), fleet=None, db=None):
    """`outcome` over a tiny store, never the live one: exit, words, lines by slug:banked."""
    incoming, fleet = tmp_path / "incoming", fleet or tmp_path / "fleet"
    if not incoming.exists():
        confirmed(incoming, "a-find", {"status": "priced", "ee": 1000.0, "fleet_program_ee": 995.0})
        confirmed(incoming, "b-find", {"status": "no items to price", "ee": None})
        confirmed(incoming, "c-find", {"status": "priced", "ee": 50.0})
        confirmed(incoming, "unconfirmed", {"ee": None}, verify=PENDING)
        confirmed(incoming, "unpriced", None)
        confirmed(incoming, "negative", {"ee": 5.0}, verdict="CLOSED")
    (register := tmp_path / "approved.md").write_text(DECIDED, encoding="utf-8")
    db = db or store(tmp_path / "ark.duckdb", *ingested)
    flags = ["--fleet", fleet, "--register", register, "--db", db]
    code, out = ff(capsys, "outcome", incoming, *roots, *flags)
    lines = findings.fleet_ledger.lines(fleet, "outcome")
    return code, out, {f"{line['slug']}:{line['banked']}": line for line in lines}


def test_an_outcome_line_is_banked_only_once_the_store_holds_the_sources_rows(tmp_path, capsys):
    """Under a decision that admits them, and only once landed; a line that did not exits 1."""
    code, out, lines = booked(capsys, tmp_path, fleet=tmp_path / "old-clone")
    assert (code, lines) == (1, {}) and "not booked" in out
    code, out, lines = booked(capsys, tmp_path, fleet=clone(tmp_path), db=tmp_path / "no-store")
    assert code == 0 and "could not be opened" in out
    assert sorted(lines) == ["a-find:False", "b-find:False", "c-find:False"]
    a, b, c = lines["a-find:False"], lines["b-find:False"], lines["c-find:False"]
    assert (a["store_ee"], a["program_ee"], a["agreement_pct"]) == (1000.0, 995.0, 99.5)
    assert (a["decision"], b["store_ee"], b["agreement_pct"]) == ("master", None, None)
    assert (b["decision"], c["program_ee"], c["decision"]) == ("candidate-only", None, "pending")
    assert len(booked(capsys, tmp_path, ingested=("some_other_source",))[2]) == 3, "none added"
    _, out, lines = booked(capsys, tmp_path, ingested=("a_find", "b_find", "c_find"))
    want = ["a-find:False", "a-find:True", "b-find:False", "b-find:True", "c-find:False"]
    assert sorted(lines) == want and "2 banked in the store" in out
    assert lines["a-find:True"]["banked"] is True
    assert lines["b-find:True"]["decision"] == "candidate-only"
    assert '"banked": true' in (tmp_path / "fleet/ledger/2026-09.jsonl").read_text()
    # A read banks as `fleet_<slug>_hostnames / cdx_timestamp`; a banked drain by its latest copy.
    confirmed(tmp_path / "incoming", "e-read", {"status": "priced", "ee": 30.0})
    (tmp_path / "incoming/e-read/read.json").write_text("{}", encoding="utf-8")
    old, later = tmp_path / "banked/20260920T0105Z", tmp_path / "banked/20260921T0105Z"
    confirmed(old, "d-find", {"ee": 70.0}, run_id="5")
    confirmed(later, "d-find", {"ee": 80.0}, run_id="6")
    ingested = ("fleet_e_read_hostnames",)
    code, _, lines = booked(capsys, tmp_path, old, later, tmp_path / "banked/*/", ingested=ingested)
    assert code == 0 and lines["e-read:True"]["decision"] == "master"
    assert lines["d-find:False"]["store_ee"] == 80.0, "the later run's copy"


LEAD = {
    "slug": "a-lead", "lens": "registry publications", "status": "verified",
    "scouted_at": "2026-09-09T00:00:00Z", "grain": "hostname", "evidence_class": "cdx_timestamp",
    "artifact": {"url": "https://example.invalid/x", "host": "example.invalid", "bytes": 10,
                 "content_type": "text/plain", "terms_url": "https://example.invalid/terms",
                 "robots": "allowed", "risk": "low"},
    "what_dates_one_item": "1999-05-04T11:02:13Z", "sample_record": "example.invalid 19990504",
    "size_estimate": {"items": 10, "ee_low": 1.0, "ee_high": 2.0}, "floor": 1000.0,
    "history": [{"lane": "scout", "run_id": "17", "at": "2026-09-09T00:00:00Z"}],
}  # fmt: skip
CONFIRMED = {"verdict": "FIND", "verify": {"status": "confirmed"}}
BANKED, NOT_YET = {"banked": True}, {"decision": "pending", "banked": False}
# slug: the drain's finding (None: drained before), its outcome lines, the status it ends in
STATUSES = {
    "banked-line": (CONFIRMED, [NOT_YET, BANKED], "banked"),
    "banked-false": (CONFIRMED, [{"banked": False}], "verified"),
    "the-string-true": (CONFIRMED, [{"banked": "true"}], "verified"),
    "the-number-one": (CONFIRMED, [{"banked": 1}], "verified"),
    "a-legacy-line": (CONFIRMED, [{"kind": "legacy", "banked": True}], "verified"),
    "waiting-on-the-owner": (CONFIRMED, [], "verified"),
    "measured-negative": ({"verdict": "CLOSED", "reason": "everything is held"}, [], "closed"),
    "disputed": ({"verdict": "FIND", "verify": {"status": "disputed"}}, [BANKED], "closed"),
    "blocked-is-work-to-redo": ({"verdict": "BLOCKED", "reason": "timed out"}, [], "verified"),
    "closed-though-banked": ({"verdict": "CLOSED"}, [BANKED], "closed"),
    "approved-later": (None, [NOT_YET, BANKED], "banked"),
    "still-pending": (None, [NOT_YET], "verified"),
    "done-already": (None, [BANKED], "banked"),
    "hand-edited": ({"verdict": "CLOSED"}, [], "verified"),
}
# A banked lead is not rewritten; a laptop history entry fails the lead schema three ways.
HEADS = {"done-already": {"status": "banked"}}
HEADS["hand-edited"] = {"history": [{"lane": "laptop", "at": "2026-09-19T00:00:00Z", "note": "x"}]}


def with_contract(fleet: Path) -> Path:
    """The fleet's validator and schemas, copied in; the clone itself is only read."""
    if CONTRACT is None:
        pytest.skip("no fleet clone with a validator to copy")
    (fleet / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONTRACT / "scripts/contract.py", fleet / "scripts/contract.py")
    shutil.copytree(CONTRACT / "schemas", fleet / "schemas")
    return fleet


def outcomes(fleet: Path, *lines: dict) -> Path:
    """Outcome lines in the fleet ledger's own month file, as the bank appends them."""
    (fleet / "ledger").mkdir(parents=True, exist_ok=True)
    with (fleet / "ledger/2026-09.jsonl").open("a", encoding="utf-8") as fh:
        for line in lines:
            row = {"kind": "outcome", "decision": "master", "at": "2026-09-26T00:00:00Z", **line}
            row["key"] = f"{row['slug']}:{row['decision']}:{row['banked']}"
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    return fleet


def test_a_lead_takes_its_drains_verdict_or_banked_from_a_json_true_outcome(tmp_path, capsys):
    """Written only with --write and the fleet's validator passing, every other field kept."""
    (fleet := tmp_path / "fleet").joinpath("leads").mkdir(parents=True)
    for slug, (doc, lines, _) in STATUSES.items():
        lead = dict(LEAD, slug=slug) | HEADS.get(slug, {})
        (fleet / f"leads/{slug}.json").write_text(json.dumps(lead), encoding="utf-8")
        if doc is not None:
            drop(tmp_path / "incoming", slug, dict(doc, slug=slug))
        outcomes(fleet, *({"slug": slug} | line for line in lines))
    outcomes(fleet, {"slug": "no-lead-file", "banked": True})
    drop(tmp_path / "incoming", "not-in-the-clone", {"verdict": "CLOSED"})
    argv = [str(tmp_path / "incoming"), "--fleet", str(fleet)]
    texts = lambda: {path.name: path.read_text() for path in (fleet / "leads").iterdir()}  # noqa: E731
    before = texts()
    assert leads.main([*argv, "--write"]) == 0 and "no validator" in capsys.readouterr().out
    with_contract(fleet)
    assert leads.main(argv) == 0 and "would write: banked-line is banked" in capsys.readouterr().out
    assert texts() == before
    assert leads.main([*argv, "--write"]) == 0
    for slug, (*_, status) in STATUSES.items():
        lead = json.loads(texts()[f"{slug}.json"])
        assert lead == dict(LEAD, slug=slug) | HEADS.get(slug, {}) | {"status": status}, slug
        assert list(lead) == list(LEAD), "rewritten key by key, in the order the fleet wrote"
    assert sorted(texts()) == sorted(before), "a lead the clone lacks is not created"
    assert [texts()[f"{slug}.json"] for slug in HEADS] == [before[f"{s}.json"] for s in HEADS]
    said = capsys.readouterr().out
    assert "hand-edited not written as closed" in said and "laptop" in said
    assert "not-in-the-clone has no lead file" in said
    assert "5 statuses written" in said and "1 refused" in said


REGISTER = "# Approved sources\n\n## Pending requests\n\n### old_source / cdx_timestamp\n"
REGISTER += "Decision: pending\n"
# Another cdx_timestamp source is approved, so the class is not new.
APPROVED = "# Approved sources\n\n### old_source / cdx_timestamp\nDecision: master\n\n"
APPROVED += "## Pending requests\n\nNone.\n"
ASKED = dict(LEAD, artifact={"url": "https://example.invalid/x", "robots": "allowed"})
CLAUSES = ("size", "terms", "robots", "class", "window")
CLAUSES = {n: {"ok": True, "evidence": f"{n} inside the bound"} for n in CLAUSES}
STANDING = {"admitted": True, "policy_version": 59, "clauses": CLAUSES}
ROBOTS = dict(CLAUSES, robots={"ok": False, "evidence": "robots.txt disallows /data/"})
NEW = "no other cdx_timestamp source is approved as master"
REFUSED = "the robots clause is not ok: robots.txt disallows /data/"
# Ten finds whose program figure agreed with the store within 1%: the program decides.
AGREEING = [{"slug": f"find-{n}", "store_ee": 1000.0, "program_ee": 1004.0} for n in range(10)]
AGREEING = [dict(line, banked=True) for line in AGREEING]


def asked(tmp_path, slug="a-lead", lead=ASKED, register=REGISTER, named=None, **price):
    """A drained, re-priced find with its lead, beside the approvals register."""
    doc = {"slug": named or slug, "run_id": "1741", "verdict": price.pop("verdict", "FIND")}
    doc |= {"pricing": {"ee": 900000.0, "track": "annual"}}
    doc["verify"] = {"status": price.pop("verify", "confirmed"), "reason": "re-ran it"}
    price = {"status": "priced", "ee": 7000.0, "netnew": 12, "pricer": "price_items.py"} | price
    drop(tmp_path / "incoming", slug, doc, store_price=price, lead=lead)
    (tmp_path / "approvals.md").write_text(register, encoding="utf-8")
    return tmp_path / "incoming", tmp_path / "approvals.md"


def block(incoming: Path, register: Path, *extra: str) -> str:
    request.main([str(incoming), "--register", str(register), "--write", *extra])
    return register.read_text(encoding="utf-8")


def block_of(text: str, head: str = "a_lead") -> str:
    return text.split(f"### {head} / cdx_timestamp\n", 1)[1].split("\n\n", 1)[0]


def test_each_confirmed_repriced_find_gets_one_pending_block_of_facts_atop_the_queue(
    tmp_path, capsys
):
    """No spec or terms invented, the deciding figure quoted, a read asked as its hostnames."""
    asked(tmp_path, "b-lead", verify="disputed")
    asked(tmp_path, "c-lead", ee=0.0)
    asked(tmp_path, "closed", verdict="CLOSED")
    asked(tmp_path, "d-lead", lead=dict(ASKED, evidence_class="link_target"))
    asked(tmp_path, "program-only", ee=None, fleet_program_ee=7020.0)
    for slug in ("e-read", "f-read"):
        read = asked(tmp_path, slug, lead=dict(ASKED, evidence_class="artifact_listing"))[0] / slug
        (read / "read.json").write_text("{}", encoding="utf-8")
    (tmp_path / "fleet_read/e-read").mkdir(parents=True)
    receipt = {"journal_sha256": "ab" * 32, "parts": [{}, {}], "lines": 1234}
    (tmp_path / "fleet_read/e-read/receipt.json").write_text(json.dumps(receipt), "utf-8")
    incoming, register = asked(tmp_path)
    (incoming / "a-lead/items.jsonl").write_text("{}\n", "utf-8")  # a drain outside the checkout
    (incoming / "_unread").mkdir()
    # Under the streak the program's figure decides where it priced the find, the store elsewhere.
    streak = ["--fleet", str(outcomes(tmp_path / "fleet", *AGREEING))]
    request.main([str(incoming), "--register", str(register), *streak])
    assert register.read_text(encoding="utf-8") == REGISTER, "nothing without --write"
    said = capsys.readouterr().out
    assert "would write: a_lead" in said and "d_lead is link_target, which needs no" in said
    text = block(incoming, register, *streak)
    # Newest first, no blank line inside a block and one between: the compactor's shape.
    heads = [part.split("\n")[0] for part in text.split("## Pending requests\n\n")[1].split("\n\n")]
    new = ["program_only", "fleet_f_read_hostnames", "fleet_e_read_hostnames", "a_lead"]
    assert heads == [f"### {key} / cdx_timestamp" for key in [*new, "old_source"]]
    assert text.endswith("### old_source / cdx_timestamp\nDecision: pending\n")
    facts = ["- ingest spec: none in this repository", "- journal: `", "banked nothing"]
    facts += ["the lead records no terms page", "dates one item: 1999-05-04T11:02:13Z"]
    facts += ["7,000.0 EE net-new on the live store", "The fleet said 900,000.0 EE"]
    assert all(fact in block_of(text) for fact in [*facts, "- potential: 7000"]), text
    program = block_of(text, "program_only")
    assert "7,020.0 EE net-new by the program on the pushed snapshot" in program
    assert "re-price by `price_items.py` said no figure" in program and "potential: 7020" in program
    assert "the program's figure is the one to read" in program
    e_read, f_read = (block_of(text, f"fleet_{s}_read_hostnames") for s in "ef")
    assert f"- ingest: ark ingest-hostnames {tmp_path / 'fleet_read/e-read'}/" in e_read
    assert f"- journal sha256: {'ab' * 32}, 2 part(s), 1,234 rows" in e_read
    assert "- journal sha256: no receipt on this machine, 0 part(s)" in f_read, "never arrived"
    assert all("- ingest spec:" not in r and "- journal: `" not in r for r in (e_read, f_read))
    parsed = approvals.load(register)
    assert parsed[("a_lead", "cdx_timestamp")].decision == "pending"
    assert parsed[("fleet_e_read_hostnames", "cdx_timestamp")].decision == "pending"
    assert ("e_read", "artifact_listing") not in parsed
    assert block(incoming, register, *streak) == text
    assert "already has a block" in capsys.readouterr().out


@pytest.mark.parametrize(
    "slug, register, standing, why",
    [
        ("a-lead", APPROVED, STANDING, None),
        ("a_lead", APPROVED, STANDING, None),
        ("a-lead", REGISTER, STANDING, NEW),
        ("a-lead", APPROVED, None, "the lead carries no standing admission"),
        ("a-lead", REGISTER, dict(STANDING, clauses=ROBOTS), f"{NEW}; {REFUSED}"),
    ],
    ids=["no-ask", "no-ask-dir", "new-class", "no-standing", "new-class-and-robots"],
)
def test_a_parked_block_says_why_and_is_filed_and_a_standing_rule_block_is_decided(
    tmp_path, capsys, monkeypatch, slug, register, standing, why
):
    """The block is the whole ask, named after its directory whatever the sidecar says."""
    lead = ASKED if standing is None else dict(ASKED, standing=standing)
    incoming, path = asked(tmp_path, slug, lead=lead, register=register, named="another-name")
    before = sorted(tmp_path.rglob("*"))
    request.main([str(incoming), "--register", str(path)])
    dry = capsys.readouterr().out
    lines, said = block_of(block(incoming, path)).splitlines(), capsys.readouterr().out
    assert sorted(tmp_path.rglob("*")) == before, "the run leaves nothing else behind"
    parked = [f"- parked: {why}"] if why else []
    assert [n for n in lines if n.startswith("- parked:")] == parked
    assert lines[-2 - len(parked) :] == [*parked, "- potential: 7000", "Decision: pending"]
    request.standing_rule.main([str(incoming), "--register", str(path), "--write"])
    monkeypatch.setattr(sync_approvals, "REGISTER", path)
    filed = [(r.source, r.potential, r.failed) for r in sync_approvals.requests(5000.0)]
    if why is None:
        assert all("no ask: the standing rule decides it" in s for s in (dry, said))
        assert "sync_approvals.py" not in dry + said and filed == []
        assert approvals.load(path)[("a_lead", "cdx_timestamp")].decision == "master"
    else:
        assert all(
            f"parked: {why}" in s and "sync_approvals.py files the" in s for s in (dry, said)
        )
        assert filed == [("a_lead", 7000.0, f"parked by the standing rule: {why}")]


def test_a_spec_waits_for_the_next_bank_while_his_held_sets_are_not_ready(tmp_path, monkeypatch):
    """`request_approval.py` exiting 3 refuses nothing, so no short block replaces it."""
    incoming, register = asked(tmp_path)
    (incoming / "a-lead/items.jsonl").write_text("{}\n", encoding="utf-8")
    monkeypatch.setitem(request.SOURCES, "a_lead", object())
    done = subprocess.CompletedProcess([], request.NOT_NOW, "", "no held sets: run ark intake")
    monkeypatch.setattr(request.subprocess, "run", lambda *a, **k: done)
    assert request.by_the_tool("a_lead", incoming / "a-lead", ASKED, {}) is None
    assert block(incoming, register) == REGISTER
