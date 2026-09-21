# Findings, round 10

Three results from this round that transfer to anyone doing this work, each measured against the
store and each saying what it was measured on. The round's totals are in `report.md`; failures,
yields and next steps are in `experience-summary.md`.

## 1. Price a collection at the grain that ships, and measure the shipped files, not the code

The Dartmouth NBER ARCS collection on archive.org carries a public per-item aggregate CDX beside
each ARC set. Our register closed it in August as "already banked": true at registrable grain,
where every parent was held. Read again at hostname grain on 2026-09-21, a 256 KB head read of all
282 items' indexes found 25 whose stamps fall in 1996-2001; those 4.09 GB read whole paid
**135,005 net-new hostname records and 84,119 equivalent-English**, 20.6 EE per MB of index, 94% of
them `www.` forms of a parent already held, each carrying its own exact-host status-200 capture
stamp. The pocket is now exhausted: the WARCS siblings are 2009-2017, 54 items have no index, and
592 per-ARC parts of the remaining items hold no in-window row.

The same habit found a gap in our own two-track export. A registry zone list ingested as a dated
artifact listing had earned a year the annual screen refuses under Section XIII, so 189,251 `.dk`
names shipped in neither file. The candidate pool took only names with no year at all. The pool
predicate now takes every registrable with no web-method year and no baseline row, and the
candidate claim went from 5,721 names and 3,360 EE to 200,668 names and 36,954 EE in one export,
found by diffing the shipped files against the store rather than by reading the code.

## 2. A whole-node IA CDX is a saturation measurement first and a source second

Item `host_cdx_ia600702` is the public CDX of every capture stored on one Internet Archive node:
57.6 GB of gzip, 1,031,419,773 rows, one gzip stream, so no mid-file sample exists and the
SURT-ordered head (IP-literal keys) prices at zero. Read whole: **14,192,504 status-200 rows
stamped 1996-2001** (1997, 2000 and 2001 only, since a node holds particular crawls), 931,864
host-years, **88% already held** in the merged baseline or the store. Net-new: 104,347 hostname
records, 50,722 EE, 0.9 EE per MB against the Dartmouth pocket's 20.6. Cost: one resumable GET,
about 2.5 hours at 3.5 to 7 MB/s, a 20-minute conversion, and one failure state, an ingest that
died at the 13 GB default DuckDB memory limit and completed at 28 GB. No sibling `host_cdx_*` item
exists on archive.org.

The 88% is the finding. For the hosts one storage node happened to hold, the benchmark already
covers seven in eight pre-2002 host-years at hostname grain, so a bulk index read now measures the
benchmark's saturation as much as it adds to it.

## 3. Refuse a class at filing, not at banking

On the morning of 2026-09-21 all 15 live leads of the autonomous fleet were hostname-grain classes
that Section XIII bars from the annual masters and that the candidate claim does not take: mail
`Received: by` clauses, Usenet `Path`, `X-Trace` and `NNTP-Posting-Host` headers, DNS surveys.
Each was fetched and priced here at 14 to 9,537 EE and shipped nowhere. The cost of the old order
was measured on the uk Usenet hierarchy the evening before: 8.47 GB, 2,569,006 host-carrying
posts, 39,999 hostname-year rows, 0 shippable EE, one hour of tooling that already existed.

The dealer now refuses a hostname-grain lead whose class is not a web method at filing time, with
the Section XIII reason, and never deals it to a price leg; findings carry grain and class; the
lenses were re-weighted toward self-published registers and dated registrable-domain lists. Since
the change every scout lead has closed on an access wall, and none was a header class. The
records already extracted ship as the source-specific candidate collection
`server_header_hostnames/` and in the candidate claim, as Section XIII directs and as the ISC
collection does: names, per-host provenance, a summary and the exclusion ledger of the run. They
promote only when an exact-host capture for that year arrives.

**What such a record is worth, measured.** On 98,381 header-dated host-year pairs from eight Usenet
hierarchies (read from the pre-ingest journals, because the store keeps one evidence row per
host-year and cannot see co-occurrence), 1.16% carry an exact-host capture in our own index for the
same year (Wilson 95% interval 1.10 to 1.23), against 0.56% to 0.86% for the same hosts at a year
shifted by one to three: the header's own year lifts the hit rate 1.4 to 2.1 times. Any in-window
year: 2.10%, beside the 2.67% the reviewer measured on ISC hostnames over 1996-2013. By the shape of
the leftmost label: client-shaped names (digits, ppp, dialup, dyn, pool) 0.06%, infrastructure names
4.07%, `www`, `web` and `ftp` names 31.1%, a 500-fold spread on one string split. Lower bounds
against a partial index, on a named 11% sample, Usenet only: a ranked verification route, not a pile.

## Equivalent-English per hour of work, this round

| method | EE | hours | per hour |
|---|---:|---:|---:|
| export predicate fix, XIII-failed registrables into the candidate claim | 33,594 | 0.9 | 36,600 |
| Dartmouth ARCS CDX at hostname grain | 84,119 | 2.5 | 33,600 |
| whole-node IA CDX at hostname grain | 50,722 | 4.0 | 12,700 |
| registrable lists seeded as candidates (FICORA, drop lists, arXiv, Computer Shopper) | 4,634 | 1.5 | 3,100 |
| three CDX suffix-sweep lanes, continuous | 3,700 a day | continuous | 330 to 580 |
| pricing eight stranded header-class leads | 2,600 measured, 0 shippable | 2.5 | 0 |
