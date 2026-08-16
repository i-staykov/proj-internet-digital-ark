# Internet Digital Ark: round 5

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 15,428,507 |
| 2. Equivalent-English total | 8,346,839.3737 |
| 3. Increment | **2,835,893** records |
| 4. Equivalent-English increment | **1,694,957.8712** |
| 5. Equivalent-English growth rate | **20.3066%** |

Lines 1 and 2 are the `merged260815` totals, unchanged, since this increment is not yet merged. The
threshold for submission is 5% of the current baseline, which is 417,341.97 equivalent-English.

Of the 2,835,893 net-new records, 2,664,363 are distinct domains and **1,788,557 appear in none of the
six baseline annual files in any year**, so the majority of the increment is genuinely new names rather
than new years on names already held. Mean equivalent-English weight per record is 0.5977.

| Year | merged260815, this counting unit | Additions | Capture-backed |
|---|--:|--:|--:|
| 1996 | 649,765 | 63,162 | 39 (0.1%) |
| 1997 | 1,358,646 | 230,156 | 289 (0.1%) |
| 1998 | 1,363,435 | 283,031 | 4,824 (1.7%) |
| 1999 | 2,745,535 | 513,452 | 16,547 (3.2%) |
| 2000 | 4,675,256 | 764,865 | 26,867 (3.5%) |
| 2001 | 2,991,302 | 981,227 | 224,018 (22.8%) |
| **Total** | **13,783,939** | **2,835,893** | **272,584 (9.6%)** |

The baseline column above counts registered domains, which is the output unit section X asks for, so
it reads lower than the 15,428,507 raw lines of line 1. Both describe the same six files. Growth
is quoted against line 2, the reviewer's own equivalent-English total for those files.

**Cumulative across every round.** Growth rates from different rounds are not additive, because the baseline was reissued five times and each rate has its own denominator. So every figure below is restated against one fixed denominator: the 4,553,314.7637 equivalent-English of `merged260715-2`, the corpus as it stood before this project's first submission. Two rounds are listed without a figure because they are interim reports contained in the round that follows, and adding them would double-count. Round 1 predates the equivalent-English metric, so its records are the reviewer's own confirmed count and the weight beside it is measured now, over the same two releases, with the unchanged model. The last column is therefore comparable down the table, and is not the rate each round was accepted against at the time; this round's accepted rate is the 20.3066% in section 1.

| Round | Date | Records | Equivalent-English | Against `merged260715-2` |
|---|---|--:|--:|--:|
| 1 | 2026-07-26 | 1,429,524 | 756,559.2864 | 16.6156% |
| 2 | 2026-08-03 | 151,949 | 91,814.6880 | 2.0164% |
| 3 | 2026-08-06 | 152,773 | 105,676.0387 | _counted within round 4_ |
| 4 | 2026-08-09 | 946,266 | 603,401.7811 | 13.2519% |
| 5 | 2026-08-12 | 159,787 | 91,908.4230 | _counted within round 6_ |
| **6 (this one)** | 2026-08-17 | **2,835,893** | **1,694,957.8712** | **37.2247%** |
| **Cumulative** | | **5,363,632** | **3,146,733.6267** | **69.1086%** |

---

## 2. What was added, and the year evidence behind each addition

Four routes account for nearly all of this round. Each is described with the field that dates a year,
because under section IV of the brief a record may enter an annual file only on evidence for that year.

**1. The Internet Archive's own capture census (`dartmouth_nber_captures`).** A 2017 research release
deposited at archive.org under the Dartmouth/NBER web-history collection publishes, for every host the
Wayback Machine held at that time, a count of captures per calendar year. One row is `host`, `year`,
`count`. A row is therefore a statement by the archive that it holds N captures of that host inside that
calendar year, which is the same fact a CDX query returns, published in bulk instead of retrieved one
host at a time. It is filed as `cdx_timestamp` for that reason. **Independent check:** for domains where
our own CDX engine had separately queried the live archive, the two agree on 138,979 (domain, year) pairs,
including exact same-day agreement on single-capture years such as `milwhite.com` 1996 (our engine
recorded `19961231231928` against the census row `ia_captures:1996:1`). The census evidences only the
years it names; no year is inferred from any other.

**2. Registry creation dates in bulk (`domain_creation_bulk`).** A published WHOIS/DNS compilation of
171 million domains carries the registry's own creation date per domain, parsed from port-43 answers.
Section IV states that a WHOIS Creation Date is valid evidence that a domain existed no later than that
date and may support inclusion in the annual file for the year the creation date falls in. That is
exactly and only how it is used here: **a creation date in 1998 writes 1998 and no other year.** The
brief's warning about later years is enforced structurally rather than by care, because the parser emits
one evidence row for one year and `assign_year` cannot write a second.

*Falsification run before admitting it.* A TLD cannot predate its own delegation. Across the six TLDs
delegated in 2001, the file contains 21,698 in-window rows and **zero** dated before 2001: `.info` 20,731
rows, `.biz` 635, `.coop` 315, `.museum` 17. Had the dates been synthesised or shifted, this is where it
would show.

**3. A file we already held, read completely (`ukwa_link_source`).** The UK Web Archive host link graph
had been parsed since July. The parser stopped at the first record whose year exceeded the window, on the
assumption the file was sorted by year. It is not: it is fifteen concatenated shards, and the check that
had verified the assumption stopped 2.4 times short of the first shard boundary at line 11,908,464. The
parser had been reading **6.76%** of the file. Removing four lines recovered 92,646 net-new pairs from
material already on disk.

**4. The January 1997 Internet Domain Survey (`isc_survey`).** The survey's own host is long dead and the
file had been recorded as unrecoverable. A sweep of every dead host in the register asked a different
question, not "does this host answer" but "did the archive keep its files", and found `zone/9701.domains.gz`
intact in the Wayback Machine under a successor hostname. A documented presence in a dated DNS survey is
direct annual evidence under section V.

Alongside these, mentions already held were re-admitted by the corroboration rule described in section 5,
and the CDX engines continued to date candidates from the archive itself.

---

## 3. Source contribution statistics

Every net-new record, by the source that dated it. Raw record increase and equivalent-English increase
are given for each, as required.

| Source | What carries the date | Evidence type | Admissible | Net-new pairs | Equivalent-English |
|---|---|---|---|--:|--:|
| `domain_creation_bulk` | see `sources.md` | `whois_creation` | master | 2,165,523 | 1,241,812.0 |
| `dartmouth_nber_captures` | see `sources.md` | `cdx_timestamp` | master | 227,273 | 142,084.0 |
| `ukwa_link_source` | UK Web Archive crawl date | `link_source` | master | 92,646 | 90,825.1 |
| `isc_survey` | survey run date | `artifact_listing` | master | 115,104 | 61,759.1 |
| `rdap_snapshot` | the registry's own `registration` event date | `whois_creation` | master | 87,657 | 54,209.7 |
| `usenet_announce` | post date of the announcement | `dated_directory` | master | 69,949 | 46,402.0 |
| `ia_cdx_bulk` | Wayback capture timestamp | `cdx_timestamp` | master | 42,776 | 36,993.4 |
| `usenet_address` | post date of the message carrying the address | `dated_directory` | master | 15,764 | 9,579.5 |
| `udrp_proceedings` | see `sources.md` | `artifact_listing` | master | 6,934 | 4,203.1 |
| `usenet_bare` | post date of the message carrying the address | `dated_directory` | master | 5,211 | 3,246.7 |
| `attrition_defacement` | see `sources.md` | `artifact_listing` | master | 3,929 | 1,874.9 |
| `enron_email` | the message `Date:` header | `dated_directory` | master | 2,163 | 1,360.2 |
| `maillist_archive` | the message `Date:` header | `dated_directory` | master | 633 | 395.3 |
| `trade_press` | the issue cover date | `dated_directory` | master | 212 | 134.7 |
| `tucows_catalogue` | software release date | `dated_directory` | master | 83 | 53.2 |
| `rtfm_faq` | the FAQ's revision header | `dated_directory` | master | 36 | 25.0 |
| **Total** | | | | **2,835,893** | **1,694,957.9** |

**Candidate pool, kept strictly separate from the annual masters:** 2,452,596 domains carry no
year-specific evidence and are shipped as `candidates.txt`, never mixed into `1996.txt` through
`2001.txt`. They are hostnames extracted from archived pages (`link_target`), which the taxonomy makes
structurally incapable of dating a year.

---

## 4. CDX execution notes

Tooling: `ark cdx`, this project's own client for the public Wayback CDX API, driven by
`scripts/supervise_cdx_pool.sh`. It runs two disjoint populations on two machines. The **VPS** works pure
bracketed gaps, a missing year Y where Y-1 and Y+1 are already held, as a completeness baseline. The
**local** engine works the candidate pool beside the discovery loop that feeds it.

| Collector prefix | Journals | Queries | Answered | Success | In-window hit rate | Distinct domains | In-window pairs |
|---|--:|--:|--:|--:|--:|--:|--:|
| `cdx_pool` | 158 | 103,467 | 87,545 | 84.6% | 44.0% | 88,153 | 56,233 |
| `cdx_q1` | 206 | 61,641 | 54,233 | 88.0% | 71.6% | 54,369 | 122,840 |
| `cdx_gap` | 104 | 41,816 | 35,964 | 86.0% | 98.4% | 36,355 | 134,864 |
| `cdx_q0` | 67 | 39,928 | 39,779 | 99.6% | 71.3% | 39,781 | 83,880 |
| `cdx` | 72 | 34,779 | 26,392 | 75.9% | 95.5% | 28,508 | 89,168 |
| `cdx_gap_vps` | 44 | 11,894 | 10,508 | 88.3% | 98.8% | 10,529 | 40,370 |
| `cdx_disc` | 6 | 3,222 | 3,192 | 99.1% | 44.6% | 3,193 | 2,032 |
| **All** | **657** | **296,747** | **257,613** | **86.8%** | **69.1%** | **259,055** | **529,387** |

Of 296,747 queries, 257,613 were answered (86.8%). The 39,134 that were not divide into two kinds, and the smaller kind is the one usually discussed. **HTTP-level errors are 2,783 (0.94%)**: 0 rate limits (429), 2,007 server errors (500, 502, 503, 504) and 776 refusals (403). **Transport-level failures are 36,351 (12.25%)**: 27,698 connections refused or reset and 8,653 timed out. So the binding constraint is not a status code we could read and obey, it is the connection being dropped before a status exists. Rate limits and server errors are retried with exponential backoff honouring `Retry-After`; refusals and timeouts are retried with a widening delay and then requeued, so no domain is lost by one failure; a 403 is treated as a permanent answer for that host and is not retried.

Failures are handled by adjusting the request rate rather than by stopping, as section VII requires.
The client sends an honest User-Agent naming the project and a contact address, runs modest concurrency,
honours `Retry-After`, and backs off on 429, 503 and 504 with a delay that adapts between a floor and a
ceiling. A batch that ends is republished rather than lost, so an interrupted run costs nothing a repeat
does not recover.

**On whether the CDX route is worth further expansion: yes, but it is no longer the binding constraint.**
Roughly 2.5 million candidate names sit unqueried against engines clearing a few hundred requests an hour.
The queue has not been the constraint at any point this round. That observation is what redirected the
round toward bulk dated corpora, and section 2 is the result.

---

## 5. How this contributes to an autonomous discovery system

The brief asks for a system that discovers, validates and preserves rather than a set of downloads. What
follows is the machinery, all of which ships in the archive.

**The evidence wall is structural, not procedural.** `domain_year.evidence_id` is `NOT NULL` and
foreign-keys a row in `evidence`. There is no code path that can write a year assignment without naming
the observation supporting it. An agent is therefore given wide latitude about what to try and none at
all about what counts as proof.

**A taxonomy decides which evidence may date a year.** Master-eligible types are `artifact_listing`, `cdx_timestamp`, `dated_directory`, `link_source`, `whois_creation`.
`link_target`, a hostname seen in an archived page, never can, and `assign_year` refuses it. That single
rule is why the discovery loop below can run unattended without risking the annual files.

**The corroboration split.** Beyond that, 16,687 of this round's pairs are confirmed by two or more independent collection lineages rather than one, and every asserted pair in the collection carries 1.5901 distinct sources on average. **All 16 are master sources, so all 2,835,893 pairs are admitted to the annual files.** None of them is candidate-only. Names may pass through the candidate pool on the way in, and this round many did, but a pair is only counted once a master source dates it.

**A human gate that an agent cannot argue past.** `docs/approved-sources-list.md` carries one decision
line per (source, evidence type), and `ark ingest` refuses any master-eligible class that is pending,
rejected or absent. Requests are machine-generated by `scripts/request_approval.py` out of a
seeded-random sample with live links, the measured counterfactual and the reasons a reviewer should
refuse, so the human checks external evidence instead of reading the agent's argument. Both sources in
section 2 passed through this gate before a single row of theirs could date a year.

**Nine invariants, run before anything ships.** `ark check` asserts, among others, that no exported
addition carries baseline evidence for that year (so the net-new figure cannot be inflated), that the
year named inside an evidence value equals the year it is filed under, and that no master-eligible
evidence sits unassigned. The gate is enforced by a pre-commit hook rather than remembered.

**A discovery loop that does not run out.** A candidate the CDX engine dates is by construction a site
that was live in the window; its archived page names other sites of the same period; those names return
to the pool, and because extracted hostnames are `link_target` and can never date a year, the loop needs
no approval and is safe to leave running unattended. It was measured this round: seeding link-looking
pages rather than home pages harvested 391 domains against 53, a 7.4x improvement, but yielded only 5
net-new, because 386 of the 391 were already held and already dated. That negative result is why bulk
link graphs are now preferred over page-by-page expansion.

**The agent harness itself.** A standing brief, `CLAUDE.md`, is loaded into every agent session and holds
only what does not change: the evidence rule, the metric, which document is authoritative for what, the
operational rules, and a section of traps that have each produced a confident wrong answer. Collectors
hold their own absolute deadlines and keep running with no agent present; the agent re-invokes itself on
a heartbeat, and a wake that finds everything healthy is required to spend itself hunting a new source,
because an idle wake beside healthy engines is a wasted one. Decisions land in an append-only dated log,
the few with structural impact become ADRs, and anything genuinely needing a human appears on exactly one
surface so it cannot be buried.

**Negative results are first-class.** **115 source families have been searched and recorded**, and `sources.md` ships beside this report naming every one. 24 were developed far enough to earn their own section (`prior_task`, `isc_survey`, `afnic_fr`, `ukwa_link_source` and `ukwa_link_target`, `arquivo_ia` and `arquivo_roteiro`, `odp`, `early_web_cdx`, `ia_cdx_bulk`, `rdap` and `rdap_snapshot`, `page_directory` and `page_expansion`, `internet_scout`, `ncsa_whats_new`, `ia_cdx`, NYPW first-capture index, Australian Web Archive, `trade_press` and `trade_press_mention`, `usenet_address` and `usenet_address_mention`, `usenet_bare` and `usenet_bare_mention`, `uucp_map_registry`, `uucp_map_creation`, `uucp_map_mention`, `rtfm_faq` and `rtfm_faq_mention`, `usenet_announce` and `usenet_mention`, `tucows_catalogue` and `tucows_mention`, `maillist_archive` and `maillist_archive_mention`, `enron_email` and `enron_email_mention`); the other 91 were evaluated and closed, each recorded with the measurement that closed it, so that negative results stay visible and the same ground is not broken twice.

---

## 6. Limitations, and what is worth expanding

**The registry creation dates are the largest single contribution and also the narrowest evidence.** A
creation date attests registration, not activity, and it attests one year only. Where a domain was
registered in 1997 and remained live through 2001, this source supplies 1997 alone; the other four years
must still be earned from a capture, a survey or a continued-registration record. This is a deliberate
under-claim and it is enforced by the parser.

**The capture census is a 2017 snapshot.** The archive has grown since, so its per-year counts are a
floor on what the Wayback Machine holds today, never a ceiling.

**Worth expanding, in order.** Bulk dated corpora first, since one such file outweighed an entire round
of per-domain querying and this round found two more. National web archive link graphs second, where the
year association is explicit: `ukwa_link_source` returned a mean equivalent-English weight of 0.9803,
the highest of any source here, because a national link graph is almost entirely `.uk`. Per-domain CDX
querying third, which still pays but is bounded by request rate rather than by candidates.

**Not worth expanding:** the closed families named above, each recorded with the measurement that closed
it so the same ground is not broken twice.

---

## 7. Reproduction

`README.md` inside the archive gives the full order. In short: `masters/` holds the merged annual lists
and `additions/` this round's net-new records only, both one registered domain per line and deduplicated
within each year; `candidates.txt` holds the names with no year evidence, separate as section X requires;
`provenance/*.parquet` joins every (domain, year) to the evidence row that justifies it, so any single
line of any annual file traces to the observation behind it; `journals/` holds the raw per-source records
before interpretation; `source/source.tar.gz` is the repository at the commit that produced the delivery;
and `verify.sh` re-checks the shipped files against each other.

`uv run ark export` regenerates every text file from the store, `uv run ark check` re-runs the nine
invariants, and `uv run python scripts/round_figures.py --verify` re-scores the round with the reviewer's
own `equivalent_english_domains.py` and its unchanged weight model.
