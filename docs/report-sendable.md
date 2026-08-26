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

| Year | merged260821 | Additions | Merged | Equivalent-English added |
|---|--:|--:|--:|--:|
| 1996 | 866,121 | 55,467 | 921,588 | 26,420.9323 |
| 1997 | 1,891,386 | 134,717 | 2,026,103 | 52,829.5998 |
| 1998 | 2,542,561 | 447,039 | 2,989,600 | 129,096.5233 |
| 1999 | 5,118,649 | 822,806 | 5,941,455 | 205,286.2928 |
| 2000 | 9,670,871 | 145,577 | 9,816,448 | 91,406.4015 |
| 2001 | 4,975,393 | 324,049 | 5,299,442 | 208,441.6701 |
| **Total** | **25,064,981** | **1,929,655** | **26,994,636** | **713,481.4198** |

**Cumulative.** Summing the increases you have awarded, which is how the update log of 2026-08-18 defines the score: 1.659986%, 10.730988%, 14.901054% and this round's 5.3395% give **32.6316%**, with round 1's 1,429,524 records held out because it was awarded at 17.38% on records before the equivalent-English metric existed.

## 2. What is new in this round, and how to check it

Every source below was admitted for the first time in this round; everything else was approved in an
earlier round and is unchanged. Each row gives what dates one item and where the artifact is, so any
of them can be opened and checked.

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
evidences that year and no other, which is what rule 6 asks for and a creation date cannot give.

`sources.md` ships beside this report and carries every source, admitted and rejected, with the
argument that dates its items. The rules deciding what counts as one valid, non-duplicated addition
of ours are in `source/src/ark/canonical.py`, with their tests, and apply to our additions only.

## 3. What dates a year, and the standard applied

| Route | What dates a year | Net-new pairs |
|---|---|--:|
| the two archive engines, a bracketed-gap population and the candidate pool | the Wayback capture timestamp, per domain and year | 80,270 |
| the RDAP sweep over generated sibling names and over `.uk` we already hold | the registry's own creation date, which dates that year and no other | 581,458 |

**Both routes are self-dating and take no corroboration split**, being records of the thing itself
rather than a description of it. **A creation date writes its own year and no other**, per rule 6.

Master-eligible classes are `artifact_listing`, `cdx_timestamp`, `dated_directory`, `link_source`, `whois_creation`, each a machine-written record asserting a state at an
instant the artifact stamps. Anything a human typed is candidate-only until another source dates that
domain first, and `link_target` never dates a year. **2,380,575 domains carry no year-specific
evidence** and ship as `candidates.txt`, kept out of the annual files.

## 4. How the discovery ran, and where the human sits

The system runs unattended for hours at a time and **never assigns a year on its own judgement**.
That split is the design, and it is what makes the output checkable.

**What worked and what did not.** One clear written objective from the supervisor, then unattended
running, worked: it is how this round's sources were found. Detached collectors holding an absolute
epoch deadline worked, and kept collecting through a day when the agent could not be reached.
**Scheduled wake-ups did not**: the agent answered only some firings. **A self-scheduling loop did
not hold** either, tried once. So the durable pattern is a human-written objective plus processes
that do not depend on the agent being awake.

**Generating the names to ask about, rather than discovering them.** The candidate pool holds
2,395,205 names with no in-window year, and asking RDAP about them returns almost nothing: 602
queries drawn twice, once from the head and once seeded-random, produced **zero** in-window creation
dates, because 73% of the pool answers 404 against 21.6% for domains we hold. A name no crawler
captured is usually a name that was never much of a site. So the question was inverted, from *which
real names have we not yet dated* to *which names can we invent that a registry will date for us*.
Four generated populations were priced against each other at equal cost: **sibling names**, every
`.com`/`.net`/`.org` label we hold in window re-suffixed to the other two and filtered to what the
store lacks, 14,080,169 of them, measured over a first full round of 150,000 queries at 14,205
in-window creation dates, 9.47%, **59.9 equivalent-English per 1,000 queries**; **English dictionary
words** across the same three suffixes, the densest in hit rate at 28.0% but 92.4% already held and
finite at roughly 235,000 words, so 13.5 per 1,000; **random four-character strings**, 6.3; and
**invented two-word compounds**, 859 queries and **exactly zero** in-window, a population that was
registered later or never. Inventing the query beat two and a half million discovered candidates by
an unbounded margin, and the reason is that a registry answers about names that survived while an
archive is the only thing that can date a name that died.

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

**Negative results are recorded as first-class.** **251 source families have been searched and recorded**, 44 developed far enough to earn their own section and 207 evaluated and closed, each with the measurement that closed it, so negative results stay visible and the same ground is not broken twice. `sources.md` ships beside this report and names every one, with its acquisition route, date semantics and yield.

## 5. Limitations, and whether to expand further

A capture proves presence and never absence, so a year with no capture is unevidenced rather than
empty, and a creation date attests one year only. Neither route can invent a year; the mistake they
can make is omission. A material share of archive requests fail at transport level rather than with a
status code, which is throttling seen from the other side of the socket.

**Worth expanding, in order.** Bulk dated corpora first. Registry datasets publishing dates second,
the route that reaches 2001 where the archives are thin. Re-auditing material already on disk third,
which produced the largest single addition of this round and cost nothing. Fourth and slowest, but
still viable indefinitely: keep querying the archives, RDAP and registry databases, which is the one
route with no supply limit and a measured rate we can plan against.

**Less promising, on this round's measurements, because saturation is higher than the sources are
long**: academic repositories and DOI datasets, national web-archive indexes, preserved CD-ROM media,
trade directories of internet businesses, FTP-mirror archive listings, and prose corpora. Each was
measured rather than assumed, and the measurement is in `sources.md`.

## 6. Merge, overlap and reconciliation

`merge_against_baseline.py` unions these additions into the current baseline,
deduplicated on the lowercased line within each year, and scores every file with your
own calculator. Per-year form in `audit/merge_stats_ark_*.csv`, in your column names
so the two audits diff directly.

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260821` | 25,064,981 | 13,362,368.8792 |
| submitted | 1,929,655 | |
| already in the baseline | 0 | |
| **accepted increment** | **1,929,655** | **713,481.4198** |
| post-merge total | 26,994,636 | 14,075,850.2990 |

**22 of 22 reconciliation checks pass.** All are arithmetic
identities, so a failure would be a defect rather than a finding: per year that
`baseline_unique + accepted_new == merged_unique`, that the per-year increments sum
to the headline, and that a freshly measured baseline reproduces the totals this
round was measured against. Each is listed with its verdict in
`audit/merge_audit_ark_*.json`.

## 7. Reproduction, and the four requested artifacts

`README.md` in the archive gives the order. `masters/` and `additions/` hold the merged annual lists
and this round's net-new records, `candidates.txt` the undated names, `provenance/*.parquet` every
(domain, year) joined to the evidence row justifying it, and `logs/` the collectors' execution logs.
A fresh copy of this archive was extracted and put through the route above before sending. Checksums
and all four checks in `verify.sh` pass, `trace.py` resolves, the rebuild from `provenance/` returns
every per-year count exactly with all eleven invariants passing, and all fourteen result files come back
byte-identical. Tier 3 was not run: it is a roughly 50 GB download and two of this project's own
collectors were querying the Internet Archive at the time.

| | asked for | where it is |
|---|---|---|
| **D1** | runnable code, dependencies, instructions | `source/source.tar.gz` at the commit in `MANIFEST.txt`, with `pyproject.toml` and `uv.lock`; its `README.md` names what every command should print |
| **D2** | experience summary | `experience-summary.md`, distilled from `sources.md`, which carries every rejection with the measurement that closed it |
| **D3** | merge and dedup code, overlap, reconciliation | section 6, `source/scripts/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your own program vendored unmodified, explained in `metric-explained.md` |

`verify.sh` checks all four inside a fresh extraction, so none can ship unmet.
