# Internet Digital Ark: the standing brief

Loaded automatically at the start of every session. **It holds only what never changes.** Anything
that moves is generated or logged elsewhere, because a hand-written file about the current state
rots: `docs/phase5-handoff.md` was accurate for one day and three of its claims were disproved by
the next morning.

## The one idea

A domain in an annual file is a **claim about a year**, and every claim names the observation that
supports it. `domain_year.evidence_id` is `NOT NULL` and foreign-keys a row in `evidence`, so no code
path can write a year assignment without one. That is structural, not a convention, and it is why an
unattended agent can be given latitude about *what to try* and none at all about *what counts as
proof*.

- **Per-item year evidence, no inference.** A capture in 1998 evidences 1998 and nothing else.
- **Master-eligible** types can assign a year: `prior_reused`, `cdx_timestamp`, `artifact_listing`,
  `link_source`, `dated_directory`, `whois_creation`. **`link_target` never can**, and `assign_year`
  refuses it.
- **The corroboration split.** Anything a human typed is admitted only if another source already
  places that domain in an annual file. Self-dating records (a capture timestamp, a registry creation
  date, a dated listing) take no split. **So widening extraction over a human-authored corpus is
  safe, and widening it over a self-dating one is not.**
- **What the split does not protect against: a hostname that was never real.** It asks only whether
  the domain is dated in *some* annual file, never whether the mention was genuine, so an invented
  name that was later really registered passes. Measured on the RFC corpus, 2026-08-11: a large
  minority of surviving mentions are protocol placeholders (`acmecorp.com`, `bigco.com`,
  `widgetco.com`, `john-doe.com`), which is why RFC 2606 reserved `example.com` in 1999. **Technical
  prose that invents plausible examples is the one typed shape where the split is not the wall**, and
  the risk is a year claim for a year the domain did not exist.
- **Which class a source belongs to is a decision, not an attribute**, and asserting it batch-wide is
  how a good source gets filed as rejected. The Netcraft survey pages were measured as `typed` on an
  unexamined assumption and are worth 8,741 pairs as `artifact_listing` against 2,204 under the split.
  If a corpus has no author, no prose and no per-item date, it is probably self-dating: check before
  quoting a number that depends on it.
- **Quote the post-split number, never the raw one.**
- **A source class may not date a year until a human has classified it.**
  `docs/approved-sources-list.md` holds one `Decision:` line per (source, evidence type), and
  `ark ingest` refuses a master-eligible class that is `pending`, `rejected` or absent.
  **This is not advisory and it is not the agent's call**: an agent arguing that its own
  find is master evidence is the least trustworthy artifact here. Write the request with
  `uv run python scripts/request_approval.py <spec> --journal <journal>`, which builds it
  out of a seeded-random sample with live links, the measured figures and the
  counterfactual, so a reviewer checks external evidence rather than reading an argument.
  **Candidate-only evidence needs no approval**: it can never date a year, so collection
  never waits on a human. A `rejected` decision binds.

## The metric

**Equivalent-English domains**: each `(domain, year)` record counts the English page-language share of
its right-most TLD. `foo.uk` 0.9813, `foo.com` 0.6321, `foo.net` 0.4530, `foo.de` 0.1324. A large
non-English source is a small source. Growth is quoted against the reviewer's **pre**-increment total.
Which release is current lives in `src/ark/baseline.py` and nowhere else.

## Where state lives, and which to trust

| | what it is | how to use it |
|---|---|---|
| `docs/ROUND.md` | **generated** current state: scoreboard, engines, residual, clock | read first, never edit |
| `docs/key-decisions.md` | **the only place that asks Ivo for anything.** Open and closed decisions, pointing to an ADR where one exists | append as you decide; anything waiting on him appears here or nowhere |
| `docs/approved-sources-list.md` | which source classes may date a year, one `Decision:` line each. **Enforced by `ark ingest`, not by convention** | a `pending` entry here must also be named under `## OPEN` in `key-decisions.md` |
| `docs/ADRs.md` | the few decisions with **structural** impact: taxonomy, store shape, machine allocation, shared write paths |
| `docs/notes.md` | append-only dated history, thousands of lines | **grep it, never read it whole**; never edit a past entry |
| `docs/sources.md` | every source, what dates it, what remains, ~60 rejected families | `just screen` before proposing anything |
| `docs/discovery.md` | how to price a source before building a collector | the acceptance bar |
| `docs/SPEC.md` | the reviewer's brief, cited by clause from 21 files | **never edit or renumber** |
| `docs/brief_amendments.md` | what he has changed since: the metric, the retired standard | current asks |
| `private/personal-context.md` | who Ivo is, and the reviewer's emails verbatim | git-ignored, never ships |

**Every figure inside a dated `notes.md` entry is historical by construction.** It was true against
the store of that day and is not a statement about now.

## House rules

- **Never `git push`.** Committing in coherent units on a non-`main` branch is authorised; `main` is not.
- **Never add a `Co-Authored-By` trailer or any AI attribution**, anywhere. Commits are Ivo's.
- **No em-dashes and no en-dashes** anywhere: code, comments, docs, prose, commit messages.
- **Log every decision** in `docs/notes.md`, dated. **It needs no sign-off**: it is the agent's own
  working, Ivo does not review it, and asking him to would bury the things that do need him.
- **`docs/key-decisions.md` is the single place anything asks Ivo for a decision.** If it is not
  there, he will not see it, so putting it anywhere else is the same as not raising it. One entry
  under `## OPEN`, one screen at most, pointing at the ADR or notes entry that carries the working.
- **Hypotheses are yours to settle.** Screen, price and decide them without asking. A lead is
  adopted, closed on a measurement, or left with its verdict recorded; only when the outcome
  amounts to a decision worth overruling does it become a `## OPEN` entry. A ledger of unfinished
  leads is a work queue, not a question for Ivo.
- **Explain and outline before non-trivial file edits**, and wait for a go-ahead. Propose, then act.
- **Run the gate before proposing a commit**, and never through a red one:
  `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && uv run ark check`
- **Update `README.md` in the same sitting** as anything that adds a tool or a command.
- **Comments short, human, objective, future-proof.** Say why, not what.
- **Never edit** `docs/report.md` (generated) or the frozen files in `submissions/phase-4/`.
  `legacy/` is read-only. All raw data under `data/raw/` stays.

## Standing operational rules

- **Two populations, two machines** (Ivo's design, 2026-08-11). The **VPS** works pure bracketed gaps,
  a missing year Y with Y-1 and Y+1 already held, as an unattended **completeness** baseline: its hit
  rate is 96-97.5% and flat across TLDs, so ranking it by English share is correct there. The **local**
  engine works the **candidate pool** beside the discovery loop that feeds it, which is the
  **discovery** half the reviewer asked to be prioritised; its hit rate runs 36.9% to 90.6% depending on
  where a name came from, so there the share must be multiplied by a *measured* rate or `.au` sorts to
  the top for zero in-window dates. Build them with
  `build_query_queue.py --population gap|pool --out PATH`.
- **Gap targets change slowly**, so the VPS needs a rare refresh rather than a periodic one, and only
  ever a shard built after the current baseline landed.
- **When jobs contend for the write lock, priority follows expected net-new equivalent-English**
  (ADR-001): banking a finished journal wins, pricing and measurement beat seeding, and a seed blocking
  something valuable is interrupted rather than waited out. **A re-run is always additive**, so
  interrupting costs nothing that a repeat does not recover.
  **The ordering is enforced in code, not remembered**: `ark ingest` waits 2400s for the lock because a
  banking pass that gives up leaves collected work on disk, and `ark seed` waits 20s and then says it
  yielded. A long patience does not make a low-priority job polite, it makes it queue and then hold.
- **Contention itself was fixed on 2026-08-11 and the numbers are worth knowing**, because everything
  above was written while the store was unusable. The ingest loop ran one `ark ingest` per journal
  **file**, 636 of them a pass every 150 seconds, and held the write lock **89% of the time**; it is one
  invocation per source now, and 0%. Separately `add_candidates` inserted row at a time, which was
  **1,207 of a 1,208-second seed**, and is now a set-based insert from an Arrow table at 267x.
  So a seed no longer holds the lock for twenty minutes, and the old reason it was safe to interrupt,
  that inserts autocommit per row, **is no longer true**: a single statement rolls back. The window is
  simply negligible instead.
- **`10.1.0.6` is private.** Ask Ivo to bring the VPN up; do not debug SSH. Use a window immediately
  and completely: fetch first, ask questions afterwards. `just engines` reports **UNKNOWN** rather
  than "everything is home" when it cannot reach the machine, and that distinction is the fix for
  having once left 5,793 records stranded for a day and a half.
- **Be a good citizen.** The Internet Archive has refused this project outright three times. Honest
  User-Agent naming the project and a contact address, honour `Retry-After`, back off on 429/503/504,
  modest concurrency, prefer bulk downloads and non-IA hosts. Never point a third heavy client at
  `web.archive.org` while the VPS is collecting.
- **Ding wants long-running programs kept running.** If something can run unattended without getting
  in the way, keep it running.

## If you were started by a cron job

A cron wake is not a new brief. It is a 15-minute check that the round is still moving, and its first
duty is to avoid making things worse. Work this in order and stop at the first step that applies.

1. **Are *you* mid-task?** If this session has unfinished work in flight, continue it and stop reading
   here. Do not re-plan, do not start something adjacent, do not restate the situation.

   **"The collectors are running" is not you being busy.** A supervisor looping over a queue wants no
   attention at all, so a wake that finds healthy collectors and an idle agent is the **normal** case
   rather than an exception.

2. **Is anything stopped, unread or stale?** One command answers all three:

       just cycle

   It checks both collectors, **whether all three of them are finding anything as opposed to merely
   running** (the two CDX populations and the RDAP sweep),
   journals on disk that nothing has ingested, derived lists older than the store, the hypothesis
   ledger, pending approvals and `docs/ROUND.md`, rebuilds what it can, and ends with the items
   **no program can decide**. Act on those. If a collector is down, restart it; if a journal is
   unbanked, ingest it.

   **Presence is not progress, and progress is not yield.** A journal full of misses grows exactly as
   fast as a journal full of hits, so a collector can be alive, writing, and worth nothing. That is
   what the yield line reports, and on 11 August it was the only check that would have caught 1,200
   queries returning zero while every other one read clean.

   **Ask the process table, never a log file, whether something is running.** `supervise_cdx_pool.sh`
   writes `data/logs/${ARK_PREFIX}.log`, so a quiet `cdx_pool.log` proves only that nothing has run
   *under that prefix*. On 11 August that inference killed a healthy collector: it had been working the
   pool since 11:10 under an invented third prefix, its own log was current, and the documented one was
   four days old and read as a dead engine. **`cdx_pool` and `cdx_gap` are the only two prefixes**, per
   the script's own header. Do not invent a third. Check with a pattern that cannot match your own
   command line, `pgrep -f 'supervise_cdx_poo[l]'`, since a bare `pkill -f supervise_cdx_pool.sh`
   matches the shell running it and has twice reported the opposite of the truth.

3. **Then bring the documentation back into one story**, which is the part only you can do. The
   sources of truth are the table in **Where state lives** above, and they have to agree with each
   other: `docs/ROUND.md` current against the store, every decision of today's in `docs/notes.md`, any
   structural one in `docs/ADRs.md` and named from `docs/key-decisions.md`, every new source class
   carrying a `Decision:` line, `README.md` naming every command that now exists. A claim that has
   been disproved gets corrected where it was made, not only in the newest file.

4. **Only then, do the next piece of real work**, sized to fit: prefer finishing one thing over
   starting three. Unfinished hypotheses are the first place to look, and they are yours to settle.
   Anything that genuinely needs Ivo goes to `docs/key-decisions.md` under `## OPEN`, which is the
   only surface he reads, rather than waiting in a session nobody is looking at.

**"Everything is fine" is a valid outcome.** Record it in one line and stop. Do not invent work to
justify the wake, and never start a second copy of a collector to look busy.

## Traps that have each produced a confident wrong answer

- **`grep` here is ripgrep and honours `.gitignore`**, hiding `data/`, `output/`, `private/`,
  `legacy/notes/` and `feedback-*/`. Use `command grep` with an explicit file list:
  `git ls-files > /tmp/f && tr '\n' '\0' < /tmp/f | xargs -0 command grep -n 'pattern'`.
  zsh does not word-split unquoted parameters, so `command grep -n "$t" $FILES` greps one
  nonexistent filename and returns zero for everything.
- **`ls data/raw/usenet/*.mbox.zip | wc -l` returns 0**, not 19,231: the arguments overflow the exec
  limit and a `2>/dev/null` swallows the error. Use `find`.
- **`grep -c "A|B|C"` is a basic regexp**, so the pipes are literal and it returns 0 by construction.
  Use `grep -cE`.
- **A search that finds nothing has either proved something or been pointed at the wrong place, and
  the two look identical.** Prove a negative against a case you know is positive.
- **`pgrep -f X` and `pkill -f X` match the shell that is running them**, because the pattern is in
  its own command line. So the check reports a process that is not there and the kill takes down the
  caller, which has happened twice here, once destroying a watcher mid-run. Bracket one letter:
  `pgrep -f 'supervise_cdx_poo[l]'` cannot match itself.
- **DuckDB takes one writer.** Open `read_only=True` with a retry loop for anything that measures.
  A long write blocks every reader. That used to mean a 20-minute outage for the auditors on every
  seed; both causes were found and fixed on 2026-08-11 (ADR-001), so the rule now matters for
  correctness rather than for waiting: a reporting command that needs the lock must still be patient,
  because the ingest loop legitimately takes it.
- **`ark export` before `ark check`, always**: one invariant reads the exported annual files.
- **Never present a projection as a measurement.** Label an estimate in the same sentence as the
  number. `docs/notes.md` records eleven distinct ways this project has fooled itself with a figure.
