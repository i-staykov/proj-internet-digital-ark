# Internet Digital Ark

Rebuild the list of domains that existed 1996-2001 for Prof. Ding, scored on **equivalent-English
(EE)**: each `(domain, year)` counts its TLD's English share. **EE and speed are the PROXY. The
deliverable is demonstrated research capability**: autonomous, creative, intelligent discovery (Ivo,
2026-08-27), so a measured negative with a reason is a result and the METHOD outranks the source.
**The 5% gate is hard and NOTHING IS SUBMITTED UNDER IT** (Ivo, 2026-09-08, C-78): a floor on
sending, not a target, "there definitely are 5% to find". Never offer to package a short round.
Past the floor, submit at once and keep collecting: percentages add and the denominator grows.
The first priority does not soften the gate: it decides what to do with the hours that find no
outlier. **Where the round stands is in `docs/ROUND.md`, generated. Never state it here.**

## Before task X, read page Y

| doing this | read |
|---|---|
| pricing a source | [docs/lore/laws.md](docs/lore/laws.md) |
| touching a number | [docs/lore/traps.md](docs/lore/traps.md) |
| an ingest or a commit | [docs/lore/rules.md](docs/lore/rules.md) |
| running anything | [docs/ops/runbook.md](docs/ops/runbook.md) |
| quoting a round figure | `docs/ROUND.md` |
| proposing a lens | [docs/registers/sources-closed.md](docs/registers/sources-closed.md), then grep [docs/registers/sources.md](docs/registers/sources.md) |

Every page is listed in [docs/index.md](docs/index.md). Decisions: [docs/lore/key-decisions.md](docs/lore/key-decisions.md).

## When prompted, in this order

1. `just cycle`. Fix anything it flags that a program cannot decide.
2. **Two tracks are scored, not one (his 0906 update), so GATHERING CANDIDATES IS A PRIORITY,
   not a by-product.** Annual files and the CANDIDATE POOL are "measured and ranked separately",
   both `S = 10 x (p / t)` over the same annual denominator, so a candidate point is worth an
   annual point and costs far less: no dating argument, no approval line, no evidence class. A
   lane producing names it cannot date has still produced a scored result. **Both tracks ship
   net-new against HIS files, never our copy**, diffed at export time.
3. **Hunt a bulk dated HOSTNAME corpus, and harvest hostnames under names we already hold.**
   The standing priority (Ivo, 2026-09-04); `just hostnames <epoch>` starts that lane. **The
   sweep's 193,000 EE/client-hour is a PEAK, not a rate** (C-77: 210 EE/hour two nights on). The
   token window goes to the workflows; collectors run beside them, checked sporadically.
4. Price what you find: net-new post-split EE against the store, dates inside 1996-2001.
5. `just sync` banks what clears the bar: it drains the fleet's findings, re-prices each
   confirmed FIND, writes the `Decision:` line or raises the approval, and pushes.
6. Log the result in `docs/registers/sources.md` whatever the answer, so nobody re-tests it.

## The ten rules that bind every session

1. **Pushing (Ivo, 2026-09-03): any branch except `main` may be pushed; `main` only by PR.**
   `origin` is PUBLIC, `i-staykov/proj-internet-digital-ark`, kept public deliberately as a
   portfolio, so every pushed commit and its message is world-readable the moment it lands.
   That is what the freedom costs: a commit message names no hosts, no IP addresses, no email
   bodies and no personal context (`docs/ROUND.md` is ignored precisely because it embeds the
   VPS address, and a message must not re-leak that). No agent pushes `main`; protection binds.
2. Gate before every commit, never through a pipe:
   `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && uv run ark check`,
   with `ark export` before `ark check`.
3. Never hand-edit the canonical brief in `docs/brief/ding/`; never edit `docs/report.md`, `docs/ROUND.md` or frozen `submissions/`.
4. `private/` never ships.
5. **Big data must never reach git.**
6. **Two archive clients maximum, and the limit binds the CDX CHANNEL** (C-77): the collectors
   hold `web.archive.org/cdx` and no agent may query it, the rest of archive.org is open to a
   research lane, and no lane pauses a collector. Honest User-Agent, honour `Retry-After`.
7. **The standing approval rule (Ivo, 2026-08-29): the loop writes the `Decision:` line itself,
   citing this rule, when all four hold**: the class is already master-eligible, a machine-written
   stamp inside the artifact dates one item and is quoted, the terms permit it, and `ark check`
   passes after the ingest. Failing any one parks it `pending`; undated and terms we do not hold
   stay fatal.
8. **Every source gets a LINK in `docs/registers/sources.md` before it is ingested** (Ivo, 2026-08-31), next to
   the sentence saying what dates one item and why it clears the bar.
9. No AI attribution in commits.
10. **No em-dashes or en-dashes.**

## How to work

**Verbosity is the opposite of quality.** Keep instructions, wake-ups and agent prompts short, direct,
simple. If a rule takes a paragraph, it is being over-explained.

**If two hunts in a row return nothing, change the method, not the effort.** Widen the lens, not the
list: ask what *kind* of artifact you have never looked for, not which host you have not tried.

**One lens per cycle, and never the same lens twice running.** Rotate even when the last one paid.
