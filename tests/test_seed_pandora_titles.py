"""The PANDORA title index reader.

Loaded by path, like the other script tests: `scripts/` is not a package.

The BOM case is the one worth pinning. The published CSV starts with a UTF-8 BOM,
so reading it as plain `utf-8` names the first column `﻿tep_id` and a
`DictReader` lookup for `tep_id` returns nothing without raising. A file that
parses to zero usable rows looks exactly like a source with nothing in it.
"""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "seed_pandora_titles",
    Path(__file__).resolve().parents[1] / "scripts" / "seed_pandora_titles.py",
)
seeder = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(seeder)

HEADER = "tep_id,name,gathered_url,surt\n"
ROWS = (
    '/tep/1,"A title",http://www.acoss.org.au/some/path.pdf,"au,org,acoss)/some/path.pdf"\n'
    '/tep/2,"Another",http://lawlink.nsw.gov.au/x,"au,gov,nsw,lawlink)/x"\n'
    '/tep/3,"Same domain again",http://www.acoss.org.au/other,"au,org,acoss)/other"\n'
)


def test_reads_registrable_domains_and_dedupes(tmp_path: Path) -> None:
    """Two rows on one domain give one name, and the unit is the registered domain.

    `lawlink.nsw.gov.au` collapses to `nsw.gov.au`, because the pinned Public
    Suffix List snapshot carries `gov.au` and not the per-state `nsw.gov.au`.
    Asserted rather than corrected: the whole corpus was canonicalised through
    this list, and III.8 asks for registered domains, so an Australian state
    government host legitimately collapses to its state registry.
    """
    path = tmp_path / "titles.csv"
    path.write_text(HEADER + ROWS, encoding="utf-8")
    domains, stats = seeder.registrable_domains(path)
    assert domains == {"acoss.org.au", "nsw.gov.au"}
    assert stats["rows"] == 3
    assert stats["with_url"] == 3


def test_a_utf8_bom_does_not_hide_the_url_column(tmp_path: Path) -> None:
    """The published file has one, and reading it as plain utf-8 yields nothing."""
    path = tmp_path / "titles_bom.csv"
    path.write_text(HEADER + ROWS, encoding="utf-8-sig")
    domains, stats = seeder.registrable_domains(path)
    assert stats["with_url"] == 3
    assert "acoss.org.au" in domains


def test_a_missing_url_column_is_an_error_not_an_empty_result(tmp_path: Path) -> None:
    """A source that silently reads as empty is indistinguishable from a barren
    one, which is the trap the whole file exists to avoid."""
    path = tmp_path / "wrong.csv"
    path.write_text("tep_id,name\n/tep/1,A title\n", encoding="utf-8")
    try:
        seeder.registrable_domains(path)
    except SystemExit as exc:
        assert "gathered_url" in str(exc)
    else:
        raise AssertionError("a missing URL column must raise rather than return nothing")


def test_rows_with_no_url_are_counted_separately(tmp_path: Path) -> None:
    path = tmp_path / "gaps.csv"
    path.write_text(HEADER + '/tep/9,"No url",,"au,org)/"\n', encoding="utf-8")
    domains, stats = seeder.registrable_domains(path)
    assert domains == set()
    assert stats == {"rows": 1, "with_url": 0, "unparsed": 0}
