# Internet Digital Ark

Reconstruct the domain names that existed 1996-2001 for Prof. Xiaowei Ding. Scored on **equivalent-English
domains**: each `(domain, year)` record counts the English share of its TLD (`.uk` 0.9813, `.com` 0.6321,
`.net` 0.4530, `.de` 0.1324). Non-English ccTLDs are close to worthless.

**The job, in one line: find new sources, hold the evidence bar, automate the work, stay creative, and
keep re-testing old sources that may have become available or cheaper.**

## The evidence bar

- **Per-item dates, no inference.** A capture in 1998 evidences 1998 and nothing else. A registry creation
  date evidences its own year only; continued registration needs its own record (Ding's rule 6).
- `domain_year.evidence_id` is `NOT NULL` and foreign-keys `evidence`, so no year can be written without
  naming the observation behind it. Master-eligible types: `prior_reused`, `cdx_timestamp`,
  `artifact_listing`, `link_source`, `dated_directory`, `whois_creation`. **`link_target` never dates a year.**
- **Corroboration split**: anything a human typed is admitted only if another source already dates that
  domain. Self-dating records take no split. The split does not check whether a hostname was ever real.
- **A master-eligible class needs a human `Decision:` line** in `docs/approved-sources-list.md` before it
  can date a year; `ark ingest` refuses otherwise. Generate the request with
  `scripts/harness/request_approval.py`. Candidate-only evidence needs no approval.
- **Quote net-new post-split equivalent-English, never gross.** Gross and net differ by more than 10x.

## Before pricing anything

**Check `docs/sources.md`.** It records every source and ~120 closed families with the measurement that
closed each. Do not re-test a closed family; do re-price a parked one, because an unbanked source decays
as the store grows (`ukwa_geoindex` fell 77,749 to 4,512 while it waited).

Check the dates fall inside 1996-2001 before counting contents. Real hostname counts on 1990-1992 files
have wasted days.

## Where state lives

| | |
|---|---|
| `docs/ROUND.md` | generated current state; read first, never edit |
| `docs/key-decisions.md` | the only place anything asks Ivo for a decision |
| `docs/approved-sources-list.md` | which classes may date a year; enforced by `ark ingest` |
| `docs/sources.md` | the register: every source, every closure, with its measurement |
| `docs/ding/`, `feedback-phase-*/`, `private/personal-context.md` | **his own words. Git-ignored, so grep will not find them.** Highest authority |

## Commands

```bash
just cycle                                       # health: collectors, yields, unbanked journals, approvals
uv run ark export && uv run ark check            # export first; one invariant reads the export
uv run python scripts/round/round_figures.py --verify   # re-score with HIS calculator before any send
just ship-approved                               # bank, report, export, gate, package, verify
```

## Rules

- Never `git push`. Commit coherent units on a non-`main` branch. No AI attribution in commits.
- **No em-dashes or en-dashes** anywhere.
- Gate before every commit, never through a pipe: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && uv run ark check`.
- Never edit `docs/SPEC.md`, `docs/report.md` (generated), frozen `submissions/phase-4|5/`, or `legacy/`.
  Keep all of `data/raw/`. `private/` never ships. **Big data must never reach git.**
- Archive citizenship: honest User-Agent with contact, honour `Retry-After`, back off on 429/503/504,
  **never a third heavy client** at `web.archive.org` while two are collecting.
- **Keep the collectors running**; an idle engine is the failure mode. VPS works `gap`, local works `pool`.
  A supervisor fixes its queue at startup, so a rebuilt queue needs a restart to take effect.
- Long-running work holds its own absolute deadline and survives the agent leaving. Restart any loop after
  editing a module it imports.

## Traps that each cost a day

- **Prove a negative against a known positive.** A search finding nothing and a search pointed at the
  wrong place look identical.
- **Verify every number, including a subagent's.** Several were fabricated or out by 1000x.
- **A running collector is not a working one**, and a supervisor's guess at why it stopped is not evidence.
  Presence is not progress; progress is not yield. `just cycle` checks yield.
- **Rank a queue by TLD weight alone and `.aaa`, `.like`, `.med` lead it.** They weigh 1.0 and were
  delegated in 2013. Require a volume floor before ranking on weight.
- **Measure rates over a trailing window, not a lifetime**, and never across a backfill.
- **Counting net-new against the store from an already-ingested journal returns zero by construction.**
- **Any name-shape filter over-catches**: `bl.uk` is the British Library, `x.com` is real.
- Look for an existing tool before writing one. A worse reimplementation of
  `build_promotion_journals.py` overstated a source 20x.
