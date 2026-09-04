# Decisions

**One surface asks Ivo for things, and it is this file** (ADR-005). Two lines per ask: what is needed and
what it is worth. If an entry needs a third line, it is being over-explained. He decides; the agent
measures. Closed decisions are one line each, because the decision is what binds and the reasoning is in
the git log and, for sources, in `sources.md` with its measurement.

## OPEN

### Does `www.<a name already held that year>` count as a hostname record? 201,767.94 EE of this round turns on it

The ingest refuses `www.<parent registrable>` because it is the parent's own site under the name
every crawler tries first (our own tightening, 2026-09-02, not his instruction). Nothing refuses
the same alias where the bare name is a hostname or registrable already dated for that year, and
measured 2026-09-03 that is **61.0% of the shipped hostname half, 201,767.94 of 330,577.84 EE**:
the round claims 346,668.36 EE and 1.673552% growth, or 144,900.42 EE and 0.699511% without it.
His words admit them ("every distinct evidence-backed hostname beneath them is retained"); our own
stated principle refuses them. Two E9.5 corpora were held out rather than ingested on it (`ukwa`
20,916.90 EE at 99.5% alias, `nypw_firstcdx` 7,074.09 EE at 100.0%), and `round_figures.py` now
prints the split so no round can quote the hostname half without it.

Worth: 201,767.94 EE of the current claim, plus whether the next hostname corpus is worth reading. If they count, nothing changes; if they do not, the refusal moves into `hostnames.py` under an ADR and the round is restated.

### Approve, refuse or downgrade usenet_body_url_hostnames / link_source: 119,640 EE measured

Hosts of explicit `http`, `https` and `ftp` URLs in Usenet post BODIES, at hostname grain, over
**every hierarchy of the catalogue except `alt`, all read whole**: eleven fetched overnight on
2026-09-04 beside the two priced the day before, 224 GB, 328.2M posts, 54.7M item lines.
163,985.8408 EE gross, **119,639.7424 EE after the ADR-007 alias seam and a sampled 6.25% fiction
rate (Wilson 95% CI 2.7% to 13.8%, so 110,005 to 124,170)**. No projection anywhere in it. Beside
it, needing no hostname decision, 83,708 registrable-years worth 49,007.3050 EE before the
corroboration split. It parks on condition 1 only: no master-eligible class covers a host a human
typed at hostname grain. In place of the split, the fiction rate is 6.25% here against ~13% for the
`dig`-output request beneath it, and the fakes are typos of real hosts rather than examples.
Density decides which hierarchy pays: news 2,552 EE per GB, comp 1,701, soc 418.

Worth: 119,640 EE measured, the largest single lane in the project's history and 10.4% of the gate. Bytes are on disk; journals rebuild in about 25 minutes a pool.

### Build or decline a collector for dartmouth_nber_arcs_hostnames / cdx_timestamp

Not a decision to take now: conditions 1 to 3 of the standing rule hold and condition 4 cannot
be evaluated because nothing has been ingested. The fleet sampled 57 of the 282 public
DARTMOUTH-NBER ARCS aggregate CDX indexes at one Range slice each and found 120 novel hosts
beneath held parents at 2001 out of 235 proper hosts (0.453 per registrable-year), projecting
~88,700 EE at 2001 and ~92,000 at 1996-2000 from one alphabetic band per item. The measured
sample is worth under 100 EE and no issue is filed. What it needs is a collector on the VPS
(scout ~40 candidate items, pull the in-window per-ARC indexes, `ark ingest-hostnames`), and
two more Range offsets on items 00333 and 02693 first to rule out a band artifact. Entry in
`approved-sources-list.md` under Pending requests; the fleet finding is
`dartmouth_captures_hostname_grain`, 2026-09-02.

Worth: ~180,000 EE projected across the window, under 100 EE measured. A collector decision, not an approval.

### Settle the terms for arin_inaddr_ns_hostnames / artifact_listing

ARIN's twelve 1999 in-addr.arpa zones in APNIC's tar (`ftp.apnic.net/apnic/arin/arin.zones.tar.gz`), nameserver hostnames at hostname grain, fleet-measured at **4,655.5 EE** (7,232 novel host-years at 1999 plus 179 parents), dated by BIND's own AXFR stamp `at Thu Jan  7 12:18:51 1999`. Parks on condition 3 only: APNIC's bulk AUP covers `/apnic/whois/`, this directory carries no notice, and ARIN's position on historical zone redistribution is unread. One mail to APNIC or ARIN settles it. Issue on ark-fleet carries the block.

Worth: 4,655.5 EE measured by the fleet, not yet re-priced on the live store. Directory frozen since 1999, so this is the whole family.

### Approve, refuse or downgrade usenet_body_pasted_hostnames / link_source

Hostnames inside Usenet post BODIES (`dig` answers, config snippets, logs) at hostname grain, fleet-measured at **~6,200 EE on one group** (`comp.protocols.dns.bind`, 67 MB) after a placeholder screen, with ~13% fictitious config examples still among the survivors. Parks on condition 1: the banked Usenet body classes date registrables under the corroboration split, and at hostname grain the split does not guard against `mail.bogus.com` beneath a held `bogus.com`. The machine-output lane alone is 2,477 EE if the human-pasted lane is refused. Issue on ark-fleet carries the block.

Worth: ~6,200 EE on one group; yield is group-specific by 22x, so the spool-wide figure is unknown. Ding's 0901 update lists dated Usenet copies as unsuitable.

### Approve, refuse or downgrade usenet_header_fqdn_hostnames / link_source

Server-written Usenet header hostnames (`X-Trace`, `NNTP-Posting-Host`, final `Path` hop) at hostname grain, fleet-measured at **2,368 EE on one 28 MB demon.* probe**, not re-priced on the live store because the probe table was deleted and the bytes are on the VPS. Parks on conditions 1 and 4: no master-eligible class covers a server-written header hostname without the split the banked Usenet classes take, and no journal exists to ingest. Ding's 2026-09-01 update lists dated Usenet copies as unsuitable, so the fleet recommends asking him first. Issue 2 on ark-fleet carries the block.

Worth: 6,877 EE on the second probe (55 MB, 2026-09-02), of which 2,823 rests on server-written fields and 4,054 on the client-written `Message-ID` host, which needs its own ruling; 20,000 to 60,000 EE projected for demon.* alone, unmeasured. A third probe on two uk.* groups adds 2,537 EE (server-written fields only, 73% retained across groups), so the 495-zip uk.* hierarchy is a labelled 50,000 to 150,000 EE guess on top.

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

**Gate 668,118 EE. The measured sources awaiting one word each are the `Decision: pending` blocks
of `docs/approved-sources-list.md`.**

### Triage the newly found sources: 40 found

**40 source(s) found and not yet priced**, in `approved-sources-list.md` under `## Found, awaiting triage`. One word each, *candidate pool* or *fold in directly*.

A counter rather than a request, by your instruction of 2026-08-15. Nothing is blocked: a pending class cannot date a year, so `ark ingest` refuses it and collection continues.

## CLOSED

| | date | decision |
|---|---|---|
| **C-70** | 2026-09-04 | The ISC reverse-DNS survey ships as its OWN `<year>-ISC.txt` files rather than being decided by us: 18,087,133 net-new hostname years, and the shape is measurably not one he holds (1.419% of its 13,347,250 distinct hosts appear anywhere in his files, against 84.2% for his own `www.` names). Rows stay OUT of `hostname_year` and out of the claim, so a yes is one line in `WEB_FACING_HOST_SOURCES` and a no needs no undoing. The covering mail asks the question. Ivo, 2026-09-04 |
| **C-69** | 2026-09-04 | `www.<parent registrable>` is its own hostname record (ADR-009), superseding the second half of C-55. Settled by counting his benchmark rather than reading his intent: 1,221,065 of his names have both forms in the same year file, 114,875 of them from nobody but him. Backfilled from evidence, 6,915,924 rows, no new bytes. A record is created only where an evidence value names that exact host, and the new invariant `a_www_record_has_its_own_evidence` keeps it that way. Round to 18.764914%, of which 94.3% of the hostname half is the alias, which the report and the mail both state. Ivo, 2026-09-04 |
| **C-68** | 2026-09-04 | `usenet_body_url_hostnames / link_source` is **master** (Ivo, 2026-09-04). Thirteen pools read whole rather than sampled: 224 GB, 328.2M posts, 54.7M item lines carrying a body URL. Ingested at hostname and registrable grain by `ark ingest-usenet-hostnames`. What dates one item is the post's own `Date:` header; hosts come only from explicit `http`, `https` and `ftp` URLs in the BODY, never from a `Path`, `Xref`, `NNTP-Posting-Host`, `Message-ID`, `From` or `Organization` header. The fiction rate is sampled at 6.25% (Wilson 2.7% to 13.8%) and quoted, not assumed |
| **C-67** | 2026-09-04 | `www.<a name already held that year>` **ships**, and ADR-007 is superseded by ADR-008 after one day (Ivo, 2026-09-04). Settled by measuring him rather than reasoning about him: his merges hold all 1,313,547 `www.` forms we sent, the bare name beside 1,106,188 of them, and he credited that round 7.562846%; then section XI of the 0904 brief said in his own words that a base hostname and a distinct subdomain hostname may each be annual records. One predicate removed from the export, nothing re-collected, because ADR-007 lived at the export and destroyed nothing. Also reopens the `ukwa`, `nypw_firstcdx` and `early_web` non-200 corpora, held out for this reason alone |
| **C-55** | 2026-09-02 | Ivo: the hostname rule is read by its purpose (retrieving archived pages), two conditions beyond its letter. A hostname record needs an observation of the host serving web content, so DNS listings (ISC survey, RIPE `nserver:`, InterNIC NS targets) date the parent only and write no hostname row; and `www.<parent>` is the registrable's own site, not a second record. Source-level allowlist in `hostnames.py`, two invariants in `checks.py`, `apply_hostname_purpose_rule.py` removed 23,381,935 rows from the store (18.2M DNS-listed, 5.2M `www.`), evidence kept. One line to restore if Ding rules otherwise |
| **C-66** | 2026-09-03 | Two OAuth tokens, and the choice is NOT automatic. The new account's token is primary and every workflow uses it; the older one is an explicit opt-in switch for an emergency, never a default and never picked by logic. No headroom comparison: always the primary while its weekly window has room, otherwise the wave skips. Ivo, 2026-09-03. Primary expires 2027-09 |
| **C-65** | 2026-09-03 | All three models, and fable used sparingly because it is inefficient per token: generator fable-5-1/high, reopen fable-5-1/medium, researcher opus-5/high, digest sonnet-5/high. Any lane on fable demotes to opus-5 when the fable-specific window is exhausted and the general one is not; lanes not on fable have no demotion and skip at the ceiling as before. Supersedes the 2026-09-01 all-fable matrix. Ivo, 2026-09-03 |
| **C-64** | 2026-09-03 | Full Disk Access declined (Ivo, 2026-09-03), so `just context-report` reads only the transcripts already reachable and the sweep over the 724 past sessions is dropped rather than deferred. The recipe stays useful on the current session directory; nothing else in E5 depended on it |
| **C-63** | 2026-09-03 | `AUTO_SHIP` stays off: a cleared gate prepares the package, the mail draft and the gate issue, and stops. Ivo sends. Packaging and sending stay under his control, one action per round. Ivo, 2026-09-03 |
| **C-62** | 2026-09-03 | `private/` is not backed up off-site: it never ships, it is not a reproduction input, and losing it would cost the research nothing. Ivo, 2026-09-03 |
| **C-61** | 2026-09-03 | Deletions are approved ONCE, as a single reviewed table covering E3.2 and E9.2 together, each row carrying class, bytes, checksum record and refetch route; no row without all four reaches the table. Replaces batch-by-batch approval, on the grounds that the retention table and the off-site copy are what make a deletion safe, not the number of approvals. Ivo, 2026-09-03 |
| **C-60** | 2026-09-03 | Pushing opens up: any branch except `main` may be pushed by any session, and `main` is reached only through a PR, which Ivo's new branch protection enforces. Supersedes the 2026-09-01 amendment that reserved pushing to the fleet's bank job. What does not change: `origin` is public, so no commit message carries a host, an address, a mail body or personal context |
| **C-59** | 2026-09-03 | The Overhaul ships as ONE review. Every ticket lands as a commit on `live`, no branch and no PR per ticket; when the last one is in, a single PR from `live` into `main` named after the project closes all of its issues, and that PR is what Ivo reviews. Agents still never push: he pushes `live` and opens it. Ivo, 2026-09-03 |
| **C-58** | 2026-09-03 | The scoring clock counts WHOLE days since the day the current baseline is named after, partial days rounded up (Ivo, 2026-09-03). Measured against his two quoted scores, only the variant started at the release TIMESTAMP reproduces both: from 2026-08-21 11:19, round 6 is 5.19 days -> 6 and round 7 is 11.77 -> 12, giving 6.884530 and 6.302372. From midnight the same day round 7 becomes 12.24 -> 13 and its score is wrong. `figures.py` already implements the timestamp form; the question stays open with Ding for confirmation |
| **C-57** | 2026-09-03 | Rules 3 and 4 of the hostname standard hold as applied (a hostname needs its own observation of the host serving web content, so DNS listings date the parent only; `www.<parent>` is never a second record). Ivo's interim ruling, to be confirmed with Ding in the phase-8 mail. C-55 stands and stays one line to restore |
| **C-56** | 2026-09-02 | `merged260902` ingested: 36,672,403 records and 19,239,935.8548 EE, reproducing his calculator to the digit. The 5% trigger is 961,996.8 EE; the round is scored from the release date 2026-09-02 |
| **C-54** | 2026-09-02 | Public-suffix namespaces (`co.uk` first, then `com.au`, `co.nz`, `org.uk`, `gov.uk`, `co.za`, `gc.ca`, the `.us` states) reopened at hostname grain and queued behind the platform parents: C-39 to C-41 closed them at registrable grain on 1.2% of the index. Page size raised to 10,000 blocks after a flat cost-per-page measurement; failed pages retried, not skipped; page count asked up front. Details in `sources.md`, runbook in `runbook.md` |
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
