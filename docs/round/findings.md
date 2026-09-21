# Findings, round 10

Three results from this round that transfer to anyone doing this work; each says what it was
measured on. Totals are in `report.md`; failures, yields and next steps in `experience-summary.md`.
"The evidence rule" is section XIII of your specification of 17 September
(`Internet_Digital_Ark_Project_0917_Update.docx`); EE is equivalent-English.

## 1. Price a collection at the grain that ships, and measure the shipped files, not the code

The Dartmouth NBER ARCS collection on archive.org carries a public per-item aggregate CDX beside
each ARC set. We had dismissed it in August as already covered: true at registrable grain, where
every parent was held. Read again at hostname grain on 2026-09-21, a 256 KB head read of all 282
items' indexes found 25 whose stamps fall in 1996-2001; those 4.09 GB read whole paid **134,564
net-new hostname records and 83,868 EE**, 20.5 EE per MB of index, 82% of them `www.` forms, each
carrying its own exact-host status-200 capture stamp. The collection is now exhausted: the WARCS
siblings are 2009-2017, 54 items have no index, and 592 per-ARC parts of the remaining items hold
no in-window row.

The same habit found a gap in our own delivery build. A registry zone file, a dated list, had
earned each name the list's year, which the evidence rule refuses for the annual files, so 189,251
`.dk` names shipped in neither file: the candidate pool took only names with no year at all. The
pool now takes every registrable domain with no web-evidence year that is absent from your
release, and the candidate claim grew by 33,594 EE in one build, found by diffing the shipped files
against our database rather than by reading the code.

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

On the morning of 2026-09-21, 15 of the 18 open leads of our autonomous search were hostname-grain
classes the evidence rule keeps out of the annual files (mail and news server headers, host logs
and tables, DNS surveys), the server-header class admitted in round 9 among them. Eight had been
fetched and priced, at 14 to 9,537 EE each, and shipped nowhere; the evening before, the uk Usenet
hierarchy had cost 8.47 GB for 2,569,006 host-carrying posts, 39,999 hostname-year rows and 0
shippable EE.

The lead queue now refuses a hostname-grain lead whose class is not web evidence when it is filed,
citing the evidence rule, and never sends it to be priced; every lead records grain and class; the
search is weighted toward registries' own published lists and dated registrable-domain lists. Of
the 37 leads closed since, 3 were refused at filing on class and the rest on access or absence of
the artifact; none was a header class. The records already extracted ship as the candidate
collection `server_header_hostnames/`, as the evidence rule directs and as the Internet Domain
Survey hostnames already do, and promote only when an exact-host capture for that year arrives.

**What such a record is worth, measured.** On 98,381 header-dated host-year pairs from eight Usenet
hierarchies, 1.16% carry an exact-host capture in our own index for the same year (Wilson 95%
interval 1.10 to 1.23), against 0.14% to 0.82% for the same hosts at a year shifted by one to
three: the header's own year lifts the hit rate. Any in-window year: 2.10%, beside the 2.67% you
measured on Internet Domain Survey hostnames over 1996-2013. By the shape of the leftmost label:
client-shaped names (digits, ppp, dialup, dyn, pool) 0.06%, infrastructure names 4.07%, `www`,
`web` and `ftp` names 31.1%, a 500-fold spread on one string split. Lower bounds against our
partial capture index, measured on 11% of the header hosts, Usenet only; the label shape ranks
which hosts to verify first.

## Equivalent-English per hour of work, this round

| method | EE | hours | per hour |
|---|---:|---:|---:|
| candidate-pool rule fix: domains whose only year fails the evidence rule | 33,594 | 0.9 | 37,300 |
| Dartmouth ARCS CDX at hostname grain | 83,868 | 2.5 | 33,500 |
| whole-node Internet Archive CDX at hostname grain | 50,722 | 4.0 | 12,700 |
| registrable-domain lists added to the candidate pool (the Finnish .fi registry, expired-domain drop lists, arXiv, Computer Shopper) | 4,634 | 1.5 | 3,100 |
| three continuous Internet Archive index sweeps by domain, together | 193,733 in twelve days | continuous | 670 |
| pricing eight header-class leads the evidence rule bars | 0 shippable | 2.5 | 0 |
