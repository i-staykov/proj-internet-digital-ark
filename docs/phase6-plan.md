# Phase 6: the plan, in your terms

Written 2026-08-18, for you rather than for an agent. Read once and keep in your head. The previous
round's version is [phase5-plan.md](phase5-plan.md) and stays as history.

---

## 1. Where you stand

Phase 5 was accepted with **nothing rejected**. He checked file integrity, domain formatting,
duplication, evidence coverage and the equivalent-English calculation, and found no invalid record, no
duplicate, and every domain-year backed by evidence. That is the second round running where the
evidence rules survived someone checking them.

| | |
|---|---|
| His corpus now | **22,491,418** records, **12,077,095.5404** equivalent-English, released as `merged260817-2` |
| What he credited phase 5 | **2,608,322** records, **1,566,229.7613** EE, **14.901054%** |
| What you sent | 2,838,715 records, 1,697,224.86 EE, 20.3337% |
| Your four rounds together | 5,136,061 records, 3,018,005.5168 EE, **24.9895%** of the corpus as it stands |
| Round 6 so far | 9,285.9 EE, 0.0769%, measured 2026-08-18 00:20 UTC |

**Two of those numbers went down and neither is bad news.** The credited round is 130,995 EE below the
submitted one because 230,393 of your records had already reached his interim `merged260817` through
another contributor before he merged yours. And the cumulative reads 24.99% rather than the 37.73% you
quoted on Sunday because the corpus itself grew 44.7% in ten days, roughly 1.57M of that yours and
2.16M someone else's. You did not lose anything; the denominator moved.

**5% of this baseline is 603,854.78 EE.** Last round it was 417,341.97. The target gets harder every
time anyone succeeds, which is the shape of the competition rather than a problem with your work.

## 2. The one genuinely new fact this round

He ships a **per-year merge audit for each contributor** alongside the baseline, and it is the first
time you can see your work beside someone else's on the same corpus.

| year | yours accepted | the other contributor's | who is growing that year |
|---|--:|--:|---|
| 1996 | 58,288 | 46,622 | even |
| 1997 | 188,186 | 245,075 | them, slightly |
| 1998 | 246,604 | 623,173 | **them, 2.5x** |
| 1999 | 444,023 | 1,423,310 | **them, 3.2x** |
| 2000 | 688,340 | 2,116,142 | **them, 3.1x** |
| 2001 | **982,881** | 267 | **you, almost entirely** |

Their 2000 submission had **791,037 records rejected for missing evidence or invalidity**; yours had
zero. So they are working faster and looser, and 1998 to 2000 is being covered by them either way.

**What follows.** 2001 is where registry creation dates reach and the archives do not, and that is
your route rather than a coincidence. The years 1998 to 2000 are the ones where a marginal record is
most likely to be one he already holds by the time he merges, which is exactly what cost you 230,393
records last round. Prefer sources that reach 1996, 1997 and 2001, and prefer sources whose evidence
nobody else is producing.

## 3. What he asked for, and what it means here

> Please continue expanding the historical domain list and exploring additional ready-made historical
> datasets, bulk dated corpora, national web-archive link graphs, academic repositories, registry
> datasets, and other innovative automated discovery methods. Please also continue reviewing whether
> previously successful methods can produce further additions.

Six shapes and one instruction to re-mine what already worked. In order of what phase 5 measured:

1. **Bulk dated corpora.** One such file was worth roughly twenty times a whole round of per-domain
   querying. Two were found last round. This is the highest-yield shape and the hunt never stops.
2. **National web-archive link graphs.** `ukwa_link_source` returned the best mean weight of any
   source at 0.9803, because a national graph is almost entirely `.uk`.
3. **Academic repositories and registry datasets.** UMN DRUM is his own worked example; the point is
   the pattern, not that dataset.
4. **Re-mining what worked.** The two largest corrections last round were both to our own errors: a
   parser reading 6.76% of a file we already held, and a survey filed as unrecoverable that was intact
   under a successor hostname. Both were free.

**Not worth expanding**, and recorded so it is not rediscovered: page-by-page link expansion. Measured
as a matched A/B, selecting link-looking pages harvested 7.4x more domains and yielded 5 net-new,
because 386 of 391 were already held and already dated.

## 4. What is running tonight

| | on what | until |
|---|---|---|
| local CDX | `queue_pool_20260818.txt`, 2,288,555 targets, 150,385 EE expected | 2026-08-18 04:00 UTC |
| VPS `cdx_gap3` | `queue_gap_vps_20260818.txt`, 347,065 bracketed gaps, 173,233 EE expected | 2026-08-18 04:00 UTC |
| RDAP | `pool_targets_20260818.txt`, 288,407 names, `.uk` first | 6 batches |
| ingest loop | banks every journal as it lands | pass 900 |

All three queues were rebuilt **after** `merged260817-2` was loaded, so none of them spends a request
on a domain-year the corpus already holds. The deadline is the announced internet gap, not a judgement
about when to stop.

## 5. What needs you

Nothing is blocked. [key-decisions.md](key-decisions.md) under `## OPEN` has four standing items, two
of which are questions you have not answered yet and neither of which stops collection: whether to ask
Nominet for bulk `.uk`, and whether I may draft a letter to a US federal agency in your name. The
triage queue holds 47 found-but-unpriced sources, which is a counter rather than a request.
