# Internet Digital Ark: round 7

Additions to the 1996-2001 annual lists, measured against `merged260901`. Every figure is generated
from the evidence store, so no table here can disagree with the files shipped beside it. This is a
summary: `sources.md` holds the per-source receipts, `experience-summary.md` the yields and
directions, `README.md` the reproduction route, `metric-explained.md` the metric.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 33,848,926 |
| 2. Equivalent-English total | 17,770,588.9026 |
| 3. Increment | **26,224,274** records |
| 4. Equivalent-English increment | **13,670,342.8300** |
| 5. Equivalent-English growth rate | **76.9268%** |

625,385 records (329,397.2492 EE) are registrable domains in `additions/`, the unit you asked me to
prioritize; 25,598,889 (13,340,945.5808 EE) are valid hostnames beneath them in `hostnames/`. The two are
disjoint in every year, neither is in the baseline, your validator rejects none of them, and the
second set can be merged or discarded as a block.

| Year | Registrables | Hostnames | Equivalent-English added |
|------|-----------:|-----------:|--------------:|
| 1996 | 8,869 | 7,742,554 | 4,156,305.3362 |
| 1997 | 18,116 | 10,781,639 | 5,263,433.0010 |
| 1998 | 23,025 | 999,412 | 574,071.3613 |
| 1999 | 46,776 | 1,458,019 | 828,029.6155 |
| 2000 | 27,630 | 1,661,393 | 937,279.6350 |
| 2001 | 500,969 | 2,955,872 | 1,911,223.8810 |
| **Total** | **625,385** | **25,598,889** | **13,670,342.8300** |

**Score, by both rules in your brief.** Cumulative verified percentage **125.7295%**, time-weighted **S = 919.90** at `10 p/t`, this round counted at its own unverified 76.9268%. Per round (1: 17.3800% / 5d = 34.76; 3: 1.6600% / 1d = 16.60; 4: 10.7310% / 6d = 17.88; 5: 14.9011% / 2d = 74.51; 6: 4.1307% / 6d = 6.88; 7: 76.9268% / 1d = 769.27), round 1 on records. The elapsed days are reconstructed from your release and receipt timestamps: they reproduce the S = 6.88 you quoted for round 6, but the set is yours to confirm.

## 2. What one hostname record is

Three conditions, all enforced in code (`source/src/ark/hostnames.py`, `checks.py`), not by
convention:

1. **RFC 1123 valid**: letters, digits and hyphens only, no leading or trailing hyphen in a label,
   at least two labels. Underscore names, IP literals and `in-addr.arpa` forms are refused.
2. **Strictly beneath a registrable this project already holds for that same year.** The parent is
   a foreign key, so a hostname cannot exist here without its registrable existing there, and a
   bare registrable is never a hostname record. No name is counted in both units.
3. **Its own machine-written observation in that year**, on that exact host.

## 3. What is new this round, and why it is admissible

One idea, applied to seven artifact families: **when you accepted hostnames, the payload was a
column of an artifact already on disk that the registrable unit had discarded.** Five of the seven
needed no new request, and most carried a written closure from an earlier round.

| Source | What dates one record | Records | EE |
|-----------------------------|--------------------------------------------------|--------:|-------:|
| ISC Internet Domain Survey host files | the survey's `YYMM` edition code in the artifact path | 18,117,395 | 9,167,369 |
| NYPW TimeMaps | the row's 14-digit capture timestamp | 4,039,562 | 2,097,955 |
| IA domain-wide CDX sweeps | the row's 14-digit capture timestamp | 2,161,296 | 1,378,051 |
| IA Early Web index | the row's 14-digit capture timestamp | 1,163,616 | 631,148 |
| USFEDGOV merged indexes | the row's 14-digit capture timestamp | 40,260 | 39,340 |
| RIPE `nserver:` hosts | the dump's generation stamp and each object's `changed:` line | 49,841 | 11,780 |
| registrable domains, all lanes | per record in `additions/evidence_manifest.csv` | 625,385 | 329,397.2492 |

Every stamp above is machine-written and inside the artifact, so no human judgement dates a year;
each class was already master-eligible for those exact bytes; the terms were read in full before
each fetch. On the survey you ruled in writing on 2026-07-24 that a dated DNS survey may enter the
annual files directly. Route, licence and per-TLD yield per source are in `sources.md`.

**Two disclosures decide what the hostname half is worth**, each one filter on
`hostnames/hostnames_evidence_manifest.csv`: 65% of the largest source's records
are dialup or numbered workstation names (`pc50.btbcs.bt.co.uk`), which answered its reverse-DNS
walk in the month it stamps and pass your validity rule but are not sites; and 26.1% of all
hostnames are `www.` forms of registrables you already hold, full weight under the rule as written
and nothing if your calculator normalises `www.` away.

The evidentiary standard is unchanged: one record is one machine-written observation of that name in
that year, `evidence_id` is a `NOT NULL` foreign key on both units, fifteen invariants enforce it
before every commit and inside the archive, `link_target` never dates a year, human-typed names take
the corroboration split, and a creation date attests its own year only. 2,419,436 domains carry
no in-window evidence, ship as `candidates.txt` and reach no annual file.

## 4. What became autonomous since round 6

Round 6 ran unattended for hours but a person judged every source. This round the loop closes, and
its code, prompts, policy and full hypothesis register with every verdict ship as
`source/fleet.tar.gz`.

- **Five scheduled workflows on a self-hosted runner**: a generator writes hypotheses, each with a
  yield floor and a kill screen; researcher waves test them in parallel; a re-opener re-reads closed
  verdicts when a screen changes; an improver changes one prompt or model knob per pull request so
  effects stay attributable. **494 source families searched and recorded** in `sources.md`: 66 developed, 428 evaluated and closed with the measurement that closed them, so the same ground is not broken twice.
- **Admission without a human, under a rule fixed in advance**: a source banks only if its class is
  already master-eligible, a machine stamp inside the artifact dates each item, the terms were read
  in full and the invariants pass. Eight sources banked that way this round; two parked for a
  written decision, one on terms and one on a class question. No agent may write the store: a
  separate admitter re-derives every figure locally first, and two agent-reported figures lost to
  that check.
- **The re-opener earned its lane**: it recovered the NYPW TimeMaps from a 14 EE closure by
  measuring the ingest ledger per folder (year rows per million: 2000 ~24,000, 1999 ~10,000, 2001
  exactly 4), ~88,000 EE that a human closure had written off.
- **CDX execution**: two clients at most, honest User-Agent, two seconds between requests,
  `Retry-After` honoured, absolute deadlines that outlive a session. Sweeps write raw
  `{url, timestamp}` journals, which is why the same bytes could be re-read under the new unit. A
  page costs about the same at 200 index blocks as at 10,000, so the sweep walks 10,000-block pages;
  one outage refused thirteen parents and they were requeued, not skipped. Per-domain gap queries
  contributed 92,479 registrable pairs.

## 5. Limitations, and where the room is

A capture proves presence and never absence, so a year without one is unevidenced rather than empty,
and both dating routes therefore err toward omission. The exception is the counting unit itself: a
hostname is valid under your rule and a reverse-DNS walk resolves dialup ports as readily as web
servers, which is disclosed per source above rather than argued about. The units ship separately, so
dropping the hostname files leaves the registrable round intact at 329,397.2492 EE.

Worth expanding, in order: the same one-level-down reading of every other banked artifact that names
hosts, since DNS, mail and mirror rosters hold hosts a web crawler never fetched; the second-level
suffix namespaces at hostname grain, where `co.uk` alone is 3.39M index blocks and 1.2% walked; the
ranked subdomain platforms still queued, resumable from `audit/source_saturation_ledger.csv`.
Measured and closed: prose corpora, academic repositories, CD-ROM media, FTP mirrors, trade
directories. The figures behind each verdict are in `experience-summary.md`.

## 6. Merge, overlap and reconciliation (D3)

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260901` | 33,848,926 | 17,770,588.9026 |
| **accepted increment** | **26,224,274** | **13,670,342.8300** |
| post-merge total | 60,073,200 | 31,440,931.7326 |

Overlap with the baseline is **0 records**, so all 26,224,274 submitted count once, and **28 of 28 reconciliation checks pass**. `merge_against_baseline.py` unions both units into the baseline, deduplicates on the lowercased line within each year and scores every file with your own calculator; the per-check verdicts are in `audit/merge_audit_ark_*.json` and the per-year form in `audit/merge_stats_ark_*.csv`, in your column names.

## 7. Reproduction, and the four artifacts

`README.md` in the archive gives the route and the file map. Before sending, a fresh extraction of this archive was put through that route: all eleven `verify.sh` checks pass, and the tier-2 rebuild from `provenance/` reproduces every per-year count, passes the fifteen invariants and returns all twenty-one result files byte-identical to the ones shipped. Tier 3, the full replay, was not run: about 50 GB, with five journal sets held out of the archive on size.

**D1** runnable code, dependencies and instructions: `source/source.tar.gz` at `source/COMMIT.txt`,
with the research loop as `source/fleet.tar.gz`. **D2** experience summary: `experience-summary.md`.
**D3** merge and dedup code, overlap and reconciliation: section 6 and `audit/`. **D4** runnable
metric code: `equivalent_english_domain_calculator/`, your program vendored unmodified, explained in
`metric-explained.md`.
