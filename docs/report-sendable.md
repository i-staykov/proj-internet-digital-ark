# Internet Digital Ark: round 7

Increment to the 1996-2001 annual lists against `merged260901`, scored with your calculator. Every
figure is generated from the evidence store when the archive is built.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 33,848,926 |
| 2. Equivalent-English total | 17,770,588.9026 |
| 3. Increment | **5,978,239** records |
| 4. Equivalent-English increment | **3,401,456.1214** |
| 5. Equivalent-English growth rate | **19.1409%** |

Two units, both at your calculator's counting unit (one distinct valid hostname per year at its
TLD's English share), disjoint, both absent from the baseline, no record rejected by your validator:

| Unit | Files | Records | Equivalent-English | Growth |
|------------------------------|-------------------|---------:|-------------:|-------:|
| registrable domains, the prioritized unit | `additions/NNNN.txt` | 623,920 | 328,764.8318 | 1.8501% |
| valid hostnames beneath registrables, accepted 2026-09-01 | `hostnames/NNNN_hostnames.txt` | 5,354,319 | 3,072,691.2896 | 17.2909% |

| Year | merged260901 | Registrables | Hostnames | Merged | Equivalent-English added |
|------|------------:|-----------:|-----------:|------------:|--------------:|
| 1996 | 979,994 | 8,864 | 79,145 | 1,068,003 | 52,642.0965 |
| 1997 | 2,161,231 | 18,104 | 175,626 | 2,354,961 | 113,128.7747 |
| 1998 | 3,119,897 | 22,997 | 523,957 | 3,666,851 | 313,548.7414 |
| 1999 | 6,345,942 | 46,194 | 841,099 | 7,233,235 | 507,442.7659 |
| 2000 | 10,705,102 | 27,486 | 1,529,638 | 12,262,226 | 858,208.6841 |
| 2001 | 10,536,760 | 500,275 | 2,204,854 | 13,241,889 | 1,556,485.0588 |
| **Total** | **33,848,926** | **623,920** | **5,354,319** | **39,827,165** | **3,401,456.1214** |

**Cumulative score 50.5637%**: the sum of the increases you awarded (1.659986%, 10.730988%, 14.901054%, 4.130718%) plus this round's 19.1409%, as your update log of 2026-08-18 defines it. Round 1 is held out: awarded on records, before the equivalent-English metric.

## 2. What the increment is

Three things, largest first:

1. **Capture corpora already on disk, re-read at hostname grain: 2,097,955 EE,
   4,039,562 records.** Until you accepted hostnames the pipeline collapsed every host to its
   registrable, so the NYPW TimeMaps (34 parts, CC BY 4.0) stood recorded as spent and 180
   domain-wide CDX journals as worth 0. The same bytes, re-read under the new unit, are the
   largest source of the round, with no new request.
2. **Domain-wide CDX sweeps over subdomain platforms: 962,876 EE, 1,295,546
   records.** `matchType=domain`, 1996-2001, over the parents your own benchmark proves dense
   (`rank_platform_parents.py`: `cjb.net` leads at 157,790 sub-hosts held, then `demon.co.uk`,
   `freeserve.co.uk`). This is the workflow your 0901 update describes; each parent is resumable
   from the saturation ledger.
3. **Registrable domains, the prioritized unit: 328,764.8318 EE, 623,920 records.** NYPW TimeMaps
   reopened and measured partition by partition (150,468 EE, after a 14 EE closure on the
   1996 folder), per-domain CDX queries over bracketed gaps (66,566), three Usenet lanes
   (71,388) and 21 small dated artifacts (40,343). 46,148 of
   these domains appear in none of your six files in any year.

| Source | Unit | What dates one record | Records | EE |
|------------------------|------|----------------------------|--------:|-------:|
| `nypw_timemap_hostgrain` | hostname | the row's own 14-digit capture timestamp | 4,039,562 | 2,097,955 |
| `ia_cdx_domain_sweep` | hostname | the row's own 14-digit capture timestamp | 1,295,546 | 962,876 |
| `nypw_timemaps` | registrable | the row's own 14-digit capture timestamp | 329,667 | 143,789 |
| `ia_cdx_bulk` | registrable | the capture timestamp of a URL on that host | 92,479 | 66,566 |
| `usenet_address` | registrable | the post's `Date:` header, corroborated by a second source | 67,145 | 39,232 |
| `usenet_announce` | registrable | the post's `Date:` header, corroborated by a second source | 36,486 | 18,569 |
| 24 further sources | registrable | one row each in `sources.md` and `audit/source_contribution.csv` | 117,354 | 72,470 |
| **Total** | | | **5,978,239** | **3,401,456** |

Every source has its own entry in `sources.md`: link, acquisition route, what dates one item, yield,
and for closed families the measurement that closed them. Per-source figures with files and
evidence rows are in `audit/source_contribution.csv`.

**Composition.** 90.6% of the hostnames are `www.` forms of a registrable. They are distinct
valid hostnames under your rule and sit in their own files, so they merge or drop as a block.

## 3. Evidentiary standard

- One record is one machine-written observation of that name in that year. For capture-backed
  sources it is the Internet Archive's 14-digit timestamp of a capture on that exact host, quoted
  with its replay URL in `additions/evidence_manifest.csv` and
  `hostnames/hostnames_evidence_manifest.csv`, so any line can be opened.
- `domain_year.evidence_id` and `hostname_year.evidence_id` are `NOT NULL` foreign keys: no year
  without an observation. Fifteen invariants check this before every commit and inside the archive.
- Master-eligible classes: `artifact_listing`, `cdx_timestamp`, `dated_directory`, `link_source`, `whois_creation`. `link_target` never dates a year. Anything a human typed
  needs a second source to date that domain first. A creation date attests its own year only.
- A hostname must sit beneath a held registrable, be RFC 1123 valid, and its parent earns the same
  year from the same capture.
- **2,419,541 domains carry no year evidence** and ship as `candidates.txt`, none in an annual
  file; 588,087 of them are under `.edu`, `.gov` or `.mil`.

## 4. Autonomous research this round

- **The loop runs unattended.** Scheduled workflows on a self-hosted runner: a generator proposes
  hypotheses, researcher waves test them in parallel and price each against the store, a re-opener
  re-reads closed verdicts whenever a screen changes, and an improver tunes one prompt or model
  knob per pull request from per-run telemetry.
- **Two of the round's finds are the loop's.** The hostname-grain re-read (item 1 above) was among
  the generator's first seven proposals. The re-opener recovered the NYPW TimeMaps from a 14 EE
  closure by measuring the ingest ledger per folder (year rows per million: 2000 ~24,000, 1999
  ~10,000, 2001 exactly 4), for ~88,000 EE. Rule learned: a partitioned corpus is measured per
  partition, never argued about.
- **Admission without a human, under a standing rule.** A source banks when its evidence class is
  already master-eligible, a machine stamp inside the artifact dates each item, the terms were read
  in full, and the invariants pass. Anything else parks until a written decision.
- **The first find admitted under that rule is a column this project had discarded on purpose.**
  A registry zone file is two hostname corpora: the owner of an NS record is the delegation, the
  right-hand side is the nameserver serving it. At registrable grain the right-hand side was
  measured and closed at 63 pairs, because `ns1.psi.net` collapses to an operator every crawl
  holds. At hostname grain the same 21,498 hosts in the 1997 InterNIC `org`, `edu`, `gov`, `mil`,
  `root` and `arpa` zones are 90% absent from both the store and your own 1997 file:
  **19,211 records and 11,860.7 EE**, dated by the SOA serial `1997041800` inside the payload, no
  new request. The lens it opens: nameservers, mail exchangers and mirrors are the hosts a web
  crawler never fetches, so DNS-side and mail-side artifacts over held registrables are the
  hostname unit's natural source even where their registrables are saturated.
- **Saturation ledger**, as your 0831 update asks: `audit/source_saturation_ledger.csv`, one row
  per source family and version. **471 source families searched and recorded** in `sources.md`: 61 developed, 410 evaluated and closed with the measurement that closed them, so the same ground is not broken twice.
- **Measured negatives that steer the next cycle**: prose corpora fail either the URL-density or
  the authority screen; academic repositories closed by enumeration through five APIs and two
  registries; CD-ROM media, FTP mirrors and trade directories at the curated-directory floor
  (0.013-0.024 net-new pairs per listed name). Each with its figure in `sources.md`.

## 5. CDX execution notes

- Two clients at most, honest User-Agent, two seconds between requests, backoff on 429/503/504,
  `Retry-After` honoured. Collectors take an absolute deadline and outlive the session.
- Per-domain queries over bracketed gaps and the candidate pool: 92,479 registrable pairs.
  Domain-wide sweeps at 200 rows a page write raw `{url, timestamp}` journals, so the same bytes
  can be re-read under a new rule, which is what paid this round.
- Errors met and handled: HTTP 400 past the last page ends a sweep cleanly; a page-count timeout on
  `cjb.net` left that parent ledgered incomplete and resumable; transport failures retry with a
  widening delay.

## 6. Limitations, and what is worth expanding

A capture proves presence, never absence: a year without one is unevidenced, not empty. The
hostname unit rewards platforms with many sub-hosts, so it is concentrated in 2000 and 2001.

Worth expanding, in order: the remaining ranked platforms, resumable from the ledger; every held
capture-bearing artifact re-read at hostname grain; registrable discovery by generated sibling
names and bracketed-gap CDX queries at its measured rate. Not worth more time, measured: prose
corpora, academic repositories, CD-ROM media, FTP mirrors, trade directories.

## 7. Merge, overlap and reconciliation (D3)

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260901` | 33,848,926 | 17,770,588.9026 |
| **accepted increment** | **5,978,239** | **3,401,456.1214** |
| post-merge total | 39,827,165 | 21,172,045.0240 |

- Overlap with the baseline: **0 records**, so all 5,978,239 submitted count once; the two unit files are disjoint in every year.
- **28 of 28 reconciliation checks pass** (per-year `baseline_unique + accepted_new == merged_unique`, unit files disjoint and summing to the submitted count, per-year increments summing to the headline, baseline re-measured). Verdicts in `audit/merge_audit_ark_*.json`, per-year form in `audit/merge_stats_ark_*.csv` in your column names.
- Method: `merge_against_baseline.py` unions both units into the baseline, deduplicated on the lowercased line within each year, and scores every file with your own calculator.

## 8. Reproduction and the four requested artifacts

`README.md` in the archive gives the order: `masters/`, `additions/`, `hostnames/`,
`candidates.txt`, `provenance/*.parquet` (every assignment joined to its evidence row), `logs/`.
Before sending, a fresh copy of this archive was extracted and put through that route: all ten `verify.sh` checks pass; the tier-2 rebuild from `provenance/` reproduces every per-year count, passes all fifteen invariants, and returns all twenty-one result files (six annual additions, six hostname files, six masters, two evidence manifests, the candidate list) byte-identical to the ones shipped. The first rehearsal caught a defect (the hostname export resolved the baseline through a repository-only path when run inside the archive); it was fixed and the rehearsal rerun clean. Tier 3, the full replay, was not run: it is a roughly 50 GB download and five journal sets are held out of the archive on size.

| | asked for | where it is |
|----|------------------|------------------------------------------|
| **D1** | runnable code, dependencies, instructions | `source/source.tar.gz` at `source/COMMIT.txt`, with `pyproject.toml` and `uv.lock`; its `README.md` names what every command prints |
| **D2** | experience summary | `experience-summary.md`, distilled from `sources.md` |
| **D3** | merge and dedup code, overlap, reconciliation | section 7, `source/scripts/round/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your program vendored unmodified, explained in `metric-explained.md` |

`verify.sh` runs ten checks inside a fresh extraction, including all four.
