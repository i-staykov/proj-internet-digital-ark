# Decisions

**One surface asks Ivo for things, and it is this file** (ADR-005). Two lines per ask: what is needed and
what it is worth. If an entry needs a third line, it is being over-explained. He decides; the agent
measures. Closed decisions are one line each, because the decision is what binds and the reasoning is in
the git log and, for sources, in `sources.md` with its measurement.

## OPEN

**Gate 668,118 EE. Sheet of measured sources awaiting one word each: `docs/decisions-open.md`.**

### Triage the newly found sources: 69 found, incl. ukwa_geoindex / cdx_timestamp and internic_zone / artifact_listing

**69 source(s) found and not yet priced**, in `approved-sources-list.md` under
`## Found, awaiting triage`. One word each, *candidate pool* or *fold in directly*.

The measured subset, which is what a decision actually turns on, is generated into
`docs/decisions-open.md` by `scripts/decision_sheet.py`: eleven rows and 54,187 EE, largest first. The two
named in the heading used to be separate asks on this surface and are now rows on that sheet, by your
instruction of 2026-08-24; they stay named here only because a priced request must remain visible.

A counter rather than a request, by your instruction of 2026-08-15. Nothing is blocked: a pending class
cannot date a year, so `ark ingest` refuses it and collection continues.

## CLOSED

| | date | decision |
|---|---|---|
| **C-49** | 2026-08-24 | O9 answered: purge the 575,417 impossible `.mil`/`.gov`/`.edu` candidates. No yield either way, wasted queries only |
| **C-48** | 2026-08-24 | O5 answered no, and it binds RDAP too: this is paid work, so no bulk Nominet querying. The `.uk` engine started that morning at 118.8 EE per 1,000 queries was stopped the same day |
| **C-47** | 2026-08-24 | O4 closed as unnecessary. The in-session cron runs the cycle hourly, so Full Disk Access for `/bin/bash` buys nothing |
| **C-46** | 2026-08-24 | O2 answered: the VPN goes up when convenient. **The VPS is a standalone autonomous helper reached from time to time, not a regularly driven machine**, so its collectors take deadlines measured in days |
| **C-45** | 2026-08-24 | O1 and O3 moved off this surface into the source triage queue, where they are two rows of `decisions-open.md` rather than two asks of their own |
| **C-44** | 2026-08-24 | O7 answered: `afnic_fr` does **not** breach rule 6. Ding has already ingested and approved these pairs into the baseline, and AFNIC is a documented one-off exception to the creation-year rule: its *Technical Integration Guide* v3.0 states `crDate` is "the last creation date of the domain name", so `crDate = max(last creation, last transmission)` and the interval `[crDate, deletion-or-now]` is continuous by construction. Cited in `sources.md` |
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
