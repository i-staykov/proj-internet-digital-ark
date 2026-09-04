# Internet Digital Ark

Rebuild the list of domains that existed 1996-2001 for Prof. Ding, scored on **equivalent-English
(EE)**: each `(domain, year)` counts its TLD's English share. **EE and speed are the PROXY. The
deliverable is demonstrated research capability**: autonomous, creative, intelligent discovery (Ivo,
2026-08-27), so a measured negative with a reason is a result and the METHOD outranks the source.
**The 5% gate is hard**, and the first priority does not soften it: it decides what to do with the
hours that find no outlier.

**Where the round stands is in `docs/ROUND.md`, which is generated. Never state it here.** The task
does not end at a gate: keep collecting until the discoverable sources are exhausted, and submit
early, because percentages add and the denominator grows.

## Before task X, read page Y

| doing this | read |
|---|---|
| pricing a source | [docs/laws.md](docs/laws.md) |
| touching a number | [docs/traps.md](docs/traps.md) |
| an ingest or a commit | [docs/rules.md](docs/rules.md) |
| running anything | [docs/runbook.md](docs/runbook.md) |
| quoting a round figure | `docs/ROUND.md` |
| proposing a lens | [docs/sources-closed.md](docs/sources-closed.md), then grep [docs/sources.md](docs/sources.md) |

Every page is listed in [docs/index.md](docs/index.md). Decisions: [docs/key-decisions.md](docs/key-decisions.md).

## When prompted, in this order

1. `just cycle`. Fix anything it flags that a program cannot decide.
2. **Hunt a bulk dated HOSTNAME corpus, and harvest hostnames under names we already hold.**
   That is the standing priority (Ivo, 2026-09-04), with some capacity reserved for new
   registrables. A per-domain gap query pays 255 EE/hour; a domain-wide sweep over names we
   already hold paid 193,000 EE per client-hour on 2026-09-04, because one answer carries
   thousands of records instead of one pair. `just hostnames <epoch>` starts that lane.
3. Price what you find: net-new post-split EE against the store, dates inside 1996-2001.
4. Bank what clears the bar. Raise an approval request only if the class is master-eligible.
5. Log the result in `docs/sources.md` whatever the answer, so nobody re-tests it.

## The ten rules that bind every session

1. **Pushing (amended by Ivo, 2026-09-03): any branch except `main` may be pushed, and `main`
   is reached only by a PR.** `origin` is PUBLIC, `i-staykov/proj-internet-digital-ark`, kept
   public deliberately as a portfolio, so every pushed commit and its message is world-readable
   the moment it lands. That is what the freedom costs: a commit message names no hosts, no IP
   addresses, no email bodies and no personal context (`docs/ROUND.md` is ignored precisely
   because it embeds the VPS address, and a commit message must not re-leak what the ignore
   protects). `main` is never pushed by any agent, and branch protection enforces it.
2. Gate before every commit, never through a pipe:
   `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && uv run ark check`,
   with `ark export` before `ark check`.
3. Never edit `docs/SPEC.md`, `docs/report.md`, `docs/ROUND.md` or frozen `submissions/`.
4. `private/` never ships.
5. **Big data must never reach git.**
6. Two archive clients maximum. Honest User-Agent, honour `Retry-After`, back off on 429/503/504.
7. **The standing approval rule (Ivo, 2026-08-29): the loop writes the `Decision:` line itself, citing
   this rule, when all four hold**: the class is already master-eligible, a machine-written stamp
   inside the artifact dates one item and is quoted, the terms permit it, and `ark check` passes after
   the ingest. Failing any one parks the source as `pending`. Undated is still fatal, and so are terms
   we do not hold.
8. **Every source gets a LINK in `docs/sources.md` before it is ingested** (Ivo, 2026-08-31), next to
   the sentence saying what dates one item and why it clears the bar.
9. No AI attribution in commits.
10. **No em-dashes or en-dashes.**

## How to work

**Verbosity is the opposite of quality.** Keep instructions, wake-ups and agent prompts short, direct,
simple. If a rule takes a paragraph, it is being over-explained.

**If two hunts in a row return nothing, change the method, not the effort.** Widen the lens, not the
list: ask what *kind* of artifact you have never looked for, not which host you have not tried.

**One lens per cycle, and never the same lens twice running.** Rotate even when the last one paid.
