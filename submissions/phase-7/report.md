# Internet Digital Ark: round 7

Increment to the 1996-2001 annual lists against `merged260901`, scored with your calculator. Every
figure is generated from the evidence store when the archive is built. This is the summary; the
receipts sit in the archive, one document per purpose, named here where relevant.

## 1. Results

| | |
|---|--:|
| Total original domain-year records 1996-2001 | 33,848,926 |
| Equivalent-English total | 17,770,588.9026 |
| Increment | **26,224,274** records |
| Equivalent-English increment | **13,670,342.8300** |
| Equivalent-English growth rate | **76.9268%** |

Two disjoint units, neither present in the baseline and none rejected by your validator:
625,385 records (329,397.2492 EE) are registrable domains in `additions/NNNN.txt`, the unit you asked
me to prioritize, and 25,598,889 (13,340,945.5808 EE) are valid hostnames beneath them in
`hostnames/NNNN_hostnames.txt`, so the second set can be merged or discarded as a block.

| Year | merged260901 | Registrables | Hostnames | Merged | Equivalent-English added |
|------|------------:|-----------:|-----------:|------------:|--------------:|
| 1996 | 979,994 | 8,869 | 7,742,554 | 8,731,417 | 4,156,305.3362 |
| 1997 | 2,161,231 | 18,116 | 10,781,639 | 12,960,986 | 5,263,433.0010 |
| 1998 | 3,119,897 | 23,025 | 999,412 | 4,142,334 | 574,071.3613 |
| 1999 | 6,345,942 | 46,776 | 1,458,019 | 7,850,737 | 828,029.6155 |
| 2000 | 10,705,102 | 27,630 | 1,661,393 | 12,394,125 | 937,279.6350 |
| 2001 | 10,536,760 | 500,969 | 2,955,872 | 13,993,601 | 1,911,223.8810 |
| **Total** | **33,848,926** | **625,385** | **25,598,889** | **60,073,200** | **13,670,342.8300** |

| round | verified % | days | time-weighted |
|---|--:|--:|--:|
| 1 (on records) | 17.3800 | 5 | 34.76 |
| 3 | 1.6600 | 1 | 16.60 |
| 4 | 10.7310 | 6 | 17.88 |
| 5 | 14.9011 | 2 | 74.51 |
| 6 | 4.1307 | 6 | 6.88 |
| 7 (this round) | 76.9268 | 1 | 769.27 |
| **cumulative** | **125.7295%** | | **919.90** |

Cumulative verified percentage **125.7295%** and time-weighted score **919.90**, by the two rules in your brief update, this round included at its own unverified 76.9268%. Round 1 is in the percentage sum although it was awarded on records. The days are reconstructed from your own release and receipt timestamps and reproduce the S = 6.88 you quoted for round 6, but the whole set is subject to your confirmation.

## 2. What counts as one record

- **Registrable domains**: extracted with a vendored Public Suffix List snapshot, so `bbc.co.uk` is
  registrable and `co.uk` is not, identically on any machine. Lowercased, IDN punycoded, ports and
  trailing dots dropped.
- **Hostnames**: RFC 1123 valid (letters, digits, hyphens; no leading or trailing hyphen in a label;
  at least two labels), sitting strictly beneath **a registrable this project holds for that same
  year**, which is enforced as a foreign key and not as a naming convention, and carrying their own
  machine-written observation in that year. A bare registrable is never a hostname record and no
  name is counted in both units.
- **Dropped, not salvaged**: underscore names (era NT servers), IP literals, names whose TLD did not
  exist that year, `in-addr.arpa` forms. Refused at ingest and counted in `audit/`.
- 2,419,436 domains carry no in-window year evidence, ship as `candidates.txt` and appear in no
  annual file; 588,081 of them are under `.edu`, `.gov` or `.mil`.

## 3. What is new, and why it is admissible

One idea applied six times: **when the counting unit changed, the payload was a column of an
artifact already on disk that the old unit had discarded.** Four of the six needed no new request.

| Source | Records | EE | What dates one record |
|---------------------------|--------:|-------:|-----------------------------------|
| ISC Internet Domain Survey per-TLD host files | 18,117,395 | 9,167,369 | the survey's own `YYMM` edition code in the artifact path |
| NYPW TimeMaps at hostname grain | 4,039,562 | 2,097,955 | the row's own 14-digit capture timestamp |
| IA domain-wide CDX sweeps over subdomain platforms | 2,161,296 | 1,378,051 | the row's own 14-digit capture timestamp |
| IA Early Web index at hostname grain | 1,163,616 | 631,148 | the row's own 14-digit capture timestamp |
| USFEDGOV merged CDX indexes, 1996-2001 | 40,260 | 39,340 | the row's own 14-digit capture timestamp |
| RIPE `domain:` objects, their `nserver:` hosts | 49,841 | 11,780 | the dump's generation stamp and each object's `changed:` line |
| registrable domains, all lanes | 625,385 | 329,397.2492 | as `additions/evidence_manifest.csv` states per record |

Every row rests on the same three grounds: the stamp that dates an item is machine-written and sits
**inside** the artifact, so no human judgement dates a year; the class was already master-eligible
for those exact bytes; the terms were read in full before the first request. On the survey you ruled
in writing on 2026-07-24 that a dated DNS survey may enter the annual files directly. Route,
licence, per-year and per-TLD yield are in `sources.md` and `audit/source_contribution.csv`.

**Two disclosures decide what the hostname half is worth**, each a single filter on
`hostnames/hostnames_evidence_manifest.csv`: 65% of the largest source's records
are dialup or numbered workstation names (`pc50.btbcs.bt.co.uk`), which answered its reverse-DNS
walk in the month it stamps and pass your validity rule but are not sites; and 26.1% of all
hostnames are `www.` forms of registrables you already hold, worth full weight under the rule as
written and nothing if your calculator normalises `www.` away.

## 4. Evidentiary standard

Unchanged. One record is one machine-written observation of that name in that year, quoted with its
replay URL or artifact identifier in the evidence manifests so any line can be opened; `evidence_id`
is a `NOT NULL` foreign key on both units and fifteen invariants enforce it before every commit and
again inside the archive. Master-eligible classes: `artifact_listing`, `cdx_timestamp`, `dated_directory`, `link_source`, `whois_creation`. `link_target` never dates a year,
anything a human typed needs a second source to date that domain first, and a creation date attests
its own year only. `metric-explained.md` states the counting unit and the weights.

## 5. What was built since round 6

Round 6 proposed sources and a person judged each one. This round the loop closes.

- **Five scheduled workflows on a self-hosted runner**: a generator writes hypotheses, each with a
  yield floor and a kill screen; researcher waves test them in parallel against a read-only copy of
  the store; a re-opener re-reads closed verdicts when a screen changes; an improver changes one
  prompt or model knob per pull request so effects stay attributable. **494 source families searched and recorded** in `sources.md`: 66 developed, 428 evaluated and closed with the measurement that closed them, so the same ground is not broken twice.
- **Admission without a human, under a rule fixed in advance**: a source banks only if its class is
  already master-eligible, a machine stamp inside the artifact dates each item, the terms were read
  in full and the invariants pass. Six banked that way; two parked for a written decision, one on
  terms and one on a class question. No agent can write the store: an admitter re-derives every
  figure locally first.
- **The re-opener paid for itself**: it recovered the NYPW TimeMaps from a 14 EE closure by measuring
  the ingest ledger per folder (year rows per million: 2000 ~24,000, 1999 ~10,000, 2001 exactly 4),
  worth ~88,000 EE that a human closure had written off.
- **CDX execution**, per your standing request: two clients at most, honest User-Agent, two seconds
  between requests, `Retry-After` honoured, backoff on 429/503/504, absolute deadlines that outlive
  a session. Sweeps write raw `{url, timestamp}` journals, which is why the same bytes could be
  re-read under the new unit. A page costs about the same at 200 index blocks as at 10,000, so the
  sweep now walks 10,000-block pages; one outage refused thirteen parents and they were requeued,
  not skipped. Per-domain gap queries contributed 92,479 registrable pairs.

Code, prompts, policy and the hypothesis register with every verdict ship as `source/fleet.tar.gz`.

## 6. Limitations, and where the room is

**A hostname is not a site**: a reverse-DNS walk resolves dialup ports as readily as web servers,
and that is where most of this round's records come from, quoted per source so it can be cut. **A
capture proves presence, never absence**: a year without one is unevidenced, not empty. **The units
are disjoint**, so discarding the hostname files leaves the registrable round intact at 329,397.2492 EE.

Worth expanding, in order: the same one-level-down reading of every other banked artifact that names
hosts, since DNS, mail and mirror rosters hold hosts a web crawler never fetched; the second-level
suffix namespaces at hostname grain, where `co.uk` alone is 3.39M index blocks and 1.2% walked; the
ranked subdomain platforms still queued, resumable from `audit/source_saturation_ledger.csv`.
Measured and closed: prose corpora, academic repositories, CD-ROM media, FTP mirrors, trade
directories, with the figures in `experience-summary.md`.

## 7. Merge, overlap and reconciliation (D3)

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260901` | 33,848,926 | 17,770,588.9026 |
| **accepted increment** | **26,224,274** | **13,670,342.8300** |
| post-merge total | 60,073,200 | 31,440,931.7326 |

- Overlap with the baseline: **0 records**, so all 26,224,274 submitted count once; the two unit files are disjoint in every year.
- **28 of 28 reconciliation checks pass** (per-year `baseline_unique + accepted_new == merged_unique`, unit files disjoint and summing to the submitted count, per-year increments summing to the headline, baseline re-measured). Verdicts in `audit/merge_audit_ark_*.json`, per-year form in `audit/merge_stats_ark_*.csv` in your column names.
- Method: `merge_against_baseline.py` unions both units into the baseline, deduplicated on the lowercased line within each year, and scores every file with your own calculator.

## 8. Reproduction, and the four requested artifacts

`README.md` in the archive gives the route and the file map; this is the result of running it.
Before sending, a fresh extraction of this archive was put through that route: all eleven `verify.sh` checks pass, and the tier-2 rebuild from `provenance/` reproduces every per-year count, passes the fifteen invariants and returns all twenty-one result files byte-identical to the ones shipped. Tier 3, the full replay, was not run: about 50 GB, with five journal sets held out of the archive on size.

| | asked for | where it is |
|----|------------------|------------------------------------------|
| **D1** | runnable code, dependencies, instructions | `source/source.tar.gz` at `source/COMMIT.txt`, with `pyproject.toml` and `uv.lock`; the loop of section 5 is `source/fleet.tar.gz` |
| **D2** | experience summary | `experience-summary.md` |
| **D3** | merge and dedup code, overlap, reconciliation | section 7, `source/scripts/round/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your program vendored unmodified, explained in `metric-explained.md` |
