"""The visitor-report extractor: what dates a page, and which tables are hosts."""

import gzip
import importlib.util
import io
import json
import subprocess
import sys
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


def test_far_captures_pair_only_when_the_summary_lists_this_page_s_busiest_hosts(tmp_path):
    busiest = "".join(f"ppp{i}.isp.net   :   {19 - i} :   205,74{i}\n" for i in range(6))
    got = {}
    for case, listed in (("same", busiest), ("other", busiest.replace("205,740", "9"))):
        raw = tmp_path / case / "raw"
        hosts, weeks = raw / "a" / "h" / "weeks" / "hosts", raw / "b" / "h" / "weeks"
        hosts.mkdir(parents=True)
        weeks.mkdir(parents=True)
        (hosts / "s.9.total-hosts.html").write_text(HOSTS.split("\n")[0] + "\n" + busiest)
        (weeks / "s.9.html").write_text(PERIOD + listed)
        later = "2004" if case == "same" else "2000"  # a differing row refuses the same day too
        pages = (("a", "2000", "hosts/s.9.total-hosts.html"), ("b", later, "s.9.html"))
        for tree, stamp, page in pages:
            receipt = {"path": f"h/weeks/{page}", "url": f"http://h:80/weeks/{page}"}
            receipt["replay"] = f"x/web/{stamp}0601000000id_/http://h/weeks/{page}"
            (raw / tree / "receipts.receipts").write_text(json.dumps(receipt))
        reports._STAMPS.clear()
        reports._URLS.clear()
        reports._PAGES.clear()
        reports.main([str(raw), str(tmp_path / case / "out")])
        got[case] = len((tmp_path / case / "out" / "rows.jsonl").read_text().splitlines())
    assert got == {"same": 6, "other": 0}, "the summary sits in another tree, four years apart"


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
    pages["sites1100.html"] = SPAN.replace("/97", "/0")  # 1.9e prints the year 2000 as "0"
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
    assert {(r["host"], r["year"], r["file"], r["arc"], r["arc_offset"]) for r in rows} == {
        ("widow.av.pa-x.dec.com", 1997, receipts[1]["replay"], arc, 7),
        ("e659229.boeing.com", 1996, receipts[2]["replay"], arc, 7),
        ("widow.av.pa-x.dec.com", 2000, receipts[3]["replay"], arc, 7),
    }


AW = """<!-- This page was generated by AccessWatch v1.32 -->
<H2>Accesses for Code 300<BR>
December 12, 1996</H2>
<DT><B>cache.tu-graz.ac.at</B>
"""
BYIP = """Complete wwwedu  usage log
November 1996
By file
=======
             6  /index.htm
By ip
=====
             1  10.1.2.3      ppp-syd-238.ca.com.au
             1  10.1.2.4      4.2.1.10.in-addr.arpa
"""


def test_self_dating_files_a_dns_cache_logs_a_monthly_log_and_an_accesswatch_day(tmp_path):
    site = tmp_path / "raw" / "s"
    site.mkdir(parents=True)
    cache = [f"8538912{i:02d} 10.1.2.3 ppp{i}.kwic.com\n" for i in range(30)]
    late = "885350000 10.1.2.3 late.kwic.com\n853891299 10.1.2.3 *\n"
    (site / "dnscache").write_text("".join(cache) + late)
    replay = "https://web.archive.org/web/19970324050535id_/http://h/dnscache"
    (site / "receipts.receipts").write_text(json.dumps({"path": "dnscache", "replay": replay}))
    hit = '{} - - [10/Oct/1998:13:55:36 -0700] "GET / HTTP/1.0" 200 1\n'
    (site / "access_log").write_text("".join(hit.format(f"h{i}.isp.net") for i in range(12)))
    visit = "[07:27:45 08/13/97 Wed] http://h/tas/ - v{}.dial.att.net -  Mozilla/3.0\n"
    (site / "counter.txt").write_text("".join(visit.format(i) for i in range(6)))
    hit = "Tue, 29 Oct 1996 09:41:38 PST - t{}.vip.best.com - http://h/\n"
    (site / "hits.txt").write_text("".join(hit.format(i) for i in range(6)))
    signing = "g{}.dial.isp.net - [09/04/100 21:43:49 MDT] - ERR: No Name<br>\n"
    (site / "guestlog.html").write_text("".join(signing.format(i) for i in range(6)))
    (site / "details.html").write_text(AW)
    (site / "H1996-11.TXT").write_text(BYIP)
    reports._URLS.clear()
    reports._STAMPS.clear()
    reports.main([str(tmp_path / "raw"), str(tmp_path / "out")])
    rows = [json.loads(line) for line in (tmp_path / "out" / "rows.jsonl").read_text().splitlines()]
    got = {(r["host"], r["year"], r["generator"]) for r in rows}
    assert len(rows) == 63, "the unresolved `*` line and the reverse-zone name give nothing"
    assert got >= {
        ("h0.isp.net", 1998, "raw-log"),
        ("v0.dial.att.net", 1997, "raw-log"),
        ("g0.dial.isp.net", 2000, "raw-log"),
        ("t0.vip.best.com", 1996, "raw-log"),
        ("ppp-syd-238.ca.com.au", 1996, "usage-log"),
        ("cache.tu-graz.ac.at", 1996, "accesswatch"),
        ("ppp0.kwic.com", 1997, "analog-dnscache"),
        ("late.kwic.com", 1997, "analog-dnscache"),
    }, "a lookup dated 1998 in a file captured in 1997 takes 1997"


STATBOT = """These statistics include all Sites logged since: <B>Monday, Apr 1, 1996 - 13:13:41</B>
These statistics last updated on: <B>Wednesday, May 14, 1997 - 14:20:23</B>
<B>Individual Web Page Visits:</B>
<LI><B>page.example.org:</B> 3 Visits Today (9 Total)
<B>Today's Visitor List:</B>
<LI><B>today.dial.xs4all.nl (Netherlands)</B>
<B>Comprehensive Visitor List:</B>
<LI><B>softair.mipnet.fr (France):</B> First Visit Tuesday, May 21
<LI><B>undated.isp.net</B>
"""


def test_statbot_dates_a_site_by_today_or_by_the_weekday_of_its_visit(tmp_path):
    site = tmp_path / "raw" / "s"
    site.mkdir(parents=True)
    (site / "ps.html").write_text(STATBOT)
    reports.main([str(tmp_path / "raw"), str(tmp_path / "out")])
    rows = [json.loads(line) for line in (tmp_path / "out" / "rows.jsonl").read_text().splitlines()]
    assert {(r["host"], r["year"]) for r in rows} == {
        ("today.dial.xs4all.nl", 1997),
        ("softair.mipnet.fr", 1996),
    }, "21 May was a Tuesday in 1996 alone; a site with no date in a two-year span is left"


LOCAL = """<!-- Generated by The Webalizer  Ver. 2.01-06 -->
<TITLE>Estatisticas de utilizacao - Dezembro 2000</TITLE>
<A NAME="TOPURLS"></A>
<TD ALIGN=left NOWRAP><FONT SIZE="-1">page.example.org</FONT></TD></TR>
<A NAME="TOPSITES"></A>
<TD ALIGN=left NOWRAP><FONT SIZE="-1">d148179.brg.pt.kpnqwest.net</FONT></TD></TR>
<A NAME="TOPREFS"></A>
<TD ALIGN=left NOWRAP><FONT SIZE="-1">referrer.example.org</FONT></TD></TR>
"""


def test_a_webalizer_page_in_another_language_is_read_by_its_file_name_and_anchor(tmp_path):
    site = tmp_path / "raw" / "s"
    site.mkdir(parents=True)
    (site / "usage_200012.html").write_text(LOCAL)
    (site / "index.html").write_text(LOCAL)
    reports.main([str(tmp_path / "raw"), str(tmp_path / "out")])
    rows = [json.loads(line) for line in (tmp_path / "out" / "rows.jsonl").read_text().splitlines()]
    assert [(r["host"], r["year"], r["raw_file"].rsplit("/", 1)[1]) for r in rows] == [
        ("d148179.brg.pt.kpnqwest.net", 2000, "usage_200012.html")
    ], "the same page under a name that carries no month is left"


WEBLOG = """<TITLE>Access Details Report: h</TITLE>
Log Analyzed on 2 Jan 2002
02:45:33 30 Dec 2001 to 03:59:00 02 Jan 2002
dhcp-144-35.resnet.ua.edu
      30 Dec -- 00:30:40 --       -- /a.html
   http://referrer.example.org/
a216155.upc-a.chello.nl
      01 Jan -- 07:11:48 --       -- /b.html
outside.isp.net
      05 Mar -- 07:11:48 --       -- /c.html
Wednesday, 13 May 1998
rv6a2.impsat.net.ar
19:41:11 -- 00:04 -- /d.html
"""


def test_weblog_dates_a_visitor_by_the_span_its_log_prints(tmp_path):
    site = tmp_path / "raw" / "s"
    site.mkdir(parents=True)
    (site / "log.details.html").write_text(WEBLOG)
    reports.main([str(tmp_path / "raw"), str(tmp_path / "out")])
    rows = [json.loads(line) for line in (tmp_path / "out" / "rows.jsonl").read_text().splitlines()]
    assert {(r["host"], r["year"]) for r in rows} == {
        ("dhcp-144-35.resnet.ua.edu", 2001),
        ("a216155.upc-a.chello.nl", 2002),
        ("rv6a2.impsat.net.ar", 1998),
    }, "5 March lies in neither year of the span and is left"


FTPWEBLOG = """<h2><a name="summary">Summary</a></h2>
<strong>Period Covered:</strong> 10:56:45 25 November 1997 to 04:20:48 07 February 1998<br>
<h2><a name="files">Complete file statistics</a></h2>
<pre>
19:25:54 01 Dec 1997       12       49169 /pub/not.a.host.edu
</pre>
<h2><a name="domains">Complete domains statistics</a></h2>
<pre>
Last Access               Hits       Bytes Domain
19:25:54 01 Dec 1997       12       49169 dl0192-gyn.gyn.nutecnet.com.br
02:00:26 05 Feb 1998       45      517770 impala.unza.zm
02:00:26 05 Mar 1998        1         100 late.unza.zm
</pre>
"""


def test_ftpweblog_dates_a_client_by_its_last_request_inside_the_printed_span(tmp_path):
    site = tmp_path / "raw" / "s"
    site.mkdir(parents=True)
    (site / "stats.html").write_text(FTPWEBLOG)
    reports.main([str(tmp_path / "raw"), str(tmp_path / "out")])
    rows = [json.loads(line) for line in (tmp_path / "out" / "rows.jsonl").read_text().splitlines()]
    assert {(r["host"], r["year"]) for r in rows} == {
        ("dl0192-gyn.gyn.nutecnet.com.br", 1997),
        ("impala.unza.zm", 1998),
    }, "a file row and a request after the span are left"


def test_an_index_page_s_links_inside_its_own_directory_become_asks_near_its_capture(tmp_path):
    page = '<a href="1999/">y</a> <a href="/other/x.html">o</a> <img src="g.gif"> http-analyze'
    (tmp_path / "h" / "stats").mkdir(parents=True)
    (tmp_path / "h" / "stats" / "_index.html").write_text(page)
    replay = "https://web.archive.org/web/20010203040506id_/http://h/stats/"
    receipt = {"url": "http://h/stats/", "path": "h/stats/_index.html", "replay": replay}
    (tmp_path / "receipts.receipts").write_text(json.dumps(receipt))
    tool = ROOT / "scripts/sources/web_reports/index_to_trees.py"
    out = tmp_path / "out.json"
    subprocess.run([sys.executable, str(tool), str(out), "2004", str(tmp_path)], check=True)
    urls = json.loads(out.read_text())["h"]["urls"]
    assert "http://h/stats/1999/\t20010203040506" in urls and len(urls) == 1 + 144
    assert "http://h/stats/www1999/lsites0599.html\t20010203040506" in urls, "a framed month"


def test_an_index_keeps_one_2xx_or_3xx_capture_per_host_and_year_in_cdx_and_cdxj():
    spec = importlib.util.spec_from_file_location(
        "host_years", ROOT / "scripts/sources/web_reports/host_years.py"
    )
    host_years = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host_years)
    lines = [
        " CDX N b a m s k r M S V g\n",
        "pl,biz)/ 20010202033400 http://www.biz.pl:80/ text/html 302 X - - 1 2 f.arc.gz\n",
        "pl,biz)/a 20010302015003 http://WWW.biz.pl:80/a text/html 200 X - - 1 2 f.arc.gz\n",
        "pl,biz)/b 20010105000000 http://biz.pl/b text/html 404 X - - 1 2 f.arc.gz\n",
        "pl,biz)/c 19950101000000 http://biz.pl/c text/html 200 X - - 1 2 f.arc.gz\n",
        'org,x)/ 20130102030405 {"url": "http://x.org/", "status": "200", "offset": "7"}\n',
        "42,lab)/ 20010101000000 http://lab.42?to=a.org text/html 200 X - - 1 2 f.arc.gz\n",
    ]
    out = io.StringIO()
    assert host_years.reduce(lines, out) == {"rows": 6, "kept": 2}
    assert [json.loads(row) for row in out.getvalue().splitlines()] == [
        {"url": "http://WWW.biz.pl:80/a", "timestamp": "20010302015003", "status": "200"},
        {"url": "http://x.org/", "timestamp": "20130102030405", "status": "200", "offset": "7"},
    ]


def test_the_path_probe_s_shards_split_the_hosts_and_skip_asked_urls():
    spec = importlib.util.spec_from_file_location(
        "probe38", ROOT / "scripts/sources/web_reports/probe38.py"
    )
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    hosts = [f"h{i}.example.edu" for i in range(40)]
    parts = [probe.asks(hosts, (i, 3), set()) for i in range(3)]
    assert sorted(sum(parts, [])) == sorted(f"http://{h}/{p}/" for h in hosts for p in probe.PATHS)
    assert probe.asks(hosts[:1], (0, 1), {"http://h0.example.edu/stats/"}) == [
        "http://h0.example.edu/usage/"
    ]


def test_a_wat_file_gives_one_linking_capture_per_linked_host_and_year():
    spec = importlib.util.spec_from_file_location(
        "wat_links", ROOT / "scripts/sources/web_reports/wat_links.py"
    )
    wat_links = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wat_links)

    def record(page, stamp, status, links, offset):
        http = {"Response-Message": {"Status": status}, "HTML-Metadata": {"Links": links}}
        return json.dumps(
            {
                "Container": {
                    "Filename": "p.arc.gz",
                    "Offset": offset,
                    "Gzip-Metadata": {
                        "Header-Length": "10",
                        "Deflate-Length": "30",
                        "Footer-Length": "8",
                    },
                },
                "Envelope": {
                    "ARC-Header-Metadata": {"Target-URI": page, "Date": stamp},
                    "Payload-Metadata": {"HTTP-Response-Metadata": http},
                },
            }
        )

    a = [
        {"path": "A@/href", "url": "http://www.x.org/a"},
        {"path": "IMG@/src", "url": "http://i.org/"},
    ]
    b = [{"path": "A@/href", "url": "HTTP://WWW.X.ORG:80/b"}, {"path": "A@/href", "url": "/own"}]
    lines = [
        "WARC/1.0",
        record("http://a.gov:80/", "19970713045543", "200", a, "167"),
        record(
            "http://b.gov/",
            "19970102030405",
            "200",
            b + [{"path": "A@/href", "url": "http://b.gov/"}],
            "9",
        ),
        record("http://c.gov/", "19970101000000", "404", a, "5"),
    ]
    out = io.StringIO()
    assert wat_links.reduce(lines, out) == {"records": 3, "kept": 1}
    assert [json.loads(row) for row in out.getvalue().splitlines()] == [
        {
            "host": "www.x.org",
            "year": "1997",
            "url": "http://b.gov/",
            "timestamp": "19970102030405",
            "file": "p.arc.gz",
            "offset": "9",
            "length": 48,
            "link": "HTTP://WWW.X.ORG:80/b",
        }
    ]
