# Internet Digital Ark: round 7

Increment to the 1996-2001 annual lists against `merged260901`, scored with your calculator. Every
figure is generated from the evidence store when the archive is built.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 33,848,926 |
| 2. Equivalent-English total | 17,770,588.9026 |
| 3. Increment | **25,811,931** records |
| 4. Equivalent-English increment | **13,512,552.2294** |
| 5. Equivalent-English growth rate | **76.0389%** |

Two units, both at your calculator's counting unit (one distinct valid hostname per year at its
TLD's English share), disjoint, both absent from the baseline, no record rejected by your validator:

| Unit | Files | Records | Equivalent-English | Growth |
|------------------------------|-------------------|---------:|-------------:|-------:|
| registrable domains, the prioritized unit | `additions/NNNN.txt` | 625,385 | 329,397.2492 | 1.8536% |
| valid hostnames beneath registrables, accepted 2026-09-01 | `hostnames/NNNN_hostnames.txt` | 25,186,546 | 13,183,154.9802 | 74.1852% |

| Year | merged260901 | Registrables | Hostnames | Merged | Equivalent-English added |
|------|------------:|-----------:|-----------:|------------:|--------------:|
| 1996 | 979,994 | 8,869 | 7,742,554 | 8,731,417 | 4,156,305.3362 |
| 1997 | 2,161,231 | 18,116 | 10,781,638 | 12,960,985 | 5,263,432.5480 |
| 1998 | 3,119,897 | 23,025 | 999,025 | 4,141,947 | 573,718.9687 |
| 1999 | 6,345,942 | 46,776 | 1,451,843 | 7,844,561 | 824,290.9369 |
| 2000 | 10,705,102 | 27,630 | 1,623,085 | 12,355,817 | 914,329.9294 |
| 2001 | 10,536,760 | 500,969 | 2,588,401 | 13,626,130 | 1,780,474.5102 |
| **Total** | **33,848,926** | **625,385** | **25,186,546** | **59,660,857** | **13,512,552.2294** |

**Cumulative score 107.4616%**: the sum of the increases you awarded (1.659986%, 10.730988%, 14.901054%, 4.130718%) plus this round's 76.0389%, as your update log of 2026-08-18 defines it. Round 1 is held out: awarded on records, before the equivalent-English metric.

## 2. What the increment is

Four things, largest first. All four are re-readings of bytes already on disk under the unit you
accepted on 1 September; none of them is a new download.

1. **The ISC Internet Domain Survey's per-TLD host files, read one level below the registrable:
   9,167,369 EE, 18,117,395 records at 1996 and 1997.** Banked in July for the registrables
   they imply and closed as complete, these files are a reverse-DNS walk: every line is
   `IP hostname`, the host itself, which the registrable ingest discarded. **The disclosure that
   decides what this is worth: 65% of the records are dialup or numbered
   workstation names** (`pc50.btbcs.bt.co.uk`, `dynws2.mdx.ac.uk`). They are real hosts that
   answered in DNS in the month the survey stamps, and they satisfy your validity rule, but they
   are not sites. They ship in the hostname files with everything else so you can drop them as a
   block if you do not want them; `hostnames/hostnames_evidence_manifest.csv` names the source of
   every record.
2. **Capture corpora already on disk, re-read at hostname grain: 2,097,955 EE,
   4,039,562 records from the NYPW TimeMaps and 631,148 EE, 1,163,616
   records from IA's Early Web index.** The NYPW TimeMaps (34 parts, CC BY 4.0), the 224 Early Web
   CDX parts and 180 domain-wide CDX journals stood recorded as spent or worth 0 at registrable
   grain. A second disclosure, on the Early Web half: nearly all of its records are `www.` forms of
   a registrable you already hold in that year, because your own files carry the non-`www.` hosts
   by name and almost no `www.` ones. A third IA index, the six USFEDGOV-EXTRACT merged CDX files
   for 1996-2001, adds 39,340 EE over 40,260 federal host-years from six
   bulk downloads and no API request.
3. **Domain-wide CDX sweeps over subdomain platforms: 1,220,260 EE, 1,748,953
   records.** `matchType=domain`, 1996-2001, over the parents your own benchmark proves dense
   (`rank_platform_parents.py`: `cjb.net` leads at 157,790 sub-hosts held, then `demon.co.uk`,
   `freeserve.co.uk`). This is the workflow your 0901 update describes; each parent is resumable
   from the saturation ledger.
4. **Registrable domains, the prioritized unit: 329,397.2492 EE, 625,385 records.** NYPW TimeMaps
   reopened and measured partition by partition (150,468 EE, after a 14 EE closure on the
   1996 folder), per-domain CDX queries over bracketed gaps (66,566), three Usenet lanes
   (71,388) and 24 small dated artifacts (40,975). 46,773 of
   these domains appear in none of your six files in any year.

| Source | Unit | What dates one record | Records | EE |
|------------------------|------|----------------------------|--------:|-------:|
| `isc_survey_host_list` | hostname | the survey's own YYMM edition code in the artifact's path | 18,117,395 | 9,167,369 |
| `nypw_timemap_hostgrain` | hostname | the row's own 14-digit capture timestamp | 4,039,562 | 2,097,955 |
| `ia_cdx_domain_sweep` | hostname | the row's own 14-digit capture timestamp | 1,748,953 | 1,220,260 |
| `early_web_hostgrain` | hostname | the row's own 14-digit capture timestamp | 1,163,616 | 631,148 |
| `nypw_timemaps` | registrable | the row's own 14-digit capture timestamp | 329,667 | 143,789 |
| `ia_cdx_bulk` | registrable | the capture timestamp of a URL on that host | 92,479 | 66,566 |
| 34 further sources | both | one row each in `sources.md` and `audit/source_contribution.csv` | 320,259 | 185,465 |
| **Total** | | | **25,811,931** | **13,512,552** |

Every source has its own entry in `sources.md`: link, acquisition route, what dates one item, yield,
and for closed families the measurement that closed them. Per-source figures with files and
evidence rows are in `audit/source_contribution.csv`.

**Composition.** 25.4% of the hostnames are `www.` forms of a registrable. They are distinct
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
- **2,419,436 domains carry no year evidence** and ship as `candidates.txt`, none in an annual
  file; 588,081 of them are under `.edu`, `.gov` or `.mil`.

## 4. Autonomous research this round

- **The loop runs unattended.** Scheduled workflows on a self-hosted runner: a generator proposes
  hypotheses, researcher waves test them in parallel and price each against the store, a re-opener
  re-reads closed verdicts whenever a screen changes, and an improver tunes one prompt or model
  knob per pull request from per-run telemetry.
- **Three of the round's finds are the loop's.** The hostname-grain re-read (item 1 above) was
  among the generator's first seven proposals. The re-opener recovered the NYPW TimeMaps from a
  14 EE closure by measuring the ingest ledger per folder (year rows per million: 2000 ~24,000,
  1999 ~10,000, 2001 exactly 4), for ~88,000 EE. A researcher wave found the first source admitted
  without a human, below.
- **Admission without a human, under a standing rule.** A source banks when its evidence class is
  already master-eligible, a machine stamp inside the artifact dates each item, the terms were read
  in full, and the invariants pass. Anything else parks until a written decision.
- **The first such admission is a column this project had discarded on purpose.** A zone file's
  NS records name two hosts: the delegation and the nameserver serving it. At registrable grain the
  nameserver side closed at 63 pairs (`ns1.psi.net` collapses to an operator every crawl holds).
  At hostname grain, 21,498 nameservers in the 1997 InterNIC `org`, `edu`, `gov`, `mil`, `root`
  and `arpa` zones are 90% absent from both the store and your 1997 file: **19,211 records,
  11,860.7 EE**, dated by the SOA serial `1997041800` in the payload, no new request. The lens it
  opens: nameservers, mail exchangers and mirrors are hosts a web crawler never fetches, so
  DNS-side and mail-side artifacts are the hostname unit's natural source even where their
  registrables are saturated. The second such admission is smaller and cheaper still: the two
  banked squidGuard blocklists read one level down, keeping the host each line names instead of
  its registrable, 7,708 records and 3,441.8 EE at 2001, zero requests (`sources.md`). The
  third is the same lens on a registry database: the nameservers RIPE `domain:` objects point at,
  in the two FUNET editions already banked for their delegated names, 49,841 records and
  11,780 EE across 1996-2001, dated by the dump's own generation stamp and each object's
  latest `changed:` line, under the RIPE NCC's written permission.
  The fourth is item 1 of section 2, the ISC survey host files, which is the largest single
  admission of the round and reached the same way: a column of a banked artifact that the
  registrable unit threw away.
- **Saturation ledger**, as your 0831 update asks: `audit/source_saturation_ledger.csv`, one row
  per source family and version. **493 source families searched and recorded** in `sources.md`: 65 developed, 428 evaluated and closed with the measurement that closed them, so the same ground is not broken twice.
- **Measured negatives that steer the next cycle**: prose corpora fail either the URL-density or
  the authority screen; academic repositories closed by enumeration through five APIs and two
  registries; CD-ROM media, FTP mirrors and trade directories at the curated-directory floor
  (0.013-0.024 net-new pairs per listed name). Each with its figure in `sources.md`.

## 5. CDX execution notes

- Two clients at most, honest User-Agent, two seconds between requests, backoff on 429/503/504,
  `Retry-After` honoured. Collectors take an absolute deadline and outlive the session.
- Per-domain queries over bracketed gaps and the candidate pool: 92,479 registrable pairs.
  Domain-wide sweeps write raw `{url, timestamp}` journals, so the same bytes can be re-read
  under a new rule, which is what paid this round.
- Measured on `co.uk`: a CDX page costs about the same at 200 index blocks as at 10,000 (11 to
  42 s against 110 s), so the sweep now walks 10,000-block pages and asks the page count up
  front. An archive outage refused thirteen parents on their control probe; they were requeued,
  and a failed page is retried rather than skipped.

## 6. Limitations, and what is worth expanding

Three limits, in the order they affect the figure:

- **A hostname is not a site.** Under your rule a valid distinct hostname counts, and a
  reverse-DNS walk resolves dialup ports and workstations as readily as web servers. That is
  where most of this round's records come from and it is quoted per source, so a cut is one
  filter on the manifest rather than a re-derivation.
- **A capture proves presence, never absence.** A year without one is unevidenced, not empty.
- **The two units are counted disjointly and shipped separately**, so discarding the hostname
  files leaves the registrable round intact at 329,397.2492 EE.

Worth expanding, in order: the same one-level-down reading of every other banked artifact that
names hosts (DNS, mail and mirror rosters are the natural seam, since a web crawler never fetched
them); the second-level suffix namespaces at hostname grain (`co.uk` alone is 3.39M index blocks
and 1.2% walked, `com.au`, `co.nz`, `org.uk`, `gov.uk`, `gc.ca` queued behind it); the remaining
ranked subdomain platforms, resumable from the ledger; registrable discovery by bracketed-gap CDX
queries at its measured rate. Not worth more time, measured: prose corpora, academic repositories,
CD-ROM media, FTP mirrors, trade directories.

## 7. Merge, overlap and reconciliation (D3)

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260901` | 33,848,926 | 17,770,588.9026 |
| **accepted increment** | **25,811,931** | **13,512,552.2294** |
| post-merge total | 59,660,857 | 31,283,141.1320 |

- Overlap with the baseline: **0 records**, so all 25,811,931 submitted count once; the two unit files are disjoint in every year.
- **28 of 28 reconciliation checks pass** (per-year `baseline_unique + accepted_new == merged_unique`, unit files disjoint and summing to the submitted count, per-year increments summing to the headline, baseline re-measured). Verdicts in `audit/merge_audit_ark_*.json`, per-year form in `audit/merge_stats_ark_*.csv` in your column names.
- Method: `merge_against_baseline.py` unions both units into the baseline, deduplicated on the lowercased line within each year, and scores every file with your own calculator.

## 8. Reproduction and the four requested artifacts

`README.md` in the archive gives the order: `masters/`, `additions/`, `hostnames/`,
`candidates.txt`, `provenance/*.parquet` (every assignment joined to its evidence row), `logs/`.
Before sending, a fresh extraction of this archive was put through that route: all eleven `verify.sh` checks pass, and the tier-2 rebuild from `provenance/` reproduces every per-year count, passes the fifteen invariants and returns all twenty-one result files byte-identical to the ones shipped. Tier 3, the full replay, was not run: about 50 GB, with five journal sets held out of the archive on size.

| | asked for | where it is |
|----|------------------|------------------------------------------|
| **D1** | runnable code, dependencies, instructions | `source/source.tar.gz` at `source/COMMIT.txt`, with `pyproject.toml` and `uv.lock`; its `README.md` names what every command prints. The research loop of section 4 is `source/fleet.tar.gz`: workflows, prompts, policy and the hypothesis register with every verdict |
| **D2** | experience summary | `experience-summary.md`, distilled from `sources.md` |
| **D3** | merge and dedup code, overlap, reconciliation | section 7, `source/scripts/round/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your program vendored unmodified, explained in `metric-explained.md` |

`verify.sh` runs eleven checks inside a fresh extraction, including all four.
