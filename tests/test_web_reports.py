"""The visitor-report extractor: what dates a page, and which tables are hosts."""

import gzip
import importlib.util
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "extract_host_reports", ROOT / "scripts/sources/web_reports/extract_host_reports.py"
)
reports = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reports)

LIST = """<TITLE>WWW Access Statistics for WWW (May 2000)</TITLE>
<PRE>        Requests     (NoMod Req)             Bytes sent  | Hostname
      62   0.11%       1   0.01%         241779   0.02%  | cache-rl02.proxy.aol.com
      36   0.06%       0   0.00%         169981   0.01%  | 10.1.2.3
<A HREF="http://www.netstore.de/Supply/http-analyze/">http-analyze 2.01pl15</A>
"""
OVERVIEW = """<TITLE>WWW Access Statistics for WWW (May 2000)</TITLE>
Total Transfers by Client Domain (Overview)
    2257  10.99%       0   0.00%         469128  12.16%  | <A HREF="lsites0500.html#D19">aol.com</A>
<A HREF="http://www.netstore.de/Supply/http-analyze/">http-analyze 2.01pl15</A>
"""
WEBSTAT = """<h2>Summary for Period: Jun  1 1996 to Jun 30 1996</h2>
<hr><h2><a name=subdomain>Total Transfers by Client Reversed Subdomain</a></h2>
at.ac.uni-linz.info-pc1               4         20618      0.01        0.01
...ddr.200.255.205.oplkrj033          1         60646      0.00        0.02
<hr><h2><a name=archive>Total Transfers from each Archive Section</a></h2>
"""


def test_a_period_dates_one_year_or_nothing():
    year = reports.period_year
    assert year(date(1999, 4, 1), date(1999, 5, 1)) == (1999, False)
    assert year(date(1999, 12, 1), date(2000, 1, 3)) == (1999, True), "a December report"
    assert year(date(1997, 12, 9), date(1998, 1, 1)) == (1997, True), "it ends on New Year"
    assert year(date(1999, 12, 1), date(2000, 1, 31)) == (None, False), "two months, two years"
    assert year(date(1997, 12, 5), date(2003, 1, 25)) == (None, False)


def test_only_host_tables_are_read_and_a_cut_name_is_refused(tmp_path):
    site = tmp_path / "raw" / "site"
    site.mkdir(parents=True)
    (site / "lsites0500.html").write_text(LIST)
    (site / "sites0500.html").write_text(OVERVIEW)
    (site / "199606.html").write_text(WEBSTAT)
    reports.main([str(tmp_path / "raw"), str(tmp_path / "out")])
    rows = [json.loads(line) for line in (tmp_path / "out" / "rows.jsonl").read_text().splitlines()]
    assert [(r["host"], r["year"], r["raw_line"]) for r in rows] == [
        ("info-pc1.uni-linz.ac.at", 1996, 3),
        ("cache-rl02.proxy.aol.com", 2000, 3),
    ]
    with gzip.open(tmp_path / "out" / "witness.txt.gz", "rt") as fh:
        witness = fh.read().splitlines()
    assert "at.ac.uni-linz.info-pc1" in witness[rows[0]["line"] - 1], "the printed form is kept"


HOSTS = "<title>x: Frequency of Access: Hosts</title>\nppp12.isp.net   :   19 :   205,741\n"
PERIOD = "Period covered by these statistics:  7 days  (29 Aug 1999 - 04 Sep 1999)\n"


def staged(tmp_path, period_capture):
    tree = tmp_path / "raw" / "wayback" / "h" / "weeks"
    (tree / "hosts").mkdir(parents=True)
    (tree / "hosts" / "s.9.total-hosts.html").write_text(HOSTS)
    (tree / "s.9.html").write_text(PERIOD)
    receipts = [
        {"path": "h/weeks/hosts/s.9.total-hosts.html", "replay": "x/web/20000110000000id_/u"},
        {"path": "h/weeks/s.9.html", "replay": f"x/web/{period_capture}id_/u"},
    ]
    (tmp_path / "raw" / "wayback" / "receipts.receipts").write_text(
        "".join(json.dumps(r) + "\n" for r in receipts)
    )
    reports._STAMPS.clear()
    reports.main([str(tmp_path / "raw"), str(tmp_path / "out")])
    return (tmp_path / "out" / "rows.jsonl").read_text().splitlines()


def test_an_archived_host_page_takes_its_period_only_from_a_capture_of_the_same_week(tmp_path):
    assert len(staged(tmp_path / "near", "20000112000000")) == 1
    assert staged(tmp_path / "far", "20010601000000") == []


WUSAGE = """<html><head><title>Week of 01/14/01 to 01/20/01
</title></head><h3>Top 50 of 2669 Documents Sorted by Access Count</h3>
<td>index.example.org</td><td align="right">9</td>
<a name="sites"><h3>Top 50 of 12027 Sites by Access Count</h3></a>
<td>crawler1.bos2.fast-search.net</td><td align="right">688</td>
<a name="referrers"><h3>Top 10 of 6028 Referring URLs by Access Count</h3></a>
<td>www.referrer.example.com</td><td align="right">3</td>
"""


def test_wusage_reads_its_sites_table_alone_and_a_row_names_its_page(tmp_path):
    site = tmp_path / "raw" / "wayback"
    (site / "h").mkdir(parents=True)
    (site / "h" / "10971.html").write_text(WUSAGE)
    replay = "https://web.archive.org/web/20010701101628id_/http://h/10971.html"
    (site / "receipts.receipts").write_text(json.dumps({"path": "h/10971.html", "replay": replay}))
    reports._STAMPS.clear()
    reports._URLS.clear()
    reports.main([str(tmp_path / "raw"), str(tmp_path / "out")])
    rows = [json.loads(line) for line in (tmp_path / "out" / "rows.jsonl").read_text().splitlines()]
    assert [(r["host"], r["year"], r["file"], r["pos"], r["field"]) for r in rows] == [
        ("crawler1.bos2.fast-search.net", 2001, replay, 5, "visitor_rdns")
    ]


WEEK = """<H2>Week of Sun Nov  3 00:00:00 1996
</H2>
<LI>2 sites accessing server most:
<UL>
<LI>e659229.boeing.com 632
<LI>10.1.2.3 357
</UL>
<LI>8 items accessed most:
<UL>
<LI>index.example.org 15
</UL>
"""


SPAN = """<TITLE>Access statistics for h (01/Nov/97 to 24/Nov/97)</TITLE>
<B>Summary period: 01/Nov/97 to 24/Nov/97
<H3>Total Transfers by Client Domain</H3>
   8142   4.1%   4261  14.4%    133780080   5.6%   | widow.av.pa-x.dec.com
<A HREF="http://www.netstore.de/Supply/http-analyze/">http-analyze 1.9d</A>
"""


def test_pages_from_an_arc_file_cite_their_replay_and_a_failed_digest_is_left(tmp_path):
    site = tmp_path / "raw" / "arc"
    (site / "h").mkdir(parents=True)
    pages = {"sites1097.html": SPAN, "sites1197.html": SPAN, "week60.html": WEEK}
    receipts = []
    for name, text in pages.items():
        (site / "h" / name).write_text(text)
        replay = f"https://web.archive.org/web/19980130211959id_/http://h/{name}"
        receipts.append({"path": f"h/{name}", "arc": "ITEM/part.arc.gz", "offset": 7, "size": 535})
        receipts[-1].update(replay=replay, sha1_ok=name != "sites1097.html")
    (site / "receipts.receipts").write_text("".join(json.dumps(r) + "\n" for r in receipts))
    reports._STAMPS.clear()
    reports._URLS.clear()
    reports.main([str(tmp_path / "raw"), str(tmp_path / "out")])
    rows = [json.loads(line) for line in (tmp_path / "out" / "rows.jsonl").read_text().splitlines()]
    arc = "https://archive.org/download/ITEM/part.arc.gz"
    assert [(r["host"], r["year"], r["file"], r["arc"], r["arc_offset"]) for r in rows] == [
        ("widow.av.pa-x.dec.com", 1997, receipts[1]["replay"], arc, 7),
        ("e659229.boeing.com", 1996, receipts[2]["replay"], arc, 7),
    ]
