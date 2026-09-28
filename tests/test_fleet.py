"""The laptop's side of the fleet loop: drain, re-price, request block, outcome line and ledger,
the push that must not drop a ledger line, and the tick's and the bank's fleet steps as the
justfile runs them."""

import gzip
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import Mock

import duckdb
import pytest

from ark import approvals
from ark.db import init_db
from ark.hostnames import ingest_hostname_journal
from ark.price_snapshot import NO_SPLIT_CLASSES

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts/harness"
FLEET = Path(os.environ.get("ARK_FLEET") or "~/Documents/GitHub/ark-fleet").expanduser()
# The fleet's own validator, schemas and ledger script, copied out or run over scratch files.
CONTRACT = FLEET if (FLEET / "scripts/contract.py").is_file() else None
LEDGER = FLEET if all((FLEET / f"scripts/{n}.py").is_file() for n in ("ledger", "pacer")) else None
RECIPE = (ROOT / "justfile").read_text(encoding="utf-8")
TICK = RECIPE[RECIPE.index("\nsync fleet=") : RECIPE.index("\nbank ")]
BANK = RECIPE[RECIPE.index("\nbank ") :]
BANK = BANK[: BANK.index("\n\n")]
# Under a hook git exports GIT_DIR and GIT_INDEX_FILE, and a scratch clone would stage into ours.
ENV = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HARNESS / f"{name}.py")
    module = sys.modules[name] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fleet_ledger, findings, request, ack = map(
    _load, ("fleet_ledger", "fleet_findings", "fleet_request", "ack_journals")
)
import sync_approvals  # noqa: E402  fleet_request put scripts/harness on the path

# A stand-in for the fleet's `scripts/ledger.py append`: it keys a line on the fields the real
# one names, keeps one it already holds, and refuses a line missing a key field.
STAND_IN = r"""
import json, sys
from pathlib import Path
KINDS = {"legacy": ("row", "line"), "outcome": ("slug", "decision", "banked")}
args = sys.argv[1:]
kind, root = args[args.index("--kind") + 1], Path(args[args.index("--root") + 1])
path = root / "ledger" / "2026-09.jsonl"
path.parent.mkdir(exist_ok=True)
have = {json.loads(t)["key"] for t in path.read_text().splitlines()} if path.exists() else set()
added = kept = 0
for number, text in enumerate(sys.stdin.read().splitlines(), 1):
    line = json.loads(text)
    if any(line.get(f) in (None, "") for f in KINDS[kind]):
        print(f"ledger: stdin line {number}: a {kind} line needs its key", file=sys.stderr)
        sys.exit(2)
    key = ":".join(str(line[f]) for f in KINDS[kind])
    if key in have:
        kept += 1
        continue
    have.add(key)
    added += 1
    with path.open("a") as fh:
        fh.write(json.dumps({**line, "kind": kind, "key": key}) + "\n")
print(f"ledger: {added} appended, {kept} kept")
"""
PENDING = {"status": "pending"}
ROWS = "20260901T1037Z\t432\t68.0\n" * 2 + "20260923T0706Z\t0\t?\n" * 2  # identical rows too
PRICER = ["uv", "run", "python"]


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
    return findings.main([str(arg) for arg in args]), capsys.readouterr().out


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


def stand_in(root: Path) -> Path:
    """A scratch fleet clone holding the stand-in ledger script."""
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts/ledger.py").write_text(STAND_IN, encoding="utf-8")
    return root


def clone(tmp_path: Path, real: bool = False) -> Path:
    """A scratch fleet clone with the fleet's own `ledger.py` and `pacer.py`, or the stand-in."""
    if not real:
        return stand_in(tmp_path / "fleet")
    (scripts := tmp_path / "fleet/scripts").mkdir(parents=True)
    for name in ("ledger.py", "pacer.py"):
        shutil.copy(LEDGER / "scripts" / name, scripts / name)
    return scripts.parent


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, env=ENV, capture_output=True, text=True, check=True, timeout=60
    )
    return done.stdout


def fake_bin(tmp_path: Path) -> str:
    """A PATH whose `uv run python` is this interpreter and whose `sleep` returns at once."""
    (bin_dir := tmp_path / "bin").mkdir(exist_ok=True)
    (bin_dir / "uv").write_text(
        '#!/bin/sh\n[ "$1" = run ] && shift\n[ "$1" = python ] && shift\n'
        f'exec "{sys.executable}" "$@"\n'
    )
    (bin_dir / "sleep").write_text("#!/bin/sh\nexit 0\n")
    for name in ("uv", "sleep"):
        (bin_dir / name).chmod(0o755)
    return f"{bin_dir}{os.pathsep}{os.environ['PATH']}"


# --- the drain: the old TSV ledger, once ------------------------------------------------


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
    lines = fleet_ledger.lines(root, "legacy")
    assert [(line["row"], line["line"]) for line in lines] == list(enumerate(ROWS.splitlines(), 1))
    assert [line["at"] for line in lines[1:3]] == ["2026-09-01T10:37:00Z", "2026-09-23T07:06:00Z"]
    assert tsv.read_text(encoding="utf-8") == ROWS, "kept until a push lands the lines"
    env = ENV | {f"GIT_{who}_{k}": v for who in ("AUTHOR", "COMMITTER") for k, v in
                 (("NAME", "ark"), ("EMAIL", "ark@localhost"))}  # fmt: skip
    main = ["update-ref", "refs/remotes/origin/main", "HEAD"]
    for args in (["init", "-q"], ["add", "ledger"], ["commit", "-q", "-m", "ledger"], main):
        subprocess.run(["git", "-C", str(root), *args], check=True, env=env)
    assert ff(capsys, "drain", incoming, "--fleet", root)[0] == 0
    assert len(fleet_ledger.lines(root, "legacy")) == 4, "a rerun adds none"
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
        (ROWS, None, "has no scripts/ledger.py"),
        (ROWS, "raise SystemExit('ledger: refused')\n", "the fleet ledger refused it"),
        (ROWS + "2026092T1000Z\t5\t?\n", STAND_IN, "row 5 has no stamp"),
        (ROWS + "20260924T2058Z\t5\t?\n20260925T1254Z\t5\t?\n", STAND_IN, "2 rows are a test"),
    ],
    ids=["no-ledger-script", "refused", "no-stamp", "test-drain-rows"],
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
    code, out = ff(capsys, "drain", tmp_path / "incoming", "--fleet", fleet)
    assert (code, said in out, tsv.read_text(encoding="utf-8")) == (0, True, body)
    assert fleet_ledger.lines(fleet, "legacy") == []


# --- the re-price -----------------------------------------------------------------------

NO_SPLIT = "net-new, no split          : 2,345 pairs, 5,897.3 EE"
KEPT = "  the split would have kept: 1,111 pairs, 1,111.1 EE  <- for the record"


def test_a_confirmed_find_is_repriced_on_the_figure_its_pricer_prints_after_the_split(
    tmp_path, monkeypatch, capsys
):
    """Only a confirmed FIND with items, by the pricer its grain names; a listing takes no split,
    and neither the figure before the split nor the one it would have kept is read."""
    disputed = drop(tmp_path / "incoming", "a-lead", finding(verify={"status": "disputed"}))
    bare = drop(tmp_path / "incoming", "b-lead")
    said = ff(capsys, "reprice", tmp_path / "incoming")[1]
    assert "a-lead is disputed, not re-priced" in said and "b-lead NOT re-priced" in said
    got = [json.loads((lead / "store_price.json").read_text()) for lead in (disputed, bare)]
    want = [("verify disputed", None), ("no items to price, see the run log", None)]
    assert [(price["status"], price["ee"]) for price in got] == want
    (disputed / "lead.json").write_text(json.dumps({"grain": "hostname"}), "utf-8")
    assert findings.grain_of("a-lead", finding(), disputed) == "hostname"
    # With no lead file the track decides, falling back to the general pricer.
    assert findings.grain_of("b-lead", finding(), bare) == "registrable"
    assert findings.grain_of("b-lead", finding(pricing={"track": "candidate"}), bare) == "candidate"
    items = findings._ITEMS_EE.search("net-new AFTER the split    : 1,234 pairs, 4,786.2 EE")
    hosts = findings._HOST_EE.search("NET-NEW hostname years 9,001  12,345.6789 EE   (quote)")
    assert (items.group(2), hosts.group(2)) == ("4,786.2", "12,345.6789")
    before = "net-new BEFORE the split   : 9,999 pairs, 9,999.9 EE  <- DO NOT QUOTE"
    assert [findings._ITEMS_EE.search(line) for line in (before, KEPT)] == [None, None]
    # The no-split line is the one `price_items.py` prints, and a listing is priced on it.
    printed = 'f"net-new, no split          : {len(netnew):,} pairs, {ee(netnew):,.1f} EE"'
    assert printed in (ROOT / "scripts/pricing/price_items.py").read_text(encoding="utf-8")
    kind = {"grain": "registrable", "evidence_class": min(NO_SPLIT_CLASSES)}
    lead, items = drop(tmp_path, "a-listing", lead=kind), tmp_path / "items.jsonl"
    monkeypatch.setattr(findings, "fetch_items", lambda _lead: items)
    ran = Mock(return_value=subprocess.CompletedProcess([], 0, f"{NO_SPLIT}\n{KEPT}\n", ""))
    monkeypatch.setattr(findings.subprocess, "run", ran)
    result = findings.price(lead, {"verdict": "FIND"})
    pricer = [*PRICER, "scripts/pricing/price_items.py", "--items", str(items), "--no-split"]
    assert [call.args[0] for call in ran.call_args_list] == [pricer]
    assert (result["status"], result["netnew"], result["ee"]) == ("priced", 2345, 5897.3)


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
    parts[1]["name"] = rename or parts[1]["name"]
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
    cmd = [*PRICER, "scripts/pricing/price_hostnames.py", str(got)]
    assert [call.args[0] for call in run.call_args_list] == [cmd]
    assert (result["status"], result["grain"], result["netnew"]) == ("priced", "hostname", 1234)
    shutil.rmtree(got)
    assert findings.price(lead, {"verdict": "FIND"})["ee"] is None


# --- the outcome line and the ledger it goes through -----------------------------------

DECIDED = "## Pending requests\n\n### a_find / artifact_listing\nDecision: master\n\n"
DECIDED += "### b_find / artifact_listing\nDecision: candidate-only\n"


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


def booked(capsys, tmp_path: Path, ingested=(), fleet=None, db=None):
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
    code, out = ff(capsys, "outcome", incoming, *flags)
    lines = fleet_ledger.lines(fleet, "outcome")
    return code, out, {f"{line['slug']}:{line['banked']}": line for line in lines}


def test_an_outcome_line_is_banked_only_once_the_store_holds_the_sources_rows(tmp_path, capsys):
    """Under a decision that admits them, and only once landed; a line that did not exits 1."""
    code, out, lines = booked(capsys, tmp_path, fleet=tmp_path / "old-clone")
    assert (code, lines, "not booked" in out) == (1, {}, True)
    code, out, lines = booked(capsys, tmp_path, fleet=clone(tmp_path), db=tmp_path / "no-store")
    assert (code, "could not be opened" in out) == (0, True)
    assert sorted(lines) == ["a-find:False", "b-find:False", "c-find:False"]
    a, b, c = lines["a-find:False"], lines["b-find:False"], lines["c-find:False"]
    assert (a["store_ee"], a["program_ee"], a["agreement_pct"]) == (1000.0, 995.0, 99.5)
    assert (a["decision"], b["decision"], c["decision"]) == ("master", "candidate-only", "pending")
    assert len(booked(capsys, tmp_path, ingested=("some_other_source",))[2]) == 3, "none added"
    _, out, lines = booked(capsys, tmp_path, ingested=("a_find", "b_find", "c_find"))
    want = ["a-find:False", "a-find:True", "b-find:False", "b-find:True", "c-find:False"]
    assert sorted(lines) == want and "2 banked in the store" in out
    assert '"banked": true' in (tmp_path / "fleet/ledger/2026-09.jsonl").read_text()


def test_the_ledger_appends_only_through_the_fleets_keyed_script_and_reads_month_by_month(
    tmp_path,
):
    """A replay adds nothing, a refused row says why, a clone without the script appends
    nothing, and a line that is not one of the kind asked for is skipped."""
    rows = [{"row": 1, "line": "a\t1\t2.0"}, {"row": 2, "line": "a\t1\t2.0"}]
    ok, said = fleet_ledger.append(tmp_path, "legacy", rows)
    assert (ok, "scripts/ledger.py" in said, (tmp_path / "ledger").exists()) == (False, True, False)
    assert fleet_ledger.lines(None, "legacy") == []
    fleet = stand_in(tmp_path)
    assert fleet_ledger.append(fleet, "legacy", rows) == (True, "ledger: 2 appended, 0 kept")
    assert fleet_ledger.append(fleet, "legacy", rows) == (True, "ledger: 0 appended, 2 kept")
    ok, said = fleet_ledger.append(fleet, "outcome", [{"slug": "x", "banked": True}])
    assert not ok and "needs its key" in said
    later = "".join(json.dumps(x) + "\n" for x in ({"kind": "legacy", "row": 3}, {"kind": "leg"}))
    (fleet / "ledger/2026-10.jsonl").write_text("not json\n[1]\n" + later)
    assert [line["row"] for line in fleet_ledger.lines(fleet, "legacy")] == [1, 2, 3]
    pairs = ((1000.0, None), (0, 5.0), (True, 5.0))
    assert [fleet_ledger.agreement_pct(*pair) for pair in pairs] == [None, None, None]


LEGACY = [
    {"row": 1, "line": "20260901T1037Z\t432\t68.0", "at": "2026-09-01T10:37:00Z"},
    {"row": 2, "line": "20260901T1037Z\t432\t68.0", "at": "2026-09-01T10:37:00Z"},
]
MONTH = "ledger/2026-09.jsonl"


def leg(clone: Path, run_id: str) -> None:
    """A leg line as the fleet's collect writes it, committed and pushed."""
    line = {"kind": "leg", "key": run_id, "run_id": run_id, "at": "2026-09-26T08:00:00Z"}
    with (clone / MONTH).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")
    git(clone, "add", MONTH)
    git(clone, "commit", "-q", "-m", f"Leg {run_id}")
    git(clone, "push", "-q", "origin", "main")


def test_a_rejected_push_replays_the_clones_ledger_lines_after_the_reset(tmp_path):
    """A collect lands first, so the laptop's push is rejected and the retry resets the clone
    onto the remote; the old TSV is gone by then, so nothing else could write its lines again."""
    origin, theirs, ours = tmp_path / "origin.git", tmp_path / "theirs", tmp_path / "ours"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    for path in (theirs, ours):
        git(tmp_path, "clone", "-q", str(origin), str(path))
        git(path, "config", "user.email", "test@example.org")
        git(path, "config", "user.name", "test")
    git(theirs, "symbolic-ref", "HEAD", "refs/heads/main")
    stand_in(theirs)
    (theirs / "ledger").mkdir()
    git(theirs, "add", "scripts")
    leg(theirs, "11")
    git(ours, "fetch", "-q", "origin")
    git(ours, "checkout", "-q", "-B", "main", "origin/main")
    assert fleet_ledger.append(ours, "legacy", LEGACY)[0]
    leg(theirs, "12")
    done = subprocess.run(
        ["bash", str(HARNESS / "push_fleet.sh"), str(ours), "20260926T0900Z"],
        cwd=tmp_path,  # no drain here, so the lead replay finds nothing to write
        env=ENV | {"TMPDIR": str(tmp_path), "PATH": fake_bin(tmp_path)},
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert "rejected on attempt 1" in done.stdout, done.stdout + done.stderr
    assert "NOT PUSHED" not in done.stdout
    git(theirs, "pull", "-q", "origin", "main")
    lines = [json.loads(text) for text in (theirs / MONTH).read_text().splitlines()]
    assert [line["run_id"] for line in lines if line["kind"] == "leg"] == ["11", "12"]
    assert [line["row"] for line in lines if line["kind"] == "legacy"] == [1, 2]


# --- the request block ------------------------------------------------------------------

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


def with_contract(fleet: Path) -> Path:
    """The fleet's validator and schemas, copied in; the clone itself is only read."""
    if CONTRACT is None:
        pytest.skip("no fleet clone with a validator to copy")
    (fleet / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONTRACT / "scripts/contract.py", fleet / "scripts/contract.py")
    shutil.copytree(CONTRACT / "schemas", fleet / "schemas")
    return fleet


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
AGREEING = [dict(line, kind="outcome", decision="master", banked=True) for line in AGREEING]


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


def test_each_confirmed_repriced_find_gets_one_pending_block_quoting_its_deciding_figure(
    tmp_path, capsys
):
    """Not a disputed, unpriced, closed or candidate-class find; a read is asked as its
    hostnames, with the lines the bank reads; nothing without --write, and once."""
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
    (fleet := tmp_path / "fleet/ledger").mkdir(parents=True)
    (fleet / "2026-09.jsonl").write_text("".join(json.dumps(line) + "\n" for line in AGREEING))
    streak = ["--fleet", str(fleet.parent)]
    request.main([str(incoming), "--register", str(register), *streak])
    assert register.read_text(encoding="utf-8") == REGISTER, "nothing without --write"
    assert "would write: a_lead" in capsys.readouterr().out
    text = block(incoming, register, *streak)
    parsed = approvals.load(register)
    new = [
        "a_lead",
        "fleet_e_read_hostnames",
        "fleet_f_read_hostnames",
        "old_source",
        "program_only",
    ]
    assert sorted(source for source, _ in parsed) == new
    assert all(
        a.decision == "pending" and a.evidence_type == "cdx_timestamp" for a in parsed.values()
    )
    facts = ["- journal: `", "- potential: 7000", "- what dates one item: 1999-05-04T11:02:13Z"]
    assert all(fact in block_of(text) for fact in [*facts, "7,000.0 EE net-new on the live store"])
    assert "- potential: 7020" in block_of(text, "program_only")
    e_read, f_read = (block_of(text, f"fleet_{s}_read_hostnames") for s in "ef")
    assert f"- ingest: ark ingest-hostnames {tmp_path / 'fleet_read/e-read'}/" in e_read
    assert f"- journal sha256: {'ab' * 32}, 2 part(s), 1,234 rows" in e_read
    assert "- journal sha256: no receipt on this machine, 0 part(s)" in f_read, "never arrived"
    assert all("- ingest spec:" not in r and "- journal: `" not in r for r in (e_read, f_read))
    assert block(incoming, register, *streak) == text
    assert "already has a block" in capsys.readouterr().out


@pytest.mark.parametrize(
    "register, standing, why",
    [
        (APPROVED, STANDING, None),
        (APPROVED, None, "the lead carries no standing admission"),
        (REGISTER, dict(STANDING, clauses=ROBOTS), f"{NEW}; {REFUSED}"),
    ],
    ids=["the-rule-decides-it", "no-standing", "new-class-and-robots"],
)
def test_a_parked_block_says_why_and_is_filed_and_a_standing_rule_block_is_decided(
    tmp_path, capsys, monkeypatch, register, standing, why
):
    """The block is the whole ask, named after its directory whatever the sidecar says."""
    lead = ASKED if standing is None else dict(ASKED, standing=standing)
    incoming, path = asked(tmp_path, lead=lead, register=register, named="another-name")
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


# --- the tick's and the bank's fleet steps, off the justfile ----------------------------


def _block(recipe: str, first: str, last: str) -> str:
    """The lines from the one starting `first` to the next one that is `last`, dedented."""
    lines = recipe.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(first))
    stop = next(i for i in range(start, len(lines)) if lines[i].rstrip() == last)
    return textwrap.dedent("\n".join(lines[start : stop + 1]))


def _bash(script: str, cwd: Path, timeout: int = 30, **env) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + script],
        cwd=cwd,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# A `gh` that lists runs the way GitHub does: newest first, filtered by `--event`, cut at
# `--limit` (GitHub's own default is 20), a 404 for a workflow it has not, and a log of downloads.
FAKE_GH = r"""
import json, os, sys
args = sys.argv[1:]
def flag(name, default=None):
    return args[args.index(name) + 1] if name in args else default
if args[:2] == ["run", "list"]:
    runs = json.load(open(os.environ["FAKE_RUNS"])).get(flag("--workflow"))
    if runs is None:
        sys.exit(f"HTTP 404: workflow {flag('--workflow')} not found")
    runs = [run for run in runs if flag("--event") in (None, run["event"])]
    for run in runs[: int(flag("--limit", "20"))]:
        print(f"{run['id']}\t{run['status']}")
elif args[:2] == ["run", "download"]:
    with open(os.environ["FAKE_LOG"], "a") as fh:
        fh.write(f"{args[2]}\n")
"""


def test_the_drain_takes_every_dispatched_run_and_a_404_skips_only_that_workflow(tmp_path):
    """A run is PROCESSED once completed, so one still running is taken again. The watchdog's
    scheduled runs carry nothing, and the oldest of a day's dispatched runs is still found."""
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin/gh").write_text(f"#!{sys.executable} -S\n{FAKE_GH}")
    (tmp_path / "bin/gh").chmod(0o755)
    runs, log, processed = tmp_path / "runs.json", tmp_path / "gh.log", tmp_path / "processed"
    drain = _block(TICK, "    for WF in leg.yaml read.yaml; do", "    done")
    paths = {"FAKE_RUNS": runs, "FAKE_LOG": log, "PROCESSED": processed, "IN": tmp_path / "in"}
    env = {"PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}"}
    env |= {name: str(path) for name, path in paths.items()}

    def drained(**workflows) -> list[str]:
        runs.write_text(json.dumps({f"{name}.yaml": listed for name, listed in workflows.items()}))
        log.write_text("")
        done = _bash(drain, tmp_path, **env)
        assert done.returncode == 0, done.stdout + done.stderr
        assert ("gh could not list leg.yaml" in done.stdout) == ("leg" not in workflows)
        return log.read_text().split()

    def run(rid: int, status: str = "completed", event: str = "workflow_dispatch") -> dict:
        return {"id": rid, "status": status, "event": event}

    reads = [run(9, "in_progress"), run(8), run(7)]
    processed.write_text("7\n")
    assert drained(read=reads) == ["9", "8"]
    assert processed.read_text().split() == ["7", "8"]
    day = [run(rid, event="schedule" if rid % 5 == 0 else "workflow_dispatch")
           for rid in range(1330, 1000, -1)]  # fmt: skip
    with processed.open("a") as fh:
        fh.write("".join(f"{r['id']}\n" for r in day if r["id"] not in (1001, 1330)))
    assert drained(leg=day, read=reads) == ["1001", "9"]


def test_a_drain_of_closed_scout_leads_alone_reaches_the_scribe(tmp_path):
    gate = _block(
        TICK, "    if ! compgen -G", '        && ! compgen -G "$IN/*/scout.md" >/dev/null; then'
    )
    script = gate + " echo nothing; else echo book; fi"
    (incoming := tmp_path / "incoming").mkdir()
    assert _bash(script, tmp_path, IN=str(incoming)).stdout.strip() == "nothing"
    (incoming / "some-lead").mkdir()
    (incoming / "some-lead" / "scout.md").write_text("# some-lead\n")
    assert _bash(script, tmp_path, IN=str(incoming)).stdout.strip() == "book"


def test_every_fleet_step_names_the_fleet_and_outcomes_follow_the_commit_before_the_push():
    """No step reads a cached queue; the outcome lines follow the register commit onto `live`,
    on every bank, and no flag from the bank says banked: the store's ingested files do."""
    steps = {
        TICK: ("fleet_findings.py drain", "discover_cycle.py"),
        BANK: ("fleet_request.py", "standing_rule.py"),
    }
    for recipe, names in steps.items():
        for name in names:
            line = next(ln for ln in recipe.splitlines() if f"scripts/harness/{name}" in ln)
            assert '--fleet "$FLEET"' in line, name
    queue = [ln for ln in RECIPE.splitlines() if "scripts/round/lead_queue.py" in ln]
    assert queue and not any("--cached" in ln for ln in queue), queue
    order = [
        'git commit -q -m "Sync fleet findings $LABEL"',
        "git push -q origin live",
        'fleet_findings.py outcome "$IN" data/fleet_findings/banked/*/',
        "fleet_leads.py",
        "push_fleet.sh",
        'mv "$IN" "data/fleet_findings/banked/$LABEL"',  # a drain leaves once committed
    ]
    at = [BANK.index(text) for text in order]
    assert at == sorted(at), order
    assert "--banked" not in BANK


def test_every_bank_books_every_drains_outcome_until_it_lands_and_its_find_is_banked(tmp_path):
    """The bank's step d, in a checkout of its own. A clone without the ledger script books
    nothing and the drain still moves; a later bank that holds no find books it pending, then
    master once the owner approves, then banked once the store holds its rows, then nothing."""
    repo = tmp_path / "repo"
    (harness := repo / "scripts/harness").mkdir(parents=True)
    for path in HARNESS.glob("*.py"):
        shutil.copy(path, harness / path.name)
    (harness / "push_fleet.sh").write_text('echo "push_fleet: pushed"\n', encoding="utf-8")
    (repo / "src").symlink_to(ROOT / "src")
    (repo / "docs/registers").mkdir(parents=True)
    (repo / "data/fleet_findings/banked").mkdir(parents=True)
    fleet = with_contract(tmp_path / "fleet")
    (fleet / "leads").mkdir()
    (lead := fleet / "leads/foo-bar.json").write_text(json.dumps(dict(LEAD, slug="foo-bar")))
    confirmed(repo / "data/fleet_findings/incoming", "foo-bar", {"status": "priced", "ee": 12000.0})
    env = {"PATH": fake_bin(tmp_path), "IN": "data/fleet_findings/incoming", "FLEET": str(fleet)}
    step_d = _block(BANK, "    # Every bank books the outcome of every drain", "    fi")

    def banked(label: str, decision: str, ran_a="no", committed="no") -> str:
        (repo / "docs/registers/approved-sources-list.md").write_text(
            f"## Pending requests\n\n### foo_bar / artifact_listing\nDecision: {decision}\n"
        )
        done = _bash(step_d, repo, 180, LABEL=label, RAN_A=ran_a, COMMITTED=committed, **env)
        assert done.returncode == 0, done.stdout + done.stderr
        return done.stdout

    keys = lambda: [line["key"] for line in fleet_ledger.lines(fleet, "outcome")]  # noqa: E731
    said = banked("20260926T0100Z", "pending", ran_a="yes", committed="yes")
    assert "the outcome lines did not land" in said and keys() == []
    assert (repo / "data/fleet_findings/banked/20260926T0100Z/foo-bar/finding.json").is_file()
    assert not any((repo / "data/fleet_findings/incoming").iterdir())
    stand_in(fleet)
    banked("20260926T0200Z", "pending")
    assert keys() == ["foo-bar:pending:False"]
    store(repo / "data/ark.duckdb", "some_other_source")
    banked("20260926T0300Z", "master")
    assert (
        keys()[-1] == "foo-bar:master:False"
        and json.loads(lead.read_text())["status"] == "verified"
    )
    store(repo / "data/ark.duckdb", "foo_bar")
    banked("20260926T0400Z", "master")
    assert (
        keys()[-1] == "foo-bar:master:True" and json.loads(lead.read_text())["status"] == "banked"
    )
    banked("20260926T0500Z", "master")
    assert len(keys()) == 3, "a later bank adds nothing"
