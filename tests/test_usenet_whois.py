"""The pasted-whois route: binding a creation line to the right name, and the split.

The test that matters is `test_escaped_copy_cannot_steal_the_previous_name`. It
is the regression for a measured defect: a message that quotes the same whois
block three times, plain, `>`-quoted and HTML-escaped, made an earlier pass bind
`openssl.org`'s creation date to `engelschall.com`, because the date pattern
matched inside the escaped copy and the name pattern did not.
"""

import gzip
import importlib.util
import json
from collections import Counter
from pathlib import Path

from ark.journal import journal_writer, write_journal_line
from ark.sources import SOURCES, _parse_usenet_whois_journal

_SPEC = importlib.util.spec_from_file_location(
    "collect_usenet_whois",
    Path(__file__).resolve().parent.parent / "scripts/sources/usenet/collect_usenet_whois.py",
)
assert _SPEC and _SPEC.loader
collect_usenet_whois = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(collect_usenet_whois)

BLOCK = """
   Registrant:
   The OpenSSL Project

      Domain Name: OPENSSL.ORG

      Administrative Contact:
         Someone  someone@openssl.org
      Technical Contact:
         Someone  someone@openssl.org

      Record last updated on 12-Jan-2001.
      Record expires on 18-Dec-2002.
      Record created on 19-Dec-1998.

      Domain servers in listed order:
      NS1.EXAMPLE.NET
      NS2.EXAMPLE.NET

      Domain Name: ENGELSCHALL.COM

      Administrative Contact:
         Someone  rse@engelschall.com

      Record created on 30-Jun-1996.
"""


def _escaped(text: str) -> str:
    """The same block as a mail client rewrote it: leading runs become `&nbsp;`."""
    out = []
    for line in text.split("\n"):
        stripped = line.lstrip(" ")
        pad = "&nbsp;" * (len(line) - len(stripped))
        out.append(pad + stripped)
    return "\n".join(out)


def test_creation_lines_bind_to_their_own_name() -> None:
    found = collect_usenet_whois.creations_in(BLOCK)
    assert {(d, y) for d, _c, y, _b in found} == {
        ("openssl.org", 1998),
        ("engelschall.com", 1996),
    }


def test_escaped_copy_cannot_steal_the_previous_name() -> None:
    # plain copy, then the escaped one, exactly as the offending message was laid out
    found = collect_usenet_whois.creations_in(BLOCK + _escaped(BLOCK))
    assert {(d, y) for d, _c, y, _b in found} == {
        ("openssl.org", 1998),
        ("engelschall.com", 1996),
    }
    # and specifically: no 1998 date on the name that follows it
    assert ("engelschall.com", 1998) not in {(d, y) for d, _c, y, _b in found}


def test_a_creation_line_far_below_its_name_is_dropped() -> None:
    filler = "\n".join(f"   line {i}" for i in range(collect_usenet_whois.MAX_BACK + 5))
    text = "      Domain Name: EXAMPLE.COM\n" + filler + "\n      Record created on 04-Jul-1997.\n"
    assert collect_usenet_whois.creations_in(text) == []


def test_out_of_window_and_unregistrable_names_are_refused() -> None:
    text = (
        "      Domain Name: EXAMPLE.COM\n      Record created on 04-Jul-2004.\n"
        "      Domain Name: DOMAIN.BILLING\n      Record created on 04-Jul-1997.\n"
    )
    assert collect_usenet_whois.creations_in(text) == []


def test_nominet_puts_the_name_on_the_next_line() -> None:
    text = "    Domain Name:\n        example.co.uk\n\n    Registered on: 01-Feb-1999\n"
    assert [(d, y) for d, _c, y, _b in collect_usenet_whois.creations_in(text)] == [
        ("example.co.uk", 1999)
    ]


def _journal(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "usenet_whois_dated.jsonl.gz"
    with journal_writer(path) as fh:
        for row in rows:
            write_journal_line(fh, row)
    return path


def test_evidence_value_leads_with_the_registry_stamp(tmp_path: Path) -> None:
    # `ark check` reads the FIRST four-digit run back out of the value, so a group
    # name carrying a year must not be what it finds.
    path = _journal(
        tmp_path,
        [
            {
                "domain": "example.com",
                "year": 1998,
                "created": "1998-12-19",
                "group": "microsoft.public.win2000.dns",
                "message_id": "<abc@example>",
                "url": "https://archive.org/details/usenet-microsoft",
            }
        ],
    )
    stats: Counter = Counter()
    records = list(_parse_usenet_whois_journal(path, stats))
    assert len(records) == 1
    assert records[0].evidence_value.startswith("record created 1998-12-19 ")
    assert records[0].year == 1998


def test_a_stamp_disagreeing_with_the_filed_year_is_refused(tmp_path: Path) -> None:
    path = _journal(
        tmp_path,
        [
            {"domain": "example.com", "year": 1998, "created": "1997-12-19", "group": "g"},
            {"domain": "other.com", "year": 2004, "created": "2004-01-01", "group": "g"},
        ],
    )
    stats: Counter = Counter()
    assert list(_parse_usenet_whois_journal(path, stats)) == []
    assert stats["created_year_mismatch"] == 1
    assert stats["malformed"] == 1


def test_the_two_specs_split_the_same_journal_by_corroboration() -> None:
    dated, candidates = SOURCES["usenet_whois_dated"], SOURCES["usenet_whois_candidates"]
    assert dated.evidence_type == "whois_creation"
    assert dated.is_candidate_only is False
    assert candidates.evidence_type == "link_target"
    assert candidates.is_candidate_only is True
    assert dated.parse is candidates.parse is _parse_usenet_whois_journal
    assert dated.source_name != candidates.source_name


def test_the_split_writes_both_halves(tmp_path: Path) -> None:
    # the split's own contract: every input row lands in exactly one output
    rows = [
        {"domain": "held.com", "year": 1998, "created": "1998-01-01", "group": "g"},
        {"domain": "novel.com", "year": 1999, "created": "1999-01-01", "group": "g"},
    ]
    path = tmp_path / "usenet_whois_probe.jsonl.gz"
    with journal_writer(path) as fh:
        for row in rows:
            write_journal_line(fh, row)
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        assert [json.loads(line)["domain"] for line in fh] == ["held.com", "novel.com"]
