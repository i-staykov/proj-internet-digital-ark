"""What the bank takes from the fleet: a read only when it matches its receipt, one pending block
per repriced find, the standing rule's decision, the asks filed together at the gate, and the
push that must not drop a ledger line."""

import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import duckdb
import pytest
from conftest import script

from ark import approvals
from ark.db import init_db
from ark.hostnames import ingest_hostname_journal

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts/harness"
RECIPE = (ROOT / "justfile").read_text(encoding="utf-8")
BANK = RECIPE[RECIPE.index("\nbank ") :]
BANK = BANK[: BANK.index("\n\n")]
# Under a hook git exports GIT_DIR and GIT_INDEX_FILE, and a scratch clone would stage into ours.
ENV = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


NAMES = ("fleet_ledger", "fleet_findings", "fleet_request", "ack_journals", "fleet_leads")
fleet_ledger, findings, request, ack, leads = (script(f"harness/{name}.py", name) for name in NAMES)
import sync_approvals  # noqa: E402  fleet_request put scripts/harness on the path

# A stand-in for the fleet's `scripts/ledger.py append`: it keys a line on the fields the real
# one names, keeps one it already holds, and refuses a line missing a key field.
STAND_IN = r"""
import json, sys
from pathlib import Path
KINDS = {"outcome": ("slug", "decision", "banked")}
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
PRICER = ["uv", "run", "python"]


@pytest.fixture(autouse=True)
def _no_real_box(tmp_path, monkeypatch):
    """Items and reads come from scratch remotes into a scratch pull, never from the fleet."""
    monkeypatch.setenv("ARK_ITEMS_REMOTE", str(tmp_path / "no-items"))
    monkeypatch.setenv("ARK_TELEMETRY_DIR", "/nonexistent")
    monkeypatch.delenv("ARK_READ_REMOTE", raising=False)
    for module in (findings, request):
        monkeypatch.setattr(module, "FLEET_READ", tmp_path / "fleet_read")


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


# --- the re-price -----------------------------------------------------------------------


def remote_read(root: Path, complete=True, tamper=False, extra="", rename="") -> Path:
    """A read as `read.yaml` leaves it: the parts plus the receipt that lists them."""
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
    """Priced on its pulled parts at hostname grain; the fleet frees a part its ingest acked."""
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


OUTCOMES = [
    {"slug": s, "decision": "held", "banked": False, "at": "2026-09-01T10:37:00Z"}
    for s in ("a", "b")
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
    onto the remote and writes the laptop's lines again."""
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
    assert fleet_ledger.append(ours, "outcome", OUTCOMES)[0]
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
    assert [line["slug"] for line in lines if line["kind"] == "outcome"] == ["a", "b"]


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
    assert all(fact in block_of(text) for fact in [*facts, "7,000.0 EE deciding**, part 1 plus"])
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
    filed = [(r.source, r.potential, r.failed) for r in sync_approvals.requests()]
    if why is None:
        assert all("no ask: the standing rule decides it" in s for s in (dry, said))
        assert "sync_approvals.py" not in dry + said and filed == []
        assert approvals.load(path)[("a_lead", "cdx_timestamp")].decision == "master"
    else:
        assert all(
            f"parked: {why}" in s and "sync_approvals.py files the" in s for s in (dry, said)
        )
        assert filed == [("a_lead", 7000.0, f"parked by the standing rule: {why}")]


def test_asks_file_together_at_the_gate_and_never_twice(tmp_path, monkeypatch, capsys):
    """Four asks, none alone at the gate, all file once their sum reaches it; a second run finds
    them open and files nothing; one ask fewer and the sum is under the gate, so nothing files."""
    asks = {"ask_a": 15_000, "ask_b": 20_000, "ask_c": 25_000, "ask_d": 18_000}

    def register(names):
        head = "# Approved sources\n\n## Pending requests\n\n"
        rows = (
            f"### {n} / cdx_timestamp\nDecision: pending\n- potential: {asks[n]:,}\n\n"
            for n in names
        )
        return head + "".join(rows)

    path = tmp_path / "approvals.md"
    path.write_text(register(asks), encoding="utf-8")
    issues: dict[str, str] = {}
    monkeypatch.setattr(sync_approvals, "REGISTER", path)
    monkeypatch.setattr(sync_approvals, "GATE", 60_000.0)
    monkeypatch.setattr(sync_approvals, "open_prs", dict)
    monkeypatch.setattr(sync_approvals, "open_issues", lambda: dict(issues))
    monkeypatch.setattr(sync_approvals, "raise_pr", lambda r, dry: f"pr/{r.slug}")
    filed = lambda r, pr, dry: issues.setdefault(r.title, f"issue/{r.slug}")  # noqa: E731
    monkeypatch.setattr(sync_approvals, "raise_issue", filed)
    assert sync_approvals.main([]) == 0
    assert sorted(issues) == [f"Approve {n}? {ee:,} EE" for n, ee in sorted(asks.items())]
    assert sync_approvals.main([]) == 0 and len(issues) == 4
    assert capsys.readouterr().out.count("open already") == 4
    issues.clear()
    path.write_text(register([n for n in asks if n != "ask_c"]), encoding="utf-8")
    assert sync_approvals.main([]) == 0 and issues == {}
    assert "3 asks, 53,000 of 60,000 EE to the gate" in capsys.readouterr().out


# --- the tick's and the bank's fleet steps, off the justfile ----------------------------


def test_a_stale_artifact_leaves_a_lead_the_fleet_re_dealt_alone(tmp_path):
    """A disputed FIND in the drain closes its lead only while the fleet's own finding agrees."""
    slug = "a-lead-no-register-holds"
    disputed = {"verdict": "FIND", "verify": {"status": "disputed"}}
    (tmp_path / "in" / slug).mkdir(parents=True)
    (tmp_path / "in" / slug / "finding.json").write_text(json.dumps({"slug": slug, **disputed}))
    (tmp_path / "fleet" / "scripts").mkdir(parents=True)
    (tmp_path / "fleet" / "schemas").mkdir()
    (tmp_path / "fleet" / "schemas" / "lead.json").write_text("{}")
    (tmp_path / "fleet" / "scripts" / "contract.py").write_text(
        "from pathlib import Path\nSCHEMAS = Path(__file__).resolve().parents[1] / 'schemas'\n"
        "def check_schema(doc, schema):\n    return []\ndef check_semantics(doc):\n    return []\n"
    )
    lead, now = tmp_path / "fleet" / "leads" / f"{slug}.json", tmp_path / "fleet" / "leads" / slug
    now.mkdir(parents=True)
    for fleet_has, status in (({"verdict": "BLOCKED"}, "scouted"), (disputed, "closed")):
        lead.write_text(json.dumps({"slug": slug, "status": "scouted"}))
        (now / "finding.json").write_text(json.dumps(fleet_has))
        leads.main([str(tmp_path / "in"), "--fleet", str(tmp_path / "fleet"), "--write"])
        assert json.loads(lead.read_text())["status"] == status
