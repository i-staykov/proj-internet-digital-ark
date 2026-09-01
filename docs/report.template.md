# Internet Digital Ark: round [ROUND]

Additions to the 1996-2001 annual lists against `[BASELINE]`, scored with your calculator. Every
figure below is generated from the evidence store when the archive is built, so no table here can
disagree with the files beside it.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

The counting unit is your calculator's: one distinct valid hostname per year, at its TLD's English
share. The increment is two disjoint files per year, both scored above and both absent from the
baseline; your validator rejects no record in either.

| Unit | Files | Records | Equivalent-English | Growth |
|------------------------------|-------------------|---------:|-------------:|-------:|
| registrable domains, prioritized as you asked | `additions/NNNN.txt` | [REGPAIRS] | [REGEE] | [REGGROWTH] |
| valid hostnames beneath registrables, accepted 2026-09-01 | `hostnames/NNNN_hostnames.txt` | [HOSTPAIRS] | [HOSTEE] | [HOSTGROWTH] |

[NEWDOMAINS] of the registrables appear in none of your six files in any year.

[PER_YEAR_TABLE]

[CUMULATIVE]

## 2. Where the additions come from, and what dates each record

Ranked by equivalent-English (EE); sources under 1,000 EE share one row. Full per-source figures,
including files ingested and evidence rows, are in `audit/source_contribution.csv`.

[ATTRIBUTION_TABLE]

**Why a record is valid.** Every record is one machine-written observation of that name in that
year. For the capture-backed sources it is the Internet Archive's 14-digit timestamp of a capture
of a URL on that exact host, quoted in the evidence value with the replay URL beside it in
`additions/evidence_manifest.csv` and `hostnames/hostnames_evidence_manifest.csv`, so any line can
be opened. A hostname must sit beneath a registrable the store holds, be RFC 1123 valid, and its
parent earns the same year from the same capture. `domain_year.evidence_id` and
`hostname_year.evidence_id` are `NOT NULL` foreign keys, so no year exists without an observation;
fifteen invariants check this before every commit and again inside the archive.

**The method behind most of it: re-price what is already on disk when the unit changes.** Until
2026-09-01 the pipeline collapsed every hostname to its registrable, and two artifacts stood
recorded as spent: the NYPW TimeMaps (34 parts, CC BY 4.0) had paid their registrable pairs, and 180
domain-wide CDX sweep journals from 2026-08-21..24 were logged as worth exactly 0, since
`www.foo.co.uk` collapsed onto a `foo.co.uk` already held. Your acceptance of hostnames made the
same bytes worth most of the [HOSTEE] equivalent-English in the hostname unit, with no new request.
The rest is one night of `matchType=domain` sweeps over the subdomain platforms your own benchmark
proves dense (`rank_platform_parents.py`: `cjb.net` leads at 157,790 sub-hosts held, then
`demon.co.uk`, `freeserve.co.uk`); `cjb.net` is marked incomplete in the saturation ledger and resumes.

**Composition, disclosed.** [WWWSHARE] of the hostnames are `www.` forms of a registrable. They are
distinct valid hostnames under your rule and score at full weight, and they sit in their own files so
you can merge or discard them as a block. The parent registrables of the same captures are in
`additions/` on their own evidence.

**CDX execution.** Two clients at most, one per slot, honest User-Agent, two seconds between
requests, backing off on 429/503/504 and honouring `Retry-After`. Per-domain queries over a
bracketed-gap population and the candidate pool added [CDXBULK] registrable pairs. Domain-wide
sweeps use `matchType=domain` at 200 rows a page and write raw `{url, timestamp}` lines to a
journal, so the same bytes can be re-read under a new rule, which is what paid this round. Errors met
and handled: HTTP 400 past the last page, which ends a sweep cleanly; a page-count call that timed out
on `cjb.net`, so that platform is ledgered incomplete and resumable; and transport failures, retried
with a widening delay. Collectors take an absolute deadline and outlive the session.

## 3. Method and automation this round

- **The loop left the laptop.** Research runs unattended as scheduled workflows on a self-hosted
  runner: a generator lane proposes hypotheses (the hostname-grain re-read of the NYPW TimeMaps,
  this round's largest source, was one of its seven first proposals), researcher waves test them
  in parallel, a re-opener re-reads closed verdicts
  whenever a screen changes, and an improver lane adjusts prompts and model choice from per-run
  telemetry, one change per pull request. The re-opener found the NYPW TimeMaps: closed at 14
  equivalent-English on the 1996 folder, then measured folder by folder from the ingest ledger
  (year rows per million: 2000 ~24,000, 1999 ~10,000, 2001 exactly 4) for ~88,000 more. A
  partitioned corpus is measured per partition, never argued about.
- **Admission without a human, under a standing rule.** A source is banked when its evidence
  class is already master-eligible, a machine stamp inside the artifact dates each item, the terms
  were read in full, and the invariants pass; anything else parks until a written decision.
  Master-eligible classes are [MASTERTYPES]. Anything a human typed is candidate-only until
  another source dates that domain first, and `link_target` never dates a year.
- **Saturation ledger**, as your 2026-08-31 update asks: `audit/source_saturation_ledger.csv`,
  one row per source family and version, with coverage, what dates one item, limitations and
  the decision. [DATASETS_SEARCHED]
- **[CANDIDATES] domains carry no year evidence** and ship as `candidates.txt`, none in an
  annual file; [POOL_RESTRICTED] of them are under `.edu`, `.gov` or `.mil`.

## 4. Limitations, and what is worth expanding

A capture proves presence and never absence, so a year without one is unevidenced rather than
empty, and a creation date attests one year only. Neither route can invent a year; the mistake they
can make is omission. The hostname unit rewards platforms with many sub-hosts, so its per-year
figures are dominated by 2000 and 2001, where the archive is densest.

**Worth expanding, in order.** The remaining ranked platforms and suffixes, resumable from the
ledger. Re-reading every capture-bearing artifact already held at hostname grain, since that paid
without a request. Registrable discovery stays the priority you set: generated sibling names over
registry data and bracketed-gap CDX queries continue at a measured, plannable rate. **Less
promising, measured**: prose corpora, academic repositories, CD-ROM media, FTP mirrors and trade
directories; each closure and its measurement is in `sources.md`.

## 5. Merge, overlap and reconciliation (D3)

[MERGE_RECONCILIATION]

## 6. Reproduction, and the four requested artifacts

`README.md` in the archive gives the order. `masters/` and `additions/` hold the merged annual lists
and the registrable increment, `hostnames/` the hostname increment, `candidates.txt` the undated
names, `provenance/*.parquet` every assignment joined to its evidence row, and `logs/` the
collectors' logs. [REPRODUCTION_RESULT]

| | asked for | where it is |
|----|------------------|------------------------------------------|
| **D1** | runnable code, dependencies, instructions | `source/source.tar.gz` at the commit in `source/COMMIT.txt`, with `pyproject.toml` and `uv.lock`; its `README.md` names what every command should print |
| **D2** | experience summary | `experience-summary.md`, distilled from `sources.md`, which carries every rejection with the measurement that closed it |
| **D3** | merge and dedup code, overlap, reconciliation | section 5, `source/scripts/round/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your own program vendored unmodified, explained in `metric-explained.md` |

`verify.sh` runs ten checks inside a fresh extraction, including all four, so none can ship unmet.
