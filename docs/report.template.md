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

## 5. How this contributes to an autonomous discovery system

**The useful results this round are four negative ones about our own system, each found by a
mechanism rather than by noticing.** That is the capability worth reporting: not that the pipeline
collected, but that it caught itself.

**A rate is not a property of a namespace, it is a property of a namespace at a point in its
exhaustion.** Section 4 has the measurement. The general lesson is that a ranking model fed its own
lifetime history will keep recommending whatever it has already spent, and the fix is to measure the
margin. Two corrections were needed inside that fix, both caught by reading the queue builder's own
output rather than trusting the change: journals were being ordered by filename, which groups by
collector before time, so "the most recent 2,000 answers" meant "the last answers of whichever
collector prefix sorts last"; and windowing the pool-wide prior made every unmeasured namespace score
zero, so nothing new could ever earn a first measurement. The prior is deliberately not windowed.

**An audit of the delivery against the four artifacts requested on 2026-08-17 found that the archive
overstated its own reproducibility by four orders of magnitude.** The reproduction instructions said
the tier-3 gap was 840 domains. Measured: 2,387,824 assignments, 44.9% of everything carrying this
project's own evidence, from two sources whose inputs cannot ship, one because the depositing item
stopped serving the day after it was downloaded. Both documents now state the measured figure where a
reader meets it. Tier 2 reproduces all of it, which is why the evidence for every assignment ships as
Parquet and `verify.sh` check 4 tests that every one resolves inside the archive.

**A requirement that lives only in prose gets shipped unmet, so the four requested artifacts are
checks.** `verify.sh` grew checks 5 to 8: that the code snapshot carries its dependency manifest and
lockfile, that the experience summary covers every topic asked for, that every reconciliation identity
in the merge audit holds and that the audit agrees with the shipped files, and that the reviewer's own
calculator, run from inside the archive, reproduces the audit's baseline figure. `merge_against_baseline.py`
uses his column names unchanged so his audit and ours can be diffed rather than compared by eye.

**Two guards earned their keep by refusing to build.** The dirty-tree guard caught an archive whose
shipped code would not have contained the very script its own check looks for. The stale-export guard
caught it twice more, because the collectors bank continuously and an export is a snapshot. And the
document you are reading exists in this form because the fill refuses to write a report with an
unwritten section, which it did not do until this round.

**Negative results are first-class.** [DATASETS_SEARCHED]

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

**Not worth expanding**: the 91 closed families in `sources.md`, each with the measurement that closed
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
