# Rules

**The standing rules, one line each, grouped by family.** The reasoning behind a rule is in [key-decisions.md](key-decisions.md) and [ADRs.md](ADRs.md); the measured laws are in [laws.md](laws.md) and the mistakes in [traps.md](traps.md). Cut from `CLAUDE.md` on 2026-09-02, and from `.github/copilot-instructions.md` on 2026-09-03, which is now a pointer.

## Evidence standard

- Per-item dates inside 1996-2001: check the dates before counting the contents.
- `domain_year.evidence_id` is `NOT NULL` and foreign-keys `evidence`; no year without an observation.
- Master-eligible classes: `prior_reused`, `cdx_timestamp`, `artifact_listing`, `link_source`, `dated_directory`, `whois_creation`; `link_target` never dates a year.
- Corroboration split: anything a human typed needs another source to date that domain first. A self-dating record takes no split, and the split tests dating only, never whether the name was ever real.
- A creation date evidences its own year only; continued registration needs its own record (rule 6).
- Undated is fatal, and so are terms we do not hold; small, ugly or hard to parse is not a reason to reject, and a 25 EE source is admitted and gets one line.
- Hostnames stand behind the same wall: `hostname_year` foreign-keys `evidence`, `ark ingest-hostnames` fills it from raw CDX capture journals, and two checks gate it.

## Scoring

- Each `(domain, year)` counts its TLD's English share: `.uk` 0.9813, `.com` 0.6321, `.net` 0.4530, `.de` 0.1324; non-English ccTLDs are worthless.
- Registrable domains are the prioritised unit; every distinct evidence-backed valid hostname beneath a held registrable ships too, in `NNNN_hostnames.txt`, and his calculator counts it at full TLD weight (Ding, 2026-09-01).
- Quote net-new post-split EE, never gross: they differ by more than 10x.
- Price before proposing: net-new EE against the store, dates inside 1996-2001.
- 5% is a hard trigger (round 6 crossed it on 2026-08-26), and the task does not end at a gate: keep collecting until the discoverable sources are exhausted, and submit early, because percentages add and the denominator grows.
- EE and speed are the proxy; the deliverable is demonstrated research capability, so a measured negative with a reason is a result and the method that found a source outranks the source (Ivo, 2026-08-27). Run independent hypotheses in parallel: keep what works, document what does not, move to the next.
- Where the round stands is in `docs/ROUND.md`, which is generated; never state it in a hand-written page.

## Cost

- **No local recipe spawns a model. Model work runs in the fleet, under the primary token** (Ivo, 2026-09-04). A local `claude -p` authenticates with the LAPTOP'S own Claude login, which is the Taktile account and has API pricing enabled, so an agent that costs an allowance in the fleet costs real money here. `just bank`'s admitter is the one place this existed; it is now opt-in via `ARK_LOCAL_ADMITTER=1` and off by default.
- The fleet's own token is `CLAUDE_CODE_OAUTH_TOKEN_PRIMARY`, the HPI account: limits, no API billing. `CLAUDE_CODE_OAUTH_TOKEN` is Ivo's personal one and is reached only when the repository variable `ARK_USE_FALLBACK_TOKEN` is `1`, which is unset and should stay unset. CI already refuses a workflow that does not name the primary secret.

## Engines and politeness

- Two archive clients maximum.
- Honest User-Agent, honour `Retry-After`, back off on 429/503/504.
- Read the terms in full before the first request, and the whole robots.txt of the host in the download URL. The RDAP episode cost the biggest route because nobody read the terms, and time pressure does not reopen that.
- Collectors take an absolute deadline and outlive the session; restart a loop after editing what it imports.
- Look for the existing tool before writing one.

## Hunting

- **The standing priority (Ivo, 2026-09-04): bulk HOSTNAME sources first, and hostnames for domains we ALREADY HOLD before hostnames for new ones. Reserve some capacity for new registrables, never all of it.** The arithmetic behind it: the same thirteen Usenet pools paid 35.8 EE at registrable grain and 119,640 at hostname grain, and a held registrable needs no discovery, no corroboration split and no new approval, so a domain-wide archive query over names already in the store is the shortest path from a request to a record. `scripts/engines/platform_sweep.sh` over `rank_platform_parents.py` is that lane; the registrable reserve is what stops the pool from starving and the method from narrowing to one shape.
- One lens per cycle, never the same lens twice running; rotate even when the last one paid.
- If two hunts in a row return nothing, change the method, not the effort: widen the lens, not the list, and ask what *kind* of artifact has never been looked for, not which host has not been tried.
- Rewrite the wake-up wording when a lens stalls, and re-price parked sources, because an unbanked source decays as the store grows.
- Never re-test a closed family, and never grind an old source because it is familiar.
- Breadth is on Ding's own list ([ding/project-brief.md](ding/project-brief.md)), and he expects each shape tried and reported: dated directories and navigation sites, national web-archive indexes and link graphs, academic repositories and DOI datasets (UMN DRUM is his worked example), paper supplements and replication packages, registry datasets, government open data, mailing-list archives, preserved software and documentation collections, outbound-link expansion from pages already held, and automated dataset discovery over repository APIs.

## Registers

- Every source gets a link in `docs/sources.md` before it is ingested, beside the sentence saying what dates one item and why it clears the bar (Ivo, 2026-08-31).
- Log every result in `docs/sources.md`, positive or negative, so nobody re-tests it.
- A master-eligible class needs a human `Decision:` line in `docs/approved-sources-list.md`; candidate-only needs nothing.
- The loop may write the `Decision:` line itself when all four hold: the evidence type is already master-eligible, a machine-written stamp inside the artifact dates one item and is quoted, the terms permit it, and `ark check` passes after the ingest (Ivo, 2026-08-29); failing any one parks the source as `pending`.
- **The bar is 10,000 EE net-new (Ivo, 2026-09-04), raised from 5,000.** It ranks rather than vetoes, as it has since 2026-08-18, but a lead whose measured ceiling is four figures is now logged and left. The raise is not a higher standard of proof: the hostname unit made bulk corpora worth an order of magnitude more than they were, the denominator outgrows any small source, and **speed is the constraint**. Hunt bulk hostname-dense corpora first, and price a lead's ceiling before its detail.
- Write-up length scales with yield: under the bar is one line in `sources.md` with the link, the dating sentence and the figure; over it earns the full treatment.
- **A new update or baseline from him is not a new phase** (Ivo, 2026-09-04). `feedback/feedback-phase-N/` is opened by his SCORED FEEDBACK on a submission, and every package that arrives before the next one is filed inside the phase we are working in. Phase 7 is the last phase with feedback; phase 8 is where we are, and the 0902V3, 0903V3 and 0904 packages all belong to it.

## Report and delivery

- The report is drafted as findings land, never reconstructed later: a five-figure source banks together with its paragraph in `docs/report.template.md`.
- `README.md` stays a one-screen front page; the runbook is [runbook.md](runbook.md).
- Never edit `docs/SPEC.md`, `docs/report.md` or frozen `submissions/`.
- `ark export` before `ark check`.
- `private/` never ships, and big data must never reach git.
- Verbosity is the opposite of quality: keep instructions, wake-ups and agent prompts short, direct, simple.

## Pushing and commits

- Gate before every commit, never through a pipe: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && uv run ark check`.
- A clone with no `data/ark.duckdb` can run only the code half. `ark export` and `ark check` raise
  `CatalogException: Table with name domain_year does not exist` there, and that is the store being
  absent rather than an invariant failing: big data never reaches git, so a fresh clone never has one
  (measured in the fresh-session test, 2026-09-03).
- Any branch except `main` may be pushed, and `main` is reached only by a PR; `main` is never pushed directly by any agent (Ivo, 2026-09-03).
- **An agent MAY merge its own PR once CI is green, on either repository (Ivo, 2026-09-04).** The rule was always that `main` is reached by a PR and never by a direct push, and merging a green PR satisfies it; waiting for Ivo to click was habit, not rule. Merge only your own, only green, and never one that raises a question only he can answer.
- `origin` is public, so a commit message names no hosts, no IP addresses, no email bodies and no personal context.
- No AI attribution in commits.
- No em-dashes or en-dashes anywhere.
