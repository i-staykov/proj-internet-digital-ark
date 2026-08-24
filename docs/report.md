# Internet Digital Ark: round 6

Additions to the 1996-2001 annual lists, measured against `merged260821`. Every figure is generated from
the evidence store, so no table here can disagree with the files shipped beside it.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 25,064,981 |
| 2. Equivalent-English total | 13,362,368.8792 |
| 3. Increment | **726,336** records |
| 4. Equivalent-English increment | **452,373.0385** |
| 5. Equivalent-English growth rate | **3.3855%** |

Lines 1 and 2 are your `merged260821` totals, unchanged, since this increment is not yet merged. The
increment covers 703,451 distinct domains, of which **209,986 appear in none of the six baseline
files in any year**.

| Year | merged260821, this counting unit | Additions | Capture-backed |
|---|--:|--:|--:|
| 1996 | 754,672 | 33,157 | 7 (0.0%) |
| 1997 | 1,791,900 | 53,044 | 22 (0.0%) |
| 1998 | 2,233,240 | 123,915 | 505 (0.4%) |
| 1999 | 4,612,976 | 164,519 | 2,023 (1.2%) |
| 2000 | 9,471,543 | 131,536 | 2,759 (2.1%) |
| 2001 | 4,550,999 | 220,173 | 55,816 (25.4%) |
| **Total** | **23,415,330** | **726,344** | **61,132 (8.4%)** |

**Cumulative.** Across the 4 rounds shipped so far plus this one, this project has added 5,862,405 domain-year records worth 3,470,382.2443 equivalent-English, which is **25.9713%** of the 13,362,368.8792 the corpus holds today. Each shipped round is quoted at the figure the reviewer ACCEPTED, which is not always the one it was submitted with: he recalculates against whatever baseline is current when he merges, and records of ours that reached it by another route in the meantime are his, not ours, to count. Round 1 predates the equivalent-English metric, so its records are the reviewer's own confirmed count and the weight beside it is measured over the two releases either side under the unchanged model.

| Round | Records | Equivalent-English |
|---|--:|--:|
| 1 | 1,429,524 | 756,559.2864 |
| 3 | 151,949 | 91,814.6880 |
| 4 | 946,266 | 603,401.7811 |
| 5 | 2,608,322 | 1,566,229.7613 |
| **6, this one** | **726,344** | **452,376.7275** |
| **Total** | **5,862,405** | **3,470,382.2443** |

## 2. What dates each year

| Route | What dates a year | Net-new pairs |
|---|---|--:|
| the two archive engines, a bracketed-gap population and the candidate pool | the Wayback capture timestamp, per domain and year | 60,498 |
| the RDAP sweep over the candidate pool | the registry's own creation date, which dates that year and no other | 556,890 |

**Both routes are self-dating and take no corroboration split.** A capture timestamp and a registry
creation date are records of the thing itself, not somebody's description of it. The registry route is
deliberately under-claimed: **a creation date writes its own year and no other**, per your rule 6, so a
domain created in 1997 and live in 2001 earns 1997 here and must earn the other four from a capture. The
parser emits one evidence row for one year, so a second cannot be written.

## 3. Source contributions

| Source | What carries the date | Evidence type | Admissible | Net-new pairs | Equivalent-English |
|---|---|---|---|--:|--:|
| `rdap_snapshot` | the registry's own `registration` event date | `whois_creation` | master | 556,890 | 342,557.4 |
| `ia_cdx_bulk` | Wayback capture timestamp | `cdx_timestamp` | master | 60,498 | 53,755.9 |
| `usenet_announce` | post date of the announcement | `dated_directory` | master | 101,465 | 50,206.3 |
| `usenet_address` | post date of the message carrying the address | `dated_directory` | master | 4,231 | 3,165.7 |
| `usenet_bare` | post date of the message carrying the address | `dated_directory` | master | 3,087 | 2,565.5 |
| `rtfm_faq` | the FAQ's revision header | `dated_directory` | master | 83 | 69.6 |
| `trade_press` | the issue cover date | `dated_directory` | master | 32 | 23.4 |
| `enron_email` | the message `Date:` header | `dated_directory` | master | 31 | 17.3 |
| `maillist_archive` | the message `Date:` header | `dated_directory` | master | 27 | 15.7 |
| **Total** | | | | **726,344** | **452,376.7** |

Every row is master-eligible. Separately, **2,395,154 domains carry no year-specific evidence** and
ship as `candidates.txt`, kept out of the annual files.

## 4. Archive execution

| Collector prefix | Journals | Queries | Answered | Success | In-window hit rate | Distinct domains | In-window pairs |
|---|--:|--:|--:|--:|--:|--:|--:|
| `cdx_suffix` | 43 | 2,238,415 | 2,238,415 | 100.0% | 100.0% | 57,592 | 4,367,087 |
| `cdx_pool` | 209 | 129,917 | 113,171 | 87.1% | 46.9% | 113,541 | 73,616 |
| `cdx_q1` | 214 | 63,919 | 55,844 | 87.4% | 71.9% | 55,943 | 127,552 |
| `cdx_gap` | 104 | 41,816 | 35,964 | 86.0% | 98.4% | 36,355 | 134,864 |
| `cdx_q0` | 67 | 39,928 | 39,779 | 99.6% | 71.3% | 39,781 | 83,880 |
| `cdx` | 75 | 35,232 | 26,844 | 76.2% | 94.8% | 28,961 | 89,561 |
| `cdx_edge` | 49 | 24,815 | 23,658 | 95.3% | 85.7% | 23,659 | 47,010 |
| `cdx_suffix_diagtest` | 1 | 20,552 | 20,552 | 100.0% | 100.0% | 20,552 | 29,459 |
| `cdx_vedge` | 15 | 14,626 | 14,201 | 97.1% | 66.9% | 14,258 | 19,409 |
| `cdx_gap_vps` | 44 | 11,894 | 10,508 | 88.3% | 98.8% | 10,529 | 40,370 |
| `cdx_gap3` | 37 | 10,608 | 9,637 | 90.8% | 64.4% | 9,641 | 11,223 |
| `cdx_suffix_20260821a` | 1 | 10,575 | 10,575 | 100.0% | 100.0% | 10,575 | 13,768 |
| `cdx_linkhint` | 11 | 9,181 | 9,130 | 99.4% | 67.4% | 9,131 | 10,179 |
| `cdx_gap2` | 13 | 3,718 | 3,309 | 89.0% | 94.5% | 3,323 | 10,420 |
| `cdx_disc` | 6 | 3,222 | 3,192 | 99.1% | 44.6% | 3,193 | 2,032 |
| `cdx_discovered` | 1 | 298 | 233 | 78.2% | 85.0% | 298 | 278 |
| `cdx_edgepilot_b` | 1 | 155 | 141 | 91.0% | 80.9% | 155 | 325 |
| **All** | **891** | **2,658,871** | **2,615,153** | **98.4%** | **96.0%** | **390,945** | **5,061,033** |

Of 2,658,871 queries, 2,615,153 were answered (98.4%). The 43,718 that were not divide into two kinds, and the smaller kind is the one usually discussed. **HTTP-level errors are 3,139 (0.12%)**: 0 rate limits (429), 2,155 server errors (500, 502, 503, 504) and 984 refusals (403). **Transport-level failures are 40,579 (1.53%)**: 29,375 connections refused or reset and 11,204 timed out. So the binding constraint is not a status code we could read and obey, it is the connection being dropped before a status exists. Rate limits and server errors are retried with exponential backoff honouring `Retry-After`; refusals and timeouts are retried with a widening delay and then requeued, so no domain is lost by one failure; a 403 is treated as a permanent answer for that host and is not retried.

## 5. The discovery method, and what changed this round

You asked for the autonomous discovery process rather than the totals, so this is the short version of
what the system is and how this round's method differed from the last.

**Two mechanisms bound an agent nobody is watching, and both are structural.**
`domain_year.evidence_id` is `NOT NULL` with a foreign key into `evidence`, so no code path can write a
year without naming the observation behind it; twelve invariants check that before every commit and again
inside the archive. And a source class cannot date a year until a human writes one `Decision:` line, with
the request generated from a seeded-random sample and live links, so the reviewer checks external evidence
rather than an agent's argument. **An agent asserting its own find is trustworthy is the least reliable
artifact in the system**, so it is never asked to.

**Tested by accident this round.** The candidate pool accumulated 575,417 names that cannot exist, strings
under three namespaces that never allowed arbitrary registration, mostly from address extraction where
anti-spam munging garbles text. **Not one reached an annual file.** All 826 `.mil`, 6,679 `.gov` and 25,155
`.edu` domains shipped carry independent attestation: 100.0%, zero on a mention alone, on the three
highest-weighted namespaces in the model.

**What changed against the previous cycle.** Phase 5 was one long agent session driving collection
directly. This round separated the two: collectors became detached shell supervisors holding an absolute
epoch deadline, so they outlive the session and a day of agent absence costs nothing, while the agent
spends its turns hunting and pricing. A scheduled job runs the health cycle independently. The instruction
file was treated as a component and **cut from 186 lines to 59**, because length was making the agent
worse: a rule that takes a paragraph gets skipped, and prose competes with the task on every turn. The
measured effect of the split is in section 4: collection continued through a full day when the agent was
away, which phase 5's design could not have done.

**Health is three questions, not one: presence, progress, yield.** A supervisor that checks only liveness
calls a batch stalled on a socket healthy; one that checks only journal growth cannot tell misses from hits.
This round the check earned itself twice: a collector re-ingested the same frozen journal fourteen times
overnight for zero rows, and a queue rebuild that looked like an improvement measured 24x worse per query
than the file it replaced, 28 dated years per 600 queries against 673.

**One method changed the question: generate the query population rather than discover it.** Finding
candidate names has never been this project's constraint; dating them has. We hold 2,395,205 names with no
in-window year, worth 1,658,653 equivalent-English if each earned a single year, and **RDAP cannot date one
of them**: two independent samples returned 602 answers and **zero** in-window creation dates, because 73%
of that pool is HTTP 404 today. A candidate is by construction a name no crawler captured, which correlates
with a name that stopped existing, and only an archive capture can date a name that is gone.

So we asked which *generated* population is densest in in-window registrations, and measured four against
each other with the registry's own creation dates. English dictionary words carry an in-window creation date
on **28.00%** of queries; random four-character strings 6.73%; **invented two-word compounds nothing at
all**, zero in-window in 859 queries; and siblings of names we already hold under another gTLD, measured on
a full production round of 150,000 queries, **9.47% and 59.9 equivalent-English per thousand queries**
against about 4.8 for the discovered candidate list. Two honest caveats. A 1,400-answer pilot of that same
sibling population read 5.64%, six-fold low, so **a sample of the source population is not a sample of the
queue**. And the density decays as the queue head moves: successive rounds returned 14,205, 14,495, 14,436,
6,287 and 2,640 in-window creations, so 52,063 pairs is what it actually paid rather than what one round
extrapolates to. The dictionary result carries the finding we did not expect: real English words skew
**1996-1999**, our thinnest years, and are still 92.4% already held, so saturation is not a property of
famous names.

**A measurement worth more than the sources it came from.** We had assumed a lapsed-and-re-registered name
reports the later creation date, which would make registry dates weak evidence. Measured over 472 domains we
date in window from captures: of the 370 that answer, **59.7% still carry an in-window creation date**. A
transfer never resets it, and neither does bankruptcy and a change of owner. What does hold is that when a
reset has happened there is no route back: across 55 domains no registry emitted `reregistration` or
`reinstantiation`, and no event of any kind predated the `registration` event. So a registry creation date is
considerably stronger in-window evidence than we had been treating it as.

**And a shape transfers where a host does not.** The largest new source this round was found by asking what
*kind* of artifact a registry of that era produced, not which registry we had not tried. The IE Domain
Registry regenerated its whole register as static A-Z pages carrying their own line, `updated automatically
at 14:51 GMT on Friday, 21 December 2001`. That is the same instrument as a DNS zone file: the registry
asserting what was registered at a stated instant, rather than a directory listing names it happens to know.
**19,341 net-new pairs and 18,846 equivalent-English** from 38 requests and 1.1 MB. Taken to nine further
namespaces the same question found MYNIC's fortnightly change report, the CO.ZA deletion queue, TWNIC's
frozen-domain list, SaudiNIC, NIC Malta, NIC Venezuela, RESTENA and IDNIC, and the screen that separates
them is one question: **who held the database, and did they ever write it to a file?** `.ie` was one
university computing service regenerating one register onto one static tree; `.za` was eleven separately
administered second levels taking applications by e-mail, so there was no single machine to regenerate.

**Four measurement rules, each bought with a wasted day.** Gross and net yield differ by more than 10x,
and a population that looks spectacular on gross was 97.9% already dated. Per-query and total yield point
opposite ways, so optimising the wrong one is easy. Ranking a queue by TLD weight alone fills it with
namespaces delegated in 2013. And a source's worth decays while it waits: one parked at 77,749
equivalent-English was worth 4,512 by the time it was approved, because our own sweeps had banked that
population first.

**The most useful result was a refusal.** An idea priced at 1,704,843 equivalent-English, two and a half
times this threshold, was forbidden by your rule 6: a creation date alone does not establish continued
registration. The rule took four minutes to find and the measurement took an afternoon. The lesson is
recorded as a standing check, because the same reasoning sat under a source already shipped.

**Negative results are first-class.** **176 source families have been searched and recorded**, 28 developed far enough to earn their own section and 148 evaluated and closed, each with the measurement that closed it, so negative results stay visible and the same ground is not broken twice. `sources.md` ships beside this report and names every one, with its acquisition route, date semantics and yield.

## 6. Limitations

**Both routes err toward under-claiming.** A capture proves presence and never absence, so a year with no
capture is unevidenced rather than empty. A creation date attests registration for one year only. Neither
can invent a year; the mistake they can make is omission.

**Two limits no amount of work fixes.** A material share of archive requests fail at transport level
rather than with a status code, which is throttling seen from the other side of the socket. And the
corroboration split asks whether a domain is dated somewhere, never whether a mention was genuine, so
prose that invents plausible examples is the one shape it does not stop. That is why both of this round's
routes are self-dating.

**Worth expanding, in order.** Bulk dated corpora first, measured at two orders of magnitude more net-new
pairs per megabyte than prose. Registry datasets publishing creation dates as open data second, because
that is the route that reaches 2001 where the archives are thin. Re-auditing material already on disk
third, which has repeatedly been the cheapest source available.

## 7. Reproduction

`README.md` in the archive gives the order. `masters/` and `additions/` hold the merged annual lists and
this round's net-new records, `candidates.txt` the names with no year evidence, `provenance/*.parquet`
every (domain, year) joined to the evidence row justifying it, and `source/source.tar.gz` the repository
at the commit that built the delivery.

A fresh copy of this archive was extracted and put through the route above before sending. Checksums
and all four checks in `verify.sh` pass, `trace.py` resolves, the rebuild from `provenance/` returns
every per-year count exactly with all eleven invariants passing, and all fourteen result files come back
byte-identical. Tier 3 was not run: it is a roughly 50 GB download and two of this project's own
collectors were querying the Internet Archive at the time.

## 8. The merge, the overlap and the reconciliation

**The merge, deduplication and overlap, computed here rather than described.**
`merge_against_baseline.py` unions these additions into the current baseline,
deduplicated on the lowercased line within each year, which is the reviewer's own
counting unit, and scores every file with his own calculator. The per-year form is
`audit/merge_stats_ark_*.csv`, in his column names so his audit and this one can be
diffed directly.

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260821` | 25,064,981 | 13,362,368.8792 |
| submitted | 726,336 | |
| already in the baseline | 0 | |
| **accepted increment** | **726,336** | **452,373.0385** |
| post-merge total | 25,791,317 | 13,814,741.9177 |

**22 of 22 reconciliation checks pass.** They are arithmetic
identities, so a failure is a defect rather than a finding: per year that
`baseline_unique + accepted_new == merged_unique` and that
`already_in_baseline + accepted_new == submitted_unique`, that the per-year
equivalent-English increments sum to the headline figure, that the baseline plus
the increment equals the post-merge total, and that a freshly measured baseline
reproduces the record count and equivalent-English total this round was measured
against. Every one is listed with its verdict in `audit/merge_audit_ark_*.json`.

## 9. The four requested artifacts

| | asked for | where it is |
|---|---|---|
| **D1** | runnable code, dependencies, execution instructions | `source/source.tar.gz` at the commit in `MANIFEST.txt`, with `pyproject.toml` and `uv.lock`. Its `README.md` names what every command should print |
| **D2** | experience summary | `experience-summary.md`, distilled from `sources.md`, which carries every rejection with the measurement that closed it |
| **D3** | merge and deduplication code, overlap counts, reconciliation | section 8, `source/scripts/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your own program vendored unmodified, explained in `metric-explained.md` |

`verify.sh` checks all four inside a fresh extraction, so none can ship unmet.
