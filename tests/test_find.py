"""`just find`: the only route into the four register pages, so it must be honest.

Three things are pinned here, because each is a way the tool could quietly stop
being a replacement for reading the file: a term that lives only in a `## Detail`
block is still found and says where it is, `--detail` prints one entry and only
that one, and nothing prints over the line cap without `--all`.

The fourth is that no page is ever read whole. That is the whole point of the
recipe, and it is asserted rather than reviewed: the module's `open` is replaced
with a handle that raises if anything calls `read` or `readlines`.

Loaded by path, like the other script tests: `scripts/` is not a package.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "round_find", Path(__file__).resolve().parents[1] / "scripts/round/find.py"
)
find = importlib.util.module_from_spec(_SPEC)
sys.modules["round_find"] = find
_SPEC.loader.exec_module(find)

OPEN_COLUMNS = (
    "| source | version or date | coverage period | retrieval method | what dates one item "
    "| baseline overlap | net-new EE (date) | quality issues | effort | verdict | link |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|\n"
)

SOURCES = (
    "# Sources\n\n"
    "Preamble that names no family.\n\n"
    "## `alpha_family`: the alpha listing\n\n"
    "- what dates one item: the transfer stamp at the head of each member.\n\n"
    "## Evaluated and rejected\n\n"
    + OPEN_COLUMNS
    + "| alpha_family | 2026-09-01 | 1997-1999 | ftp listing | the transfer stamp | 50.4% held "
    "| 2189.0 EE (2026-09-01) | one arm sampled | 12 hours | FIND "
    "| <https://example.org/alpha> [detail](#alpha-family) |\n"
    "| beta_family | 2026-09-02 | 2001 | cdx query | the capture stamp | 84.8% held "
    "| 10736.0 EE (2026-09-02) | crawl-fed, so novelty is low | 4 hours | PRICED "
    "| <https://example.org/beta> [detail](#beta-family) |\n"
    "\n"
    "## Detail\n\n"
    "### alpha-family\n\n"
    "**alpha_family (2026-09-01)**\n\n"
    "**FIND at 2189.0 EE.** The zone members were read whole, and the quokka clause the row\n"
    "could not carry is here: 13 editions, none of them sampled.\n\n"
    "### beta-family\n\n"
    "**beta_family (2026-09-02)**\n\n"
    "**PRICED at 10736.0 EE.** A wombat is not a quokka and this block must not print with it.\n"
)

CLOSED = (
    "# Closed sources\n\n"
    "## Closed families, converted from the register\n\n"
    "| source | date | measured | reason | link |\n"
    "|---|---|---|---|---|\n"
    "| gamma_family | 2026-08-30 | 0 EE | Nothing was fetched: robots refusal. | |\n"
    "\n"
    "## Detail\n\n"
    "### gamma-family\n\n"
    "**gamma_family (2026-08-30)**\n\n"
    "**BLOCKED on robots.** The host names ClaudeBot at line 51 of 61.\n\n"
    "### long-family\n\n" + "".join(f"line {number} of a long entry.\n" for number in range(60))
)

APPROVED = (
    "# Approved sources\n\n"
    "### alpha_family / artifact_listing\n\n"
    "- measured: 2189.0 net-new post-split EE over 3,462 pairs\n"
    "- what dates one item: the transfer stamp\n\n"
    "Decision: master\n"
    "Decided by Ivo, 2026-09-01.\n\n"
    "### delta_family / artifact_listing\n\n"
    "- what dates one item: the same stamp, read from the other endpoint\n\n"
    "Decision: candidate-only\n"
)

PENDING = (
    "# Hypotheses pending\n\n"
    "### delta_family / artifact_listing\n\n"
    "- measured: 1328.31 net-new post-split EE over 1,998 pairs\n"
    "- what dates one item: the quarter the report covers\n\n"
    "Decision: pending\n\n"
    "| # | Source | What dates an item | Type | Net-new pairs | EE | Evidence | Decision |\n"
    "|--:|---|---|---|---|---|---|---|\n"
    + "".join(
        f"| {number} | bulk_family_{number} | a stamp | artifact_listing | 10 | 6.3 "
        "| MEASURED | pending |\n"
        for number in range(60)
    )
)


@pytest.fixture
def register(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "sources.md").write_text(SOURCES, encoding="utf-8")
    (docs / "sources-closed.md").write_text(CLOSED, encoding="utf-8")
    (docs / "approved-sources-list.md").write_text(APPROVED, encoding="utf-8")
    (docs / "hypotheses-pending.md").write_text(PENDING, encoding="utf-8")
    return tmp_path


def run(register, *args, width="200"):
    return find.main([*args, "--root", str(register), "--width", width])


def test_a_row_hit_names_the_page_key_verdict_and_ee(register, capsys):
    assert run(register, "ftp listing") == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("sources:")
    for field in ("alpha_family", "FIND", "2189.0 EE"):
        assert field in lines[0]
    assert "row" in lines[0]
    # The matched cell, not the row: the link and the overlap cells stay out of it.
    assert "example.org" not in lines[0]
    assert "50.4%" not in lines[0]


def test_the_closed_page_rows_read_as_closed(register, capsys):
    assert run(register, "robots refusal") == 0
    line = capsys.readouterr().out.splitlines()[0]
    assert line.startswith("closed:")
    assert "gamma_family" in line
    assert " closed " in line  # the verdict cell the five columns do not carry


def test_a_section_hit_inherits_its_decision_line(register, capsys):
    assert run(register, "the quarter the report covers") == 0
    line = capsys.readouterr().out.splitlines()[0]
    assert line.startswith("pending:")
    assert "delta_family" in line
    assert "pending" in line
    assert "1328.31 EE" in line


def test_a_term_only_in_a_detail_block_is_found_and_says_so(register, capsys):
    assert run(register, "quokka") == 0
    out = capsys.readouterr().out.splitlines()
    # Two hits, both in detail blocks, and neither is a row: the rows never say it.
    assert len(out) == 3
    assert all("detail" in line for line in out[:2])
    assert "alpha-family" in out[0]
    assert "beta-family" in out[1]
    assert "--detail" in out[2]


def test_detail_prints_exactly_that_entry(register, capsys):
    assert run(register, "alpha-family", "--detail") == 0
    out = capsys.readouterr().out
    at = SOURCES.splitlines().index("### alpha-family") + 1
    assert out.splitlines()[0] == f"sources:{at} ### alpha-family"
    assert "13 editions, none of them sampled." in out
    # The next entry starts four lines later and must not come with it.
    assert "wombat" not in out
    assert "beta-family" not in out


def test_detail_prefers_the_block_over_the_section_of_the_same_name(register, capsys):
    # A row is a projection of its entry, so the entry is the answer to --detail.
    assert run(register, "alpha_family", "--detail") == 0
    assert "13 editions, none of them sampled." in capsys.readouterr().out


def test_detail_matches_an_underscored_key_against_a_slugged_anchor(register, capsys):
    assert run(register, "gamma_family", "--detail") == 0
    out = capsys.readouterr().out
    assert "### gamma-family" in out
    assert "line 51 of 61" in out


def test_detail_refuses_to_guess_between_two_entries(register, capsys):
    # `delta_family` is a section in two pages and a detail block in neither, so
    # which one is wanted is the caller's to say.
    assert run(register, "delta_family", "--detail") == 2
    err = capsys.readouterr().err.splitlines()
    assert len(err) == 1
    assert "approved#delta_family" in err[0] and "pending#delta_family" in err[0]
    assert run(register, "pending#delta_family", "--detail") == 0
    assert "Decision: pending" in capsys.readouterr().out


def test_the_cap_holds_and_says_what_it_suppressed(register, capsys):
    assert run(register, "bulk_family") == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == find.CAP
    assert "21 more hits suppressed" in out[-1]
    assert run(register, "bulk_family", "--all") == 0
    assert len(capsys.readouterr().out.splitlines()) == 60


def test_the_cap_holds_in_detail_too(register, capsys):
    assert run(register, "long-family", "--detail") == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == find.CAP
    assert "more lines of this entry suppressed" in out[-1]
    assert run(register, "long-family", "--detail", "--all") == 0
    assert len(capsys.readouterr().out.splitlines()) == 62


def test_a_family_narrows_to_one_key(register, capsys):
    assert run(register, "the capture stamp", "beta_family") == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 1 and "beta_family" in out[0]
    assert run(register, "the transfer stamp", "--family", "beta_family") == 1
    assert "under family 'beta_family'" in capsys.readouterr().err


def test_nothing_matched_exits_1_with_one_line(register, capsys):
    assert run(register, "platypus") == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1


def test_a_missing_register_is_a_failed_search_not_an_empty_one(tmp_path, capsys):
    assert find.main(["alpha", "--root", str(tmp_path)]) == 2
    assert "the search failed" in capsys.readouterr().err


def test_no_line_is_wider_than_asked(register, capsys):
    assert run(register, "stamp", width="80") == 0
    assert all(len(line) <= 80 for line in capsys.readouterr().out.splitlines())


def test_no_page_is_read_whole(register, monkeypatch, capsys):
    """The recipe exists so the register never lands in a terminal or in memory."""
    opened = []
    real_open = open

    class Watched:
        def __init__(self, path, **kwargs):
            self.handle = real_open(path, **kwargs)
            self.lines = 0

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.handle.close()
            return False

        def __iter__(self):
            for line in self.handle:
                self.lines += 1
                yield line

        def read(self, *args):
            raise AssertionError("read() loads the page whole")

        def readlines(self, *args):
            raise AssertionError("readlines() loads the page whole")

    def watched(path, **kwargs):
        handle = Watched(path, **kwargs)
        opened.append(handle)
        return handle

    monkeypatch.setattr(find, "open", watched, raising=False)
    assert run(register, "stamp") == 0
    assert run(register, "alpha-family", "--detail") == 0
    capsys.readouterr()
    # Four pages for the search, four to find the entry, one to print its block.
    assert len(opened) == 9
    assert all(handle.lines for handle in opened)


def test_a_column_name_is_found_rather_than_reported_absent(register, capsys):
    """A header row is searchable text: exit 1 must mean absent, never skipped.

    Skipping header rows outright made a search for one of the register's own column
    names answer "not in the register", which is the one wrong answer this command
    cannot give, since it is the only route into the pages.
    """
    assert run(register, "baseline overlap") == 0
    out = capsys.readouterr().out
    assert "header" in out
    assert "no hit" not in out
