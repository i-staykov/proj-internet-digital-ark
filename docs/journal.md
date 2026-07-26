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
