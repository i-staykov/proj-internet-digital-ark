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
- **Quote the post-split number, never the raw one.**
- **A source class may not date a year until a human has classified it.**
  `docs/open-approvals.md` holds one `Decision:` line per (source, evidence type), and
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
| `docs/key-decisions.md` | short list of open and closed decisions, for Ivo to overrule | append as you decide |
| `docs/open-approvals.md` | which source classes may date a year, one `Decision:` line each. **Enforced by `ark ingest`, not by convention** |
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
- **Log every decision** in `docs/notes.md`, dated, ending `**Signed off by Ivo: pending.**`
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
  something valuable is interrupted rather than waited out. That is safe: inserts autocommit and a
  re-run is additive.
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
   rather than an exception. Confusing the two is what left the local engine stopped from 7 to 11
   August while every status line read healthy.

2. **Is anything stopped, unread or stale?** One command answers all three:

       just cycle

   It checks both collectors, journals on disk that nothing has ingested, derived lists older than the
   store, the hypothesis ledger, pending approvals and `docs/ROUND.md`, rebuilds what it can, and ends
   with the items **no program can decide**. Act on those. If a collector is down, restart it; if a
   journal is unbanked, ingest it. Before starting any long-running process, check whether one is
   already up, and check it with a pattern that cannot match your own command line:
   `pgrep -f 'supervise_cdx_poo[l]'`. A bare `pkill -f supervise_cdx_pool.sh` matches the shell running
   it and has twice reported the opposite of the truth.

3. **Then bring the documentation back into one story**, which is the part only you can do. The
   sources of truth are the table in **Where state lives** above, and they have to agree with each
   other: `docs/ROUND.md` current against the store, every decision of today's in `docs/notes.md`, any
   structural one in `docs/ADRs.md` and named from `docs/key-decisions.md`, every new source class
   carrying a `Decision:` line, `README.md` naming every command that now exists. A claim that has
   been disproved gets corrected where it was made, not only in the newest file.

4. **Only then, do the next piece of real work**, sized to fit: prefer finishing one thing over
   starting three. Anything needing a human goes to `docs/key-decisions.md` or
   `docs/open-approvals.md` rather than waiting in a session nobody is reading.

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
  A long write blocks every reader, so a 20-minute ingest is a 20-minute outage for the auditors.
- **`ark export` before `ark check`, always**: one invariant reads the exported annual files.
- **Never present a projection as a measurement.** Label an estimate in the same sentence as the
  number. `docs/notes.md` records eleven distinct ways this project has fooled itself with a figure.
