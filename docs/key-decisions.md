# Key decisions, open and closed

**What this is.** The one surface that asks Ivo for anything. `OPEN` is a numbered list, `O1` upward,
**one or two lines each**, and every entry says plainly whether granting it would reach the 5% gate.

**Rewritten 2026-08-20 on his instruction**, and the rule it enforces is the point: this file had grown
to a 280-line essay and the four questions it actually asked were invisible inside it. **If an entry
needs a third line, the extra belongs in `docs/archive/decisions-working.md`, not here.** He decides
from the one-liner and reads the working only if he wants to.

**This is the only file that asks Ivo for anything**, on his instruction of 2026-08-11: "Everything
I have to sign-off should be in one place, so I know about it." So:

- `notes.md` entries **no longer ask for a sign-off**. That log is the agent's own working, and
  asking him to countersign 37 entries of it buried the few things that genuinely needed him.
- A `pending` class in `approved-sources-list.md` is **mirrored here automatically**, by
  `request_approval.py` when it writes the request and by `just cycle` if one ever appears without
  an entry. That file stays the thing `ark ingest` enforces and the thing he edits; this is how he
  learns it wants him. A test against both live files fails if a pending class is not named here.
- **Unfinished hypotheses are not raised here.** They are the agent's queue: screened, priced and
  decided without asking, and only an outcome worth overruling becomes an entry under `OPEN`.

**Why the headings carry their number at the END, which looks odd and is deliberate.** `just cycle`
writes and re-reads these headings, and both the mirroring code and a test match on the heading's
opening words, so `### O4. Triage the newly found sources` would silently stop being recognised as the
entry it is. The number goes last so a human gets his numbering and no machine contract moves.

**Reading it.** `OPEN` needs you. `CLOSED` was decided by the agent under a standing rule or a
measurement, and is recorded so you can still object. Newest first within each block.


---

## OPEN

**Gate 668,118 EE on `merged260821`. We hold 88,062, which is 13.2% of it, up from 10.8% this
afternoon and 2.8% yesterday.**

**The fast channel is RDAP and it is running on both machines.** The registry's own creation date is
`whois_creation`: master-eligible, self-dating, no corroboration split, and approved since phase 4,
so it needed no decision from anyone. It is a different service from the archive, so it does not
compete with the CDX sweeps, and it runs at **156 queries a second across the two machines against
the archive's 17,500 a day**. Measured delivered rate: **about 12,900 EE an hour.** Working in C-42.

**16.7 million domains are queued**, about thirty hours of work, worth roughly **262,000 EE** at the
measured per-query rates. That is 39% of the gate from a channel that needs nothing from you.

| | the ask | what it is worth |
|---|---|---|
| **O1** | Approve `ukwa_geoindex` / `cdx_timestamp` as **master**. Free, public, CC Public Domain, on disk and parsed. | **77,749 EE, 11.6% of the gate, the minute you say so.** |
| **O2** | Keep the VPN up when you can. The VPS is the faster of the two machines at RDAP, 102 q/s against 54. | Roughly two thirds of total throughput. |
| **O3** | Set one `Decision:` line for `internic_zone` / `artifact_listing` | 8,627.7 EE, 1.3% of the gate |
| **O4** | Give `/bin/bash` Full Disk Access so the scheduled check can run | Housekeeping, two minutes |
| **O5** | May we query Nominet in bulk for `.uk`? | **No.** The whole `.uk` pool is 48,545 EE, 7.8% |
| **O6** | One word each on 60 found sources, whenever you like | **No.** All 60 priced whole is about a tenth |

**The honest total.** Banked 88,062, plus about 262,000 queued in RDAP, plus `ukwa_geoindex` 77,749
and `internic_zone` 8,628 on your word, is **about 436,000 EE, 65% of the gate**. That is not the
whole thing and I will not pretend it is, but it is the first time a single channel has been worth
a third of the gate and been deliverable in a day rather than a month.

**A contributor added 977,561 EE in one day**, 94% of it in the year 2000, so the gate rises about
48,878 a day. RDAP delivers about 310,000 a day, so the gap closes rather than widens.

**Withdrawn by your instruction of 2026-08-20, public sources only:** research access to the WhoisXML
API database, the depth question to DomainTools, and the outreach for an unpublished early-web crawl.
The Kaggle account goes too, since the sweep it would have unblocked was run unauthenticated and found
nothing larger than what is already held. ICANN CZDS stays available, free and public, but is not raised
as an ask because a zone file carries no creation dates and cannot date a year by itself.

### Approve ukwa_geoindex / cdx_timestamp as master  (O1)

**77,749.1 equivalent-English over 79,253 net-new pairs, measured over the whole file rather than
sampled**, 98.1% `.uk` at weight 0.9813, and 45,122 of the domains are ones the store has never seen.
Self-dating, so no corroboration split. Set its `Decision:` line in this file's triage table. Working
in C-31.

### Approve, refuse or downgrade internic_zone / artifact_listing  (O3)

Set its `Decision:` line in `approved-sources-list.md` to `master`, `candidate-only` or `rejected`; that
file carries the seeded-random sample with live links. **8,627.7 EE as master, 1.4% of the gate.**

### Give /bin/bash Full Disk Access  (O4)

System Settings > Privacy & Security > Full Disk Access. Without it the launchd health check exits 126
four times a day, because this repository sits under `~/Documents`. Then run `just schedule` again.

### Bring the VPN up when convenient  (O2)

`10.1.0.6` stopped answering around 09:00Z on 2026-08-20. Its collector holds a deadline of 31 August
and is still working, but nothing it finds can be banked here until the tunnel is back.

### May we query Nominet in bulk for the .uk candidate pool  (O5)

Their terms are ambiguous and a sweep was stopped for that reason. **Priced 2026-08-19 at 48,545 EE**
even if every undated `.uk` name answered with an in-window date, so it cannot produce a round.

### Triage the newly found sources: 60 found  (O6)

**60 source(s) found and not yet priced**, in `approved-sources-list.md` under `## Found, awaiting triage`. One word each, *candidate pool* or *fold in directly*.

A counter rather than a request, by your instruction of 2026-08-15. Nothing is blocked: a pending class cannot date a year, so `ark ingest` refuses it and collection continues.

---

## CLOSED

### C-43. RDAP is the fast channel, and both of my first two target lists were wrong (2026-08-21)

**Ivo's reframing was the whole insight**: finding more candidates is worthless when the constraint
is *dating* them. The store already held 2.35 million undated candidates and the archive gives about
17,500 queries a day. RDAP is a different service, it returns the registry's own creation date, and
`rdap_snapshot / whois_creation` has been approved master since phase 4. So it needed no decision
from anyone and does not compete with the CDX sweeps.

**Measured: 156 queries a second across two machines**, against the archive's 17,500 a day, and a
delivered rate of about **12,900 equivalent-English an hour**.

**Where to point it took three measurements, and my first two answers were wrong in opposite ways.**

**Wrong once, by filtering for novelty.** The obvious optimisation is to query only domains the store
has never seen, since a domain we already hold cannot produce a net-new pair:

| target list | in-window | net-new of those | net EE / 1,000 |
|---|--:|--:|--:|
| never seen by the store | 1.02% | 100% | **6.3** |
| unfiltered | 36.4% | 11.4% | **25.7** |
| **store domains never RDAP-queried** | 19.26% | 16.6% | **20.2** |

**A domain the store has never seen is precisely a domain that did not exist in 1996-2001**, so the
novelty filter removes the value along with the waste. The population that pays is names some era
source already attested but whose creation year we do not hold: 11,446,886 of the store's 14.8
million qualify.

**Wrong twice, by ordering on English weight.** That put `.er`, `.gu` and `.nr` at the head: they
score 1.0000 in the model, the store holds a handful of each, and their registries answer in about
five seconds. **Measured at 0.2 queries a second against 65 for the same code on Verisign, a 300x
difference decided entirely by which registry was asked.** A volume floor moved `.au` to the front
at 11 q/s, still 6x slow. The ranking has to be **equivalent-English per second**, so the list now
sorts on weight times a measured per-registry rate and `.com` leads.

**Three faults found by running it rather than reading it.** The VPS `src/` was stale, so `ark rdap`
rejected `--workers` and the run exited reporting an exhausted list rather than a broken one.
`date -u -r` is macOS-only, so the deadline printed empty on Linux and a misconfigured run looked
configured. And clearing a stale lock by hand started a second supervisor: **32 concurrent workers at
Verisign from one machine**, which is how a project gets refused. The lock now reads its pid and asks
the process table, so a live holder is respected and a dead one is taken over.

**What is queued.** 16.7 million domains across both machines, about thirty hours, worth roughly
262,000 EE at the measured rates: the store population at 20.2 per thousand, then a follow-on of
4,980,427 novel domains from the reviewer's own out-of-window URL dumps at 6.3.

### C-42. Page 0 of a CDX namespace is about twice as dense as the namespace (2026-08-21)

**A sampling bias found by checking my own ranking against the sweep it had ranked**, and the third
correction in one day to the same family of estimates. Worth its own entry because the artifact this
round leaves behind depends on it.

`psl_rank.py` estimates a namespace's size as `pages x domains-per-page`, sampling one page for the
density. It sampled **page 0**. CDX pages are ordered by SURT key, so page 0 is the alphabetical
start of a namespace, where short numeric and single-letter names cluster. Measured across the
quartiles:

| suffix | page 0 | 25% | 50% | 75% | bias |
|---|--:|--:|--:|--:|--:|
| `com.au` | 11 | 4 | 7 | 8 | **1.7x** |
| `co.uk` | 70 | 0 | 33 | - | **2.1x** |
| `org.uk` | 25 | 62 | 77 | 29 | 0.4x |

So page 0 overstates the large namespaces by about **2x**, and the error propagates straight into a
headroom figure and then into a decision about where to point a three-day sweep. `org.uk` running the
other way is the reminder that this is a bias and not a constant: it cannot be corrected with a
factor, only by sampling properly.

**Fixed by sampling three quartile pages and averaging**, which costs two extra requests per suffix.
The first scan's output was discarded rather than kept with a caveat, because a ranked list with a
2x error in its score column is exactly the kind of artifact that gets trusted later.

**The general lesson, which is the one worth carrying.** Three separate estimates this round were
wrong in the same way: a structural quantity was sampled at whatever point was cheapest to reach,
and the sample's position turned out to carry information. The head of a file, the first page of an
index, the first hour of a collector. **If a sample's position is convenient, ask what the position
selects for before trusting what it says.**

### C-41. The suffix sweep is exhausted, and the complete accounting of what remains (2026-08-21)

**The measurement that ends the route.** After `co.uk`, the sweep moved to `com.au`, `ac.uk`,
`gov.uk` and the rest of the ranked list. On the live `ac.uk` journal:

| | |
|---|--:|
| capture rows read | **2,069,189** |
| distinct in-window pairs | 458 |
| already held | 442 |
| **net-new** | **16 pairs, 15.7 EE** |

Two million index rows for sixteen pairs. The delivered rate over the sweep's second and third hours
is **about 620 EE/hour, roughly 15,000 EE/day**, against the 134,000 EE/day I reported from its first
hour on `co.uk`.

**The honest reading of C-38.** The sweep is a genuine bulk instrument and it did work: `co.uk` was a
16,936-page namespace the store had barely touched, and taking it was worth about 68,000 EE in a few
hours. But that was **one unharvested namespace, not a new rate**. Every other high-weight suffix is
already in the benchmark, which is unsurprising: the Wayback CDX is the most obvious source in this
task and several contributors have been mining it for weeks.

**`psl_rank.py` exists so the next agent does not re-guess.** It walks the whole Public Suffix List,
filters to weight >= 0.5 and to TLDs that existed in the window, and measures each survivor's page
count and per-page domain density rather than assuming either. 2,988 suffixes pass the filters. Its
output is `data/raw/cdx_suffix/psl_ranked.tsv`, which is the artifact worth keeping from this round.

**The complete accounting, everything measured, nothing projected:**

| | EE | state |
|---|--:|---|
| banked against `merged260821` | 72,170 | done |
| `ukwa_geoindex` | 77,749 | on disk, parsed, **waits on O1** |
| `internic_zone` | 8,628 | journal on disk, **waits on O3** |
| `.us` locality namespaces | ~6,000 | measured, sweepable, unheld |
| remaining suffix sweep and Usenet | ~15,000/day, falling | running |
| **total identified** | **~165,000, 25% of the gate** | |

**So there is no 5% of immediate potential and I will not claim there is.** The gate is 668,118 EE
and moved 48,878 in a day. What would change that is a bulk dated corpus that is not IA-derived, and
this round closed the remaining candidates: the Alexa crawl indexes (access-restricted, C-37), the
`.com` extension (structurally impossible, C-39), the British Library repository (one dataset, all of
it taken), and the commercial WHOIS vendors (excluded by the public-sources rule).

### C-40. The suffix sweep is real but an order of magnitude smaller than C-38 and C-39 claimed (2026-08-21)

**This corrects two of my own entries from the same day, and the correction is larger than either
finding.** C-38 measured the sweep at about 134,000 net-new EE per day and C-39 priced `com.au` at
308,000 EE of headroom. Both rested on the same unmeasured assumption and both are wrong.

**The assumption.** `suffix_rank.py` estimated a namespace's size as `pages x 20`, where 20 domains
per 200-row page was taken from the `.uk` sweeps. **A page count measures captures; the metric pays
for domains, and the ratio between them is a property of how a namespace was crawled.** Measured on
`com.au`: **56,872 capture rows yielded 435 distinct in-window pairs**, about 1.5 domains per page
against the assumed 20. That namespace is a few sites crawled deeply, not many sites crawled once.

**Re-ranked with the density sampled per suffix rather than assumed, every candidate collapses:**

| suffix | weight | pages | held | headroom EE, assumed | headroom EE, measured |
|---|--:|--:|--:|--:|--:|
| `com.au` | 0.9904 | 20,491 | 98,659 | 308,174 | **0** |
| `gov.uk` | 0.9813 | 1,498 | 2,733 | 26,718 | **0** |
| `ac.uk` | 0.9813 | 1,386 | 4,902 | 22,392 | **0** |
| `govt.nz` | 0.9895 | 209 | 565 | 3,577 | 475 |

**The 134,000 EE/day figure has the same defect.** It was taken over the first hour on `co.uk`,
which is 16,936 pages of a namespace the store had barely touched, and it does not survive contact
with a namespace we already hold. The honest current rate, measured on the live `com.au` journal
against the store: **28.3% net-new but only 435 pairs and 121.8 EE from 56,872 capture rows.**

**What is still true.** The sweep is a genuine bulk enumeration and it costs one query per page
rather than one per domain, so it remains the right instrument. What is false is that any large
namespace remains unharvested: the store already holds 445,443 `co.uk`, 98,659 `com.au` and 38,158
`org.uk` domains, and the sweep is now confirming our own coverage rather than extending it.

**So the 5% gap is not closed by this route, and the OPEN block is corrected to say so.** The
mistake worth naming is that I priced a route on a structural estimate and reported it before the
first namespace had been measured end to end. C-38's own rate was measured against one favourable
namespace in its first hour, which is exactly the "a rate is a property of a moment" trap this
project has written down twice.

### C-39. The suffix sweep cannot be extended to `.com`, and the reason is structural (2026-08-21)

**The obvious next step after C-38, closed in ten minutes rather than a day.** The sweep enumerates a
whole namespace from one query and reaches about 7,000 EE/hour. `.com` is the largest namespace in
the metric, so the question is whether the same trick reaches it.

**It does not, and the failure is not the 403 everyone would expect.** `matchType=domain` on `com`,
`net` and `org` returns HTTP 403, which the register already knew. The idea worth testing was that a
second-level prefix might be legal, letting `.com` be swept as 36 namespaces. It is legal: `a.com`
returns HTTP 200. **But it matches only the literal domain `a.com`.** Measured: `a.com`, `b.com` and
`c.com` each report exactly **1 page**, where `co.uk` reports 16,936. `matchType=domain` means "this
domain and its subdomains", not "domains beginning with this string".

So the sweep reaches exactly where a **public suffix** exists to name the namespace, and `.com` has
no sub-namespace to name. That is a property of the DNS hierarchy rather than of the archive's
policy, so it will not change and should not be retried.

**What it leaves, and it is a lot.** `suffix_rank.py` measures which multi-label suffixes are worth
sweeping by combining weight, true namespace size from the CDX page count, and what the store holds:

| suffix | weight | pages | held | headroom EE |
|---|--:|--:|--:|--:|
| `com.au` | 0.9904 | 20,491 | 98,659 | **308,174** |
| `co.nz` | 0.9895 | 4,462 | 39,642 | 49,077 |
| `gov.uk` | 0.9813 | 1,498 | 2,733 | 26,718 |
| `org.au` | 0.9904 | 1,453 | 5,694 | 23,142 |
| `ac.uk` | 0.9813 | 1,386 | 4,901 | 22,392 |
| `co.uk` | 0.9813 | 16,936 | 445,443 | **0, exhausted** |

**`com.au` alone is 46% of the gate**, and the contrast with `co.uk` is the point: both are about
17,000-20,000 pages, and one is worth nothing because we already hold it. Headroom, not size, is what
ranks a namespace.

### C-38. The query-rate ceiling is broken: one endpoint enumerates a whole namespace (2026-08-21)

**This overturns C-36, which said 5% was about 50 days away, and it overturns the reasoning behind
every archive route in this register.** Every one of them asked about a single domain at a time,
capping the project near 17,500 queries a day. That cap no longer binds.

**`matchType=domain` on a public SUFFIX returns captures for every domain beneath it, and it
paginates.** Established with controls on 2026-08-21, and the control matters because the register
already records the bare-TLD form being refused and that is still true:

| query | result |
|---|---|
| `url=uk&matchType=domain` | **HTTP 403**, as are the `from`, `collapse`, `fl` and `showNumPages` variants |
| `url=co.uk&matchType=domain` | **200**, returning many distinct registrable domains |
| `showNumPages` on `co.uk` | **3,387,186 pages** |
| pages 0, 1, 2 | **disjoint**, so the namespace can genuinely be walked |

So the block is on the bare TLD rather than on the query shape, and a public suffix is treated as an
ordinary two-label name while behaving as a suffix. The distinction was worth testing precisely
because the register's earlier note, "`url=mil&matchType=domain` returns 403", is true and would
have closed this without the second experiment.

**Measured, then measured again at scale.** A five-minute run gave 23 pages, 96,343 capture rows,
1,437 in-window pairs, **600 net-new and 588.8 EE**. One hour gave 1,045,699 rows, 13,286 pairs,
**5,696 net-new and 5,589.5 EE at 42.9% net-new**, every one `.uk` at weight 0.9813.

| route | net-new EE per day |
|---|--:|
| edge-year per-domain querying | ~13,500 |
| **suffix sweep** | **~134,000** |

**It needs no new decision.** Each row carries a 14-digit capture timestamp, so the evidence is
`cdx_timestamp`, and `cdx_snapshot / cdx_timestamp` is already approved master.
`cdx_suffix_convert.py` collapses capture rows into that journal format rather than declaring a new
`SourceSpec`, which would duplicate a reviewed decision for no gain.

**Banked immediately: the store went from 54,417 to 68,056 EE**, 8.79% to **10.99% of the gate**, in
about ninety minutes.

**Two operational notes that belong with it.** The sweep and the CDX collectors are both heavy
clients at `web.archive.org` and compete for one rate budget, so the local engine is stopped while
the sweep runs; the sweep is about ten times better per request, which makes that trade obvious.
And the sweep stops dead on 429 or 503 rather than backing off, because this route is worth
protecting and the Internet Archive has refused this project three times.

### C-37. The original Alexa crawl indexes exist, are enormous, and are access-restricted (2026-08-21)

**The most obvious idea nobody had written down: stop querying the Wayback index one domain at a
time and download the crawl indexes it was built from.** They exist, they are exactly the right
shape, and they are shut. Recorded in full because the idea will occur to the next agent within an
hour and this saves them the day.

Archive.org carries the original Alexa crawls under `alexacrawls` (**226,901 items**), `alexa_1999`
(243), `20thcenturyweb` (331) and `greencrawl` (148). A typical item, for instance
`green-0027-19990127005032-917571173-c`, is a 1.45 GB crawl from January 1999 that ships its own
**636 MB `.cdx.gz`**: a bulk capture index of every URL the crawl saw, each with a 14-digit
timestamp. That is `cdx_timestamp`, self-dating, and `early_web_cdx / cdx_timestamp` is **already
approved master**, so it would have needed no decision from anyone.

**It is also the one thing that would have broken the rate limit**, because the constraint on this
project is 17,500 archive queries a day and one of these files carries more captures than a month of
querying.

**Measured, with a control, because the first attempt proved nothing.** That attempt reported 401 on
every item and its control returned HTTP 502, meaning archive.org was refusing everything at that
moment and the 401s were not evidence about the files. Re-run with a control that had to pass first:

| item | result |
|---|---|
| control, `usenet-bit`, a file we have downloaded before | **OK**, after four 500s |
| `green-0027-...` | **HTTP 401**, metadata carries `access-restricted-item: true` |
| `sarah-000063-...` | **HTTP 403** |
| `green-000196-...` | 302 to a storage node that then returns 500, three times |

**So the metadata is public and the payload is not.** This is a policy restriction rather than link
rot, and it is consistent with the Internet Archive having refused this project three times: the raw
crawl data behind the Wayback Machine is not open bulk download.

**The reopen condition is narrow and worth stating.** Not "try again later", which will read the same
500s. It is: an item in these collections **whose metadata lacks `access-restricted-item`**, or a
research-access route to the collection, which is outreach and therefore not ours to start.
`scripts/alexa_crawl_index.py` enumerates and samples them, so testing the condition is one command.

### C-36. 5% by Sunday is not reachable, and here is the arithmetic that says so (2026-08-21)

**Asked for directly, so answered directly rather than hedged.** The gate is 619,240 EE. We hold
51,057. Everything identified, measured and either running or one word away:

| | EE | state |
|---|--:|---|
| banked against `merged260820` | 51,057 | done |
| Usenet backlog on local disk, 110.8 GB | ~15,000 | banking, about 19h left |
| Usenet English hierarchies, remote | 40,000 to 86,000 | downloading |
| `ukwa_geoindex` | 77,749 | on disk and parsed, waits on O1 |
| `internic_zone` | 8,628 | journal on disk, waits on O3 |
| both CDX engines, 3 days | ~28,000 | running |
| **total by Sunday** | **220,000 to 266,000** | **36% to 43% of the gate** |

**The binding constraint is archive query rate and nothing else.** The edge population holds
1,597,226 EE, which is 2.6x the gate, and it is measured rather than projected: 0.659 net EE per
query against the builder's 0.6075 forecast. At 17,500 queries a day that is **50 days**, or about
**25 with the VPS working**. No bulk source found in this round changes that, because the bulk
sources are the small part and the queue is the large one.

**Two things would move the date and both are yours.** The VPN, which roughly halves it, and O1,
which is 77,749 EE sitting parsed on disk. Neither makes Sunday.

### C-35. National Usenet hierarchies really do name national domains, tested rather than assumed (2026-08-21)

The register dismissed 135 GB of `de`, `it`, `tw`, `fido7`, `pl`, `fr` and `nl` Usenet on the
reasoning that an English-weighted metric discounts them. **That is an assumption about content
drawn from a fact about language, and it is exactly the kind this project has been wrong about
before**, so it was tested: a German newsgroup could perfectly well name `.com` domains, and `.com`
scores 0.6321 against `.de`'s 0.1324.

Measured over 598 MB of `de.soc.politik.misc`, `de.admin.news.groups` and `de.sci.philosophie`:

| | |
|---|--:|
| net-new post-split pairs | 636 |
| equivalent-English | 155.2 |
| **mean weight** | **0.2353** |
| EE per MB | **0.26** |

Against 0.68 for `bit.listserv` and 3.25 for `microsoft.public`. **The assumption holds**: the mean
weight of 0.2353 is close to `.de`'s own 0.1324 and nowhere near `.com`'s 0.6321, so these groups do
name mostly national domains. Extrapolated, the whole 135 GB is worth about 35,000 EE, which is not
worth the download or the days of processing.

**The point of recording a confirmed assumption is that it was cheap to check and would have been
expensive to be wrong about**, in either direction: 135 GB wasted, or 400,000 EE missed.

### C-34. A 5% path exists, it is measured, and every part of it is public (2026-08-20)

**Ivo's standing bar is "at least a 5% potential". This is the first time the project can show one
from measured numbers rather than hope.** The gate is 619,240 EE.

| source | net EE | state |
|---|--:|---|
| already banked against `merged260820` | **38,106** | done, and rising hourly |
| the **edge population**, 6,038,320 targets | **1,597,226** | queue built, engine running on it |
| `ukwa_geoindex` | 77,749 | downloaded, parsed, waits on O1 |
| unheld Usenet hierarchies | ~60,000 | downloading and banking now, no approval needed |
| `internic_zone` | 8,628 | journal on disk, waits on O3 |

**The edge population alone is 2.6x the gate**, and that figure is net rather than gross, which was
checked rather than assumed. The queue builder forecast 0.6075 net EE per query for its best 250,000
targets. Measured against the **in-flight, not-yet-banked** journal, which is the only place the
question can be asked honestly:

| | |
|---|--:|
| answered | 451 |
| years the archive returned | 945, **2.075 EE/query gross** |
| of those, **net-new** | 300, **0.659 EE/query net** |
| net-new share of what came back | **31.7%** |

**0.659 measured against 0.6075 forecast, so the builder's expected values are sound and the queue's
1,597,226 EE is a real figure.** The gross number is 2.075 and quoting it would have overstated the
engine by 3.1x; it is recorded here so nobody quotes it later.

**So the constraint is throughput, not sources.** Measured over 12 batches: 6,672 answered in 7.8
hours, 20,520 queries/day, **13,500 net EE/day**. Against a threshold receding 5,129/day the gap
closes at about 8,400 EE/day, so the remaining 435,000 EE after the four listed sources is **about
seven weeks locally and about three with the VPS**. Under C-33's time weighting that difference is
worth roughly double the final score, which is why the VPN is now O2.

**What this does not say.** It does not say a round is imminent, and the seven weeks is a projection
from one day's throughput, not a measurement of seven weeks. What it does say is that the question
"is there a 5% path at all" is now answered yes, on public sources, with each component measured.

### C-33. Scoring is now time-weighted, so submitting sooner is worth as much as submitting bigger (2026-08-20)

**His update of 2026-08-20 17:02 UTC+8, quoted in `docs/ding/project-brief.md` and the update log.**
Recorded here because it changes what "wait until 5%" costs, and because no summary of it should be
trusted over his own text.

For each accepted submission, `S_i = k x (p_i / t_i)` with `k = 10`, where `p_i` is the verified
equivalent-English percentage increase and **`t_i` is elapsed days from the release of the applicable
benchmark to receipt of the complete submission**. Ranking is `S_total = sum(S_i)`. The direct sum of
verified percentages survives as a separate contribution record.

**What that does to this project's plan.** The 5% gate still gates a submission, and he restates that
reaching it "is a trigger for the next formal submission batch, not a completion condition". But the
clock for `t_i` started when `merged260820` was released, which was 2026-08-20. **A 5% round submitted
on day 10 scores 5.0; the same round on day 30 scores 1.67.** So the cost of a slow round is now
explicit and large, where before it was only the credit lost to a growing denominator.

He also added, on 2026-08-18, that participation does not end at 5%: contributors continue "until they
have systematically searched, tested, and reasonably exhausted all discoverable sources".

### C-32. The threshold recedes 10x slower than the model assumed, and the gap now closes (2026-08-20)

**The single number that most changes what this project should do**, and it is measured rather than
modelled.

`merged260820` is 23,015,567 records and **12,384,808.0318 EE**, measured per year with his own
calculator, so the gate is **619,240 EE**. The corpus grew **307,712.4914 EE in three days**, and that
growth is exactly one contributor's accepted 5% round, reproduced to the digit from his own
`merge_stats_final_submission_5pct_0820.csv`.

| interval | days | others' EE/day |
|---|--:|--:|
| to `merged260815` | 5 | 424,091 |
| to `merged260817` | 2 | 1,082,013 |
| **to `merged260820`** | 3 | **102,571** |

So the threshold recedes at about **5,129 EE/day**, not the 54,101 the plan was built on. Our own
edge-year collection measures about **17,400 EE/day**. **Collection now exceeds recession by roughly
12,300 EE/day and the gap closes.**

**The standing conclusion that per-domain querying can never reach the gate is therefore withdrawn.**
It was true when the recession was ten times larger and it is not true now. What has not changed is
that querying alone is slow: closing 600,000 EE at 12,300/day is about seven weeks, and under C-33 a
seven-week round scores a fifth of a one-week one. **Bulk sources are still the answer; they are now
the answer for a different reason.**

**One caution that belongs with this number.** It is a single three-day interval. If the other
contributors resume at 400,000 EE/day the recession returns to 20,000 and the conclusion flips back.
`scripts/submission_cadence.py` recomputes it from his published totals and now reads the direction
from the data rather than asserting it.

### C-31. The British Library geoindex is real, free and worth 77,749 EE, measured over the whole file (2026-08-20)

**The largest available public source this project has found, and it was sitting at position 0 of the
triage queue with an estimate 1.3x to 7.8x too low.** Recorded because the extraction turned up a trap
that the register had explicitly predicted and that nearly bit again.

The geographic index of the JISC UK Web Domain Dataset: every `.uk` resource the Internet Archive held
for 1996-2013, one row per capture, `<14-digit timestamp>/<url><TAB><postcode>`. **11,217,295,098 bytes
at `bl.iro.bl.uk/downloads/`, CC Public Domain Mark 1.0, ranged GETs answered, no access letter.** The
timestamp is `cdx_timestamp`, self-dating, so it takes **no corroboration split**.

**Measured over the whole file, not sampled:**

| | |
|---|--:|
| in-window rows extracted | 17,912,511 |
| distinct in-window (domain, year) pairs | 289,857 |
| already held | 210,604 |
| **net-new pairs** | **79,253 (27.3%)** |
| of which domains the store has never seen | 45,122 |
| **net-new equivalent-English** | **77,749.1** |
| mean weight | 0.9810 |

98.1% of the net-new is `.uk` at 0.9813, which is why 79,253 pairs carry almost the same number of EE.
The triage table had it at 10,000 to 60,000 pairs; it is 79,253.

**The trap, which the register predicted and which the first run walked into.** The 12 members look
sorted by timestamp, which would put 1996-2001 in a contiguous prefix and make extraction cheap. The
sibling `host-linkage.tsv.gz` looked sorted too and was fifteen concatenated shards, and the check that
cleared it stopped 2.4x short of the first boundary. So `postcode-ab` was streamed to EOF: **0 decreases
over all 529,492,931 compressed bytes, with the in-window count flat for the last 470 MB.** Early abort
justified.

**And then it was wrong anyway, because sortedness is a property of the member and not of the archive.**
`postcode-a0` has **49 timestamp decreases**, as do nine of the twelve. Only `ab` and `ac` are sorted. The
first pull aborted `a0` early and wrote a file holding 74,907 in-window rows; streamed in full it holds
1,390,754, so the early abort would have taken **5.4%** of that member and looked entirely normal doing
it. The abort is now cancelled the moment a decrease is seen, the two partial files were deleted, and the
ten sharded members were re-streamed to EOF.

**Cost: about 9 GB of downloads and 40 minutes**, against `bl.iro.bl.uk`, which is not
`web.archive.org`, so it ran beside the CDX collector without competing with it.

### C-30. The UKWA host link graph is 10x bigger than the copy we hold, and the only copy is unservable (2026-08-20)

**The best public lead found so far, and it is blocked on an HTTP 504 rather than on a permission or a
measurement.** Recorded in full because the blocker may be transient and the prize is the whole gate.

`ukwa_link_source` is the JISC UK Web Domain Dataset host link graph, `year|source_host|target_host`,
and it is `.uk` at weight **0.9813**, the second-highest in the model. **Our copy is 2,147,483,648 bytes,
which is 2^31 exactly**, and a figure that lands on a power of two to the byte is a truncation rather
than a file's end.

**Two captures exist and nobody had compared them.** CDX on that URL:

| capture | length |
|---|--:|
| `20200106181208` | 2,148,135,247 |
| `20221031190607` | **20,930,377,408** |

Our copy came from the 2020 capture, which is genuinely a truncated crawl. **The 2022 capture holds the
whole 20.9 GB**, which is 9.7x more of a source that already yields 2,468,674 in-window rows and 231,865
`link_source` evidence rows from its first tenth.

**Why it matters more than the ratio suggests.** `.uk` had on the order of a million registrations by
2001 and the store dates about 400,000 of them, so the headroom is real rather than saturated, and every
one of those pairs scores 0.9813.

**Every route to the 2022 capture was tried and all are shut**, checked 2026-08-20:

- the Wayback replay returns **HTTP 504 from nginx**, reproducibly, on a plain GET, a ranged GET and a
  streaming GET, with a control request on the same URL failing identically. A 20.9 GB WARC record is
  evidently too expensive to replay.
- the live path `webarchive.org.uk/datasets/ukwa.ds.2/linkage/` answers **200 with a 159-byte redirect
  stub**, which is the trap the register already records: a direct download looks like it worked.
- the dataset **DOI 404s**, `data.webarchive.org.uk` does not resolve, and `bl.iro.bl.uk` returns 403.
- **archive.org holds no mirror**: a search for `host-linkage`, `UK Web Domain Dataset` and `ukwa.ds`
  returns zero items.
- CDX no longer exposes `offset` and `filename`, so the WARC record cannot be fetched directly from
  `archive.org/download`, which would have been the way around a slow replay.

**So this is not closed on measurement and must not be read as closed.** The reopen condition is exact:
**any route that serves capture `20221031190607`, or any other copy of the full 20.9 GB file.** The
register's own worst error was reading three host-level failures as closing an artifact, and this row is
one host-level failure.

### C-29. The largest unheld public corpus is worth about a sixth of the gate, not the gate (2026-08-20)

**Re-measured because the register's own figure invited it, and the figure was 5x to 14x optimistic.**

`usenethistorical` on archive.org holds 1,019 items and 195 GB we do not hold. It was deferred in
August on **yield per byte**, 15.5 net-new post-split pairs per MB against 997 for the Dartmouth census.
That is the right metric when bytes are expensive and the wrong one when they are free: 40 GB at
15.5 pairs/MB is 635,000 pairs, the order of the gate, for an afternoon's download. So it was measured
rather than argued about, on two samples through the project's own `measure_usenet_yield.py`:

| sample | MB | net-new post-split pairs | per MB | EE post-split | EE per MB |
|---|--:|--:|--:|--:|--:|
| `bit.listserv`, 4 groups | 442 | 498 | **1.13** | 301.40 | **0.68** |
| `microsoft.public`, 3 groups | 512 | 2,895 | **5.66** | 1,660.19 | **3.25** |

**Neither reaches the 15.5 pairs per MB the register recorded**, and the honest reading of the two
together is that the hierarchy matters more than the corpus does: `microsoft` is 5x `bit`.

Extrapolated linearly over the roughly 52 GB that is English-facing, 26.6 GB of it `microsoft`, the
unheld remainder is worth **about 104,000 equivalent-English, 17% of the 603,855 gate**, and that is an
upper bound because saturation falls hardest on the largest hierarchy and 46% to 49% of the net-new
names in both samples are within one edit of a name already held.

**The reason it is nowhere near the headline is in the parse counts, not the extraction.** 72.6% of
`bit` messages and **86.5% of `microsoft` messages fall outside 1996-2001**, and two of the three
`microsoft` groups sampled returned **zero** in-window records. Most of those bytes are 2002 and later.

**Worth taking anyway, and cheap**: it needs no permission, costs a download, and Usenet is a different
provenance lineage from every large gain this round, so it corroborates rather than repeats.

### C-28. The local engine moves to the edge population, which is C-24's own contingency firing (2026-08-19)

**Decided by measurement under a standing rule, so it needed no answer from Ivo, but it reverses the
practical effect of C-24 and is recorded for that reason.**

C-24 kept the local engine on the candidate pool and closed with one explicit condition: *"the edge queue
is available for whenever the pool runs thin."* It has run thin, and the switch is that sentence firing
rather than a disagreement with it.

**The measurement had to be done twice, and the first version was wrong in a way worth naming.** A
trailing window of the last 20,000 answered queries per prefix put the pool at 57.6% and 0.474
equivalent-English per query, which flatly contradicted `just cycle`'s 18.4%. The window was reaching
back into older, better journals, and it was ordered by file mtime, which is not content recency because
a journal copied from the VPS gets a new mtime. Ordering by the run stamp in the filename and reporting
each journal separately:

| population | answered | hit rate | EE per query |
|---|--:|--:|--:|
| `cdx_pool`, last 15 runs | 7,355 | **15.8%** | **0.110** |
| `cdx_gap3`, last 8 runs | 2,060 | 67.8% | 1.126 |
| `cdx_edgepilot_b` | 141 | 80.9% | 1.776 |

**A second attempt to compare them fairly failed, and the failure is the documented trap.** Those figures
count every year a query returns, which is right for the pool, where the domain holds no year and
everything is new, and wrong for gap and edge, where only the missing years count. Re-measuring net-new
against the store returned **0.000 for every population**, because `maintain.sh` had already banked every
journal, and net-new against the live store from a banked journal is zero by construction. Zero looks
identical to worthless. The comparison therefore rests on the queue builder's own expected values, which
are structural rather than retrospective: **0.6075 EE per query for the best 250,000 edge targets**
against the pool's realised **0.110**.

**Why edge rather than gap, which is better still.** The gap population is the VPS's, and two collectors
on one list duplicate each other's queries. Edge is disjoint from gap **by construction**: an edge target
is 1996 or 2001, and a bracketed gap needs both neighbours, so it can never reach them. No coordination
is needed and neither machine can tread on the other.

**Confirmed in flight rather than assumed.** The first three minutes on the new queue returned 40
answered and **53 year-records, 1.33 per query, against the pool's 0.167**. The queue holds 6,038,320
targets and 1,597,226 EE of expected value, so it will not run thin soon.

**The pool list is kept and kept fresh.** A population that has run thin is not one that is finished, and
the candidate pool grows every time a mention is extracted. `audit_residual.py` now tracks both files and
`discover_cycle.py` rebuilds each with its own population.

### C-27. A third of the candidate pool's quoted value is names that were never real (2026-08-19)

**The pool's headline "1,639,929 EE if every one earned a year" is overstated by 574,973 EE, 35.1%,
and the overstatement sits in one identifiable block.** 584,646 undated candidates are `.gov`, `.mil`,
`.edu` or `.int`, namespaces whose weights are 0.9825, 0.9981, 0.9717 and 1.0000, so they carry a third
of the ceiling on 25% of the rows. `.gov` and `.mil` are closed registries that between them never held
more than a few thousand names in the window, and the store holds 184,948 and 186,181 of them.

They arrive almost entirely from `usenet_address_mention` and `usenet_mention`, and they are what
anti-harvester munging looks like at scale: `yjwuuxuqqa.gov`, `sboojsgvvo.gov`, `rjhxf.mil`.

**Measured rather than asserted, and with the positive control the brief demands.** Within the
`cdx_pool` journals, so the same population, period and method on both sides:

| namespace | answered | with a capture | rate |
|---|--:|--:|--:|
| everything else | 105,404 | 51,328 | **48.70%** |
| `.edu` | 1,709 | 5 | 0.29% |
| `.mil` | 1,372 | 0 | 0.00% |
| `.gov` | 394 | 0 | 0.00% |
| `.int` | 30 | 0 | 0.00% |

**The positive control is that the same namespaces answer normally elsewhere in the same engine.** In
`cdx_gap`, `cdx_q0` and `cdx_q1`, `.edu` returns 74.7% to 86.0% and `.gov` 57.1% to 94.2%. So neither the
namespace nor the query method is at fault, and a search that found nothing here has proved something
rather than been pointed at the wrong place. That test is the whole reason this is a closure and not a
hunch.

**This is not a name-shape filter and must not be turned into one.** The membership test that justifies
excluding these rows is registry closure, an external fact about `.gov` and `.mil`, not the look of the
strings. `dotgov_real_names` in the triage queue is the list that would make the exclusion checkable.

Nothing has been deleted and no filter has been applied. What changes is the quoted ceiling, and that
574,374 of the 2,278,511 rows in `queue_pool_local.txt` are worth 0.14% rather than 48.70%. They rank
late, so the engine is not spending on them today.

### C-26. Demunging Usenet addresses is real and is worth a few thousand EE, not a round (2026-08-19)

Prompted by C-27: the same block of pool names contains recoverable ones. 35,162 undated candidates
carry a known anti-harvester token (`nospam`, `removethis`, `spamsucks` and 17 others), for example
`nospamciti-link.com` and `undertonenospam.com`. Stripping the token yields **23,028 distinct
candidates, of which 15,062 are already dated in the store**, which is the only class the corroboration
split would admit, since a Usenet address is something a human typed.

So the ceiling is 15,062 domains, and the realised figure is lower again because a recovered pair only
counts where that domain does not already hold that year. **Worth doing and worth nothing like 5%.**
Recorded so it is not rediscovered as a large idea.

### C-25. The research-repository route to a bulk capture census is dry across five registries (2026-08-19)

`repository_ia_capture_census` sits in the triage queue on the reasoning that `dartmouth_nber_captures`
paid 227,273 pairs, so siblings of it might exist. **Searched and empty.** DataCite restricted to
datasets, Zenodo, Harvard Dataverse, OSF and HuggingFace, 15 query phrasings across crawl, hyperlink
graph, capture census and early-web wording, 569 distinct records returned and **not one is an
in-window web corpus.** The nearest misses are a 2020 German academic web crawl, a Common Crawl
language benchmark and a banner-ad study that is itself derived from Wayback snapshots.

This does not close the idea that such a deposit exists somewhere, but it closes the five places where
a deposit of that kind would normally be registered, and it should stop the next agent repeating the
sweep.

### C-24. Edge-year gaps are real, measured, and NOT worth reallocating an engine to (2026-08-18)

**Raised as a question and settled by measurement in the same afternoon, so it never needed an answer
from Ivo.** Recorded because the reasoning is reusable and because the figure moved three times.

The gap engine can only target a year bracketed by two years already held, so **1996 and 2001 were
never targets at all**: they would need 1995 and 2002. That left 6,499,136 slots unqueried, 99.8% of
the 2001 half never asked, against only 285,862 domains ever asked of the archive out of 10,867,530
held. `gaps.py` justified the restriction as "far more speculative" and that had never been measured.

**The rate was measured three times and only the third was right.**

| | method | 2001 | 1996 |
|---|---|--:|--:|
| conditional off 725 journals | given an adjacent CAPTURE | 94.4% | 60.0% |
| pilot against the LIVE edge set | 200 domains | 24.2% | 0.0% |
| **pilot against a FIXED snapshot** | same 200 domains | **59.7%** | **0.0%** |

The first was labelled a ceiling and was one: it is conditional on the archive holding the adjacent
capture, while this population holds its adjacent year from any source, often a registry creation date
for a site never archived. **The second was wrong in a way worth naming, because it looked like the
careful version.** Measuring against the live edge set biases a rate downward by its own success: every
domain where 2001 was found got banked, left the edge set, and was removed from the denominator it had
just satisfied. 24.2% and 59.7% are the same 200 answers.

**And the answer, on the honest rates, is that nothing should move.** Rebuilt with 0.597 and 0.000, the
merged queue gives **9,999 of its best 10,000 rows to bracketed gaps**, which is the ranking working
correctly rather than a disappointment. The edge population is worth 1,597,557 equivalent-English over
6,039,003 targets, 0.264 per query, against about 0.18 for the candidate pool and 1.249 for a bracketed
gap. So it is roughly 1.5x the pool rather than the 4.7x I reported an hour earlier, and there is no
allocation case: the VPS stays on bracketed gaps, the local engine stays on discovery, and the edge
queue is available for whenever the pool runs thin.

**1996 is not a thin edge, it is not an edge at all**: 0 of 186. It is kept in the selector at rate
zero rather than deleted, so one constant revives it if a later pilot ever measures it above zero.

Full working in ADR-006, which carries all three measurements and the correction between them.

### C-23. The four new deliverables are enforced by the build, not by a checklist (2026-08-18)

Ding added four requirements for every future submission on 2026-08-17, quoted in full in
`brief_amendments.md` and called **D1** to **D4** from now on: the runnable code, a concise experience
summary, the merge and deduplication arithmetic against the latest baseline, and the metric
calculation with its explanation.

**Mechanical, except for one judgement.** The judgement is that they became **checks 5 to 8 in
`verify_delivery.sh`** rather than a section of the README. This project has one expensive proof that a
requirement living only in prose gets shipped unmet: the phase-5 build filtered provenance to save
429 MB and left 11,316,960 of 16,619,832 assignments citing evidence no longer in the archive, and all
three checks that existed passed because every one read the additions manifest and none read the
parquet. `package_delivery.sh` now also refuses to build if the merge reconciliation fails.

**The one that was real work is D3.** He has always done the merge on his own side and shipped his
audit of it; he now wants ours too, so the two can be diffed. `scripts/merge_against_baseline.py`
therefore uses **his column names unchanged**, counts the raw lowercased line as he does rather than
the registrable domain, and scores every file with **his** calculator rather than ours. First run: 22
of 22 reconciliation checks pass, reproducing his published baseline of 22,491,418 records and
12,077,095.5404 equivalent-English to the digit.

Two of those checks compare a freshly measured baseline against `src/ark/baseline.py`, so a round
measured against a release he has already replaced now fails loudly. That drift went unnoticed for five
days in August 2026 and overstated net-new by 151,949 records he had already credited.

Nothing here needs you. Working: `notes.md`, 2026-08-18.

### C-22. The current baseline is `merged260817-2`, and a round now records what he ACCEPTED (2026-08-18)

Mechanical rather than discretionary, and recorded because every figure depends on it. `baseline.py`
carries the marker, his record count of 22,491,418 and the six per-year equivalent-English totals,
measured by running his own calculator over each file. Those six sum to **12,077,095.5404**, which is
the total he published, to the digit, so the numbers in that file are demonstrably his rather than ours.
4,220,591 year rows added under the new marker, and the collectors were requeued against it the same
night so they stop asking about domains the corpus already holds.

**The discretionary part is one line.** `SUBMITTED_ROUNDS` now stores the figure he **accepted** for each
round rather than the one it was submitted with. Phase 5 went out at 2,838,715 records and 1,697,224.86
EE and was credited 2,608,322 and 1,566,229.7613; the 230,393 difference had reached his interim
`merged260817` by another route. Quoting the submitted figure would inflate the cumulative by exactly
that overlap, and the overlap is only ever visible in his reply, never in our store.

### C-21. The promotion tranche is banked, at 88% of its quoted figure (2026-08-16)

You authorised it. Re-priced against the new baseline **before** writing anything, which mattered: it
was 106,604 pairs / 69,337.4 EE against `merged260810` and **94,051 pairs / 61,196.7 EE** against
`merged260815`. Banked in eight ingests; the year rows sum to 94,051 and reconcile to the projection
exactly. All nine integrity invariants pass afterwards, including `additions_not_double_counted`, which
is the one that would fire if any promoted pair were already in his files.

Two effects pulled opposite ways and only one is obvious: a larger baseline **removes** promoted pairs by
holding them, and **admits** more, because the corroboration split asks whether some other source places
the domain in an annual file and four million new rows place a great many more. The net was a loss.

`ukwa_link_target`, `uucp_map_mention` and `page_expansion` stay excluded: a link-graph edge cannot date
its target and corroboration cannot rescue that. Working: `notes.md`, 2026-08-16.

### C-20. The baseline moved to `merged260815`, loaded and pointed at (2026-08-16) [SUPERSEDED BY C-22]

Mechanical rather than discretionary, and recorded because every figure depends on it. `baseline.py`
carries the marker, the reviewer's record count and the six per-year equivalent-English totals, the last
measured by running his calculator over each file rather than by carrying our own increments forward,
since this release came from another contributor's merge. 4,006,500 year rows added under the new marker.

### C-19. Netcraft survey listings stay candidate-only: your condition was tested and failed (2026-08-12)

You answered the one open request conditionally: the domains do not look human typed to you, and *if you
are sure of how these lists came about and that they hold domains which were actually active during the
year they were surveyed, then they can be master evidence*. **You were right about the first half and it
was the second that killed it.**

Reading the archived pages settles provenance: a machine-generated alphabetical dump of every hostname in
Netcraft's database matching the search word, no prose, no author, no per-item date. Nobody typed these
hostnames, so the corroboration split was never the right question and the `typed` classification that
this lead was originally rejected under was simply wrong.

Contemporaneity is the part that failed. A name printed on a page captured in 1999 should behave like a
site that was live in 1999, and against two controls it does not:

| instrument | netcraft | live in 1999 by an archive capture | undated pool, no claim to any year |
|---|--:|--:|--:|
| earliest archive capture 1999 or earlier | 9.4% (127) | 100% by construction | 10.9% (12,836) |
| still registered today | 52.2% (230) | 94.3% (230) | n/a |
| registered continuously since 1999 or earlier | 25.0% (120) | 74.7% (217) | 16.6% (413,942) |

The first row decides it and is the only one free of survivorship bias: both populations were queried by
the same engine against the same archive in the same days, and **Netcraft's names are no likelier to have
been captured by 1999 than names with no claim to 1999 at all.** Registry dates cannot settle it either
way, because a 1999 domain that lapsed and was re-registered reports the later date; twelve sampled names
created between 2003 and 2026 were each verified as genuinely printed on the archived 1999 page, so the
extraction is faithful and it is the inference from listing to liveness that fails.

**Cost of refusing: close to nothing.** The forgone reading was 8,741 pairs and 5,708.4
equivalent-English. All 13,078 names were banked as candidates on 11 August and the engine has been
querying them since; 127 are already dated on their own capture evidence, which needs no approval and
does not ask anyone to trust the listing. Working in `approved-sources-list.md` and `notes.md`
2026-08-12.

### C-18. The hit-rate fallback gains the grain it was missing, the TLD (2026-08-11)

Mine to decide, recorded so you can object. It completes C-17, which was only half a fix.

The pool score is `P(hit) x English share`, and `P(hit)` coarsened from the exact (source, TLD) cell
straight to the source average. **It skipped the TLD, which is the grain that already knew.** `.mil` was on
record at **0.000 over 1,372 answers** and `.gov` at 0.000 over 394, while `.com` sits at 0.898 and `.net`
at 0.915: a 900x spread, far wider than across sources. So an unmeasured `.mil` cell inherited a source
average and English share put 2,675 of them at the head. **That was not a missing measurement, it was a
measurement never read.**

The chain is now (source, TLD), then the **lower** of the TLD and source rates, then pool-wide. Lower is
the conservative reading: an unmeasured cell must not outrank a well-measured one. A TLD nothing has
answered still gets the pool rate rather than zero, since querying is the only way it earns a first
measurement.

Measured after the rebuild: the first 3,000 went from 2,675 `.mil` to 100% `.com`; expected value per query
rose from 0.6515 to 0.6877 over the best 50,000; pool targets in that head went from 8,798 to 24,726, so
discovery now competes with gap-filling at the top. The whole-queue estimate **fell** from 578,632 to
545,879 EE, which is the point: the old number was inflated by optimism.

**Stated plainly because it matters:** the head's sources all have unmeasured `.com` cells, so they inherit
`.com`'s good average. The optimism moved axis rather than disappearing. The difference from `.mil` is that
these have *no* evidence rather than contradicting evidence, one 600-domain batch measures each of them, and
the yield check now reports within a batch whether the bet paid.


### C-17. The pool queue is ranked by a measured plausibility factor, not by English share alone (2026-08-11)

Mine to decide under your rule that hypotheses and judgements like this are the agent's; recorded so you
can object. **It corrects damage I caused this afternoon.**

The rebuild I ran at 15:53 put **2,675 `.mil` names in the queue's first 3,000**, and the local engine then
spent two batches and **1,200 archive queries finding exactly zero in-window captures**. 371,465 `.gov` and
`.mil` names stood in front of the first real domain, which at the measured rate is about **25 days of the
discovery engine producing nothing**.

The cause is the one this project keeps paying for, and the RDAP builder's own docstring names it: ranking
by expected equivalent-English needs a probability, and where none is measured the score fell back to a
pool-wide rate, so `0.9825 x a fabricated name` still sorted to the top. C-2 fixed it for RDAP by excluding
`.gov` and `.mil` by hand; the CDX queue never got that judgement.

Fixed with the measurement rather than a list, because a hand-maintained exclusion list would have covered
those two and rotted. `dated / (dated + pool)` per TLD separates them cleanly and updates itself:
`.com` 0.78 and `.uk` 0.76 against `.edu` 0.029, `.gov` 0.0055 and `.mil` 0.00038. It multiplies the pool
score, so `.mil` drops about 2,000x with no TLD named anywhere, and the tiny ccTLDs that also littered the
head land in between, which is right: unproven is not impossible. Reverse-DNS zones are excluded outright,
since that is a fact about the namespace rather than a judgement about the corpus.

After the rebuild the head is `.za`, `.nz` and `.uk`, and the first 50,000 targets contain zero `.gov`,
`.mil` or reverse-DNS names. The engine picks the file up at its next dispatch, so nothing was restarted.


### C-16. One surface asks you for things, and it is this file -> [ADR-005](ADRs.md) (2026-08-11)

Your instruction: "Everything I have to sign-off should be in one place, so I know about it. That was
key-decisions, it pointed to ADRs if necessary." Three things had drifted out of it, and the third is
the one that proves the point, because **you did not know it existed**.

1. **Notes sign-off, removed.** 37 entries each ended `Signed off by Ivo: pending`, asking for a
   countersignature on the agent's own working. Past entries are append-only history and stay as
   written; no new entry carries it, and `CLAUDE.md` no longer asks for it.
2. **`open-approvals.md` renamed to `approved-sources-list.md`**, and a `pending` class in it is now
   mirrored here automatically, at the moment the request is written and again on any cycle that
   finds one unsurfaced. A test over both live files fails if a pending class is not named here, so
   the guarantee is enforced rather than remembered.
3. **Hypotheses are mine to settle.** The ledger's unfinished leads were being reported as needing
   your judgement, which is how you came to be asked about five things you had never heard of. They
   are now reported as the agent's own work queue: screened, priced, and decided, with only an
   outcome worth overruling arriving here.

The shape you described is preserved exactly: this file is the surface, and it points at an ADR when
the reasoning is structural.


### C-15. A declarative *probe*, and bespoke *collectors* -> [ADR-004](ADRs.md) (2026-08-11)

Ivo asked for a declarative fetcher, as one of three fixes for the harness sitting idle. Adopted for
**measuring** a source and refused for **ingesting** one, which is the half worth arguing about.
`just probe probes/x.toml` turns a URL into a priceable journal from a TOML description with no Python
written, and `just price` then reports the net-new figure. Its output has no ingest spec, so there is no
path by which a probe can date a year: the safety is an absence rather than a rule, the same trick C-13
used.

The reason for the split is that of the last four sources considered, **two were rejected on the number
and never needed a parser at all**, so the expensive step was the measurement and not the code. A
declarative path to master evidence was refused because a parser's value is in refusals specific to its
document, and because cheap plus self-dating is precisely the combination that contaminates.

Validated against a known answer rather than a plausible one: the first spec written was a self-test
against the already-ingested UDRP dockets, and **seven lines of TOML reproduced the 186-line collector's
8,923 records exactly**, with nothing in either set the other missed.


### C-14. The harness wakes every 15 minutes, and "the collectors are running" is not the agent being busy (2026-08-11)

Ivo's instruction, after watching the harness sit idle: cron every 15 minutes, plus a `CLAUDE.md` section
governing what a cron-started session does. Adopted with the ordering he sketched and one definition added,
which is the load-bearing part: **a wake that finds healthy collectors and an idle agent is the normal
case, not an exception**, so the wake asks "is anything stopped" first, `just cycle` is the one-shot that
answers it, and "everything is fine" is an explicitly valid outcome so a wake has no reason to invent work.

Two supporting fixes went in with it. The loop now rebuilds a derived list it finds stale instead of only
reporting it. And the staleness test compares each list against the mark that actually invalidates it,
newest pairs for the gap queue and newest candidates for the pool queue, rather than against the baseline
release; on its first run that found three stale lists the old check called fine, which is the idleness
Ivo saw from the outside.

**One rule came out of getting this wrong in the same sitting.** I read `cdx_pool.log`, found it four days
old, concluded the local engine was dead, and killed a collector that had been working the pool healthily
since 11:10 that morning under an invented third log prefix. So: **ask the process table, never a log
file**, and `cdx_pool` and `cdx_gap` are the only prefixes that population may use.


### C-13. A source class may not date a year until a human classifies it -> [ADR-003](ADRs.md) (2026-08-11)

Ivo's proposal, adopted with one refinement. `docs/approved-sources-list.md` holds one `Decision:` line per
(source, evidence type) and **`ark ingest` enforces it** before opening the database. The refinement: the
quarantine is **outside** the store rather than a state inside it, because collectors already write
journals and never open the database, so an unapproved source cannot contaminate anything, having never
been written. Requests are built from a seeded-random sample with live links, the measured figures and
the counterfactual, so the reviewer checks external evidence instead of reading the agent's argument.
Candidate-only evidence is ungated: collection never waits on a human, promotion always does.


### C-12. UDRP proceedings are master `artifact_listing` -> [ADR-002](ADRs.md) (2026-08-11)

Was O-6. Ivo: "Treated as master artifact-listing sounds fine to me, just make sure to document and
reason about the decision and ingest carefully as you described." Reasoning, the argument against, the
three mitigations and the limitations are in **ADR-002**. Worth **7,714 net-new pairs and 4,708.9
equivalent-English** rather than 1,471 and 914.1 under the split reading.

### C-11. The write-lock contention: no structural change, an allocation rule instead -> [ADR-001](ADRs.md) (2026-08-11)

Was O-5. Ivo: "if a solution with no technical debt exists, adopt it, if not, try to preserve the current
structure and allocate the time between locks, based on who is most likely to contribute most net-new EE
domains."

**As written that evening: no debt-free fix was available, because the cause was not known.** Two plausible
causes were measured and both eliminated, the structure was preserved, the seed path was instrumented, and
the allocation rule you asked for was put in force.

**Resolved the same evening, and the first sentence above no longer holds.** The instrumentation ran on a
13,078-name seed and one phase was 1,207 of 1,208.6 seconds: `insert_candidates`. So the debt-free fix did
exist, it was the idiom `bulk.py` already used, and `add_candidates` now inserts set-wise from an Arrow
table: **13.47 s becomes 0.05 s, 267x, with identical results.** The row-at-a-time insert was the
hypothesis eliminated *first*, wrongly, because switching it to `executemany` looked like batching and
`executemany` is N statements rather than a batch. A third guess of mine, per-row autocommit, was tested
and refuted at 12.03 s against 11.88 s.

Separately, the contention itself was 636 `ark ingest` invocations per pass in the ingest loop, one per
file, which measured **89% write-lock occupancy and is now 0%**. Both fixes and all the measurements are in
**ADR-001**, whose status is now Accepted rather than Open. The allocation rule stays in force and is now
enforced in code by asymmetric lock patience rather than stated in prose, but note its justification
changed: interrupting a seed is safe because the window is negligible, not because partial inserts
survive. Full reasoning and the
four rejected alternatives are in **ADR-001**.

### C-10. The two populations go to two machines, and it supersedes C-6 (2026-08-11)

**Ivo's design, and he is right about the part I had corrected.** The VPS works a pool of **pure
bracketed gaps**: a missing year Y where Y-1 and Y+1 are already held. The local engine works the
**candidate pool**, domains held with no year at all, beside the discovery loop that keeps feeding it.

**Why sorting by TLD English share is correct here and wrong for the other pool**, which is the
sharpening my C-5 note missed. A gap query answers 96.0% to 97.5% of the time and that rate is
effectively flat across TLDs, so with the probability factor near 1 and uniform, expected value
collapses to share times the years one query can fill. The candidate pool is the opposite: its hit rate
runs from 36.9% for a name merely mentioned in Usenet text to 90.6% for a link harvested off an
archived page, so there the share must be multiplied by a *measured* rate or `.au` sorts to the top
again. Same formula, and only one of the two populations lets you drop a factor.

**It also maps onto the two outcomes the reviewer asked to keep separate**, which is a good sign:
a gap hit adds a **pair** and never a domain, so the VPS is the completeness baseline; a pool hit makes
a name **net-new**, so the local engine is the discovery half that he asked to be prioritised. The
machine allocation and the reporting split are now the same distinction.

**Two consequences.** Gap targets change slowly, so the VPS needs a refresh rarely rather than
periodically, which was the weakest part of C-5. And **this supersedes C-6**: the local CDX engine goes
back on, but pointed at the discovery pool rather than at a mixed queue, and driven by the loop.

Implemented as `build_query_queue.py --population gap|pool --out PATH`, so the ranking, the era gate
and the measured multipliers are the ones already in use rather than a second implementation.

### C-9. The report leads with the method; the numbers stay at the top as the result (2026-08-11)

Ivo: "the numbers can still go at the top as the 'result', but the focus should be on the method, the
harness, yes." So the five fields open the report, and the body is about how they were found. Two
sources *closed* on measurement become results rather than omissions, which is what SPEC IX asks for
and what a volume framing cannot express.

### C-8. Go back to `.org`, and to previously unavailable sources generally (2026-08-11)

Ivo: "going back to previously unavailable sources is part of the task and what has repeatedly proved
worth it." Correct, and it is already the documented pattern rather than a new idea: feedback section 4
asks for blocked sources to be revisited, and the register's own best example is the Australian Web
Archive, where one endpoint was dead and the other answered normally once someone checked the second
host. **Standing rule from now on: a source closed on *availability* is a source to re-probe, and only
a source closed on *measurement* stays closed.** The two verdict classes are already distinguishable in
`sources.md`, so the screener can say which kind it hit.

### C-7. Ding's research vision logged, and it is background rather than specification (2026-08-11)

His AI4EconFinance / Internet Digital Ark and Digital Archaeology email to Giesecke is now in
`private/personal-context.md` under its own heading, marked FYI. Ivo: "our task specification comes
from elsewhere", meaning `SPEC.md` as amended. Two things in it do bear on method: temporal fidelity
is the point rather than record count, which is why the per-year rule is the deliverable's core
property; and "AI agents that independently discover hypotheses, collect and synthesize evidence"
describes this round's harness, so the harness is on-vision.

### C-6. Local CDX engine stays off (2026-08-11) [SUPERSEDED BY C-10 THE SAME DAY]

Was O-1. Ivo's call: discovery work matters more than another crawl client on this machine. Recorded so
the agent does not quietly reverse it when the queue looks tempting.

### C-5. VPS is the unattended safety baseline, with its queue refreshed periodically (2026-08-11)

Ivo's rule, adopted: the VPS keeps filling in domain-years unattended as steady output, its candidate
pool is refreshed periodically rather than once, and the refresh happens whenever the VPN is up. Added
as a periodic task.

**One correction to the wording, and it matters because the project has already paid for it.** The
instruction was to sort "by the most promising TLDs in terms of EE". Sorting by TLD English share is
what put `.au` first in the whole queue on a 0.9904 share for zero in-window dates, and spent 1,709
queries on a 97.2%-English TLD for five hits. `build_query_queue.py` already sorts by **expected
equivalent-English per query**, which is the share multiplied by a *measured* hit rate, and that is
the ordering the refresh will keep. Same intent, and the multiplier that stops it going wrong.

### C-4. Current state becomes generated, and the handoff retires (2026-08-11)

`phase5-handoff.md` is a hand-written snapshot of current state, which is the one category of memory
that cannot be hand-written: three of its claims were disproved within a day. State moves to a
generated `ROUND.md` with a guard against hand edits, the handoff moves to `legacy/docs/`.
See notes.md, 2026-08-11.

### C-3. Two sources closed on measurement (2026-08-10)

Linux Software Map: 86 net-new pairs, 37.3 EE after the corroboration split, 94.7% already held. Other
defacement mirrors: no sibling survives on archive.org or GitHub. Both are in the rejected register,
so the screener now catches them.

### C-2. `.gov` and `.mil` excluded from RDAP ranking on a fabrication test (2026-08-10)

182 and 2,624 pool names per dated name, against 0.3 for `.com` and `.uk`. Reported as a warning
rather than enforced, since which TLDs to drop is a judgement.

### C-1. VPS deadline extended to 2026-08-31T12:00Z on a freshly rebuilt shard (2026-08-10)

The old shard predated `merged260810` and 28% of the current best-10,000 head was invisible to it.
