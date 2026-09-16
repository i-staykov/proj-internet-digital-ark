"""`parse_registry_items`: a fleet price leg's `{host, year, text}` items for a registry
list, filed at the name as listed, dated by the registry's own stamp in `text`.

First used for DK Hostmaster's `domains.txt` (approved 2026-09-16, #143): three 2001
captures, each opening with `20011217: 349694 subdomains of DK`, 358,529 names.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ark.sources import SOURCES, parse_registry_items


def write(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "items.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows) + "\n", encoding="utf-8")
    return p


def test_the_name_is_filed_at_the_year_its_stamp_names(tmp_path: Path) -> None:
    stats: Counter = Counter()
    rows = list(
        parse_registry_items(
            write(
                tmp_path,
                [
                    {"host": "Example.dk", "year": 2001, "text": "DK Zonen header 20010413"},
                    {"host": "other.dk", "year": 2000, "text": "DK Zonen header 20001231"},
                ],
            ),
            stats,
        )
    )
    assert [(r.raw, r.year) for r in rows] == [("example.dk", 2001), ("other.dk", 2000)]
    assert rows[0].evidence_value.startswith("20010413: ")
    assert stats["journal_lines"] == 2


def test_a_stamp_naming_another_year_is_refused_here_not_at_the_gate(tmp_path: Path) -> None:
    stats: Counter = Counter()
    rows = list(
        parse_registry_items(
            write(
                tmp_path,
                [
                    {"host": "late.dk", "year": 2001, "text": "DK Zonen header 20020105"},
                    {"host": "undated.dk", "year": 2001, "text": "no stamp"},
                    {"host": "old.dk", "year": 1995, "text": "DK Zonen header 19950101"},
                    {"year": 2001, "text": "DK Zonen header 20010101"},
                ],
            ),
            stats,
        )
    )
    assert rows == []
    assert stats["stamp_does_not_name_the_year"] == 2
    assert stats["malformed"] == 2


def test_the_danish_list_is_registered_as_a_listing_with_no_split() -> None:
    spec = SOURCES["dk_hostmaster_dk_zonen_domains_txt_wayback_2001"]
    assert spec.evidence_type == "artifact_listing"
    assert spec.parse is parse_registry_items
