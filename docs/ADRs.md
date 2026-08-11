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
