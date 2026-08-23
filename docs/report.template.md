# Internet Digital Ark: round [ROUND]

Additions to the 1996-2001 annual domain lists, measured against `[BASELINE]`. Every figure is
generated from the evidence store, so no table here can drift from the files shipped beside it.

---

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

Lines 1 and 2 are the `[BASELINE]` totals, unchanged, since this increment is not yet merged. The
increment covers [UNIQUE] distinct domains, of which **[NEWDOMAINS] appear in none of the six baseline
files in any year**.

[PER_YEAR_TABLE]

The baseline column counts registered domains, so it reads lower than the raw lines of line 1; both
describe the same six files.

[CUMULATIVE]

---

## 2. What was added, and what dates each year

[ROUTES_TABLE]

`sources.md`, shipped beside this report, carries the full entry for each: acquisition command, date
semantics, measured yield, caveats.

**Both routes are self-dating and neither takes the corroboration split.** A Wayback capture
timestamp and a registry creation date are records of the thing itself rather than somebody's
description of it. The registry route is deliberately under-claimed: a creation date attests
registration for one year and nothing after it, so a domain created in 1997 and live until 2001 earns
1997 here and must earn the other four from a capture or a survey. The parser emits one evidence row
for one year, so a second cannot be written.

**The engines are request-rate bound at a single archive, and that is the whole constraint.** Two
disjoint populations run on two machines: bracketed gaps as an unattended completeness baseline, and
the candidate pool beside the discovery loop that feeds it. 2.28 million pool targets sit unqueried,
so the queue has never been the limit.

---

## 3. Source contribution statistics

[EE_SOURCE_TABLE]

Every row above is master, so eligible for the annual files. Separately, **[CANDIDATES] domains have no
year-specific evidence** and ship as `candidates.txt`, kept out of the annual masters.

---

## 4. CDX execution notes

`ark cdx`, this project's client for the public Wayback CDX API, over two disjoint populations on two
machines: the VPS works bracketed gaps as a completeness baseline, the local engine works the candidate
pool beside the discovery loop feeding it.

[CDX_TABLE]

[CDX_FAILURES]

**Still worth expanding, and still not the binding constraint.** The measurement that says so:
2,284,110 candidate names sit unqueried against engines clearing a few hundred requests an hour, so
the limit is the request rate at one archive rather than anything about the population. Section VII of
the brief forbids calling a CDX route exhausted on anything but demonstrated yield, and this route is
not exhausted; it is metered.

**One finding this round changed how the queue is ranked, and it was worth more than a week of
querying.** The pool engine fell from 91.2% in-window to 6.1% overnight without failing any health
check: alive, writing, and answering. The cause was that per-TLD hit rates were measured as lifetime
averages, and the productive names in a namespace get queried first, so a worked-out namespace keeps
a flattering average. Measured over all 188 pool journals, `.org` read 0.461 lifetime and 0.068 over
its most recent 500 answers, a 6.8x overstatement, and its 0.7101 English weight held it at the head
of the queue for 0.048 expected equivalent-English per query against 0.783 for `.uk`. Rates are now
measured over a trailing window of 2,000 answers, which corrects in both directions: `.uk` and `.com`
were understated by lifetime for the mirror reason. After re-ranking, the same engine returned 33.8%.

---

## 5. The autonomous discovery system, which is the part worth reading

This round is deliberately reported architecture-first. The collection figures above are the output; the
system below is the thing that produced them without supervision, and it is what we would keep if the
corpus were thrown away.

### 5.1 What bounds an agent that nobody is watching

Two mechanisms do the work, and both are structural rather than procedural.

**The evidence wall.** `domain_year.evidence_id` is `NOT NULL` with a foreign key into `evidence`, so no
code path anywhere can write a year assignment without naming the observation that supports it. There is
no "trust me" branch to find. Eleven integrity invariants run as `ark check` before any commit and inside
the delivery archive: the wall holds, no annual assignment rests on candidate-only evidence, every pair
carries master-eligible evidence for that exact year, no year falls outside 1996-2001, no assignment
duplicates another, and nothing earned sits unassigned.

**The approval gate.** A source class may not date a year until a human has written one `Decision:` line;
`ark ingest` refuses a master-eligible class that is `pending` and exits non-zero. The request itself is
generated, not argued: `request_approval.py` emits a seeded-random sample with live links and the measured
figures, so the reviewer checks external evidence rather than an agent's reasoning. That inversion is the
point. **An agent asserting that its own find is trustworthy is the least reliable artifact in the
system**, so the design never asks it to.

The corroboration split sits underneath both: anything a human typed is admitted only if another source
already dates that domain, and self-dating records take no split.

**These are not theoretical.** This round the candidate pool accumulated 575,417 names that cannot exist,
strings like `tfvkrp.mil` under three namespaces that have never permitted arbitrary registration, 462,155
of them from Usenet address extraction where anti-spam munging garbles text. **Not one reached an annual
file.** Every shipped `.mil`, `.gov` and `.edu` domain, 826, 6,679 and 25,155 of them, carries independent
attestation: 100.0%, zero resting on a mention alone, on the three highest-weighted namespaces in the
model where junk would have been most expensive. The wall was tested by accident and held completely.

### 5.2 The instruction file as an instrument

The agent's standing brief is one file, loaded every turn. It has been treated as a tuneable component
rather than documentation, and the finding is counter-intuitive: **it was cut from 186 lines to 79 because
length was making the agent worse.** A rule that takes a paragraph to state is a rule that gets skipped;
prose competes with the task for attention on every turn. What survives is the evidence bar, the
where-state-lives table, and a list of traps that each cost a day, one line apiece.

One copy, not one per tool, because two copies of an evidence rule drift and that is the last rule that
should. The tool-specific entry points are pointers to it.

### 5.3 Collectors that survive the agent leaving

Collection does not run inside the agent's session. Each engine is a shell supervisor taking an **absolute
epoch deadline**, detached, holding its own queue, and continuing when the agent goes away for a day. That
property is what makes unattended operation real rather than aspirational.

Two disjoint populations on two machines, so neither spends a query the other has spent: bracketed gap
years as an unattended completeness baseline, where the hit rate is flat across namespaces and ranking by
English share alone is correct; and the candidate pool beside the discovery loop, where the hit rate varies
by a factor of two and a half depending on where the name came from, so weight must be multiplied by a
**measured** rate. A scheduled `launchd` job runs the health cycle independently of any agent.

### 5.4 Health is three questions, not one

**Presence is not progress, and progress is not yield.** A supervisor that checks only liveness reports a
batch stalled on a socket as healthy; one that checks only journal growth cannot tell a journal full of
misses from one full of hits. So liveness is polled, growth is judged on a longer clock, and yield is
measured outside the supervisor against the collector's own history.

This round produced the cleanest possible demonstration. RDAP was down or crippled on both machines for
most of a day and **neither failure looked like one**: locally the process died on a dead inherited stdin
and the supervisor reported "the list is exhausted or the API refused", which is the one sentence
guaranteed to stop anyone looking, when the previous round had dated 138,783 of 200,000; remotely it was
alive, and therefore looked fine, while running at 1.92 queries a second instead of 95 because it had been
pointed at a list spanning every registry and slow registries block a queue. **A collector that is running
is not a collector that is working, and a supervisor's guess at why it stopped is not evidence.**

### 5.5 Measurement discipline, learned by getting it wrong

The recurring failure is not collecting too little; it is believing a number. Four rules now hold, each
bought with a wasted day.

**Gross and net differ by more than an order of magnitude.** Registries look spectacular on gross rate,
`.sg` at 341 and `.ca` at 234 equivalent-English per thousand queries against Verisign's 4.75, and the
population they were measured on was 97.9% already dated. Measured net on full-headroom names, `.ca` is
7.7: **1.6x, not 20x.**

**Per-query yield and total yield point opposite ways.** A link-hinted archive query is worth sixty times
an RDAP query, and the archive answers about 15,000 a day against the registries' 17 million, so RDAP
still delivers an order of magnitude more per day. Optimising the wrong one of those was written on the
decision surface and corrected within the hour.

**Rank a queue by weight alone and it fills with namespaces delegated in 2013.** `.aaa`, `.like` and `.med`
weigh 1.0 because they are English, and are worth nothing in 1996-2001. A volume floor precedes the
ranking now.

**A source's worth decays while it waits.** A parked source measured at 77,749 equivalent-English was worth
4,512 by the time it was approved, because our own sweeps had banked that population through a different
door. Anything held pending a decision is re-priced before it is quoted.

### 5.6 What the mechanisms caught this round

Three findings, all produced by a check rather than by noticing.

**A prize measured before the rule was read.** An idea priced at 1,704,843 equivalent-English, two and a
half times the whole submission threshold, was forbidden by rule 6 of the brief: a creation date alone does
not establish that a domain remained registered. The rule took four minutes to find and the measurement
took an afternoon. The same check then exposed a source already shipped that rests on the same reasoning,
which is now the one open question on the decision surface.

**A source overstated twentyfold by skipping the rules it was measured against.** A tranche was put on the
decision surface at 97,893 equivalent-English and is worth about 5,000. The query asked whether a domain
appears anywhere in the annual files and **did not exclude the corpus from corroborating itself**. The tool
that implements the rule correctly, with three filters, one of which alone rejects 35%, was already in the
repository, written for that exact question. **Look for the existing tool before writing a worse one.**

**Guards that refuse to build.** The dirty-tree guard caught an archive whose shipped code would not have
contained the script its own check looks for. The stale-export guard caught the same class twice more,
because collectors bank continuously and an export is a snapshot. The delivery privacy check caught a
round plan that would have shipped to the reviewer after a directory move defeated a pattern matching one
level only.

**Negative results are first-class, and the register is the deliverable.** [DATASETS_SEARCHED]

---

## 6. Limitations, and what is worth expanding

**Limits of this round's two routes, with the direction of each error.** A capture timestamp proves
presence and never absence, so a year with no capture is unevidenced rather than empty. A registry
creation date attests registration rather than activity, and only for the year it falls in. Both err
toward under-claiming: neither can invent a year, and the shape of the mistake they can make is
omission.

**Two limits of the archive as a whole, which no amount of querying fixes.** 12.34% of requests fail
at transport level rather than with a status code, which is the same throttling seen from the other
side of the socket. And the corroboration split, which gates anything a human typed, asks only whether
a domain is dated in some annual file and never whether the mention was genuine, so technical prose
that invents plausible examples is the one shape it does not stop. That is why this round's routes are
both self-dating.

**Worth expanding, in order, each with what ranks it.** Bulk dated corpora first, measured at 997
net-new pairs per megabyte against 15.5 for a prose corpus. National web archive link graphs second,
where the year association is explicit and the weight is high, with the caveat that most national
archives' in-window holdings turn out to be Internet Archive donations and are therefore already held.
Registry datasets publishing creation dates as open data third, because that is the route that reaches
2001 where the archives are thin. Re-auditing material already on disk fourth, which has twice been
the cheapest source available.

**Not worth expanding**: the 112 closed families in `sources.md`, each with the measurement that closed
it. Two of those closures were narrowed this round rather than reversed, and both corrections are
recorded where the original claim was made rather than only in the newest file.

---

## 7. Reproduction

`README.md` in the archive gives the full order. `masters/` and `additions/` hold the merged annual
lists and this round's net-new records, `candidates.txt` the names with no year evidence,
`provenance/*.parquet` every (domain, year) joined to the evidence row justifying it, `journals/` the
raw per-source records, and `source/source.tar.gz` the repository at the commit that built the delivery.

[REPRODUCTION_RESULT]

---

## 8. The merge, the overlap and the reconciliation

[MERGE_RECONCILIATION]

---

## 9. The four artifacts requested on 2026-08-17

| | asked for | where it is in the archive |
|---|---|---|
| **D1** | complete runnable code, scripts, configurations, dependencies, execution instructions | `source/source.tar.gz`, the repository at the commit in `MANIFEST.txt`, with `pyproject.toml` and `uv.lock`. Its `README.md` is the operating guide and names what every command should print |
| **D2** | a concise experience summary | `experience-summary.md`. `sources.md` is the full register it distils, family by family, each rejection with the measurement that closed it |
| **D3** | the merge and deduplication code, overlap counts, accepted increment, reconciliation checks | section 8 above. `source/scripts/merge_against_baseline.py`, output in `audit/merge_stats_ark_*.csv` and `audit/merge_audit_ark_*.json` |
| **D4** | the runnable metric code and its explanation | `equivalent_english_domain_calculator/`, his own program vendored unmodified, explained clause by clause in `metric-explained.md` |

`verify.sh` checks all four inside a fresh extraction, as checks 5 to 8, so none of them can ship
unmet. That is deliberate rather than tidy: the one requirement in this project that was ever
satisfied by prose alone, the evidence wall, is also the one that broke in a shipped archive.
