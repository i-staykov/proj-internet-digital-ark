# Internet Digital Ark: round [ROUND]

Additions to the 1996-2001 annual lists, against `[BASELINE]`. Every figure is generated from the
evidence store, so nothing here can disagree with the files beside it. Receipts are in
`sources.md`, yields in `experience-summary.md`, the route in `README.md`.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

[REGPAIRS] records ([REGEE] EE) are registrable domains in `additions/`; [HOSTPAIRS] ([HOSTEE] EE)
are valid hostnames beneath them in `hostnames/`. The two are disjoint in every year, neither is in
the baseline, your validator rejects none of them, and either set can be merged or discarded whole.

**[WWWSHARE] of the hostname half is `www.<a name already in your files for that year>`.** That is
stated here rather than left to be found. Each of those records has its own capture of that exact
host, never the parent's capture reused, and your III.8 and XI both say a base hostname and a
qualifying subdomain may each be a record. We also counted your side: `[BASELINE]` holds 1,450,310
names beginning `www.` and 1,221,065 of them have the bare name in the same year file, 114,875 from
sources other than us. If you read the rule the other way, dropping the prefix forms is one filter
and the registrable round stands at [REGEE] EE.

[PER_YEAR_TABLE]

[CUMULATIVE_SENTENCE]

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

[ATTRIBUTION_TABLE]

Every stamp above is machine-written and inside the artifact, so no human judgement dates a year.
[CANDIDATES] domains carry no in-window evidence, ship as `candidates.txt`, and reach no annual
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

`isc_survey_hostnames/` holds **[ISCPAIRS]** hostname years from the ISC Internet Domain Survey of
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
files leaves the registrable round intact at [REGEE] EE.

Worth expanding next, in order: the same one-level-down reading of the remaining capture-bearing
and URL-listing artifacts already on disk; the second-level suffix namespaces at hostname grain,
where `co.uk` alone is 3.39M index blocks and 1.2% walked; the ranked subdomain platforms still
queued in `audit/source_saturation_ledger.csv`. Measured and closed this round: the `alt` Usenet
remainder, on saturation. Prose corpora, academic repositories, CD-ROM media, FTP mirrors and trade
directories were closed earlier, with figures in `experience-summary.md`.

## 6. Merge, overlap and reconciliation (D3)

[MERGE_RECONCILIATION]

## 7. Reproduction, and the four deliverables

`README.md` in the archive gives the route and the file map. Every evidence row names its source,
evidence type, dated value, URL and extraction method; `additions/evidence_manifest.csv` and
`hostnames/hostnames_evidence_manifest.csv` repeat those columns per record. [REPRODUCTION_RESULT]

**D1** code and instructions: `source/source.tar.gz` at `source/COMMIT.txt`, with the autonomous
research loop as `source/fleet.tar.gz`. **D2** experience summary: `experience-summary.md`.
**D3** merge and dedup code, overlap and reconciliation: section 6 and `audit/`. **D4** runnable
metric code: `equivalent_english_domain_calculator/`, your program vendored unmodified and
explained in `metric-explained.md`.
