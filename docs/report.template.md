# Internet Digital Ark: round [ROUND]

Increment to the 1996-2001 annual lists against `[BASELINE]`, scored with your calculator. Every
figure is generated from the evidence store when the archive is built. This is the summary; the
receipts sit in the archive, one document per purpose, named here where relevant.

## 1. Results

| | |
|---|--:|
| Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| Equivalent-English total | [EEBASELINE] |
| Increment | **[TOTAL]** records |
| Equivalent-English increment | **[EE]** |
| Equivalent-English growth rate | **[EEGROWTH]** |

Two disjoint units, neither present in the baseline and none rejected by your validator:
[REGPAIRS] records ([REGEE] EE) are registrable domains in `additions/NNNN.txt`, the unit you asked
me to prioritize, and [HOSTPAIRS] ([HOSTEE] EE) are valid hostnames beneath them in
`hostnames/NNNN_hostnames.txt`, so the second set can be merged or discarded as a block.

[PER_YEAR_TABLE]

[CUMULATIVE]

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
- [CANDIDATES] domains carry no in-window year evidence, ship as `candidates.txt` and appear in no
  annual file; [POOL_RESTRICTED] of them are under `.edu`, `.gov` or `.mil`.

## 3. What is new, and why it is admissible

One idea applied six times: **when the counting unit changed, the payload was a column of an
artifact already on disk that the old unit had discarded.** Four of the six needed no new request.

| Source | Records | EE | What dates one record |
|---------------------------|--------:|-------:|-----------------------------------|
| ISC Internet Domain Survey per-TLD host files | [HOST_ISC_N] | [HOST_ISC_EE] | the survey's own `YYMM` edition code in the artifact path |
| NYPW TimeMaps at hostname grain | [HOST_NYPW_N] | [HOST_NYPW_EE] | the row's own 14-digit capture timestamp |
| IA domain-wide CDX sweeps over subdomain platforms | [HOST_SWEEP_N] | [HOST_SWEEP_EE] | the row's own 14-digit capture timestamp |
| IA Early Web index at hostname grain | [HOST_EARLYWEB_N] | [HOST_EARLYWEB_EE] | the row's own 14-digit capture timestamp |
| USFEDGOV merged CDX indexes, 1996-2001 | [HOST_USFEDGOV_N] | [HOST_USFEDGOV_EE] | the row's own 14-digit capture timestamp |
| RIPE `domain:` objects, their `nserver:` hosts | [HOST_RIPE_N] | [HOST_RIPE_EE] | the dump's generation stamp and each object's `changed:` line |
| registrable domains, all lanes | [REGPAIRS] | [REGEE] | as `additions/evidence_manifest.csv` states per record |

Every row rests on the same three grounds: the stamp that dates an item is machine-written and sits
**inside** the artifact, so no human judgement dates a year; the class was already master-eligible
for those exact bytes; the terms were read in full before the first request. On the survey you ruled
in writing on 2026-07-24 that a dated DNS survey may enter the annual files directly. Route,
licence, per-year and per-TLD yield are in `sources.md` and `audit/source_contribution.csv`.

**Two disclosures decide what the hostname half is worth**, each a single filter on
`hostnames/hostnames_evidence_manifest.csv`: [HOST_ISC_DIALUP_PCT]% of the largest source's records
are dialup or numbered workstation names (`pc50.btbcs.bt.co.uk`), which answered its reverse-DNS
walk in the month it stamps and pass your validity rule but are not sites; and [WWWSHARE] of all
hostnames are `www.` forms of registrables you already hold, worth full weight under the rule as
written and nothing if your calculator normalises `www.` away.

## 4. Evidentiary standard

Unchanged. One record is one machine-written observation of that name in that year, quoted with its
replay URL or artifact identifier in the evidence manifests so any line can be opened; `evidence_id`
is a `NOT NULL` foreign key on both units and fifteen invariants enforce it before every commit and
again inside the archive. Master-eligible classes: [MASTERTYPES]. `link_target` never dates a year,
anything a human typed needs a second source to date that domain first, and a creation date attests
its own year only. `metric-explained.md` states the counting unit and the weights.

## 5. What was built since round 6

Round 6 proposed sources and a person judged each one. This round the loop closes.

- **Five scheduled workflows on a self-hosted runner**: a generator writes hypotheses, each with a
  yield floor and a kill screen; researcher waves test them in parallel against a read-only copy of
  the store; a re-opener re-reads closed verdicts when a screen changes; an improver changes one
  prompt or model knob per pull request so effects stay attributable. [DATASETS_SEARCHED]
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
  not skipped. Per-domain gap queries contributed [CDXBULK] registrable pairs.

Code, prompts, policy and the hypothesis register with every verdict ship as `source/fleet.tar.gz`.

## 6. Limitations, and where the room is

**A hostname is not a site**: a reverse-DNS walk resolves dialup ports as readily as web servers,
and that is where most of this round's records come from, quoted per source so it can be cut. **A
capture proves presence, never absence**: a year without one is unevidenced, not empty. **The units
are disjoint**, so discarding the hostname files leaves the registrable round intact at [REGEE] EE.

Worth expanding, in order: the same one-level-down reading of every other banked artifact that names
hosts, since DNS, mail and mirror rosters hold hosts a web crawler never fetched; the second-level
suffix namespaces at hostname grain, where `co.uk` alone is 3.39M index blocks and 1.2% walked; the
ranked subdomain platforms still queued, resumable from `audit/source_saturation_ledger.csv`.
Measured and closed: prose corpora, academic repositories, CD-ROM media, FTP mirrors, trade
directories, with the figures in `experience-summary.md`.

## 7. Merge, overlap and reconciliation (D3)

[MERGE_RECONCILIATION]

## 8. Reproduction, and the four requested artifacts

`README.md` in the archive gives the route and the file map; this is the result of running it.
[REPRODUCTION_RESULT]

| | asked for | where it is |
|----|------------------|------------------------------------------|
| **D1** | runnable code, dependencies, instructions | `source/source.tar.gz` at `source/COMMIT.txt`, with `pyproject.toml` and `uv.lock`; the loop of section 5 is `source/fleet.tar.gz` |
| **D2** | experience summary | `experience-summary.md` |
| **D3** | merge and dedup code, overlap, reconciliation | section 7, `source/scripts/round/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your program vendored unmodified, explained in `metric-explained.md` |
