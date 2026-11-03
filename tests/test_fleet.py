"""What the bank takes from the fleet: a read only when it matches its receipt, and the ack the
fleet frees a part by, which names the part's bytes only once the store's ingest holds them."""

import gzip
import hashlib
import json
from pathlib import Path

import duckdb
import pytest
from conftest import script

from ark import approvals
from ark.db import init_db
from ark.hostnames import ingest_hostname_journal

findings = script("harness/fleet_findings.py", "fleet_findings")
ack = script("harness/ack_journals.py", "ack_journals")


@pytest.fixture(autouse=True)
def _no_real_box(tmp_path, monkeypatch):
    """Items and reads come from scratch remotes into a scratch pull, never from the fleet."""
    monkeypatch.setenv("ARK_ITEMS_REMOTE", str(tmp_path / "no-items"))
    monkeypatch.setenv("ARK_TELEMETRY_DIR", "/nonexistent")
    monkeypatch.delenv("ARK_READ_REMOTE", raising=False)
    monkeypatch.setattr(findings, "FLEET_READ", tmp_path / "fleet_read")


def store(path: Path) -> Path:
    conn = duckdb.connect(str(path))
    init_db(conn)
    conn.close()
    return path


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


def test_only_a_read_matching_its_receipt_is_pulled_and_its_ingest_acks_it(
    tmp_path, monkeypatch, capsys
):
    lead = tmp_path / "incoming/a-lead"
    for n, (kwargs, said) in enumerate(BAD_READS):
        monkeypatch.setenv("ARK_READ_REMOTE", str(remote_read(tmp_path / str(n), **kwargs)))
        assert findings.fetch_read(lead) is None and said in capsys.readouterr().out
        assert list((tmp_path / "fleet_read").iterdir()) == [], f"{said}: no read, no staging"
    monkeypatch.setenv("ARK_READ_REMOTE", str(remote_read(tmp_path / "whole")))
    assert (got := findings.fetch_read(lead)) == tmp_path / "fleet_read/a-lead"
    names = sorted(p.name for p in got.glob("fleetread_*"))
    assert names == [f"fleetread_bulk_cdx_file__a-lead_000{n}.jsonl.gz" for n in (1, 2)]
    (register := tmp_path / "approved.md").write_text(HOSTNAMES, encoding="utf-8")
    monkeypatch.setattr(approvals, "DEFAULT_APPROVALS_PATH", register)
    conn, part = duckdb.connect(str(db := store(tmp_path / "store.duckdb"))), got / names[0]
    assert ingest_hostname_journal(conn, part)["hostname_year_rows"] == 1
    conn.close()
    assert ack.acks(db) == [(part.name, hashlib.sha256(part.read_bytes()).hexdigest())]
