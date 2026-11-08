"""The parsers `just bank` folds (`src/ark/sources.py`: `cdx_snapshot`, the `usenet_dated` and
`usenet_candidates` journal), the specs' wall every `ark ingest` reads, and the RIPE NCC promise
the decided RIPE blocks cite: no parser of theirs emits personal data."""

import gzip
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from ark import sources as src
from ark.evidence_types import WEB_METHODS
from ark.sources import SOURCES
from ark.stats import PROVENANCE_LINEAGE


def _parse(parser, tmp_path: Path, name: str, text: str):
    """Write `text` to `name`, gzipped when it ends `.gz`, and return the records and stats."""
    path = tmp_path / name
    if name.endswith(".gz"):
        path.write_bytes(gzip.compress(text.encode("utf-8")))
    else:
        path.write_text(text, encoding="utf-8")
    stats: Counter = Counter()
    return list(parser(path, stats)), stats


def _lines(rows: list[str]) -> str:
    return "\n".join(rows) + "\n"


def _jsonl(rows: list[dict]) -> str:
    return "".join(json.dumps(r) + "\n" for r in rows)


# a lane of mentions or of outbound links is candidate-only, and every other lane may date a year
CANDIDATE_KEY = re.compile(r"_(candidates|mentions|links|link_target)$")


def test_a_spec_is_candidate_only_as_its_key_says_and_files_under_a_source_of_its_own() -> None:
    """A split's halves and one parser's two archives share a parser, never a source; the geoindex
    reads as web evidence, and the lanes of one archive or spool never corroborate."""
    assert SOURCES["arquivo_roteiro"].parse is SOURCES["arquivo_ia"].parse
    assert SOURCES["usenet_whois_candidates"].parse is SOURCES["usenet_whois_dated"].parse
    assert all(s.is_candidate_only == bool(CANDIDATE_KEY.search(k)) for k, s in SOURCES.items())
    assert len({spec.source_name for spec in SOURCES.values()}) == len(SOURCES)
    assert SOURCES["ukwa_geoindex"].acquisition_method in WEB_METHODS
    ia = ("ia_cdx", "poland_pl_extract_hostnames", "usfedgov_extract_hostnames")
    spool = ("usenet_announce", "usenet_header_fqdn_hostnames", "usenet_body_url_hostnames")
    assert [len({PROVENANCE_LINEAGE[name] for name in lanes}) for lanes in (ia, spool)] == [1, 1]


# fmt: off
CDX_SNAPSHOT = [  # (domain, status, years, what else the row keeps)
    ("hit.com", 200, [1997], {}), ("none.com", 200, [], {}), ("err.com", 503, [], {}),
    ("out.com", 200, [2005], {}), ("big.com", 200, [1998], {"truncated": True}),
    ("conv.com", 200, [1998], {"stamps": {"1998": "19981205115848"}}),
    ("Host.com", 200, [1997, 1999],
     {"hosts": {"www.host.com": "19970101000000", "host.com": "19990301000000"}}),
    ("bad.com", 200, [2000], {"stamps": {"2000": "2000"}}),
    ("off.com", 200, [2001], {"stamps": {"2001": "19991231"}}),
]
# fmt: on


def test_cdx_snapshot_yields_a_record_per_returned_year_naming_its_capture(tmp_path) -> None:
    """One record per year returned, no inference of adjacent years; a per-year stamp or the
    domain's own `hosts` entry names the capture, and nothing else does."""
    rows = [{"domain": d, "status": s, "years": y} | kept for d, s, y, kept in CDX_SNAPSHOT]
    records, stats = _parse(src.parse_cdx_snapshot, tmp_path, "cdx_1.jsonl", _jsonl(rows))
    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("hit.com", 1997, "cdx capture 1997"),
        ("big.com", 1998, "cdx capture 1998"),
        ("conv.com", 1998, "cdx capture 19981205115848 conv.com"),
        ("Host.com", 1997, "cdx capture 1997"),
        ("Host.com", 1999, "cdx capture 19990301000000 host.com"),
        ("bad.com", 2000, "cdx capture 2000"),
        ("off.com", 2001, "cdx capture 2001"),
    ]
    urls = [r.evidence_url.removeprefix("https://web.archive.org/web/") for r in records]
    assert urls[1:5] == [
        "1998/big.com",
        "19981205115848/http://conv.com/",
        "1997/Host.com",
        "19990301000000/http://host.com/",
    ]
    assert (stats["journal_lines"], stats["query_failed"], stats["exact_capture"]) == (9, 1, 2)
    assert (stats["no_capture_in_window"], stats["truncated_response"]) == (2, 1)


def test_a_usenet_journal_line_names_its_post_by_group_and_message_id(tmp_path) -> None:
    """An absent group is `usenet`, never guessed; a line out of the window or unreadable is
    counted."""
    assert SOURCES["usenet_dated"].parse is SOURCES["usenet_candidates"].parse
    rows = [{"domain": "a.com", "year": 1997, "group": "comp.lang.python", "message_id": "<a@b>"}]
    rows += [{"domain": "b.com", "year": 1999, "message_id": "<c@d>", "url": "https://e/1"}]
    rows += [{"domain": "late.com", "year": 2004}, {"year": 1998}]
    text = _jsonl(rows) + "{not json\n"
    records, stats = _parse(SOURCES["usenet_dated"].parse, tmp_path, "usenet_dated.jsonl.gz", text)
    assert [(r.raw, r.year, r.evidence_value, r.evidence_url) for r in records] == [
        ("a.com", 1997, "comp.lang.python <a@b>", "https://archive.org/details/usenet-comp"),
        ("b.com", 1999, "usenet <c@d>", "https://e/1"),
    ]
    assert (stats["journal_lines"], stats["malformed"], stats["unparseable_line"]) == (5, 2, 1)


# The RIPE NCC permission: derive (domain, year) pairs and publish no personal data. Contact
# details sit inline in the domain objects, so every leak case fails on a widened pattern.
# fmt: off
RIPE_SNAPSHOT = _lines([
    "#", "# 990804 00:07:01", "#", "# Restricted rights.", "",
    "*dn: OULU.FI", "*de: Oulu University", "*ac: KR101", "*ch: lk-kr@finou.oulu.fi 19910916",
    "*so: RIPE", "", "*dn: TuKKK.FI", "*de: Rehtorinpellonkatu 3, SF-20500 TURKU, Finland",
    "*ac: +358 21 6383105", "*ac: mniemi@abo.fi", "*tc: hostmaster@utu.fi", "*so: RIPE", "",
    "*dn: 231.130.IN-ADDR.ARPA", "*de: reverse zone", "*so: RIPE", "",
    "*in: 193.166.0.0 - 193.166.255.255", "*na: FUNET", "*ch: ripe-dbm@ripe.net 19990711"])
RIPE_CHANGED = _lines([
    "#", "# 990804 00:07:01", "#", "", "*dn: OULU.FI", "*de: Oulu University",
    "*ch: lk-kr@finou.oulu.fi 19910916", "*ch: dfk@cwi.nl 19970930",
    "*ch: ripe-dbm@ripe.net 19990711", "*so: RIPE", "", "*dn: TuKKK.FI",
    "*ch: mniemi@abo.fi 19980825", "*ch: mniemi@abo.fi 19981103", "*so: RIPE", "",
    "*dn: 231.130.IN-ADDR.ARPA", "*ch: hostmaster@example.net 19980101", "*so: RIPE"])
RIPE_SPLIT = _lines([
    "#", "#       Restricted rights.", "#", "", "domain:       hasselblad.gm",
    "descr:        Victor Hasselblad AB", "nserver:      ns.domain.se",
    "changed:      ovema@a.sol.no 19971128", "source:       RIPE", "", "domain:       example.bg",
    "changed:      hostmaster@example.bg 20001114", "changed:      hostmaster@example.bg 20010302",
    "changed:      hostmaster@example.bg 20030506", "source:       RIPE", "",
    "domain:       200.193.193.in-addr.arpa", "changed:      mx@lucky.net 20010716",
    "source:       RIPE"])
RIPE_LEAKS = {  # (parser, text, never emitted, pairs emitted, stats)
    # the snapshot's header stamp dates every domain object
    "snapshot": (src.parse_ripe_dbase_1999, RIPE_SNAPSHOT,
                 "@ +358 Rehtorinpellonkatu TURKU abo.fi utu.fi ripe-dbm",
                 [("OULU.FI", 1999), ("TuKKK.FI", 1999)],
                 {"header_year": 1999, "reverse_zone_skipped": 1}),
    # `changed:` reaches the years the snapshot cannot: 1991 is before the window, and the
    # second 1998 line on TuKKK adds nothing
    "changed": (src.parse_ripe_dbase_changed, RIPE_CHANGED, "@ finou cwi.nl ripe-dbm abo.fi mniemi",
                [("OULU.FI", 1997), ("OULU.FI", 1999), ("TuKKK.FI", 1998)],
                {"changed_out_of_window": 1, "same_year_repeat": 1, "reverse_zone_skipped": 1}),
    # the split edition's long keys reach 2000 and 2001; 2003 is after the window
    "split": (src.parse_ripe_dbase_split_2004, RIPE_SPLIT, "@ ovema a.sol.no lucky.net hostmaster",
              [("example.bg", 2000), ("example.bg", 2001), ("hasselblad.gm", 1997)],
              {"changed_out_of_window": 1, "reverse_zone_skipped": 1}),
}


@pytest.mark.parametrize(("parser", "text", "forbidden", "pairs", "counted"),
                         list(RIPE_LEAKS.values()), ids=list(RIPE_LEAKS))
# fmt: on
def test_ripe_emits_no_personal_data(tmp_path: Path, parser, text, forbidden, pairs, counted):
    """Every emitted value is a bare hostname and a date: no address, phone or contact line."""
    records, stats = _parse(parser, tmp_path, "ripe.db", text)
    emitted = " ".join(r.raw for r in records) + " ".join(r.evidence_value for r in records)
    for needle in forbidden.split():
        assert needle not in emitted, f"parser leaked {needle!r}"
    assert sorted((r.raw, r.year) for r in records) == pairs
    assert {key: stats[key] for key in counted} == counted
    # `ark check` compares the year inside the value against the assigned year
    assert all(str(r.year) in r.evidence_value for r in records)
