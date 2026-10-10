# Findings

Three results that transfer to anyone doing this work; each says what it was measured on. Totals
are in `report.md`; failures, yields and next steps in `experience-summary.md`. "The evidence rule"
is section XIII of your specification of 6 October
(`Internet_Digital_Ark_Project_1006_Update.docx`); EE is equivalent-English.

## 1. Price a collection at the grain that ships, and measure the shipped files, not the code

The Dartmouth NBER ARCS collection on archive.org carries a public per-item aggregate CDX beside
each ARC set. At registrable grain every parent was held. At hostname grain, a 256 KB head read
of all 282 items' indexes found 25 whose stamps fall in 1996-2001; those 4.09 GB read whole paid
**134,564 net-new hostname records and 83,868 EE**, 20.5 EE per MB of index, 82% of them `www.`
forms, each carrying its own exact-host status-200 capture stamp.

The candidate pool takes every registrable domain with no web-evidence year that is absent from
your release. A pool of only undated names left 189,251 `.dk` names, dated by a registry zone list
the evidence rule refuses, in neither file: 33,594 EE, found by diffing the shipped files against
our database rather than by reading the code.

## 2. A whole-node Internet Archive CDX is a saturation measurement first and a source second

Item `host_cdx_ia600702` is the public CDX of every capture stored on one Internet Archive node:
57.6 GB of gzip, 1,031,419,773 rows, one gzip stream, so no mid-file sample exists, and the head
of the file, sorted by reversed hostname, is all IP-address keys and prices at zero. Read whole:
**14,192,504 status-200 rows stamped 1996-2001** (1997, 2000 and 2001 only, since a node holds
particular crawls), 931,864 host-years, **88.8% already held** in your release or our database.
Net-new: 104,347 hostname records, 50,722 EE, 0.9 EE per MB against the Dartmouth collection's
20.5. Cost: one resumable GET, about 2.5 hours at 3.5 to 7 MB/s, and a 20-minute conversion. No
sibling `host_cdx_*` item exists on archive.org.

The 88.8% is the finding. For the hosts one storage node happened to hold, the benchmark already
covers nearly nine in ten pre-2002 host-years at hostname grain, so a bulk index read now measures
the benchmark's saturation as much as it adds to it.

## 3. Refuse a class when the lead is filed, not after it is fetched

15 of 18 open leads measured were hostname-grain classes the evidence rule keeps out of the
annual files (mail and news server headers, host logs and tables, DNS surveys). Eight fetched and
priced, at 14 to 9,537 EE each, shipped nowhere; the uk Usenet hierarchy cost 8.47 GB for
2,569,006 host-carrying posts, 39,999 hostname-year rows and 0 shippable EE.

The lead queue refuses a hostname-grain lead whose class is not web evidence when it is filed,
citing the evidence rule, and never sends it to be priced; every lead records grain and class. Such
records go to the candidate collection `server_header_hostnames/`, as the evidence rule directs,
and promote only when an exact-host capture for that year arrives.

**What such a record is worth, measured.** Re-derived from the collection's own journals against
the web captures in our database by `scripts/round/header_promotion.py`: at least 0.40% of 749,068
header-dated host-years carry an exact-host capture for the same year, and 1.00% in any in-window
year, beside the 2.67% you measured on Internet Domain Survey hostnames over 1996-2013. Both are
lower bounds, since our database keeps one record per host and year and a header record written
first holds its place, and the shifted years are not held down the same way, so no comparison with
them is drawn.

## Equivalent-English per hour of work

| method | EE | hours | per hour |
|---|---:|---:|---:|
| candidate-pool rule fix: domains whose only year fails the evidence rule | 33,594 | 0.9 | 37,300 |
| Dartmouth ARCS CDX at hostname grain | 83,868 | 2.5 | 33,500 |
| whole-node Internet Archive CDX at hostname grain | 50,722 | 4.0 | 12,700 |
| registrable-domain lists added to the candidate pool (the Finnish .fi registry, expired-domain drop lists, arXiv, Computer Shopper) | 4,634 | 1.5 | 3,100 |
| pricing eight header-class leads the evidence rule bars | 0 shippable | 2.5 | 0 |
