"""Promotion re-files an observation; it must not alter one.

The tranche is 106,604 pairs written under a MASTER source, so a field mangled here
becomes a year assignment nobody can trace back to a post. The round-trip test is the
one that matters: what the builder writes must parse back to the evidence value the
loader originally stored, or the Message-ID in the shipped corpus stops naming the
post it claims to name.
"""

import gzip
import importlib.util
import json
from collections import Counter
from pathlib import Path

from ark.sources import SOURCES

_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "build_promotion_journals", _ROOT / "scripts" / "build_promotion_journals.py"
)
promo = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(promo)


def test_group_and_message_id_split_on_the_first_space() -> None:
    line = promo.journal_line("foo.com", 1997, "alt.test usenet post <abc@x>", "https://e/1")
    assert line == {
        "domain": "foo.com",
        "year": 1997,
        "group": "alt.test",
        "message_id": "usenet post <abc@x>",
        "url": "https://e/1",
    }


def test_a_value_with_no_space_invents_no_group() -> None:
    """The parser defaults an absent group to `usenet`; guessing one here would put a
    fabricated newsgroup into the audit trail."""
    line = promo.journal_line("foo.com", 1999, "solitary", None)
    assert "group" not in line
    assert line["message_id"] == "solitary"
    assert "url" not in line


def test_every_promotion_target_exists_and_is_master_eligible() -> None:
    """The mapping is the whole safety argument: a mention may only be re-filed under a
    sibling that reads the same journal format."""
    for mention_source, ingest_key in promo.PROMOTION.items():
        assert ingest_key in SOURCES, f"{ingest_key} is not an ingest key"
        spec = SOURCES[ingest_key]
        assert spec.evidence_type != "link_target", f"{ingest_key} is still candidate-only"
        mention_spec = next(s for s in SOURCES.values() if s.source_name == mention_source)
        assert mention_spec.parse is spec.parse, (
            f"{mention_source} and {ingest_key} do not share a parser, so re-filing "
            f"would hand the loader a format it does not read"
        )


def test_link_graph_sources_are_not_promotable() -> None:
    """`ukwa_link_target` was nearly promoted. Its only relative dates the linking page,
    never the linked-to page, which is the distinction `link_target` exists to hold."""
    for never in ("ukwa_link_target", "uucp_map_mention", "page_expansion"):
        assert never not in promo.PROMOTION


def test_a_written_line_parses_back_to_the_same_evidence_value(tmp_path) -> None:
    """Round trip through the real loader, which is what proves the re-file lossless."""
    value = "comp.lang.python usenet post <3358fb02.28570944@news.alt.net>"
    path = tmp_path / "promoted.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps(promo.journal_line("brownschool.com", 1997, value, "https://e/1")))
        fh.write("\n")

    records = list(SOURCES["usenet_dated"].parse(path, Counter()))
    assert len(records) == 1
    assert records[0].raw == "brownschool.com"
    assert records[0].year == 1997
    assert records[0].evidence_value == value
