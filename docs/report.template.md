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

Every source below was admitted for the first time in this round. Sources approved in earlier rounds
are unchanged and still contributing, above all `usenet_announce`; their yields are in
`audit/source_contribution.csv`, whose `netnew_pairs` column sums to the increment in section 1. Each
row gives what dates one item and where the artifact is, so any of them can be opened and checked.

[NEW_SOURCES_TABLE]

**Two of these need a sentence.** `ripe_dbase_1999` is used with the written permission of the RIPE
NCC, gratefully acknowledged, and only the domain name is read from it: no contact, address or other
personal data. `ripe_dbase_changed` reads a second attribute of that same file, the dated `changed:`
line each object carries per update; an object cannot be modified before it exists, so the line
evidences that year and no other, which is what rule 6 asks for and a creation date cannot give.

`sources.md` ships beside this report and carries every source, admitted and rejected, with the
argument that dates its items. The rules deciding what counts as one valid, non-duplicated addition
of ours are in `source/src/ark/canonical.py`, with their tests, and apply to our additions only.

## 3. What dates a year, and the standard applied

[ROUTES_TABLE]

**Both routes are self-dating and take no corroboration split**, being records of the thing itself
rather than a description of it. **A creation date writes its own year and no other**, per rule 6.
Registry creation dates alone are half this round's equivalent-English, on 30% of its pairs: weight
decides, not volume, and the source contributing the most pairs paid a fifth as much because it is
mostly `.de` at 0.1324. Per-source figures are in `audit/source_contribution.csv`.

Master-eligible classes are [MASTERTYPES], each a machine-written record asserting a state at an
instant the artifact stamps. Anything a human typed is candidate-only until another source dates that
domain first, and `link_target` never dates a year. **[CANDIDATES] domains carry no year-specific
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

**Generating the names to ask about, rather than discovering them.** The candidate pool held
2,395,205 names with no in-window year when this was measured on 24 August, and asking RDAP about them
returns almost nothing: 602
queries drawn twice, once from the head and once seeded-random, produced **zero** in-window creation
dates, because 73% of the pool answers 404 against 21.6% for domains we hold. A name no crawler
captured is usually a name that was never much of a site. So the question was inverted, from *which
real names have we not yet dated* to *which names can we invent that a registry will date for us*.
Four generated populations were priced against each other in the same unit, equivalent-English per
1,000 queries: **sibling names**, every
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

**What that gate is worth, measured.** [DECISIONS] sources were admitted in this round, each on a
separate written decision. [POOL_RESTRICTED] strings sit in the candidate pool under `.edu`, `.gov` and
`.mil`, namespaces no one could register in freely, and **not one of them reached an annual file**
without independent attestation. thirteen invariants run before
every commit and again inside the shipped archive; one of them caught a defect in this round, an
evidence value citing a page's date for a row dated from its own column, which was a wrong citation
rather than a wrong year.

**Negative results are recorded as first-class.** [DATASETS_SEARCHED]

## 5. Limitations, and whether to expand further

A capture proves presence and never absence, so a year with no capture is unevidenced rather than
empty, and a creation date attests one year only. Neither route can invent a year; the mistake they
can make is omission. A material share of archive requests fail at transport level rather than with a
status code, which is throttling seen from the other side of the socket.

**Worth expanding, in order.** Bulk dated corpora first. Registry datasets publishing dates second,
the route that reaches 2001 where the archives are thin. Re-auditing material already on disk third,
which produced 399,401 pairs and 58,398 equivalent-English for no new download. Fourth and slowest, but
still viable indefinitely: keep querying the archives, RDAP and registry databases, which is the one
route with no supply limit and a measured rate we can plan against.

**Less promising, on this round's measurements, because saturation is higher than the sources are
long**: academic repositories and DOI datasets, national web-archive indexes, preserved CD-ROM media,
trade directories of internet businesses, FTP-mirror archive listings, and prose corpora. Each was
measured rather than assumed, and the measurement is in `sources.md`.

## 6. Merge, overlap and reconciliation

[MERGE_RECONCILIATION]

## 7. Reproduction, and the four requested artifacts

`README.md` in the archive gives the order. `masters/` and `additions/` hold the merged annual lists
and this round's net-new records, `candidates.txt` the undated names, `provenance/*.parquet` every
(domain, year) joined to the evidence row justifying it, and `logs/` the collectors' execution logs.
[REPRODUCTION_RESULT]

| | asked for | where it is |
|---|---|---|
| **D1** | runnable code, dependencies, instructions | `source/source.tar.gz` at the commit in `source/COMMIT.txt`, with `pyproject.toml` and `uv.lock`; its `README.md` names what every command should print |
| **D2** | experience summary | `experience-summary.md`, distilled from `sources.md`, which carries every rejection with the measurement that closed it |
| **D3** | merge and dedup code, overlap, reconciliation | section 6, `source/scripts/round/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your own program vendored unmodified, explained in `metric-explained.md` |

`verify.sh` checks all four inside a fresh extraction, so none can ship unmet.
