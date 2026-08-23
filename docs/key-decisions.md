# Decisions

**One surface asks Ivo for things, and it is this file** (ADR-005). Two lines per ask: what is needed and
what it is worth. If an entry needs a third line, it is being over-explained. He decides; the agent
measures. Closed decisions are one line each, because the decision is what binds and the reasoning is in
the git log and, for sources, in `sources.md` with its measurement.

## OPEN

**Gate 668,118 EE. We hold 372,772, which is 55.8%. The gap is 295,347.** Measured 2,680 EE an hour with
everything running; the gate recedes about 893 an hour.

### O7. Does afnic_fr breach your rule 6, and 54,632 shipped pairs turn on it

54,632 already-shipped pairs are open-ended intervals resting on a creation date plus the domain existing
today, which rule 6 says is not enough; the 25,429 with a published withdrawal date are safe either way.
**Correctness, not yield: nothing to gain and 54,632 pairs to lose.**

### O1. Approve ukwa_geoindex / cdx_timestamp as master

Free, public, CC Public Domain, on disk and parsed. Worth 77,749 EE when found and **4,512 when last
measured**, because our own `.uk` sweeps banked that population first. Re-price before quoting.

### O3. Approve, refuse or downgrade internic_zone / artifact_listing

One `Decision:` line. Last measured 8,628 EE and **assume it is stale downward** for the same reason as O1.

### O2. Keep the VPN up when convenient

The VPS is the faster machine at RDAP, 102 q/s against 54, so roughly two thirds of total throughput.

### O4. Give /bin/bash Full Disk Access

So the scheduled cycle can run unattended. Two minutes.

### O5. Bulk Nominet queries for .uk

**Answered: no.** The whole `.uk` candidate pool is 48,545 EE.

### Triage the newly found sources: 60 found

**60 source(s) found** and awaiting one word each in `approved-sources-list.md`, *candidate pool* or *fold
in directly*. Not urgent: all 60 priced whole is about a tenth of the gate, and nothing is blocked while
they sit, since a pending class cannot date a year.

### O9. 575,417 impossible .mil/.gov/.edu candidates in the pool

Purge them? **No yield either way.** They are names like `tfvkrp.mil` under namespaces that never allowed
arbitrary registration, 462,155 of them from Usenet address extraction. The evidence wall held: 0 reached
an annual file, and every shipped `.mil`, `.gov` and `.edu` domain carries independent attestation. Wasted
queries only.

**O8 is withdrawn.** I put `link_target` on this surface at 97,893 EE; it is worth about 5,000 and is
banked. The query failed to exclude the corpus from corroborating itself, and
`scripts/build_promotion_journals.py` already applied the three filters I skipped.

## CLOSED

| | date | decision |
|---|---|---|
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
