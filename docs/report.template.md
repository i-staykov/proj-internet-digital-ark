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

**Health is three questions, not one.** Presence is not progress and progress is not yield. A supervisor
that checks only liveness calls a batch stalled on a socket healthy; one that checks only journal growth
cannot tell misses from hits. This round RDAP was crippled on both machines for most of a day and neither
fault looked like one: locally it died on a dead inherited stdin while the supervisor reported "the list
is exhausted", and remotely it was alive and therefore looked fine while running at 1.92 queries a second
instead of 95. **A running collector is not a working one, and a supervisor's guess at why it stopped is
not evidence.**

**One method changed the question: generate the targets rather than discover them.** Finding candidate
names has never been this project's constraint; dating them has. So instead of hunting for more names we
asked which *generated* population is densest in in-window registrations, and measured four against each
other using the registry's own creation dates. English dictionary words carry an in-window creation date
on **28.00%** of queries and pay **13.5 equivalent-English per thousand queries**; siblings of names we
already hold under another gTLD pay 9.7; random four-character strings 6.3; and invented two-word
compounds pay **nothing at all**, zero in-window in 859 queries. The engine's own candidate list pays
about 4.8, so the best generated population is worth nearly three times the discovered one, and it does
not run out: the sibling queue is 14,080,169 names of which 2.3% had ever been queried. The dictionary
result also says something we did not expect. Real English words skew **1996-1999**, our thinnest years,
and are still 92.4% already held, so saturation is not a property of famous names.

**And a shape transfers where a host does not.** The largest new source this round was found by asking
what *kind* of artifact a registry of that era produced, not which registry we had not tried. The IE
Domain Registry regenerated its whole register as static A-Z web pages carrying their own line, `updated
automatically at 14:51 GMT on Friday, 21 December 2001`. That is the same instrument as a DNS zone file:
the registry asserting what was registered at a stated instant, rather than a directory listing names it
happens to know. **18,512 net-new pairs and 18,038 equivalent-English** from 27 HTTP requests and 724 KB.
The same question is now being asked of every other namespace whose registry was run by a university
computing service, which is where these artifacts survive.

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
