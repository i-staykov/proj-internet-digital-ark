# Experience summary

**Deliverable D2.** A record is one exact hostname in one year, dated by web evidence of that
host: a capture, an index row or a crawl list's node. The round's equivalent-English (EE) is in
the report and `audit/report_figures.json`, records per method and EE per year in
`extended_years/manifest.json`; `sources.md` and `sources-closed.md` hold every source tested
with its verdict.

## 1. The reusable techniques: walk a namespace, read a dated list whole

One `matchType=domain` request on a public suffix such as `co.uk` returns every captured host
beneath it in disjoint pages (`co.uk` is 3,387,186 index blocks, 339 requests); we keep one root
URL answering 2xx or 3xx per exact (host, year) (`scripts/engines/cdx_extended_walk.py`). A list
whose dataset documents a crawl inside one year dates every host on it in one pass: ClueWeb09's
first 12 MB named 56,244 hosts new to 2009 in 1.0 s (`scripts/sources/crawl_lists/clueweb.py`).

## 2. What worked, and its measured yield

- **The public-suffix walk** (`ia_cdx_domain_sweep`): 1,354 EE a request, unwalked 2002 to 2013.
- **Dated crawl lists** (`crawl_list_node`): WDC 2012's host index, 44,607,097.92 EE on 2012;
  ClueWeb12's whole list, 6,025,901 hosts; ClueWeb09's prefix, 677,838.98 EE.
- **HTTP Archive logs** (`httparchive_har_entry`): 2012's 651 GB read whole in about 24 h, about
  8,000 EE a machine-hour against about 3,100 for the three CDX lanes.
- **Bulk CDX indexes at hostname grain** (`bulk_cdx_file`): End of Term 225,160.61 EE at 9.9 EE
  per MB, Dartmouth NBER ARCS 20.6 EE per MB, the node CDX 0.9.

## 3. What did not work

- **The walk on 1996 to 2001:** 2.4 EE a request, since its early web is held: 88% of the node
  CDX's 931,864 in-window host-years were.
- **Other in-window crawls:** LAW's 2004 to 2007 crawl lists are nearly all in your files; TREC
  web, WebBase and the Early Web CDX descend from the Internet Archive's 1996 to 1997 crawls
  behind your release; End of Term's per-WARC files add nothing past its nine parts; Common
  Crawl's host disallows all robots.
- **Server-written header hostnames:** section XIV of your 16 October specification makes them
  candidates, never annual records.
- **Asking name by name:** a `matchType=domain` per parent with no hostname paid 642 EE per
  client-hour; a question per year missing between two held ones (`ia_cdx_collapsed_query`)
  1.249 EE, 255 per client-hour; one per undated pool domain 125.

## 4. Lessons

1. **A head overstates the whole.** Page 0 of a namespace is about twice as dense as the whole;
   HTTP Archive 2012's hosts new to the year fell from 100% in its first zip to 7% by the 17th.
2. **Distinct hosts per row set a page's worth, not TLD weight:** `co.uk` paid 16.0 EE per 1,000
   rows at 61.5 rows a host, against 657.2 at 1.5 (42x).
3. **The index answers only what is asked exactly:** its filter is a search, so the walker anchors
   it, and re-asks a 10,000-block page cut mid-stream as subpages.
4. **Re-price at the shipping grain, on the live store:** 180 suffix journals priced 0 at
   registrable grain, 301,650 EE at hostname grain; a header projection of 10,889 EE delivered
   1,038.4 after another ingest.
5. **A stream can end early on every read:** UKWA's host-linkage file stops at 2 GiB,
   ClueWeb09's Wayback capture at 357 MB of 10.2 GB, so a download is checked against its stated
   size.

## 5. Limitations, and the direction of the error

A bare TLD answers 403, so `.com` cannot be walked, only two-label suffixes such as `co.uk` and
`com.ar`. A crawl list carries no response code, so its node proves only that the documented crawl
fetched a page of that host; ClueWeb09 ships the prefix its 2016 Wayback capture serves. A capture
proves presence, never absence, so every figure errs toward omission. Registry events and mentions
ship as candidates with provenance; the TLD gate is the public suffix list plus nine retired
ccTLDs, not a documented IANA list.

## 6. Recommended directions

1. **1996 to 2001:** the walk is spent there; a share of the CDX lanes' starts asks per-domain gap
   questions for those years (`scripts/engines/cdx_extended_walk.py`), and growth past them needs
   other custodians' capture indexes.
2. **2002 to 2013:** walk the remaining suffix pages.
3. **Registry datasets that publish dates** score on the candidate track; only exact-host evidence
   for the year moves a candidate into a year file.
