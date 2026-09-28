"""The proposal screener stops a reproposed dead lead. The register is parsed from the closed
page, so a parser that silently stopped matching would report no collision, which reads as
permission; `closed-screen.md` is a closed page in the register's own shape."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLOSED = ROOT / "tests/fixtures/register/closed-screen.md"
_SPEC = importlib.util.spec_from_file_location(
    "screen", ROOT / "scripts/harness/screen_hypothesis.py"
)
screen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(screen)


def test_the_register_parses_to_one_lead_per_row_and_one_entry_per_lead(tmp_path) -> None:
    # the container heading of the older table shape is not a lead, and its header is title-case
    (legacy := tmp_path / "sources.md").write_text(
        "## Evaluated and rejected\n\n| Source | Verdict |\n|---|---|\n| Old | dead |\n"
    )
    assert [entry.name for entry in screen.closed_leads(legacy)] == ["Old"]
    register = screen.closed_leads(CLOSED)
    assert len(register) == len(screen.closed_leads(CLOSED, CLOSED)) == 6, "a lead on both pages"
    names = " | ".join(entry.name.lower() for entry in register)
    expected = ("ircache", "geocities", "edgar", "common crawl", "webbase")
    assert [name for name in expected if name not in names] == [], "missing from the register"
    assert "FTP host is dead" in register[0].verdict, "the verdict is the rest of the row"


FICHE = "municipal library card catalogue microfiche"
LOGS = ("IRCache / NLANR proxy traces", "domain squatted, FTP dead")
EDGAR = ("SEC EDGAR filings 1996-2001", "4 net-new pairs from 150 filings")
DISCS = ("Shareware discs beyond Tucows", "archive.org cannot list inside an ISO; cdbbsarchive")
NATIONAL = ("Some national web archive collection of historical data", "out of window")
OCLC = ("OCLC Web Characterization Project", "aggregate statistics only")
PROSE = ("Some corpus", "0.4 net-new pairs per reachable item, as the award galleries failed")
# (proposal, a closed row alone on its register, whether it collides)
PROPOSALS = {
    "a-reproposed-dead-lead": ("NLANR IRCache proxy trace logs", LOGS, True),
    "the-real-name-under-a-shared-window": ("SEC EDGAR quarterly filings", EDGAR, True),
    "the-verdict-body-catches-what-the-name-misses": ("Bookshelf ISO in cdbbsarchive", DISCS, True),
    "a-genuinely-different-proposal": (FICHE, LOGS, False),
    # without a stop list, `archive` matches most of the register and the reader ignores it
    "common-words-alone": ("a web archive of historical data", NATIONAL, False),
    "a-shared-year-range-says-when-not-what": ("INET proceedings 1996-2001", EDGAR, False),
    "a-generic-noun": ("Apache Software Foundation project releases", OCLC, False),
    "unrelated-prose-in-a-verdict": (FICHE, PROSE, False),
}


@pytest.mark.parametrize(("proposal", "row", "collides"), PROPOSALS.values(), ids=PROPOSALS)
def test_a_reproposed_dead_lead_collides_and_common_words_do_not(proposal, row, collides):
    hits = screen.collisions(proposal, [screen.Closed(*row, 1)])
    assert [entry.name for _, entry in hits] == ([row[0]] if collides else [])


def test_closed_on_says_whether_a_lead_may_be_reprobed_and_what_was_measured() -> None:
    """A dead host might be alive again, a measurement does not improve by waiting, and an
    entry closing one route on reach and another on yield says both."""
    reach = "the text files return HTTP 401, and the HathiTrust route would not have paid"
    both = screen.Closed("Printed directories", reach + ": measured at 15.7 net-new pairs", 3)
    dead = screen.Closed("Some archive", "the host does not resolve; no route in", 1)
    priced = screen.Closed("Some corpus", "0.4 net-new pairs per reachable item", 2)
    got = [(entry.closed_on, entry.also_measured) for entry in (dead, priced, both)]
    assert got == [("availability", False), ("measurement", True), ("availability", True)]
