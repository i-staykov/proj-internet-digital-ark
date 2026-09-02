# Rules

**The standing rules, one line each, grouped by family.** The reasoning behind a rule is in [key-decisions.md](key-decisions.md) and [ADRs.md](ADRs.md); the measured laws are in [laws.md](laws.md) and the mistakes in [traps.md](traps.md). Cut from `CLAUDE.md` on 2026-09-02.

## Evidence standard

- Per-item dates inside 1996-2001: check the dates before counting the contents.
- `domain_year.evidence_id` is `NOT NULL` and foreign-keys `evidence`; no year without an observation.
- Master-eligible classes: `prior_reused`, `cdx_timestamp`, `artifact_listing`, `link_source`, `dated_directory`, `whois_creation`; `link_target` never dates a year.
- Corroboration split: anything a human typed needs another source to date that domain first.
- A creation date evidences its own year only; continued registration needs its own record (rule 6).
- Undated is fatal, and so are terms we do not hold; small, ugly or hard to parse is not a reason to reject, and a 25 EE source is admitted and gets one line.
- Hostnames stand behind the same wall: `hostname_year` foreign-keys `evidence`, `ark ingest-hostnames` fills it from raw CDX capture journals, and two checks gate it.

## Scoring

- Each `(domain, year)` counts its TLD's English share: `.uk` 0.9813, `.com` 0.6321, `.net` 0.4530, `.de` 0.1324; non-English ccTLDs are worthless.
- Registrable domains are the prioritised unit; every distinct evidence-backed valid hostname beneath a held registrable ships too, in `NNNN_hostnames.txt`, and his calculator counts it at full TLD weight (Ding, 2026-09-01).
- Quote net-new post-split EE, never gross: they differ by more than 10x.
- Price before proposing: net-new EE against the store, dates inside 1996-2001.
- 5% is a hard trigger (round 6 crossed it on 2026-08-26), and the task does not end at a gate: keep collecting until the discoverable sources are exhausted, and submit early, because percentages add and the denominator grows.
- EE and speed are the proxy; the deliverable is demonstrated research capability, so a measured negative with a reason is a result and the method that found a source outranks the source (Ivo, 2026-08-27).
- Where the round stands is in `docs/ROUND.md`, which is generated; never state it in a hand-written page.

## Engines and politeness

- Two archive clients maximum.
- Honest User-Agent, honour `Retry-After`, back off on 429/503/504.
- Read the terms in full before the first request, and the whole robots.txt of the host in the download URL.
- Collectors take an absolute deadline and outlive the session; restart a loop after editing what it imports.
- Look for the existing tool before writing one.

## Registers

- Every source gets a link in `docs/sources.md` before it is ingested, beside the sentence saying what dates one item and why it clears the bar (Ivo, 2026-08-31).
- Log every result in `docs/sources.md`, positive or negative, so nobody re-tests it.
- A master-eligible class needs a human `Decision:` line in `docs/approved-sources-list.md`; candidate-only needs nothing.
- The loop may write the `Decision:` line itself when all four hold: the evidence type is already master-eligible, a machine-written stamp inside the artifact dates one item and is quoted, the terms permit it, and `ark check` passes after the ingest (Ivo, 2026-08-29); failing any one parks the source as `pending`.
- Write-up length scales with yield: under 5,000 EE is one line in `sources.md` with the link, the dating sentence and the figure; over it earns the full treatment.
- One lens per cycle, never the same lens twice running; if two hunts in a row return nothing, change the method, not the effort.

## Report and delivery

- The report is drafted as findings land, never reconstructed later: a five-figure source banks together with its paragraph in `docs/report.template.md`.
- `README.md` stays a one-screen front page; the runbook is [runbook.md](runbook.md).
- Never edit `docs/SPEC.md`, `docs/report.md` or frozen `submissions/`.
- `ark export` before `ark check`.
- `private/` never ships, and big data must never reach git.
- Verbosity is the opposite of quality: keep instructions, wake-ups and agent prompts short, direct, simple.

## Pushing and commits

- Gate before every commit, never through a pipe: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && uv run ark check`.
- Only the fleet's bank job pushes, and only the fleet branch; interactive sessions never push unless Ivo asks; `main` is never pushed by any agent (Ivo, 2026-09-01).
- `origin` is public, so a commit message names no hosts, no IP addresses, no email bodies and no personal context.
- No AI attribution in commits.
- No em-dashes or en-dashes anywhere.
