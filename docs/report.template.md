# Internet Digital Ark: round [ROUND]

Increment to the 1996-2001 annual lists against `[BASELINE]`, scored with your calculator. Every
figure is generated from the evidence store when the archive is built.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

Two units, both at your calculator's counting unit (one distinct valid hostname per year at its
TLD's English share), disjoint, both absent from the baseline, no record rejected by your validator:

| Unit | Files | Records | Equivalent-English | Growth |
|------------------------------|-------------------|---------:|-------------:|-------:|
| registrable domains, the prioritized unit | `additions/NNNN.txt` | [REGPAIRS] | [REGEE] | [REGGROWTH] |
| valid hostnames beneath registrables, accepted 2026-09-01 | `hostnames/NNNN_hostnames.txt` | [HOSTPAIRS] | [HOSTEE] | [HOSTGROWTH] |

[PER_YEAR_TABLE]

[CUMULATIVE]

## 2. What the increment is

Three things, largest first:

1. **Capture corpora already on disk, re-read at hostname grain: [HOST_NYPW_EE] EE,
   [HOST_NYPW_N] records.** Until you accepted hostnames the pipeline collapsed every host to its
   registrable, so the NYPW TimeMaps (34 parts, CC BY 4.0) stood recorded as spent and 180
   domain-wide CDX journals as worth 0. The same bytes, re-read under the new unit, are the
   largest source of the round, with no new request.
2. **Domain-wide CDX sweeps over subdomain platforms: [HOST_SWEEP_EE] EE, [HOST_SWEEP_N]
   records.** `matchType=domain`, 1996-2001, over the parents your own benchmark proves dense
   (`rank_platform_parents.py`: `cjb.net` leads at 157,790 sub-hosts held, then `demon.co.uk`,
   `freeserve.co.uk`). This is the workflow your 0901 update describes; each parent is resumable
   from the saturation ledger.
3. **Registrable domains, the prioritized unit: [REGEE] EE, [REGPAIRS] records.** NYPW TimeMaps
   reopened and measured partition by partition ([REG_NYPW_EE] EE, after a 14 EE closure on the
   1996 folder), per-domain CDX queries over bracketed gaps ([REG_CDX_EE]), three Usenet lanes
   ([REG_USENET_EE]) and [REG_OTHER_N] small dated artifacts ([REG_OTHER_EE]). [NEWDOMAINS] of
   these domains appear in none of your six files in any year.

[ATTRIBUTION_TOP]

Every source has its own entry in `sources.md`: link, acquisition route, what dates one item, yield,
and for closed families the measurement that closed them. Per-source figures with files and
evidence rows are in `audit/source_contribution.csv`.

**Composition.** [WWWSHARE] of the hostnames are `www.` forms of a registrable. They are distinct
valid hostnames under your rule and sit in their own files, so they merge or drop as a block.

## 3. Evidentiary standard

- One record is one machine-written observation of that name in that year. For capture-backed
  sources it is the Internet Archive's 14-digit timestamp of a capture on that exact host, quoted
  with its replay URL in `additions/evidence_manifest.csv` and
  `hostnames/hostnames_evidence_manifest.csv`, so any line can be opened.
- `domain_year.evidence_id` and `hostname_year.evidence_id` are `NOT NULL` foreign keys: no year
  without an observation. Fifteen invariants check this before every commit and inside the archive.
- Master-eligible classes: [MASTERTYPES]. `link_target` never dates a year. Anything a human typed
  needs a second source to date that domain first. A creation date attests its own year only.
- A hostname must sit beneath a held registrable, be RFC 1123 valid, and its parent earns the same
  year from the same capture.
- **[CANDIDATES] domains carry no year evidence** and ship as `candidates.txt`, none in an annual
  file; [POOL_RESTRICTED] of them are under `.edu`, `.gov` or `.mil`.

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
  per source family and version. [DATASETS_SEARCHED]
- **Measured negatives that steer the next cycle**: prose corpora fail either the URL-density or
  the authority screen; academic repositories closed by enumeration through five APIs and two
  registries; CD-ROM media, FTP mirrors and trade directories at the curated-directory floor
  (0.013-0.024 net-new pairs per listed name). Each with its figure in `sources.md`.

## 5. CDX execution notes

- Two clients at most, honest User-Agent, two seconds between requests, backoff on 429/503/504,
  `Retry-After` honoured. Collectors take an absolute deadline and outlive the session.
- Per-domain queries over bracketed gaps and the candidate pool: [CDXBULK] registrable pairs.
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

[MERGE_RECONCILIATION]

## 8. Reproduction and the four requested artifacts

`README.md` in the archive gives the order: `masters/`, `additions/`, `hostnames/`,
`candidates.txt`, `provenance/*.parquet` (every assignment joined to its evidence row), `logs/`.
[REPRODUCTION_RESULT]

| | asked for | where it is |
|----|------------------|------------------------------------------|
| **D1** | runnable code, dependencies, instructions | `source/source.tar.gz` at `source/COMMIT.txt`, with `pyproject.toml` and `uv.lock`; its `README.md` names what every command prints. The research loop of section 4 is `source/fleet.tar.gz`: workflows, prompts, policy and the hypothesis register with every verdict |
| **D2** | experience summary | `experience-summary.md`, distilled from `sources.md` |
| **D3** | merge and dedup code, overlap, reconciliation | section 7, `source/scripts/round/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your program vendored unmodified, explained in `metric-explained.md` |

`verify.sh` runs ten checks inside a fresh extraction, including all four.
