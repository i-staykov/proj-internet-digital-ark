# Internet Digital Ark

Rebuild the list of domains that existed 1996-2001 for Prof. Ding. Scored on **equivalent-English (EE)**:
each `(domain, year)` counts its TLD's English share. `.uk` 0.9813, `.com` 0.6321, `.net` 0.4530,
`.de` 0.1324. Non-English ccTLDs are worthless.

**Where the round stands is in `docs/ROUND.md`, which is generated. Never state it here.**
Round 6 crossed the 5% gate on 2026-08-26. The task does not end at a gate: keep collecting until the
discoverable sources are exhausted, and submit early, because percentages add and the denominator grows.

## What the score is a proxy for

**EE and speed are the PROXY. The deliverable is demonstrated research capability**:
autonomous, creative, intelligent discovery (Ivo, 2026-08-27). So a measured negative with
a reason is a result, the METHOD that found a source outranks the source, and breadth of
hypothesis beats grinding one shape. Run independent hypotheses in parallel; keep what
works, document what does not, move to the next. This does not soften the 5% target: it
decides what to do with the hours that do not find an outlier.

## The standing approval rule (Ivo, 2026-08-29)

**The loop may admit a source without asking, when ALL of these hold**, writing the
`Decision:` line itself and citing this rule:

1. the evidence type is already master-eligible, so no new class is being invented;
2. what dates one item is a **machine-written stamp inside the artifact**, quoted in the entry;
3. the terms permit it, read in full before the first request;
4. `ark check` passes after the ingest.

Anything failing one of the four still parks as `pending`. Ivo's reasoning: he has never
once denied a source, so the per-class gate was filtering nothing and blocking all banking.
**This moves the gate, it does not lower it.** The evidence standard is unchanged, and
rule 6 and the corroboration split still apply.

**Broaden what gets tried, not what counts as evidence.** Small is not a reason to reject:
a 25 EE source is admitted and simply gets one line. Ugly, awkward or hard to parse is not
a reason either; park it candidate-only if unsure. **Undated is still fatal, and so are
terms we do not hold.** The RDAP episode cost the biggest route precisely because nobody
read the terms, and time pressure does not reopen that.

**Write-up length scales with yield.** Under 5,000 EE gets ONE line in `sources.md`: the
link, the sentence saying what dates one item, the figure. The report lists them in a
single table pointing there. Over 5,000 EE earns the full treatment.

## When prompted, in this order

1. `just cycle`. Fix anything it flags that a program cannot decide.
2. **Hunt a bulk dated corpus.** This is the job. Querying alone adds ~3,000 EE/hour.
3. Price what you find: net-new EE against the store, dates inside 1996-2001, before proposing anything.
4. Bank what clears the bar. Raise an approval request only if the class is master-eligible.
5. Log the result in `docs/sources.md` whatever the answer, so nobody re-tests it.

## The bar for admitting a source

- **Per-item dates inside 1996-2001.** Check the dates before counting the contents.
- `domain_year.evidence_id` is `NOT NULL` and foreign-keys `evidence`. No year without an observation.
- Master-eligible: `prior_reused`, `cdx_timestamp`, `artifact_listing`, `link_source`, `dated_directory`,
  `whois_creation`. **`link_target` never dates a year.**
- **Corroboration split**: anything a human typed needs another source to date that domain first.
- A creation date evidences its own year only. Continued registration needs its own record (rule 6).
- A master-eligible class needs a human `Decision:` line in `docs/approved-sources-list.md`.
  Candidate-only needs nothing.
- **Quote net-new post-split EE, never gross.** They differ by more than 10x.
- **Every source gets a LINK in `docs/sources.md` before it is ingested** (Ivo, 2026-08-31),
  next to the sentence saying what dates one item and why it clears the bar. Two approved
  sources had their bytes fetched to a temp dir that was later reclaimed, and only the URL
  made them refetchable.

## Method, and when to change it

**Verbosity is the opposite of quality.** Keep instructions, wake-ups and agent prompts short, direct,
simple. If a rule takes a paragraph, it is being over-explained.

**If two hunts in a row return nothing, change the method, not the effort.** Widen the lens, not the
list: ask what *kind* of artifact you have never looked for, not which host you have not tried. Rewrite
the wake-up wording. Re-price parked sources, since an unbanked source decays as the store grows.
Never re-test a closed family; never grind an old source because it is familiar.

## Breadth, on Ding's own list

He asks for all of these and expects each to be tried and reported, positive or negative: dated
directories and navigation sites, national web-archive indexes and link graphs, academic repositories
and DOI datasets (UMN DRUM is his worked example), paper supplements and replication packages, registry
datasets, government open data, mailing-list archives, preserved software and documentation
collections, outbound-link expansion from pages already held, and automated dataset discovery over
repository APIs.

**One lens per cycle, and never the same lens twice running.** Rotate even when the last one paid.
A run of nothing is a signal to move sideways, not to push harder on the same shape.

## What kills a source, before you download it

`discovery.md` has the three measured laws. In one line each, plus what has closed since:

1. IA-derived cannot be net-new: the baseline is IA-derived too.
2. Listing a name proves the artifact's date, not that the name was live.
3. A trust-selected corpus holds authorities, not hosts.
4. A current-state snapshot cannot evidence a past year.
5. Human-typed novel names take the split and earn no year.
6. Anonymised or hashed hostnames are worth nothing: ask for the sanitisation paragraph first.
7. Dating and URL-bearing anticorrelate: a record naming a site is one somebody has since edited.
8. Overlap with the baseline corroborates a reading; it never justifies one (Ivo, 2026-08-24).
   The grounds must be what dates the item: the artifact asserting a state at an instant it
   stamps itself, and a capture fixing when it existed. Agreement with `prior_task` is a check
   on that argument, and cited only after it.

Prose density ceiling: ~0.042 net-new pairs per item, so ~119,000 items to clear the bar. Ask what the
corpus is *about* before trusting even that.

**Density and authority are two INDEPENDENT screens and a corpus must pass both.** Formal prose fails
the first: Hansard is 3.26M words per 5 URLs, 0.00153 URLs per 1,000 words. Grey literature passes it
emphatically at **221x that rate** (ERIC, 0.339 per 1,000 words) and then fails the second at 93.0%
already held, because program reports print the URLs of institutions we already have. Measure BOTH on
a sample before pricing any prose corpus, and expect `.edu` and `.gov` to die to the split: ERIC held
184 `.edu` pairs and exactly one survived.

**Under the split, a list's EE is (domains held AND missing that year) x nothing else. Novelty is a COST.**
A novel name earns no year. But high already-held is only half the test: an IRR dump at 97.6% held paid
**4.44 EE** because 95.2% were held **in that very year**. The screen is *held AND missing this year*.
junkfilter paid 2,189 EE spanning 13 editions 1997-2001; a two-year list over the same population paid
120. Ask which YEARS an artifact can add to names we already have.

**Compute headroom from the ADJACENT year only.** A gap between a domain's LAST held year and the
target is evidence of death, not of missing data: of 9,680 `.us` names missing 2001, **6,948 were last
seen in July 1997**, and only 37.65% of the names an ISC 1997 walk attests have any 2001 record at all
(`.com` from the same file: 40.31%). So "held ANY year, missing Y" is contaminated and "held Y-1,
missing Y" is not. Quote the adjacent figure.

**Aim at 2001, not 1996.** Measured headroom: **6,708,320 domains held at 2000 and missing 2001**, worth
~2.92M EE gross in the top eight TLDs, against **103,953** for the 1996-to-1997 gap. A 64x difference.
Thin in absolute pairs is not the same as fillable. So aim the frozen-mirror rule at media and mirrors
that stopped in **2001-2003**, not the 1990s.

**The 2001 threshold, and it is the screen to use.** P(store lacks 2001 | domain held) is `com` 0.611,
`net` 0.653, `org` 0.568, `uk` 0.309, `de` 0.841. So one ALREADY-HELD name in a 2001-dated artifact is
worth 0.386 EE in `com`, and **1,000 EE needs only ~2,600 held `com` names** (2,477 `org`, 2,484 `au`,
3,298 `uk`). That is 32x below the 83,000 the curated-directory floor demands, because that floor was
measured on artifacts dated in years already well covered. **A few thousand held names dated 2001 is a
find; the same list dated 1999 is not.**

**But that is a population average and does NOT transfer to head-selected corpora.** A 2001 magazine
article archive measured **0.041 EE per name**, nine times worse, because a magazine cites the head of
the distribution and we already cover the head at 2001. Head-type artifacts need ~24,000 names. **The
pre-download discriminator is the expected held-fraction**: blocklists ~50%, authority corpora 87-99%,
forged-header spam corpora **~5%** (a remailer log was 23,102 names and 4.56% held, since spam sender
hostnames are invented). And when sampling to check, sample DISTINCT DOMAINS, not `domain_year` rows:
per-row gives P=0.492 against the true per-domain 0.611.

**Crawling kills DISCOVERY, not COMPLETENESS, and the two laws interact.** A crawl-fed adversary finds
few novel names (only 15% of a squidGuard list is unknown to us), so it loses on discovery. But if its
held names LACK the year it is dated, it wins anyway: the **2001-12-18** squidGuard blacklist is 84.8%
known and only 57.9% held at 2001, so it pays **10,736 EE**, while the 2000-10-18 edition paid 18
because its names already carried 2000. **So ask which YEAR the artifact can add before dismissing it
for crawling.** Non-crawl channels still win on discovery: junkfilter 50.4% held, SpamEater 59.1%, a
typosquat listing 25.8%. Visitor logs lose on both, at 98.4% and 99.6%, because the hostname is
reverse DNS and the long tail resolves to its ISP.

Curated-directory floor, measured over four artifacts: 0.013 to 0.024 net-new post-split pairs per
LISTED domain, at 0.39 to 0.70 EE per pair. So 1,000 EE needs 83,000+ listed domains in one artifact.
For a human-curated list, novelty and datability are mutually exclusive: what we lack takes the split,
what survives the split we already hold. Ask whether the lister held the database, not how long the list is.

## Rules

- Never `git push`. Non-`main` branch only. No AI attribution in commits. **No em-dashes or en-dashes.**
- Gate before every commit, never through a pipe:
  `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && uv run ark check`
- `ark export` before `ark check`. Never edit `docs/SPEC.md`, `docs/report.md`, frozen `submissions/`.
- `private/` never ships. **Big data must never reach git.**
- Two archive clients maximum. Honest User-Agent, honour `Retry-After`, back off on 429/503/504.
- Collectors take an absolute deadline and outlive the session. Restart a loop after editing what it imports.

## Traps

- **Prove a negative against a known positive.** Nothing-found and pointed-wrong look identical.
- **Verify every number, including a subagent's.** Several were fabricated or out by 1000x.
- **An already-ingested journal shows 0 net-new by construction.** Measure against a pre-ingest snapshot.
- A running collector is not a working one. Presence, progress and yield are three questions.
- Rank a queue by TLD weight alone and 2013 gTLDs lead it. Volume floor first.
- Any name-shape filter over-catches: `bl.uk` is the British Library, `x.com` is real.
- Look for the existing tool before writing one.
- **A size floor is not a content check.** A replay URL built as `{stamp}id_{host}`, missing the
  slash in `id_/`, made web.archive.org answer seven different objects with the same 154,263-byte
  interstitial, and a floor set at half the expected bytes passed all seven. Assert on what the
  artifact must CONTAIN, and read identical sizes across different objects as a failed fetch.
- **archive.org's `services/search/v1/scrape` LIES under load. Use `advancedsearch.php` for any zero.**
  Caught twice on 2026-08-19: it returned the same 6 items for five different collections, and an identical
  bogus `total=28330` for five different queries, producing six false zeros in one batch. It also
  rejects `count<100`. A false zero is how a real source gets buried.
- **Clear a whole FTP host with ONE request: pull its own `ls-lR.gz` or `locatedb.gz` and grep offline.**
  Proven twice on 2026-08-19: `ftp.gwdg.de`'s 926 MB locatedb indexed an 8.8 GB tree, and a 9.8 MB `ls-lR` gave
  1.46M lines. Politer and more complete than crawling, and it turns a zero into a proved zero.
- **On a port-43 whois source, read PAST the record.** The terms of use follow the data, so a reader
  that stops at the last field reports "no licence" on a source that explicitly prohibits bulk access.
  `.nz` cost 7,586 EE that way; `.uk` says the same thing.
- **A 403 wall is not always a refusal. Test it before recording one.** `.info` RDAP returned 403 on
  record 199 and on all 394 after it, unbroken, with `awselb/2.0`, 118 bytes and no `Retry-After`.
  After ~12 minutes idle the SAME User-Agent got a genuine 404: it throttles above ~3 q/s and answers
  again after a rest. Honour it by slowing down, not by filing the host as refusing us.
- **Read the WHOLE robots.txt, not its head, and act on it before any other request.** A by-name group
  can sit anywhere in the file and a permissive `User-agent: *` block at the top does not override it.
  `tomocha.net` disallows ClaudeBot at line 51 of 61; reading ten lines cost a breach and 1,623 EE.
  Refusing us by name: `cryptome.org`, `tbtf.com`, `www.openpgp.net`, `ftp.nluug.nl`, `tomocha.net`,
  `mirror.aarnet.edu.au`, `ftp.aarnet.edu.au`, `www.potaroo.net`, `ftp.sunet.se`, `ftp.surfnet.nl`,
  `www.math.upenn.edu`, `ftp.cc.uoc.gr`, `ftp.acc.umu.se`, `www.floodgap.com`, `gopher.floodgap.com`, `leb.net`
  (upenn, uoc and umu name Claude-User, Claude-Code, Claude-SearchBot, Claude-Web and ClaudeBot together;
  umu.se puts them at lines 115-119 of a 6,238 B file whose FIRST group is a permissive `User-agent: *`;
  both floodgap hosts are `Disallow: /` for ClaudeBot and www.floodgap.com also names `anthropic-ai`,
  which closes the obvious host for any gopher or retro-internet lens before it is proposed).
- **Host survival and robots refusal are correlated, so this will keep happening.** The old mirrors that
  survive did so because a commercial or university operation kept paying, and mirror operators are
  exactly the population now adding blanket or Claude-named `Disallow: /`. Five of seven live large
  mirrors in one sweep refused; the two that allowed crawling carried only current distro trees.
- **Verisign RDAP is a QUOTA, not a rate.** It served 64,568 queries at a flat 65 q/s for seventeen
  minutes, then clamped to about 1 q/s for at least twenty-five minutes across three restarts. Restarting
  does not clear it; only resting might. Budget a night's Verisign work as one block of ~65,000 queries.
- **A collapse after a change is not evidence the change caused it.** Three queue orderings were compared
  inside that clamp and all read as catastrophic, which produced a confident and wrong law about ranking.
  Get a per-minute series out of the journals before attributing a rate change to anything.
- **Grep `sources.md` before briefing an agent, not after.** A lens described as untried when it is
  closed three times over wastes the run and teaches the agent to distrust the brief.

Details: `.github/copilot-instructions.md`. State: `docs/ROUND.md`. Decisions: `docs/key-decisions.md`.
