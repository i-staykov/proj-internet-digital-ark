"""Taking one source's rows back out, which is the other half of a standing-rule decision.

This is the only code in the project that deletes evidence, so the tests are about its edges
rather than its happy path: it must take every table the ingest wrote, leave every other
source untouched, and do nothing at all without `--write`.
"""

import importlib.util
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/harness/unbank_source.py"

_SPEC = importlib.util.spec_from_file_location("unbank_source", SCRIPT)
unbank = importlib.util.module_from_spec(_SPEC)
sys.modules["unbank_source"] = unbank
_SPEC.loader.exec_module(unbank)

from ark.db import SCHEMA_SQL  # noqa: E402


def store(tmp_path) -> Path:
    """Two sources, one domain each, both dated, one of them also at hostname grain."""
    path = tmp_path / "ark.duckdb"
    conn = duckdb.connect(str(path))
    conn.execute(SCHEMA_SQL)
    for source_id, name in ((1, "keeper"), (2, "condemned")):
        conn.execute("INSERT INTO source VALUES (?, ?, 'timestamped', NULL)", [source_id, name])
    for domain, source_id in (("keep.com", 1), ("gone.com", 2)):
        conn.execute(
            "INSERT INTO domain (domain, tld, discovered_source) VALUES (?, ?, ?)",
            [domain, domain.rsplit(".", 1)[-1], source_id],
        )
    for evidence_id, domain, source_id in ((10, "keep.com", 1), (20, "gone.com", 2)):
        conn.execute(
            "INSERT INTO evidence (evidence_id, domain, source_id, evidence_year, evidence_type,"
            " evidence_value) VALUES (?, ?, ?, 1998, 'cdx_timestamp', 'x')",
            [evidence_id, domain, source_id],
        )
        conn.execute(
            "INSERT INTO domain_year (domain, assigned_year, evidence_id) VALUES (?, 1998, ?)",
            [domain, evidence_id],
        )
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id)"
        " VALUES ('www.gone.com', 'gone.com', 1998, 20)"
    )
    conn.execute("INSERT INTO ingested_file VALUES ('condemned', 'j.jsonl.gz', 'abc', 1, now())")
    conn.close()
    return path


def rows(path: Path, sql: str) -> int:
    conn = duckdb.connect(str(path), read_only=True)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


def test_the_condemned_sources_rows_all_go(tmp_path):
    path = store(tmp_path)
    assert unbank.main(["condemned", "--db", str(path), "--write"]) == 0
    assert rows(path, "SELECT count(*) FROM evidence WHERE source_id = 2") == 0
    assert rows(path, "SELECT count(*) FROM domain_year WHERE domain = 'gone.com'") == 0
    assert rows(path, "SELECT count(*) FROM hostname_year") == 0
    assert rows(path, "SELECT count(*) FROM ingested_file") == 0


def test_every_other_source_is_untouched(tmp_path):
    path = store(tmp_path)
    unbank.main(["condemned", "--db", str(path), "--write"])
    assert rows(path, "SELECT count(*) FROM evidence WHERE source_id = 1") == 1
    assert rows(path, "SELECT count(*) FROM domain_year WHERE domain = 'keep.com'") == 1


def test_the_domain_and_the_source_rows_stay(tmp_path):
    # A domain nothing dates is a candidate, which is a true statement about it, and
    # `domain.discovered_source` still references the source row.
    path = store(tmp_path)
    unbank.main(["condemned", "--db", str(path), "--write"])
    assert rows(path, "SELECT count(*) FROM domain WHERE domain = 'gone.com'") == 1
    assert rows(path, "SELECT count(*) FROM source WHERE name = 'condemned'") == 1


def test_without_write_it_only_counts(tmp_path, capsys):
    path = store(tmp_path)
    assert unbank.main(["condemned", "--db", str(path)]) == 0
    assert rows(path, "SELECT count(*) FROM evidence WHERE source_id = 2") == 1
    assert "holds" in capsys.readouterr().out


def test_a_source_the_store_never_held_is_reported_not_an_error(tmp_path, capsys):
    path = store(tmp_path)
    assert unbank.main(["never_ingested", "--db", str(path), "--write"]) == 0
    assert "not in the store" in capsys.readouterr().out


def test_a_spec_key_is_translated_to_the_name_the_store_uses():
    from ark.sources import SOURCES

    key = next(iter(SOURCES))
    assert unbank.source_names([key]) == [SOURCES[key].source_name]
    assert unbank.source_names(["not_a_spec"]) == ["not_a_spec"]
