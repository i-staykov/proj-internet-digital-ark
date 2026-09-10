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
EE) are hostnames beneath them in `hostnames/`: disjoint in every year, and either set can be
merged or discarded whole. [UNIQUE] distinct domains carry the increment, [NEWDOMAINS] of them
absent from your six files in every year.

[PER_YEAR_TABLE]

[CUMULATIVE_SENTENCE]

## 2. What is new, and where it came from

[ATTRIBUTION_TABLE]

Every stamp is machine-written and inside the artifact, so no human judgement dates a year, and the
middle column names the stamp per source. Nothing here is a record you already hold: the export
diffs every shipped list against your own annual files, so section 5's overlap is zero by
construction.

**One class is new**, a server writing its own name: the `Received: ... by <host>` clause a
receiving mail server writes about itself, and the `Path:`, `X-Trace:` and `NNTP-Posting-Host:`
headers a news server writes about a transaction it completed. No sender-supplied field is read.
`findings.md` gives the exclusions and the two parsing traps caught first. A capture proves
presence and never absence, and a header attests its own message's year and no other, so both err
toward omission.

## 3. The candidate track, counted the same way

You score candidates separately, at the same rate, over the same denominator, so this is a
contribution and is held to the annual standard: every collection we hold unioned into one pool,
then diffed against your `candidate_pool.txt` and all six annual files.

| | Names | Equivalent-English |
|---|--:|--:|
| registrable domains | [CANDREG] | [CANDREGEE] |
| exact hostnames | [CANDHOST] | [CANDHOSTEE] |
| **`candidate_additions.txt`** | **[CANDADD]** | **[CANDTRACKEE]** |

**[CANDTRACKPCT]** of the same denominator as section 1, never added to it.

The hostnames are the ISC Internet Domain Survey of 1996-1997, dated by each edition's own code:
a DNS observation, which your 0905 ruling makes candidate-only and promotable one host at a time on
exact-host web evidence. The registrables are names our lanes found without a year we could defend.
**Provenance is per name and not in this list**: `provenance/` joins each name to its evidence row,
and `isc_survey_hostnames/isc_survey_provenance.csv` carries the survey edition, source file,
recovery URL, record location, extraction method and year for every hostname, the shape you
specified on 2026-09-06. That folder still ships; its names are inside the pool and not counted
twice.

One measurement worth passing on: our working pool holds [CANDIDATES] undated names, of which
[CANDREG] are absent from your files. Shipping a working set as a contribution would have
overstated that half of the track by 78x.

## 4. How the work runs, and where it goes next

Two archive clients at most, ever, with an honest User-Agent naming the project and a contact, and
they hold the CDX channel exclusively. An autonomous research harness runs beside them on a
self-hosted runner: one lane proposes sources, one prices each against a snapshot of the store, a
separate admitter re-derives every figure locally before anything is banked, and a re-opener
re-tests closed verdicts whenever a measurement screen retires. **The research lanes cannot write
to the store**, which is why an agent's own figure has never decided a record.

**No agent assigns a year, and no source reaches an annual file without a written decision.** A
year comes from a machine-written stamp inside the artifact; `ark ingest` refuses any class with no
`Decision:` line and refused twice this round until one existed. Eighteen invariants run before
every commit and again inside this archive.

Next, in the order we would spend the hours: the server-header class at the archives it has not
been run against, which needs no new bandwidth; the ISP Usenet hierarchies, where the customer host
appears rather than the news server; sibling national ccTLD extractions of the shape the Poland
index has; second-level suffix namespaces at hostname grain, where `co.uk` alone is 3.39M index
blocks and 1.2% walked; and promoting ISC candidates as exact-host web evidence arrives, the one
route that turns [CANDHOSTEE] candidate equivalent-English into annual records.

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
