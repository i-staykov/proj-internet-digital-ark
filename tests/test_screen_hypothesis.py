"""The proposal screener: does it actually stop a reproposed dead lead?

Loaded by path, like the other script tests: `scripts/` is not a package.

The register is parsed from `docs/sources.md` rather than copied, so two of these
tests run against the real document. That is deliberate: a parser that silently
stops matching the file it reads would leave the tool reporting "no collision"
for everything, which is the worst possible failure here because it reads as
permission.
"""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "screen_hypothesis",
    Path(__file__).resolve().parents[1] / "scripts" / "screen_hypothesis.py",
)
screen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(screen)


def test_the_real_register_parses_to_a_plausible_number_of_leads() -> None:
    """`docs/discovery.md` says roughly fifty families are closed. A parser that
    returns a handful has stopped matching the document."""
    register = screen.closed_leads()
    assert len(register) >= 40
    names = " | ".join(entry.name.lower() for entry in register)
    for expected in ("ircache", "geocities", "edgar", "common crawl", "webbase"):
        assert expected in names, f"{expected} missing from the parsed register"


def test_the_container_heading_is_not_itself_a_lead() -> None:
    register = screen.closed_leads()
    assert not any(e.name.lower().startswith("evaluated and rejected") for e in register)


def test_one_lead_gives_one_entry() -> None:
    """NYPW carries both a `## ` heading and an inline verdict line."""
    register = screen.closed_leads()
    assert len({e.name for e in register}) == len(register)


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
    """Found by using the tool on ten fresh hypotheses.

    Every source in this project is about 1996-2001, so the window is in half the
    register's entry names. `1996-2001` occurs in exactly one of them, which made
    the single-rare-token rule fire, and "INET conference proceedings 1996-2001"
    was reported as colliding with "SEC EDGAR filings 1996-2001". A date says when,
    never what.
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


def test_every_dating_class_carries_its_corroboration_rule() -> None:
    """The classes are the whole point of gate 2: `self` must warn that widening
    is unsafe, `typed` must name the split, `undated` must say seed-only."""
    assert "NOT safe" in " ".join(screen.DATING["self"][1])
    assert "corroboration split" in " ".join(screen.DATING["typed"][1])
    assert "Seed-only" in " ".join(screen.DATING["undated"][1])
