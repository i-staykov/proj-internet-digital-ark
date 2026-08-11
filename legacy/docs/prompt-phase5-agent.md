# Prompt for the phase-5 agent

Paste everything below the line into a fresh Claude Code session opened in
`/Users/ivaylo.staykov/Documents/GitHub/proj-internet-digital-ark`.

Kept in `private/` because it is a working instruction, not a deliverable, and `private/` is
git-ignored so it can never travel in a delivery archive.

---

You are joining the **Internet Digital Ark** on branch `phase-5`, in
`/Users/ivaylo.staykov/Documents/GitHub/proj-internet-digital-ark`.

**Read `docs/phase5-handoff.md` first and completely, before running anything.** It is the state of the
project, the round's objective, and the specific ways this repository will waste your time. It tells you
which other documents to read and in what order. Reading it is not optional overhead: roughly fifty
source families have already been evaluated and rejected with the measurement that killed each, and
rediscovering one is the single most likely way to lose a day.

## What the project is

Reconstruct the list of domain names that existed 1996-2001, for a reviewer who merges accepted
`(domain, year)` records into six annual `.txt` files. **A domain in an annual file is a claim about a
year, and every claim must name the observation that supports it.** That is enforced by the schema, not
by convention. Scoring is equivalent-English: each record counts the English page-language share of its
right-most TLD, so `foo.uk` is worth 0.9813 of a record and `foo.de` 0.1324.

Phase 4 was accepted in full and reissued as the baseline `merged260810`. Phase 5 currently stands at
52,768 net-new pairs and 22,313.82 equivalent-English, already verified with the reviewer's own
calculator.

**A second collector is running on a VPS, and there are three things to know before you plan around it.**
It is at `digga@10.1.0.6` in `/projects/proj-internet-digital-ark`, and it must not be disturbed. That is
a private address, so **you cannot reach it unless I bring the VPN up: ask me, rather than debugging your
own SSH configuration.** Its journals are invisible to every measurement you take here until you rsync
them home, and this project once ran it for a day and a half with 5,793 year-records stranded on its
disk. And it **stops collecting at 2026-08-19T11:30Z without telling anyone**, because that is the
deadline epoch its supervisor was given. Section 2 of the handoff has the commands for all three,
including how to restart it and why that needs a freshly built queue shard.

## The objective

The reviewer's words: this is "an intelligent scientific discovery and knowledge discovery problem, not
merely an ordinary downloading task." He wants automated analysis, association inference, multi-source
clue mining, automated search and DeepResearch engines, and the objective is to "keep generating new
hypotheses, test them against dated evidence, and continuously expand coverage."

The previous four rounds were a human finding a source, measuring it, and writing a collector. **He is
asking for the finding and the measuring to be automated**, while keeping the evidence standard exactly
as strict. `docs/brief_amendments.md` has his five priorities in his own words; `docs/discovery.md` is
the method for pricing a source that the harness has to apply.

## Start here, in this order

1. Read `docs/phase5-handoff.md`, then the documents it lists.
2. Run `just check` (nine data invariants plus lint, format and tests) and `uv run ark stats`. Confirm
   stats says `merged260810`. If it says anything else, stop and say so.
3. **Then come back to me with a plan before building anything.** Tell me what you intend to do, in what
   order, and what you expect each step to be worth. I want to agree the shape before you spend hours on
   it.

Section 4 of the handoff ranks the measured opportunities. **Section 5 is what the round has to produce**
(the archive, the report, and the five fields he grades on): read that before you plan, not after, because
none of the discovery work counts until it ships in that shape.

The three opportunities worth your attention first are the 1.54M never-asked registry names (~82,700
equivalent-English at a known and cheap rate), the 17,525 Usenet archives that have never been through a
yield measurement despite all being ingested, and `alt.*`, which is 79% of the Usenet groups and 57% of
the bytes with its yield entirely unknown. All three need no new source, and the last two need no network.

## What will waste your time, so do not

- **Do not trust `grep` here.** It is a shell function backed by ripgrep, which honours `.gitignore`,
  which hides `data/`, `output/`, `private/`, `legacy/notes/` and `feedback-*/` from every recursive
  search. Use `command grep` with an explicit file list. Section 7 of the handoff has three more traps of
  the same family, each of which has already produced a confident wrong answer in this project.
- **Do not propose a source without checking the rejected register** in `docs/sources.md`.
- **Do not present a projection as a measurement.** Section 6 of the handoff lists eleven distinct ways
  this project has fooled itself with a number, every one of which cost real hours. Label an estimate in
  the same sentence as the number.
- **Do not relax the evidence rules to make a harness easier to build.** Per-item year evidence, no
  inference across years, and the corroboration split for anything a human typed. Those rules are why the
  last round was accepted line for line.
- **Do not point a third heavy client at `web.archive.org`.** It has refused this project outright three
  times, and the VPS is already collecting. Prefer bulk downloads and non-IA hosts, honest User-Agent,
  honour `Retry-After`, back off on 429/503/504.
- **Do not hold the DuckDB write lock.** Open the store `read_only=True` with a retry loop on
  "Conflicting lock" for anything that only measures.

## House rules, non-negotiable

- **Never `git push`. Never `git commit` unless I ask you to.** I commit and push. Work on `phase-5`.
- **Never add a `Co-Authored-By` trailer or any AI attribution**, in a commit message or anywhere else.
- **No em-dashes and no en-dashes anywhere**: code, comments, docs, prose.
- **Log every decision** in `docs/notes.md` as a dated entry in the existing style, ending
  `**Signed off by Ivo: pending.**` Never edit a figure inside an existing dated entry: they are history.
- **Explain and outline before non-trivial file edits, and wait for my go-ahead.** Propose, then act.
- **Run the gate before proposing a commit**, and never propose one through a red gate:
  `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && uv run ark check`
- **Update `README.md` in the same sitting** as anything that adds a tool or a command. It is my
  verification checklist.
- **All raw data under `data/raw/` stays.** This round is about what is unexhausted in it.
- **Never edit** `docs/SPEC.md` (the reviewer's brief, cited by clause number from 21 files), the frozen
  files under `submissions/phase-4/`, or `docs/report.md` (generated; packaging refuses if it disagrees
  with `fill_report.py`). `legacy/` is read-only.

## What good work looks like here

Measure before you build, quote the post-split number rather than the raw one, and prefer a source where
each item carries its own date. Two of the three largest additions this project has ever made came from
bytes already on disk and sent no network request at all, because the original extractor could not see
what was there. **Before writing a source off, check what the parser actually reads.**

If you find that something I or a previous session asserted is wrong, say so plainly with the command
that shows it. That has already happened twice this week and both times it was the most valuable thing in
the session.
