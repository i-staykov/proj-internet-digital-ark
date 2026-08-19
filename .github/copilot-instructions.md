# Internet Digital Ark: the standing brief

**This file is the harness.** It is loaded automatically at the start of every session and holds only
what never changes. Anything that moves is generated or logged elsewhere, because a hand-written file
about current state rots. For the full orientation, read `handoff-copilot.md` once.

## The goal, and the one constraint that decides everything

Reconstruct the list of domain names that existed 1996-2001, for Prof. Xiaowei Ding. Scored on
**equivalent-English domains**: each `(domain, year)` record counts the English page-language share of
its right-most TLD (`.uk` 0.9813, `.com` 0.6321, `.net` 0.4530, `.de` 0.1324). A large non-English
source is a small source.

**A submission is only allowed at 5% growth or above.** The threshold is about 603,855 EE and it
**recedes by roughly 54,101 EE a day** because other contributors keep growing the corpus, while
per-domain archive querying adds about 13,200 EE a day. **The gap widens by about 40,901 EE a day and
never closes.** So only a bulk dated corpus of roughly 600,000 EE produces a submittable round. Read
that again before spending a day on a collector: `scripts/submission_cadence.py` recomputes it.

## The one idea

A domain in an annual file is a **claim about a year**, and every claim names the observation that
supports it. `domain_year.evidence_id` is `NOT NULL` and foreign-keys a row in `evidence`, so no code
path can write a year assignment without one. That is structural, not a convention.

- **Per-item year evidence, no inference.** A capture in 1998 evidences 1998 and nothing else.
- **Master-eligible** types may assign a year: `prior_reused`, `cdx_timestamp`, `artifact_listing`,
  `link_source`, `dated_directory`, `whois_creation`. **`link_target` never can**, and `assign_year`
  refuses it.
- **The corroboration split.** Anything a human typed is admitted only if another source already places
  that domain in an annual file. Self-dating records (a capture timestamp, a registry creation date, a
  dated listing) take no split. So widening extraction over a human-authored corpus is safe and widening
  it over a self-dating one is not.
- **What the split does not catch: a hostname that was never real.** It asks only whether the domain is
  dated somewhere, never whether the mention was genuine. Technical prose invents plausible examples
  (`acmecorp.com`, `widgetco.com`), which is why RFC 2606 reserved `example.com`.
- **Quote the post-split number, never the raw one.**
- **A source class may not date a year until a human has classified it.**
  `docs/approved-sources-list.md` holds one `Decision:` line per (source, evidence type), and
  `ark ingest` refuses a master-eligible class that is `pending`, `rejected` or absent. **This is not
  advisory and it is not the agent's call.** Write the request with
  `uv run python scripts/request_approval.py <spec> --journal <journal>`, which builds it from a
  seeded-random sample with live links, the measured figures and the counterfactual, so a reviewer
  checks external evidence rather than reading an argument. **Candidate-only evidence needs no
  approval**, so collection never waits on a human.

## House rules, all non-negotiable

- **Never `git push`.** Committing coherent units on a non-`main` branch is authorised; `main` is not.
- **Never add a `Co-Authored-By` trailer or any AI attribution.** Commits are Ivo's.
- **No em-dashes and no en-dashes** anywhere: code, comments, docs, commit messages.
- **Run the gate before proposing a commit**, and never through a red one:
  `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && uv run ark check`
  A pre-commit hook enforces it (`just hooks`). **Never put the gate through a pipe**: `pytest -q | tail`
  returns tail's exit status, so `&&` walks past a failure. Never `git add -A`.
- **`ark export` before `ark check`, always**: one invariant reads the exported annual files.
- **Explain and outline before non-trivial file edits**, then act.
- **Update `README.md` in the same sitting** as anything that adds a tool or command.
- **Never edit** `docs/SPEC.md` (cited by clause from 21 files), `docs/report.md` (generated), the frozen
  files in `submissions/phase-4/` and `submissions/phase-5/`, or anything under `legacy/`. All raw data
  under `data/raw/` stays. `private/` is git-ignored and never ships.
- **Big data must never reach git.** A `git add -A` once swept a 1.3 GB baseline into history.
- **Be a good citizen.** The Internet Archive has refused this project three times. Honest User-Agent
  naming the project and a contact address, honour `Retry-After`, back off on 429/503/504, modest
  concurrency, prefer bulk downloads.

## Where state lives, and which to trust

| | what it is | how to use it |
|---|---|---|
| `docs/ROUND.md` | **generated** current state | read first, never edit |
| `docs/key-decisions.md` | **the only place that asks Ivo for anything** | anything waiting on him appears here or nowhere |
| `docs/approved-sources-list.md` | which classes may date a year. **Enforced by `ark ingest`** | a `pending` entry must also be under `## OPEN` in key-decisions |
| `docs/sources.md` | every source, what dates it, **112 closed families** | check here before proposing anything |
| `docs/discovery.md` | how to price a source | the acceptance bar |
| `docs/ADRs.md` | the few structurally significant decisions |
| `docs/ding/` | **his own documents, transcribed verbatim** | the highest authority |
| `docs/brief_amendments.md` | what he has changed since the SPEC | current asks |
| `docs/archive/` | historical: the old decision log, dossiers | **grep, never read whole** |

**Four surfaces carry his instructions and they rank.** A later email of his beats `docs/ding/`, which
beats `docs/SPEC.md`; `docs/brief_amendments.md` records the overruling.

## What every submission must contain, D1 to D4

Required of **every** future submission (his email, 2026-08-17): **D1** the complete runnable code and
execution instructions; **D2** a concise experience summary; **D3** the merge and deduplication code
with overlap counts, accepted increment and reconciliation checks, mirroring the column names of his own
`merge_stats_<contributor>_<date>.csv`; **D4** the runnable equivalent-English calculation with the fixed
weights, formula, baseline total, **post-merge total**, increment and growth rate.

**`just ship` is the enforcement point, not a checklist**, and `verify.sh` checks all four inside a fresh
extraction. Anything that lives only in prose gets shipped unmet.

## Traps that have each produced a confident wrong answer

- **A search that finds nothing has either proved something or been pointed at the wrong place, and the
  two look identical. Prove a negative against a case you know is positive.** This is the single most
  useful rule here. Three separate wrong conclusions in one afternoon came from skipping it.
- **Any name-shape filter over-catches.** "Nominet sold no second-level `.uk` until 2014" would have
  deleted `bl.uk`, the British Library. `.br` marked as never allowing them holds `ansp.br`, a real
  academic network. A rule flagging single-letter labels flags `0.com` and `x.com`, both real. **The
  early DNS was heterogeneous**, and a registry's "opened in year X" date says when a level opened to the
  *public*, not when it began to exist.
- **Counting net-new against the store from an already-ingested journal returns zero by construction**,
  and zero looks identical to worthless. A hit *rate* is safe to compare; a net-new *value* needs a
  snapshot taken before ingest.
- **A rate is a property of a namespace at a point in its exhaustion.** Measure over a trailing window,
  not a lifetime. But the pool-wide prior is deliberately **not** windowed, because windowing it scores
  every unmeasured namespace at zero.
- **Never present a projection as a measurement.** Label an estimate in the same sentence as the number.
- **`grep` here may honour `.gitignore`**, hiding `data/`, `output/`, `private/`, `legacy/`. Use
  `git ls-files > /tmp/f && tr '\n' '\0' < /tmp/f | xargs -0 grep -n 'pattern'`.
- **`ls data/raw/usenet/*.mbox.zip | wc -l` returns 0**, not 19,231: argument overflow. Use `find`.
- **`grep -c "A|B|C"` is a basic regexp** and returns 0 by construction. Use `grep -cE`.
- **Never pipe a health check through `head` or `tail`.** A truncated health check looks like absence.
- **`pgrep -f X` and `pkill -f X` match the shell running them.** Bracket a letter:
  `pgrep -f 'supervise_cdx_poo[l]'`. **Kill a worker child before its supervisor**, or the worker is
  reparented and keeps querying while `pgrep` reports it stopped.
- **DuckDB takes one writer.** Open `read_only=True` with a retry loop for anything that measures.
