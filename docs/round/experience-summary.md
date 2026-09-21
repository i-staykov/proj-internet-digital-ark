# Experience summary

**Deliverable D2 of the specification.** Round 10: what worked, what did not, the yields and the
limits. `sources.md` beside this carries every source tested, with the measurement that settled
it; `findings.md` carries the three results in full. "The evidence rule" is section XIII of your
specification of 17 September; EE is equivalent-English; "our database" is the evidence store every
figure here is measured against.

## 1. The reusable technique

**Price what is already held, or already dismissed, at the grain that ships.** This round's
increment is 329,141 EE against your release `merged260917-2`, and 168,184 of it, 51%, came from
three re-readings that cost no new discovery:

| what was re-read | what the first reading had discarded | what it paid |
|---|---|--:|
| Dartmouth NBER ARCS per-item CDX, dismissed in August as already covered | the captured hosts beneath registrable domains that were all held | 83,868 EE |
| the whole CDX of one Internet Archive storage node, 57.6 GB, priced at 0 from its first lines | the named hosts: the index sorts IP-literal keys first, so a head sample sees none | 50,722 EE |
| our candidate-pool rule, which took only names with no dated year | 189,251 `.dk` registrable domains whose only dated year came from a registry zone list, a class the evidence rule keeps out of the annual files, so they shipped in neither file | 33,594 EE |

**Exhaust the artifact you already hold before looking for another one.** It needs no licence and
no bandwidth, and the database is its own control.

## 2. What worked

- **Unattended admission under a rule fixed in advance** (class eligible for the annual files under
  the evidence rule, machine stamp inside the artifact, terms read in full, invariants pass)
  admitted both bulk CDX collections of this round; every hostname-grain header class parked for a
  written decision, which is the rule working.
- **Refusing at filing what cannot ship.** On 2026-09-21, 15 of the 18 open source proposals in the
  autonomous loop were hostname-grain classes the evidence rule keeps out of the annual files. Such
  a proposal is now refused when filed, with the reason, and the search is weighted toward
  registries' own published lists and dated registrable-domain lists.
- **Archive clients judged by the index files they write, not by whether the process is alive**:
  41,378 files over the twelve days since the 10 September submission, with output on every day.
- **Pricing before building.** Eight header-class artifacts were fetched and priced in 2.5 hours at
  14 to 9,537 EE each; none was built into a collector, because none could ship.

## 3. What did not work

- **Server-written header hostnames, under the evidence rule.** The uk Usenet hierarchy: 8.47 GB,
  2,569,006 host-carrying posts, 39,999 hostname-year rows, 0 shippable EE. Server-written headers
  prove a host in service, not a website; the hosts they date ship as a provenance-linked candidate
  collection and in the candidate claim, never as annual records.
- **Ranking the domains to sweep by captured hosts without dropping the giants.** A capture-derived
  ranking put yahoo, google and t.co at the head; the three archive clients wrote nothing for two
  hours under throttling until stopped and the giants pruned. Drop the parents your files already
  hold at scale before queuing.
- **The availability endpoint as a third client.** Re-tested for 25 minutes on candidate hostnames:
  450 asks, 0 exact and 3 variant recoveries, 20 throttles, then a sustained 429; about 5 EE an hour
  (the report's 114 an hour for the same endpoint is on undated registrable names), so its slot
  became a third CDX client.
- **Closed with measurements**, so not worth repeating: the July 1995 NASA HTTP log (31,654
  host-years, none in window at any grain); Crossref reference URLs (48,000 works, 15 EE, ceiling
  1,450); 14 European registry homepages (stubs); the Australian Web Archive CDX (`Disallow: /`);
  2,218 in-window Alexa and wide-crawl items whose indexes answer 401 (closed on the first 401, not
  probed per item); the JISC UK host-linkage file, unservable past 2 GiB through replay.

### The archive errors this round, and what each one changed

| error | what it changed |
|---|---|
| `curl` timed out part-way through a 57.6 GB item and `--retry` truncated the file | a never-truncating `curl -C -` loop that compares the byte count to the item's stated size before declaring it complete |
| `HTTP 206` with 0 bytes past 2,147,483,647 on a replayed file | a replayed artifact is read only to 2 GiB and its tail is declared unservable, not missing |

The three CDX clients together paid 193,733 EE in the twelve days since 10 September, about 670 EE
an hour: `matchType=domain` on a registrable already in the database, honest User-Agent,
`from=1996`, `to=2001`, 2xx and 3xx.

## 4. Lessons

1. **Net-new, post-split.** The node CDX holds 931,864 in-window host-years; 88.8% were already
   held, and the 11.2% is the figure.
2. **Re-price at the moment of admission and at the grain that ships.** A collection dismissed at
   registrable grain paid 83,868 EE at hostname grain a month later; a source priced at 8,343.6 EE
   on a stale copy of the database measured 4.5 against the live one.
3. **Measure a partitioned corpus per partition.** A 256 KB head read of 282 indexes found the 25
   that carry the window before a gigabyte was fetched.

## 5. Limitations, and the direction of the error

The counting unit is settled by your rulings of 5 and 6 September and by the evidence rule:
registry events, mail and Usenet headers and textual mentions ship as source-specific candidate
collections with provenance, and the annual files hold exact-host website evidence only. Both
dating routes err toward omission: a capture proves presence, never absence.

Two gaps against the evidence rule, also listed in the report: the exclusion ledger is emitted for
the server-header candidate collection's run only (`candidates_unparsed.txt` carries a reason per
line for the rest), and the TLD gate is the public suffix list plus nine retired ccTLDs, not a
documented IANA list. Both are one filter over the database.

## 6. Recommended directions, and the measured pace

Between the submission of 10 September and this one the 5% threshold moved from 1.74 million EE to
2.80 million on `merged260917-2`. Over the same twelve days the autonomous loop ran continuously
(647 scheduled research runs, 41,378 archive index files) and added 329,141 EE. The two best methods
paid 37,300 and 33,500 EE an hour of work and are exhausted; the three archive clients together pay
about 670 an hour. The remaining 2,474,589 EE is about 70 hours of the best method or 150 days of
the clients.

1. **Bulk custodian capture indexes read whole at hostname grain** remain the best yield per
   megabyte, and archive.org now holds none we have not read (the research collection and the node
   index of section 1). The same shape at other custodians is the avenue left open.
2. **Registry datasets that publish dates** score on the candidate track at about 3,100 EE per hour
   of work; an annual record needs a capture beside them.
3. **Exact-host captures beside the candidate collections** are the one route that turns candidate
   EE into annual records; a CDX client carries it, and section 3 measured the availability endpoint
   out.
4. **The two access-blocked sources of round 9, the JISC UK per-year CDX index and SEC EDGAR
   filings, are unchanged: preserved, unservable, priced as before.**
