# Architecture decision records

**What belongs here and what does not.** `docs/notes.md` is the dated log of every decision, and it is
long by design. This file holds only the few decisions with **structural** impact: a change to the
evidence taxonomy, to the store's shape, to how the machines are allocated, or to a write path every
route depends on. Each record states the question, what was measured, what was decided, and **what was
rejected and why**, so a later session can disagree with the reasoning rather than rediscover it.

**How it links to the other logs.** `docs/key-decisions.md` is the short review surface and names the
ADR for anything structural. `notes.md` carries the day-to-day working. An ADR is the durable answer.

**Status values.** `Accepted` means it is in force. `Superseded by ADR-N` means read that one instead.
`Open` means the question is live and the record exists so the next session does not start from zero.

---

## ADR-001. The store's single write lock, and the seed that holds it for half an hour

**Date** 2026-08-11. **Status** Open, with an interim rule in force.

### The question

DuckDB permits many readers **or** one writer. Until today nothing contended for the store: collectors
write journals and never open it, and ingests ran when a human was watching. Today three things want it
continuously, which is new: the ingest loop every fifteen minutes, and two collectors whose output that
loop folds in.

Against that, `ark seed` held the write lock for **26 minutes for 6,079 names** and **33 minutes for
35,391**, and while a writer holds the lock every reader is blocked. During that window the pricer, the
state generator and the residual auditor all stalled. So the question is whether the seeding path needs
restructuring, and if so how.

### What was measured, including two wrong answers

**First hypothesis: the row-at-a-time insert.** `seed_from_file` called `add_candidate` in a Python loop,
so 29,432 names became 29,432 single-row `INSERT`s into a columnar store. That is real, and it was
batched into one `executemany` as `db.add_candidates`. **It was not the cause**: the same seed then held
the lock for 33 minutes anyway.

**Second hypothesis: the classification query.** `_CLASSIFY_SQL` evaluates a correlated `EXISTS` per
candidate name against `evidence`, which is 53.9 million rows, and that looked like the obvious cost.
**Measured against the real store it is 0.33 s for 3,000 names.** A hand-written semi-join replacement
measured **1.30 s for the same input, four times slower**, so the existing query is already the better
formulation and DuckDB is planning it as a hash semi-join rather than 3,000 probes.

**So the cause is unidentified.** Both plausible candidates are eliminated by measurement. What remains
untested: the SQLite `enqueue` of several thousand rows into a 358 MB queue file, transaction commit and
WAL checkpoint behaviour on an 8 GB store, and interaction with the ingest loop writing concurrently.

### What was decided

1. **No structural change.** Rewriting a write path that every seeding route depends on, without knowing
   which line is slow, would be a change made on a guess. Two guesses have already been wrong here.
2. **The seed path is instrumented instead.** `seed_from_file` now logs elapsed seconds per phase:
   read-and-canonicalise, classify, insert, enqueue. The next occurrence produces a measurement rather
   than a third hypothesis. This is observability, not debt: four timing marks and one log line.
3. **The batched insert stays.** It is correct, tested, and removes a redundant second `to_registrable`
   call per name. Its justification is now "it is the right shape" rather than "it fixed the slowness",
   which it did not.
4. **An allocation rule, which is the operative decision.** When jobs contend for the write lock,
   **priority follows expected net-new equivalent-English**. Concretely:
   - ingesting a collector's finished journal wins: it banks work already paid for;
   - pricing and measurement win over seeding: they decide where the next hours go;
   - **seeding yields**, because a candidate claims nothing until something dates it, and the two seeds
     run today were measured at an expectation near zero (PANDORA) or are already banked as candidates
     by a cheaper route (UDRP);
   - a seed that is blocking anything valuable is interrupted rather than waited out. This is safe:
     inserts autocommit, so a stopped seed keeps what it wrote and `INSERT OR IGNORE` makes a re-run
     additive.

### What was rejected, and why

- **A second store, or read replicas.** Solves the contention and introduces two sources of truth for
  the evidence graph, which is the one thing this project's design refuses. The provenance export, the
  integrity gate and tier-2 reproduction all assume one store.
- **Moving the candidate pool to SQLite.** The pool is queried by joins against `evidence` and
  `domain_year` constantly, so splitting it across engines would turn cheap joins into application-level
  work.
- **A write queue in front of the store.** Real technical debt: a new component to keep correct, and it
  would hide contention rather than remove it.
- **Longer patience everywhere.** Already done where it belongs (the read-only tools wait 15 minutes),
  but patience is not a fix: it makes a reader wait quietly instead of failing loudly.

### Consequence to watch

The interim rule makes seeding the thing that always yields, which is right while seeds are worth
nothing and wrong the moment a seed feeds a route that pays. The RDAP pool and the CDX pool are both fed
by seeding, so if the discovery loop starts converting candidates at a good rate, this ordering needs
revisiting rather than reapplying.

---

## ADR-002. UDRP dispute proceedings are master `artifact_listing`, not a split source

**Date** 2026-08-11. **Status** Accepted, on Ivo's decision.

### The question

ICANN publishes a consolidated table of domain-name dispute proceedings across all five providers that
heard cases in 1996-2001, with an explicit commencement date and the disputed name in its own column.
Measured against the live store: 5,306 in-window proceedings, 8,800 distinct (domain, year) pairs over
8,769 domains, of which **only 1,086 are already held**. 87.7% absent is the highest share of any source
measured on this project.

Which evidence class applies decides what it is worth, and the difference is 5.5x:

| reading | net-new pairs | equivalent-English | mean weight |
|---|--:|--:|--:|
| `artifact_listing`, master, self-dating | **7,714** | **4,708.9** | 0.6214 |
| `dated_directory`, taking the corroboration split | 1,471 | 914.1 | 0.6214 |

### Why `artifact_listing`

**The precedent is exact.** `attrition_defacement` is already `artifact_listing` on identical logic: a
defaced host was serving on the day the mirror recorded it, so the record is contemporaneous evidence of
existence with the date printed in it. A proceeding exists only because the domain was registered and a
complaint was filed against it, and the provider verified the registration with the registrar. The claim
is the same shape and the authority is stronger.

**The domain is in a structured column, not in prose.** This is the property the corroboration split
exists to compensate for, and it is absent here. The split was introduced because a hostname a human
typed into a Usenet post carries transcription risk, and it is what makes `usenet_bare` safe to widen.
Tucows' `creator` field was trusted on the same reasoning where its neighbours were not. A published
docket's domain column is that kind of field.

**It does not depend on a crawl.** The reason this source matters at all is that a dispute record
attests existence without anyone having visited the site, which is precisely why 1996-1997 are hard.
Sending it through a split that requires another source to have already seen the domain would discard
exactly the names no other source has, which is the population worth having: 87.7% of what it names.

### The argument against, which is real

Self-dating means **no wall behind the extraction**: a bad match becomes a master claim rather than a
candidate. Three mitigations, all in place before the figure was believed:

1. **The extraction reads one table cell**, not the text between two case numbers. The first version did
   the latter and swept in `www3.wipo.int` from the page furniture.
2. **A row without a proceeding number is refused**, because the number is what makes a row auditable,
   and the evidence value carries `UDRP <number> commenced <date>` so the integrity gate can check that
   the value names the year it is filed under.
3. **Eight tests pin what it refuses**, not only what it accepts, which is the right emphasis for a
   source with no split behind it.

### One figure that must not be misread

The pricer's typo bound reports 46.4% of net-new names within one edit of a name already held. On every
other source that is a contamination estimate. **Here it measures the signal**: a typosquat is one edit
from a famous name by construction. This is the only source measured on this project where a high
edit-distance score is evidence the extraction is finding the right thing, and a future session applying
the usual reading would reject a good source.

### Limitations carried forward

ICANN's own page calls itself "an incomplete list of UDRP proceedings", so the figure is a **floor**, not
a census: the providers' own search tools hold cases this table omits. The lineage is `dispute_docket`,
its own family, so a pair it confirms alongside an RDAP creation date is genuine cross-lineage
corroboration rather than one organisation agreeing with itself.

---

## ADR-003. A source class may not date a year until a human classifies it

**Date** 2026-08-11. **Status** Accepted, on Ivo's proposal.

### The question

The harness can propose a source, screen it against the closed register, fetch it and price it against
the live store without help. It cannot decide whether that source's records belong in the annual files,
because that is a judgement about **what counts as proof** rather than a measurement.

Until today that judgement happened by email. UDRP went from "priced" to "ingested as master evidence"
on one exchange, and the reasoning for it lived in an ADR that only the agent had read. That does not
scale to an unattended run, and more importantly it puts the least trustworthy artifact in the
repository, **an agent arguing that its own find is master evidence**, on the critical path.

### What was decided

**A gate, not a convention.** `docs/open-approvals.md` holds one `Decision:` line per
(source name, evidence type). `ark ingest` refuses any master-eligible class whose decision is `pending`,
`rejected` or absent, and it refuses **before opening the database** so an unapproved ingest does not
even take the write lock. `src/ark/approvals.py` is the enforcement and `ingest_files` is the choke point
every caller passes through.

**Four decisions, and `rejected` binds.** `pending` refuses, `master` admits, `candidate-only` admits the
source while forbidding it from dating a year, and `rejected` refuses and stops the request generator
re-opening it. An agent that forgets a rejection re-proposes it a week later, which is the same failure
the closed register exists to prevent for sources.

**Candidate-only evidence is deliberately ungated.** It can never date a year, the reviewer asked for the
pool to be as large as practicable, and gating it would stall collection for no gain. So **collection
never waits on a human and promotion always does**, which is the property that makes the queue safe to
leave unattended.

### One refinement on the proposal, and it matters

Ivo's sketch had the harness collecting `master_candidates` into a quarantined state. **The quarantine is
outside the store instead.** Collectors already write journals and never open the database, so
"collected but unclassified" needs no new state at all: the journal sits on disk and the gate refuses the
ingest. That is strictly stronger, because an unapproved source **cannot contaminate anything, having
never been written**, rather than depending on every future query to respect a marker. It is also less
code and adds no schema.

### What makes a request decidable in two minutes

The reader does not trust the agent's prose, and should not. So `scripts/request_approval.py` builds a
request almost entirely from checkable things:

- **a seeded-random sample of real records, each with a live link.** Seeded, and the seed printed, so the
  sample is reproducible and **was not chosen by the agent**. Given the choice the agent would pick
  flattering examples. WIPO decisions get a per-case URL composed from the case number, since a link to
  an index proves nothing; NAF rows honestly fall back to the index because its ids are opaque.
- **the measured figures**, produced by a program against the live store, including the share absent.
- **the counterfactual**: what the source is worth under `master`, under the split, and under
  `candidate-only`, so the stake is visible before the decision rather than after.
- **the nearest already-closed family** from the register, since the strongest reason to refuse is usually
  that something of this shape has already failed on measurement.
- **reasons to refuse, written by the agent against its own request.**

The single judgement it does ask the agent for is the **dating claim**, one sentence on what dates one
item, and it is labelled as the agent's claim rather than presented as fact.

### What was rejected, and why

- **Quarantine inside the store**, as above: weaker and more code.
- **Per-record approval.** Approving 8,972 rows individually is not a review, it is a rubber stamp. The
  class is the right granularity, and a **material change to the extraction should re-open it**, since
  that is what went wrong with the Microsoft Bookshelf ISO: self-dating plus a loose extraction would
  have turned binary noise into master claims.
- **Trusting the ADR as the record.** An ADR is the agent's reasoning. The gate reads a decision line a
  human wrote, and the two are deliberately separate artifacts.
- **Gating candidate-only evidence too.** Consistent, and it would stall collection to protect nothing.

### Consequences, including the awkward one

Everything already in the store was grandfathered, and the authority is cited per entry: the reviewer
merging and crediting the round that contained it, or Ivo classifying it by name and date. That is real
approval rather than the agent approving its own past work, but it is worth naming plainly that 24 of the
25 classes were approved retrospectively in one sitting.

A test asserts that **every master-eligible spec has an entry**, so adding a source without classifying
it fails in the suite rather than at three in the morning in an unattended run. The unit-test fixture
relaxes the gate, because unit tests build specs with invented source names, so `tests/test_approvals.py`
is the only place the gate is genuinely exercised and it tests the gate rather than the convention.
