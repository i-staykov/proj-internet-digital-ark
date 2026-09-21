# Internet Digital Ark: round 10

Additions to the 1996-2001 annual lists and to the candidate pool, against `merged260917-2`. Every
figure below is generated from the evidence store, so this report cannot disagree with the files
beside it.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 103,223,503 |
| 2. Equivalent-English total | 56,074,593.5291 |
| 3. Increment | **591,027** records |
| 4. Equivalent-English increment | **329,140.5166** |
| 5. Equivalent-English growth rate | **0.5870%** |

841 records (395.9463 EE) are registrable domains in `additions/`, 590,186 (328,744.5703 EE)
are hostnames beneath them in `hostnames/`: disjoint in every year, either set mergeable or
discardable whole. 723 of the 841 distinct domains carrying the increment are absent
from your six files in every year; the rest is completeness, years filled on names you hold. Every
`www.` record carries its own exact-host capture for that year, and nothing is inferred between a
bare name and its `www.` form.

| Year | Registrables | Hostnames | Equivalent-English added |
|------|-----------:|-----------:|--------------:|
| 1996 | 0 | 437 | 233.1241 |
| 1997 | 0 | 4,576 | 2,742.2903 |
| 1998 | 0 | 11,521 | 6,360.0689 |
| 1999 | 0 | 44,926 | 24,681.8126 |
| 2000 | 7 | 145,416 | 80,361.4079 |
| 2001 | 834 | 383,310 | 214,761.8128 |
| **Total** | **841** | **590,186** | **329,140.5166** |

**The candidate track is claimed too, separately.** `candidate_additions.txt`: 261,977 names,
77,497.7487 EE, **0.1382%** of the same denominator, never added to the annual increment.
It is net-new the way the annual files are: every collection we hold unioned into one pool, then
diffed against your `candidate_pool.txt` and all six annual files. 217,900 are registrable names
whose only dated evidence Section XIII screens out of the annual files (registry zone and drop
lists, dated directories, author mail hosts), re-tracked here rather than lost; 44,077 are
hostnames in two provenance-linked collections: 4,265 ISC survey observations, candidate-only
under your 0905 ruling (`isc_survey_hostnames/`), and 39,812 hosts whose only dated evidence is
a server-written mail or Usenet header, candidates under Section XIII (`server_header_hostnames/`).
Provenance is per name, in `provenance/` and each collection's own CSV.

Cumulative verified percentage 79.4048%, this round at its own unverified 0.5870% and round 1 on records. Time-weighted score 6.88 + 6.302372 + 5.687792 + 0.944228 = 19.814392, your own scores for rounds 6, 7, 8 and 9. Under your 0903 rule, from the origin your round 8 divisor implies (2026-09-04 less 33 days), this round is t = 50. Domain-Year Score: S = 10 x (0.586969 / 50) = 0.117394. Candidate-Pool Score: S = 10 x (0.138205 / 50) = 0.027641.

## 2. Where the increment came from, and what dates each record

| Source | Unit | What dates one record | Records | EE |
|------------------------|------|----------------------------|--------:|-------:|
| `ia_cdx_domain_sweep` | hostname | the row's own 14-digit capture timestamp | 341,489 | 190,023 |
| `bulk_cdx_file` | hostname | a Wayback capture timestamp | 238,911 | 134,590 |
| `nypw_timemap_hostgrain` | hostname | the row's own 14-digit capture timestamp | 9,717 | 4,106 |
| `ia_node_host_cdx_hostnames` | registrable | a Wayback capture timestamp | 811 | 375 |
| `early_web_hostgrain` | hostname | the row's own 14-digit capture timestamp | 44 | 23 |
| `ia_cdx_hostnames` | registrable | the row's own 14-digit capture timestamp | 19 | 16 |
| 3 further sources | both | one row each in `sources.md` and `audit/source_contribution.csv` | 36 | 8 |
| **Total** | | | **591,027** | **329,141** |

Every year comes from a machine-written stamp inside the artifact, an exact-host capture timestamp
in an archive's own index or a custodian's per-host capture extract, so no human judgement dates a
record. Per-record columns are in `additions/evidence_manifest.csv` and
`hostnames/hostnames_evidence_manifest.csv` (hostname, parent, year, evidence type, evidence value,
source, acquisition method, evidence URL); per-source reasoning is in `sources.md`.

**Two collections are new this round, both public Internet Archive CDX indexes read whole at
hostname grain**, Section XIII's reference pattern with the captured URL and stamp retained. The
per-item aggregate CDX of the Dartmouth NBER ARCS collection: 25 of 282 items carry 1996-2001
stamps, 135,005 records, 84,119 EE, a collection our register had closed in August at registrable
grain. The whole CDX of storage node ia600702: 1,031,419,773 rows, 14,192,504 in-window status-200
rows, 88% of them already held, 104,347 records, 50,722 EE. `findings.md` gives yield, overlap,
cost and failure state for each. Server-written mail and Usenet headers, admitted in round 9, are
hostname-in-use evidence under Section XIII and never annual records; the hosts they date ship
as the source-specific candidate collection `server_header_hostnames/`, with per-host provenance
and the exclusion ledger of its validation run, and count in the candidate claim of section 1.

**No agent writes to the store and no agent assigns a year.** The research harness proposes and
prices sources autonomously and now refuses at filing any hostname-grain class outside Section
XIII's web methods; a separate admitter re-derives every figure before anything banks, and
`ark ingest` refuses an evidence class with no written decision. The invariants of `ark check` run
before every commit and again inside this archive.

## 3. Merge, overlap and reconciliation (D3)

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260917-2` | 103,223,503 | 56,074,593.5291 |
| **accepted increment** | **591,027** | **329,140.5166** |
| post-merge total | 103,814,530 | 56,403,734.0457 |

**Not one of the 591,027 records submitted is already in the baseline**, so every one of them counts exactly once: the export diffs each shipped list against your own annual files before it writes them. **28 of 28 reconciliation checks pass**. `merge_against_baseline.py` unions both units into the baseline, deduplicates on the lowercased line within each year and scores every file with your own calculator; the per-check verdicts are in `audit/merge_audit_ark_*.json` and the per-year form in `audit/merge_stats_ark_*.csv`, in your column names.

## 4. Reproduction, and where the rest is documented

Before sending, a fresh extraction of this archive was put through that route: the checksum beside the archive verifies, all twelve `verify.sh` checks pass, and the tier-2 rebuild from `provenance/` alone reproduces every per-year count, passes the eighteen invariants and returns every shipped file this project claims byte-identical to the one here. The six `masters/` files are the exception by design, since this round: they are your own release plus our additions, and your own rows are no longer shipped back to you inside the provenance table. Tier 3, the full replay, was not run: about 50 GB, with eight journal sets held out of the archive on size. `README.md` gives the route and the file map.

| what you asked to see documented | where it is |
|---|---|
| counting unit, normalisation, registrable extraction, the metric | `metric-explained.md`; `equivalent_english_domain_calculator/`, your program vendored unmodified (**D4**) |
| validity and salvage rules, dedup process, dropped-domain statistics | `README.md`, `dropped_domains.txt`, `audit/` (**D3**) |
| source contributions, annual and candidate counted separately | sections 1 and 2, `audit/source_contribution.csv`, `sources.md` |
| CDX tools, retrieval strategy, errors and how they were handled | `experience-summary.md` (**D2**) |
| newly identified methods, yields, limitations, what is worth expanding | `findings.md` and `experience-summary.md` (**D2**) |
| code and instructions to reproduce the workflow | `source/source.tar.gz` at `source/COMMIT.txt`, the autonomous harness as `source/fleet.tar.gz` (**D1**) |

Two gaps against Section XIII are stated in `experience-summary.md` section 5 rather than hidden:
the exclusion ledger with the seven named columns exists for the header collection's run only
(`candidates_unparsed.txt` carries a reason per line for the rest), and the TLD gate is the public
suffix list plus a nine-entry historical ccTLD allowlist rather than a documented IANA list.

What remains, priced in `experience-summary.md` section 6: registry datasets that publish dates,
for the candidate track; exact-host captures beside the 32,341.0925 EE of ISC candidates and the
header-class assets, the one route that promotes either; the JISC UK CDX index once the UK Web
Archive serves it again; and custodian capture indexes of the two kinds read this round, of which
archive.org holds no more.

## 5. The two open research questions (Section IV-A)

**Q1. Pre-1996 web data at scale.** Every qualifying pattern in Section XIII is a web-era artifact,
and the Internet Archive began crawling in 1996, so no pre-1996 hostname can meet XIII as written:
the question needs a pre-1996 evidence standard before it needs sources. We propose three tiers,
each with its error rate stated per source. **Tier A**, a pre-1996 web capture held by a non-IA
custodian (national libraries, university archives, software-distribution mirrors that kept HTTP
logs): evidence level equal to XIII's, expected coverage small and institutional. **Tier B**, a
machine-written, server-stamped record naming the exact host at a date: `Path`,
`NNTP-Posting-Host` and `Received: by` headers, dated FTP mirror listings, UUCP maps. XIII excludes
these for 1996-2001 because captures exist there; before 1996 they are the only machine-stamped
option, and they prove a host in service, not a website. **Tier C**, dated human-written mentions:
candidates only. Feasibility: about 110 GB of Usenet reaching before 1996 is already on disk, with
per-post `Date` and server headers, and the extraction shipped in this archive reads 2.6 million
host-carrying posts an hour; rights are those of the archive copies. Limitations: the date is the
server's clock, the hosts are servers and relays, and coverage skews to institutions that ran
news. Retention route: a pre-1996 collection held apart from 1996-2001, per host the source,
message-id, header field and stamp, with an overlap report against the benchmark. A measured
example from this round: the July 1995 NASA HTTP log dates 31,654 host-years (21,932 EE at
hostname grain) before the window; it is a tier-B asset, not an annual record.

**Q2. Assigning the year more accurately.** Our answer is a graded model whose error rates are
measured, and a field that lets the grade travel with the record. **Instrument 1**, an exact-host
capture in the target year from an archive's index or a custodian's per-host extract: direct
evidence, the reference standard, the only route into an annual file. **Instrument 2**, the Wayback
availability endpoint as a second dating engine, graded against CDX ground truth already on disk
with no new CDX requests: 204 CDX year-pairs over 150 domains, 187 recovered, 91.7% recall (94.3%
at 2001), and 40 of 40 CDX-negative domains returned empty, so it does not invent years; its two
defects (status-200 only, `www.` canonicalised away) make every miss an under-claim. **Instrument
3**, dated DNS surveys and server-written headers: discovery-only, hostname-in-use rather than
website. Measured this round on 98,381 header-dated host-years from eight Usenet hierarchies:
1.16% carry an exact-host capture for the same year (95% interval 1.10 to 1.23) against 0.56%
to 0.86% at a shifted year, and 2.10% in any in-window year beside your 2.67% for ISC over
1996-2013; by leftmost label, client-shaped names 0.06%, infrastructure names 4.07%, `www` and
`web` names 31.1%, so the verification queue is ranked before a request is spent (`findings.md`,
section 3). Reconciliation: at export every candidate is
diffed against your `candidate_pool.txt` and all six annual files, and a name accepted in an annual
master leaves the pool. Proposal: a per-record `evidence_level` field, direct, discovery or
unresolved, in the manifests and the candidate collections, so the reconciliation is
machine-checkable on your side; this archive's manifests carry `evidence_type` and
`acquisition_method`, from which the level is a lookup. Promotion: a candidate moves to an annual
file only when an exact-host, target-year capture is retained beside it; nothing is inferred
between a bare name and its `www.` form or between adjacent years. Where a second engine pays,
measured: of 6,568,275 domains held in year N and missing N+1, one pinned availability query at
`20010701` recovers 55.0% +/- 6.3%; the same engine aimed at the 2.41 million undated pool is
closed at 114 EE an hour, because 98.4% of that pool is Usenet-extracted names and 600 sampled hit
5.17% against 97.5% on interleaved controls. Assumption: a capture proves presence and never
absence. Limitation: both instruments err toward omission, so a year with no capture is
unevidenced, not empty.
