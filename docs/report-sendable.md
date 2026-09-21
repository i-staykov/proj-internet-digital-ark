# Internet Digital Ark: round 10

Additions to the 1996-2001 annual lists and to the candidate pool, against your release
`merged260917-2`; every figure is generated from our evidence store. "The specification" is your
`Internet_Digital_Ark_Project_0917_Update.docx` of 17 September, "the evidence rule" its section XIII
(Mandatory Evidence Classification and Hostname Integrity Gate), "the two open questions" its
section IV-A. EE is equivalent-English.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 103,223,503 |
| 2. Equivalent-English total | 56,074,593.5291 |
| 3. Increment | **591,027** records |
| 4. Equivalent-English increment | **329,140.5166** |
| 5. Equivalent-English growth rate | **0.5870%** |

841 records (395.9463 EE) are registrable domains, in `additions/`; 590,186 (328,744.5703 EE)
are hostnames beneath them, in `hostnames/`: disjoint in every year, either set mergeable or
discardable whole, every record carrying its own exact-host capture in that year. 723
registrable domains are absent from your six files in every year; the rest fills years on names
you hold.

| Year | Registrables | Hostnames | Equivalent-English added |
|------|-----------:|-----------:|--------------:|
| 1996 | 0 | 437 | 233.1241 |
| 1997 | 0 | 4,576 | 2,742.2903 |
| 1998 | 0 | 11,521 | 6,360.0689 |
| 1999 | 0 | 44,926 | 24,681.8126 |
| 2000 | 7 | 145,416 | 80,361.4079 |
| 2001 | 834 | 383,310 | 214,761.8128 |
| **Total** | **841** | **590,186** | **329,140.5166** |

**The candidate track, claimed separately and never added to the above.** `candidate_additions.txt`:
261,977 names, 77,497.7487 EE, **0.1382%** of the same denominator, after removing every
name in your `candidate_pool.txt` or annual files. 217,900 are registrable domains whose only dated
evidence the evidence rule keeps out of the annual files (registry zone and drop lists, dated
directories, author e-mail hosts); 44,077 are hostnames from the two collections of section 3.

Cumulative verified percentage 79.4048%, this round at its own unverified 0.5870% and round 1 on records. Time-weighted score 6.88 + 6.302372 + 5.687792 + 0.944228 = 19.814392, your own scores for rounds 6, 7, 8 and 9. Under the time-weighted score rule of your 3 September update, from the origin your round 8 divisor implies (2026-09-04 less 33 days), this round is t = 50. Domain-Year Score: S = 10 x (0.586969 / 50) = 0.117394. Candidate-Pool Score: S = 10 x (0.138205 / 50) = 0.027641.

## 2. What is new, and where it came from

| Source | Unit | What dates one record | Records | EE |
|------------------------|------|----------------------------|--------:|-------:|
| `ia_cdx_domain_sweep` | hostname | the row's own 14-digit capture timestamp | 341,489 | 190,023 |
| `bulk_cdx_file` | hostname | the row's own 14-digit capture timestamp in the archive's index | 238,911 | 134,590 |
| `nypw_timemap_hostgrain` | hostname | the row's own 14-digit capture timestamp | 9,717 | 4,106 |
| 6 further sources | both | one row each in `sources.md` and `audit/source_contribution.csv` | 910 | 422 |
| **Total** | | | **591,027** | **329,141** |

Both large sources are **Internet Archive capture indexes (CDX) read whole at hostname grain**:
every captured URL with the archive's own 14-digit timestamp, the evidence rule's reference
pattern. We keep the exact hostname and stamp of every HTTP 200 row dated 1996-2001.

- **Dartmouth NBER ARCS**, a research crawl collection on archive.org with a CDX beside each of
  its 282 items: the 25 with 1996-2001 stamps, read whole (4.1 GB), paid 135,005 records and
  84,119 EE. We had closed it in August at registrable grain, where every parent was held.
- **Storage node ia600702**, the public 57.6 GB CDX of every capture on one archive.org node:
  1,031,419,773 rows, 14,192,504 of them HTTP 200 and dated 1996-2001, 931,864 host-years,
  **88% already in your release or our store**; the remaining 104,347 records paid 50,722 EE. A
  bulk index read now measures the benchmark's saturation as much as it adds to it.

The autonomous research loop now refuses at filing any hostname-grain source whose class the
evidence rule keeps out of the annual files; the last such fetch was 8.5 GB for 0 shippable EE.

## 3. Two candidate collections, separate from the annual files

`isc_survey_hostnames/` is unchanged from round 9: 4,265 hosts of the 1996-1997 Internet Domain
Survey, candidates by your ruling of 5 September that a DNS listing is not website evidence.

`server_header_hostnames/` is new, as the evidence rule instructs for mail and Usenet delivery
headers: 39,812 exact hostnames whose only dated evidence is a header a mail or news server wrote
about itself (`Received: by`, `Path`, `X-Trace`, `NNTP-Posting-Host`), proof of a host in service,
not of a website. It ships with per-host provenance and the seven-column exclusion ledger of its
validation run; a host promotes only beside an exact-host capture for that year.

Its worth, measured on 98,381 header-dated host-years from eight Usenet hierarchies with no new
requests: **1.16% carry an exact-host capture for the same year** (95% interval 1.10 to 1.23),
against 0.56% to 0.86% at a year shifted by one to three; 2.10% in any in-window year, beside the
2.67% you measured on Internet Domain Survey hosts over 1996-2013. By leftmost label: dial-up shaped
names 0.06%, infrastructure names 4.07%, `www` and `web` names 31.1%. Lower bounds against a partial
index, Usenet only: a ranked verification queue.

## 4. The two open questions

**Q1. Discovering pre-1996 web data at scale.**

No pre-1996 hostname can meet the evidence rule as written: every qualifying pattern is a web
capture, and the Internet Archive began crawling in 1996. The question needs a pre-1996 evidence
standard before it needs sources; we propose three tiers, named by what wrote the date.

Tier A, a pre-1996 web capture held by another custodian (national libraries, university archives,
software mirrors that kept HTTP logs): the evidence rule's own standard, small and institutional in
coverage. Tier B, a server naming the exact host at a date: news and mail headers as in section 3,
dated FTP mirror listings, UUCP maps; before 1996 the only machine-stamped option, proving a host in
service, not a website. Tier C, dated human-written mentions: candidates only.

What we can add is the tier-B corpus and its cost: about 110 GB of Usenet reaching before 1996 is
already on disk with per-post `Date` and server headers, and the shipped extractor reads 2.6
million host-carrying posts an hour. Limits: the server's clock dates it, the hosts are servers and
relays, coverage skews to institutions that ran news. Retention: a pre-1996 collection held apart
from 1996-2001, with source, message-id, header field and stamp per host, and an overlap report
against the benchmark.

**Q2. Determining the year a website existed more accurately.**

Three evidence levels with measured error rates, the level travelling with the record. Direct: an
exact-host capture in the target year from an archive index or a custodian's per-host
extract, the only route into an annual file. Second engine: the Wayback availability endpoint,
graded against CDX ground truth on disk, 187 of 204 year-pairs recovered (91.7%, 94.3% at 2001)
and 40 of 40 CDX-negative domains empty; it returns HTTP 200 captures only and drops `www.`, so
every miss under-claims. Discovery-only: DNS surveys and server-written headers at the rates of
section 3, which rank a verification queue before a request is spent.

Reconciliation: at export every candidate is diffed against your `candidate_pool.txt` and six
annual files, and a name accepted annually leaves the pool. We propose one field per record,
`evidence_level` (direct, discovery, unresolved), so the reconciliation is machine-checkable on your
side; our manifests carry `evidence_type` and `acquisition_method`, from which it is a lookup.
Promotion only beside an exact-host, target-year capture; nothing is inferred between a bare name
and its `www.` form or between adjacent years.

Where the second engine pays: of 6,568,275 domains held in year N and missing N+1, one query pinned
at mid-2001 recovers 55.0% +/- 6.3%; on the 2.41 million undated pool it is closed at 114 EE an
hour. Both instruments err toward omission.

## 5. Merge, overlap and reconciliation (D3)

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260917-2` | 103,223,503 | 56,074,593.5291 |
| **accepted increment** | **591,027** | **329,140.5166** |
| post-merge total | 103,814,530 | 56,403,734.0457 |

**Not one of the 591,027 records submitted is already in the baseline**, so every one of them counts exactly once: the export diffs each shipped list against your own annual files before it writes them. **28 of 28 reconciliation checks pass**. `merge_against_baseline.py` unions both units into the baseline, deduplicates on the lowercased line within each year and scores every file with your own calculator; the per-check verdicts are in `audit/merge_audit_ark_*.json` and the per-year form in `audit/merge_stats_ark_*.csv`, in your column names.

## 6. Reproduction, deliverables, limits

Before sending, a fresh extraction of this archive was put through that route: the checksum beside the archive verifies, all twelve `verify.sh` checks pass, and the tier-2 rebuild from `provenance/` alone reproduces every per-year count, passes the eighteen invariants and returns every shipped file this project claims byte-identical to the one here. The six `masters/` files are the exception by design, since this round: they are your own release plus our additions, and your own rows are no longer shipped back to you inside the provenance table. Tier 3, the full replay, was not run: about 50 GB, with eight journal sets held out of the archive on size. `README.md` gives the route and the file map. **D1** `source/source.tar.gz`
at `source/COMMIT.txt`, the autonomous loop as `source/fleet.tar.gz`; **D2** `experience-summary.md`
and `findings.md`; **D3** section 5 and `audit/`; **D4** `equivalent_english_domain_calculator/`,
your program vendored unmodified.

Two gaps against the evidence rule: the seven-column exclusion ledger exists for the header
collection's run only (`candidates_unparsed.txt` carries a reason per line for the rest), and the
TLD gate is the public suffix list plus nine retired ccTLDs, not a documented IANA list. Worth
expanding next, priced in `experience-summary.md`: dated registry datasets for the candidate track,
and exact-host captures beside the two candidate collections, the one route that promotes either.
