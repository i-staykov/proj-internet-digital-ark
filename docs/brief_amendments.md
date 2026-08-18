# The brief, as amended

[SPEC.md](SPEC.md) is the reviewer's original task brief of 2026-07-21, kept **verbatim and
unedited**, because twenty-one files in this repository cite its clauses by roman numeral and that
numbering is the only way he can look one up. He has since changed the scoring metric, retired one
standard and added a new expectation, none of which appears in that document.

This file is where those changes live. It is the standing statement of what is currently being asked
for; `SPEC.md` remains the constitution and is amended here rather than in place.

Quotations are his words. Year ranges are written with a hyphen throughout, including inside
quotations, which is the only alteration made to anything quoted here.

| Round | His document | Where it is on disk |
|---|---|---|
| after phase-1 | feedback, 2026-07-27 | `feedback-phase-1/` (markdown) |
| after phase-2 | feedback v3, 2026-07-31 | `feedback-external-phase-2/` (markdown) |
| after phase-3 | feedback v4 plus the equivalent-English calculator, 2026-08-03 | `feedback-phase-3/` |
| after phase-4 | feedback, 2026-08-10 | `feedback-phase-4/` (`.docx` only, transcribed below) |
| after phase-5 | feedback, 2026-08-17 | `feedback-phase-6/`, his `.docx` transcribed in full under [ding/](ding/) |

---

## 1. The scoring metric: equivalent-English domains

**Since August 2026 this replaces record counting**, and it is the only figure that decides whether a
round was worth running.

Each unique valid `(domain, year)` record contributes the **English primary-language share of its
right-most TLD**, from a fixed `CC-MAIN-2024-10` table he supplied. Invalid or unmatched records
contribute zero. `foo.uk` is worth 0.9813 of a record, `foo.com` 0.6321, `foo.net` 0.4530,
`foo.de` 0.1324.

Three consequences that are easy to get wrong:

- **This reverses the phase-2 advice to chase non-English regional directories.** A `.br` record is
  worth 0.0934 and a `.de` one 0.1324. A large non-English source is now a small source.
- **Growth is quoted against his pre-increment total, not the post-increment one.** That is his
  convention, and dividing by the wrong total changes the headline.
- **Per-year growth is measured against that year's own baseline**, not against the corpus total.

The weight table is vendored at `src/ark/data/tld_english_share.json` and read through
`src/ark/english_share.py`. His own calculator lives at
`feedback-phase-3/equivalent_english_domain_calculator/` and is a **live dependency**:
`scripts/round_figures.py --verify` runs it over our increment and refuses the numbers if his total
differs from ours or if his validator rejects a record we counted. No figure goes to him without
passing that gate.

## 2. The page-level English standard: retired

Phase-3 feedback v4 section 6 introduced a rule that an addition had to be shown to have been an
**English-language website** in that year, judged from archived body text, and phase 4 shipped the
additions split into English-verified and unverified sets.

**That standard was retired in August 2026 and replaced by the metric above.** The deliverable is one
`additions/` set beside `candidates.txt`. Reporting page-level language verification now describes a
rule nobody applies, which reads as a rule still in force, so it is not reported at all. The engine
that implemented it is preserved at `legacy/src/language.py`; see `legacy/README.md`.

## 3. Evidence rules that have not changed

These are `SPEC.md` III and IX, restated because everything else here depends on them.

- A domain may enter an annual file only with **per-item evidence for that specific year**. No
  inference: a capture in 1998 evidences 1998 and nothing else. No interpolation across years, no
  assuming continuity, no dating a domain from a page's "last modified".
- A **WHOIS or RDAP creation date** evidences the annual file for the year it falls in, and no later
  year (III.6).
- **Cross-year duplication is required, not tolerated.** A domain shown active in four years belongs
  in four annual files, each with its own basis (III.7).
- Anything without per-item year evidence goes to the **candidate pool** and never to an annual file
  (III.2). The pool should be as large as practicable.
- The output unit is the **registered domain**, not the hostname or a user path (III.8).
- Every list ships with its acquisition method documented. Expanding a list without documenting the
  method is "strictly unacceptable" (XI).

## 4. What he asked for after phase 4, on 2026-08-10

Phase 4 was accepted in full: 946,266 records over 684,523 distinct domains, of which 76,538 had
never appeared in any of the six baseline years, worth +603,401.7811 equivalent-English, a
**10.730988%** increase. He reissued the corpus as `merged260810`.

His own summary of why the method is right, which is worth keeping because it says which parts to
protect:

> Internet Archive timestamps, RDAP registration dates, and registry-generated lists can serve as
> direct year evidence. For human-authored or OCR-derived materials such as Usenet, email, FAQs, and
> scanned magazines, requiring independent proof that the extracted string is a real domain is an
> appropriate safeguard. Unsupported strings remain in candidates.txt rather than entering annual
> files, reducing spelling errors, OCR artifacts, fabricated addresses, and filename-like false
> positives.

> Retaining the source, date, archive link, execution logs, and reconstruction programs makes the
> submission traceable and reproducible. Please preserve this evidence-first architecture in future
> rounds.

### The five priorities

1. **Residual opportunity inside every source already used.** "Revisit every successful source and
   method from this round to determine whether additional date ranges, archives, query patterns,
   address formats, geographic collections, or candidate pools remain unexhausted." Specifically:
   "identify unprocessed files, failed parses, truncated runs, unqueried candidates, missing date
   partitions, and extraction patterns with low recall."
2. **Discovery beyond the current source set**, through "automated discovery of historical corpora,
   mirrors, indexes, software archives, academic datasets, mailing-list collections, and digitized
   publications."
3. **Association and graph inference**, connecting "known domains with organizations, email
   addresses, hostnames, aliases, redirects, neighboring records, ownership data, and archived
   outbound links."
4. **Track two outcomes separately.** "Prioritize genuinely unknown domains while continuing to fill
   missing years when reliable dated evidence is available. Track these two outcomes separately so
   that discovery breadth and historical completeness remain visible." A net-new **pair** and a
   net-new **domain** are different tests, and conflating them once reported 1,161,961 domains
   against a true 463,566.
5. **Continued attention to English-language material**, following the metric.

### The intelligent-discovery expectation

This is the framing change, and it is the one that decides what phase 5 should look like:

> This is an intelligent scientific discovery and knowledge discovery problem, not merely an ordinary
> downloading task.

> Please use a broad range of creative, intelligent methods for continued domain discovery. These
> should include automated analysis, association inference, multi-source clue mining, intelligent
> scientific discovery, automated knowledge discovery, automated search engines, automated
> DeepResearch engines, and other reproducible computational strategies. The objective is to keep
> generating new hypotheses, test them against dated evidence, and continuously expand coverage of
> previously unknown domains.

> The next step is to preserve the same evidentiary rigor while increasing the breadth, automation,
> and creativity of discovery.

He put the same point more directly in an earlier message:

> The current task should not be considered simply as a conventional data collection or download
> problem. Expanding the 1996-2001 domain corpus requires a more creative approach based on
> "intelligent scientific discovery and knowledge discovery". The remaining valuable domains from
> this early Internet period may not exist in a single obvious dataset or a ready-made public
> archive. Therefore, please continue exploring this problem using various creative and intelligent
> approaches, combining different types of evidence and potential sources rather than relying only on
> traditional directory downloads or existing lists.

Read together with priority 1, the instruction is not "find more places to download from". It is:
**generate hypotheses, price them against dated evidence, and keep the ones that survive**, with the
generating and the pricing both automated. That is the argument for building the discovery harness in
[discovery.md](discovery.md) rather than adding another hand-run collector.

### On targets

Asked in August 2026 what a meaningful percentage increase would be, he answered "perhaps 10%".
Phase 4 returned 10.730988%.

**Phase 5 has a hard target: 5% by Sunday night, 2026-08-16.** Ding expects it, and Ivo confirmed on
2026-08-13 that it is a requirement rather than an aspiration. Against `merged260810` that is
**311,319.32 equivalent-English**, and it is the figure the round is judged on. It supersedes the
sentence this paragraph used to carry, that no target had been set.

**The measured shortfall is on the record and is not small.** At the rate the three engines actually
bank, the round lands near 2.5%, so the target needs roughly 4.7x the measured throughput or a bulk
dated corpus worth about 190,000 EE that has not been found. That is stated here so no later document
can quietly reinterpret the target as met.

Two things follow, and the second is the uncomfortable one.

- **5% of a grown baseline is not half of phase 4's 10.7%, it is more work in absolute terms.** Phase 4
  earned 603,401.78 EE against a smaller corpus; 5% of `merged260810` is 311,319.32 EE against a corpus
  that phase 4 itself enlarged, after phase 4 consumed the cheap sources.
- **The target is not assumed anywhere in the code, and must not be.**
  `scripts/build_query_queue.py` used to size the queue against a tenth of the baseline and no longer
  does, because carrying a met goal forward silently retargets a fraction of a baseline that has itself
  grown. A target belongs in the report and in the allocation argument, never in a queue length.

What the target costs in throughput is measured, not guessed, in the check-in of 2026-08-13 late in
`notes.md`: the round banks about 624 EE/h across all three engines, and 5% by Sunday evening needs
about 2,920 EE/h.

---

## 5. What he asked for after phase 5, on 2026-08-17

**The task documents did not change.** `Internet_Digital_Ark_Project_0815_Update.docx`,
`Update_Log.docx` and `Task_Package_File_Guide.txt` in the new package are byte-identical to the
phase-5 ones, checked by sha256. What changed is the corpus and one paragraph of email. Both are
transcribed in [ding/](ding/), which is now the place to read his brief rather than a summary of it.

Phase 5 was accepted with **nothing rejected**:

> The submission was independently checked for file integrity, domain formatting, duplication,
> evidence coverage, and Equivalent-English calculation. All submitted domain-year records were
> supported by corresponding evidence, and no invalid or duplicate records were found.

**And recalculated downward, which is the part worth remembering.** He merges against whatever
baseline is current when he gets to it, not the one quoted in the submission:

> Because 230,393 submitted records had already been incorporated into the updated `merged260817`
> baseline, the final accepted increment was recalculated against that latest baseline.

So the credited round is **2,608,322 records and 1,566,229.7613 equivalent-English, 14.901054%**,
against the 2,838,715 and 1,697,224.86 that were sent. The corpus is now `merged260817-2`:
**22,491,418 records, 12,077,095.5404 equivalent-English**.

### What he asked for next, in his words

> Please continue expanding the historical domain list and exploring additional ready-made historical
> datasets, bulk dated corpora, national web-archive link graphs, academic repositories, registry
> datasets, and other innovative automated discovery methods. Please also continue reviewing whether
> previously successful methods can produce further additions.

Six named shapes and one instruction to re-mine what already worked. Every one of them is already a
row in `sources.md`, so this is a ranking instruction rather than a new requirement: bulk dated corpora
and national link graphs first, because they are the two that outproduced per-domain querying by more
than an order of magnitude in phase 5.

**One thing the accepted figures make measurable for the first time.** He ships a per-year merge audit
of each contributor's submission alongside the baseline, so phase 6 can be aimed at where our work is
thin rather than at where it is merely possible. On the phase-5 audit our 2001 was 982,881 accepted
records against another contributor's 267, and our 1999 was 444,023 against their 1,423,310. The years
1998 to 2000 are where the corpus is being grown by someone else and 2001 is where it is not.

### The four deliverables now required of every submission

Added by email the same day, and this is the part with teeth, because it changes what a delivery
archive must contain rather than what should be collected. His words:

> For every future submission, please also provide:
>
> - The complete runnable code, scripts, configurations, dependencies, and execution instructions
>   used for discovery and processing.
> - A concise experience summary covering successful and unsuccessful approaches, measured source
>   yields, limitations, lessons learned, reusable techniques, and recommended directions for
>   continued expansion.
> - The code and explanation used to normalize, merge, and deduplicate the submitted annual files
>   against the latest baseline, including overlap counts, the accepted increment, and reconciliation
>   checks.
> - The runnable Equivalent-English Domain calculation code and a clear explanation of the fixed TLD
>   weights, model version, formula, invalid or unmatched-domain treatment, baseline total,
>   post-merge total, increment, and growth rate.

They are referred to throughout this repository as **D1** to **D4** in that order, so a commit
message or a check name can cite one without restating it.

**This is a reuse request, not a distrust one.** He had just accepted the round with nothing rejected,
so nothing here is a response to a defect. Read together, the four ask for the thing that turns one
submission into something the next person can run: the code, what was learned, the merge arithmetic,
and the metric. Section X of his standing brief already asked for reproducibility; this makes the
specific artifacts explicit.

**D3 is the one that asks for something the project has never produced.** He performs the merge on
his side and ships his own audit of it, `merge_stats_<contributor>_<date>.csv` and the matching
`merge_audit_*.json`, whose columns are `year, baseline_unique, submitted_unique, already_in_baseline,
accepted_new, merged_unique, equivalent_english_increment, growth_pct_vs_year_baseline`. Asking us to
produce it means his number and ours can be diffed, and the overlap column is exactly the one that
moved phase 5 from 2,838,715 records to 2,608,322. **Mirror his schema rather than inventing one**:
a reconciliation is only useful if the two sides have the same column names.

**D4 asks for a post-merge total, which is not the figure this project has been quoting.** Growth has
always been stated against his pre-increment baseline, which is his own convention and stays. The
post-merge total is a second number, what the corpus would hold once the submission is folded in, and
it is what makes the increment checkable by subtraction.
