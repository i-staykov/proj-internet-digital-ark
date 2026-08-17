# Internet Digital Ark: round 5

Additions to the 1996-2001 annual domain lists, measured against `[BASELINE]`. Every figure is
generated from the evidence store, not typed, so no table can drift from the files shipped beside it.

---

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

Lines 1 and 2 are the `[BASELINE]` totals, unchanged, since this increment is not yet merged. The 5%
threshold is [EE5PCT] equivalent-English. The increment covers [UNIQUE] distinct domains, of which
**[NEWDOMAINS] appear in none of the six baseline files in any year**; mean weight per record is [EEMEAN].

[PER_YEAR_TABLE]

The baseline column counts registered domains, the output unit section X asks for, so it reads lower
than the [BASELINEPAIRS] raw lines of line 1. Both describe the same six files.

[CUMULATIVE]

---

## 2. What was added, and what dates each year

Four routes account for almost all of it. `sources.md`, shipped beside this report, carries the full
entry for each: acquisition command, date semantics, measured yield and caveats.

| Route | What dates a year | Net-new pairs |
|---|---|--:|
| the Internet Archive's own capture census, a 2017 Dartmouth/NBER release | the archive's count of captures it holds for that host in that calendar year | 227,273 |
| a published compilation of registry creation dates over 171M domains | the registry's own creation date, which dates that year and no other | 2,165,523 |
| the UK Web Archive host link graph, already held since July | the crawl date on the link record | 92,646 |
| the January 1997 Internet Domain Survey, recovered from a dead host | the survey edition date | 115,104 |

Two of these needed no new download and one needed no querying, which is the finding of the round and
is taken up in section 5.

**Each was verified before admission, not after.** The capture census agrees with our own independent
CDX querying of the live archive on **[DARTMOUTH_AGREEMENT] (domain, year) pairs**, including exact
same-day agreement on single-capture years. The registry dates were falsified against a constraint
nobody encoded: a TLD cannot predate its own delegation, and across the six TLDs delegated in 2001 the
file holds 21,698 in-window rows and **zero** dated before 2001.

**The narrowest evidence is also the largest contributor, and it is under-claimed deliberately.** A
creation date attests registration, not activity, and it attests one year. Where a domain was
registered in 1997 and ran until 2001, this route supplies 1997 alone; the other four years must still
be earned from a capture or a survey. The parser emits one evidence row for one year, so `assign_year`
cannot write a second.

---

## 3. Source contribution statistics

Every net-new record by the source that dated it, with the raw and equivalent-English increase for each.

[EE_SOURCE_TABLE]

All are master, meaning eligible for the annual files. Separately, **[CANDIDATES] domains carry no
year-specific evidence** and ship as `candidates.txt`, never mixed into the annual masters. They are
hostnames extracted from archived pages, typed `link_target`, which the taxonomy makes structurally
incapable of dating a year.

---

## 4. CDX execution notes

`ark cdx`, this project's client for the public Wayback CDX API, driven by `supervise_cdx_pool.sh`
over two disjoint populations on two machines: the VPS works pure bracketed gaps as a completeness
baseline, the local engine works the candidate pool beside the discovery loop that feeds it.

[CDX_TABLE]

[CDX_FAILURES]

Failures adjust the request rate rather than stopping the campaign. The client sends an honest
User-Agent naming the project and a contact address, runs modest concurrency, honours `Retry-After`,
and backs off on 429, 503 and 504 between a floor and a ceiling. An interrupted batch is republished
rather than lost.

**Worth further expansion, but no longer the binding constraint.** Roughly 2.5 million candidate names
sit unqueried against engines clearing a few hundred requests an hour. The queue was never the limit
this round, and that observation is what redirected it toward bulk dated corpora.

---

## 5. How this contributes to an autonomous discovery system

**The finding worth reporting is a negative one about our own strategy.** Collection had been optimised
against request throughput at a single archive. When the baseline was reissued mid-round carrying
another contributor's UMN DRUM delivery, the shape of it was the lesson: one bulk dated corpus was worth
roughly twenty times our previous round of per-domain querying. A bulk dated corpus does not have that
constraint at all. The system was re-aimed at that shape, and sections 2 and 3 are the result. The
measured comparison now guides ranking: the capture census returned **997 net-new pairs per megabyte**
against **15.5** for a Usenet sample, so sources are priced by yield per byte before a collector is built.

**The evidence wall is structural, not procedural.** `domain_year.evidence_id` is `NOT NULL` and
foreign-keys `evidence`. No code path can write a year assignment without naming the observation behind
it, so an agent has wide latitude about what to try and none about what counts as proof. A taxonomy
decides which evidence may date a year: master-eligible types are [MASTERTYPES], while `link_target`,
a hostname seen in an archived page, never can, and `assign_year` refuses it.

**A human gate an agent cannot argue past.** `approved-sources-list.md` carries one decision per
(source, evidence type) and `ark ingest` refuses any master-eligible class that is pending or absent.
Requests are machine-generated from a seeded-random sample with live links, the measured counterfactual
and the reasons to refuse, so the reviewer checks external evidence instead of reading the agent's
argument. Both large sources here passed that gate before a single row could date a year.

**Nine invariants run before anything ships**, enforced by a pre-commit hook rather than remembered.
They assert among other things that no exported addition carries baseline evidence for that year, so
the net-new figure cannot be inflated, and that no master-eligible evidence sits unassigned.

**A discovery loop that does not run out.** A candidate the engine dates was by construction live in
the window; its archived page names contemporaries; those return to the pool. Because extracted
hostnames can never date a year, the loop needs no approval and is safe unattended. Measured this
round: link-looking pages harvested 391 domains against 53 for home pages, a 7.4x improvement, but
yielded 5 net-new because 386 were already held and dated. That negative result is why bulk link graphs
now outrank page-by-page expansion.

**The harness.** A standing brief is loaded into every agent session holding only what does not change:
the evidence rule, the metric, which document is authoritative, and a register of traps that have each
produced a confident wrong answer. Collectors hold absolute deadlines and run with no agent present.
The agent re-invokes itself on a heartbeat, and a wake that finds everything healthy must spend itself
hunting a new source. Decisions land in an append-only dated log; anything needing a human appears on
exactly one surface. **[DATASETS_SEARCHED]**

---

## 6. Limitations, and what is worth expanding

The capture census is a 2017 snapshot, so its per-year counts are a floor on what the archive holds
today, never a ceiling. The registry compilation covers domains still registered in December 2024, so
it is survivorship-biased: a name created in 1998, dropped, and re-registered in 2015 reads 2015 and
falls out of the window. The direction of error is loss, and the reverse cannot happen.

**Worth expanding, in order.** Bulk dated corpora first, since one such file outweighed an entire round
of per-domain querying and two more were found this round. National web archive link graphs second,
where the year association is explicit: `ukwa_link_source` returned a mean weight of 0.9803, the highest
here, because a national link graph is almost entirely `.uk`. Per-domain CDX querying third, which still
pays but is bounded by request rate rather than by candidates. Not worth expanding: the closed families
in `sources.md`, each recorded with the measurement that closed it.

---

## 7. Reproduction

`README.md` in the archive gives the full order. `masters/` holds the merged annual lists and `additions/` this round's net-new
records, one registered domain per line, deduplicated within each year; `candidates.txt` holds the names
with no year evidence; `provenance/*.parquet` joins every (domain, year) to the evidence row justifying
it, so any line of any annual file traces to an observation; `journals/` holds the raw per-source records
before interpretation; `source/source.tar.gz` is the repository at the commit that built the delivery.

[REPRODUCTION_RESULT]
