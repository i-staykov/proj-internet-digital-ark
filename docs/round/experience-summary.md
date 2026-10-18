# Experience summary

**Deliverable D2.** One method made round 12: the public-suffix walk of the Internet Archive CDX
index. Its 2002 to 2013 part, all walked, is 99.8% of the equivalent-English (EE) credited to your
annual files, both parts: 14,516,509.9365 of 14,541,219.6635 EE, 6.932714773% growth on your 2002 to 2013 files.
`sources.md` and `sources-closed.md` carry every source tested with its verdict; "the evidence
rule" is section XIV of your specification of 16 October.

## 1. The reusable technique: walk a namespace, not a name

One `matchType=domain` request on a public suffix such as `co.uk` returns every captured host
beneath it, in disjoint pages (`co.uk` is 3,387,186 index blocks, 339 requests). We keep root URLs
answering 2xx or 3xx, one row per exact (host, year), and drop what your file for that year holds.
One answer names thousands of hosts: unwalked 2002 to 2013 pages paid 1,354 EE a request
(`scripts/engines/cdx_extended_walk.py`).

## 2. What worked, and its measured yield

- **The public-suffix walk:** 14,516,509.9365 EE credited, 1,354 EE a request.
- **Dartmouth NBER ARCS per-item CDX, read at hostname grain:** 83,868 EE, 20.6 EE per megabyte.
- **Whole-node Internet Archive CDX `host_cdx_ia600702`, read whole:** 50,722 EE, 0.9 EE per
  megabyte.
- **Candidate-pool rule fix, `.dk` names dated only by a zone list:** 33,594 EE, 37,300 EE an hour.

## 3. What did not work

- **The walk on 1996 to 2001.** The same unwalked pages paid 2.4 EE a request there, against
  1,354 for 2002 to 2013: the early web this index covers is already held. The node CDX measured
  it: 88.8% of its 931,864 in-window host-years were in your release or our database. Round 12's 1996 to 2001 part
  grew 0.034315905%.
- **Server-written header hostnames, under the evidence rule.** The uk Usenet hierarchy cost
  8.47 GB for 2,569,006 host-carrying posts and 0 shippable EE; at least 0.40% of 749,068
  header-dated host-years carry an exact-host capture for the same year. 15 of 18 open leads
  measured were such classes, so a lead of such a class is refused when filed.
- **Asking name by name.** One `matchType=domain` per parent with no hostname paid 642 EE per
  client-hour, one CDX question per undated pool domain 125.
- **The availability endpoint.** 450 asks in 25 minutes: 0 exact recoveries, about 5 EE an hour.

## 4. Lessons

1. **A first page overstates a walk.** Page 0 is about twice as dense as the whole, so a page 0
   projection is an upper bound.
2. **Distinct hosts per row set a page's worth, not TLD weight.** `co.uk` paid 16.0 EE per 1,000
   rows at 61.5 rows a host, against 657.2 at 1.5 (42x).
3. **The index answers only what is asked exactly.** Its filter is a search, so an unanchored
   root filter matches every row, and a 10,000-block page is cut mid-stream: the walker anchors
   its filter and re-asks a cut page as subpages.
4. **Re-price at the grain that ships, against the live database.** Dartmouth priced 0 at
   registrable grain and 83,868 EE at hostname grain; a source priced at 8,343.6 EE on a stale
   copy measured 4.5 against the live one.
5. **Check bytes, not exit codes.** `curl --retry` truncated a 57.6 GB item, and a replay serves
   0 bytes past 2 GiB: downloads compare against the stated size, and a replayed tail is declared
   unservable.

## 5. Limitations, and the direction of the error

A bare TLD answers 403, so `.com` cannot be walked: the walk reaches the two-label suffixes
(`co.uk`, `com.au`) of TLDs weighing 0.5 or more English. A capture proves presence, never
absence, so every figure errs toward omission. The annual files hold exact-host website evidence
only; registry events, mail and Usenet headers and textual mentions ship as candidate collections
with provenance. The exclusion ledger covers the server-header collection only, and the TLD gate
is the public suffix list plus nine retired ccTLDs, not a documented IANA list.

## 6. Recommended directions

1. **2002 to 2013:** walk the remaining suffix pages; that part already clears the 3% gate.
2. **1996 to 2001:** the walk is spent there, so growth needs year-resolved sources outside it:
   capture indexes at other custodians read whole at hostname grain, the best yield per megabyte
   we measured.
3. **Registry datasets that publish dates** score on the candidate track at about 3,100 EE per
   hour of work; an exact-host capture beside a candidate is the one route into an annual record.
