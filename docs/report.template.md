# Internet Digital Ark: round [ROUND]

Additions to the 1996-2001 annual lists, measured against `[BASELINE]`. Every figure is generated
from the evidence store, so no table here can disagree with the files shipped beside it. This is a
summary: `sources.md` holds the per-source receipts, `experience-summary.md` the yields and
directions, `README.md` the reproduction route, `metric-explained.md` the metric.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

[REGPAIRS] records ([REGEE] EE) are registrable domains in `additions/`, the unit you asked me to
prioritize; [HOSTPAIRS] ([HOSTEE] EE) are valid hostnames beneath them in `hostnames/`. The two are
disjoint in every year, neither is in the baseline, your validator rejects none of them, and the
second set can be merged or discarded as a block.

[PER_YEAR_TABLE]

[CUMULATIVE]

## 2. What one hostname record is

Four conditions, all enforced in code (`source/src/ark/hostnames.py`, `checks.py`), not by
convention. The first two are your rule; the last two are its purpose, retrieving archived pages,
applied on 2026-09-02 after a first build had counted names that pass the letter and serve it nothing:

1. **RFC 1123 valid**: letters, digits and hyphens only, no leading or trailing hyphen in a label,
   at least two labels. Underscore names, IP literals and `in-addr.arpa` forms are refused.
2. **Strictly beneath a registrable this project holds for that same year.** The parent is a
   foreign key, so a hostname cannot exist here without its registrable existing there, and a bare
   registrable is never a hostname record. No name is counted in both units.
3. **Its own machine-written observation in that year, showing the host serving web content**: a
   capture of a URL on it, or a URL listing naming it. A DNS listing proves a machine answered, not
   a site, so it dates the parent registrable and writes no hostname record.
4. **Not `www.<parent>`.** That is the registrable's own site under the name every crawler tries
   first; the capture dates the registrable, and counting it again would be the same site twice.

## 3. What is new this round, and why it is admissible

One idea, applied to five artifact families: **when you accepted hostnames, the payload was a
column of an artifact already on disk that the registrable unit had discarded.** Four of the five
needed no new request, and most carried a written closure from an earlier round.

| Source | What dates one record | Records | EE |
|-----------------------------|--------------------------------------------------|--------:|-------:|
| IA domain-wide CDX sweeps | the row's 14-digit capture timestamp | [HOST_SWEEP_N] | [HOST_SWEEP_EE] |
| IA Early Web index | the row's 14-digit capture timestamp | [HOST_EARLYWEB_N] | [HOST_EARLYWEB_EE] |
| NYPW TimeMaps | the row's 14-digit capture timestamp | [HOST_NYPW_N] | [HOST_NYPW_EE] |
| USFEDGOV merged indexes | the row's 14-digit capture timestamp | [HOST_USFEDGOV_N] | [HOST_USFEDGOV_EE] |
| squidGuard and chastity URL blocklists | the robot's compile stamp; the tar member's mtime | [HOST_BLOCKLIST_N] | [HOST_BLOCKLIST_EE] |
| registrable domains, all lanes | per record in `additions/evidence_manifest.csv` | [REGPAIRS] | [REGEE] |

Every stamp above is machine-written and inside the artifact, so no human judgement dates a year;
each class was already master-eligible for those exact bytes; the terms were read in full before
each fetch. Route, licence and per-TLD yield per source are in `sources.md`.

**Two things your rule admits and this round does not count.** The same one-level-down reading
of three DNS artifacts (the ISC Internet Domain Survey host files, RIPE `nserver:` attributes,
InterNIC zone NS targets) had written 18,219,285 dated hostname rows, the survey alone exporting as
9.17M EE, that pass conditions 1 and 2 and fail 3: two thirds of the survey's names are dialup
ports and numbered workstations (`pc50.btbcs.bt.co.uk`), for which no archived page can exist. They
are held out, their rows still date the parents, and the lane is one line to re-enable if you rule
that DNS listings count. And 5,162,650 `www.<parent>` rows, valid and captured, fail condition 4;
their captures date the registrables instead. Your 0902 brief says a domain-wide query may return
the base hostname and every qualifying subdomain and that overlap is removed downstream, so this
is the one place the round is deliberately narrower than your text: a `www.` capture is here read
as the registrable's own page, and the rows are recoverable from the evidence with one filter if
you want them as records. Both counts are store rows reported by
`apply_hostname_purpose_rule.py` on the store as first built.

The evidentiary standard is unchanged: one record is one machine-written observation of that name in
that year, `evidence_id` is a `NOT NULL` foreign key on both units, seventeen invariants enforce it
before every commit and inside the archive, `link_target` never dates a year, human-typed names take
the corroboration split, and a creation date attests its own year only. [CANDIDATES] domains carry
no in-window evidence, ship as `candidates.txt` and reach no annual file.

## 4. What became autonomous since round 6

Round 6 ran unattended for hours but a person judged every source. This round the loop closes, and
its code, prompts, policy and full hypothesis register with every verdict ship as
`source/fleet.tar.gz`.

- **Five scheduled workflows on a self-hosted runner**: a generator writes hypotheses, each with a
  yield floor and a kill screen; researcher waves test them in parallel; a re-opener re-reads closed
  verdicts when a screen changes; an improver changes one prompt or model knob per pull request so
  effects stay attributable. [DATASETS_SEARCHED]
- **Admission without a human, under a rule fixed in advance**: a source banks only if its class is
  already master-eligible, a machine stamp inside the artifact dates each item, the terms were read
  in full and the invariants pass. Eight sources banked that way this round and two parked for a
  written decision. No agent may write the store: a separate admitter re-derives every figure
  locally first, and two agent-reported figures lost to that check. The rule admits on the
  letter of your standard; the purpose reading in section 2 was a human decision over the result,
  which is the division of labour intended.
- **The re-opener earned its lane**: it recovered the NYPW TimeMaps from a 14 EE closure by
  measuring the ingest ledger per folder (year rows per million: 2000 ~24,000, 1999 ~10,000, 2001
  exactly 4), ~88,000 EE that a human closure had written off.
- **CDX execution**: two clients at most, honest User-Agent, two seconds between requests,
  `Retry-After` honoured, absolute deadlines that outlive a session. Sweeps write raw
  `{url, timestamp}` journals, which is why the same bytes could be re-read under the new unit. A
  page costs about the same at 200 index blocks as at 10,000, so the sweep walks 10,000-block pages;
  one outage refused thirteen parents and they were requeued, not skipped. Per-domain gap queries
  contributed [CDXBULK] registrable pairs.

## 5. Limitations, and where the room is

A capture proves presence and never absence, so a year without one is unevidenced rather than empty,
and both dating routes err toward omission; the purpose reading in section 2 adds a third omission
by design, the DNS-listed hosts held out above. The units ship separately, so dropping the hostname
files leaves the registrable round intact at [REGEE] EE.

Worth expanding, in order: the same one-level-down reading of every other capture-bearing or
URL-listing artifact already on disk, since a URL list names hosts a domain sweep never reached
(the DARTMOUTH-NBER ARCS indexes are sampled and priced in `key-decisions.md`); the second-level
suffix namespaces at hostname grain, where `co.uk` alone is 3.39M index blocks and 1.2% walked; the
ranked subdomain platforms still queued, resumable from `audit/source_saturation_ledger.csv`.
Measured and closed: prose corpora, academic repositories, CD-ROM media, FTP mirrors, trade
directories. The figures behind each verdict are in `experience-summary.md`.

## 6. Merge, overlap and reconciliation (D3)

[MERGE_RECONCILIATION]

## 7. Reproduction, and the four artifacts

`README.md` in the archive gives the route and the file map. [REPRODUCTION_RESULT]

**D1** runnable code, dependencies and instructions: `source/source.tar.gz` at `source/COMMIT.txt`,
with the research loop as `source/fleet.tar.gz`. **D2** experience summary: `experience-summary.md`.
**D3** merge and dedup code, overlap and reconciliation: section 6 and `audit/`. **D4** runnable
metric code: `equivalent_english_domain_calculator/`, your program vendored unmodified, explained in
`metric-explained.md`.
