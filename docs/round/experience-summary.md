# Experience summary

**D2 of the submission standard.** What worked, what did not, the measured yields, the limits and where
to go next. Short by intent. `sources.md` ships beside this and carries every source, admitted and
rejected, with its evidence type, location, timestamp, extraction method and the measurement that
settled it.

Every figure here is measured against the store, not projected, and says what it was measured against.

## 1. The reusable technique

**Price what is already held, or already closed, at the grain that ships.** This round's increment is
329,141 equivalent-English against `merged260917-2`, and 168,435 of it, 51%, came from three
re-readings that cost no new discovery: two public Internet Archive CDX indexes read at hostname
grain, and our own export predicate measured against the files it shipped.

| what was re-read | what the first reading had discarded | what it paid |
|---|---|--:|
| Dartmouth NBER ARCS per-item CDX, closed in August as "already banked" | the captured host beneath a registrable every parent of which was held | 84,119 EE |
| the whole CDX of one IA storage node, 57.6 GB, priced at 0 on its head | the alphabetic hosts behind an IP-literal SURT head | 50,722 EE |
| the candidate-pool predicate, "no year at all" | 189,251 registrables whose only year Section XIII refuses | 33,594 EE |

Earlier rounds found the same shape: NYPW TimeMaps closed at 14.2 EE paid 143,408 and then 70,937
more at hostname grain; the IA Early Web CDX paid 65,026; the 1999 RIPE snapshot re-read for its
`changed:` lines paid 58,398. **Exhaust the artifact you already hold before looking for another
one.** It needs no licence, no bandwidth, and the store is its own control.

## 2. What worked

- **One clear written objective, then unattended running.** Research runs as scheduled lanes on a
  self-hosted runner (scout, price, verify, improver) and banks hourly into the store with no human
  in the loop under a rule fixed in advance: class already master-eligible, machine stamp inside the
  artifact, terms read in full, invariants pass. Both bulk CDX collections of this round were
  admitted that way; every hostname-grain header class parked for a written decision, which is the
  rule working.
- **Refusing at filing what cannot ship.** All 15 live fleet leads on 2026-09-21 were hostname-grain
  classes outside Section XIII's web methods. The dealer now refuses such a lead at filing with the
  XIII reason, findings carry grain and class, and the lenses weight self-published registers and
  dated registrable-domain lists. Every scout lead since has closed on an access wall, none on class.
- **Separating the agent that measures from the code that writes.** A researcher lane never touches
  the store; a separate admitter re-derives every figure locally before anything banks. The fleet's
  figure for one Dartmouth band was 8,343.6 EE; the store said 4.5, and the store won.
- **Detached collectors holding an absolute epoch deadline**, three CDX suffix-sweep lanes at most,
  judged by the journals they write rather than by their liveness: 41,377 journals on every one of
  the twelve days since the last submission.
- **Machine-written artifacts over anything a person wrote.** An archive's own capture index, a
  registry printing its own database, a server naming itself. Mean weight is often poor and volume
  carries it.
- **Pricing before building.** Eight header-class artifacts were fetched and priced on the laptop
  in 2.5 hours at 14 to 9,537 EE each; none was built into a lane, because none could ship.

## 3. What did not work

- **Header hostnames at hostname grain, under Section XIII.** The uk Usenet hierarchy: 8.47 GB,
  2,569,006 host-carrying posts, 39,999 hostname-year rows, 0 shippable equivalent-English, one
  hour. Server-written headers prove a host in service, not a website. The hosts they date ship as
  a provenance-linked candidate collection and in the candidate claim, never as annual records.
- **Ranking sweep parents on captured hosts without dropping the giants.** A capture-derived
  ranking put yahoo, google and t.co at the head; three lanes wrote nothing for two hours (645
  throttle lines) until stopped and the giants pruned. Drop parents his files hold at scale first.
- **The availability endpoint as a third client.** Re-tested for 25 minutes: 450 asks, 0 exact and
  3 variant recoveries, 20 throttles, then a sustained 429; about 5 EE an hour, so its slot went
  back to a sweep lane.
- **Closed with measurements**, so not worth repeating: the July 1995 NASA HTTP log (31,654
  host-years, none in window at any grain); Crossref reference URLs (48,000 works, 15 EE, ceiling
  1,450); 14 European registry homepages (stubs); the Australian Web Archive CDX (`Disallow: /`);
  2,218 in-window Alexa and wide-crawl items whose indexes answer 401; the JISC UK host-linkage
  file, unservable past 2 GiB through replay; academic repositories and DOI datasets; prose corpora.

### The archive errors this round, and what each one changed

| error | what it changed |
|---|---|
| `curl` timeout at byte 1,831,792,640 of a 57.6 GB item, and a `--retry` that truncated the file | a never-truncating `curl -C -` loop that compares the byte count to the item's stated size before declaring it complete |
| DuckDB `OutOfMemory` at the 13 GB default while ingesting 4,000,000-row journals | every hand-run store command sources the same 28 GB limit the scheduled sync uses |
| `HTTP 429` on `archive.org/wayback/available` after 450 asks, no `Retry-After` | the endpoint is retired as a client; the slot is a CDX sweep lane |
| `HTTP 401` on the per-item CDX of 2,218 in-window crawl items | private indexes are closed on the first 401, not probed per item |
| `HTTP 206` with 0 bytes past 2,147,483,647 on a replayed file | a replayed artifact is read only to 2 GiB and its tail is declared unservable, not missing |
| `robots.txt` `Disallow: /` on a national web-archive CDX | the whole robots file is read before the first request; the source closes on the rule |
| 645 throttle lines on three sweep lanes fed platform giants | a giant list pruned from the queues before injection |

Sweep lanes: `matchType=domain` on a registrable already in the store, two CDX clients and one
availability client at most, honest User-Agent, `from=1996`, `to=2001`, 2xx and 3xx. Measured rate
this round 330 to 580 EE an hour for the three lanes together.

## 4. Lessons: the measured rules for pricing and reading a source

Each lesson below cost at least a day to learn.

1. **Quote net-new, never gross, and post-split rather than pre-split.** The node CDX holds 931,864
   in-window host-years; 88% were already held, and the 12% is the figure.
2. **Novelty is a cost, not a gain.** A novel name earns no year under the split; the screen is *held
   AND missing this year*. An almost fully-held list still paid because its names lacked its year.
3. **Compute headroom from the adjacent year only.** "Held any year, missing Y" is contaminated by
   death and "held Y-1, missing Y" is not.
4. **Stratify by year before concluding anything.** Sampling the year you have just filled will
   refute any source.
5. **Re-price at the moment of admission and at the grain that ships.** A collection closed at
   registrable grain paid 84,119 EE at hostname grain a month later; a lead priced at 8,343.6 EE on
   a snapshot paid 4.5 on the store.
6. **Sample distinct domains, not rows.** Per-row sampling gave 0.492 against a true per-domain 0.611.
7. **Verify a bulk artifact against its own published size or checksum before reading it.** The
   57.6 GB item was declared complete only at its stated byte count, after one truncated download.
8. **A partitioned corpus is measured per partition, never argued about.** A 256 KB head read of
   282 indexes found the 25 that carry the window before a gigabyte was fetched.
9. **Keep the raw rows.** A converter that writes `{url, timestamp}` and a separate ingest that
   decides what a row is worth cost nothing on the day and paid the whole hostname unit.
10. **Write the report from the data, never the other way.** Every figure is a token filled from the
    store and the merge audit, so the numbers cannot drift from the archive between builds.

## 5. Limitations, and the direction of the error

Both dating routes err toward **under-claiming**. A capture proves presence and never absence, so a
year with no capture is unevidenced rather than empty; a creation date attests one year only. Neither
can invent a year, so the mistake they make is omission.

The counting unit is settled. A `www.` record stands where it carries its own exact-host evidence, and
nothing is inferred in either direction between a bare name and its `www.` form (2026-09-06). A dated
DNS-survey observation does not establish web content, so those hostname-years ship as a named
candidate collection rather than as annual records (2026-09-05). Section XIII extends the same line
to registry events, mail and Usenet headers and textual mentions: they ship as source-specific
candidate collections with provenance, and the annual files hold exact-host website evidence only.

Two gaps against Section XIII are stated rather than hidden. The seven-column exclusion ledger is
emitted for the header collection's validation run only, the rest of the pool carrying a reason per
line in `candidates_unparsed.txt`; and the TLD gate is the public suffix list plus a nine-entry
historical ccTLD allowlist rather than a documented IANA list. Both are one filter over the store.

A material share of archive requests fail at transport level rather than with a status code, which is
throttling seen from the other side of the socket, and the best-preserved hosts are disproportionately
the ones now adding blanket `Disallow` rules.

## 6. Recommended directions, and the measured pace

Between the submission of 2026-09-10 and this one the 5% threshold moved from 1,744,355 EE on
`merged260908` to 2,803,730 EE on `merged260917-2`. In the same eleven days this harness ran
continuously, 657 fleet legs, 41,377 collector journals and 63 hourly banks, and added 329,141 EE.
The two best method-hours paid 36,600 and 33,600 EE; the continuous lanes pay 330 to 580 an hour. At
those rates the threshold is a further 8 hours of the best method, which no longer exists to be
repeated, or about 300 days of the lanes.

1. **Bulk custodian capture indexes read whole at hostname grain** remain the best yield per
   megabyte, and archive.org now holds none we have not read: one research collection, one node CDX.
   The same shape at other custodians is the avenue left open.
2. **Registry datasets that publish dates** reach 2001, where the archives are thin, and score on the
   candidate track at about 3,100 EE per hour of work; an annual record needs a capture beside them.
3. **Exact-host captures beside the candidate collections** are the one route that turns candidate
   EE into annual records; the availability endpoint cannot carry it at 5 EE an hour, a CDX client can.
4. **Two sources are blocked on access rather than evidence.** The JISC UK per-year CDX index, 13.45 GB
   in window over the highest-weight TLD, is preserved but unservable until the UK Web Archive returns
   (targeted Autumn 2026). SEC EDGAR filings measure 2,500 to 4,000 EE in 2000-2001 at one request per
   filing, about 35 hours.
