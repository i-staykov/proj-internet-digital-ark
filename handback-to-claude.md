# Handback to Claude, 2026-08-23

**Read `.github/copilot-instructions.md` first, then `docs/ROUND.md`, then `docs/key-decisions.md`.**
This file only covers what changed while Copilot held the project, 2026-08-19 to 2026-08-23. It is a
snapshot and will rot; the register and the decision surface are the durable records.

## Where the round stands

**372,835 EE banked against a 668,118 gate: 55.8%.** It was about 88,000 when this stretch began. The
remaining 295,000 is querying time at the current rate, roughly a week, unless somebody finds a bulk
dated corpus. Nine separate hunts over four days did not.

**Measured rate: 2,680 EE an hour** over a clean window with everything running, down from 3,931 that
morning because the RDAP queue moved off store-known names (25.7 EE per thousand queries) and onto
Common Crawl names (4.2). Expect it to keep falling as the queue thins. The gate recedes about 893 an
hour.

## What is running right now

Seven jobs, all with absolute deadlines around 2026-08-30, all detached and surviving the agent going
away. `pgrep -f 'rdap_novel_run|supervise_cdx_pool|maintain.sh'` locally, and the same on the VPS.

| host | job | queue | size |
|---|---|---|---|
| local | `rdap_novel_run.sh` | `data/raw/rdap/fastq_local.txt` | 26,765,190 |
| local | `rdap_novel_run.sh` (name `rdap_registries`) | `data/raw/rdap/queue_registries.txt` | 705,346 |
| local | `supervise_cdx_pool.sh` | `data/raw/cdx/queue_master.txt` | 1,912,141 |
| local | `maintain.sh 900 150` and `cdx_suffix_bank.sh` | | |
| VPS | `rdap_novel_run.sh` | `data/raw/rdap/fastq_remote.txt` | 26,765,189 |
| VPS | `supervise_cdx_pool.sh` | `data/raw/cdx/queue_tightgap_ranked.txt` | 449,754 |

**Two archive clients only, never three.** The suffix sweep was stopped to make room for the link-hint
queue; that was deliberate, not a crash.

## The five things worth knowing

**1. RDAP failed silently on both machines for a full day and neither failure looked like one.** The
local run died with Python's `init_sys_streams: can't initialize sys standard streams`, a dead stdin
inherited from a terminal that had gone away, and the supervisor reported it as **"the list is
exhausted or the API refused"**. It was not exhausted: the round before had dated 138,783 of 200,000.
The VPS meanwhile was alive, and therefore looked healthy, while running at **1.92 queries a second
against the 95 the same code gets from `.com`**, because it had been pointed at an 8.2 million name
list spanning every registry and slow registries block the queue. Both now launch with stdin from
`/dev/null` and query `.com`/`.net` only. **A collector that is running is not a collector that is
working, and a supervisor's guess at why it stopped is not evidence.**

**2. Point RDAP at the store, not at novel names.** Measured, four to one: domains the store already
holds but has never asked return **25.7 EE per thousand**, names it has never seen return **6.3**,
because a domain the store has never seen is precisely one that did not exist in 1996-2001. Common
Crawl domain vertex files were admitted as bulk *candidate supply* (not as a dating source, which stays
closed): 88.6 million domains, 41 million never seen, piloted at 4.2 EE per thousand.

**3. Ivo caught me proposing something his brief forbids, and he was right.** I priced a "registration
span" at **1,704,843 EE, 2.5 times the whole gate**: treat an RDAP creation date plus the fact the
domain answers today as an interval and assign every year from creation onward. **Rule 6 forbids it**:
a creation date "alone does not automatically establish that the domain remained registered", and a
later annual file "still requires a WHOIS record demonstrating continued registration in that year".
Rules 1 and 7 say the same, and we had already told him in writing on 2026-08-17 that creation dates
were "used strictly as specified: a creation date in 1998 writes 1998 and no other year". **I measured
the prize before reading the rule. The rule took four minutes to find.**

That check exposed **O7**, which is still open and still needs Ding: `afnic_fr` assigns whole
intervals, and where AFNIC publishes a withdrawal date the registry is positively asserting
registration across it, so those 25,429 pairs are safe. But **54,632 assigned pairs are open-ended and
beyond the creation year**, resting on creation plus current existence, which is what rule 6 says is
not enough. Those are already shipped. The two cases stand or fall together.

**4. I put a wrong number on Ivo's decision surface and had to withdraw it.** I claimed `link_target`
was worth **97,893 EE**; it is worth about **5,000**, now banked. My query asked whether a pair's
domain appears anywhere in `domain_year` and **did not exclude the corpus from corroborating itself**.
`scripts/build_promotion_journals.py` already implements this exact rule with three filters I skipped,
one of which alone rejects 35%. **The tool that got it right was already in the repository, written for
this exact question, and I reimplemented a worse version instead of looking.**

The accuracy work behind it does stand and is genuinely useful: a link's year is confirmed **85.3%** of
the time by Ding's own baseline against a **37.1%** shifted-year control. Using links to decide *which
questions to ask the archive* measured **297 EE per thousand queries, 63 times the RDAP queue**, and
needs no approval because the evidence written is `cdx_timestamp`.

**5. 575,417 candidates in the pool cannot exist**, names like `tfvkrp.mil` and `sypwlusx.edu` under
namespaces that never allowed arbitrary registration, 462,155 of them from Usenet address extraction,
so the cause is anti-spam munging and garbled quoting. **The evidence wall held completely: every
shipped `.mil`, `.gov` and `.edu` domain, 826, 6,679 and 25,155 of them, carries independent
attestation. 100.0%, zero on mention evidence alone**, on the three highest-weighted namespaces in the
model. It costs queries, not credibility. They are excluded from queues rather than deleted, and a
tighter address extractor would stop them accumulating. That is **O9**.

## Source families closed, all on measurement

Added to `docs/sources.md` with the working: the CDX public-suffix sweep (works as a mechanism, 4,800
EE, not a channel, because the bare TLD is HTTP 403 so `.com` cannot be enumerated); every RIR database
(GDPR dummification leaves exactly one email domain, `ripe.net`, across 64,310 objects); dated CD-ROM
media, browser installers, BackPAN and Debian historical (~3,000 EE total); `textfiles.com` and FidoNet
nodelists (**rejected on date, not content**: real hostname counts, every file dated 1990-1992);
non-Verisign RDAP registries (17 candidate TLDs have no RDAP endpoint at all, which removes 1.24
million `.de` names from RDAP's reach; PIR blocks us; `.au` and `.pl` publish nothing datable).

**`ukwa_geoindex` decayed from 77,749 EE to 4,512 while it waited for approval**, because our own `.uk`
suffix sweeps banked that population through a different door. **The value of an unbanked source decays
as the store grows**, so re-price anything parked pending a decision before quoting it. Assume
`internic_zone`'s 8,628 is stale the same way.

## Traps worth inheriting

- **Gross yield and net yield differ by more than an order of magnitude.** Registries look spectacular
  on gross rate (`.sg` 341, `.info` 336, `.ca` 234 EE per thousand against Verisign's 4.75) and the
  population they were measured on is **97.9% already dated**. Measured net on full-headroom names,
  `.ca` is 7.7. **1.6x, not 20x.**
- **Per-query yield and total yield point opposite ways.** A link-hinted archive query is worth 60
  times an RDAP query, and the archive answers ~15,000 a day against the registries' 17 million, so
  RDAP still delivers ~80,000 EE a day against the archive queues' ~6,400. **I wrote the opposite on
  the decision surface and had to correct it within the hour.**
- **Ranking a queue by TLD weight alone puts `.aaa`, `.like`, `.med`, `.gu` at the head.** They weigh
  1.0 because they are English namespaces and are worth nothing, since the new gTLDs were delegated in
  2013 or later. Require a volume floor inside the queue before ranking on weight.
- **A rate measured across a backfill is not a rate.** The first measurement after the internet gap
  read 8,769 EE an hour and was mostly the VPS backlog being ingested.
- **Subagents fabricate numbers.** One synthesised a per-registry table "based on documented registry
  behavior" whose PIR figure the codebase contradicts; two made 1000x arithmetic errors; one reported
  a source as viable without checking its dates were in window. **Verify every number a subagent
  returns before acting on it.**

## What I would do next

1. **Get answers to O7 and O9.** O7 is the only open question that could move the round materially, in
   either direction, and it is Ding's rule to interpret.
2. **Keep the engines fed.** The queues hold about a week. `just cycle` checks yield; presence is not
   progress.
3. **Keep hunting a bulk dated corpus.** Per-domain querying cannot reach the gate, and that is now
   confirmed by our own measurements rather than inherited from the brief. Everything else is arithmetic
   on a receding target.

Nothing was pushed. Branch `phase-6`, latest `f186be4`, gate green on every commit.
