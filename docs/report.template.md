# Internet Digital Ark: round [ROUND]

Additions to the 1996-2001 annual lists, measured against `[BASELINE]`. Every figure is generated from
the evidence store, so no table here can disagree with the files shipped beside it.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

Lines 1 and 2 are your `[BASELINE]` totals, unchanged, since this increment is not yet merged. The
increment covers [UNIQUE] distinct domains, of which **[NEWDOMAINS] appear in none of the six baseline
files in any year**.

[PER_YEAR_TABLE]

[CUMULATIVE]

## 2. What dates each year

[ROUTES_TABLE]

**Both routes are self-dating and take no corroboration split.** A capture timestamp and a registry
creation date are records of the thing itself, not somebody's description of it. The registry route is
deliberately under-claimed: **a creation date writes its own year and no other**, per your rule 6, so a
domain created in 1997 and live in 2001 earns 1997 here and must earn the other four from a capture. The
parser emits one evidence row for one year, so a second cannot be written.

## 3. Source contributions

[EE_SOURCE_TABLE]

Every row is master-eligible. Separately, **[CANDIDATES] domains carry no year-specific evidence** and
ship as `candidates.txt`, kept out of the annual files.

## 4. Archive execution

[CDX_TABLE]

[CDX_FAILURES]

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
**19,353 net-new pairs and 18,827 equivalent-English** from 38 requests and 1.1 MB, admitted on those
grounds and on nothing else: the 99.6% agreement with your own 2000 files, edition by edition, was used
to check the reading rather than to justify it. Taken to nine further
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

**Negative results are first-class.** [DATASETS_SEARCHED]

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

[REPRODUCTION_RESULT]

## 8. The merge, the overlap and the reconciliation

[MERGE_RECONCILIATION]

## 9. The four requested artifacts

| | asked for | where it is |
|---|---|---|
| **D1** | runnable code, dependencies, execution instructions | `source/source.tar.gz` at the commit in `MANIFEST.txt`, with `pyproject.toml` and `uv.lock`. Its `README.md` names what every command should print |
| **D2** | experience summary | `experience-summary.md`, distilled from `sources.md`, which carries every rejection with the measurement that closed it |
| **D3** | merge and deduplication code, overlap counts, reconciliation | section 8, `source/scripts/merge_against_baseline.py`, output in `audit/` |
| **D4** | runnable metric code and its explanation | `equivalent_english_domain_calculator/`, your own program vendored unmodified, explained in `metric-explained.md` |

`verify.sh` checks all four inside a fresh extraction, so none can ship unmet.
