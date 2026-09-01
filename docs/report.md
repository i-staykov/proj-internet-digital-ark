# Internet Digital Ark: round 7

Additions to the 1996-2001 annual lists against `merged260901`, scored with your calculator. Every
figure below is generated from the evidence store when the archive is built, so no table here can
disagree with the files beside it.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 33,848,926 |
| 2. Equivalent-English total | 17,770,588.9026 |
| 3. Increment | **5,496,283** records |
| 4. Equivalent-English increment | **3,078,203.9386** |
| 5. Equivalent-English growth rate | **17.3219%** |

The counting unit is your calculator's: one distinct valid hostname per year, at its TLD's English
share. The increment is two disjoint files per year, both scored above and both absent from the
baseline; your validator rejects no record in either.

| Unit | Files | Records | Equivalent-English | Growth |
|------------------------------|-------------------|---------:|-------------:|-------:|
| registrable domains, prioritized as you asked | `additions/NNNN.txt` | 623,835 | 328,715.1485 | 1.8498% |
| valid hostnames beneath registrables, accepted 2026-09-01 | `hostnames/NNNN_hostnames.txt` | 4,872,448 | 2,749,488.7901 | 15.4721% |

46,116 of the registrables appear in none of your six files in any year.

| Year | merged260901 | Registrables | Hostnames | Merged | Equivalent-English added |
|------|------------:|-----------:|-----------:|------------:|--------------:|
| 1996 | 979,994 | 8,864 | 79,143 | 1,068,001 | 52,640.8323 |
| 1997 | 2,161,231 | 18,019 | 156,413 | 2,335,663 | 101,217.1697 |
| 1998 | 3,119,897 | 22,997 | 523,333 | 3,666,227 | 313,157.8930 |
| 1999 | 6,345,942 | 46,194 | 823,132 | 7,215,268 | 496,234.0371 |
| 2000 | 10,705,102 | 27,486 | 1,459,870 | 12,192,458 | 813,656.2976 |
| 2001 | 10,536,760 | 500,275 | 1,830,557 | 12,867,592 | 1,301,297.7089 |
| **Total** | **33,848,926** | **623,835** | **4,872,448** | **39,345,209** | **3,078,203.9386** |

**Cumulative.** Summing the increases you have awarded, which is how the update log of 2026-08-18 defines the score: 1.659986%, 10.730988%, 14.901054%, 4.130718% and this round's 17.3219% give **48.7446%**, with round 1's 1,429,524 records held out because it was awarded at 17.38% on records before the equivalent-English metric existed.

## 2. Where the additions come from, and what dates each record

Ranked by equivalent-English (EE); sources under 1,000 EE share one row. Full per-source figures,
including files ingested and evidence rows, are in `audit/source_contribution.csv`.

| Source, unit | Artifact, and how it was obtained | What dates one record | Records | EE |
|--------------|--------------------------|----------------------|--------:|-------:|
| `nypw_timemap_hostgrain`, hostname | NYPW TimeMaps (IA, CC BY 4.0), 34 parts held since round 6, re-read at hostname grain | the row's own 14-digit capture timestamp | 4,039,562 | 2,097,955 |
| `ia_cdx_domain_sweep`, hostname | IA CDX `matchType=domain` sweeps of `.uk` suffixes and subdomain platforms, raw journals | the row's own 14-digit capture timestamp | 832,886 | 651,534 |
| `nypw_timemaps`, registrable | NYPW TimeMaps, 34 parts, reopened after a 14 EE closure on the 1996 folder | the row's own 14-digit capture timestamp | 329,667 | 143,789 |
| `ia_cdx_bulk`, registrable | IA CDX per-domain queries over bracketed gaps and the candidate pool | the capture timestamp of a URL on that host | 92,479 | 66,566 |
| `usenet_address`, registrable | Usenet archives (IA), sender and body addresses | the post's `Date:` header, corroborated by a second source | 67,145 | 39,232 |
| `usenet_announce`, registrable | Usenet site announcements (IA) | the post's `Date:` header, corroborated by a second source | 36,486 | 18,569 |
| `usenet_bare`, registrable | Usenet archives (IA), bare hostnames in bodies | the post's `Date:` header, corroborated by a second source | 19,387 | 13,587 |
| `chastity_list_blacklist`, registrable | Chastity filter blacklist tarball, 2001 | tar member headers `Dec 14 2001` and dated diff filenames | 21,175 | 12,038 |
| `mynic_my_change_report`, registrable | MYNIC `.my` fortnightly change reports (IA) | the per-day heading over each `New`/`Delete` entry | 9,070 | 6,875 |
| `nypw_timemaps_nonok`, registrable | same files, rows with a non-200 status the parser used to discard | the row's own 14-digit capture timestamp | 13,277 | 6,680 |
| `coza_deletion_listing`, registrable | CO.ZA registry deletion shortlists (IA) | the capture stamp on a registry page naming live names | 3,826 | 3,704 |
| `jeb_bush_gubernatorial_email`, registrable | Florida governor's office e-mail export | the mail client's own `Sent:` line | 5,259 | 3,271 |
| `early_bulk_whois_snapshot`, registrable | early bulk whois transcriptions (Berkman) | the registry creation date in the record, that year only | 4,435 | 2,777 |
| `cctld_register_listing_capture`, registrable | ccTLD register listings `.mt`, `.sa` and others (IA) | the capture stamp on the registry's own register page | 6,620 | 2,426 |
| `junkfilter_dated_blocklist`, registrable | junkfilter blocklist releases 1997-2001 | `Last-Modified`, in-body `$Id` and tar member stamps agreeing | 3,407 | 2,104 |
| `granitecanyon_zone_rejects`, registrable | Granite Canyon public DNS rejected-zone lists (IA) | the list's own generation stamp, e.g. `7-May-2001 22:11 GMT` | 3,039 | 1,698 |
| `urlmerchant_inventory`, registrable | URLMerchant domain broker inventory (IA) | the page's own `META UPDATED` generator stamp | 2,513 | 1,564 |
| `fac_single_audit`, registrable | Federal Audit Clearinghouse single-audit data | the row's `AUDITEEDATESIGNED`, corroborated by a second source | 1,981 | 1,320 |
| 10 further sources | each under 1,000 EE, listed in `audit/source_contribution.csv` | | 4,069 | 2,515 |
| **Total** | | | **5,496,283** | **3,078,204** |

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
same bytes worth most of the 2,749,488.7901 equivalent-English in the hostname unit, with no new request.
The rest is one night of `matchType=domain` sweeps over the subdomain platforms your own benchmark
proves dense (`rank_platform_parents.py`: `cjb.net` leads at 157,790 sub-hosts held, then
`demon.co.uk`, `freeserve.co.uk`); `cjb.net` is marked incomplete in the saturation ledger and resumes.

**Composition, disclosed.** 93.6% of the hostnames are `www.` forms of a registrable. They are
distinct valid hostnames under your rule and score at full weight, and they sit in their own files so
you can merge or discard them as a block. The parent registrables of the same captures are in
`additions/` on their own evidence.

**CDX execution.** Two clients at most, one per slot, honest User-Agent, two seconds between
requests, backing off on 429/503/504 and honouring `Retry-After`. Per-domain queries over a
bracketed-gap population and the candidate pool added 92,479 registrable pairs. Domain-wide
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
  Master-eligible classes are `artifact_listing`, `cdx_timestamp`, `dated_directory`, `link_source`, `whois_creation`. Anything a human typed is candidate-only until
  another source dates that domain first, and `link_target` never dates a year.
- **Saturation ledger**, as your 2026-08-31 update asks: `audit/source_saturation_ledger.csv`,
  one row per source family and version, with coverage, what dates one item, limitations and
  the decision. **465 source families have been searched and recorded**, 60 developed far enough to earn their own section and 405 evaluated and closed, each with the measurement that closed it, so negative results stay visible and the same ground is not broken twice. `sources.md` ships beside this report and names every one, with its acquisition route, date semantics and yield.
- **2,419,546 domains carry no year evidence** and ship as `candidates.txt`, none in an
  annual file; 588,087 of them are under `.edu`, `.gov` or `.mil`.

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

`merge_against_baseline.py` unions both units into the current baseline,
deduplicated on the lowercased line within each year, and scores every file with your
own calculator. Per-year form in `audit/merge_stats_ark_*.csv`, in your column names
so the two audits diff directly.

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260901` | 33,848,926 | 17,770,588.9026 |
| **accepted increment** | **5,496,283** | **3,078,203.9386** |
| post-merge total | 39,345,209 | 20,848,792.8412 |

**Overlap with the baseline is 0 records**, so all 5,496,283 submitted are accepted and nothing counts twice; the registrable and hostname files are disjoint in every year.

**28 of 28 reconciliation checks pass.** All are arithmetic
identities, so a failure would be a defect rather than a finding: per year that
`baseline_unique + accepted_new == merged_unique` and that the two unit files are
disjoint and sum to the submitted count, that the per-year increments sum
to the headline, and that a freshly measured baseline reproduces the totals this
round was measured against. Each is listed with its verdict in
`audit/merge_audit_ark_*.json`.

## 6. Reproduction, and the four requested artifacts

`README.md` in the archive gives the order. `masters/` and `additions/` hold the merged annual lists
and the registrable increment, `hostnames/` the hostname increment, `candidates.txt` the undated
names, `provenance/*.parquet` every assignment joined to its evidence row, and `logs/` the
collectors' logs. A fresh copy of this archive was extracted and put through the route above before sending. Every one of
the ten checks in `verify.sh` passes, and the tier-2 rebuild from `provenance/` returns every per-year
count exactly, with all fifteen invariants passing and all twenty-one result files (six annual additions,
six hostname files, six masters, two evidence manifests, the candidate list) byte-identical to the ones
shipped here. The first rehearsal of this build caught a defect: run from inside the archive, the
hostname export resolved the baseline through a repository-only path and rebuilt every hostname as
net-new; it was fixed and the rehearsal rerun. Tier 3 was not run: it is a roughly 50 GB download, and
five journal sets are held out of this archive on size, so it would replay every source but those.

| | asked for | where it is |
|----|------------------|------------------------------------------|
| **D1** | runnable code, dependencies, instructions | `source/source.tar.gz` at the commit in `source/COMMIT.txt`, with `pyproject.toml` and `uv.lock`; its `README.md` names what every command should print |
| **D2** | experience summary | `experience-summary.md`, distilled from `sources.md`, which carries every rejection with the measurement that closed it |
| **D3** | merge and dedup code, overlap, reconciliation | section 5, `source/scripts/round/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your own program vendored unmodified, explained in `metric-explained.md` |

`verify.sh` runs ten checks inside a fresh extraction, including all four, so none can ship unmet.
