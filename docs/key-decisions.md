# Decisions

**One surface asks Ivo for things, and it is this file** (ADR-005). Two lines per ask: what is needed and
what it is worth. If an entry needs a third line, it is being over-explained. He decides; the agent
measures. Closed decisions are one line each, because the decision is what binds and the reasoning is in
the git log and, for sources, in `sources.md` with its measurement.

## OPEN

### Approve, refuse or downgrade usenet_header_fqdn_hostnames / link_source

Server-written Usenet header hostnames (`X-Trace`, `NNTP-Posting-Host`, final `Path` hop) at hostname grain, fleet-measured at **2,368 EE on one 28 MB demon.* probe**, not re-priced on the live store because the probe table was deleted and the bytes are on the VPS. Parks on conditions 1 and 4: no master-eligible class covers a server-written header hostname without the split the banked Usenet classes take, and no journal exists to ingest. Ding's 2026-09-01 update lists dated Usenet copies as unsuitable, so the fleet recommends asking him first. Issue 2 on ark-fleet carries the block.

Worth: 2,368 EE measured, 20,000 to 25,000 EE projected for demon.* alone, unmeasured.

### Approve, refuse or downgrade internic_zone_hostnames_1999 / artifact_listing

The nameserver targets of the 1999 `edu` and `gov` zones at hostname grain, the lane banked today for 1997 at 11,860.7 EE. Priced on the live store 2026-09-02 at **4,678.2 EE over 6,650 (hostname, 1999) records**. It parks on condition 3 of the standing rule, terms: the files came off `tomocha.net`, whose ClaudeBot refusal is the open question above, and the 1999 `edu` file itself opens with Network Solutions' access-agreement notice. The bytes are on disk, nothing is fetched by deciding. `approved-sources-list.md` has the block; issue 1 on ark-fleet carries it.

Worth: 4,678.2 EE. This sharpens the tomocha question from 0 EE to a figure.

### Write to Verisign, PIR or Nominet, or leave the RDAP route closed

Every registry this project has queried by RDAP publishes terms inside the response, and all four read so far prohibit high-volume automated querying: Verisign, PIR and CIRA with a registration-only carve-out, Nominet with none plus a ban on using the extracted contents at all. Both engines were stopped on 2026-08-27 and `ark rdap` now refuses those TLDs in code. The route was half of phase 6's equivalent-English, so a written permission of the RIPE kind is the only thing that reopens it.

Worth: the route's future. Stopping costs 851.0 EE of unshipped pairs and nothing already credited; `approved-sources-list.md` has the quotes and the per-registry figures.

Sharpened 2026-08-30 by the registry-permission screen in `sources.md`: ask Nominet not for RDAP relief but for a two-column extract, domain name and registration date, for `.uk` names registered before 1 January 2002. No registrant data, so the ask falls outside their Data Release Policy, which is personal-data-only; send it through `registrars.nominet.uk`, not `data-release@nominet.uk`. Nominet holds the whole window (`demon.co.uk` dated 1996-05-05, nineteen days before Nominet existed, so the Naming Committee register was inherited with its dates).

Worth: 63,921 EE for creation dates alone, 702,229 EE if they can supply registration history. Do not write to auDA (never held the window) and write to CIRA only for the 2000-2002 transition slice, ~24,900 EE.

### Rule on the 118.7 EE of unshipped Nominet pairs

Nominet is the only one of the four whose terms prohibit USE as well as collection: "explicitly prohibited from extracting, copying and/or using or re-using ... all or part". The store holds 4,714 `.uk` RDAP pairs and 4,625.8 EE, of which 121 pairs and 118.7 EE are net-new and not yet sent. The rest is already in his baseline and cannot be recalled.

Worth: -118.7 EE if withdrawn. Withdrawing is the reading the terms support; keeping them needs a reason.

### Say whether the tomocha.net refusal covers its zone files too

`jpnic_register` was withdrawn on 2026-08-25 because `tomocha.net` disallows ClaudeBot by name, with the note that its 1,623 EE must not be used. The 1999 InterNIC `edu` and `gov` zones from the same host on the same day were banked, at 179.8 EE. Tomocha mirrors somebody else's register in both cases, so either the refusal covers both or neither.

Worth: 0 EE this round. `internic_zone` at 1999 is 0 pairs net-new against `merged260827`, all already in his baseline, so only the register's wording is at stake.

### Decide the round length, now that scoring is time-weighted

The brief update of 2026-08-20 scores each submission `S_i = 10 * p_i / t_i`, with `t_i` in days from the benchmark's release to receipt, and he confirmed it by quoting `S_6 = 6.88` for a 4.130718% round that took six days. Round 7 stands at 0.4377% against a benchmark released today, so a submission tomorrow scores about 4.4 and the same work sent in six days scores 0.7.

Worth: the ranking, not the increment. Frequent small rounds dominate; the 5% trigger and this rule pull opposite ways and only you can choose.

### Approve, refuse or downgrade internic_zone / artifact_listing

`approved-sources-list.md` has this class as `pending`, so `ark ingest` refuses it and its journal is sitting on disk. The request block in that file carries the seeded-random sample with live links, the measured figures and the counterfactual; decide from those rather than from anything the agent argues. Set its `Decision:` line to `master`, `candidate-only` or `rejected`.

Raised automatically, because a `pending` line in a file you do not open is not a question anyone asked.

### Approve, refuse or downgrade ukwa_geoindex / cdx_timestamp

`approved-sources-list.md` has this class as `pending`, so `ark ingest` refuses it and its journal is sitting on disk. The request block in that file carries the seeded-random sample with live links, the measured figures and the counterfactual; decide from those rather than from anything the agent argues. Set its `Decision:` line to `master`, `candidate-only` or `rejected`.

Raised automatically, because a `pending` line in a file you do not open is not a question anyone asked.

**Gate 668,118 EE. Sheet of measured sources awaiting one word each: `docs/decisions-open.md`.**

### Triage the newly found sources: 40 found

**40 source(s) found and not yet priced**, in `approved-sources-list.md` under `## Found, awaiting triage`. One word each, *candidate pool* or *fold in directly*.

A counter rather than a request, by your instruction of 2026-08-15. Nothing is blocked: a pending class cannot date a year, so `ark ingest` refuses it and collection continues.

## CLOSED

| | date | decision |
|---|---|---|
| **C-52** | 2026-09-01 | Ding accepted hostnames as annual records (registrables still prioritized). Built same day per the plan trigger: hostname_year + ingest-hostnames + per-year hostname exports + two wall checks; the 180 raw suffix journals repriced from 0 to 338,865 net-new hostname records (301,650 EE); platform sweep took the second client slot, gaploc stood down |
| **C-53** | 2026-09-01 | Headline metric is the combined increment at the calculator's unit (registrables + hostnames), because Ding accepted hostnames explicitly and scores other participants that way; the registrable-only figures are quoted beneath it. Report rewritten to the phase-6 shape Ding called exceptionally well documented: one generated attribution table over both units, short prose, D1-D4. Ivo, 2026-09-01 |
| **C-51** | 2026-09-01 | Ivo: one month left, speed first. Rung 2 (4 waves/day), self-improvement lane added (policy.json + prompts/ tuned one knob per PR behind an evidence gate), approval issues only at 1,000+ EE, model matrix set per lane, runner sudo scoped to the collector units |
| **C-50** | 2026-09-01 | The vedge engine queue replaced with the fleet-measured high-weight 2001 gap tail: 167,870 uk/au/edu/ca names held at 2000 and missing 2001, journal-deduped, 0.91 EE/pair against the old head 0.63. Old queue kept as gap_ranked_vps.txt.pre-hiweight |
| **C-49** | 2026-08-24 | O9 answered: purge the 575,417 impossible `.mil`/`.gov`/`.edu` candidates. No yield either way, wasted queries only |
| **C-48** | 2026-08-24 | O5 answered no, and it binds RDAP too: this is paid work, so no bulk Nominet querying. The `.uk` engine started that morning at 118.8 EE per 1,000 queries was stopped the same day |
| **C-47** | 2026-08-24 | O4 closed as unnecessary. The in-session cron runs the cycle hourly, so Full Disk Access for `/bin/bash` buys nothing |
| **C-46** | 2026-08-24 | O2 answered: the VPN goes up when convenient. **The VPS is a standalone autonomous helper reached from time to time, not a regularly driven machine**, so its collectors take deadlines measured in days |
| **C-47** | 2026-08-27 | The loop belongs outside the agent: a stop hook cannot tell work from sleep |
| **C-46** | 2026-08-27 | Debian's per-release package index is a blocklist seam, worth 14,229 EE in five requests |
| **C-45** | 2026-08-24 | O1 and O3 moved off this surface into the source triage queue, where they are two rows of `decisions-open.md` rather than two asks of their own |
| **C-44** | 2026-08-24 | O7 answered: `afnic_fr` does **not** breach rule 6. Ding has already ingested and approved these pairs into the baseline, and AFNIC is a documented one-off exception to the creation-year rule: its *Technical Integration Guide* v3.0 states `crDate` is "the last creation date of the domain name", so `crDate = max(last creation, last transmission)` and the interval `[crDate, deletion-or-now]` is continuous by construction. Cited in `sources.md` |
| **C-45** | 2026-08-27 | The RDAP terms were in every response all along, and all four registries forbid this |
| **C-44** | 2026-08-27 | `merged260827` ingested: 27,152,319 pairs and 14,169,892.8027 EE, reproducing his arithmetic to the digit |
| **C-43** | 2026-08-21 | RDAP is the fast channel, and both of my first two target lists were wrong |
| **C-42** | 2026-08-21 | Page 0 of a CDX namespace is about twice as dense as the namespace |
| **C-41** | 2026-08-21 | The suffix sweep is exhausted, and the complete accounting of what remains |
| **C-40** | 2026-08-21 | The suffix sweep is real but an order of magnitude smaller than C-38 and C-39 claimed |
| **C-39** | 2026-08-21 | The suffix sweep cannot be extended to `.com`, and the reason is structural |
| **C-38** | 2026-08-21 | The query-rate ceiling is broken: one endpoint enumerates a whole namespace |
| **C-37** | 2026-08-21 | The original Alexa crawl indexes exist, are enormous, and are access-restricted |
| **C-36** | 2026-08-21 | 5% by Sunday is not reachable, and here is the arithmetic that says so |
| **C-35** | 2026-08-21 | National Usenet hierarchies really do name national domains, tested rather than assumed |
| **C-34** | 2026-08-20 | A 5% path exists, it is measured, and every part of it is public |
| **C-33** | 2026-08-20 | Scoring is now time-weighted, so submitting sooner is worth as much as submitting bigger |
| **C-32** | 2026-08-20 | The threshold recedes 10x slower than the model assumed, and the gap now closes |
| **C-31** | 2026-08-20 | The British Library geoindex is real, free and worth 77,749 EE, measured over the whole file |
| **C-30** | 2026-08-20 | The UKWA host link graph is 10x bigger than the copy we hold, and the only copy is unservable |
| **C-29** | 2026-08-20 | The largest unheld public corpus is worth about a sixth of the gate, not the gate |
| **C-28** | 2026-08-19 | The local engine moves to the edge population, which is C-24's own contingency firing |
| **C-27** | 2026-08-19 | A third of the candidate pool's quoted value is names that were never real |
| **C-26** | 2026-08-19 | Demunging Usenet addresses is real and is worth a few thousand EE, not a round |
| **C-25** | 2026-08-19 | The research-repository route to a bulk capture census is dry across five registries |
| **C-24** | 2026-08-18 | Edge-year gaps are real, measured, and NOT worth reallocating an engine to |
| **C-23** | 2026-08-18 | The four new deliverables are enforced by the build, not by a checklist |
| **C-22** | 2026-08-18 | The current baseline is `merged260817-2`, and a round now records what he ACCEPTED |
| **C-21** | 2026-08-16 | The promotion tranche is banked, at 88% of its quoted figure |
| **C-20** | 2026-08-16 | The baseline moved to `merged260815`, loaded and pointed at [SUPERSEDED BY C-22] |
| **C-19** | 2026-08-12 | Netcraft survey listings stay candidate-only: your condition was tested and failed |
| **C-18** | 2026-08-11 | The hit-rate fallback gains the grain it was missing, the TLD |
| **C-17** | 2026-08-11 | The pool queue is ranked by a measured plausibility factor, not by English share alone |
| **C-16** | 2026-08-11 | One surface asks you for things, and it is this file (see ADR-005) |
| **C-15** | 2026-08-11 | A declarative *probe*, and bespoke *collectors* (see ADR-004) |
| **C-14** | 2026-08-11 | The harness wakes every 15 minutes, and "the collectors are running" is not the agent being busy |
| **C-13** | 2026-08-11 | A source class may not date a year until a human classifies it (see ADR-003) |
| **C-12** | 2026-08-11 | UDRP proceedings are master `artifact_listing` (see ADR-002) |
| **C-11** | 2026-08-11 | The write-lock contention: no structural change, an allocation rule instead (see ADR-001) |
| **C-10** | 2026-08-11 | The two populations go to two machines, and it supersedes C-6 |
| **C-9** | 2026-08-11 | The report leads with the method; the numbers stay at the top as the result |
| **C-8** | 2026-08-11 | Go back to `.org`, and to previously unavailable sources generally |
| **C-7** | 2026-08-11 | Ding's research vision logged, and it is background rather than specification |
| **C-6** | 2026-08-11 | Local CDX engine stays off [SUPERSEDED BY C-10 THE SAME DAY] |
| **C-5** | 2026-08-11 | VPS is the unattended safety baseline, with its queue refreshed periodically |
| **C-4** | 2026-08-11 | Current state becomes generated, and the handoff retires |
| **C-3** | 2026-08-10 | Two sources closed on measurement |
| **C-2** | 2026-08-10 | `.gov` and `.mil` excluded from RDAP ranking on a fabrication test |
| **C-1** | 2026-08-10 | VPS deadline extended to 2026-08-31T12:00Z on a freshly rebuilt shard |
