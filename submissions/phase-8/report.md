# Internet Digital Ark: round 8

Additions to the 1996-2001 annual lists, against `merged260904`. Every figure is generated from the
evidence store, so nothing here can disagree with the files beside it. Receipts are in
`sources.md`, yields in `experience-summary.md`, the route in `README.md`.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 43,235,797 |
| 2. Equivalent-English total | 23,029,472.9274 |
| 3. Increment | **7,834,717** records |
| 4. Equivalent-English increment | **4,322,566.2232** |
| 5. Equivalent-English growth rate | **18.7697%** |

94,672 records (61,669.4256 EE) are registrable domains in `additions/`; 7,740,045 (4,260,896.7976 EE)
are valid hostnames beneath them in `hostnames/`. The two are disjoint in every year, neither is in
the baseline, your validator rejects none of them, and either set can be merged or discarded whole.

**95.0% of the hostname half is `www.<a name already in your files for that year>`.** That is
stated here rather than left to be found. Each of those records has its own capture of that exact
host, never the parent's capture reused, and your III.8 and XI both say a base hostname and a
qualifying subdomain may each be a record. We also counted your side: `merged260904` holds 1,450,310
names beginning `www.` and 1,221,065 of them have the bare name in the same year file, 114,875 from
sources other than us. If you read the rule the other way, dropping the prefix forms is one filter
and the registrable round stands at 61,669.4256 EE.

| Year | Registrables | Hostnames | Equivalent-English added |
|------|-----------:|-----------:|--------------:|
| 1996 | 2,145 | 228,154 | 136,855.3100 |
| 1997 | 4,642 | 349,536 | 208,236.2993 |
| 1998 | 6,333 | 1,020,780 | 571,909.9852 |
| 1999 | 11,048 | 1,434,761 | 796,510.3073 |
| 2000 | 14,401 | 1,626,239 | 908,292.4850 |
| 2001 | 56,103 | 3,080,575 | 1,700,761.8364 |
| **Total** | **94,672** | **7,740,045** | **4,322,566.2232** |

Cumulative verified percentage 75.1353%, time-weighted score 13.186902 over the rounds you scored. **Your 0903 t_i change makes this round either 187.697140 or 4.171048** (t = 1 on the benchmark interval, t = 45 days on the absolute task-assignment interval). Which do you intend, and does it re-score the awarded rounds?

## 2. What one hostname record is

Three conditions, enforced in code (`source/src/ark/hostnames.py`, `checks.py`), not by convention.

1. **Valid per your rule**: dot-separated labels, letters, digits and interior hyphens only, ending
   in an alphabetic TLD label. Underscore names, IP literals and `in-addr.arpa` forms are refused.
2. **Strictly beneath a registrable we hold for that same year.** The parent is a foreign key, a
   bare registrable is never a hostname record, and no name is counted in both units.
3. **Its own machine-written observation in that year, showing the host serving web content**: a
   capture of a URL on it, or a URL listing naming it. A DNS listing proves a machine answered
   rather than a site, so it dates the parent and writes no hostname record.

## 3. What is new, and where it came from

| Source, unit | Artifact, and how it was obtained | What dates one record | Records | EE |
|--------------|--------------------------|----------------------|--------:|-------:|
| `nypw_timemap_hostgrain`, hostname | NYPW TimeMaps (IA, CC BY 4.0), 34 parts held since round 6, re-read at hostname grain | the row's own 14-digit capture timestamp | 4,721,923 | 2,413,147 |
| `ia_cdx_domain_sweep`, hostname | IA CDX `matchType=domain` sweeps of `.uk` suffixes and subdomain platforms, raw journals | the row's own 14-digit capture timestamp | 1,000,897 | 698,944 |
| `early_web_hostgrain`, hostname | IA Early Web CDX index, 224 parts held since July, re-read at hostname grain | the row's own 14-digit capture timestamp | 1,074,009 | 581,826 |
| `usenet_body_url`, hostname | Every non-alt Usenet hierarchy of the archive.org collection, 224 GB read whole, hosts taken only from explicit http, https and ftp URLs in the post BODY | the post's own machine-written `Date:` header | 940,093 | 564,855 |
| `usenet_body_url_hostnames`, registrable | see `sources.md` | the crawl date on the link record | 77,764 | 45,513 |
| `ia_cdx_hostnames`, registrable | see `sources.md` | a Wayback capture timestamp | 16,778 | 16,095 |
| `usfedgov_extract_hostgrain`, hostname | IA USFEDGOV-EXTRACT 1996-2001 merged CDX indexes, one capture per host, bulk download | the row's own 14-digit capture timestamp | 1,219 | 1,067 |
| `maillist_body_url`, hostname | see `sources.md` | a Wayback capture timestamp | 1,893 | 1,051 |
| 2 further sources | each under 1,000 EE, listed in `audit/source_contribution.csv` | | 141 | 68 |
| **Total** | | | **7,834,717** | **4,322,566** |

Every stamp above is machine-written and inside the artifact, so no human judgement dates a year.
2,353,788 domains carry no in-window evidence, ship as `candidates.txt`, and reach no annual
file.

**The methodological finding of this round, which we think transfers.** Reading a bulk corpus at
hostname grain pays only where a person typed the host, not where a crawler visited it: a CDX index
re-read one level down is 99.5% to 100.0% the crawler's own `www.` alias, while a corpus of typed
URLs keeps three quarters of its value. Within that, **density decides which part of a corpus to
read, not size**, and density is how much people typed URLs at each other: across the Usenet
hierarchies it ranged from 2,552 equivalent-English per GB (`news`) to 418 (`soc`), a sixfold spread
independent of volume. And the two saturation figures point opposite ways: **22.2% across
hierarchies, 90.5% inside one already read.** So breadth pays and depth does not, and the rule we
now follow is to read one archive from every community before a second from any of them. That
closed a 101 GB fetch on a measured 40 equivalent-English per GB instead of an assumed 130,000.

## 4. One question, shipped as its own folder

`isc_survey_hostnames/` holds **18,087,127** hostname years from the ISC Internet Domain Survey of
1996-1997, and **they are not in the figures above.** The survey's per-TLD host files are dated by
their own edition code and name each host explicitly, so they satisfy conditions 1 and 2 and are
direct rather than inferred. They fail condition 3 as we read it: a reverse-DNS walk shows a machine
answering, not a page.

Your section XI asks for hostname-level identity wherever there is year-specific evidence and does
not restate the web-content condition, so the honest thing is to ask rather than decide.
**Does a host listed in a dated 1996-1997 reverse-DNS survey, with no capture of a page on it,
count as an annual hostname record?** If yes, the folder merges as it stands. If no, discard it and
nothing else changes. We flag one fact against it: 1.419% of these hosts appear anywhere in your
files, against 84.2% for the `www.` shape, so it is a population you have not held before, and much
of it is dialup ports and numbered workstations.

## 5. Limitations

A capture proves presence, never absence, so a year without one is unevidenced rather than empty,
and both dating routes err toward omission. The units ship separately, so dropping the hostname
files leaves the registrable round intact at 61,669.4256 EE.

Worth expanding next, in order: the same one-level-down reading of the remaining capture-bearing
and URL-listing artifacts already on disk; the second-level suffix namespaces at hostname grain,
where `co.uk` alone is 3.39M index blocks and 1.2% walked; the ranked subdomain platforms still
queued in `audit/source_saturation_ledger.csv`. Measured and closed this round: the `alt` Usenet
remainder, on saturation. Prose corpora, academic repositories, CD-ROM media, FTP mirrors and trade
directories were closed earlier, with figures in `experience-summary.md`.

## 6. Merge, overlap and reconciliation (D3)

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260904` | 43,235,797 | 23,029,472.9274 |
| **accepted increment** | **7,834,717** | **4,322,566.2232** |
| post-merge total | 51,070,514 | 27,352,039.1506 |

Overlap with the baseline is **0 records**, so all 7,834,717 submitted count once, and **28 of 28 reconciliation checks pass**. `merge_against_baseline.py` unions both units into the baseline, deduplicates on the lowercased line within each year and scores every file with your own calculator; the per-check verdicts are in `audit/merge_audit_ark_*.json` and the per-year form in `audit/merge_stats_ark_*.csv`, in your column names.

## 7. Reproduction, and the four deliverables

`README.md` in the archive gives the route and the file map. Every evidence row names its source,
evidence type, dated value, URL and extraction method; `additions/evidence_manifest.csv` and
`hostnames/hostnames_evidence_manifest.csv` repeat those columns per record. Before sending, a fresh extraction of this archive was put through that route: all eleven `verify.sh` checks pass, and the tier-2 rebuild from `provenance/` reproduces every per-year count, passes the seventeen invariants and returns all twenty-one result files byte-identical to the ones shipped. Tier 3, the full replay, was not run: about 50 GB, with eight journal sets held out of the archive on size.

**D1** code and instructions: `source/source.tar.gz` at `source/COMMIT.txt`, with the autonomous
research loop as `source/fleet.tar.gz`. **D2** experience summary: `experience-summary.md`.
**D3** merge and dedup code, overlap and reconciliation: section 6 and `audit/`. **D4** runnable
metric code: `equivalent_english_domain_calculator/`, your program vendored unmodified and
explained in `metric-explained.md`.
