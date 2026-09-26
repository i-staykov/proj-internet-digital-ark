"""The proposal screener: does it actually stop a reproposed dead lead?

The register is parsed from the closed page rather than copied, so a parser that silently
stopped matching would report "no collision" for everything, and that reads as permission.
`closed-screen.md` is a closed page in the register's own shape.
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOSED = ROOT / "tests/fixtures/register/closed-screen.md"
_SPEC = importlib.util.spec_from_file_location(
    "screen_hypothesis", ROOT / "scripts/harness/screen_hypothesis.py"
)
screen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(screen)


def test_the_register_parses_to_one_lead_per_row() -> None:
    register = screen.closed_leads(CLOSED)
    assert len(register) == 6
    names = " | ".join(entry.name.lower() for entry in register)
    for expected in ("ircache", "geocities", "edgar", "common crawl", "webbase"):
        assert expected in names, f"{expected} missing from the parsed register"


def test_one_lead_gives_one_entry() -> None:
    """A source named on both pages is one lead, not two."""
    assert len(screen.closed_leads(CLOSED, CLOSED)) == 6


def test_a_reproposed_dead_lead_collides(tmp_path: Path) -> None:
    doc = tmp_path / "sources.md"
    doc.write_text(
        "## Evaluated and rejected\n\n"
        "| Source | Verdict |\n"
        "|---|---|\n"
        "| **IRCache / NLANR proxy traces** (2026-08-06) | domain squatted, FTP dead |\n"
        "| Common Crawl | earliest collection is 2008-05 |\n"
    )
    register = screen.closed_leads(doc)
    assert len(register) == 2
    hits = screen.collisions("NLANR IRCache proxy trace logs", register)
    assert hits and "IRCache" in hits[0][1].name
    assert "FTP dead" in hits[0][1].verdict


def test_a_genuinely_different_proposal_does_not_collide(tmp_path: Path) -> None:
    doc = tmp_path / "sources.md"
    doc.write_text(
        "## Evaluated and rejected\n\n"
        "| Source | Verdict |\n"
        "|---|---|\n"
        "| **IRCache / NLANR proxy traces** (2026-08-06) | domain squatted |\n"
    )
    register = screen.closed_leads(doc)
    assert screen.collisions("municipal library card catalogue microfiche", register) == []


def test_common_words_alone_do_not_collide(tmp_path: Path) -> None:
    """Without a stop list, `archive` matches most of the register and every
    proposal is reported as a collision, which trains the reader to ignore it."""
    doc = tmp_path / "sources.md"
    doc.write_text(
        "## Evaluated and rejected\n\n"
        "| Source | Verdict |\n"
        "|---|---|\n"
        "| Some national web archive collection of historical data | out of window |\n"
    )
    register = screen.closed_leads(doc)
    assert screen.collisions("a web archive of historical data", register) == []


def test_a_shared_year_range_is_not_a_collision(tmp_path: Path) -> None:
    """Every source here is about 1996-2001, so the window is in half the register's entry
    names and a single-rare-token rule reports "INET conference proceedings 1996-2001" as
    colliding with "SEC EDGAR filings 1996-2001". A date says when, never what.
    """
    doc = tmp_path / "sources.md"
    doc.write_text(
        "## Evaluated and rejected\n\n"
        "| Source | Verdict |\n"
        "|---|---|\n"
        "| SEC EDGAR filings 1996-2001 (2026-08-08) | 4 net-new pairs from 150 filings |\n"
    )
    register = screen.closed_leads(doc)
    assert screen.collisions("INET conference proceedings 1996-2001", register) == []
    # the real name still collides, so the fix did not simply disable the check
    assert screen.collisions("SEC EDGAR quarterly filings", register)


def test_a_generic_noun_is_not_a_collision(tmp_path: Path) -> None:
    doc = tmp_path / "sources.md"
    doc.write_text(
        "## Evaluated and rejected\n\n"
        "| Source | Verdict |\n"
        "|---|---|\n"
        "| OCLC Web Characterization Project | aggregate statistics only |\n"
    )
    register = screen.closed_leads(doc)
    assert screen.collisions("Apache Software Foundation project releases", register) == []


def test_closure_reason_separates_reprobeable_leads_from_finished_ones() -> None:
    """A measurement does not improve by waiting; a dead host might be alive. The register's
    Australian Web Archive entry is the case: one endpoint served an anti-bot challenge, a
    second host answered normally, and the family was nearly closed on the first result.
    """
    dead = screen.Closed("Some archive", "the host does not resolve; no route in", 1)
    priced = screen.Closed("Some corpus", "0.4 net-new pairs per reachable item", 2)
    assert dead.closed_on == "availability"
    assert priced.closed_on == "measurement"


def test_the_register_has_both_classes_and_availability_is_the_minority() -> None:
    """If everything classified one way the distinction would be decorative."""
    register = screen.closed_leads(CLOSED)
    assert sum(entry.closed_on == "availability" for entry in register) == 2


def test_an_entry_can_close_one_route_on_reach_and_another_on_yield() -> None:
    """`closed_on` returns one value and stays biased toward `availability`, which is right,
    but an entry can close two routes: reporting only the bias sends a reader to re-probe a
    family whose second route was already measured, reproducing a verdict.
    """
    both = screen.Closed(
        "Printed directories",
        "the text files return HTTP 401, and the HathiTrust route would not have paid: "
        "measured at 15.7 net-new pairs per volume",
        1,
    )
    reach_only = screen.Closed("Some archive", "the host does not resolve; no route in", 2)
    assert both.closed_on == "availability" and both.also_measured
    assert reach_only.closed_on == "availability" and not reach_only.also_measured


def test_the_register_flags_the_entry_that_caused_this() -> None:
    """The printed-directory row closes one route on reach and one on a measurement."""
    register = screen.closed_leads(CLOSED)
    printed = [e for e in register if "Printed Internet directory books" in e.name]
    assert printed, "the printed-directory entry has been renamed or removed"
    assert printed[0].closed_on == "availability"
    assert printed[0].also_measured


def test_every_dating_class_carries_its_corroboration_rule() -> None:
    """The classes are the whole point of gate 2: `self` must warn that widening
    is unsafe, `typed` must name the split, `undated` must say seed-only."""
    assert "NOT safe" in " ".join(screen.DATING["self"][1])
    assert "corroboration split" in " ".join(screen.DATING["typed"][1])
    assert "Seed-only" in " ".join(screen.DATING["undated"][1])


def test_the_verdict_body_catches_a_collision_the_name_misses(tmp_path: Path) -> None:
    """A proposal for the 1996 Microsoft Bookshelf Internet Directory did not collide with the
    entry closing the CD-ROM family that contains it, because `cdbbsarchive` and `ISO`
    appear in the verdict and not in the entry name.
    """
    doc = tmp_path / "sources.md"
    doc.write_text(
        "## Evaluated and rejected\n\n"
        "| Source | Verdict |\n"
        "|---|---|\n"
        "| Shareware discs beyond Tucows (2026-08-06) | archive.org cannot list inside "
        "an ISO, and cdbbsarchive holds 3,578 items with no date metadata |\n"
    )
    register = screen.closed_leads(doc)
    # the entry name shares nothing discriminating with the proposal
    assert not (screen._tokens("Microsoft Bookshelf Internet Directory") & register[0].tokens())
    # the body does, and that is enough
    hits = screen.collisions("Microsoft Bookshelf Internet Directory ISO in cdbbsarchive", register)
    assert hits, "a body-only collision must still fire"


def test_the_body_match_does_not_fire_on_unrelated_prose(tmp_path: Path) -> None:
    """A verdict is a paragraph, so a low floor could match anything."""
    doc = tmp_path / "sources.md"
    doc.write_text(
        "## Evaluated and rejected\n\n"
        "| Source | Verdict |\n"
        "|---|---|\n"
        "| Some corpus (2026-08-06) | measured at 0.4 net-new pairs per reachable item, "
        "which is the same failure mode as the award galleries |\n"
    )
    register = screen.closed_leads(doc)
    assert screen.collisions("municipal library card catalogue microfiche", register) == []
