"""The register conversion: does a row plus its detail block still say everything?

The first attempt at this passed its own invariants (source keys equal, URL
occurrences equal, no line over 500) and still deleted a clause from one entry, split
a URL across two cells, and replaced source links with detail anchors. Those three are
what these tests pin, on fixtures small enough to read.

Loaded by path, like the other script tests: `scripts/` is not a package.
"""

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "convert_register",
    Path(__file__).resolve().parents[1] / "scripts/round/convert_register.py",
)
convert = importlib.util.module_from_spec(_SPEC)
sys.modules["convert_register"] = convert
_SPEC.loader.exec_module(convert)

LONG_URL = "https://discmaster.textfiles.com/file/14148/MacHack%202001.toast/pc/squid/access.log"

# One entry of each shape the register carries: a short one that fits its row, a long
# one that cannot, a closed one that moves file, and one whose prose names a URL.
REGISTER = f"""# Sources

Preamble.

## Evaluated and rejected

| Source | Verdict |
|---|---|
| **short_family (2026-09-01)** | **FIND at 12 EE.** What dates one item: the header stamp. |
| **nerd_world (2026-09-01)** | **CLOSED at 0 EE.** What dates one item: the CGI's own \
per-entry stamp. 399 of 2,059 distinct domains held-and-missing-2001, so the artifact adds \
no year to a name we hold, and the reopen condition is a 2001 capture that does not exist. \
Artifact: <{LONG_URL}>. Sampled 44 of 44 already held. |
| **blocked_family (2026-08-30)** | **BLOCKED on robots.** Nothing was fetched. |

## Something after the register

Trailing prose.
"""

CLOSED = """# Closed sources

One row per source measured and closed.

| source | date | measured | reason | link |
|---|---|---|---|---|
| earlier_triage_row | 2026-08-24 | 0.9 EE | Answered before. |  |
"""


def _convert(tmp_path: Path) -> tuple[str, str, list]:
    sources = tmp_path / "sources.md"
    closed = tmp_path / "sources-closed.md"
    sources.write_text(REGISTER, encoding="utf-8")
    closed.write_text(CLOSED, encoding="utf-8")
    new_sources, new_closed, entries = convert.convert(sources, closed)
    assert convert.check(entries, (REGISTER, CLOSED), (new_sources, new_closed)) == []
    return new_sources, new_closed, entries


def test_every_entry_keeps_every_token_in_its_own_row_or_detail_block(tmp_path: Path) -> None:
    """Per entry, not per file. A whole-file count hides one loss behind one gain."""
    _, _, entries = _convert(tmp_path)
    for entry in entries:
        row = convert.closed_row(entry) if entry.closed else convert.open_row(entry)
        kept = row + " ".join(convert.detail_block(entry)) if entry.detail else row
        assert not any(convert.missing(entry.original, kept)), entry.key


def test_the_clause_the_first_attempt_deleted_survives(tmp_path: Path) -> None:
    """`399 of 2,059 distinct domains held-and-missing-2001` was lost between two
    extractors reading different windows. One window now, and it is checked."""
    new_sources, new_closed, _ = _convert(tmp_path)
    both = new_sources + new_closed
    for token in ("399", "2,059", "held-and-missing-2001"):
        assert token in both, token


def test_a_url_is_never_split_and_never_truncated(tmp_path: Path) -> None:
    new_sources, new_closed, entries = _convert(tmp_path)
    found = convert.URL_RE.findall(new_sources) + convert.URL_RE.findall(new_closed)
    assert LONG_URL in found
    # no fragment of it anywhere: a halved URL is a URL the input never had
    assert set(found) == set(convert.URL_RE.findall(REGISTER + CLOSED))


def test_the_link_column_holds_the_source_url_not_only_the_anchor(tmp_path: Path) -> None:
    """The standing rule is that every source carries its link. An anchor is not one."""
    _, _, entries = _convert(tmp_path)
    named = [e for e in entries if e.urls]
    assert named, "the fixture has an entry with a URL"
    for entry in named:
        cell = convert.link_cell(entry)
        assert entry.urls[0] in cell, cell
        assert not cell.startswith("[detail]"), cell
    # and an entry that names none says so, rather than showing an anchor alone
    for entry in entries:
        if not entry.urls:
            assert convert.link_cell(entry).startswith("n/a"), entry.key


def test_a_closed_verdict_moves_the_row_and_an_open_one_does_not(tmp_path: Path) -> None:
    new_sources, new_closed, entries = _convert(tmp_path)
    verdicts = {e.key: (e.verdict, e.closed) for e in entries}
    assert verdicts["short_family"] == ("FIND", False)
    assert verdicts["nerd_world"][1] and verdicts["blocked_family"][1]
    assert "short_family" in new_sources and "short_family" not in new_closed
    assert "nerd_world" in new_closed
    # the rows the closed page already had are still there, above the new section
    assert new_closed.index("earlier_triage_row") < new_closed.index(convert.CLOSED_HEADING)


def test_no_line_is_over_the_limit(tmp_path: Path) -> None:
    new_sources, new_closed, _ = _convert(tmp_path)
    for text in (new_sources, new_closed):
        assert max(len(line) for line in text.splitlines()) <= convert.LINE_LIMIT


def test_an_unknown_cell_reads_n_a_rather_than_being_invented(tmp_path: Path) -> None:
    _, _, entries = _convert(tmp_path)
    short = next(e for e in entries if e.key == "short_family")
    # the entry names no overlap figure and no coverage year, and says so
    assert short.overlap == "n/a" and short.coverage == "n/a"
    blocked = next(e for e in entries if e.key == "blocked_family")
    assert blocked.retrieval == "robots refusal"
