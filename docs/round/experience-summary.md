# Experience summary

**D2 of the submission standard.** What worked, what did not, the measured yields, the limits and where
to go next. Short by intent. `sources.md` ships beside this and carries every source, admitted and
rejected, with its evidence type, location, timestamp, extraction method and the measurement that
settled it.

Every figure here is measured against the store, not projected, and says what it was measured against.

## 1. The reusable technique

**Re-price what is already on disk whenever the unit, a screen, or a stated reason changes.** This
round's increment is 1,874,979 equivalent-English against `merged260908`, and 355,090 of it, 18.9%,
came from bytes the project already held and had written off, with no new request. The pattern is
narrower than "re-read the artifact": in every case the payload was **a field the old reading
discarded**, or the closure rested on a number nobody had re-measured.

| held artifact | what had been discarded | what it paid |
|---|---|--:|
| Usenet spool, 104.8 GB, closed as "224 GB, on neither machine any more" | the three headers a NEWS SERVER writes about itself, and a size that was wrong by 15x | 350,946 EE |
| Arquivo.pt `IA.cdxj`, closed on projected rate at registrable grain | the captured host beneath the registrable | 4,144 EE |

Earlier rounds found the same shape and it has now paid in four of them: NYPW TimeMaps, closed at
14.2 EE on one folder, paid 143,408 EE and then 70,937 more at hostname grain; the IA Early Web CDX
paid 65,026; the 1999 RIPE snapshot re-read for its `changed:` lines paid 58,398. **Exhaust the
artifact you already hold before looking for another one.** It needs no licence, no bandwidth, and
it is measured against the store as its own control.

## 2. What worked

- **One clear written objective, then unattended running.** Research runs as scheduled lanes on a
  self-hosted runner (generator, researcher waves, re-opener, improver). One round's largest source
  was a generator proposal, and eight sources have been admitted with no human in the loop under a rule
  fixed in advance: class already master-eligible, machine stamp inside the artifact, terms read in
  full, invariants pass. Two parked for a written decision, which is the rule working rather than
  failing, and the two hostname-unit rulings (section 5) were human decisions over the result.
- **Separating the agent that measures from the code that writes.** A researcher lane can never
  touch the store; a separate admitter re-derives every figure locally before anything is banked.
  Agent-reported figures have differed from the re-derivation more than once; the local number won.
- **Detached collectors holding an absolute epoch deadline**, so they outlive the session. They kept
  collecting through a day when the agent could not be reached.
- **Machine-written artifacts over anything a person wrote.** The large registrable additions were
  either an archive's own capture index (NYPW TimeMaps, the domain-wide CDX sweeps) or a registry
  printing its own database (RIPE, MYNIC change reports, `.za` deletion listings). Mean weight is
  often poor and volume carries it.
- **Pricing a source before building a collector.** Several candidates died on a measurement that cost
  minutes; one measured 5,884 on the register and 0.0000 per filing in the stratum that mattered.
- **Generating the names to query instead of discovering them.** Asking RDAP about the 2,395,205
  undated names already in the pool returned zero in-window creation dates over 602 queries, because
  73% of that pool answers 404: a name no crawler captured is usually a name that was never much of a
  site. Four invented populations were priced against each other instead, and sibling names, every
  held `.com`/`.net`/`.org` label re-suffixed to the other two, returned 14,205 in-window creation
  dates from 150,000 queries, 59.9 equivalent-English per 1,000. English dictionary words had the
  best hit rate at 28.0% and the worst ceiling, finite at about 235,000 words and 92.4% already held.
  Invented two-word compounds returned exactly zero from 859 queries. **A registry can only date a
  name that survived, so inventing plausible survivors beats enumerating known casualties.**

## 3. What did not work

- **Self-scheduled wake-ups inside one agent session.** Firings were answered unreliably, and the
  fix was structural rather than better prompting: the schedule moved out to the runner's cron, and
  the session-bound loop was retired.
- **Letting a research wave and the banking step overlap.** A wave that picked its hypotheses while
  the admitter was still writing verdicts re-tested six settled ones. Ordering, not effort: result
  lines are now written and published before the admitter runs.
- **Prose corpora, comprehensively.** Formal prose yields almost no URLs (5 in 3.26M words in one
  parliamentary corpus); grey literature yields 221x that rate and then fails on saturation at 93.0%
  already held. Both screens must pass and prose rarely passes the second.
- **Crawl-derived lists, for discovery.** They find few names we lack. But they can still win on
  completeness: a 2000-dated blocklist paid 18 equivalent-English while the 2001 edition of the same
  list paid 10,376.9, because its names lacked that year rather than lacking existence.
- **Closed with measurements**, so not worth repeating: academic repositories and DOI
  datasets (five APIs and two registries converge on three artifacts we already hold), national
  web-archive indexes, preserved CD-ROM media by name and by size, trade directories of internet
  businesses, and FTP-mirror archive listings (6.16M entries, 143,338 genuinely dated 2001, zero lists).

### The archive errors this round, and what each one changed

The hostname half of the round comes from one query family: `matchType=domain` on a registrable
already in the store, so one answer carries every host under it. Two clients at most, ever, with an
honest User-Agent naming the project and a contact, `from=1996`, `to=2001`, status filtered to 2xx
and 3xx. A redirect counts because it is a host that resolved and answered: 2.4% more rows for the
same request, 98.6% of them net-new. 4xx and 5xx stay out, since a 404 shows the server answered
and not that the host served.

| error | what it changed |
|---|---|
| `HTTP 403` on `url=<single-label TLD>&matchType=domain`, and on its `from`, `collapse` and `fl` variants | a whole TLD cannot be enumerated this way, so only multi-label suffixes and registrables are swept |
| `HTTP 503` on a count query | transient rather than a throttle signal: retried at `5 x 3^n` seconds capped at 300, and the count query doubles as the availability check so no request is spent probing |
| `HTTP 429` with no `Retry-After` on `archive.org/wayback/available`, sustained while a sweep runs | that endpoint shares a limiter with the CDX channel. `web.archive.org/web/timemap/link/<url>` does not, and replaced it |
| a truncated gzip tail on a journal still being written | the reader stops at the last complete record; the ingest is keyed on the file's sha256, so a re-read cannot double-count |
| a 200 that is a period 404, or a 301 onto a live 404 | the body is read rather than the status trusted |

A page costs about the same at any size, since it is a count of index blocks: 200 blocks took 11 to
42 seconds and 10,000 took 110, so the page count is asked once up front with `showNumPages`. A
parent is parked on measured capture rows per distinct host rather than on elapsed time, and its
position is saved, so the work already done is never repeated.

## 4. Lessons: the measured rules for pricing a source

Each lesson below cost at least a day to learn.

1. **Quote net-new, never gross, and post-split rather than pre-split.** The gap is often an order
   of magnitude: one registry ruling read 9,551.2 gross against 783.0 after the split.
2. **Novelty is a cost, not a gain.** A novel name earns no year under the split; the screen is *held
   AND missing this year*. An almost fully-held list still paid because its names lacked its year.
3. **Compute headroom from the adjacent year only.** Of 9,680 `.us` names missing 2001, 6,948 were last
   seen in July 1997, so "held any year, missing Y" is contaminated by death and "held Y-1, missing Y"
   is not.
4. **Stratify by year before concluding anything.** A source sampled in 1999 measured 0.0000 per item
   and 0.0324 in 2001, because 1999 had just been saturated by another ingest. Sampling the year you
   have just filled will refute any source.
5. **Re-price at the moment of admission, not of discovery.** One source measured 77,749 in August and
   4,493 four days later against a store that had grown into it.
6. **Sample distinct domains, not rows.** Per-row sampling gave 0.492 against a true per-domain 0.611.

## 5. Limitations, and the direction of the error

Both dating routes err toward **under-claiming**. A capture proves presence and never absence, so a
year with no capture is unevidenced rather than empty; a creation date attests one year only. Neither
can invent a year, so the mistake they make is omission.

The one place the error could run the other way is the counting unit, and both open questions on it
have since been ruled. A `www.` record stands where it carries its own exact-host evidence, and
nothing is inferred in either direction between a bare name and its `www.` form (2026-09-06). A
dated DNS-survey observation does not establish web content, so 17.7 million such hostname-years
ship as a named candidate collection rather than as annual records (2026-09-05). One hold-out
remains open: an FTP index row carries the crawler's own completion stamp for that exact host in
that year, which is stronger than a DNS observation and is not a webpage, so those rows are held
out of the annual files until the reviewer rules. The evidence is kept either way and one filter
recovers it.

A material share of archive requests fail at transport level rather than with a status code, which is
throttling seen from the other side of the socket. And host survival correlates with refusal: the old
mirrors that still run do so because an institution kept paying, and those operators are the population
now adding blanket `Disallow` rules, so the best-preserved hosts are disproportionately closed.

## 6. Recommended directions

1. **Bulk dated corpora**, still the best yield per megabyte by two orders of magnitude over prose.
2. **Registry datasets that publish dates**, the only route that reaches 2001, where the archives are
   thin: `P(store lacks 2001 | domain held)` is 0.611 for `.com` against near zero for 1999.
3. **Re-auditing material already on disk**, which produced a fifth of this round for no new download
   (section 1), and the remaining capture-bearing artifacts have not yet been re-read at hostname grain.
4. **Two sources are blocked on access rather than evidence.** The JISC UK per-year CDX index, 13.45 GB
   in window over the highest-weight TLD, is preserved but unservable: the UK Web Archive has been
   offline since the October 2023 British Library cyber-attack, with restoration targeted at Autumn 2026
   and a URL-lookup service first. SEC EDGAR filings measure 2,500 to 4,000 equivalent-English
   concentrated in 2000-2001 but need one request per filing, roughly 35 hours, because the bulk feed
   route does not exist before 2002.

## Lessons added this round

- **Re-measure the reason a source was closed, not just the verdict.** A class rejected as
  "224 GB and no space" was 15.3 GB, with 104.8 GB of the same corpus already on the laptop. It
  became the second-largest lane of the round and needed no fetch. A closure now records the
  measurement under it so the measurement can be re-run.
- **Read an evidence class by its authorship, not by its syntax.** "A receiving mail server names
  itself in `Received: ... by`" generalises to any server that writes about a transaction it
  completed, which admitted Usenet `Path:`, `X-Trace:` and `NNTP-Posting-Host:` with no new rule
  and no new approval class.
- **A peak rate is a fact about the queue, not about the source.** The same query and clients paid
  193,000 equivalent-English per client-hour on a fresh ranked head and 210 two nights later. Plan
  with the sustained figure: over ten hours the head overstated it by 2.4x.
- **Price a ranker only on parents it has never been used on.** Correlating rank against realised
  yield over already-swept parents gives +0.746 and reads as an inverted ranker; over parents swept
  fresh from a new ranking the same correlation is -0.655. The first number measures sweep history.
- **Verify a bulk artifact against its own published checksums before reading it, and delete on
  mismatch.** 19 of 19 indexes verified; the row count then reproduced an independent scout's count
  to within exactly the number of header lines, which is what made the yield trustworthy without a
  second pass.
- **A partitioned corpus is measured per partition, never argued about.** The ingest ledger's
  per-file year counts are free and have twice settled a claim that was orders of magnitude wrong
  before it cost bandwidth.
- **Keep the raw rows.** A sweep that writes `{url, timestamp}` and a separate ingest that decides
  what a row is worth cost nothing on the day and paid the whole hostname unit later. A collector
  that canonicalises on write destroys that option.
- **Write the report from the data, never the other way.** Every figure in the report is a token
  filled from the store and the merge audit, and the attribution table is generated from the
  shipped files, so the numbers cannot drift from the archive between builds.
