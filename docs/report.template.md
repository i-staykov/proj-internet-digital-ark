# Internet Digital Ark: round [ROUND]

Additions to the 1996-2001 annual lists, measured against `[BASELINE]`. Every figure below is
generated from the evidence store, so no table here can disagree with the files shipped beside it.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

The increment covers [UNIQUE] distinct domains, of which **[NEWDOMAINS] appear in none of the six
baseline files in any year**.

[PER_YEAR_TABLE]

[CUMULATIVE]

## 2. What is new in this round, and how to check it

Every source below was admitted for the first time in this round. Each row gives the evidence type,
what dates one item, and where the artifact is, so any of them can be opened and checked. Sources not
listed here were approved in earlier rounds and are unchanged.

[NEW_SOURCES_TABLE]

**Two of these need a sentence.** `ripe_dbase_1999` is used with the written permission of the RIPE
NCC, gratefully acknowledged, and only the domain name is read from it: no contact, address or other
personal data. `ripe_dbase_changed` reads a second attribute of that same file, the dated `changed:`
line each object carries per update; an object cannot be modified before it exists, so the line
evidences that year and no other, which is what rule 6 asks for and a creation date cannot give. Its
top eight changer addresses are ccTLD registry role accounts, DENIC alone 49.4%.

`sources.md` ships beside this report and carries every source, admitted and rejected, with its
evidence type, location, timestamp, extraction method and measurement.

## 3. What dates a year, and the standard applied

[ROUTES_TABLE]

**Both routes are self-dating and take no corroboration split**, being records of the thing itself
rather than a description of it. **A creation date writes its own year and no other**, per rule 6.

Master-eligible classes are `[MASTERTYPES]`, each a machine-written record asserting a state at an
instant the artifact stamps. Anything a human typed is candidate-only until another source dates that
domain first, and `link_target` never dates a year. **[CANDIDATES] domains carry no year-specific
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

| across [INGESTRUNS] ingest runs | records | | |
|---|--:|---|--:|
| raw lines read | [RAWLINES] | **salvaged** by normalisation | **[CORRECTED]** |
| staged records | [STAGEDRECORDS] | **rejected** as invalid | **[REJECTED]** |
| outside 1996-2001, never eligible | [OUTOFWINDOW] | | |

Reject reasons over the 1,299,177 dropped lines retained in the shipped audit CSVs: IP address 95.41%,
no known public suffix 2.92%, invalid hostname syntax 0.95%, bare public suffix 0.63%, invalid
character 0.09%.

## 5. Archive execution

[CDX_TABLE]

[CDX_FAILURES]

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

**What that gate is worth, measured.** [DECISIONS] sources were admitted in this round, each on a
separate written decision. The candidate pool accumulated 575,417 strings under namespaces that never
allowed arbitrary registration and **not one reached an annual file**. Twelve invariants run before
every commit and again inside the shipped archive; one of them caught a defect in this round, an
evidence value citing a page's date for a row dated from its own column, which was a wrong citation
rather than a wrong year.

**Negative results are recorded as first-class.** [DATASETS_SEARCHED]

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

[MERGE_RECONCILIATION]

## 9. Reproduction, and the four requested artifacts

`README.md` in the archive gives the order. `masters/` and `additions/` hold the merged annual lists
and this round's net-new records, `candidates.txt` the undated names, `provenance/*.parquet` every
(domain, year) joined to the evidence row justifying it. [REPRODUCTION_RESULT]

| | asked for | where it is |
|---|---|---|
| **D1** | runnable code, dependencies, instructions | `source/source.tar.gz` at the commit in `MANIFEST.txt`, with `pyproject.toml` and `uv.lock`; its `README.md` names what every command should print |
| **D2** | experience summary | `experience-summary.md`, distilled from `sources.md`, which carries every rejection with the measurement that closed it |
| **D3** | merge and dedup code, overlap, reconciliation | section 8, `source/scripts/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your own program vendored unmodified, explained in `metric-explained.md` |

`verify.sh` checks all four inside a fresh extraction, so none can ship unmet.
