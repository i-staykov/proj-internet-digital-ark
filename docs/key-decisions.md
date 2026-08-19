# Key decisions, open and closed

**What this is.** A two-minute review surface for Ivo. The agent appends here as it works, so a
decision can be reversed while it still matters rather than after the round ships.

**This is the only file that asks Ivo for anything**, on his instruction of 2026-08-11: "Everything
I have to sign-off should be in one place, so I know about it." So:

- `notes.md` entries **no longer ask for a sign-off**. That log is the agent's own working, and
  asking him to countersign 37 entries of it buried the few things that genuinely needed him.
- A `pending` class in `approved-sources-list.md` is **mirrored here automatically**, by
  `request_approval.py` when it writes the request and by `just cycle` if one ever appears without
  an entry. That file stays the thing `ark ingest` enforces and the thing he edits; this is how he
  learns it wants him. A test against both live files fails if a pending class is not named here.
- **Unfinished hypotheses are not raised here.** They are the agent's queue: screened, priced and
  decided without asking, and only an outcome worth overruling becomes an entry under `OPEN`.

**How it differs from the other two logs.** `notes.md` is the full dated reasoning and is append-only
history, 4,600 lines of it. `ROUND.md` is the generated current state. **This file is neither: it is
the short list of things a human might want to overrule.** One entry, one screen at most, and a
pointer to the ADR or notes entry that carries the working.

**Reading it.** `OPEN` needs you. `CLOSED` was decided by the agent under a standing rule or a
measurement, and is recorded so you can still object. Newest first within each block.

---

## OPEN

**Project paused 2026-08-18 and handed to GitHub Copilot.** Collectors stopped, round packaged and not
sent. Read `handoff-ivo.md` first; the agent reads `.github/copilot-instructions.md` and
`handoff-copilot.md`.

### The only question that matters now: where do 590,000 equivalent-English come from?

**5% gates every submission** (Ivo, 2026-08-18): we may not send anything below it. That closes the
cadence question I had open here, and it makes the arithmetic brutal rather than merely tight.

- threshold today: **603,854.78 EE**; we hold **14,358.92**.
- the threshold **recedes by about 54,101 EE a day** as other contributors grow the corpus, measured at
  1,082,013 EE/day over the newest interval between his releases.
- our own collection adds about **13,200 EE a day**.
- so the gap **widens by roughly 40,901 EE a day and never closes by querying.** `scripts/submission_cadence.py`.

**Therefore only a bulk dated corpus can produce a submittable round**, something in the order of 600,000
EE at once, which is what phase 5 did at 195,779 EE/day by landing `domain_creation_bulk` and the
Dartmouth capture census. Per-domain archive querying is arithmetically incapable of it. Seven source
families were screened on 2026-08-18 and every one was already closed on a sound measurement, so **there
is no known candidate of that size on the list today.** That is the honest state, and it is the problem
to hand over.

### The one sized lead found on 2026-08-19: the registry route is roughly 40% worked, not finished

`domain_creation_bulk` is the largest source this project holds, 2,165,523 in-window pairs from a
published compilation of 171 million domains. **It was assumed to be spent. Measured, it is not.**

Counted over the 25.9 GB file itself: **84,279,284 `.com` rows, of which 2,100,199 carry a creation date
inside 1996-2001.** The current `.com` zone is roughly 157 million names, so the compilation holds about
**half the namespace**.

**The tempting inference is that a complete compilation holds twice as many in-window creations, and it
had to be tested rather than believed.** The test: draw 2,999 `.com` domains this project already dates
inside the window **on evidence that is not `whois_creation`**, so the sample cannot have come from this
file, and ask how many the file holds.

| | |
|---|--:|
| sampled, dated in window on non-WHOIS evidence | 2,999 |
| present in the compilation at all | **1,187 (39.6%)** |
| of those, carrying an in-window creation date | 656 (55.3% of the 1,187) |

Two things fall out. **The compilation covers the in-window population worse than it covers the
namespace**, 39.6% against about 54%, and **44.7% of the in-window names it does hold now carry a later
creation date**, which is a domain that dropped and was re-registered, and is the mechanism that makes
WHOIS lossy about 1998 in the first place.

**What that is worth, stated as an estimate and not a measurement.** If the uncovered part of the current
`.com` zone carries in-window creations at anything like the density of the covered part, a complete
current compilation is worth a further **1.8 to 3.1 million `.com` year-pairs, or roughly 1.1 to 2.0
million equivalent-English at weight 0.6321**. That is two to three times the 603,855 EE gate. The range
is wide because it turns on how much of the 39.6% shortfall is names that no longer exist anywhere, which
no current compilation can recover, against names simply absent from this publisher's crawl.

**So the ask is concrete rather than a research direction, and it is the first thing found in this round
that could clear 5% on its own.** Three routes, in ascending cost:

1. **A larger published compilation.** The one we hold is a Kaggle deposit and there is no Kaggle account
   on this machine. Others may exist. This costs an account and an afternoon.
2. **ICANN CZDS.** Free zone-file access to `.com`, `.net` and `.org` gives the complete current name
   list, though not creation dates. It needs an account, a stated purpose and registry approval. It would
   settle the estimate above exactly, by telling us how many names the compilation is missing.
3. **Creation dates for the missing names.** This is the part that does not scale: port-43 and RDAP run
   at thousands a day here, and tens of millions of lookups is not a plan. So route 3 only becomes real
   if route 1 finds a compilation that already did the work.

**Nothing here has been fetched and nothing needs deciding tonight.** What is needed is a yes to opening
a Kaggle account and applying to CZDS, both of which are ordinary and neither of which touches the
evidence rules: a registry creation date is already an approved master class under `whois_creation`.

### Our cumulative score, reconstructed: 41.0640%

Ding does not hold this figure either, so it is reconstructed from his emails on your instruction: the
sum of the **net-new record** percentage of each accepted round, each against the baseline it was scored
against.

| round | accepted records | baseline records | record % |
|---|--:|--:|--:|
| 1 | 1,429,524 | 8,224,963 | 17.3803% |
| 3 | 151,949 | 10,263,632 | 1.4805% |
| 4 | 946,266 | 10,415,768 | 9.0849% |
| 5 | 2,608,322 | 19,883,096 | 13.1183% |
| | | | **41.0640%** |

**The method is validated by round 1**: he stated 17.38% himself and this reproduces 17.3803%. One
baseline is derived rather than quoted, `merged260730` at 10,263,632 = 9,654,487 plus the 609,145 records
of an external contributor's round, so that row carries a small uncertainty and no other does.

**Reported separately, as you asked:** cumulative accepted equivalent-English is **3,018,005.5168** over
5,136,061 records, which is 24.9895% of the corpus as it now stands. That percentage is not additive and
must not be summed with the table above.

### Approve, refuse or downgrade internic_zone / artifact_listing

Still `pending`, so `ark ingest` refuses it and its journal waits on disk. **12,150 net-new pairs and
8,627.7 EE** under `master`, 7,089 and 5,033.9 under the corroboration split, zero as `candidate-only`.
The request block in `approved-sources-list.md` carries a seeded-random sample with live links, the
measured figures and the counterfactual. It is worth 60% of the packaged round, and it is nowhere near
the 5% gate on its own.

### Two permission asks, and one of them has now been priced

- **May we query Nominet in bulk for the `.uk` pool?** Their terms are ambiguous and a sweep was stopped
  for that reason. **Priced 2026-08-19 and it is small: the whole ceiling is 48,545 EE.** The pool holds
  49,470 undated `.uk` names at weight 0.9813, so even if Nominet answered every one with a creation date
  inside the window, that is **8.0% of the 603,855 EE gate** and 3.0% of the pool's own upper bound. A
  WHOIS sweep of names we already hold cannot be the route to a submittable round, whatever the terms
  say. What could be is a **bulk request to Nominet for the names registered 1996-2001**, which is a
  different ask and belongs with the outreach below rather than with a sweep.
- **May the project write two researchers and one agency** to ask whether an early-web crawl or link
  graph can be shared? This is the one route that could plausibly reach 600,000 EE, because it asks for
  bulk data that is not published. **It is now the only such route on the list**, since the repository
  registries were swept and are dry (C-25).

### Triage the newly found sources: 60 found, none priced

A counter, not a request, by your instruction of 2026-08-15: you review this when something reaches 5%. **60 source(s) found and not yet priced**, listed in `approved-sources-list.md` under `## Found, awaiting triage`.

Priced whole, the queue covers about a tenth of the deficit, so nothing here is urgent and reviewing it would not change this round. **Nothing is blocked either way**: a pending class cannot date a year, so `ark ingest` refuses it and collection continues. One word each when you want them, *candidate pool* or *fold in directly*.

## CLOSED

### C-27. A third of the candidate pool's quoted value is names that were never real (2026-08-19)

**The pool's headline "1,639,929 EE if every one earned a year" is overstated by 574,973 EE, 35.1%,
and the overstatement sits in one identifiable block.** 584,646 undated candidates are `.gov`, `.mil`,
`.edu` or `.int`, namespaces whose weights are 0.9825, 0.9981, 0.9717 and 1.0000, so they carry a third
of the ceiling on 25% of the rows. `.gov` and `.mil` are closed registries that between them never held
more than a few thousand names in the window, and the store holds 184,948 and 186,181 of them.

They arrive almost entirely from `usenet_address_mention` and `usenet_mention`, and they are what
anti-harvester munging looks like at scale: `yjwuuxuqqa.gov`, `sboojsgvvo.gov`, `rjhxf.mil`.

**Measured rather than asserted, and with the positive control the brief demands.** Within the
`cdx_pool` journals, so the same population, period and method on both sides:

| namespace | answered | with a capture | rate |
|---|--:|--:|--:|
| everything else | 105,404 | 51,328 | **48.70%** |
| `.edu` | 1,709 | 5 | 0.29% |
| `.mil` | 1,372 | 0 | 0.00% |
| `.gov` | 394 | 0 | 0.00% |
| `.int` | 30 | 0 | 0.00% |

**The positive control is that the same namespaces answer normally elsewhere in the same engine.** In
`cdx_gap`, `cdx_q0` and `cdx_q1`, `.edu` returns 74.7% to 86.0% and `.gov` 57.1% to 94.2%. So neither the
namespace nor the query method is at fault, and a search that found nothing here has proved something
rather than been pointed at the wrong place. That test is the whole reason this is a closure and not a
hunch.

**This is not a name-shape filter and must not be turned into one.** The membership test that justifies
excluding these rows is registry closure, an external fact about `.gov` and `.mil`, not the look of the
strings. `dotgov_real_names` in the triage queue is the list that would make the exclusion checkable.

Nothing has been deleted and no filter has been applied. What changes is the quoted ceiling, and that
574,374 of the 2,278,511 rows in `queue_pool_local.txt` are worth 0.14% rather than 48.70%. They rank
late, so the engine is not spending on them today.

### C-26. Demunging Usenet addresses is real and is worth a few thousand EE, not a round (2026-08-19)

Prompted by C-27: the same block of pool names contains recoverable ones. 35,162 undated candidates
carry a known anti-harvester token (`nospam`, `removethis`, `spamsucks` and 17 others), for example
`nospamciti-link.com` and `undertonenospam.com`. Stripping the token yields **23,028 distinct
candidates, of which 15,062 are already dated in the store**, which is the only class the corroboration
split would admit, since a Usenet address is something a human typed.

So the ceiling is 15,062 domains, and the realised figure is lower again because a recovered pair only
counts where that domain does not already hold that year. **Worth doing and worth nothing like 5%.**
Recorded so it is not rediscovered as a large idea.

### C-25. The research-repository route to a bulk capture census is dry across five registries (2026-08-19)

`repository_ia_capture_census` sits in the triage queue on the reasoning that `dartmouth_nber_captures`
paid 227,273 pairs, so siblings of it might exist. **Searched and empty.** DataCite restricted to
datasets, Zenodo, Harvard Dataverse, OSF and HuggingFace, 15 query phrasings across crawl, hyperlink
graph, capture census and early-web wording, 569 distinct records returned and **not one is an
in-window web corpus.** The nearest misses are a 2020 German academic web crawl, a Common Crawl
language benchmark and a banner-ad study that is itself derived from Wayback snapshots.

This does not close the idea that such a deposit exists somewhere, but it closes the five places where
a deposit of that kind would normally be registered, and it should stop the next agent repeating the
sweep.

### C-24. Edge-year gaps are real, measured, and NOT worth reallocating an engine to (2026-08-18)

**Raised as a question and settled by measurement in the same afternoon, so it never needed an answer
from Ivo.** Recorded because the reasoning is reusable and because the figure moved three times.

The gap engine can only target a year bracketed by two years already held, so **1996 and 2001 were
never targets at all**: they would need 1995 and 2002. That left 6,499,136 slots unqueried, 99.8% of
the 2001 half never asked, against only 285,862 domains ever asked of the archive out of 10,867,530
held. `gaps.py` justified the restriction as "far more speculative" and that had never been measured.

**The rate was measured three times and only the third was right.**

| | method | 2001 | 1996 |
|---|---|--:|--:|
| conditional off 725 journals | given an adjacent CAPTURE | 94.4% | 60.0% |
| pilot against the LIVE edge set | 200 domains | 24.2% | 0.0% |
| **pilot against a FIXED snapshot** | same 200 domains | **59.7%** | **0.0%** |

The first was labelled a ceiling and was one: it is conditional on the archive holding the adjacent
capture, while this population holds its adjacent year from any source, often a registry creation date
for a site never archived. **The second was wrong in a way worth naming, because it looked like the
careful version.** Measuring against the live edge set biases a rate downward by its own success: every
domain where 2001 was found got banked, left the edge set, and was removed from the denominator it had
just satisfied. 24.2% and 59.7% are the same 200 answers.

**And the answer, on the honest rates, is that nothing should move.** Rebuilt with 0.597 and 0.000, the
merged queue gives **9,999 of its best 10,000 rows to bracketed gaps**, which is the ranking working
correctly rather than a disappointment. The edge population is worth 1,597,557 equivalent-English over
6,039,003 targets, 0.264 per query, against about 0.18 for the candidate pool and 1.249 for a bracketed
gap. So it is roughly 1.5x the pool rather than the 4.7x I reported an hour earlier, and there is no
allocation case: the VPS stays on bracketed gaps, the local engine stays on discovery, and the edge
queue is available for whenever the pool runs thin.

**1996 is not a thin edge, it is not an edge at all**: 0 of 186. It is kept in the selector at rate
zero rather than deleted, so one constant revives it if a later pilot ever measures it above zero.

Full working in ADR-006, which carries all three measurements and the correction between them.

### C-23. The four new deliverables are enforced by the build, not by a checklist (2026-08-18)

Ding added four requirements for every future submission on 2026-08-17, quoted in full in
`brief_amendments.md` and called **D1** to **D4** from now on: the runnable code, a concise experience
summary, the merge and deduplication arithmetic against the latest baseline, and the metric
calculation with its explanation.

**Mechanical, except for one judgement.** The judgement is that they became **checks 5 to 8 in
`verify_delivery.sh`** rather than a section of the README. This project has one expensive proof that a
requirement living only in prose gets shipped unmet: the phase-5 build filtered provenance to save
429 MB and left 11,316,960 of 16,619,832 assignments citing evidence no longer in the archive, and all
three checks that existed passed because every one read the additions manifest and none read the
parquet. `package_delivery.sh` now also refuses to build if the merge reconciliation fails.

**The one that was real work is D3.** He has always done the merge on his own side and shipped his
audit of it; he now wants ours too, so the two can be diffed. `scripts/merge_against_baseline.py`
therefore uses **his column names unchanged**, counts the raw lowercased line as he does rather than
the registrable domain, and scores every file with **his** calculator rather than ours. First run: 22
of 22 reconciliation checks pass, reproducing his published baseline of 22,491,418 records and
12,077,095.5404 equivalent-English to the digit.

Two of those checks compare a freshly measured baseline against `src/ark/baseline.py`, so a round
measured against a release he has already replaced now fails loudly. That drift went unnoticed for five
days in August 2026 and overstated net-new by 151,949 records he had already credited.

Nothing here needs you. Working: `notes.md`, 2026-08-18.

### C-22. The current baseline is `merged260817-2`, and a round now records what he ACCEPTED (2026-08-18)

Mechanical rather than discretionary, and recorded because every figure depends on it. `baseline.py`
carries the marker, his record count of 22,491,418 and the six per-year equivalent-English totals,
measured by running his own calculator over each file. Those six sum to **12,077,095.5404**, which is
the total he published, to the digit, so the numbers in that file are demonstrably his rather than ours.
4,220,591 year rows added under the new marker, and the collectors were requeued against it the same
night so they stop asking about domains the corpus already holds.

**The discretionary part is one line.** `SUBMITTED_ROUNDS` now stores the figure he **accepted** for each
round rather than the one it was submitted with. Phase 5 went out at 2,838,715 records and 1,697,224.86
EE and was credited 2,608,322 and 1,566,229.7613; the 230,393 difference had reached his interim
`merged260817` by another route. Quoting the submitted figure would inflate the cumulative by exactly
that overlap, and the overlap is only ever visible in his reply, never in our store.

### C-21. The promotion tranche is banked, at 88% of its quoted figure (2026-08-16)

You authorised it. Re-priced against the new baseline **before** writing anything, which mattered: it
was 106,604 pairs / 69,337.4 EE against `merged260810` and **94,051 pairs / 61,196.7 EE** against
`merged260815`. Banked in eight ingests; the year rows sum to 94,051 and reconcile to the projection
exactly. All nine integrity invariants pass afterwards, including `additions_not_double_counted`, which
is the one that would fire if any promoted pair were already in his files.

Two effects pulled opposite ways and only one is obvious: a larger baseline **removes** promoted pairs by
holding them, and **admits** more, because the corroboration split asks whether some other source places
the domain in an annual file and four million new rows place a great many more. The net was a loss.

`ukwa_link_target`, `uucp_map_mention` and `page_expansion` stay excluded: a link-graph edge cannot date
its target and corroboration cannot rescue that. Working: `notes.md`, 2026-08-16.

### C-20. The baseline moved to `merged260815`, loaded and pointed at (2026-08-16) [SUPERSEDED BY C-22]

Mechanical rather than discretionary, and recorded because every figure depends on it. `baseline.py`
carries the marker, the reviewer's record count and the six per-year equivalent-English totals, the last
measured by running his calculator over each file rather than by carrying our own increments forward,
since this release came from another contributor's merge. 4,006,500 year rows added under the new marker.

### C-19. Netcraft survey listings stay candidate-only: your condition was tested and failed (2026-08-12)

You answered the one open request conditionally: the domains do not look human typed to you, and *if you
are sure of how these lists came about and that they hold domains which were actually active during the
year they were surveyed, then they can be master evidence*. **You were right about the first half and it
was the second that killed it.**

Reading the archived pages settles provenance: a machine-generated alphabetical dump of every hostname in
Netcraft's database matching the search word, no prose, no author, no per-item date. Nobody typed these
hostnames, so the corroboration split was never the right question and the `typed` classification that
this lead was originally rejected under was simply wrong.

Contemporaneity is the part that failed. A name printed on a page captured in 1999 should behave like a
site that was live in 1999, and against two controls it does not:

| instrument | netcraft | live in 1999 by an archive capture | undated pool, no claim to any year |
|---|--:|--:|--:|
| earliest archive capture 1999 or earlier | 9.4% (127) | 100% by construction | 10.9% (12,836) |
| still registered today | 52.2% (230) | 94.3% (230) | n/a |
| registered continuously since 1999 or earlier | 25.0% (120) | 74.7% (217) | 16.6% (413,942) |

The first row decides it and is the only one free of survivorship bias: both populations were queried by
the same engine against the same archive in the same days, and **Netcraft's names are no likelier to have
been captured by 1999 than names with no claim to 1999 at all.** Registry dates cannot settle it either
way, because a 1999 domain that lapsed and was re-registered reports the later date; twelve sampled names
created between 2003 and 2026 were each verified as genuinely printed on the archived 1999 page, so the
extraction is faithful and it is the inference from listing to liveness that fails.

**Cost of refusing: close to nothing.** The forgone reading was 8,741 pairs and 5,708.4
equivalent-English. All 13,078 names were banked as candidates on 11 August and the engine has been
querying them since; 127 are already dated on their own capture evidence, which needs no approval and
does not ask anyone to trust the listing. Working in `approved-sources-list.md` and `notes.md`
2026-08-12.

### C-18. The hit-rate fallback gains the grain it was missing, the TLD (2026-08-11)

Mine to decide, recorded so you can object. It completes C-17, which was only half a fix.

The pool score is `P(hit) x English share`, and `P(hit)` coarsened from the exact (source, TLD) cell
straight to the source average. **It skipped the TLD, which is the grain that already knew.** `.mil` was on
record at **0.000 over 1,372 answers** and `.gov` at 0.000 over 394, while `.com` sits at 0.898 and `.net`
at 0.915: a 900x spread, far wider than across sources. So an unmeasured `.mil` cell inherited a source
average and English share put 2,675 of them at the head. **That was not a missing measurement, it was a
measurement never read.**

The chain is now (source, TLD), then the **lower** of the TLD and source rates, then pool-wide. Lower is
the conservative reading: an unmeasured cell must not outrank a well-measured one. A TLD nothing has
answered still gets the pool rate rather than zero, since querying is the only way it earns a first
measurement.

Measured after the rebuild: the first 3,000 went from 2,675 `.mil` to 100% `.com`; expected value per query
rose from 0.6515 to 0.6877 over the best 50,000; pool targets in that head went from 8,798 to 24,726, so
discovery now competes with gap-filling at the top. The whole-queue estimate **fell** from 578,632 to
545,879 EE, which is the point: the old number was inflated by optimism.

**Stated plainly because it matters:** the head's sources all have unmeasured `.com` cells, so they inherit
`.com`'s good average. The optimism moved axis rather than disappearing. The difference from `.mil` is that
these have *no* evidence rather than contradicting evidence, one 600-domain batch measures each of them, and
the yield check now reports within a batch whether the bet paid.


### C-17. The pool queue is ranked by a measured plausibility factor, not by English share alone (2026-08-11)

Mine to decide under your rule that hypotheses and judgements like this are the agent's; recorded so you
can object. **It corrects damage I caused this afternoon.**

The rebuild I ran at 15:53 put **2,675 `.mil` names in the queue's first 3,000**, and the local engine then
spent two batches and **1,200 archive queries finding exactly zero in-window captures**. 371,465 `.gov` and
`.mil` names stood in front of the first real domain, which at the measured rate is about **25 days of the
discovery engine producing nothing**.

The cause is the one this project keeps paying for, and the RDAP builder's own docstring names it: ranking
by expected equivalent-English needs a probability, and where none is measured the score fell back to a
pool-wide rate, so `0.9825 x a fabricated name` still sorted to the top. C-2 fixed it for RDAP by excluding
`.gov` and `.mil` by hand; the CDX queue never got that judgement.

Fixed with the measurement rather than a list, because a hand-maintained exclusion list would have covered
those two and rotted. `dated / (dated + pool)` per TLD separates them cleanly and updates itself:
`.com` 0.78 and `.uk` 0.76 against `.edu` 0.029, `.gov` 0.0055 and `.mil` 0.00038. It multiplies the pool
score, so `.mil` drops about 2,000x with no TLD named anywhere, and the tiny ccTLDs that also littered the
head land in between, which is right: unproven is not impossible. Reverse-DNS zones are excluded outright,
since that is a fact about the namespace rather than a judgement about the corpus.

After the rebuild the head is `.za`, `.nz` and `.uk`, and the first 50,000 targets contain zero `.gov`,
`.mil` or reverse-DNS names. The engine picks the file up at its next dispatch, so nothing was restarted.


### C-16. One surface asks you for things, and it is this file -> [ADR-005](ADRs.md) (2026-08-11)

Your instruction: "Everything I have to sign-off should be in one place, so I know about it. That was
key-decisions, it pointed to ADRs if necessary." Three things had drifted out of it, and the third is
the one that proves the point, because **you did not know it existed**.

1. **Notes sign-off, removed.** 37 entries each ended `Signed off by Ivo: pending`, asking for a
   countersignature on the agent's own working. Past entries are append-only history and stay as
   written; no new entry carries it, and `CLAUDE.md` no longer asks for it.
2. **`open-approvals.md` renamed to `approved-sources-list.md`**, and a `pending` class in it is now
   mirrored here automatically, at the moment the request is written and again on any cycle that
   finds one unsurfaced. A test over both live files fails if a pending class is not named here, so
   the guarantee is enforced rather than remembered.
3. **Hypotheses are mine to settle.** The ledger's unfinished leads were being reported as needing
   your judgement, which is how you came to be asked about five things you had never heard of. They
   are now reported as the agent's own work queue: screened, priced, and decided, with only an
   outcome worth overruling arriving here.

The shape you described is preserved exactly: this file is the surface, and it points at an ADR when
the reasoning is structural.


### C-15. A declarative *probe*, and bespoke *collectors* -> [ADR-004](ADRs.md) (2026-08-11)

Ivo asked for a declarative fetcher, as one of three fixes for the harness sitting idle. Adopted for
**measuring** a source and refused for **ingesting** one, which is the half worth arguing about.
`just probe probes/x.toml` turns a URL into a priceable journal from a TOML description with no Python
written, and `just price` then reports the net-new figure. Its output has no ingest spec, so there is no
path by which a probe can date a year: the safety is an absence rather than a rule, the same trick C-13
used.

The reason for the split is that of the last four sources considered, **two were rejected on the number
and never needed a parser at all**, so the expensive step was the measurement and not the code. A
declarative path to master evidence was refused because a parser's value is in refusals specific to its
document, and because cheap plus self-dating is precisely the combination that contaminates.

Validated against a known answer rather than a plausible one: the first spec written was a self-test
against the already-ingested UDRP dockets, and **seven lines of TOML reproduced the 186-line collector's
8,923 records exactly**, with nothing in either set the other missed.


### C-14. The harness wakes every 15 minutes, and "the collectors are running" is not the agent being busy (2026-08-11)

Ivo's instruction, after watching the harness sit idle: cron every 15 minutes, plus a `CLAUDE.md` section
governing what a cron-started session does. Adopted with the ordering he sketched and one definition added,
which is the load-bearing part: **a wake that finds healthy collectors and an idle agent is the normal
case, not an exception**, so the wake asks "is anything stopped" first, `just cycle` is the one-shot that
answers it, and "everything is fine" is an explicitly valid outcome so a wake has no reason to invent work.

Two supporting fixes went in with it. The loop now rebuilds a derived list it finds stale instead of only
reporting it. And the staleness test compares each list against the mark that actually invalidates it,
newest pairs for the gap queue and newest candidates for the pool queue, rather than against the baseline
release; on its first run that found three stale lists the old check called fine, which is the idleness
Ivo saw from the outside.

**One rule came out of getting this wrong in the same sitting.** I read `cdx_pool.log`, found it four days
old, concluded the local engine was dead, and killed a collector that had been working the pool healthily
since 11:10 that morning under an invented third log prefix. So: **ask the process table, never a log
file**, and `cdx_pool` and `cdx_gap` are the only prefixes that population may use.


### C-13. A source class may not date a year until a human classifies it -> [ADR-003](ADRs.md) (2026-08-11)

Ivo's proposal, adopted with one refinement. `docs/approved-sources-list.md` holds one `Decision:` line per
(source, evidence type) and **`ark ingest` enforces it** before opening the database. The refinement: the
quarantine is **outside** the store rather than a state inside it, because collectors already write
journals and never open the database, so an unapproved source cannot contaminate anything, having never
been written. Requests are built from a seeded-random sample with live links, the measured figures and
the counterfactual, so the reviewer checks external evidence instead of reading the agent's argument.
Candidate-only evidence is ungated: collection never waits on a human, promotion always does.


### C-12. UDRP proceedings are master `artifact_listing` -> [ADR-002](ADRs.md) (2026-08-11)

Was O-6. Ivo: "Treated as master artifact-listing sounds fine to me, just make sure to document and
reason about the decision and ingest carefully as you described." Reasoning, the argument against, the
three mitigations and the limitations are in **ADR-002**. Worth **7,714 net-new pairs and 4,708.9
equivalent-English** rather than 1,471 and 914.1 under the split reading.

### C-11. The write-lock contention: no structural change, an allocation rule instead -> [ADR-001](ADRs.md) (2026-08-11)

Was O-5. Ivo: "if a solution with no technical debt exists, adopt it, if not, try to preserve the current
structure and allocate the time between locks, based on who is most likely to contribute most net-new EE
domains."

**As written that evening: no debt-free fix was available, because the cause was not known.** Two plausible
causes were measured and both eliminated, the structure was preserved, the seed path was instrumented, and
the allocation rule you asked for was put in force.

**Resolved the same evening, and the first sentence above no longer holds.** The instrumentation ran on a
13,078-name seed and one phase was 1,207 of 1,208.6 seconds: `insert_candidates`. So the debt-free fix did
exist, it was the idiom `bulk.py` already used, and `add_candidates` now inserts set-wise from an Arrow
table: **13.47 s becomes 0.05 s, 267x, with identical results.** The row-at-a-time insert was the
hypothesis eliminated *first*, wrongly, because switching it to `executemany` looked like batching and
`executemany` is N statements rather than a batch. A third guess of mine, per-row autocommit, was tested
and refuted at 12.03 s against 11.88 s.

Separately, the contention itself was 636 `ark ingest` invocations per pass in the ingest loop, one per
file, which measured **89% write-lock occupancy and is now 0%**. Both fixes and all the measurements are in
**ADR-001**, whose status is now Accepted rather than Open. The allocation rule stays in force and is now
enforced in code by asymmetric lock patience rather than stated in prose, but note its justification
changed: interrupting a seed is safe because the window is negligible, not because partial inserts
survive. Full reasoning and the
four rejected alternatives are in **ADR-001**.

### C-10. The two populations go to two machines, and it supersedes C-6 (2026-08-11)

**Ivo's design, and he is right about the part I had corrected.** The VPS works a pool of **pure
bracketed gaps**: a missing year Y where Y-1 and Y+1 are already held. The local engine works the
**candidate pool**, domains held with no year at all, beside the discovery loop that keeps feeding it.

**Why sorting by TLD English share is correct here and wrong for the other pool**, which is the
sharpening my C-5 note missed. A gap query answers 96.0% to 97.5% of the time and that rate is
effectively flat across TLDs, so with the probability factor near 1 and uniform, expected value
collapses to share times the years one query can fill. The candidate pool is the opposite: its hit rate
runs from 36.9% for a name merely mentioned in Usenet text to 90.6% for a link harvested off an
archived page, so there the share must be multiplied by a *measured* rate or `.au` sorts to the top
again. Same formula, and only one of the two populations lets you drop a factor.

**It also maps onto the two outcomes the reviewer asked to keep separate**, which is a good sign:
a gap hit adds a **pair** and never a domain, so the VPS is the completeness baseline; a pool hit makes
a name **net-new**, so the local engine is the discovery half that he asked to be prioritised. The
machine allocation and the reporting split are now the same distinction.

**Two consequences.** Gap targets change slowly, so the VPS needs a refresh rarely rather than
periodically, which was the weakest part of C-5. And **this supersedes C-6**: the local CDX engine goes
back on, but pointed at the discovery pool rather than at a mixed queue, and driven by the loop.

Implemented as `build_query_queue.py --population gap|pool --out PATH`, so the ranking, the era gate
and the measured multipliers are the ones already in use rather than a second implementation.

### C-9. The report leads with the method; the numbers stay at the top as the result (2026-08-11)

Ivo: "the numbers can still go at the top as the 'result', but the focus should be on the method, the
harness, yes." So the five fields open the report, and the body is about how they were found. Two
sources *closed* on measurement become results rather than omissions, which is what SPEC IX asks for
and what a volume framing cannot express.

### C-8. Go back to `.org`, and to previously unavailable sources generally (2026-08-11)

Ivo: "going back to previously unavailable sources is part of the task and what has repeatedly proved
worth it." Correct, and it is already the documented pattern rather than a new idea: feedback section 4
asks for blocked sources to be revisited, and the register's own best example is the Australian Web
Archive, where one endpoint was dead and the other answered normally once someone checked the second
host. **Standing rule from now on: a source closed on *availability* is a source to re-probe, and only
a source closed on *measurement* stays closed.** The two verdict classes are already distinguishable in
`sources.md`, so the screener can say which kind it hit.

### C-7. Ding's research vision logged, and it is background rather than specification (2026-08-11)

His AI4EconFinance / Internet Digital Ark and Digital Archaeology email to Giesecke is now in
`private/personal-context.md` under its own heading, marked FYI. Ivo: "our task specification comes
from elsewhere", meaning `SPEC.md` as amended. Two things in it do bear on method: temporal fidelity
is the point rather than record count, which is why the per-year rule is the deliverable's core
property; and "AI agents that independently discover hypotheses, collect and synthesize evidence"
describes this round's harness, so the harness is on-vision.

### C-6. Local CDX engine stays off (2026-08-11) [SUPERSEDED BY C-10 THE SAME DAY]

Was O-1. Ivo's call: discovery work matters more than another crawl client on this machine. Recorded so
the agent does not quietly reverse it when the queue looks tempting.

### C-5. VPS is the unattended safety baseline, with its queue refreshed periodically (2026-08-11)

Ivo's rule, adopted: the VPS keeps filling in domain-years unattended as steady output, its candidate
pool is refreshed periodically rather than once, and the refresh happens whenever the VPN is up. Added
as a periodic task.

**One correction to the wording, and it matters because the project has already paid for it.** The
instruction was to sort "by the most promising TLDs in terms of EE". Sorting by TLD English share is
what put `.au` first in the whole queue on a 0.9904 share for zero in-window dates, and spent 1,709
queries on a 97.2%-English TLD for five hits. `build_query_queue.py` already sorts by **expected
equivalent-English per query**, which is the share multiplied by a *measured* hit rate, and that is
the ordering the refresh will keep. Same intent, and the multiplier that stops it going wrong.

### C-4. Current state becomes generated, and the handoff retires (2026-08-11)

`phase5-handoff.md` is a hand-written snapshot of current state, which is the one category of memory
that cannot be hand-written: three of its claims were disproved within a day. State moves to a
generated `ROUND.md` with a guard against hand edits, the handoff moves to `legacy/docs/`.
See notes.md, 2026-08-11.

### C-3. Two sources closed on measurement (2026-08-10)

Linux Software Map: 86 net-new pairs, 37.3 EE after the corroboration split, 94.7% already held. Other
defacement mirrors: no sibling survives on archive.org or GitHub. Both are in the rejected register,
so the screener now catches them.

### C-2. `.gov` and `.mil` excluded from RDAP ranking on a fabrication test (2026-08-10)

182 and 2,624 pool names per dated name, against 0.3 for `.com` and `.uk`. Reported as a warning
rather than enforced, since which TLDs to drop is a judgement.

### C-1. VPS deadline extended to 2026-08-31T12:00Z on a freshly rebuilt shard (2026-08-10)

The old shard predated `merged260810` and 28% of the current best-10,000 head was invisible to it.
