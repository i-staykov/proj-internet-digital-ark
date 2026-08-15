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

### Bank the 106,604 promoted Usenet mentions? Worth 1.11 points, free, one command

**The single largest thing available, and it needs no download, no request and no new source class.**
Re-running the corroboration split against today's store admits mentions that failed it when written,
because the engines have since dated those domains. Built and tested:
`scripts/build_promotion_journals.py --tag T --write`, then the `ark ingest` lines it prints.

- **106,604 pairs, 69,337.4 EE, +1.1136 points.** Round goes from ~2.09% to ~3.2%.
- Registry-contradicted pairs already dropped (35% of the raw set, against 16.5% for pairs the store
  already accepts). Two positive controls: mention years land inside the domain's own capture span
  **5.52x** over chance, and within a year of a real capture 68.5% against a 22.1% null.
- **I have not run it**: 106,604 pairs entering the annual files on typed evidence is your call.

Working: `notes.md`, 2026-08-15 entries. My recommendation is to bank it.

### 5% is a hard requirement and the round will land near 2.3%

Status, not a question. Recorded in `brief_amendments.md`. 5% is 311,319.32 EE; the round holds
~130,000 and banks **413 EE/h measured over 24h**, so Sunday lands **~2.30%**, or **~3.44%** with the
promotion above.

Everything that could have closed the gap was searched and closed on measurement: zone files, research
crawl corpora, national archives, bulk archive indexes, RDAP headroom (0.107 points, not the 1.47 once
carried), and the whole 49-source triage queue (**9.19% of the deficit**). There is no route I know of.
The report states the shortfall and the measured reason.

### The local engine now costs 3 throttled requests per answer, for 0.085 points

Not blocking; it keeps running unless you say otherwise. Newest batch: 600 queries, **1,830 throttles,
188 failures**, ~2,430 HTTP requests for 412 answers. Candidates are fine (75.7% of answered carry a
capture), so this is citizenship, not tuning, and every technical lever is tested and closed. Its whole
remaining contribution is **~5,300 EE, 0.085 points**. The VPS is on another host at 84.5% and unaffected.

### May we query Nominet in bulk for the .uk pool?

`.uk` lands an in-window date on **30.6%** of queries at weight 0.9813, six times `.org`, over ~54,000
unasked names: about **16,000 EE**. I stopped after 140 queries because Nominet's own RDAP terms forbid
high-volume automated querying and re-use, and `sources.md` records it refusing us three times in
fourteen queries. Options: leave it (current behaviour), ask them (I draft, you send), or tell me to
sweep slowly anyway.

### May I write to a US federal agency on the project's behalf?

USAC's portal serves only the last ten years and says to email `opendata@usac.org` for older records.
`usac_erate_form471_contact_email_1998_2001` aims at the measured `.us` gap (18,300 in-window `.us`
against 3,239,423 `.com`). **Outward-facing in your name, so I will not do it without your word**; if
yes, I draft and you send. Positive control already measured on the published years.

### Triage the newly found sources: 49 found, none priced

A counter, not a request, by your instruction of 2026-08-15: you review it when something reaches 5%.
Measured whole, it covers **9.19% of the deficit**, so nothing here is urgent and reviewing it would not
change Sunday. It keeps growing for the rounds after this one.


---

## CLOSED

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
