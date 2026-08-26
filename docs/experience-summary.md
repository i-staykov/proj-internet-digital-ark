# Experience summary

**D2 of the submission standard.** What worked, what did not, the measured yields, the limits and where
to go next. Short by intent. `sources.md` ships beside this and carries every source, admitted and
rejected, with its evidence type, location, timestamp, extraction method and the measurement that
settled it.

Every figure here is measured against the store, not projected, and says what it was measured against.

## 1. The method, and the part that is transferable

**The largest addition of this round came from a file already ingested.** The 1999 RIPE snapshot had
been read for one attribute, the domain name, and dated to the file's own instant. Each object also
carries a `changed:` line per update applied to it, 2,016,169 of them, each with its own date. An
object cannot be modified before it exists, so those lines reach 1996, 1997 and 1998, which the
snapshot's own date cannot: **399,401 further pairs, 58,398 equivalent-English, no new download.**

The same question paid three times in this round:

| asked of | what it gave |
|---|---|
| `webarchive.org.uk/datasets/ukwa.ds.2/` "what else is in this directory?" | a per-year CDX index nobody had listed, 13.45 GB in window |
| `archive.org` "what is the item named for, the group or the hierarchy?" | a 14 MB registry archive hiding behind a better-matching 208 KB decoy |
| `ripe.db.gz` "what else do these objects say?" | 58,398 equivalent-English |

**So the rule is: exhaust the artifact you already hold before looking for another one.** It is cheaper
than discovery, it needs no new licence, and it is where this round's yield actually came from.

## 2. What worked

- **One clear written objective, then unattended running.** This is how the round's sources were found.
- **Detached collectors holding an absolute epoch deadline**, so they outlive the session. They kept
  collecting through a day when the agent could not be reached.
- **Registry-generated artifacts over anything a person wrote.** Every large addition this round is a
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
  list paid 10,736, because its names lacked that year rather than lacking existence.
- **Closed with measurements this round**, so not worth repeating: academic repositories and DOI
  datasets (five APIs and two registries converge on three artifacts we already hold), national
  web-archive indexes, preserved CD-ROM media by name and by size, trade directories of internet
  businesses, and FTP-mirror archive listings (6.16M entries, 143,338 genuinely dated 2001, zero lists).

## 4. Measured rules for pricing a source

1. **Quote net-new, never gross.** They differ by more than 10x. One source read 15,270 gross and
   12,775 net.
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

## 6. Where to go next

1. **Bulk dated corpora**, still the best yield per megabyte by two orders of magnitude over prose.
2. **Registry datasets that publish dates**, the only route that reaches 2001, where the archives are
   thin: `P(store lacks 2001 | domain held)` is 0.611 for `.com` against near zero for 1999.
3. **Re-auditing material already on disk**, which produced the largest single addition of this round
   and cost nothing.
4. **Two sources are blocked on access rather than evidence.** The JISC UK per-year CDX index, 13.45 GB
   in window over the highest-weight TLD, is preserved but unservable: the UK Web Archive has been
   offline since the October 2023 British Library cyber-attack, with restoration targeted at Autumn 2026
   and a URL-lookup service first. SEC EDGAR filings measure 2,500 to 4,000 equivalent-English
   concentrated in 2000-2001 but need one request per filing, roughly 35 hours, because the bulk feed
   route does not exist before 2002.
