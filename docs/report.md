# Internet Digital Ark: round 9

Additions to the 1996-2001 annual lists and to the candidate pool, against `merged260908`. Every
figure below is generated from the evidence store, so this report cannot disagree with the files
beside it.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 65,313,842 |
| 2. Equivalent-English total | 34,887,095.7393 |
| 3. Increment | **3,399,258** records |
| 4. Equivalent-English increment | **1,874,979.2367** |
| 5. Equivalent-English growth rate | **5.3744%** |

91,168 records (65,738.2990 EE) are registrable domains in `additions/`, 3,308,090 (1,809,240.9377 EE)
are hostnames beneath them in `hostnames/`: disjoint in every year, either set mergeable or
discardable whole. 44,919 of the 84,942 distinct domains carrying the increment are absent
from your six files in every year.

| Year | Registrables | Hostnames | Equivalent-English added |
|------|-----------:|-----------:|--------------:|
| 1996 | 1,354 | 6,138 | 4,706.0329 |
| 1997 | 4,620 | 11,473 | 9,965.1210 |
| 1998 | 5,642 | 41,452 | 28,290.1568 |
| 1999 | 19,884 | 136,285 | 94,087.1613 |
| 2000 | 20,232 | 329,152 | 194,617.8658 |
| 2001 | 39,436 | 2,783,590 | 1,543,312.8989 |
| **Total** | **91,168** | **3,308,090** | **1,874,979.2367** |

**The candidate track is claimed too, separately.** `candidate_additions.txt`: 13,139,161 names,
6,696,064.0603 EE, **19.1935%** of the same denominator, never added to the annual increment.
It is net-new the way the annual files are, every collection we hold unioned into one pool and then
diffed against your `candidate_pool.txt` and all six annual files. 13,109,834 are ISC survey
hostnames, dated by each edition's own code and candidate-only under your 0905 ruling; 29,327 are
registrables our lanes found without a year we could defend, out of 2,279,755 undated names in
the working pool, so shipping the pool itself would have overstated that half 78-fold. Provenance is
per name and not in the list: `provenance/` and `isc_survey_hostnames/isc_survey_provenance.csv`,
in the shape you specified on 0906.

Cumulative verified percentage 80.5097%, this round at its own unverified 5.3744% and round 1 on records. Time-weighted score 18.874694 over the three rounds you scored, your own figure where you stated one. Under your 0903 rule, from the origin your round 8 divisor implies (2026-09-04 less 33 days), this round is t = 39 and adds 1.378057.

## 2. Where the increment came from, and what dates each record

| Source | Unit | What dates one record | Records | EE |
|------------------------|------|----------------------------|--------:|-------:|
| `ia_cdx_domain_sweep` | hostname | the row's own 14-digit capture timestamp | 2,262,861 | 1,353,286 |
| `usenet_server_written_header` | hostname | the post's own machine-written `Date:` header | 736,440 | 350,946 |
| `usenet_body_url` | hostname | the post's own machine-written `Date:` header | 109,258 | 64,821 |
| `ia_cdx_bulk` | registrable | the capture timestamp of a URL on that host | 30,343 | 29,954 |
| `usenet_address` | registrable | the post's `Date:` header, corroborated by a second source | 33,288 | 19,565 |
| `poland_pl_extract_hostgrain` | hostname | the row's own 14-digit capture timestamp, from the original URL and never the SURT key | 147,649 | 15,798 |
| 14 further sources | both | one row each in `sources.md` and `audit/source_contribution.csv` | 79,419 | 40,609 |
| **Total** | | | **3,399,258** | **1,874,979** |

Every year comes from a machine-written stamp inside the artifact, a capture timestamp or the
message's own `Date:` header, so no human judgement dates a record; per-record columns are in
`additions/evidence_manifest.csv` and `hostnames/hostnames_evidence_manifest.csv`, per-source
reasoning in `sources.md`. **One evidence class is new: a server writing its own name.** The
`Received: ... by <host>` clause you accepted last round reads the same in NNTP, so the `Path:`,
`X-Trace:` and `NNTP-Posting-Host:` headers a news server writes about a transaction it completed
are admitted under the same rule and no new one. No sender-supplied field is read. That class paid
350,946 EE from spool already on disk, at no new bandwidth; `findings.md` gives the
exclusions and the two parsing traps. A capture proves presence and never absence, so both units err
toward omission.

**No agent writes to the store and no agent assigns a year.** The research harness proposes and
prices sources autonomously, a separate admitter re-derives every figure before anything banks, and
`ark ingest` refuses an evidence class with no written decision, twice this round. Eighteen
invariants run before every commit and again inside this archive.

## 3. Merge, overlap and reconciliation (D3)

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260908` | 65,313,842 | 34,887,095.7393 |
| **accepted increment** | **3,399,258** | **1,874,979.2367** |
| post-merge total | 68,713,100 | 36,762,074.9760 |

**Not one of the 3,399,258 records submitted is already in the baseline**, so every one of them counts exactly once: the export diffs each shipped list against your own annual files before it writes them. **28 of 28 reconciliation checks pass**. `merge_against_baseline.py` unions both units into the baseline, deduplicates on the lowercased line within each year and scores every file with your own calculator; the per-check verdicts are in `audit/merge_audit_ark_*.json` and the per-year form in `audit/merge_stats_ark_*.csv`, in your column names.

## 4. Reproduction, and where the rest is documented

Before sending, a fresh extraction of this archive was put through that route: all eleven `verify.sh` checks pass, and the tier-2 rebuild from `provenance/` reproduces every per-year count, passes the seventeen invariants and returns all twenty-one result files byte-identical to the ones shipped. Tier 3, the full replay, was not run: about 50 GB, with eight journal sets held out of the archive on size. `README.md` gives the route and the file map.

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
6,691,826.9522 candidate EE into annual records. `experience-summary.md` prices each.
