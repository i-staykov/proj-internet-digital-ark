# Design documentation

**Why the code is shaped the way it is.** `README.md` says what to run and [report.md](report.md)
says what came out; this file holds the reasoning that neither of those should carry. It is
deliberately meta-level: anything a docstring or a comment already says belongs there, not here.

Related documents: [SPEC.md](SPEC.md) is the reviewer's brief and [brief_amendments.md](brief_amendments.md)
is what he has changed since; [sources.md](sources.md) documents each source individually,
[discovery.md](discovery.md) is the method for pricing a new one, and [notes.md](notes.md) is the dated
decision log.

---

## 1. The one idea the pipeline is built on

A domain name in an annual file is a **claim about a year**, and every claim must name the observation
that supports it. Everything else follows from taking that literally.

`domain_year.evidence_id` is `NOT NULL` and is a foreign key to a specific row in `evidence`. There is
no code path that writes a year assignment without one, because the schema will not accept it. This is
the **evidence wall**: it makes the property structural rather than a convention that erodes.

Evidence types are split in two:

- **master-eligible**, meaning the observation fixes a year: an archive capture timestamp, a dated
  directory or survey artifact, a registry creation date, the baseline's own prior evidence.
- **candidate-only**, meaning the observation shows a name exists but says nothing about when: a link
  from another page, a hostname in a seed list.

`assign_year` refuses candidate-only evidence. A name with candidate-only evidence goes to the
**candidate pool** and stays out of the annual files until something dates it. The pool is not a
waiting room for rejects; it is where the honest answer "this exists, the year is unknown" lives.

**Why a separate pool rather than a confidence score.** A score invites a threshold, a threshold
invites tuning, and tuning a threshold against a target count is how a collection stops being
evidence-backed. Two bins with a rule between them cannot be tuned.

---

## 2. Collectors write journals, not evidence

Every network stage (`ark cdx`, `ark rdap`, `ark download`, `ark lang`) writes a gzipped JSON Lines
**journal** of raw responses and touches no database. A later `ark ingest` turns journals into
evidence.

Three properties come from that one decision:

- **A long collection never holds the store's write lock**, so hours of crawling coexist with
  ingests, exports and reports.
- **Every network stage replays offline.** Tier 3 reproduction re-derives evidence from bytes on disk
  rather than from a live service whose answers have changed since.
- **A parsing bug is recoverable.** The expensive part is the request. If extraction was wrong, fix
  the extractor and re-ingest; nothing has to be re-fetched.

A running collector writes `<journal>.jsonl.gz.part` and renames on exit, including on Ctrl-C and
`kill`, so an ingest glob never picks up a half-written file. A content-hash ledger records what has
been ingested, so re-running an ingest is a no-op rather than a duplication.

**The failure this design has actually had:** a wrapper script discarded `ark ingest`'s exit status
and marked 92 archives done after a lock failure, which silently dropped their evidence. The ledger
was right; the caller was not. Scripts that mark work done now check the status they wrap.

---

## 3. Rate governance, and what the archive actually limits

`web.archive.org` is the binding resource for this project, and it has refused service three times.
The `RateGovernor` eases its delay down while responses are healthy and backs off on 429, 503 and 504,
honouring `Retry-After`. `--min-delay` is a floor it may not ease below.

**Concurrency is not the throughput lever, and this has now been measured three times**: a pilot lost
the archive entirely at 4 workers; a server with more cores was no faster than the laptop and slower
on CDX; and a batch-level A/B found 3 workers slower than 2. The limit is what the service will serve
one client. **The lever is requests per verdict, not requests in flight.**

The practical consequence for anyone tuning this: raising the worker count changes the failure mode,
not the rate. Lowering requests per pair changes the rate.

---

## 4. Two lessons from a retired engine

The page-level English verification engine is gone: the reviewer replaced that standard with the
equivalent-English metric in August 2026, and the code is in `legacy/src/language.py` with the full
account in `legacy/README.md`. Two of its design rules are general enough to belong here, because they
apply to anything that asks a service a question and records the answer.

**Unsettled is a first-class outcome.** A verdict, a documented rejection, and "the question did not
land" are three different things. A naive design collapses the third into the second, which excludes a
possibly-good record on the strength of a transport error. This project made exactly that mistake once
in the RDAP engine, at a cost of 12,888 domains, which is why the distinction is now enforced rather
than trusted.

**A record is never excluded on the strength of a question that was not asked.** A filtered CDX query
returning nothing means "nothing matching that filter", not "nothing at all". Before an absence is
recorded, a second unfiltered probe goes out. The same principle is why `ark check` reports a check
that read no files as **skipped** rather than passed: a check that examined nothing must not read like
one that found nothing wrong.

The `domain_language` table stays in `db.py` with its migration. Existing stores hold those rows, every
provenance export already delivered contains them, and `ark rebuild` loads them, so dropping it would
make a shipped archive unrebuildable.

## 5. One set of additions, and the pool beside it

The deliverable is `netnew/`, six annual files, plus `candidate_unverified.txt`. Those two are not a
set and a subset: a name in the pool has **no** year, so it appears in no annual file, and a name that
earns a year leaves the pool. Adding the two together double counts nothing.

Phase 4 briefly shipped a three-way split, with the additions partitioned into English-verified and
unverified sets. When the standard went, the partition went with it, and shipping it after that point
was worse than useless: the English folder came out empty, the archive's own `verify.sh` printed three
vacuous WARN lines about a partition of nothing, and the delivery loudly documented a rule nobody was
applying. **An archive that documents a retired rule reads as a rule still in force.**

## 6. Determinism, and what "reproducible" is allowed to mean

Three tiers, in increasing cost, described operationally in the READMEs. What matters here is what
each one actually proves:

1. **Verify the shipped result.** Nothing has changed and every pair traces to a recorded observation.
   Does not prove the observations were read correctly.
2. **Rebuild from the evidence graph.** The lists follow from the evidence, byte for byte. Does not
   prove the evidence follows from the sources.
3. **Rebuild from the original sources.** The evidence follows from the source data.

Tier 2 is the byte-identical one, and it is the one worth defending. Its enemies are inputs that move:
`uv.lock` pins dependency versions, the Public Suffix List is vendored rather than fetched, and
outputs are C-locale sorted. Two sources cannot be pinned, because they are republished (`.fr`) or
keep growing (Internet Scout); the journals and the Parquet export do not move, which is what makes
tier 2 hold anyway.

**The clean-room test is mandatory, not optional.** Unpack the archive in a directory unrelated to the
repository and follow its own instructions with no prior knowledge. It has found two defects nothing
else did, including a crash on step three of the documented tier-2 path.

---

## 7. The integrity gate

`ark check` runs nine invariants over the store and exits non-zero on any failure. They are not
tests of the code; they are tests of the data, and the two fail differently. `just check` runs both,
deliberately, because giving either one the bare name invites running one and believing the other
passed.

An invariant earns its place by having caught something, or by guarding a property that would be
expensive to discover was broken. Adding one is cheap; the honest question is what it would catch.

---

## 8. Sizing decisions by measurement

The standing rule is **measure the yield against the store before ingesting anything**. It is not
caution for its own sake: three of five sources assessed in one day were rejected after measurement
contradicted the estimate, two of them by two orders of magnitude, and one of those measurements
avoided a 19.35 GB download in two minutes.

The same rule applies inward. Whether the 1996 and 1997 additions deserve any verification budget was
settled by probing 200 of them rather than by argument, and the answer, 9.1% with a capture, changed
the queue ordering.

**Where an estimate is unavoidable, it is labelled in the same sentence as the number.** A projection
presented as a measurement is the specific error this project is most exposed to, because most of its
figures are measurements.

---

## 9. Layout

```
src/ark/          the pipeline package and the `ark` CLI
  db.py           schema, migrations, the store
  baseline.py     which reviewer release is current, and its totals
  english_share.py  the scoring metric's weight table
  checks.py       the nine data invariants
  cli.py          every command
scripts/          collectors, splitters, supervisors, packaging, measurement
tests/            pytest, network mocked
docs/             the brief and its amendments, sources, discovery, this file, notes, the report
legacy/           retired engines and spent probes; not linted, not tested, not shipped
```

Scripts under `scripts/` are the parts that run unattended for hours. They are shell rather than
Python where their job is process supervision, because their job is exactly what a shell is good at:
start a thing, watch it, restart it, log what happened.

The watchdog checks **progress rather than presence**. A batch hung on a socket leaves the supervisor
alive and the journal frozen, which a PID check reports as healthy, and that is the failure that costs
a night.

## 10. Ordering the queue by what the score actually rewards

Since August 2026 the reviewer scores **equivalent-English domains**, replacing a
plain record count: a (domain, year) record counts not 1 but the English
page-language share of its right-most TLD, from a `CC-MAIN-2024-10` table he
supplied. `foo.uk` is worth 0.9813 of a record, `foo.de` 0.1324. Which release the
totals are measured against is named in `src/ark/baseline.py` and nowhere else.

That changes what a queue is for. **Neither population can be finished**, and both
grow faster than the crawl closes them, because a larger merged baseline creates
new bracketed gaps. So the ordering decides the outcome and the tail is
theoretical. The measured pool sizes and hit rates live in `docs/sources.md` under
`ia_cdx_bulk` and `rdap`, which is where they ship; repeating them here is how they
come to disagree. Both list builders therefore rank
by **expected equivalent-English per query**, and the two factors come from
different places:

- **what an answer is worth** is the TLD share, pinned in `src/ark/data/`;
- **whether there will be an answer** is measured from our own journals, never
  assumed.

The candidate pool needs both, because its hit rate varies enormously with where
the name came from. The gap pool needs only the first, because a bracketed year is
nearly always there; the second factor there is how many bracketed years one query
can fill.

Two mistakes are recorded in `notes.md` because both cost real hours. Ranking by
share alone spent 1,709 queries on a TLD scoring 97.2% English for five hits,
because a high share says what an answer is worth and nothing about whether there
will be one; and estimating a hit rate from the pool query alone measured it over a
population that structurally excludes hits, because a domain that hits is given a
year and leaves the pool. The general lesson is that a plausible-looking ranking
is worth nothing until its own output is measured against something independent.

The pre-metric order, thinnest gap year first, survives as `--legacy-year-order`
and as the tiebreak inside an equal-value tier, so year balance still decides
between two targets worth the same. It was 54% worse per query as a primary key.

## 11. Collecting from several machines at once

Two things make this cheap, and both were built for other reasons.

Collection never opens the store. A remote machine needs the repository, `uv` and
a target list; it writes journals and nothing else, so there is no database to
synchronise and no lock to contend. Had the SQLite work queue been the mechanism
instead of journals, this would need a shared queue and a protocol.

Journals are content-addressed in the ledger by `(source name, file name)`, so
two machines can produce journals independently as long as their names differ.
`ARK_PREFIX` gives each machine its own, and any prefix starting `cdx_` stays
inside the globs the ingest commands and the resume scan already use.

Splitting is by **content hash of the domain, not by position in the list**. Hash
assignment needs no coordination: each machine derives the same answer from the
domain alone, so the slices stay disjoint and jointly complete however often
either side regenerates. Positional slicing would instead give one machine the
entire high-value head, which under an equivalent-English ordering is where most
of the score lives. The hash is `blake2b` rather than `hash()`, because the
built-in is salted per interpreter run: two machines would disagree about the
split, querying some domains twice and skipping others entirely.

The real constraint is not machines but the archive. It rate-limits per source
address, and it has refused this project outright three times. A second address is
a second budget, which is why this helps at all, and also why per-node concurrency
should go *down* when a node is added rather than staying flat. Section VI of the
brief requires treating a rate limit as a signal to adapt; adding capacity to a
service that is already throttling us is only defensible if total load stays near
what it has shown it tolerates.
