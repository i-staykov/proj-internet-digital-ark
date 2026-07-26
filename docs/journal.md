# journal.md — unattended session, 2026-07-26

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

**02:20 — session start.** Supervisor launched. Verified its `pgrep` guard matches `bin/ark cdx`
(the real venv process) rather than `ark cdx`, which would also match the supervisor's own command
line and make both engines look permanently busy.

**02:20-03:10 — A4, A5, A6 (correctness made provable).** Committed as one unit.

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

**03:10-03:45 — C dispatched, B1 done (candidate pool fixed).** Section C is six independent live
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

**03:45-04:20 — B2, B3.** Candidate pool **4 -> 5,478**.

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

**04:20-04:40 — B4, B5 (candidate pool documented).** New report **§3.1**.

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

**04:40-05:55 — B6 (`ark download`, §VII expansion) and an Internet Archive outage.**

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
