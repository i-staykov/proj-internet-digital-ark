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
Phase 4 returned 10.730988%. **No target has been set for phase 5**, and none is assumed anywhere in
the code: `scripts/build_query_queue.py` used to size the queue against a tenth of the baseline and
no longer does, because carrying a met goal forward silently retargets a tenth of a baseline that has
itself grown.
