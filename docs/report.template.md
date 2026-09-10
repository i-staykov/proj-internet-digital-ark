# Internet Digital Ark: round [ROUND]

Additions to the 1996-2001 annual lists and to the candidate pool, against `[BASELINE]`. Every
figure below is generated from the evidence store, so this report cannot disagree with the files
beside it.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

[REGPAIRS] records ([REGEE] EE) are registrable domains in `additions/`, [HOSTPAIRS] ([HOSTEE] EE)
are hostnames beneath them in `hostnames/`: disjoint in every year, either set mergeable or
discardable whole. [NEWDOMAINS] of the [UNIQUE] distinct domains carrying the increment are absent
from your six files in every year.

[PER_YEAR_TABLE]

**The candidate track is claimed too, separately.** `candidate_additions.txt`: [CANDADD] names,
[CANDTRACKEE] EE, **[CANDTRACKPCT]** of the same denominator, never added to the annual increment.
It is net-new the way the annual files are, every collection we hold unioned into one pool and then
diffed against your `candidate_pool.txt` and all six annual files. [CANDHOST] are ISC survey
hostnames, dated by each edition's own code and candidate-only under your 0905 ruling; [CANDREG] are
registrables our lanes found without a year we could defend, out of [CANDIDATES] undated names in
the working pool, so shipping the pool itself would have overstated that half 78-fold. Provenance is
per name and not in the list: `provenance/` and `isc_survey_hostnames/isc_survey_provenance.csv`,
in the shape you specified on 0906.

[CUMULATIVE_SENTENCE]

## 2. Where the increment came from, and what dates each record

[ATTRIBUTION_TOP]

Every year comes from a machine-written stamp inside the artifact, a capture timestamp or the
message's own `Date:` header, so no human judgement dates a record; per-record columns are in
`additions/evidence_manifest.csv` and `hostnames/hostnames_evidence_manifest.csv`, per-source
reasoning in `sources.md`. **One evidence class is new: a server writing its own name.** The
`Received: ... by <host>` clause you accepted last round reads the same in NNTP, so the `Path:`,
`X-Trace:` and `NNTP-Posting-Host:` headers a news server writes about a transaction it completed
are admitted under the same rule and no new one. No sender-supplied field is read. That class paid
[HOST_USENETHDR_EE] EE from spool already on disk, at no new bandwidth; `findings.md` gives the
exclusions and the two parsing traps. A capture proves presence and never absence, so both units err
toward omission.

**No agent writes to the store and no agent assigns a year.** The research harness proposes and
prices sources autonomously, a separate admitter re-derives every figure before anything banks, and
`ark ingest` refuses an evidence class with no written decision, twice this round. Eighteen
invariants run before every commit and again inside this archive.

## 3. Merge, overlap and reconciliation (D3)

[MERGE_RECONCILIATION]

## 4. Reproduction, and where the rest is documented

[REPRODUCTION_RESULT] `README.md` gives the route and the file map.

| what you asked to see documented | where it is |
|---|---|
| counting unit, normalisation, registrable extraction, the metric | `metric-explained.md`; `equivalent_english_domain_calculator/`, your program vendored unmodified (**D4**) |
| validity and salvage rules, dedup process, dropped-domain statistics | `README.md`, `dropped_domains.txt`, `audit/` (**D3**) |
| source contributions, annual and candidate counted separately | section 1 and 2, `audit/source_contribution.csv`, `sources.md` |
| CDX tools, retrieval strategy, errors and how they were handled | `experience-summary.md` (**D2**) |
| newly identified methods, yields, limitations, what is worth expanding | `findings.md` and `experience-summary.md` (**D2**) |
| code and instructions to reproduce the workflow | `source/source.tar.gz` at `source/COMMIT.txt`, the autonomous harness as `source/fleet.tar.gz` (**D1**) |

Worth the next hours, in this order: the server-header class at the archives it has not been run
against, which needs no new bandwidth; the ISP Usenet hierarchies, where the customer host appears
rather than the news server; sibling national ccTLD extractions of the shape the Poland index has;
and promoting ISC candidates as exact-host evidence arrives, the one route that turns
[CANDHOSTEE] candidate EE into annual records. `experience-summary.md` prices each.
