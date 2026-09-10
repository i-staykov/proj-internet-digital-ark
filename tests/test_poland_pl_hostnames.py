"""The Poland .pl ccTLD extraction, item-level CDX read at hostname grain.

Approved master by Ivo on 2026-09-10. Same class and same artifact shape as
`usfedgov_extract_hostnames`, its own source row because it is its own collection with its
own terms. What is pinned here is the receipt check, which is the only thing standing
between a truncated fetch and a corpus of half-read dates, and the field the host comes
from: field 3 and never field 1, because the SURT key drops `www` and reverses the labels.
"""

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

from ark.hostnames import (
    POLAND_METHOD,
    POLAND_SOURCE,
    WEB_FACING_HOST_SOURCES,
    source_for,
    writes_hostname_years,
)
from ark.stats import PROVENANCE_LINEAGE

ROWS = [
    " CDX N b a m s k r M S V g",
    "pl,gazeta,gwx)/~piotrh/art/horowitz/hz11.html 19960510131727"
    " http://gwx.gazeta.pl:80/~piotrh/art/horowitz/hz11.html text/html 200 XNRE4YN - - 357 3 a",
    # the same host and year again, later in the file: one capture dates the pair
    "pl,gazeta,gwx)/index.html 19960710131727 http://gwx.gazeta.pl:80/index.html"
    " text/html 200 QQQQQQQ - - 357 3 a",
    "pl,com,busko-zdroj,zsp)/~ak/k.htm 20010520075947"
    " http://www.zsp.busko-zdroj.com.pl:80/~ak/k.htm text/html 200 ZZZZZZZ - - 357 3 a",
    # not 200: outside the population the approval was priced on
    "pl,onet)/ 20010101000000 http://www.onet.pl:80/ text/html 404 AAAAAAA - - 1 1 a",
    # in 2003, outside the window
    "pl,wp)/ 20030101000000 http://www.wp.pl:80/ text/html 200 BBBBBBB - - 1 1 a",
]


def _module():
    spec = importlib.util.spec_from_file_location(
        "poland_pl_hostgrain",
        Path(__file__).resolve().parents[1] / "scripts/sources/poland/poland_pl_hostgrain.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _index(tmp_path: Path, name: str, rows: list[str]) -> Path:
    path = tmp_path / name
    with gzip.open(path, "wt") as fh:
        fh.write("\n".join(rows) + "\n")
    return path


def _receipt(path: Path) -> tuple[int, str]:
    return path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest()


def test_only_two_hundreds_inside_the_window_reach_the_journal(tmp_path, monkeypatch) -> None:
    m = _module()
    monkeypatch.setattr(m, "OUT", tmp_path / "out")
    index = _index(tmp_path, "pl-2001-EXTRACTION-x.cdx.gz", ROWS)
    assert m.reduce_one(index, _receipt(index)) == 0
    written = sorted((tmp_path / "out").glob("*.jsonl.gz"))
    assert [p.name for p in written] == ["poland_pl_pl-2001-EXTRACTION-x_hostgrain.jsonl.gz"]
    with gzip.open(written[0], "rt") as fh:
        got = [json.loads(line) for line in fh]
    # the 404 and the 2003 capture are gone; the two 1996 captures of one host are one pair,
    # and the EARLIEST of them is the one that dates it
    assert got == [
        {
            "url": "http://gwx.gazeta.pl:80/~piotrh/art/horowitz/hz11.html",
            "timestamp": "19960510131727",
        },
        {"url": "http://www.zsp.busko-zdroj.com.pl:80/~ak/k.htm", "timestamp": "20010520075947"},
    ]


def test_the_host_comes_from_the_original_url_and_never_from_the_surt_key() -> None:
    """Field 1 reverses the labels and drops `www`, so reading it would invent hosts."""
    m = _module()
    url = "http://www.zsp.busko-zdroj.com.pl:80/~ak/k.htm"
    assert m.host_of(url) == "www.zsp.busko-zdroj.com.pl"
    assert m.host_of("http://gwx.gazeta.pl:80/index.html") == "gwx.gazeta.pl"


def test_a_short_or_altered_index_is_refused_rather_than_read(tmp_path, monkeypatch) -> None:
    """A size floor is not a content check, and a half-read index would date hosts anyway."""
    m = _module()
    monkeypatch.setattr(m, "OUT", tmp_path / "out")
    index = _index(tmp_path, "pl-2001-EXTRACTION-x.cdx.gz", ROWS)
    size, sha = _receipt(index)
    assert m.reduce_one(index, (size + 1, sha)) == 2
    assert m.reduce_one(index, (size, "0" * 64)) == 2
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").glob("*.jsonl.gz"))


def test_the_journal_name_routes_to_this_source_and_no_other(tmp_path) -> None:
    name = Path("poland_pl_pl-2001-EXTRACTION-x_hostgrain.jsonl.gz")
    assert source_for(name) == (POLAND_SOURCE, POLAND_METHOD)
    # the sibling extraction lane must not be caught by the same prefix
    assert source_for(Path("usfedgov_USFEDGOV-EXTRACT-2001_hostgrain.jsonl.gz"))[0] != POLAND_SOURCE


def test_the_lane_writes_hostname_years_and_shares_the_archives_lineage() -> None:
    assert writes_hostname_years(POLAND_SOURCE)
    assert POLAND_SOURCE in WEB_FACING_HOST_SOURCES
    # it is an IA index like USFEDGOV-EXTRACT, so the two may not corroborate each other
    assert PROVENANCE_LINEAGE[POLAND_SOURCE] == "internet_archive"
    assert PROVENANCE_LINEAGE["usfedgov_extract_hostnames"] == "internet_archive"


def test_every_receipt_names_an_index_the_fetcher_will_ask_for() -> None:
    m = _module()
    known = m.receipts()
    assert len(known) == 19
    for name, (size, sha) in known.items():
        assert name.startswith("pl-2001-EXTRACTION-") and name.endswith(".cdx.gz")
        assert size > 40_000_000 and len(sha) == 64
