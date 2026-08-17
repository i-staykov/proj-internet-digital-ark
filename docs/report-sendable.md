# Internet Digital Ark: round 5

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 15,428,507 |
| 2. Equivalent-English total | 8,346,839.3737 |
| 3. Increment | **2,836,693** records |
| 4. Equivalent-English increment | **1,695,551.8368** |
| 5. Equivalent-English growth rate | **20.3137%** |

Lines 1 and 2 are the `merged260815` totals, unchanged, since this increment is not yet merged. The 5%
threshold is 417,341.97 equivalent-English. The increment covers 2,665,102 distinct domains, of which
**1,789,260 appear in none of the six baseline files in any year**; mean weight per record is 0.5977.

| Year | merged260815, this counting unit | Additions | Capture-backed |
|---|--:|--:|--:|
| 1996 | 649,765 | 63,162 | 39 (0.1%) |
| 1997 | 1,358,646 | 230,171 | 289 (0.1%) |
| 1998 | 1,363,435 | 283,076 | 4,825 (1.7%) |
| 1999 | 2,745,535 | 513,580 | 16,554 (3.2%) |
| 2000 | 4,675,256 | 765,126 | 26,914 (3.5%) |
| 2001 | 2,991,302 | 981,578 | 224,292 (22.9%) |
| **Total** | **13,783,939** | **2,836,693** | **272,913 (9.6%)** |

The baseline column counts registered domains, the output unit section X asks for, so it reads lower
than the 15,428,507 raw lines of line 1. Both describe the same six files.

**Cumulative.** Across the four rounds shipped so far this project has added 5,364,432 domain-year records worth 3,147,327.5923 equivalent-English, which is **37.7068%** of the 8,346,839.3737 the corpus holds today. Round 1 predates the equivalent-English metric, so its records are the reviewer's own confirmed count and the weight beside it is measured over the two releases either side under the unchanged model.

| Round | Records | Equivalent-English |
|---|--:|--:|
| 1 | 1,429,524 | 756,559.2864 |
| 3 | 151,949 | 91,814.6880 |
| 4 | 946,266 | 603,401.7811 |
| **5, this one** | **2,836,693** | **1,695,551.8368** |
| **Total** | **5,364,432** | **3,147,327.5923** |

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
CDX querying of the live archive on **138,760 (domain, year) pairs**, including exact
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

| Source | What carries the date | Evidence type | Admissible | Net-new pairs | Equivalent-English |
|---|---|---|---|--:|--:|
| `domain_creation_bulk` | the registry's own creation date for that domain | `whois_creation` | master | 2,165,523 | 1,241,812.0 |
| `dartmouth_nber_captures` | the archive's own count of captures it holds in that year | `cdx_timestamp` | master | 227,273 | 142,084.0 |
| `ukwa_link_source` | UK Web Archive crawl date | `link_source` | master | 92,646 | 90,825.1 |
| `isc_survey` | survey run date | `artifact_listing` | master | 115,104 | 61,759.1 |
| `rdap_snapshot` | the registry's own `registration` event date | `whois_creation` | master | 88,129 | 54,491.8 |
| `usenet_announce` | post date of the announcement | `dated_directory` | master | 69,949 | 46,402.0 |
| `ia_cdx_bulk` | Wayback capture timestamp | `cdx_timestamp` | master | 43,104 | 37,305.2 |
| `usenet_address` | post date of the message carrying the address | `dated_directory` | master | 15,764 | 9,579.5 |
| `udrp_proceedings` | the commencement date of the dispute | `artifact_listing` | master | 6,934 | 4,203.1 |
| `usenet_bare` | post date of the message carrying the address | `dated_directory` | master | 5,211 | 3,246.7 |
| `attrition_defacement` | the date the defacement was recorded | `artifact_listing` | master | 3,929 | 1,874.9 |
| `enron_email` | the message `Date:` header | `dated_directory` | master | 2,163 | 1,360.2 |
| `maillist_archive` | the message `Date:` header | `dated_directory` | master | 633 | 395.3 |
| `trade_press` | the issue cover date | `dated_directory` | master | 212 | 134.7 |
| `tucows_catalogue` | software release date | `dated_directory` | master | 83 | 53.2 |
| `rtfm_faq` | the FAQ's revision header | `dated_directory` | master | 36 | 25.0 |
| **Total** | | | | **2,836,693** | **1,695,551.8** |

All are master, meaning eligible for the annual files. Separately, **2,451,893 domains carry no
year-specific evidence** and ship as `candidates.txt`, never mixed into the annual masters. They are
hostnames extracted from archived pages, typed `link_target`, which the taxonomy makes structurally
incapable of dating a year.

---

## 4. CDX execution notes

`ark cdx`, this project's client for the public Wayback CDX API, driven by `supervise_cdx_pool.sh`
over two disjoint populations on two machines: the VPS works pure bracketed gaps as a completeness
baseline, the local engine works the candidate pool beside the discovery loop that feeds it.

| Collector prefix | Journals | Queries | Answered | Success | In-window hit rate | Distinct domains | In-window pairs |
|---|--:|--:|--:|--:|--:|--:|--:|
| `cdx_pool` | 159 | 103,887 | 87,877 | 84.6% | 44.1% | 88,551 | 56,524 |
| `cdx_q1` | 207 | 61,941 | 54,454 | 87.9% | 71.6% | 54,574 | 123,494 |
| `cdx_gap` | 104 | 41,816 | 35,964 | 86.0% | 98.4% | 36,355 | 134,864 |
| `cdx_q0` | 67 | 39,928 | 39,779 | 99.6% | 71.3% | 39,781 | 83,880 |
| `cdx` | 72 | 34,779 | 26,392 | 75.9% | 95.5% | 28,508 | 89,168 |
| `cdx_gap_vps` | 44 | 11,894 | 10,508 | 88.3% | 98.8% | 10,529 | 40,370 |
| `cdx_disc` | 6 | 3,222 | 3,192 | 99.1% | 44.6% | 3,193 | 2,032 |
| `cdx_discovered` | 1 | 298 | 233 | 78.2% | 85.0% | 298 | 278 |
| **All** | **660** | **297,765** | **258,399** | **86.8%** | **69.2%** | **259,903** | **530,610** |

Of 297,765 queries, 258,399 were answered (86.8%). The 39,366 that were not divide into two kinds, and the smaller kind is the one usually discussed. **HTTP-level errors are 2,827 (0.95%)**: 0 rate limits (429), 2,051 server errors (500, 502, 503, 504) and 776 refusals (403). **Transport-level failures are 36,539 (12.27%)**: 27,762 connections refused or reset and 8,777 timed out. So the binding constraint is not a status code we could read and obey, it is the connection being dropped before a status exists. Rate limits and server errors are retried with exponential backoff honouring `Retry-After`; refusals and timeouts are retried with a widening delay and then requeued, so no domain is lost by one failure; a 403 is treated as a permanent answer for that host and is not retried.

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
decides which evidence may date a year: master-eligible types are `artifact_listing`, `cdx_timestamp`, `dated_directory`, `link_source`, `whois_creation`, while `link_target`,
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
exactly one surface. ****118 source families have been searched and recorded**, and `sources.md` ships beside this report naming every one. 27 were developed far enough to earn their own section (`prior_task`, `isc_survey`, `afnic_fr`, `ukwa_link_source` and `ukwa_link_target`, `arquivo_ia` and `arquivo_roteiro`, `odp`, `early_web_cdx`, `ia_cdx_bulk`, `dartmouth_nber_captures`, `domain_creation_bulk`, `rdap` and `rdap_snapshot`, `page_directory` and `page_expansion`, `internet_scout`, `ncsa_whats_new`, `ia_cdx`, NYPW first-capture index, Australian Web Archive, `trade_press` and `trade_press_mention`, `usenet_address` and `usenet_address_mention`, `usenet_bare` and `usenet_bare_mention`, `uucp_map_registry`, `uucp_map_creation`, `uucp_map_mention`, `rtfm_faq` and `rtfm_faq_mention`, `ukwa_geoindex`, `usenet_announce` and `usenet_mention`, `tucows_catalogue` and `tucows_mention`, `maillist_archive` and `maillist_archive_mention`, `enron_email` and `enron_email_mention`); the other 91 were evaluated and closed, each recorded with the measurement that closed it, so that negative results stay visible and the same ground is not broken twice.**

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

**This was run, and the first run failed.** A previous build of this archive was extracted fresh and
put through its own documented route. Tier 1 passed: checksums, the six annual files, and every pair
traced to the evidence manifest. **Tier 2 failed.** Rebuilding the result from the shipped provenance
gave 712,927 additions for 1996 against a true 63,162, and `ark check` failed on `evidence_wall_intact`
and `every_pair_has_master_evidence`, because 11,316,960 of 16,619,832 assignments cited an evidence row
that a packaging size-cut had removed from the file beside them.

The cut is reverted, the full evidence table ships, and the rebuild now returns every per-year count
exactly and passes all nine invariants. `verify.sh` has gained a fourth check for the defect that the
first three could not see, since all of them read the additions manifest and none read the provenance.

Tier 3, rebuilding from the original sources, is a roughly 50 GB download and was not run here: two of
this project's own collectors were querying the Internet Archive at the time, and a third heavy client
against it is against the project's own citizenship rule.
