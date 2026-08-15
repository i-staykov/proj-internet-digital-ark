# Finding and pricing a new source

**How to decide whether something is worth ingesting, before spending a night on it.** This is the
discipline the project has actually paid to learn, written down so it does not have to be relearned.
[sources.md](sources.md) is the register of what has been tried; this is the method.

Read this before proposing a source, and read `sources.md`'s rejected table before proposing one that
sounds obvious. Roughly forty source families have been evaluated and rejected, each with the
measurement that killed it, and rediscovering one is the single most likely way to waste a session.

---

## 1. What a source has to provide

A domain in an annual file is a **claim about a year**, and every claim names the observation that
supports it. So the only question that matters about a candidate source is: **does each item carry
its own date?**

- **Master-eligible evidence** ties one domain to one specific year. Types are `prior_reused`,
  `cdx_timestamp`, `artifact_listing`, `link_source`, `dated_directory`, `whois_creation`
  (`src/ark/evidence_types.py`).
- **Candidate-only evidence** (`link_target`) shows a domain exists but says nothing about when. It
  never produces an annual row. Candidate pools are valuable, and score nothing until dated.
- **No inference, ever.** A capture in 1998 evidences 1998 and nothing else. Do not interpolate
  across years, do not assume continuity, do not date a domain from a page's "last modified".
- Undated lists are **seed-only**. They still have value, since the CDX and RDAP engines can date
  them, but say so plainly instead of counting them as additions.

Two kinds of master evidence behave differently and the difference decides how much scrutiny a source
needs:

| | example | corroboration |
|---|---|---|
| **self-dating** | a capture timestamp, a registry creation date, a dated artifact listing | none needed: the record is authoritative about the year |
| **typed inside a dated artifact** | a hostname a human wrote in a Usenet post, an OCR'd magazine page | **takes the corroboration split**: the pair is admitted only if another source already places that domain in an annual file |

The corroboration split, not the extraction pattern, is the wall that keeps a bad regex out of the
annual files. That is why widening recall over a human-authored corpus is safe and widening it over a
self-dating one is not.

**The trap inside "what dates one item" is not an absent date, it is a date that dates the wrong thing.**
A source with no date at all is easy to refuse. A source carrying a plausible date next to a hostname is
the one that gets ingested and is wrong, so the question has a sharper form: **a per-entity date is not a
per-field date.** Ask what the date attaches to, and refuse it unless it attaches to the observation being
borrowed. Four instances, each found separately before the pattern was named:

- **the dated-dataset fallacy**: a per-entity current-state row, read as dating an address it merely
  carries today
- **MARC 856**: a catalogue record entered in 1998 may have acquired its URL field in 2005, so the
  record's creation date dates the record and not the link
- **a trademark filed on an intent-to-use basis**: evidences an intention, not a live domain, and only a
  use-in-commerce filing with a dated specimen says the site existed
- **Netcraft**: a name printed on a page captured in 1999, where the capture dates the *page* and the
  inference from listing to liveness is the step that failed, measured

A useful test: if the source were re-published tomorrow with today's date, would the item's date change?
If yes, the date belongs to the container and not to the observation.

## 2. The acceptance bar

A source is worth building a collector for when all three hold:

1. **Per-item year evidence**, as above. Anything else is seed-only.
2. **At least ~5,000 net-new `(domain, year)` pairs**, measured on a sample or credibly extrapolated
   from one.
3. **A mean equivalent-English weight that pays.** Report the measured mean weight of the **net-new**
   part, not of the source. At or above 0.6 is good. Below about 0.4 the volume has to justify itself
   explicitly.

Never present an unmeasured source as measured, and never pad a list to reach a count. Ranking three
honest findings beats reporting five with two guesses in them.

## 3. The pattern that has actually worked

Every large win this project has had is the same shape: **a corpus where each item carries its own
date and mentions hostnames.**

| source | the dated artifact | domains added |
|---|---|---|
| `usenet_announce` | a Usenet post's own posting date | 335,504 |
| `early_web_cdx` | Internet Archive capture timestamps | 2,160,814 |
| `isc_survey` | dated DNS survey editions | 1,314,476 |
| `rdap_snapshot` | the registry's own creation date | 48,394 pairs |
| `uucp_map_registry` | a registry dump with publication and approval dates | 28,471 pairs |
| `page_directory` | an archived directory page's capture date | 5,220 |
| `tucows_catalogue` | dated software catalogue pages | 3,464 |

The corollary is the fastest filter available: if you cannot say in one sentence what dates an
individual item, the source is seed-only and the conversation is over.

## 4. Measure before ingesting, and measure against the store

**The standing rule is to measure the yield against the live store before ingesting anything.** It is
not caution for its own sake. Three of five sources assessed in one day were rejected after
measurement contradicted the estimate, two of them by two orders of magnitude, and one of those
measurements avoided a 19.35 GB download in two minutes.

Four ways this project has got a projection wrong, all recorded in [notes.md](notes.md) because each
cost real hours:

- **Wrong counting unit.** The NYPW index was estimated at 27,276 net-new domains and measured at
  **53**. The estimate compared registered domains against raw hostname lines.
- **Linear extrapolation over a corpus that repeats itself.** A 120-archive pilot projected 1.9M
  equivalent-English against a true 62,821. A sample of 0.58% of a self-repeating corpus proves the
  shape, never the total. Fit the saturation curve as well as the line, and quote the lower one.
- **A snapshot that went stale mid-run.** A header projection said ~10,889 EE and delivered 1,038.4,
  because it was measured against a store export from three hours earlier and another ingest had
  written 102,577 overlapping pairs in between. **A snapshot is valid only until the next ingest.**
  Re-export after any ingest, or open the store read-only and measure against it.
- **Quoting the pre-split number.** A raw recovered set of 2,440,926 pairs admitted 107,304 after the
  corroboration split. Quoting the raw figure would have overstated the source 24-fold. **Always
  quote the post-split number.**

One structural finding worth carrying into any new lead: **a source that selects for authority cannot
be net-new, however large it is.** Usenet `Path:` relay hops, institutional link directories and
award galleries all failed the same way. 7.1 million accepted relay hops were only 4,736 distinct
domains, and a CDX-derived baseline already holds every one of them in every year. Ask what
population a source selects for before asking how big it is.

Its sibling, and the cheaper of the two to apply: **a corpus derived from the Internet Archive cannot
be net-new against a baseline that is itself Internet-Archive-derived.** Ask what a source's *upstream*
is before pricing it at all. This closes a whole family in one question rather than one measurement
each: the TREC web collections, Stanford WebBase and Early Web CDX are all downstream of the same
1996-1997 crawls the baseline comes from, and the two of them that were actually measured returned
**0.01% and 0.01% net-new**. It also explains why the Australian Web Archive priced at exactly zero
AWA-only pairs: it is Internet Archive data wearing a different interface. The tell is a dataset
described as "built from a crawl donated by the Internet Archive".

**That rule has one exception and it is the most valuable family we know of, so read it before
applying the rule.** Being IA-derived is fatal when the source is a *re-serving* of captures the
baseline already drew on, and is the opposite of fatal when it is a **different projection of IA's
holdings, delivered in bulk**. The distinction is not about provenance, it is about which constraint
binds: our coverage of the Internet Archive is limited by **our own query rate**, not by IA's
holdings. Measured 2026-08-15: **239,631 domains have ever been asked at CDX** against 2.5M sitting in the
pool, and the two engines clear about **713 requests an hour** between them. Those two numbers move, and
the ratio between them is the argument rather than either figure: at any plausible rate the pool is years
of work, so anything that converts a per-domain question into a file download is worth more than its size
suggests.

So a bulk index that names hosts IA holds, without our having to ask about each one, converts our
scarcest resource into a file download. That is exactly why the UK Web Archive host link graph is the
best-performing shape ever measured here at **90.4%**, against 46.0% pool-wide: it **is** Internet
Archive data, and it pays because a link graph surfaces hosts that IA's own CDX rows do not return as
captured sites. Judge such a source on the English share of what it covers and on whether it can
actually be downloaded, never on its upstream.

Where an estimate is unavoidable, **label it in the same sentence as the number**. Most figures in
this project are measurements, which is exactly what makes an unlabelled projection dangerous.

## 4a. Ask the disk and the store before asking the network

**Three times in two days a question that looked like it needed a fetch was answered for free**, so this
is a step rather than an instinct. Before spending a request on a lead, ask whether 411 GB of Usenet, the
rest of `data/raw/`, or the store itself already contains the answer.

- **Anti-spam blocklists**, 1997-2001. Looked like a fetch. Every in-window list is IP-based, so there was
  nothing to extract, and the domain-bearing version of the idea, spam sightings, was already ingested:
  13 `news.admin.net-abuse.*` groups on disk, **173,526 evidence rows over 168,075 domains**.
- **The domain aftermarket.** Queued as needing archived listing pages and Wayback requests we could not
  spare. `alt.domain-names.forsale`, `.registries`, `.wanted` and `.disputes` are on disk and ingested:
  **36,425 rows over about 32,685 domains**. The population was measurable for nothing, and the
  measurement moved the lead from potential 40 to 22.
- **The CA Domain Registry.** Found as a hunt for archived daily registration lists; it is
  `can.domain.mbox.zip`, already held, carrying 37,578 `Date-Approved:` fields.

The general form: **a question about a population is usually cheaper to answer than a question about a
source.** "Do names of this kind earn years?" can be asked of the store in one query; "does this website
still exist?" costs a request and often answers a worse question. The store also answers honestly about
overlap, which is the number that decides everything here and the one a fetch never tells you.

And the corollary that cost the most: `LIMIT 4` is not a census, a heading is not a schema, and a
maximum index is not a count. Ask the whole file.

## 5. Before proposing a source, check it is not already dead

`sources.md` has a rejected register: each entry names the measurement that closed it and, where one
exists, the condition that would reopen it. It includes several leads that look obvious and are not:
DMOZ pre-2002 dumps (archive.org holds exactly one ODP item, from 2015), IRCache and NLANR proxy
traces (domain squatted, FTP dead, zero archive.org items), the Internet Traffic Archive (the ideal
1996 Berkeley dataset has anonymised URLs), shareware CD-ROM catalogues (archive.org cannot list
inside an ISO, so density costs a full ISO download per item, and the items carry no date metadata),
web rings (a prefix query returns zero because the member lists are query strings off the site root),
and the Australian Web Archive (works, and is redundant with the Internet Archive: zero
AWA-only pairs).

An automated discovery agent will walk straight back into all of these unless it reads that register
first. Reading it is the cheapest step in the process.

## 6. What phase 5 changes about all of this

The reviewer's [amended brief](brief_amendments.md) asks for the generating and the pricing to be
**automated**: hypotheses proposed, tested against dated evidence, and kept or discarded, on a loop,
rather than a human picking the next lead by hand.

Nothing above changes. The acceptance bar, the corroboration split and the measure-before-ingesting
rule are what make an automated proposal safe to act on, and they are the reason a harness can be
trusted to run unattended at all. What changes is who applies them and how often.

The concrete shape that follows from sections 1 to 5:

- **A hypothesis is a source plus a claim about what dates its items.** That is the unit the harness
  should generate, because it is the unit section 1 can reject cheaply.
- **Pricing is a sample measured against the live store**, reported as net-new pairs, net-new domains
  and mean weight of the net-new part, with projections labelled. Section 4 is the checklist for not
  fooling yourself, and every item on it is a mistake already made once.
- **The two outcomes are counted separately**: a genuinely unknown domain and a filled year on a
  known domain are different results, and the reviewer asked for both to stay visible.
- **The dead-lead register is an input, not an afterthought.** A proposal that duplicates a closed
  lead should be killed before it costs a request.
