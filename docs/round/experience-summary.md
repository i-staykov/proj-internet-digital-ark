# Experience summary

**Deliverable D2.** A record is one exact hostname in one year, dated by a capture or documented
crawl of that host: the Internet Archive CDX index gives nearly all of 1996 to 2001, dated crawl
lists and bulk indexes read whole most of 2002 to 2013. The round's equivalent-English (EE) is in
the report and `audit/report_figures.json`, per method in `extended_years/manifest.json` and the
evidence manifests; `sources.md` and `sources-closed.md` hold every source tested with its verdict.

## 1. The reusable techniques: walk a namespace, read a dated list whole

One `matchType=domain` request on a public suffix such as `co.uk` returns every captured host
beneath it in disjoint pages (`co.uk` is 3,387,186 index blocks, 339 requests); we keep one root
URL answering 2xx or 3xx per exact (host, year) (`scripts/engines/cdx_extended_walk.py`). A list
whose dataset documents a crawl inside one year dates every host on it in one pass: ClueWeb09's
first 12 MB named 56,244 hosts new to 2009 in 1.0 s (`scripts/sources/crawl_lists/clueweb.py`).

## 2. What worked, and its measured yield

- **The public-suffix walk** (`ia_cdx_domain_sweep`): 1,354 EE a request, unwalked 2002 to 2013.
- **Dated crawl lists** (`crawl_list_node`): the WDC 2012 host index, ClueWeb12 and ClueWeb09, each
  streamed whole; ClueWeb12 priced 3,396,843.10 EE against merge261007-4.
- **HTTP Archive request logs** (`httparchive_har_entry`): 2012's 651 GB read whole in about 24 h,
  about 8,000 EE an hour of machine time against about 3,100 for the three CDX lanes.
- **Bulk CDX indexes read whole at hostname grain** (`bulk_cdx_file`): End of Term 225,160.61 EE at
  9.9 EE per MB, Dartmouth NBER ARCS 20.6 EE per MB, the node CDX 0.9.
- **One CDX question per domain** (`ia_cdx_collapsed_query`): 1.249 EE on a gap (a year missing
  between two held ones), 0.2645 on the 2001 edge.

## 3. What did not work

- **The walk on 1996 to 2001:** 2.4 EE a request, the early web this index covers being held: 88.8%
  of the node CDX's 931,864 in-window host-years were in your release or our database.
- **Other in-window crawls:** LAW's it-2004, eu-2005, sk-2005 and uk-2007-05 lists are in your
  files; TREC web, WebBase and the Early Web CDX descend from your 1996 to 1997 crawls; End of
  Term's per-WARC files add nothing past its nine parts; Common Crawl's host disallows all robots.
- **Server-written header hostnames, under section XIV of your 16 October specification:** the uk
  Usenet hierarchy, 8.47 GB and 2,569,006 host-carrying posts, gave 0 shippable EE; 15 of 18 open
  leads measured were such classes, so such a lead is refused when filed.
- **Asking name by name:** a `matchType=domain` per parent with no hostname paid 642 EE per
  client-hour, a question per gap 255, per pool domain 125, the availability endpoint 0 exact
  recoveries in 450 asks: worth asking only where pages pay nothing, 1996 to 2001.

## 4. Lessons

1. **A head overstates the whole.** Page 0 of a namespace is about twice as dense as the whole;
   HTTP Archive 2012's hosts new to the year fell from 100% in its first zip to 7% by the 17th.
2. **Distinct hosts per row set a page's worth, not TLD weight:** `co.uk` paid 16.0 EE per 1,000
   rows at 61.5 rows a host, against 657.2 at 1.5 (42x).
3. **The index answers only what is asked exactly:** its filter is a search, so the walker anchors
   it, and re-asks a 10,000-block page cut mid-stream as subpages.
4. **Re-price at the shipping grain, on the live database:** Dartmouth priced 0 at registrable
   grain, 83,868 EE at hostname grain; another source, 8,343.6 EE on a stale copy, measured 4.5.
5. **Check bytes, not exit codes:** `curl --retry` truncated a 57.6 GB item and a replay serves 0
   bytes past 2 GiB, so downloads compare against the stated size.

## 5. Limitations, and the direction of the error

A bare TLD answers 403, so `.com` cannot be walked: the walk reaches the two-label suffixes
(`co.uk`, `com.au`) of TLDs weighing 0.5 or more English. A crawl list carries no response code,
so its node proves a page fetched in the documented window; ClueWeb09 ships the prefix its 2016
Wayback capture serves. A capture proves presence, never absence, so every figure errs toward
omission. Headers, registry events and mentions ship as candidates with provenance; the TLD gate
is the public suffix list plus nine retired ccTLDs, not a documented IANA list.

## 6. Recommended directions

1. **1996 to 2001:** the walk is spent there; `EARLY` of every four CDX lane starts take the best
   unit for it, a gap question, and growth past that needs other custodians' capture indexes.
2. **2002 to 2013:** walk the remaining suffix pages; read each bulk index one item a year first.
3. **Registry datasets that publish dates** score on the candidate track at about 3,100 EE per
   hour of work; an exact-host capture beside a candidate is the one route into an annual record.
