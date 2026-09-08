# Internet Digital Ark: round [ROUND]

Additions to the 1996-2001 annual lists, against `[BASELINE]`. Every figure is generated from the
evidence store, so nothing here can disagree with the files beside it. Receipts are in
`sources.md`, yields in `experience-summary.md`, the route in `README.md`.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

[REGPAIRS] records ([REGEE] EE) are registrable domains in `additions/`; [HOSTPAIRS] ([HOSTEE] EE)
are valid hostnames beneath them in `hostnames/`. The two are disjoint in every year, neither is in
the baseline, your validator rejects none of them, and either set can be merged or discarded whole.

**[WWWSHARE] of the hostname half is `www.<a name already in your files for that year>`.** That is
stated here rather than left to be found. Each of those records has its own capture of that exact
host, never the parent's capture reused, and your IV.8 and XI both say a base hostname and a
qualifying subdomain may each be a record. We also counted your side: `[BASELINE]` holds 1,450,310
names beginning `www.` and 1,221,065 of them have the bare name in the same year file, 114,875 from
sources other than us. If you read the rule the other way, dropping the prefix forms is one filter
and the registrable round stands at [REGEE] EE.

[PER_YEAR_TABLE]

[CUMULATIVE_SENTENCE]

## 2. What one hostname record is

Three conditions, enforced in code (`source/src/ark/hostnames.py`, `checks.py`), not by convention.

1. **Valid per your rule**: dot-separated labels, letters, digits and interior hyphens only, ending
   in an alphabetic TLD label. Underscore names, IP literals and `in-addr.arpa` forms are refused.
2. **Strictly beneath a registrable we hold for that same year.** The parent is a foreign key, a
   bare registrable is never a hostname record, and no name is counted in both units.
3. **Its own machine-written observation in that year, showing the host serving web content**: a
   capture of a URL on it, or a URL listing naming it. A DNS listing proves a machine answered
   rather than a site, so it dates the parent and writes no hostname record.

## 3. What is new, and where it came from

[ATTRIBUTION_TABLE]

Every stamp above is machine-written and inside the artifact, so no human judgement dates a year.

**Annual and candidate contributions, separately, as your section XI asks.** The five fields above
are annual records only. Beside them, [CANDIDATES] domains carry no in-window evidence, ship as
`candidates.txt`, reach no annual file, and are worth [CANDIDATEEE] equivalent-English **if every
one were later dated**, which is a ceiling on future work and not a contribution to this round.

**The methodological findings of this round, which we think transfer.**

1. **What a domain-wide query is worth is set by the years the parent is held in, not by how many
   hosts it has.** A capture under a parent we do not hold for that year cannot become a record, so
   ranking parents by sub-host count alone spends requests on rows that are already ours or cannot
   be assigned. Ranking instead on hosts we lack multiplied by the years we hold the parent, minus
   the host-years already held, took the accepted share of one night's sweep from 4.9% to 21%.
2. **A peak rate is a statement about the queue, not about the source, and re-ranking is what
   restores it.** The same query, code and two clients paid about 193,000 equivalent-English per
   client-hour on the dense head of a ranked queue and 210 per hour two nights later once that head
   had been walked. Re-ranking the queue against the store and restarting the two clients on its
   new head returned 1,009,324 capture rows in one window, of which 225,088 were net-new records
   worth 141,208 equivalent-English, or 565 equivalent-English per megabyte of journal. **That
   figure is not a rate either.** Measured over the whole ten hours from the re-rank, the same two
   clients wrote 1,067 megabytes of journal that banked 247,042 equivalent-English, which is **231
   per megabyte, and the head overstates the sustained figure by 2.4x**. So the head is a fact
   about the ordering, and an hour is planned with the sustained figure. **The caution that goes with it:** correlating a parent's rank
   against what it actually banked gives Spearman +0.746 over 198 parents, which reads as a ranker
   that is exactly inverted, because the head of any ranking is swept FIRST and re-measuring it
   measures sweep history. Restricted to the 54 parents swept fresh from a new ranking the same
   correlation is -0.655. Price a ranker only on parents it has never been used on.
3. **An absence is evidence about the search, not about the artifact.** Two families closed in our
   own register at 0 EE, one because a navigation sweep of a site's home page found no inventory
   page and one because an index of FTP hosts was assumed already held, were both wrong: the pages
   were one link deeper, and 31.49% to 64.31% of that index's hosts were missing at their own year.
   A verdict resting on "we looked and found nothing" is now re-probed by reading the site's own
   link structure out of an archived page rather than by guessing paths.

4. **Order a bulk corpus by obscurity, not by size, and measure the band edges rather than
   reasoning about them.** Reading the Usenet `alt` hierarchy at hostname grain, 14,482 of its
   15,288 groups, the yield per gigabyte is not flat and not monotonic in size. The two largest
   discussion groups paid **0.0000 equivalent-English**: `alt.answers` is the FAQ group, its URLs
   are the most-posted URLs on Usenet, and every one of its 17,385 host-years was already held.
   The 2 to 150 megabyte band paid about **134 per gigabyte**. The 0.3 to 2 megabyte band paid
   **509 per gigabyte**, almost four times better, with 63% of its posts inside 1996-2001 and only
   6.4% of its net-new hosts the `www.` alias seam. Below 0.3 megabytes it falls back to 145. The
   mechanism is saturation, not size: an obscure group's URLs are the ones nobody reposted. Our
   first plan excluded everything under 2 megabytes on the reasoning that a small archive probably
   holds no in-window post, and that reasoning was wrong about the best band in the corpus.
   **The companion caution:** a seven-file probe of a 418-file mailing-list archive said 1,036
   equivalent-English and the whole archive paid 325, and a three-group probe of `alt` said 722 per
   gigabyte against 134 realised. Probes of skewed corpora overstate by 3x to 5x, so a band is
   priced by reading it, not by sampling it.

## 4. CDX acquisition: the tools, the strategy, the errors and what it added

The hostname half of this round, [HOSTPAIRS] records and [HOSTEE] equivalent-English, comes from
one query family. Two clients at most, ever, with an honest User-Agent naming the project and a
contact.

| | |
|---|---|
| tool | `source/scripts/engines/cdx_suffix_sweep.py`, driven by `platform_sweep_loop.sh` |
| question | `matchType=domain` on a registrable this store already holds, so one answer carries every host under it |
| parameters | `fl=original,timestamp`, `from=1996`, `to=2001`, `filter` on the status code, 2xx and 3xx only, and `pageSize` in index blocks |
| why 3xx counts | a redirect is a host that resolved and answered. Measured 2.4% more rows for the same request, 98.6% of the extra net-new. 4xx and 5xx stay out: a 404 shows the server answered, not that the host served |
| page cost | a page is a count of index blocks and costs about the same at any size: 200 blocks took 11 to 42 s, 10,000 took 110 s. The page count is asked once up front with `showNumPages` |
| ordering | parents ranked by hosts we lack times the years we hold the parent, minus host-years already held |
| stopping | a parent is parked on measured capture rows per distinct host, not on elapsed time, and its position is saved so the work already done is kept |

**The errors, and what we did about each.**

| error | how it was handled |
|---|---|
| `HTTP 403` on `url=<single-label TLD>&matchType=domain`, and on its `from`, `collapse` and `fl` variants | a whole TLD cannot be enumerated this way. Only multi-label suffixes and registrables are swept |
| `HTTP 503` on a count query | transient rather than a throttle signal: retried with a short backoff, `5 x 3^n` seconds capped at 300, and the count query doubles as the availability check so no extra request is spent probing |
| `HTTP 429` with no `Retry-After` on `archive.org/wayback/available`, sustained while the sweep runs | that endpoint shares a limiter with the CDX channel. `web.archive.org/web/timemap/link/<url>` does not, returns every memento with its datetime, and replaces it |
| a truncated gzip tail on a journal still being written | the reader stops at the last complete record; the ingest is keyed on the file's sha256 so a re-read cannot double-count |
| a 200 that is a period 404, or a 301 onto a live 404 | the body is read rather than the status trusted |

## 5. One question, shipped as its own folder

`isc_survey_hostnames/` holds **[ISCPAIRS]** hostname years from the ISC Internet Domain Survey of
1996-1997, and **they are not in the figures above.** The survey's per-TLD host files are dated by
their own edition code and name each host explicitly, so they satisfy conditions 1 and 2 and are
direct rather than inferred. They fail condition 3 as we read it: a reverse-DNS walk shows a machine
answering, not a page.

Your section XI asks for hostname-level identity wherever there is year-specific evidence and does
not restate the web-content condition, so the honest thing is to ask rather than decide.
**Does a host listed in a dated 1996-1997 reverse-DNS survey, with no capture of a page on it,
count as an annual hostname record?** If yes, the folder merges as it stands. If no, discard it and
nothing else changes. We flag one fact against it: 1.419% of these hosts appear anywhere in your
files, against 84.2% for the `www.` shape, so it is a population you have not held before, and much
of it is dialup ports and numbered workstations.

## 6. Limitations

A capture proves presence, never absence, so a year without one is unevidenced rather than empty,
and both dating routes err toward omission. The units ship separately, so dropping the hostname
files leaves the registrable round intact at [REGEE] EE.

Worth expanding next, in order: the same one-level-down reading of the remaining capture-bearing
and URL-listing artifacts already on disk; the second-level suffix namespaces at hostname grain,
where `co.uk` alone is 3.39M index blocks and 1.2% walked; the ranked subdomain platforms still
queued in `audit/source_saturation_ledger.csv`. Measured and closed this round: the `alt` Usenet
remainder, on saturation. Prose corpora, academic repositories, CD-ROM media, FTP mirrors and trade
directories were closed earlier, with figures in `experience-summary.md`.

**One eligibility question we cannot settle ourselves.** An FTP index row carries the crawler's own
completion stamp for that exact host in that year, so the service answered and its files were
counted. That is stronger than a DNS observation, which your 0906 update makes candidate-only, but
it is not a webpage. We hold such rows out of the annual files until you rule, and they are in no
figure in this report.

## 7. Merge, overlap and reconciliation (D3)

[MERGE_RECONCILIATION]

## 8. Reproduction, and the four deliverables

`README.md` in the archive gives the route and the file map. Every evidence row names its source,
evidence type, dated value, URL and extraction method; `additions/evidence_manifest.csv` and
`hostnames/hostnames_evidence_manifest.csv` repeat those columns per record. [REPRODUCTION_RESULT]

**D1** code and instructions: `source/source.tar.gz` at `source/COMMIT.txt`, with the autonomous
research loop as `source/fleet.tar.gz`. **D2** experience summary: `experience-summary.md`.
**D3** merge and dedup code, overlap and reconciliation: section 7 and `audit/`. **D4** runnable
metric code: `equivalent_english_domain_calculator/`, your program vendored unmodified and
explained in `metric-explained.md`.
