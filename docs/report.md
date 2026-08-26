# Internet Digital Ark: round 6

Additions to the 1996-2001 annual lists, measured against `merged260821`. Every figure is generated from
the evidence store, so no table here can disagree with the files shipped beside it.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 25,064,981 |
| 2. Equivalent-English total | 13,362,368.8792 |
| 3. Increment | **769,438** records |
| 4. Equivalent-English increment | **488,722.0745** |
| 5. Equivalent-English growth rate | **3.9348%** |

Lines 1 and 2 are your `merged260821` totals, unchanged, since this increment is not yet merged. The
increment covers 780,850 distinct domains, of which **244,786 appear in none of the six baseline
files in any year**.

| Year | merged260821, this counting unit | Additions | Capture-backed |
|---|--:|--:|--:|
| 1996 | 754,672 | 36,469 | 7 (0.0%) |
| 1997 | 1,791,900 | 66,571 | 33 (0.0%) |
| 1998 | 2,233,240 | 127,226 | 627 (0.5%) |
| 1999 | 4,612,976 | 178,372 | 3,296 (1.8%) |
| 2000 | 9,471,543 | 145,002 | 3,251 (2.2%) |
| 2001 | 4,550,999 | 267,695 | 70,095 (26.2%) |
| **Total** | **23,415,330** | **821,335** | **77,309 (9.4%)** |

**Cumulative.** Across the 4 rounds shipped so far plus this one, this project has added 5,957,396 domain-year records worth 3,543,792.1104 equivalent-English, **26.5207%** of the 13,362,368.8792 the corpus holds today. Records / equivalent-English by round, each at the figure you ACCEPTED rather than the one submitted: round 1 1,429,524 / 756,559; round 3 151,949 / 91,815; round 4 946,266 / 603,402; round 5 2,608,322 / 1,566,230; **6, this one 821,335 / 525,787**.

## 2. Counting unit, normalisation and what gets dropped

**The counting unit is the (registrable domain, year) pair**, deduplicated on the lowercased line
within each year, which is your own unit. Every name from every source passes through one function
before reaching the database, so the dedup key is identical across sources.

**Normalisation, in order:** percent-decode, trim, lowercase; strip scheme, `//`, path, query,
fragment, userinfo and port; strip stray leading and trailing `.` and `,` but never a hyphen, which
would alter the name; then reduce to the registrable domain with a **pinned Public Suffix List** plus
historical ccTLDs, so `ci.anchorage.ak.us` becomes `anchorage.ak.us` while `k12.ak.us` is refused as a
public suffix in its own right. **Validity:** a line is dropped if it is empty, an IPv4 literal, a
reverse-DNS zone, syntactically invalid, carries no known public suffix, is a bare public suffix, or
has an invalid character in the registered label. **Salvage** is the same operation applied to a dirty
line, so a URL or mail address is reduced rather than discarded.

| across 131,461 ingest runs | records | | |
|---|--:|---|--:|
| raw lines read | 1,550,495,756 | **salvaged** by normalisation | **129,499,514** |
| staged records | 206,802,958 | **rejected** as invalid | **2,575,246** |
| outside 1996-2001, never eligible | 1,236,201,812 | | |

Reject reasons over the 1,299,177 dropped lines retained in the shipped audit CSVs: **IP address
95.41%**, no known public suffix 2.92%, invalid hostname syntax 0.95%, bare public suffix 0.63%,
invalid character in the registered label 0.09%. The IP share is expected: link graphs and server logs
name hosts by address, and an address is not a domain under your counting unit.

## 3. What dates each year, and the standard applied to each category

| Route | What dates a year | Net-new pairs |
|---|---|--:|
| the two archive engines, a bracketed-gap population and the candidate pool | the Wayback capture timestamp, per domain and year | 71,641 |
| the RDAP sweep over the candidate pool | the registry's own creation date, which dates that year and no other | 581,235 |

**Both routes are self-dating and take no corroboration split**, being records of the thing itself
rather than a description of it. The registry route is deliberately under-claimed: **a creation date
writes its own year and no other**, per your rule 6, so a domain created in 1997 and live in 2001 earns
1997 here and must earn the other four from a capture.

**The standard, by category.** Master-eligible classes are ``artifact_listing`, `cdx_timestamp`, `dated_directory`, `link_source`, `whois_creation``, each a machine-written
record asserting a state at an instant the artifact itself stamps. Anything a human typed is
candidate-only until another source dates that domain first, and `link_target` never dates a year at
all. A master-eligible class also needs a written human decision before it can assign a year, so
nothing enters the annual files on an agent's judgement.

**Structurally enforced.** `domain_year.evidence_id` is `NOT NULL` with a foreign key into
`evidence`, so no code path can write a year without naming the observation behind it, and twelve
invariants check that before every commit and again inside the archive. Tested by accident this round:
the candidate pool accumulated 575,417 strings under namespaces that never allowed arbitrary
registration and **not one reached an annual file**.

## 4. Source contributions

| Source | Evidence type | Net-new pairs | Equivalent-English |
|---|---|--:|--:|
| `rdap_snapshot` | `whois_creation` | 581,235 | 357,622.9 |
| `ia_cdx_bulk` | `cdx_timestamp` | 71,641 | 61,129.7 |
| `usenet_announce` | `dated_directory` | 106,915 | 52,774.6 |
| `iedr_register` | `artifact_listing` | 19,263 | 18,769.9 |
| `us_domain_delegated` | `artifact_listing` | 16,384 | 15,173.2 |
| `internic_zone` | `artifact_listing` | 12,503 | 8,993.1 |
| `ukwa_geoindex` | `cdx_timestamp` | 4,591 | 4,493.0 |
| `usenet_address` | `dated_directory` | 5,119 | 3,811.2 |
| `usenet_bare` | `dated_directory` | 3,467 | 2,856.8 |
| *5 further sources, each under 0.1% of the round* | | 217 | 162.2 |
| **Total** | | **821,335** | **525,786.6** |

Every row is master-eligible. Separately, **2,394,569 domains carry no year-specific evidence** and
ship as `candidates.txt`, kept out of the annual files as you asked.

**Admitted this round, and the ground each was admitted on** (the full argument, and every rejected source beside it, is in `sources.md`): **`iedr_register`**, the registry regenerated its whole register as static pages, each carrying the instant a cron wrote it; **`us_domain_delegated`**, a delegated-zone list is the registry serving those names at the instant the edition is stamped, the same instrument as a zone file; **`internic_zone`**, the zone file's own SOA serial, which the registry wrote; **`ukwa_geoindex`**, a per-row capture timestamp, self-dating and unsplit; **`ukwa_link_source`**, the crawl year on each host link-graph row.

## 5. Archive execution

| Collector prefix | Journals | Queries | Answered | Success | In-window hit rate | Distinct domains | In-window pairs |
|---|--:|--:|--:|--:|--:|--:|--:|
| `cdx_suffix` | 43 | 2,238,415 | 2,238,415 | 100.0% | 100.0% | 57,592 | 4,367,087 |
| `cdx_pool` | 247 | 148,890 | 131,375 | 88.2% | 51.6% | 131,780 | 99,623 |
| `cdx_q1` | 214 | 63,919 | 55,844 | 87.4% | 71.9% | 55,943 | 127,552 |
| `cdx_gap` | 104 | 41,816 | 35,964 | 86.0% | 98.4% | 36,355 | 134,864 |
| `cdx_q0` | 67 | 39,928 | 39,779 | 99.6% | 71.3% | 39,781 | 83,880 |
| `cdx` | 75 | 35,232 | 26,844 | 76.2% | 94.8% | 28,961 | 89,561 |
| *12 further prefixes* | 189 | 119,659 | 114,468 | 95.7% | | 114,818 | 198,358 |
| **All** | **939** | **2,687,859** | **2,642,689** | **98.3%** | **95.8%** | **418,589** | **5,100,925** |

**Strategy.** One query per domain against the Wayback CDX index, filtered to in-window captures, written to an append-only journal that is ingested only once complete, so a killed batch loses no answered query. **Errors:** of 2,687,859 queries 2,642,689 were answered (98.3%); HTTP-level failures are 3,139 (0.12%), being 0 rate limits (429), 2,155 server errors and 984 refusals (403), while **transport-level failures are 42,031 (1.56%)**, 30,193 refused or reset and 11,838 timed out. **The binding constraint is not a status code we could obey but the connection being dropped before a status exists.** **Handling:** rate limits and server errors retry with exponential backoff honouring `Retry-After`; refusals and timeouts retry with a widening delay and are then requeued, so no domain is lost to one failure; a 403 is a permanent answer for that host and is not retried.

## 6. Discovery method, and what this round learned

Collectors hold absolute epoch deadlines and outlive any session; the agent hunts and prices sources
and never writes a year itself. The gains came less from new hosts than from four measurements that
changed which sources are worth opening. `experience-summary.md` carries the full working.

- **Aim at 2001, not 1996.** The store holds **6,708,320 domains at 2000 missing 2001**, against
  103,953 for the 1996-to-1997 gap. `P(store lacks 2001 | domain held)` is 0.611 `.com`, 0.653 `.net`,
  0.568 `.org`, 0.309 `.uk`, so **one already-held `.com` name in a 2001-dated artifact is worth 0.386
  equivalent-English and about 2,600 such names clear 1,000**: 32x below the curated-directory floor,
  which was measured on artifacts dated in years already covered.
- **Novelty is a cost; the screen is held AND missing this year.** So **crawling kills discovery but
  not completeness**: a 2000-dated blacklist paid 18 equivalent-English because its names already
  carried 2000, while the 2001 edition of the same list paid **10,736**, being 84.8% known but only
  57.9% held at 2001.
- **Compute headroom from the adjacent year only.** A gap between a domain's last held year and the
  target is evidence of death, not of missing data: of 9,680 `.us` names missing 2001, **6,948 were
  last seen in July 1997**. "Held any year, missing Y" is contaminated; "held Y-1, missing Y" is not.
- **Density and authority are two independent screens.** One parliamentary corpus yielded 5 URLs in
  3.26M words; grey literature passes that screen at **221x the rate** and then fails the second at
  93.0% already held, because programme reports print the URLs of institutions we already hold.

**The method that generalised** was asking what *kind* of artifact an organisation of that era
produced, then what else sat in the same directory: that found the `.ie` register, the InterNIC 1997
zone files, the JISC UK per-year index and a US Domain delegation list. **Negative results are
first-class.** **243 source families have been searched and recorded**, 35 developed far enough to earn their own section and 208 evaluated and closed, each with the measurement that closed it, so negative results stay visible and the same ground is not broken twice. `sources.md` ships beside this report and names every one, with its acquisition route, date semantics and yield. Every rejected source is in `sources.md` with its evidence type,
location, timestamp, extraction method and the measurement that closed it.

## 7. Limitations, and whether further expansion is worthwhile

**Both routes err toward under-claiming.** A capture proves presence and never absence, so a year
with no capture is unevidenced rather than empty, and a creation date attests one year only. Neither
can invent a year; the mistake they can make is omission. **Three limits no amount of work fixes.** A
material share of archive requests fail at transport level rather than with a status code, which is
throttling seen from the other side of the socket. The corroboration split asks whether a domain is
dated somewhere, never whether a mention was genuine, so invented-but-plausible prose is the one shape
it does not stop, which is why both routes here are self-dating. And host survival correlates with
refusal: the mirrors that still run do so because an institution kept paying, and those operators are
the population now adding blanket `Disallow` rules.

**Worth expanding, in order.** Bulk dated corpora first, at two orders of magnitude more net-new pairs
per megabyte than prose. Registry datasets publishing creation dates second, the route that reaches
2001 where archives are thin. Re-auditing material already on disk third. **Not worth expanding**, each
closed with numbers this round: academic repositories and DOI datasets, national web-archive indexes,
preserved CD-ROM media, trade directories of internet businesses, and prose corpora of any kind.

## 8. The merge, the overlap and the reconciliation

**Computed here, not described.** `merge_against_baseline.py` unions these
additions into the current baseline, deduplicated on the lowercased line within
each year, and scores every file with your own calculator. Per-year form in
`audit/merge_stats_ark_*.csv`, in your column names so the two audits diff directly.

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260821` | 25,064,981 | 13,362,368.8792 |
| submitted | 769,438 | |
| already in the baseline | 0 | |
| **accepted increment** | **769,438** | **488,722.0745** |
| post-merge total | 25,834,419 | 13,851,090.9537 |

**22 of 22 reconciliation checks pass**, all arithmetic identities,
so a failure would be a defect rather than a finding: per year that
`baseline_unique + accepted_new == merged_unique` and
`already_in_baseline + accepted_new == submitted_unique`, that the per-year
increments sum to the headline figure, and that a freshly measured baseline
reproduces the totals this round was measured against. Each is listed with its
verdict in `audit/merge_audit_ark_*.json`.

## 9. Reproduction, and the four requested artifacts

`README.md` in the archive gives the order. `masters/` and `additions/` hold the merged annual lists
and this round's net-new records, `candidates.txt` the undated names, `provenance/*.parquet` every
(domain, year) joined to the evidence row justifying it. A fresh copy of this archive was extracted and put through the route above before sending. Checksums
and all four checks in `verify.sh` pass, `trace.py` resolves, the rebuild from `provenance/` returns
every per-year count exactly with all eleven invariants passing, and all fourteen result files come back
byte-identical. Tier 3 was not run: it is a roughly 50 GB download and two of this project's own
collectors were querying the Internet Archive at the time.

| | asked for | where it is |
|---|---|---|
| **D1** | runnable code, dependencies, instructions | `source/source.tar.gz` at the commit in `MANIFEST.txt`, with `pyproject.toml` and `uv.lock`; its `README.md` names what every command should print |
| **D2** | experience summary | `experience-summary.md`, distilled from `sources.md`, which carries every rejection with the measurement that closed it |
| **D3** | merge and dedup code, overlap, reconciliation | section 8, `source/scripts/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your own program vendored unmodified, explained in `metric-explained.md` |

`verify.sh` checks all four inside a fresh extraction, so none can ship unmet.
