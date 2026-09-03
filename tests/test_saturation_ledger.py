"""The shipped saturation ledger, read out of the register by column header.

Loaded by path, like the other script tests: `scripts/` is not a package.

The register moved from prose in two table cells to one row per source on
2026-09-03, so this parser reads headings rather than regexes over sentences. A
heading that gets renamed silently empties a column of the shipped CSV, which is
why the fixture spells both table shapes out.
"""

import csv
import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "saturation_ledger",
    Path(__file__).resolve().parents[1] / "scripts/round/saturation_ledger.py",
)
ledger = importlib.util.module_from_spec(_SPEC)
sys.modules["saturation_ledger"] = ledger
_SPEC.loader.exec_module(ledger)

OPEN_TABLE = """## Evaluated and rejected

| source | version or date | coverage period | retrieval method | what dates one item | \
baseline overlap | net-new EE (date) | quality issues | effort | verdict | link |
|---|---|---|---|---|---|---|---|---|---|---|
| ripe_dbase_1999 | 1999-01-07 | 1996-1999 | ftp listing | the dump's own cut stamp | \
41.2% held | 90,770.29 (2026-08-26) | one edition only | 1.2 GB | active | <https://example.org/x> |
| squidguard_origin | 2001-12-18 | 2001 | http download | the tar member header | 84.8% known | \
10,376.92 (2026-08-30) | robot-compiled, so novelty is low | 429,365 bytes | parked | n/a |
"""

CLOSED_TABLE = """# Closed sources

| source | date | measured | reason | link |
|---|---|---|---|---|
| nz_dnc_zone_data / whois_creation | 2026-08-24 | 7,586 EE | Measured at 7,586 EE and rejected \
on the registry's own terms. Do not reopen without written permission | n/a |
"""


def test_the_eleven_column_table_maps_onto_the_reviewer_schema() -> None:
    rows = ledger.rows_from_register(OPEN_TABLE, "docs/sources.md")
    assert [r["source_family"] for r in rows] == ["ripe_dbase_1999", "squidguard_origin"]
    first = rows[0]
    assert first["version_or_date"] == "1999-01-07"
    assert first["coverage_period"] == "1996-1999"
    assert first["retrieval_method"] == "ftp listing"
    assert first["baseline_overlap"] == "41.2% held"
    assert first["coverage_ee"] == "90770.29"
    assert first["what_dates_one_item"] == "the dump's own cut stamp"
    assert first["effort"] == "1.2 GB"
    assert first["status"] == "active"
    assert first["decision"] == "retain: still contributing"
    assert first["reference"] == "docs/sources.md"
    assert rows[1]["status"] == "parked"
    assert rows[1]["decision"] == "revisit: priced, not banked"


def test_the_five_column_closed_table_fills_what_it_can() -> None:
    """`sources-closed.md` has five columns, so the rest stays empty rather than guessed."""
    rows = ledger.rows_from_register(CLOSED_TABLE, "docs/sources-closed.md")
    assert len(rows) == 1
    row = rows[0]
    assert row["source_family"] == "nz_dnc_zone_data / whois_creation"
    assert row["coverage_ee"] == "7586"
    assert row["status"] == "closed"
    assert row["coverage_period"] == ""
    assert row["retrieval_method"] == ""
    # the decision quotes the entry from its reopen condition on, never a template
    assert row["decision"] == "reopen without written permission"


def test_the_real_register_is_read_from_both_files(tmp_path: Path) -> None:
    """A parser that stops matching the documents reports an empty ledger, and an
    empty ledger looks like a source-free round rather than a broken script."""
    out = tmp_path / "ledger.csv"
    sys.argv = [
        "saturation_ledger",
        "--out",
        str(out),
        "--contribution",
        str(tmp_path / "absent.csv"),
    ]
    assert ledger.main() == 0
    rows = list(csv.DictReader(out.open()))
    assert len(rows) > 400
    assert {r["status"] for r in rows} <= {"active", "parked", "closed"}
    families = {r["source_family"] for r in rows}
    for expected in ("nz_dnc_zone_data", "early_web_cdx_hostname_grain"):
        assert any(expected in f for f in families), f"{expected} missing from the ledger"
    from_closed = [r for r in rows if r["reference"] == "docs/sources-closed.md"]
    assert len(from_closed) > 300, "the closed half of the register is not being read"
