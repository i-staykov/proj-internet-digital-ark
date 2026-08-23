# Internet Digital Ark

Rebuild the list of domains that existed 1996-2001 for Prof. Ding. Scored on **equivalent-English (EE)**:
each `(domain, year)` counts its TLD's English share. `.uk` 0.9813, `.com` 0.6321, `.net` 0.4530,
`.de` 0.1324. Non-English ccTLDs are worthless.

**Now: gate 668,118 EE (5% of `merged260821`). We hold ~373,000. Need ~295,000 more.**

## When prompted, in this order

1. `just cycle`. Fix anything it flags that a program cannot decide.
2. **Hunt a bulk dated corpus.** This is the job. Querying adds ~3,000 EE/hour and cannot close the gap.
3. Price what you find: net-new EE against the store, dates inside 1996-2001, before proposing anything.
4. Bank what clears the bar. Raise an approval request only if the class is master-eligible.
5. Log the result in `docs/sources.md` whatever the answer, so nobody re-tests it.

## The bar for admitting a source

- **Per-item dates inside 1996-2001.** Check the dates before counting the contents.
- `domain_year.evidence_id` is `NOT NULL` and foreign-keys `evidence`. No year without an observation.
- Master-eligible: `prior_reused`, `cdx_timestamp`, `artifact_listing`, `link_source`, `dated_directory`,
  `whois_creation`. **`link_target` never dates a year.**
- **Corroboration split**: anything a human typed needs another source to date that domain first.
- A creation date evidences its own year only. Continued registration needs its own record (rule 6).
- A master-eligible class needs a human `Decision:` line in `docs/approved-sources-list.md`.
  Candidate-only needs nothing.
- **Quote net-new post-split EE, never gross.** They differ by more than 10x.

## Method, and when to change it

**Verbosity is the opposite of quality.** Keep instructions, wake-ups and agent prompts short, direct,
simple. If a rule takes a paragraph, it is being over-explained.

**If two hunts in a row return nothing, change the method, not the effort.** Widen the lens, not the
list: ask what *kind* of artifact you have never looked for, not which host you have not tried. Rewrite
the wake-up wording. Re-price parked sources, since an unbanked source decays as the store grows.
Never re-test a closed family; never grind an old source because it is familiar.

## Rules

- Never `git push`. Non-`main` branch only. No AI attribution in commits. **No em-dashes or en-dashes.**
- Gate before every commit, never through a pipe:
  `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && uv run ark check`
- `ark export` before `ark check`. Never edit `docs/SPEC.md`, `docs/report.md`, frozen `submissions/`.
- `private/` never ships. **Big data must never reach git.**
- Two archive clients maximum. Honest User-Agent, honour `Retry-After`, back off on 429/503/504.
- Collectors take an absolute deadline and outlive the session. Restart a loop after editing what it imports.

## Traps

- **Prove a negative against a known positive.** Nothing-found and pointed-wrong look identical.
- **Verify every number, including a subagent's.** Several were fabricated or out by 1000x.
- **An already-ingested journal shows 0 net-new by construction.** Measure against a pre-ingest snapshot.
- A running collector is not a working one. Presence, progress and yield are three questions.
- Rank a queue by TLD weight alone and 2013 gTLDs lead it. Volume floor first.
- Any name-shape filter over-catches: `bl.uk` is the British Library, `x.com` is real.
- Look for the existing tool before writing one.

Details: `.github/copilot-instructions.md`. State: `docs/ROUND.md`. Decisions: `docs/key-decisions.md`.
