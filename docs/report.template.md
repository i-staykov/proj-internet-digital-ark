# Internet Digital Ark: round [ROUND]

Additions to the 1996-2001 annual lists, against `[BASELINE]`. Every figure is generated from the
evidence store, so nothing here can disagree with the files beside it. The round's research
findings are in `findings.md`, the failures, yields and next steps in `experience-summary.md`, the
per-source receipts in `sources.md`, and the route through the archive in `README.md`.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

[REGPAIRS] records ([REGEE] EE) are registrable domains in `additions/` and [HOSTPAIRS] ([HOSTEE]
EE) are hostnames beneath them in `hostnames/`. The two are disjoint in every year, neither is in
the baseline, and either set can be merged or discarded whole. The increment covers [UNIQUE]
distinct domains, [NEWDOMAINS] of which appear in none of your six files in any year.

[PER_YEAR_TABLE]

[CUMULATIVE_SENTENCE]

## 2. What is new, and where it came from

[ATTRIBUTION_TABLE]

The table counts every record submitted; the increment in section 1 is smaller because it excludes
the few your baseline already holds, which section 4 counts. Every stamp above is machine-written
and inside the artifact, so no human judgement dates a year, and the middle column says which stamp
for every source.

**One class is new.** A server writing its own name: the `Received: ... by <host>` clause a
receiving mail server writes about itself, and the `Path:`, `X-Trace:` and `NNTP-Posting-Host:`
headers a news server writes about a transaction it completed. No sender-supplied field is read.
`findings.md` section 1 gives the exclusions and the two parsing traps that had to be caught first.

A capture proves presence and never absence, and a server header attests the year of its own
message and no other, so both routes err toward omission rather than invention.

## 3. The candidate track

[CANDIDATES] domains carry no evidence that earns them a year. They ship as `candidates.txt` and
reach no annual file. They are worth [CANDIDATEEE] equivalent-English if every one were later
dated, which is a ceiling on future work and not a contribution to this round.

**New this round: the same pool also ships as one batch of year files, `candidates/<year>.txt`.**
Most of these names carry a dated observation that does not promote them, chiefly a link-target row
naming the domain in a crawl of that year, so the year says when the name was seen rather than that
it existed. The files overlap and their counts must not be summed as the pool size. Nothing here is
new data: every name is already in `candidates.txt`.

`isc_survey_hostnames/` is the separate provenance-linked candidate collection you specified on
2026-09-06: [ISCPAIRS] hostname-years with per-host provenance, in no figure above.

## 4. Merge, overlap and reconciliation (D3)

[MERGE_RECONCILIATION]

## 5. Reproduction, and the four deliverables

`README.md` in the archive gives the route and the file map. Every evidence row names its source,
evidence type, dated value, URL and extraction method; `additions/evidence_manifest.csv` and
`hostnames/hostnames_evidence_manifest.csv` repeat those columns per record. [REPRODUCTION_RESULT]

**D1** code and instructions: `source/source.tar.gz` at `source/COMMIT.txt`, with the autonomous
research loop as `source/fleet.tar.gz`. **D2** experience summary: `experience-summary.md`, with
this round's findings in `findings.md`. **D3** merge and dedup code, overlap and reconciliation:
section 4 and `audit/`. **D4** runnable metric code: `equivalent_english_domain_calculator/`, your
program vendored unmodified and explained in `metric-explained.md`.
