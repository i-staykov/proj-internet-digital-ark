# Internet Digital Ark: round 5

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 15,428,507 |
| 2. Equivalent-English total | 8,346,839.3737 |
| 3. Increment | **2,838,732** records |
| 4. Equivalent-English increment | **1,697,225.1735** |
| 5. Equivalent-English growth rate | **20.3337%** |

Lines 1 and 2 are the `merged260815` totals, unchanged, since this increment is not yet merged. The
increment covers 2,666,867 distinct domains, of which **1,790,909 appear in none of the six baseline
files in any year**.

| Year | merged260815, this counting unit | Additions | Capture-backed |
|---|--:|--:|--:|
| 1996 | 649,765 | 63,164 | 39 (0.1%) |
| 1997 | 1,358,646 | 230,192 | 289 (0.1%) |
| 1998 | 1,363,435 | 283,156 | 4,837 (1.7%) |
| 1999 | 2,745,535 | 513,761 | 16,602 (3.2%) |
| 2000 | 4,675,256 | 765,569 | 27,144 (3.5%) |
| 2001 | 2,991,302 | 982,890 | 225,540 (22.9%) |
| **Total** | **13,783,939** | **2,838,732** | **274,451 (9.7%)** |

The baseline column counts registered domains, so it reads lower than the raw lines of line 1; both
describe the same six files.

**Cumulative.** Across the four rounds shipped so far this project has added 5,366,471 domain-year records worth 3,149,000.9290 equivalent-English, which is **37.7269%** of the 8,346,839.3737 the corpus holds today. Round 1 predates the equivalent-English metric, so its records are the reviewer's own confirmed count and the weight beside it is measured over the two releases either side under the unchanged model.

| Round | Records | Equivalent-English |
|---|--:|--:|
| 1 | 1,429,524 | 756,559.2864 |
| 3 | 151,949 | 91,814.6880 |
| 4 | 946,266 | 603,401.7811 |
| **5, this one** | **2,838,732** | **1,697,225.1735** |
| **Total** | **5,366,471** | **3,149,000.9290** |

---

## 2. What was added, and what dates each year

| Route | What dates a year | Net-new pairs |
|---|---|--:|
| the Internet Archive's own capture census, a 2017 Dartmouth/NBER release | the archive's count of captures it holds for that host in that calendar year | 227,273 |
| a published compilation of registry creation dates over 171M domains | the registry's own creation date, which dates that year and no other | 2,165,523 |
| the UK Web Archive host link graph, already held since July | the crawl date on the link record | 92,646 |
| the January 1997 Internet Domain Survey, recovered from a dead host | the survey edition date | 115,104 |

`sources.md`, shipped beside this report, carries the full entry for each: acquisition command, date
semantics, measured yield, caveats.

**Both new sources were verified before admission.** The capture census agrees with our own independent
CDX querying of the live archive on **138,760 (domain, year) pairs**, including exact
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

| Source | What carries the date | Evidence type | Admissible | Net-new pairs | Equivalent-English |
|---|---|---|---|--:|--:|
| `domain_creation_bulk` | the registry's own creation date for that domain | `whois_creation` | master | 2,165,523 | 1,241,812.0 |
| `dartmouth_nber_captures` | the archive's own count of captures it holds in that year | `cdx_timestamp` | master | 227,273 | 142,084.0 |
| `ukwa_link_source` | UK Web Archive crawl date | `link_source` | master | 92,646 | 90,825.1 |
| `isc_survey` | survey run date | `artifact_listing` | master | 115,104 | 61,759.1 |
| `rdap_snapshot` | the registry's own `registration` event date | `whois_creation` | master | 88,643 | 54,714.0 |
| `usenet_announce` | post date of the announcement | `dated_directory` | master | 69,949 | 46,402.0 |
| `ia_cdx_bulk` | Wayback capture timestamp | `cdx_timestamp` | master | 44,629 | 38,756.4 |
| `usenet_address` | post date of the message carrying the address | `dated_directory` | master | 15,764 | 9,579.5 |
| `udrp_proceedings` | the commencement date of the dispute | `artifact_listing` | master | 6,934 | 4,203.1 |
| `usenet_bare` | post date of the message carrying the address | `dated_directory` | master | 5,211 | 3,246.7 |
| `attrition_defacement` | the date the defacement was recorded | `artifact_listing` | master | 3,929 | 1,874.9 |
| `enron_email` | the message `Date:` header | `dated_directory` | master | 2,163 | 1,360.2 |
| `maillist_archive` | the message `Date:` header | `dated_directory` | master | 633 | 395.3 |
| `trade_press` | the issue cover date | `dated_directory` | master | 212 | 134.7 |
| `tucows_catalogue` | software release date | `dated_directory` | master | 83 | 53.2 |
| `rtfm_faq` | the FAQ's revision header | `dated_directory` | master | 36 | 25.0 |
| **Total** | | | | **2,838,732** | **1,697,225.2** |

Every row above is master, so eligible for the annual files. Separately, **2,450,244 domains have no
year-specific evidence** and ship as `candidates.txt`, kept out of the annual masters.

---

## 4. CDX execution notes

`ark cdx`, this project's client for the public Wayback CDX API, over two disjoint populations on two
machines: the VPS works bracketed gaps as a completeness baseline, the local engine works the candidate
pool beside the discovery loop feeding it.

| Collector prefix | Journals | Queries | Answered | Success | In-window hit rate | Distinct domains | In-window pairs |
|---|--:|--:|--:|--:|--:|--:|--:|
| `cdx_pool` | 162 | 105,687 | 89,390 | 84.6% | 44.6% | 90,100 | 57,882 |
| `cdx_q1` | 212 | 63,441 | 55,504 | 87.5% | 71.9% | 55,648 | 126,557 |
| `cdx_gap` | 104 | 41,816 | 35,964 | 86.0% | 98.4% | 36,355 | 134,864 |
| `cdx_q0` | 67 | 39,928 | 39,779 | 99.6% | 71.3% | 39,781 | 83,880 |
| `cdx` | 72 | 34,779 | 26,392 | 75.9% | 95.5% | 28,508 | 89,168 |
| `cdx_gap_vps` | 44 | 11,894 | 10,508 | 88.3% | 98.8% | 10,529 | 40,370 |
| `cdx_disc` | 6 | 3,222 | 3,192 | 99.1% | 44.6% | 3,193 | 2,032 |
| `cdx_discovered` | 1 | 298 | 233 | 78.2% | 85.0% | 298 | 278 |
| **All** | **668** | **301,065** | **260,962** | **86.7%** | **69.3%** | **262,525** | **535,031** |

Of 301,065 queries, 260,962 were answered (86.7%). The 40,103 that were not divide into two kinds, and the smaller kind is the one usually discussed. **HTTP-level errors are 2,905 (0.96%)**: 0 rate limits (429), 2,129 server errors (500, 502, 503, 504) and 776 refusals (403). **Transport-level failures are 37,198 (12.36%)**: 27,775 connections refused or reset and 9,423 timed out. So the binding constraint is not a status code we could read and obey, it is the connection being dropped before a status exists. Rate limits and server errors are retried with exponential backoff honouring `Retry-After`; refusals and timeouts are retried with a widening delay and then requeued, so no domain is lost by one failure; a 403 is treated as a permanent answer for that host and is not retried.

An interrupted batch is republished rather than lost, so a stopped run costs only the queries it had not
yet made.

**Still worth expanding, but no longer the binding constraint.** Roughly 2.5 million candidate names sit
unqueried against engines clearing a few hundred requests an hour, so the queue was never the limit this
round. That is what redirected it toward bulk dated corpora.

---

## 5. How this contributes to an autonomous discovery system

**The useful finding this round is a negative one about our own strategy.** Collection had been
optimised against request throughput at a single archive. When `merged260815` arrived carrying another
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

**Negative results are first-class.** **118 source families have been searched and recorded**, and `sources.md` ships beside this report naming every one. 27 were developed far enough to earn their own section (`prior_task`, `isc_survey`, `afnic_fr`, `ukwa_link_source` and `ukwa_link_target`, `arquivo_ia` and `arquivo_roteiro`, `odp`, `early_web_cdx`, `ia_cdx_bulk`, `dartmouth_nber_captures`, `domain_creation_bulk`, `rdap` and `rdap_snapshot`, `page_directory` and `page_expansion`, `internet_scout`, `ncsa_whats_new`, `ia_cdx`, NYPW first-capture index, Australian Web Archive, `trade_press` and `trade_press_mention`, `usenet_address` and `usenet_address_mention`, `usenet_bare` and `usenet_bare_mention`, `uucp_map_registry`, `uucp_map_creation`, `uucp_map_mention`, `rtfm_faq` and `rtfm_faq_mention`, `ukwa_geoindex`, `usenet_announce` and `usenet_mention`, `tucows_catalogue` and `tucows_mention`, `maillist_archive` and `maillist_archive_mention`, `enron_email` and `enron_email_mention`); the other 91 were evaluated and closed, each recorded with the measurement that closed it, so that negative results stay visible and the same ground is not broken twice.

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

A fresh copy of this archive was extracted and put through the route above before sending. Checksums
and all four checks in `verify.sh` pass, `trace.py` resolves, the rebuild from `provenance/` returns
every per-year count exactly with all nine invariants passing, and all fourteen result files come back
byte-identical. Tier 3 was not run: it is a roughly 50 GB download and two of this project's own
collectors were querying the Internet Archive at the time.
