# journal.md: unattended session, 2026-07-26

Live log of an autonomous stretch on the `feature` branch, 02:20 to 16:00 CEST. Only decisions,
findings and numbers that matter; the full reasoning goes to [notes.md](notes.md) as usual, and the
task state stays in [todo.md](todo.md). To be synthesised into a report on return.

**Working from todo.md top to bottom.** Section D complete, A1a-A3c complete at session start.
Remaining at start: A4, A5, A6, then C (sources), B (candidate pool incl. §VII loop), G
(cross-validation), H (delivery, starting with the slop purge).

## Session start state, 02:20

| | |
|---|--:|
| Net-new domains / **pairs** | 463,364 / **1,304,348** |
| Store | 8,171,261 pairs · 11,050,295 evidence rows |
| Integrity | `ark check` 6/6 PASS · 149 tests · ruff clean |
| Branch | `feature`, at `3489dd1` |

Both engines running and supervised: `scripts/supervise_engines.sh` re-dispatches whichever is idle
every two minutes until 15:24, because a batch loop exhausts its count and idle hours are lost pairs.
Journals are ingested at checkpoints, never while being written.

---

## Log

**02:20: session start.** Supervisor launched. Verified its `pgrep` guard matches `bin/ark cdx`
(the real venv process) rather than `ark cdx`, which would also match the supervisor's own command
line and make both engines look permanently busy.

**02:20-03:10: A4, A5, A6 (correctness made provable).** Committed as one unit.

- **The integrity gate went from 6 invariants to 9**, and the new three were each measured clean
  before being added, so they are regression guards rather than bug reports. The valuable one is
  `evidence_year_matches_its_value`: it machine-enforces III.6 (a creation date attests only its own
  year) while exempting AFNIC's documented span. Measuring first mattered, because a naive version
  flags 87,324 AFNIC rows that are **correct by design**.
- The other two: `additions_not_double_counted` (net-new cannot be inflated by rows the baseline
  already had) and `nothing_earned_is_left_unassigned` (no master evidence row without its
  assignment, which is exactly the failure that would leave a confirmed domain in the candidate pool,
  so it answers the candidates-must-really-be-candidates requirement at the source rather than at the
  export). Each has a test that plants the violation and confirms the gate catches it.
- **A4 resolved as a rule plus enforcement rather than a 170 MB CSV**: every master line is either in
  the additions manifest or inherited from the supplied file for that year, disjoint (check 8) and
  exhaustive (check 3).
- **A6 surfaced something useful.** Reading §III verbatim rather than from memory showed **III.3 is
  specifically about the DMOZ 2015-03-27 aggregate**, which this pipeline never uses. That
  independently supports the ODP decision: the objection III.3 raises is precisely the
  undated-aggregate case that was avoided by ingesting only dated dumps.
- Removed hardcoded test counts from the report, since they go stale on every commit.

**Engines:** ingested the completed journals, **+3,115 pairs** banked. Store now **1,307,463**
net-new pairs. Both engines running, supervisor healthy.

**03:10-03:45: C dispatched, B1 done (candidate pool fixed).** Section C is six independent live
source investigations, so it went out as a parallel workflow rather than being done serially; B1 is
independent of its findings, so it was done meanwhile instead of idling.

- **The empty candidate pool was a missing ingester, not a bug in the stats.**
  `parse_ukwa_link_source` only ever yielded the source host, and its own docstring promised a
  target-side source that was never written. Now built, sharing one reader with the source side.
- **Candidate pool 4 -> 5,439 domains**, from 88,263 `link_target` evidence rows over 69,152 distinct
  targets. Zero year assignments from candidate-only evidence, as the taxonomy requires.
- **Finding: 92% of link targets (63,716 of 69,152) were already held.** Being linked to from the
  `.uk` web in this window is overwhelmingly a property of sites the baseline already covers, so the
  target side is worth its obscure 8% tail rather than volume. Worth stating in the report so the
  pool's size is not mistaken for pool value.

**03:45-04:20: B2, B3.** Candidate pool **4 -> 5,478**.

- **webbase measured properly at last:** 738,625 hostnames -> 603,323 distinct registered domains,
  603,141 already baseline, 64 already ours, **39 new**. The three-way seeding split turns the old
  "99.99% overlap" claim into a reproducible measurement.
- **`deduplicated_urls_2001-2002`: 0 new candidates** from 1.1M lines. Exhausted, as predicted in
  July. **Decided against seeding the twelve later files**: the one closest to the window yields
  nothing, so later crawls cannot do better, and their post-2001 populations would dilute the pool's
  meaning. §IX.2 asks for as large as *practicable*, not as large as possible.
- **B3 turned out to need verification, not code.** All 6,352 domains left undatable by either engine
  already hold an assigned year, because both engines are fed from already-held pools: an undatable
  result is a held domain with an unfilled gap, not a candidate. So III.10.c holds by construction.
  That is a property of the pools rather than the code, so both collectors now print a hint to run
  `ark seed` on the same list when they leave domains undated, which protects a future run over
  unknown domains from losing them silently.

**04:20-04:40: B4, B5 (candidate pool documented).** New report **§3.1**.

- Composition by discovering source, TLD mix, and what promotes a candidate (per year, never per
  domain).
- The section leads with *why the pool is 5,478 rather than larger*, which is the more interesting
  fact: the undated pools are 92-100% already held, so seeding them buys provenance rather than
  population. That reframes a small pool from a weakness into a measurement.
- B5 needed no new work: candidates have no assignment by construction, and the complementary
  failure (evidence recorded but never assigned, which would leave a confirmed domain in the pool) is
  what the new `nothing_earned_is_left_unassigned` invariant catches, measured at 0.

**Engines:** +440 pairs from an RDAP journal. Store **1,307,903** net-new pairs. C workflow still
running, all six investigations active.

**04:40-05:55: B6 (`ark download`, §VII expansion) and an Internet Archive outage.**

- **`ark download` built**, replacing a one-line stub. Journals one record *per capture* rather than
  per page, since a directory captured in 1998 and 2000 evidences its entries in each year
  separately. Curated-directory status is **asserted per seed** (`<TAB>directory`), never inferred
  from markup, because that assertion grants master evidence under §IV.i. Two source specs read the
  same journal and take their respective halves. stdlib `html.parser`, no new dependency, 14 tests.
- **`discovered_round` now threaded through the loader** and exposed as `ark ingest --round N`, which
  is what §VII.f/h need to show an actual cycle.
- **Internet Archive started refusing us.** The pilot failed on all three seeds; the local network was
  healthy and `rdap.org` fine, but `web.archive.org` refused TCP on 443. Eight probes: **2 up, 6
  refused, ~25% availability.** The CDX logs show the onset (`failed_0` per batch climbing to 436,
  `failed_503: 66`).
  - **No data was corrupted**, because failures are never recorded as answers. That decision, made
    yesterday after the opposite bug cost 2,727 domains, is what made this lost *time* rather than
    lost *data*.
  - Adapted per §VI rather than abandoning: the supervisor now probes IA before dispatching and holds
    CDX while it refuses; concurrency cut 8 -> 4. RDAP unaffected.
  - **Lesson: killing a worker without killing its dispatcher just spawns another.** The original
    batch loop survived a `pkill` of its child and immediately re-dispatched at 8 workers against a
    refusing host, which looked like my new gate failing. Found by listing dispatchers, not workers.
- **Risk flagged:** the section-C investigation agents depend on IA CDX, so their Mosaic / 100hot /
  WWW-Virtual-Library verdicts could be false negatives caused by this outage. Not taking any "dead"
  verdict at face value without re-checking against the outage window.

**05:55-07:10: G3, G4, H0 and a corrected metric.** Store **1,308,206** net-new pairs.

- **G4 contribution tables**, written by `ark export` into the audit folder: `source_contribution.csv`
  per source and `year_growth.csv` per year in the supplied `merge_stats` column shape. Validating
  them **found a real defect**: the net-new *pair* column had been computed with the net-new *domain*
  test, which silently zeroed every gap-filling source (`ia_cdx_bulk` read 0 instead of 3,324, ISC
  read 432,577 instead of 1,132,129). Fixed, and the column now sums **exactly** to the scoreboard,
  which a test asserts.
- **G2 corroboration by provenance lineage.** The headline "2,562,315 pairs with 2+ sources" was ~77%
  Internet-Archive-on-Internet-Archive. Grouping sources by the body of observation they derive from
  gives the honest figure: **583,634 pairs confirmed by 2+ independent lineages, 6,067 of them
  net-new**. Both are now reported side by side.
- **G3 reliability sampling at zero query cost**, by cross-referencing claims against the 2,587
  domains the CDX engine has already answered. `cdx_timestamp` 100% (a self-consistency check that
  validates the query path), `artifact_listing` **35%**, RDAP 32%. The 35% is published with its
  reading: a DNS survey records that a domain resolved, the archive records that someone crawled it,
  so the 65% disagreement **is** the coverage the archive lacks. A source agreeing 100% would be
  redundant.
- **H0 slop purge complete**, verified by count across every shipping surface (all 0). Also caught a
  stale "6 invariants" in the appendix, now 9.
- **Engines:** RDAP healthy throughout. IA still flapping between 25% and 40% availability; the
  supervisor holds and resumes CDX correctly. The three remaining section-C investigations are the
  IA-dependent ones and are still running.

**07:10-04:25: H1, H2, H4, B7, H7 and four bugs.** Store **1,309,970** net-new pairs (from
1,308,206), 9/9 invariants PASS, **192 tests** (from 176), ruff clean, 13 commits.

- **H1 `just` recipes, and the collision resolved.** `just verify-repo` validates the code,
  `just check-data` validates the data, `just check` runs both, so neither can be mistaken for the
  other. The pipeline is six named stages chained by `just reproduce`.
- **A latent bug found while wiring that up, and it was the dangerous kind.** The documented ingest
  glob `data/raw/cdx/cdx_*.jsonl.gz` matches a journal a collector is still writing, and the parser
  tolerates a half-written gzip stream rather than refusing it (measured: 121 records out of the
  live file). So an ingest issued mid-run would have ledgered the hash of a partial file, and every
  later ingest of the finished one would fail its hash check with the rest of the run unreachable.
  Checked whether it had already bitten: 26 ledgered journals, 0 mismatches, pure luck of timing.
  Runs now write `<name>.part` and rename on exit.
- **That fix then broke termination, which is worth recording.** Making SIGTERM raise `SystemExit`
  so the rename happens exposed the other half: the collectors submit the whole batch up front and
  `ThreadPoolExecutor` waits for every queued task on exit, so `pkill` was silently ignored and the
  run needed `kill -9`. Fixed by cancelling pending futures. Handling a signal is only half the job;
  what the process does on the way out is the half that hides.
- **A test was overwriting a shipping artifact.** `data/reports/source_contribution.csv` held two
  rows, `prior_task` and `ia_cdx` with one evidence row each, and its mtime was the last test run.
  `export_all` took three output paths but wrote the contribution tables to the real `data/reports`
  regardless. Packaging after a test run would have shipped a per-source table describing 2 domains
  instead of 5.29M.
- **H2 reproduction instructions rewritten** as 22 numbered steps, each with one command and the
  output it should print, and inputs (51 GB, network) split from the rebuild (offline, ~10 min).
  Every figure measured rather than inferred, which caught two of my own wrong numbers.
- **H4 auxiliary seed pool: 3,595,769 hostnames and URLs** over 2,195,955 domains. III.8 makes the
  registered domain the counting unit, so `shop.foo.com` collapses into `foo.com` and a crawler
  never reaches it. `ark seed-pool` re-reads each source through the *same parser* as `ark ingest`
  and keeps the raw value, so a seed cannot disagree with its own evidence.
- **B7 three expansion rounds, +1,267 pairs**, landing in the thinnest years (1998 +485, 1999 +464).
  Round 1 failed usefully: directory home pages gave 92 domains and zero new candidates, which is
  what pointed at the subject pages one level in. No page was called a curated directory until the
  catalogue's own metadata said so.
- **A source review's top recommendation declined.** It projected 700-1,100 net-new domains from
  100hot.com as master directory evidence. Its prescribed markup is not in the pages, and the
  productive captures are different ones, but it was right that the listed hosts are plain text: a
  text scan finds 488 net-new pairs the link extractor misses. Asserting them would break our own
  rule that only curated *entries* count, since a regex cannot tell an entry from an advertisement.
  Seeded as candidates instead: **258 new**, each to earn its own year from a capture.
- **Concurrency re-measured** after the outage rather than assumed: 4 workers ~185 answered/hour at
  64%, 8 workers ~383 at 92.5%, 12 workers ~262 at 84%. The pre-outage operating point of 8 holds.
- **H7 fresh clone passes** with only `uv`: sync, lint, 192 tests, `ark init`, `ark check` ALL PASS.
- **Packaging** now refuses a stale `output/` the same way it refuses a dirty tree, after catching
  the archive shipping 1,513 fewer pairs than the store held. The archive also ships the query
  journals (1.7 MB), which is what lets a reviewer reproduce both network stages with no network.

---

## Synthesis for your return (2026-07-26, 07:00)

**Where it stands.** 463,565 net-new domains over **1,322,358 net-new pairs**, from 463,364 /
1,308,206 when you went to bed. `ark check` 9/9 PASS, 195 tests (from 176), ruff clean, 32 commits
on `feature`, working tree clean. **The delivery archive is built and verified**: 128 MB, 111 files,
110/110 checksums OK, unpacks cleanly, `source/COMMIT.txt` matches HEAD, and its six year files hold
exactly 1,322,358 lines, matching the scoreboard. A fresh clone with only `uv` syncs, lints, passes
195 tests, and returns ALL PASS.

**Collection is stopped, deliberately.** Both collectors were shut down cleanly at 12:55 so the
store would stop moving while the final export, audit fixes and packaging were done; every journal
published (zero `.part` files left behind) and all were ingested. To resume:

```
nohup bash scripts/supervise_engines.sh 43000 8 &   # collectors, 8 workers is the measured optimum
nohup bash scripts/maintain_loop.sh 43000 &         # folds finished journals in every 20 min
```

After resuming, folding new pairs into the deliverable is three commands, and packaging refuses to
build from an `output/` older than the store rather than shipping a quiet mismatch:

```
bash scripts/maintain.sh          # ingest finished journals, print the scoreboard
uv run ark export
bash scripts/package_delivery.sh
```

**What got done.** Every remaining `H` item, all of `B7`, and one section-C source.

| | |
|---|---|
| H1 | `just` recipes for every documented command; the `check` collision resolved by giving neither validation the bare name |
| H2 | Reproduction rewritten as 24 numbered steps, each with the output it should print; inputs (51 GB, network) split from the rebuild (offline, ~10 min) |
| H4 | Auxiliary seed pool shipped: **3,595,769 hostnames and URLs** over 2.2M domains |
| B7 | **Four** section VII rounds, **+1,577 pairs**, plus the verification sample that closes the loop |
| H3/H6/H7 | Archive built and verified; fresh clone with only `uv` syncs, lints, passes 195 tests, and runs the integrity gate |
| H8 | Read-through against §IX; added report §7 answering whether each route is worth expanding |

**Four bugs found, all in shipping paths.**

1. **The documented ingest glob could permanently lose evidence.** `cdx_*.jsonl.gz` matches a
   journal a collector is still writing, and the parser tolerates a half-written gzip stream rather
   than refusing it. An ingest issued mid-run would ledger the hash of a partial file, and every
   later ingest of the finished one would fail its hash check with the rest unreachable. It had not
   fired yet (26 ledgered journals, 0 mismatches) purely by timing. Runs now publish under `.part`
   and rename on exit.
2. **Fixing that broke termination.** Making SIGTERM raise so the rename happens meant `SystemExit`
   propagated into `ThreadPoolExecutor.__exit__`, which waits for every queued task, so `pkill` was
   ignored and the run needed `kill -9`. Handling a signal is half the job; what the process does on
   the way out is the half that hides.
3. **A test was overwriting a shipping artifact.** `export_all` took three output paths but wrote
   the contribution tables to the real `data/reports` regardless, so the suite replaced the
   per-source table with its own two-row store. Packaging after a test run would have shipped a
   table describing 2 domains instead of 5.29M.
4. **Two `just` globs were quietly wrong**, found by expanding each one and comparing the count
   against the file ledger. The ISC pattern missed one of the five files it claimed to ingest.

**The judgement call I would most like you to check.** A parallel source review ranked 100hot.com
first of six and projected 700-1,100 net-new domains as master `dated_directory` evidence. Its
prescribed markup is not in the pages and the productive captures are different ones, but it was
right that the listed hosts are plain text, so a text scan finds 488 net-new pairs the link
extractor misses. **I declined to assert them**, because a regex cannot separate a listed entry from
an advertisement, and our own rule is that only curated entries count. They went to the candidate
pool instead, and were then verified: of 298 discovered candidates, 233 answered and **198 (85%)
held an in-window capture**, giving +278 pairs and +198 domains that now rest on archive captures
naming specific years rather than on a page's say-so. The cost was one 40-minute batch.

**Same discipline, applied to the directory route.** Archived HTML carries typos, and this route
produced `arvard.edu`, `gov.edu` and `gintysuooly.com`. So a name no other source attests is never
asserted from a listing; it is demoted to the candidate pool. That split now lives in `ark.expand`
with a tool that applies it to any journal, so the safe path is the easy one.

**Measurements worth keeping.** The archive refused us for hours, then returned degraded, so
concurrency was re-measured rather than assumed: 4 workers ~185 answered/hour at 64%, **8 workers
~383 at 92.5%**, 12 workers ~262 at 84%. Throughput halved; the optimum did not move. Nothing was
corrupted, because a failure is never recorded as an answer.

**Open, and deliberately so.** The candidate pool holds 5,583 domains; the bracketed CDX pool still
holds ~470,000 unqueried domains, which report §7 argues is the one route that converts hours into
pairs at a stable rate. Section E stays skipped by your decision. `plan.md` and `todo.md` are
current, with every box ticked in the sitting its work landed.

## Adversarial audit of the shipping documents (2026-07-26, 13:00)

Ran a seven-way audit of every shipping surface against the store, the repo and each other, with
each finding independently re-verified. **Twenty real defects, all now fixed**; one was rejected as
a false positive. Two would have been visible to Prof. Ding:

- **The documented checksum command did not work.** `checksums.sha256` listed 232 paths relative to
  `data/raw/` and 3 relative to the repo root, so running it as documented verified 3 files and
  reported the other 232 unreadable. Normalised to one base; **all 235 now verify.**
- **The archive shipped rounds 1 to 3 of the expansion journals and not round 4**, while its own
  readme told the reader to restore round 4, because the packaging script enumerated round
  directories by hand. It now finds every journal under `data/raw/expand`.

Wrong facts, not drift:

- The `link_target` row of the evidence table said the type was **unpopulated (0 rows) and its
  ingester not yet built**. It carries 88,511 rows, the ingest is step 14 of the documented rebuild,
  and the report credited its output two sections later. It was also missing from the
  evidence-rows-by-type list.
- The rate governor's ceiling was given as 2 s; it is the 5 s `--max-delay` default and no
  production run overrides it.
- "22 numbered steps" (24) and "the 21-row rejected table" (17 rows).

The remaining thirteen were hand-maintained figures that drift with every ingest, and the durable
fix was to stop maintaining them by hand: `scripts/refresh_report_figures.py` now also owns the
section 4 metrics bullet, the evidence-rows-by-type list, the `ia_cdx_bulk` and `rdap_snapshot`
figures, the README archive total, and two per-source yields in `sources.md`. Anything it owns
cannot be stale after a repackage, which is the class of error this audit mostly found.

**What I would still check yourself.** The `page_directory` evidence rests on my reading that a
page declaring itself "an expert-run catalog" satisfies IV.i. I verified that from the capture's own
metadata rather than the site's reputation, and demoted every name no other source attests, but it
is a judgement about evidence standards and therefore yours to confirm.
