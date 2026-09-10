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

Every stamp above is machine-written and inside the artifact, so no human judgement dates a year,
and the middle column says which stamp for every source. Nothing in this table is a record your
baseline already holds: the export diffs every shipped list against your own six annual files, so
the overlap in section 5 is zero by construction.

**One class is new.** A server writing its own name: the `Received: ... by <host>` clause a
receiving mail server writes about itself, and the `Path:`, `X-Trace:` and `NNTP-Posting-Host:`
headers a news server writes about a transaction it completed. No sender-supplied field is read.
`findings.md` section 1 gives the exclusions and the two parsing traps that had to be caught first.

A capture proves presence and never absence, and a server header attests the year of its own
message and no other, so both routes err toward omission rather than invention.

## 3. The candidate track, counted the same way

You score candidates separately and at the same rate, so this is a contribution and is held to the
same standard as the annual one: a name your files already carry is not an addition. Every
candidate collection we hold is unioned into one pool, then diffed against your `candidate_pool.txt`
and all six annual files.

| | Names | Equivalent-English |
|---|--:|--:|
| registrable domains | [CANDREG] | [CANDREGEE] |
| exact hostnames | [CANDHOST] | [CANDHOSTEE] |
| **`candidate_additions.txt`** | **[CANDADD]** | **[CANDTRACKEE]** |

That is **[CANDTRACKPCT]** of the same equivalent-English denominator as section 1, on the track you
count separately, and it is never added to the annual increment.

**Where the names came from.** The hostnames are the ISC Internet Domain Survey of 1996-1997, dated
by each edition's own code and named host by host: a DNS observation, which your 2026-09-05 ruling
makes candidate-only, and which promotes one host at a time when exact-host web evidence arrives.
The registrable names are what our own lanes turned up without an in-window stamp, chiefly hosts
named in Usenet posts and mail archives whose date we could not pin to a year we could defend.
**Provenance is per name and not in this list**: `provenance/` joins every name to the evidence row
behind it, and `isc_survey_hostnames/isc_survey_provenance.csv` carries the survey edition, source
file, recovery URL, record location, extraction method and target year for every hostname, which is
the shape you specified on 2026-09-06. That collection also still ships in its own folder; its
names are inside the pool above and are not counted twice.

**Our registrable pool is nearly exhausted against yours, which is worth knowing.** It holds
[CANDIDATES] undated names and ships whole as `candidates.txt` as the working set, but only
[CANDREG] of them are absent from your files. Reporting the working set as the contribution would
have overstated that half of the track by 78x.

## 4. How the work runs, and what we would do next

Two archive clients at most, ever, with an honest User-Agent naming the project and a contact, and
they hold the CDX channel exclusively. Beside them an autonomous research harness runs on a
self-hosted runner: one lane proposes sources, one prices each against a snapshot of the store, a
separate admitter re-derives every figure locally before anything is banked, and a re-opener
re-tests closed verdicts whenever a measurement screen retires. The research lanes can never write
to the store, which is why an agent's own figure has never decided a record.

**No agent assigns a year, and no source reaches an annual file without a written decision.** A
year comes from a machine-written stamp inside the artifact; `ark ingest` refuses any class with no
`Decision:` line, and it refused twice this round until the decision existed. Eighteen invariants
run before every commit and again inside the archive you are holding.

**Next, in the order we would spend the hours.** The server-header class at the archives it has not
been run against, which needs no new bandwidth. The ISP Usenet hierarchies, where the customer host
appears rather than the news server. Sibling national ccTLD extractions of the shape the Poland
index has, which exist for other countries under the same uploader. Second-level suffix namespaces
at hostname grain, where `co.uk` alone is 3.39M index blocks and 1.2% walked. And promoting ISC
candidates one host at a time as exact-host web evidence arrives, which is the only route that
turns that 6.7 million into annual records.

## 5. Merge, overlap and reconciliation (D3)

[MERGE_RECONCILIATION]

## 6. Reproduction, and the four deliverables

`README.md` in the archive gives the route and the file map. Every evidence row names its source,
evidence type, dated value, URL and extraction method; `additions/evidence_manifest.csv` and
`hostnames/hostnames_evidence_manifest.csv` repeat those columns per record. [REPRODUCTION_RESULT]

**D1** code and instructions: `source/source.tar.gz` at `source/COMMIT.txt`, with the autonomous
research loop as `source/fleet.tar.gz`. **D2** experience summary: `experience-summary.md`, with
this round's findings in `findings.md`. **D3** merge and dedup code, overlap and reconciliation:
section 5 and `audit/`. **D4** runnable metric code: `equivalent_english_domain_calculator/`, your
program vendored unmodified and explained in `metric-explained.md`.
