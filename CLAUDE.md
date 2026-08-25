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

## Breadth, on Ding's own list

He asks for all of these and expects each to be tried and reported, positive or negative: dated
directories and navigation sites, national web-archive indexes and link graphs, academic repositories
and DOI datasets (UMN DRUM is his worked example), paper supplements and replication packages, registry
datasets, government open data, mailing-list archives, preserved software and documentation
collections, outbound-link expansion from pages already held, and automated dataset discovery over
repository APIs.

**One lens per cycle, and never the same lens twice running.** Rotate even when the last one paid.
A run of nothing is a signal to move sideways, not to push harder on the same shape.

## What kills a source, before you download it

`discovery.md` has the three measured laws. In one line each, plus what has closed since:

1. IA-derived cannot be net-new: the baseline is IA-derived too.
2. Listing a name proves the artifact's date, not that the name was live.
3. A trust-selected corpus holds authorities, not hosts.
4. A current-state snapshot cannot evidence a past year.
5. Human-typed novel names take the split and earn no year.
6. Anonymised or hashed hostnames are worth nothing: ask for the sanitisation paragraph first.
7. Dating and URL-bearing anticorrelate: a record naming a site is one somebody has since edited.
8. Overlap with the baseline corroborates a reading; it never justifies one (Ivo, 2026-08-24).
   The grounds must be what dates the item: the artifact asserting a state at an instant it
   stamps itself, and a capture fixing when it existed. Agreement with `prior_task` is a check
   on that argument, and cited only after it.

Prose density ceiling: ~0.042 net-new pairs per item, so ~119,000 items to clear the bar. Ask what the
corpus is *about* before trusting even that.

**Density and authority are two INDEPENDENT screens and a corpus must pass both.** Formal prose fails
the first: Hansard is 3.26M words per 5 URLs, 0.00153 URLs per 1,000 words. Grey literature passes it
emphatically at **221x that rate** (ERIC, 0.339 per 1,000 words) and then fails the second at 93.0%
already held, because program reports print the URLs of institutions we already have. Measure BOTH on
a sample before pricing any prose corpus, and expect `.edu` and `.gov` to die to the split: ERIC held
184 `.edu` pairs and exactly one survived.

**Under the split, a list's EE is (held domains) x (years it can add). Novelty above ~50% is a COST.**
A novel name earns no year, so what pays is a LONG-RUNNING dated series over a population we already
hold: junkfilter spans 13 editions 1997-2001 and paid 2,189 EE, while a two-year list over the same
population paid 120, its held domains already carrying 1997 at 93.0% and 1998 at 91.4%. Ask how many
YEARS an artifact can add before asking how many names it has.

**Adversarial selection inverts killer 3, but ONLY if the adversary did not crawl.** Ask what channel
fed it. Mail received or whois transcribed pays: junkfilter 50.4% already-held, SpamEater 59.1%, a
typosquat listing 25.8%. Anything that learned its names by following links inherits the crawler's
own population and pays nothing: a squidGuard robot list whose header says it was compiled from
739,695 crawled links is 99.47% held and worth 18 EE. Visitor logs are the same failure by another
route, 98.4% and 99.6%, because the hostname is reverse DNS and the long tail resolves to its ISP.

Curated-directory floor, measured over four artifacts: 0.013 to 0.024 net-new post-split pairs per
LISTED domain, at 0.39 to 0.70 EE per pair. So 1,000 EE needs 83,000+ listed domains in one artifact.
For a human-curated list, novelty and datability are mutually exclusive: what we lack takes the split,
what survives the split we already hold. Ask whether the lister held the database, not how long the list is.

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
- **Grep `sources.md` before briefing an agent, not after.** A lens described as untried when it is
  closed three times over wastes the run and teaches the agent to distrust the brief.

Details: `.github/copilot-instructions.md`. State: `docs/ROUND.md`. Decisions: `docs/key-decisions.md`.
