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

<!-- ROUND [ROUND]: two or three short paragraphs, no more.
     One per route that needs it, and only where there is something a reader could not
     infer from the table: what was done to falsify the source before it was admitted,
     where its evidence is narrower than it looks, what a checker should watch for.
     Every number here must come from a token or from `sources.md`. Nothing typed.
     Delete this comment when the paragraphs are written. -->

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

<!-- ROUND [ROUND]: one sentence on whether the CDX route is still the binding constraint,
     with the measurement that says so. Section VII of his brief forbids calling a CDX
     route exhausted on anything but demonstrated yield. Delete this comment when written. -->

---

## 5. How this contributes to an autonomous discovery system

<!-- ROUND [ROUND]: the section he reads most closely, and the one that must not repeat a
     previous round. State what the system learned to do that it could not do before, and
     price it: a rule adopted, a route retired on a measurement, a decision the harness
     made without a human. Prefer a negative result with a number over a positive claim
     without one. The machinery itself he already knows; name it in a clause, not a
     paragraph. Delete this comment when written. -->

**Negative results are first-class.** [DATASETS_SEARCHED]

---

## 6. Limitations, and what is worth expanding

<!-- ROUND [ROUND]: the honest limits of this round's sources, stating the DIRECTION of each
     error. Then what is worth expanding, in order, each with the measurement that ranks it,
     and what is not, pointing at the closed families in `sources.md`.
     Delete this comment when written. -->

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
