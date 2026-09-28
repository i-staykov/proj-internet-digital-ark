"""The pricers ask `held` what is already dated or known.

One store and his staged release serve all three: a pair is held when it is ours or its
exact name is in his file for that year, and a name is known when we found it or any file
of his holds it.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from his_release import WEB_METHOD, capture

from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

# In 1998: ours.com is ours and already-his.com is his; fresh.com is ours in another year;
# seeded.com is a candidate of ours with no row; no file of his holds his-filed.com or
# rolled.com, and the store keeps neither, as it keeps no name only his release filed;
# ourss.com and already-hiss.com are one edit from a known name
NAMES = (
    "ours.com already-his.com fresh.com seeded.com his-filed.com held-candidate.com "
    "lonely.com ourss.com already-hiss.com rolled.com"
)


def _load(rel: str):
    spec = importlib.util.spec_from_file_location(Path(rel).stem, _SCRIPTS / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def store(tmp_path: Path, his_files: Path, monkeypatch) -> Path:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "data/ark.duckdb"
    path.parent.mkdir()
    conn = connect(path)
    init_db(conn)
    ours = ensure_source(conn, "ia_cdx", "timestamped")
    for name in ("ours.com", "fresh.com", "seeded.com"):
        add_candidate(conn, name, ours)
    for name, year in (("ours.com", 1998), ("fresh.com", 2000)):
        row = record_evidence(
            conn, name, ours, year, "cdx_timestamp", capture(name, year), None, WEB_METHOD
        )
        assign_year(conn, row)
    conn.close()
    return path


def test_price_items_holds_by_exact_name_and_bounds_typos_on_known_names(
    store: Path, tmp_path: Path, monkeypatch, capsys
) -> None:
    items = tmp_path / "items.jsonl"
    items.write_text(json.dumps({"item": "i1", "year": 1998, "text": NAMES}) + "\n")
    price_items = _load("pricing/price_items.py")
    monkeypatch.setattr(price_items, "STORE", store)
    monkeypatch.setattr(sys, "argv", ["price_items.py", "--items", str(items)])
    price_items.main()
    out = capsys.readouterr().out
    assert "already held, ours or his  : 2\n" in out
    assert "net-new AFTER the split    : 1 pairs" in out
    assert "to the candidate pool      : 7 pairs, 5 names new to the pool" in out
    assert "typo upper bound         : 2 of 8 sampled net-new names" in out


def test_one_edit_variants_are_the_neighbourhood_and_never_the_name() -> None:
    price_items = _load("pricing/price_items.py")
    variants = price_items.one_edit_variants("ab.com")
    assert "ab.com" not in variants
    assert {"a.com", "abc.com", "ax.com", "b.com", "aab.com"} <= variants
    assert "ba.com" not in variants  # a transposition is two edits


def test_probe_texts_corpus_holds_by_exact_name(store: Path, tmp_path: Path, monkeypatch, capsys):
    probe = _load("pricing/probe_texts_corpus.py")
    monkeypatch.setattr(probe, "search", lambda query, rows: [{"identifier": "i1", "year": 1998}])
    monkeypatch.setattr(probe, "full_text", lambda identifier, cache: NAMES)
    monkeypatch.setattr(sys, "argv", ["probe", "--query", "q", "--cache", str(tmp_path / "c")])
    probe.main()
    out = capsys.readouterr().out
    assert "net-new pairs        8\n" in out
    assert "net-new domains      7\n" in out
    assert "corroborated (domain already in an annual file): 1\n" in out
    assert "never seen at all (not even a candidate): 5\n" in out


def test_request_approval_holds_by_exact_name(store: Path, tmp_path: Path, monkeypatch) -> None:
    approval = _load("harness/request_approval.py")
    register = tmp_path / "approvals.md"
    register.write_text("## Pending requests\n\nNone.\n", encoding="utf-8")
    monkeypatch.setattr(approval, "ROOT", tmp_path)
    monkeypatch.setattr(approval, "APPROVALS", register)
    monkeypatch.setattr(approval, "nearest_closed", lambda name: "nothing close.")
    journal = tmp_path / "udrp.jsonl"
    journal.write_text(
        "".join(json.dumps({"domain": d, "year": 1998}) + "\n" for d in NAMES.split()),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv", ["request_approval.py", "udrp_proceedings", "--journal", str(journal)]
    )
    approval.main()
    text = register.read_text(encoding="utf-8")
    assert "| already held, ours or his | 2 |" in text
    assert "| `master` (taking the corroboration split) | 1 |" in text
