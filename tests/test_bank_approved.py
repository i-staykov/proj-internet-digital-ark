"""Only a `master` class banks, the unbankable are loud, and a red gate unbanks only this bank."""

import importlib.util
import io
import json
import re
import subprocess
import sys
import urllib.error
from functools import partial
from pathlib import Path
from unittest.mock import ANY, Mock

import duckdb
import pytest

from ark.approvals import load
from ark.db import SCHEMA_SQL

ROOT = Path(__file__).resolve().parents[1]
RECIPE = (ROOT / "justfile").read_text(encoding="utf-8")


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/harness/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # its dataclasses resolve their annotations through sys.modules
    spec.loader.exec_module(module)
    return module


bank, unbank = _module("bank_approved"), _module("unbank_source")
SPECS = {f"{n}_spec": Mock(source_name=f"{n}_source") for n in ("foo", "bar")}
JOURNAL, URL = "data/raw/foo/foo.jsonl.gz", "https://example.org/foo.jsonl.gz"
SPEC, JLINE, REFETCH = "ingest spec: `foo_spec`", f"journal: `{JOURNAL}`", f"refetch: {URL}"
FOO, BAR, READ = (f"{s} / cdx_timestamp" for s in ("foo_source", "bar_source", "fleet_x_hostnames"))
PARTS = [f"fleetread_bulk_cdx_file__x_000{n}.jsonl.gz" for n in (1, 2)]
TAG, READ_DIR = "fleetread_bulk_cdx_file__x_abababababab", "data/raw/fleet_read/x"
REGISTRABLES = f"data/raw/cdx/cdx_suffix_{TAG}.jsonl.gz"
READ_BLOCK = f"### {READ}\n\n- ingest: ark ingest-hostnames {READ_DIR}/\n\nDecision: master\n"
WHOIS = "fleetread_whois_dump__x_0002.jsonl.gz"


def _block(*lines: str, heading: str = FOO, decision: str = "master") -> str:
    return f"### {heading}\n\n" + "".join(f"- {s}\n" for s in lines) + f"\nDecision: {decision}\n\n"


def _approved(root: Path, *blocks: str, journal: bool = False) -> tuple[str, dict]:
    """The blocks read back through the real approvals parser, the journal on disk if asked."""
    text = "# approvals\n\n## Priced\n\n" + "".join(blocks)
    (root / "approved-sources-list.md").write_text(text, encoding="utf-8")
    if journal:
        (root / JOURNAL).parent.mkdir(parents=True)
        (root / JOURNAL).write_bytes(b"rows")
    return text, load(root / "approved-sources-list.md")


def _plan(root: Path, text: str, approvals: dict, banked=()):
    return bank.plan_bank(text, approvals, root=root, read=lambda _: set(banked), specs=SPECS)


def _outcomes(plan, root: Path) -> dict[str, list[tuple]]:
    """Every non-empty list of the plan, its paths relative to the root."""
    rel = lambda v: str(v.relative_to(root)) if isinstance(v, Path) else v  # noqa: E731
    out = {"blocked": plan.blocked, "waiting": [(r.label,) for r in plan.waiting]}
    for name in ("ready", "done", "refetch", "reads"):
        out[name] = [tuple(map(rel, row)) for row in getattr(plan, name)]
    return {name: rows for name, rows in out.items() if rows}


def _read_dir(root: Path, parts=PARTS, extra=(), complete=True) -> None:
    """A pulled read: `parts` named by its receipt, `extra` on disk beside them."""
    (root / READ_DIR).mkdir(parents=True)
    for name in [*parts, *extra]:
        (root / READ_DIR / name).write_bytes(b"rows")
    named = [{"name": name, "sha256": "cd" * 32} for name in parts]
    receipt = {"complete": complete, "journal_sha256": "ab" * 32, "parts": named}
    (root / READ_DIR / "receipt.json").write_text(json.dumps(receipt))


@pytest.mark.parametrize(
    "block,disk,banked,expected",
    [
        (_block(SPEC, JLINE), "journal", (), {"ready": [("foo_spec", JOURNAL)]}),
        (_block(SPEC, JLINE, decision="pending"), "journal", (), {"waiting": [(FOO,)]}),
        (_block(SPEC, JLINE, decision="rejected"), "journal", (), {}),
        (_block(SPEC, JLINE, REFETCH), None, (), {"refetch": [("foo_spec", URL, JOURNAL)]}),
        (_block(SPEC, JLINE, REFETCH), None, ["foo.jsonl.gz"],
         {"done": [("foo_spec", "foo.jsonl.gz")]}),
        (_block(SPEC, JLINE), None, (), (FOO, f"journal {JOURNAL} is not on this machine and the"
         " block carries no `- refetch:` line")),
        (_block(SPEC, "journal: `../../etc/passwd`", REFETCH), None, (),
         (FOO, "journal path escapes the repository: ../../etc/passwd")),
        (READ_BLOCK, {}, (), {"reads": [(READ, READ_DIR)]}),
        (READ_BLOCK, {}, PARTS, {"done": [(READ, "2 part(s) of x")]}),
        (READ_BLOCK, {}, (Path(REGISTRABLES).name, PARTS[0]), {"reads": [(READ, READ_DIR)]}),
        (READ_BLOCK, {"complete": False}, (), "no complete read"),
        (READ_BLOCK, None, (), "no complete read"),
        (READ_BLOCK, {"extra": ["fleetread_bulk_cdx_file__x_0003.jsonl.gz"]}, (),
         "a part on disk is not the receipt's, or a named part is not a part"),
        (READ_BLOCK, {"parts": [PARTS[0], "fleetread_bulk_cdx_file__y_0001.jsonl.gz"]}, (),
         "its parts are not all fleet_x_hostnames's"),
        (READ_BLOCK, {"parts": [PARTS[0], WHOIS]}, (),
         f"{WHOIS}: whois_dump is not a web method, so it dates no host"),
    ],
    ids=["master-banks", "pending-never-banks", "rejected-never-banks", "absent-is-refetched",
         "ingested-is-not-refetched", "no-bytes-no-refetch-is-blocked", "path-escapes-repo",
         "read-banks", "read-every-part-banked-is-done", "read-stopped-part-way-runs-again",
         "read-incomplete-receipt", "read-never-arrived", "read-stray-part",
         "read-another-leads-part", "read-not-a-web-method"],
)  # fmt: skip
def test_each_approved_class_plans_to_one_outcome(tmp_path, block, disk, banked, expected):
    text, approvals = _approved(tmp_path, block, journal=disk == "journal")
    if isinstance(disk, dict):
        _read_dir(tmp_path, **disk)
    if isinstance(expected, str):
        expected = (READ, f"{expected} in {READ_DIR} on this machine")
    expected = {"blocked": [expected]} if isinstance(expected, tuple) else expected
    assert _outcomes(_plan(tmp_path, text, approvals, banked), tmp_path) == expected


def test_an_absent_journal_is_reported_refetched_and_then_banked(tmp_path, capsys) -> None:
    """A block ends at a heading, keys are backticked, planning writes nothing, unbanked is loud."""
    bar = _block("ingest spec: `bar_spec`", "journal: `data/raw/bar/bar.gz`", heading=BAR)
    foo = _block("ingest spec: `foo_spec`, reading `*dn:` and nothing else", JLINE, REFETCH)
    text, approvals = _approved(tmp_path, bar, foo)
    tree = lambda: {p: p.is_file() and p.read_bytes() for p in tmp_path.rglob("*")}  # noqa: E731
    before, plan = tree(), _plan(tmp_path, text, approvals)
    assert _plan(tmp_path, text, approvals) == plan and tree() == before
    bank.report(plan)
    printed = capsys.readouterr().out
    assert f"refetching from {URL}" in printed and f"NOT BANKED: 1\n!!   {BAR}: journal" in printed
    fetch = partial(bank.download, opener=lambda *a, **k: io.BytesIO(b"rows"))
    assert "refetched foo.jsonl.gz for foo_spec" in bank.run_refetches(plan.refetch, fetch)[0]
    assert _plan(tmp_path, text, approvals).ready == [("foo_spec", tmp_path / JOURNAL)]


@pytest.mark.parametrize(
    "opener,said",
    [
        (lambda *a, **k: io.BytesIO(b"<!DOCTYPE html><title>Sign in</title>" + b"x" * 4000),
         "the response is a page, not the artifact"),
        (Mock(side_effect=urllib.error.HTTPError(URL, 503, "busy", {"Retry-After": "600"}, None)),
         "HTTP 503, Retry-After 600"),
    ],
    ids=["html-page", "throttled-503"],
)  # fmt: skip
def test_a_refetch_that_is_not_the_artifact_fails_and_leaves_nothing(tmp_path, opener, said):
    with pytest.raises(bank.RefetchFailed, match=re.escape(said)):
        bank.download(URL, tmp_path / "foo.jsonl.gz", opener=opener)
    assert {p.name for p in tmp_path.iterdir()} <= {"approvals.md"}  # the conftest register


def test_a_red_gate_unbanks_only_the_reads_source(tmp_path, monkeypatch, capsys) -> None:
    """Every ingest of a read names its own source; a source older than the bank is refused."""
    found = re.search(r"INGESTED=\$\(awk '([^']+)' \"\$BANK_LOG\"\)", RECIPE)
    begun = re.search(r"B_START=\$\(date -u \+(\S+)\)", RECIPE)
    assert found and begun and begun.start() < RECIPE.index("bank_approved.py --write")
    assert re.search(r'unbank_source\.py \$INGESTED --write \\\s+--run-start "\$B_START"', RECIPE)
    start = subprocess.run(["date", "-u", f"+{begun.group(1)}"], capture_output=True, text=True)
    _approved(tmp_path, READ_BLOCK)
    _read_dir(tmp_path)
    (tmp_path / REGISTRABLES).parent.mkdir(parents=True)
    ran = []

    def run(command, **_):
        if bank.CONVERTER in command:  # the converter found one exact-host registrable
            (tmp_path / REGISTRABLES).write_bytes(b"{}")
        return ran.append(command) or Mock(returncode=0)

    monkeypatch.setattr(bank, "ROOT", tmp_path)
    monkeypatch.setattr(bank, "APPROVALS", tmp_path / "approved-sources-list.md")
    monkeypatch.setattr(bank, "files_read", lambda _: set())
    monkeypatch.setattr(bank.subprocess, "run", run)
    monkeypatch.setattr(sys, "argv", ["bank_approved.py", "--write"])
    bank.main()
    monkeypatch.undo()
    log = capsys.readouterr().out + "== uv run ark ingest cdx_snapshot data/raw/cdx/a.jsonl.gz\n"
    glob, ingest = f"{READ_DIR}/{bank.READ_PARTS}", "uv run ark ingest fleet_x_hostnames".split()
    assert ran[0][3:] == [bank.CONVERTER, "--glob", glob, "--tag", TAG, "--state", ANY]
    assert ran[1:] == [[*ingest, REGISTRABLES], [*ingest, *(f"{READ_DIR}/{p}" for p in PARTS)]]
    awk = subprocess.run(["awk", found.group(1)], input=log, capture_output=True, text=True)
    assert awk.stdout.split() == ["fleet_x_hostnames", "fleet_x_hostnames", "cdx_snapshot"]
    db = str(tmp_path / "ark.duckdb")
    with duckdb.connect(db) as conn:
        conn.execute(
            SCHEMA_SQL + ";INSERT INTO source VALUES (1, 'ia_cdx_bulk', 'timestamped', NULL),"
            " (2, 'fleet_x_hostnames', 'timestamped', NULL); INSERT INTO domain"
            " (domain, discovered_source) VALUES ('o.com', 1), ('n.com', 1), ('r.com', 2);"
            "INSERT INTO evidence (domain, source_id, evidence_year, evidence_type, evidence_value,"
            " ingested_at) SELECT domain, discovered_source, 1998, 'cdx_timestamp', 'x',"
            " if(domain = 'o.com', '2026-01-01'::TIMESTAMPTZ, now()) FROM domain;"
            "INSERT INTO domain_year SELECT domain, 1998, evidence_id, now() FROM evidence;"
            "INSERT INTO hostname_year SELECT 'www.' || domain, domain, 1998, evidence_id, now()"
            " FROM evidence; INSERT INTO ingested_file SELECT s.name, domain, 'abc', 1,"
            " ingested_at FROM evidence JOIN source s USING (source_id)"
        )
        held = unbank.counts(conn, "ia_cdx_bulk")
    args = [*awk.stdout.split(), "--db", db, "--write", "--run-start", start.stdout.strip()]
    assert unbank.main(args) == 1
    assert "REFUSED ia_cdx_bulk" in capsys.readouterr().err
    with duckdb.connect(db, read_only=True) as conn:
        assert unbank.counts(conn, "ia_cdx_bulk") == held == dict.fromkeys(held, 2), "every grain"
        assert not any(unbank.counts(conn, "fleet_x_hostnames").values())
