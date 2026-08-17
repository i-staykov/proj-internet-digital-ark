# Internet Digital Ark: round 5

Additions to the 1996-2001 annual domain lists, measured against `[BASELINE]`. Every figure is
generated from the evidence store, so no table here can drift from the files shipped beside it.

---

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

Lines 1 and 2 are the `[BASELINE]` totals, unchanged, since this increment is not yet merged. The
increment covers [UNIQUE] distinct domains, of which **[NEWDOMAINS] appear in none of the six baseline
files in any year**.

[PER_YEAR_TABLE]

The baseline column counts registered domains, so it reads lower than the raw lines of line 1; both
describe the same six files.

[CUMULATIVE]

---

## 2. What was added, and what dates each year

[ROUTES_TABLE]

`sources.md`, shipped beside this report, carries the full entry for each: acquisition command, date
semantics, measured yield, caveats.

**Both new sources were verified before admission.** The capture census agrees with our own independent
CDX querying of the live archive on **[DARTMOUTH_AGREEMENT] (domain, year) pairs**, including exact
same-day agreement on single-capture years. The registry dates were tested against a constraint nobody
encoded: a TLD cannot predate its own delegation, and across the six delegated in 2001 the file holds
21,698 in-window rows and **zero** dated before 2001.

One caveat on checking the census yourself: **the archive.org item it came from stopped serving on
2026-08-17**, the day after we downloaded it, though it is still in the search index at its full size.
Its records remain checkable regardless, because each carries a live Wayback URL for that host and year;
`sources.md` gives the detail.

**The largest contributor carries the narrowest evidence, and is under-claimed deliberately.** A
creation date attests registration, not activity, and only for one year. A domain registered in 1997
and live until 2001 gets 1997 from this route alone; the other four years must be earned from a capture
or a survey. The parser emits one evidence row for one year, so a second cannot be written.

---

## 3. Source contribution statistics

[EE_SOURCE_TABLE]

Every row above is master, so eligible for the annual files. Separately, **[CANDIDATES] domains have no
year-specific evidence** and ship as `candidates.txt`, kept out of the annual masters.

---

## 4. CDX execution notes

`ark cdx`, this project's client for the public Wayback CDX API, over two disjoint populations on two
machines: the VPS works bracketed gaps as a completeness baseline, the local engine works the candidate
pool beside the discovery loop feeding it.

[CDX_TABLE]

[CDX_FAILURES]

An interrupted batch is republished rather than lost, so a stopped run costs only the queries it had not
yet made.

**Still worth expanding, but no longer the binding constraint.** Roughly 2.5 million candidate names sit
unqueried against engines clearing a few hundred requests an hour, so the queue was never the limit this
round. That is what redirected it toward bulk dated corpora.

---

## 5. How this contributes to an autonomous discovery system

**The useful finding this round is a negative one about our own strategy.** Collection had been
optimised against request throughput at a single archive. When `[BASELINE]` arrived carrying another
contributor's UMN DRUM delivery, its shape was the lesson: one bulk dated corpus was worth roughly
twenty times our previous round of per-domain querying, because such a corpus does not have that
constraint at all. Re-aiming the search at that shape produced sections 2 and 3.

**That is now a ranking rule rather than an anecdote.** Sources are priced by yield per byte before a
collector is written: the capture census measured **997 net-new pairs per megabyte** against **15.5**
for a Usenet sample, a 64x difference that no amount of extra querying closes. The same measurement
retired a route we had been developing: seeding link-looking pages rather than home pages harvested 391
domains against 53, a 7.4x improvement, yet yielded only 5 net-new, because 386 were already held and
already dated. Page-by-page expansion is therefore now outranked by bulk link graphs, and the negative
result is recorded so it is not rediscovered.

**The machinery enforcing this is as documented in previous rounds** and ships in the archive. One note
on how it behaved: both new sources had to clear the human gate before a single row could date a year,
on a machine-generated request built from a seeded-random sample with live links and the measured
counterfactual, so the decision rested on external evidence rather than on the agent's argument.

**Negative results are first-class.** [DATASETS_SEARCHED]

---

## 6. Limitations, and what is worth expanding

The capture census is a 2017 snapshot, so its counts are a floor on what the archive holds now. The
registry compilation covers domains still registered in December 2024, so it is survivorship-biased: a
name created in 1998, dropped, and re-registered in 2015 reads 2015 and falls out of the window. The
direction of error is loss, and the reverse cannot happen.

**Worth expanding, in order.** Bulk dated corpora first, since one such file outweighed a whole round of
querying and two more were found here. National web archive link graphs second, where the year
association is explicit and the weight is high: `ukwa_link_source` returned a mean of 0.9803, the best
of any source, because such a graph is almost entirely `.uk`. Per-domain CDX querying third, bounded by
request rate rather than by candidates. Not worth expanding: the closed families in `sources.md`, each
recorded with the measurement that closed it.

---

## 7. Reproduction

`README.md` in the archive gives the full order. `masters/` and `additions/` hold the merged annual
lists and this round's net-new records, `candidates.txt` the names with no year evidence,
`provenance/*.parquet` every (domain, year) joined to the evidence row justifying it, `journals/` the
raw per-source records, and `source/source.tar.gz` the repository at the commit that built the delivery.

[REPRODUCTION_RESULT]
