# Internet Digital Ark: round 6

Additions to the 1996-2001 annual lists, measured against `merged260821`. Every figure below is
generated from the evidence store, so no table here can disagree with the files shipped beside it.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 25,064,981 |
| 2. Equivalent-English total | 13,362,368.8792 |
| 3. Increment | **1,929,655** records |
| 4. Equivalent-English increment | **713,481.4198** |
| 5. Equivalent-English growth rate | **5.3395%** |

The increment covers 1,660,237 distinct domains, of which **666,783 appear in none of the six
baseline files in any year**.

| Year | merged260821, this counting unit | Additions | Capture-backed |
|---|--:|--:|--:|
| 1996 | 754,672 | 55,467 | 7 (0.0%) |
| 1997 | 1,791,900 | 134,717 | 37 (0.0%) |
| 1998 | 2,233,240 | 447,042 | 695 (0.2%) |
| 1999 | 4,612,976 | 822,812 | 4,416 (0.5%) |
| 2000 | 9,471,543 | 145,578 | 3,480 (2.4%) |
| 2001 | 4,550,999 | 324,051 | 80,145 (24.7%) |
| **Total** | **23,415,330** | **1,929,667** | **88,780 (4.6%)** |

**Cumulative.** Across the 4 rounds shipped so far plus this one, this project has added 7,065,728 domain-year records worth 3,731,492.3212 equivalent-English, **27.9254%** of the 13,362,368.8792 the corpus holds today. Records / equivalent-English by round, each at the figure you ACCEPTED rather than the one submitted: round 1 1,429,524 / 756,559; round 3 151,949 / 91,815; round 4 946,266 / 603,402; round 5 2,608,322 / 1,566,230; **6, this one 1,929,667 / 713,487**.

## 2. What is new in this round, and how to check it

Every source below was admitted for the first time in this round. Each row gives the evidence type,
what dates one item, and where the artifact is, so any of them can be opened and checked. Sources not
listed here were approved in earlier rounds and are unchanged.

| Source | Evidence type | What dates one item | Receipt | Pairs | EE |
|---|---|---|---|--:|--:|
| `ripe_dbase_1999` | `artifact_listing` | the file's own generation stamp, `# 990804 00:07:01` on line 2 | ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz | 641,038 | 90,770.3 |
| `ripe_dbase_changed` | `artifact_listing` | the date on each object's own `changed:` transaction line | same file, `*ch:` attribute | 399,401 | 58,398.0 |
| `us_domain_delegated` | `artifact_listing` | the edition's tar-preserved mtime, or its capture stamp | archive.org/details/2015.04.ftp.isc.org and www.isi.edu/in-notes/ | 16,384 | 15,173.2 |
| `squidguard_2001_blacklist` | `artifact_listing` | the list's own `compiled in ... on 2001.12.18` header, or the diff's filename date | archive.debian.org/.../squidguard_1.2.0.orig.tar.gz | 18,000 | 10,376.9 |
| `namewinner_expiring` | `artifact_listing` | the per-row date `25-OCT-01`, on every line | web.archive.org/web/20011026120205id_/namewinner.com/whole_list.php?del=tab | 18,937 | 11,546.3 |
| `can_domain_registry_notices` | `whois_creation` | the registry's own `Date-Approved:` field in its public approval notice | archive.org/download/usenet-can/can.domain.mbox.zip | 9,485 | 7,934.2 |
| `cctld_register_listing_inbody` | `artifact_listing` | the register page's own machine-written timestamp, or the row's due date | twnic.net.tw/DN/fz1.shtml and idnic.net.id/Info/RekapBelumBayar.html | 10,177 | 1,609.6 |
| `dartmouth_bfs_seed` | `cdx_timestamp` | field 2 of each CDX row, a 14-digit capture timestamp | archive.org, Dartmouth_10KwebURLs_GWB BFS level 0 | 2,442 | 1,408.6 |
| `iedr_register` | `artifact_listing` | the register page's own `updated automatically at ... 2001` line | IE Domain Registry register, archived | 19,263 | 18,769.9 |
| `internic_zone` | `artifact_listing` | the SOA serial inside the zone payload, `1997041800` | InterNIC 1997 zone files, nic.mil mirror | 12,503 | 8,993.1 |
| `ukwa_geoindex` | `cdx_timestamp` | the 14-digit capture timestamp on each row | webarchive.org.uk/datasets/ukwa.ds.2/geo/ | 4,591 | 4,493.0 |

**Two of these need a sentence.** `ripe_dbase_1999` is used with the written permission of the RIPE
NCC, gratefully acknowledged, and only the domain name is read from it: no contact, address or other
personal data. `ripe_dbase_changed` reads a second attribute of that same file, the dated `changed:`
line each object carries per update; an object cannot be modified before it exists, so the line
evidences that year and no other, which is what rule 6 asks for and a creation date cannot give. Its
top eight changer addresses are ccTLD registry role accounts, DENIC alone 49.4%.

`sources.md` ships beside this report and carries every source, admitted and rejected, with its
evidence type, location, timestamp, extraction method and measurement.

## 3. What dates a year, and the standard applied

| Route | What dates a year | Net-new pairs |
|---|---|--:|
| the two archive engines, a bracketed-gap population and the candidate pool | the Wayback capture timestamp, per domain and year | 80,270 |
| the RDAP sweep over the candidate pool | the registry's own creation date, which dates that year and no other | 581,458 |

**Both routes are self-dating and take no corroboration split**, being records of the thing itself
rather than a description of it. **A creation date writes its own year and no other**, per rule 6.

Master-eligible classes are ``artifact_listing`, `cdx_timestamp`, `dated_directory`, `link_source`, `whois_creation``, each a machine-written record asserting a state at an
instant the artifact stamps. Anything a human typed is candidate-only until another source dates that
domain first, and `link_target` never dates a year. **2,380,575 domains carry no year-specific
evidence** and ship as `candidates.txt`, kept out of the annual files.

## 4. Counting unit, normalisation and what is dropped

**The counting unit is the (registrable domain, year) pair**, deduplicated on the lowercased line
within each year. Every name from every source passes through one function before reaching the
database, so the dedup key is identical across sources.

**Normalisation, in order:** percent-decode, trim, lowercase; strip scheme, `//`, path, query,
fragment, userinfo, port, and stray leading or trailing `.` and `,` but never a hyphen; then reduce to
the registrable domain with a pinned Public Suffix List plus historical ccTLDs, so `ci.anchorage.ak.us`
becomes `anchorage.ak.us` while `k12.ak.us` is refused as a public suffix in its own right.
**Validity:** drop the line if it is empty, an IPv4 literal, a reverse-DNS zone, syntactically invalid,
carries no known public suffix, is a bare public suffix, or has an invalid character in the registered
label. **Salvage** is the same operation on a dirty line, so a URL or mail address is reduced rather
than discarded.

| across 131,825 ingest runs | records | | |
|---|--:|---|--:|
| raw lines read | 1,634,272,120 | **salvaged** by normalisation | **129,805,348** |
| staged records | 213,031,636 | **rejected** as invalid | **2,836,010** |
| outside 1996-2001, never eligible | 1,236,761,978 | | |

Reject reasons over the 1,299,177 dropped lines retained in the shipped audit CSVs: IP address 95.41%,
no known public suffix 2.92%, invalid hostname syntax 0.95%, bare public suffix 0.63%, invalid
character 0.09%.

## 5. Archive execution

| Collector prefix | Journals | Queries | Answered | Success | In-window hit rate | Distinct domains | In-window pairs |
|---|--:|--:|--:|--:|--:|--:|--:|
| `cdx_suffix` | 43 | 2,238,415 | 2,238,415 | 100.0% | 100.0% | 57,592 | 4,367,087 |
| `cdx_pool` | 253 | 152,394 | 133,671 | 87.7% | 52.2% | 134,197 | 104,344 |
| `cdx_q1` | 214 | 63,919 | 55,844 | 87.4% | 71.9% | 55,943 | 127,552 |
| *16 further prefixes* | 446 | 249,484 | 229,119 | 91.8% | | 231,915 | 525,056 |
| **All** | **956** | **2,704,212** | **2,657,049** | **98.3%** | **95.7%** | **432,095** | **5,124,039** |

**Strategy.** One query per domain against the Wayback CDX index, filtered to in-window captures, written to an append-only journal that is ingested only once complete, so a killed batch loses no answered query. **Errors:** of 2,704,212 queries 2,657,049 were answered (98.3%); HTTP-level failures are 3,139 (0.12%), being 0 rate limits (429), 2,155 server errors and 984 refusals (403), while **transport-level failures are 44,024 (1.63%)**, 31,362 refused or reset and 12,662 timed out. **The binding constraint is not a status code we could obey but the connection being dropped before a status exists.** **Handling:** rate limits and server errors retry with exponential backoff honouring `Retry-After`; refusals and timeouts retry with a widening delay and are then requeued, so no domain is lost to one failure; a 403 is a permanent answer for that host and is not retried.

## 6. How the discovery ran, and where the human sits

The system runs unattended for hours at a time and **never assigns a year on its own judgement**. That
split is the design, and it is what makes the output checkable.

**What ran.** Collectors are detached shell supervisors holding an absolute epoch deadline, so they
outlive the session that started them and a day of absence costs nothing. The agent spends its turns
hunting sources, measuring them against the store and pricing them, and writes no year itself.

**What worked and what did not.** One clear written instruction from the supervisor, then unattended
running, worked: it is how this round's sources were found. Detached collectors with absolute deadlines
worked, and kept collecting through a day when the agent was unreachable. **Scheduled wake-ups did
not**: the agent answered only some firings. **A self-scheduling loop did not hold** either, tried
once. So the durable pattern is a human-written objective plus processes that do not depend on the
agent being awake.

**Where the human sits.** The agent runs the two collection engines, which are mechanical, and it may
re-run anything already decided. Everything else goes onto an approval list with a measured figure and
primary links. The supervisor works through that list source by source, opens the links, checks the
dating argument, and rules per source: master, candidate-only or rejected. **This is enforced in code
rather than by habit**: `ark ingest` refuses to run for a class with no written `Decision:` line, and
it refused twice in this round until the decision existed.

**What that gate is worth, measured.** 11 sources were admitted in this round, each on a
separate written decision. The candidate pool accumulated 575,417 strings under namespaces that never
allowed arbitrary registration and **not one reached an annual file**. Twelve invariants run before
every commit and again inside the shipped archive; one of them caught a defect in this round, an
evidence value citing a page's date for a row dated from its own column, which was a wrong citation
rather than a wrong year.

**Negative results are recorded as first-class.** **252 source families have been searched and recorded**, 44 developed far enough to earn their own section and 208 evaluated and closed, each with the measurement that closed it, so negative results stay visible and the same ground is not broken twice. `sources.md` ships beside this report and names every one, with its acquisition route, date semantics and yield.

## 7. Limitations, and whether to expand further

A capture proves presence and never absence, so a year with no capture is unevidenced rather than
empty, and a creation date attests one year only. Neither route can invent a year; the mistake they can
make is omission. A material share of archive requests fail at transport level rather than with a
status code, which is throttling seen from the other side of the socket.

**Worth expanding, in order.** Bulk dated corpora first. Registry datasets publishing dates second,
the route that reaches 2001 where archives are thin. Re-auditing material already on disk third, which
produced the largest single addition of this round. **Closed with measurements this round**, so not
worth repeating: academic repositories and DOI datasets, national web-archive indexes, preserved CD-ROM
media, trade directories of internet businesses, FTP-mirror archive listings, and prose corpora.

## 8. Merge, overlap and reconciliation

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
