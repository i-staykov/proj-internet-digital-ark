# Internet Digital Ark

## Rule 0: lean, or it is worthless

**These docs are the source of truth as of today. Never write how things were.** Git is the only
history. Verbosity is the enemy of quality: this is research for people with no time, and a longer
text is worth less. Say it once, as short as it can be said, then stop. **Never grow a file:** the
edit that adds a rule deletes the rule it replaces. No restating, no preamble, no AI slop.

**No posterity.** A decision is written as the fact it makes true, never as who made it or when.

---
Rebuild the domains that existed 1996-2001 for Prof. Ding, scored on **equivalent-English (EE)**:
each `(domain, year)` counts its TLD's English share. **EE and speed are the PROXY; the deliverable
is demonstrated research capability**, so a measured negative with a reason is a result and the
METHOD outranks the source.

**The annual masters are a WEBSITE-evidence product** (spec XIII). Only exact-host year-specific
web evidence enters `1996.txt`-`2001.txt`: an IA CDX capture, a dated snapshot, a dated web link-graph
record, or a custodian's per-host/year web-capture extract. DNS, registry, RDAP, WHOIS, mail and
Usenet headers and textual mentions are CANDIDATES, which are scored separately at the same rate.

**The 5% gate is a floor on sending and nothing ships under it.** We may ASK Ding to
accept less when the research side carries it; he decides. Never package a short round unasked.
Past the floor, submit at once. **Where the round stands is in `docs/ROUND.md`, generated.**

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
2. **GATHER CANDIDATES.** Both tracks score at the same rate and a candidate costs no dating
   argument, approval or evidence class. Both ship net-new against HIS files, diffed at export.
3. **Hunt a bulk dated HOSTNAME corpus that meets the XIII standard.**
4. Price what you find: net-new post-split EE against the store, dates inside 1996-2001.
5. `just sync` banks what clears the bar: it drains the fleet's findings, re-prices each
   confirmed FIND, writes the `Decision:` line or raises the approval, and pushes.
6. Log the result in `docs/registers/sources.md` whatever the answer, so nobody re-tests it.

## The ten rules

1. **Any branch but `main` may be pushed; `main` only by PR.** `origin` is PUBLIC, so a commit
   message names no host, IP, email body or personal context.
2. The hook gate (ruff, format, scan, pytest) on every commit, and ark check after every ingest and before every ship.
3. Never hand-edit the canonical brief in `docs/brief/ding/`; never edit `docs/report.md`, `docs/ROUND.md` or frozen `submissions/`.
4. `private/` never ships.
5. **Big data must never reach git.**
6. **Three archive clients maximum**: all three hold `web.archive.org/cdx`, two on the
   laptop and one on the VPS, and no agent may query it. The rest of archive.org is open to a
   research lane; no lane pauses a collector. Honest User-Agent, honour `Retry-After`. **On
   throttling, retire a client, never add one.**
7. **Autonomy.** A lead inside the standing size, terms, robots and class bounds gets its
   `Decision:` line from the loop and proceeds without approval; its register row and ledger line
   document it for review with the submission. Outside any bound it parks `pending`. The owner
   approves a new evidence class and every send. The bounds live once, in ark-fleet `policy.json` `standing`.
8. **Every source gets a LINK in `docs/registers/sources.md` before ingest**, beside the sentence
   saying what dates one item.
9. No AI attribution in commits.
10. **No em-dashes or en-dashes.**

## How to work

**Two hunts returning nothing: change the method, not the effort.** Ask what *kind* of artifact you
have never looked for, not which host you have not tried.

**One lens per cycle, never the same twice running.** Rotate even when the last one paid.
