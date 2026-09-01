# Experience summary

**D2 of the submission standard.** What worked, what did not, the measured yields, the limits and where
to go next. Short by intent. `sources.md` ships beside this and carries every source, admitted and
rejected, with its evidence type, location, timestamp, extraction method and the measurement that
settled it.

Every figure here is measured against the store, not projected, and says what it was measured against.

## 1. The reusable technique

**Re-price what is already on disk whenever the unit or a screen changes.** This round's
increment is 3,078,204 equivalent-English, and about 2.5 million of it came from bytes the
project already held and had written off, with no new request:

| held artifact | what changed | what it paid |
|---|---|--:|
| NYPW TimeMaps, closed at 14.2 EE on the 1996 folder | the novelty screen retired; the 1999 and 2000 folders were measured from the ingest ledger instead of argued about | ~88,000 EE registrable |
| the same 34 parts | the reviewer accepted hostnames as records; the parts were re-emitted at hostname grain | 2,097,955 EE |
| 180 domain-wide CDX sweep journals, logged as worth 0 | same unit change: `www.foo.co.uk` no longer collapses onto a held `foo.co.uk` | 301,650 EE |
| the same 34 parts again | the parser had discarded every non-200 row; a 302 or 404 still needs the name delegated | 6,680 EE |

Earlier rounds found the same shape: the 1999 RIPE snapshot re-read for its `changed:` lines paid
58,398 EE, and the RDAP sibling-name generation paid 357,755 by asking about names invented rather
than found. **Exhaust the artifact you already hold before looking for another one.** It needs no
new licence, it is measured against the store as a control group, and it is where the yield came from.

## 2. What worked

- **One clear written objective, then unattended running.** Research runs as scheduled fleet lanes on a self-hosted runner (generator, researcher waves, re-opener, improver); the round's largest source was a generator proposal.
- **Detached collectors holding an absolute epoch deadline**, so they outlive the session. They kept
  collecting through a day when the agent could not be reached.
- **Registry-generated artifacts over anything a person wrote.** Every large registrable addition in round 7 was a
  registry or registrar printing its own database: RIPE, the US Domain delegation list, the `.ca`
  approval notices, a registrar's expiring-domain list. Mean weight is often poor and volume carries it.
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

- **Scheduled wake-ups.** The agent answered only some firings, so unattended progress was not reliable.
- **A self-scheduling loop.** Tried once and it did not hold.
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

A material share of archive requests fail at transport level rather than with a status code, which is
throttling seen from the other side of the socket. And host survival correlates with refusal: the old
mirrors that still run do so because an institution kept paying, and those operators are the population
now adding blanket `Disallow` rules, so the best-preserved hosts are disproportionately closed.

## 6. Recommended directions

1. **Bulk dated corpora**, still the best yield per megabyte by two orders of magnitude over prose.
2. **Registry datasets that publish dates**, the only route that reaches 2001, where the archives are
   thin: `P(store lacks 2001 | domain held)` is 0.611 for `.com` against near zero for 1999.
3. **Re-auditing material already on disk**, which produced most of this round for no new download
   (section 1), and the remaining capture-bearing artifacts have not yet been re-read at hostname grain.
4. **Two sources are blocked on access rather than evidence.** The JISC UK per-year CDX index, 13.45 GB
   in window over the highest-weight TLD, is preserved but unservable: the UK Web Archive has been
   offline since the October 2023 British Library cyber-attack, with restoration targeted at Autumn 2026
   and a URL-lookup service first. SEC EDGAR filings measure 2,500 to 4,000 equivalent-English
   concentrated in 2000-2001 but need one request per filing, roughly 35 hours, because the bulk feed
   route does not exist before 2002.

## Lessons added this round

- **Re-read closed verdicts whenever a measurement screen retires.** A source rejected at
  14.2 equivalent-English on its most saturated partition paid ~88,000 when the retired
  novelty screen was replaced and the other end of the partition was measured. A
  dedicated re-opener lane now does this on a schedule.
- **A partitioned corpus is measured per partition, never argued about.** The ingest
  ledger's per-file year counts are free and settled a four-orders-of-magnitude wrong
  claim before it cost bandwidth.
- **Agents in CI print mode need a structural contract**, not advice: hard timeout,
  scheduling tools disabled, fallback verdict, telemetry. A backgrounded sort plus a
  scheduled wake-up silently cost one run its whole budget before the contract existed.
- **Spend models only where judgement pays.** Booking results is deterministic code now;
  models propose, test and admit. Cadence is earned from a per-run ledger of
  equivalent-English per token, under a hard weekly budget ceiling.
- **Keep the raw rows.** A sweep that writes `{url, timestamp}` lines and a separate
  ingest that decides what a row is worth cost nothing extra on the day and paid the
  whole hostname unit later. A collector that canonicalises on write destroys that option.
- **Write the report from the data, never the other way.** Every figure in the report is a
  token filled from the store and the merge audit, and the attribution table is generated
  from the shipped files, so the numbers cannot drift from the archive between builds.

