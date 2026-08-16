# Internet Digital Ark: round report

Additions to the 1996-2001 annual domain lists, measured against `merged260815`.

**Every figure in the tables** is generated from the store by `scripts/report_figures.py` and
substituted by `scripts/fill_report.py`, so a table here cannot drift from the shipped files. The
handful of one-off measurements quoted in the prose of sections 2 and 3 are not regenerated per round;
each describes a specific run and is recorded with that run in `sources.md`.

---

## 1. What this round adds

| | |
|---|--:|
| Net-new (domain, year) pairs | **437,612** |
| Over unique domains | 370,982 |
| Domains absent from the baseline in every year | **208,665** |
| Equivalent-English added | **305,795.4** |
| Growth on the 8,346,839.4 baseline | **3.6636%** |
| Mean equivalent-English weight per pair | 0.6988 |

| Year | merged260815, this counting unit | Additions | Capture-backed |
|---|--:|--:|--:|
| 1996 | 649,765 | 6,098 | 5 (0.1%) |
| 1997 | 1,358,646 | 117,123 | 41 (0.0%) |
| 1998 | 1,363,435 | 19,599 | 590 (3.0%) |
| 1999 | 2,745,535 | 44,399 | 2,006 (4.5%) |
| 2000 | 4,675,256 | 60,370 | 4,197 (7.0%) |
| 2001 | 2,991,302 | 190,023 | 30,548 (16.1%) |
| **Total** | **13,783,939** | **437,612** | **37,387 (8.5%)** |

**Against the 5% threshold this is short, and the arithmetic is worth setting out exactly, because the
threshold moved during the round.** 5% of the current baseline is **417,341.97** equivalent-English, and
the shortfall is **111,546.57**.

**The baseline was reissued mid-round, and it changed both sides of the ratio at once.** `merged260810`
held 11,362,034 records and 6,226,386.4245 equivalent-English. `merged260815` holds 15,428,507
records and 8,346,839.3737, a **34.06% larger denominator**, both measured with the reviewer's own
`equivalent_english_domains.py` and its unchanged weight model. At the same time 39,492 pairs we had
collected became pairs the baseline already holds, worth **32,880 equivalent-English** of numerator.
Measured against the
release it was built against, this round reads 2.1641%; measured against the release that counts, it
reads 3.6636%. Both numbers are correct and only the second is the one being accepted against.

**The reason is the single most useful finding of the round, and it is not about us.** The new baseline
grew because another contributor delivered 4,063,995 accepted records drawn from one existing research
dataset, the University of Minnesota DRUM early-web link lists (DOI 10.13020/D62684). The per-year shape
of that delivery says what kind of artifact it was: 1,536 records for 1996 and 50 for 2001, against
950,371 for 1999 and 2,878,339 for 2000. **One bulk dated corpus was worth roughly twenty times our
entire round of per-domain archive querying.**

That is a measurement of our strategy, not our luck. This round's collection had been optimised against
the constraint we could see, which was **request throughput against a single archive**: roughly 2.5
million candidate names sit unqueried because the collectors clear a few hundred requests an hour between
them, and section 5 documents that campaign in full. A bulk dated corpus does not have that constraint at
all. It converts a rate limit into a file download.

**So the discovery system was re-aimed at that shape, and the result is the most useful finding in this
report: the constraint was never throughput.** Three of the four largest gains of the round came from
material that was already public or already on our own disk, and none of them cost a meaningful number
of requests:

| what | net-new pairs | in the figures above? | how it was found |
|---|--:|---|---|
| a parser reading 6.76% of a file we had held since July | 92,646 | banked | asked whether a file's sort key ever decreases |
| mentions re-admitted by a rule that had not changed | 94,051 | banked | re-ran an old test against a grown corpus |
| the January 1997 domain survey, recorded as unrecoverable | 76,324 | banked | tested a copy nobody had tested |
| a capture census the Internet Archive published as an ordinary item | 227,273 | **no, awaiting classification** | swept a collection for the shape that beat us |

**The fourth row is not in any figure in this report.** Its evidence type is master-eligible and its
source class has not yet been classified by a human, so the pipeline refuses it and its file waits on
disk. That is the approvals gate described in section 4 doing exactly what it exists for. Measured, it
would add 142,084.0 equivalent-English.

The throughput constraint is real and is still measured in section 5, but it was the second-order
problem. **The first-order problem was where we were looking.**

Two of those four are corrections to our own errors rather than discoveries, and the report says so
deliberately. The link-graph parser stopped at the first row past the window on a docstring claim that
the file was year-sorted; it is fifteen concatenated shards, the year column decreases fourteen times,
and the check that had verified the claim in July was real but stopped 2.4x short of the first shard
boundary. The survey file was recorded as unrecoverable on the strength of two true statements about a
different copy of it. Both are instances of one rule, now written into the method: **a closure about one
copy of an artifact is not a closure about the artifact, and to test whether a file is sorted you ask
whether its key ever decreases rather than sampling it.**

## 2. How these were found

This round the method was the work, so it is reported before the sources are.

**The question this round had to answer is what happens when the sources run out.** Each round consumes
the cheap ones, and the register of families closed on measurement is now the larger half of the count
in section 6. So the
process was rebuilt around a different premise: that the scarce resource is no longer places to look but
**judgement about which places are worth a request**, and that judgement can be made mechanical if every
verdict is recorded with the measurement that produced it.

**The result is that whole families now close without a single request.** Two rules did most of the work
this round, both derived from measurements already in hand rather than from argument:

- **A source that selects for authority cannot be net-new, however large it is.** Relay chains through
  7.1 million entries yielded 4,736 distinct domains, every one already held in every year. Link
  directories, award galleries and curated indexes fail identically.
- **A corpus derived from the same archive as the baseline cannot be net-new against it.** Three large
  research web collections and a national archive were settled by asking what their *upstream* was.
  Two that were measured returned **0.01% net-new**.

The second rule carries an exception that matters more than the rule, and finding it was the round's
sharpest correction: the constraint is not provenance but **which resource is scarce**. Our coverage of
the archive is limited by our own query rate, not by its holdings, so a bulk index *of the same archive*
is enormously valuable because it converts a rate limit into a file download. The best-performing source
this project has ever measured is exactly that shape and hits **90.4%** where the general population
hits 46.0%. A rule that would have closed it was wrong and was corrected the same day.

**The largest opportunity of the round turned out to be already on disk.** A domain typed in a dated
message is admitted only if some other source independently places that domain in the corpus. Tens of
thousands of names that failed that test when they were first read have since been dated by the
collectors, so re-applying the same unchanged rule to a corpus that has grown promotes them. This costs
no request and no new source. It is reported here because the interesting part is the shape: **in a
mature corpus, re-examining old evidence against new knowledge outperforms looking for new evidence.**

**Five programs now carry the parts of that process that can be made mechanical.** Each encodes a
mistake already paid for once:

| | what it does | the mistake it prevents |
|---|---|---|
| screen | checks a proposal against the closed families, and reports whether each was closed by a **measurement** or by something being **unreachable** | re-testing a lead already killed; and, worse, leaving a source closed because a host was down three years ago |
| re-probe | re-asks every unreachable-class lead automatically, since the record already names the hosts that failed | a permanent closure recorded from a transient failure |
| price | measures any dated corpus against the live database: net-new records, net-new domains, mean weight, a contamination bound, and a saturating projection beside the linear one | quoting a raw extraction (one such figure overstated a source 24-fold) or a linear projection (one overstated by thirty times) |
| ledger | records what was proposed, priced, adopted or killed, with status | an unattended process re-proposing its own ideas |
| state | regenerates the statement of where the round stands from the programs that own each figure | a hand-written summary going stale, which is how three claims in the previous one were wrong within a day |

**What the method produced, including the negative results, which are the majority.** Four families were
searched and closed on measurement rather than on assumption: research web crawl collections, national
web archives, bulk archive indexes, and the material already held on disk. **Two of the four paid, and
which two is the correction worth carrying.** Material already on disk paid, as expected. Bulk archive
indexes had been written off, and that was wrong: a per-year capture census the Internet Archive
computed over its own holdings, published as an ordinary item, is the single largest source this round
found. The rule that had closed the family, that a corpus derived from the same archive as the baseline
cannot be net-new against it, is sound; what it does not cover is a bulk *index* of that archive, which
converts our binding constraint from a rate limit into a download. Some of
those closures are now permanent in a useful way: one prize was priced at its ceiling from a published
figure rather than by buying it, and a second was settled by discovering that the restriction covers the
*index* files and not merely the content, which had been assumed and never tested.

**A stale closure is worse than no entry**, and this round found one. A collection had been recorded as
having an unreachable distributor; the distributor is alive and selling. The verdict did not change,
because size closes it anyway, but the recorded *reason* did, since a reason that has expired invites the
same fruitless re-probe every time the register is read.

**Three of our own alarms were found reporting the opposite of the truth**, which is worth stating in a
report about method because an alarm that cries wolf is worse than no alarm: it trains the reader to skip
it. One fired by design on a condition that was expected. One counted a single background process as two
and would have destroyed a healthy one on every check. One reported a dead source as revived when a
squatter had simply parked the domain, which was fixed by reading the response body the checker was
already fetching. Each is now pinned by a test.

**The boundary, stated plainly, because overclaiming it would be the easiest thing to do here.** The
mechanical half runs unattended and correctly: noticing that a collector has died, that a journal is
sitting unbanked on another machine, that a file on disk was never read, that a target list predates the
current baseline, that a measurement was started and never finished. The other half is judgement:
inventing a hypothesis worth testing, writing the reader that turns a source into dated items, and
deciding whether a measured yield justifies building a collector. A program cannot do those, and one
claiming to would confidently price the wrong thing. So each cycle does all of the first and ends by
naming exactly what of the second is waiting.

**Why this is safe to run unattended at all**, which is the part that makes it more than a scheduler.
Every year assignment is a foreign key to the specific observation that supports it, the schema refuses
an assignment without one, and nine invariants run on every build. An unattended process therefore has
latitude about what to try and none whatever about what counts as proof. One of those invariants refused
this round's new source on its first ingest, over eleven records whose stored identifier could be read as
naming the wrong year, and the source entered only after that was corrected.

## 3. Where the additions come from

| Source | What carries the date | Evidence type | Admissible | Net-new pairs | Equivalent-English |
|---|---|---|---|--:|--:|
| `ukwa_link_source` | UK Web Archive crawl date | `link_source` | master | 92,646 | 90,825.1 |
| `isc_survey` | survey run date | `artifact_listing` | master | 115,104 | 61,759.1 |
| `rdap_snapshot` | the registry's own `registration` event date | `whois_creation` | master | 87,657 | 54,209.7 |
| `usenet_announce` | post date of the announcement | `dated_directory` | master | 69,949 | 46,402.0 |
| `ia_cdx_bulk` | Wayback capture timestamp | `cdx_timestamp` | master | 37,291 | 31,726.9 |
| `usenet_address` | post date of the message carrying the address | `dated_directory` | master | 15,764 | 9,579.5 |
| `udrp_proceedings` | see `sources.md` | `artifact_listing` | master | 6,934 | 4,203.1 |
| `usenet_bare` | post date of the message carrying the address | `dated_directory` | master | 5,211 | 3,246.7 |
| `attrition_defacement` | see `sources.md` | `artifact_listing` | master | 3,929 | 1,874.9 |
| `enron_email` | the message `Date:` header | `dated_directory` | master | 2,163 | 1,360.2 |
| `maillist_archive` | the message `Date:` header | `dated_directory` | master | 633 | 395.3 |
| `trade_press` | the issue cover date | `dated_directory` | master | 212 | 134.7 |
| `tucows_catalogue` | software release date | `dated_directory` | master | 83 | 53.2 |
| `rtfm_faq` | the FAQ's revision header | `dated_directory` | master | 36 | 25.0 |
| **Total** | | | | **437,612** | **305,795.4** |

**All 14 are master sources, so all 437,612 pairs are admitted to the annual files.** None of them is candidate-only. Names may pass through the candidate pool on the way in, and this round many did, but a pair is only counted once a master source dates it.

**What "admissible" means here.** A source may back an entry in an annual file only if the evidence it
produces is one of the master types: `artifact_listing`, `cdx_timestamp`, `dated_directory`, `link_source`, `whois_creation`. Anything else, in practice a bare outbound link,
is `link_target` and can never assign a year; it goes to the candidate pool and ships separately in
`candidates.txt`. Two of the integrity invariants enforce this on every build: `no_candidate_leakage`
finds any annual assignment backed by candidate-only evidence, and `every_pair_has_master_evidence`
finds any assigned pair lacking a master-eligible row for that exact year. Both currently report zero.

Those master types divide into two kinds, and the difference is worth one paragraph because it is
the difference in how much each pair rests on.

**Self-dating artifacts, where the record itself is the authority.** `whois_creation` is the
registry's own registration event. `cdx_timestamp` is a capture the Internet Archive actually holds.
`artifact_listing` is a dated registry or survey file that enumerates names. For these the date is a
property of an authoritative record, so nothing further is needed and nothing further is done.

**Addresses printed inside a dated artifact**, which is `dated_directory`: a magazine page, a Usenet
post, a FAQ, an email. The artifact's date is sound, but a human typed the address, so these take one
extra filter described below.

Each source is named below by the **artifact that carries the date**, because that is what decides
what a (domain, year) pair rests on.

<!-- One subsection per source that is NEW OR CHANGED THIS ROUND, and no others.
     The table above already reports every source's volume and admissibility, so a
     subsection earns its place only by saying something the table cannot: what
     artifact carries the date, what population was asked, and what limit the
     source has. Name each one by the artifact that carries the date.

     Write the volume figures nowhere but the table. Every hand-typed number in
     this document has to be re-derived by a reader who cannot see the store, and
     the last round shipped one that contradicted its own generated table.

     Phase-4's six subsections are kept verbatim in
     `submissions/phase-4/report.md`; copy the shape from there, not the content. -->

### `ukwa_link_source`: the crawl year written in every row of a host link graph

The JISC UK Web Domain Dataset host link graph. Each row is
`year|source_host|target_host<TAB>count`, and **field one is the year the crawl observed that link**,
so the date is per record and intrinsic rather than a property of the file. Only the **source** host is
admitted: it was fetched successfully in that year for the row to exist at all, which is a fact about
the source. The target host was merely pointed at, which shows nothing about the target, so it carries
`link_target`, can never date a year, and ships in the candidate pool instead. The same file is read
twice under two source names for exactly that reason.

**What changed this round was our reading of it, not the source.** The parser stopped at the first row
past 2001, on a comment asserting the file was sorted by year with the window as its head. It is fifteen
concatenated shards, each sorted internally; the year column decreases fourteen times, the first
boundary falling at line 11,908,464. The scan had been ending at line 166,895 and reading **6.76%** of
the in-window rows. The correction is the whole file.

Its mean equivalent-English weight is the highest of any source in the table above, because a `.uk` link
graph is `.uk` by construction. The limit is the mirror image of that strength: it says nothing about
any web outside the United Kingdom.

### `isc_survey`: a dated census of the DNS, extended back to January 1997

The Network Wizards and ISC Internet Domain Survey walked the DNS twice a year and published the names
it found. The survey edition is encoded in the filename, and every name in a file was observed in the
DNS on that date, so the file's provenance fixes the year for all of its lines. The reviewer confirmed
in writing that a dated DNS survey may enter the annual files directly, and his 2026-08-15 update
restates it.

**The January 1997 edition was recorded in our own register as unrecoverable and was not.** Two true
statements, that the published name lists end in July 1997 and that ISC's own copies of two editions are
corrupt beyond repair, had been read together as closing the edition itself. A copy held by the Wayback
Machine had never been tested. It is intact, and the check that establishes this is the one the corrupt
copies fail: the file is in sort order end to end, whereas a desynchronised compression stream decodes
into plausible-looking text that is not. Independent corroboration, which matters more than any internal
check: the OECD's 1997 report cites this survey at about 828,000 domains and we count 824,791.

The standing limit is unchanged and worth restating: the claim is "seen in the DNS on the survey date",
not "registered", and the survey misses large sites that lacked reverse DNS.

### `usenet_announce`, `usenet_address` and `usenet_bare`: the same rule, re-run on a larger corpus

No new collection and no new rule. A hostname typed in a dated message is admitted for that year only if
some other source independently places that domain in an annual file, and names that failed that test
when first read have since been dated by the collectors. Re-applying the unchanged test to a corpus that
has grown admits them.

This is worth a subsection because of what it is not: it is not a relaxation. The identical predicate
was evaluated against a larger set of corroborating evidence. Registry-contradicted pairs are dropped
first, and two positive controls were measured before anything was written, one placing mention years
inside the domain's own capture span far more often than chance would give.

Deliberately excluded, because they were nearly included by mistake: link-graph edges cannot be promoted
onto their targets, however well corroborated the target is. Corroboration answers "is this domain
real", never "does this edge date its target".

## 4. The extra filter on typed addresses

The `dated_directory` sources are the ones where a human typed the address, so they carry the risk
that the string is not a real domain at all: an OCR error from a scanned page, a transcription typo,
a Usenet address deliberately munged against harvesters, or a file name that merely looks like a host.

Every one of them therefore passes a corroboration split before it may assign a year. The test is
exact and mechanical: **the domain must already appear in the annual files from a different source.**
That other source establishes the name is real; the dated artifact then supplies only the year. A
string appearing nowhere else is not asserted at all. It is demoted to the candidate pool, ships
separately in `candidates.txt`, and claims nothing.

The consequence is the guarantee worth having: **an invented name cannot reach an annual file**,
because a name nobody else ever saw has no other source to corroborate it. This is a property of the
pipeline rather than a review step that could be skipped, and it costs real volume. The table above
reports only what survived the split, which is why a figure quoted from it is always smaller, and
always the one this work is worth.

Beyond that, 5,076 of this round's pairs are confirmed by two or more independent collection lineages rather than one, and every asserted pair in the collection carries 1.5957 distinct sources on average.

## 5. CDX acquisition: tools, strategy, failures and yield

Every figure in this section is read from the collectors' own journals on disk by
`scripts/cdx_execution_notes.py`, which discovers the collector prefixes from the journal directory
rather than being told them. That detail is not incidental: an earlier version of this measurement was
given a hardcoded list of two prefixes, and it read clean for 31 hours while a collector wrote 3,219
answered queries and zero in-window captures under a third name.

**Tools.** `ark cdx` is our own client against the public Wayback CDX API. `scripts/build_query_queue.py`
selects and orders the population to ask. `scripts/supervise_cdx_pool.sh` runs the client in bounded
batches against an absolute deadline, restarting it between batches so a hung run cannot stall the
campaign. `ark ingest` banks each finished journal.

**What was asked, and how requests were batched.** Two populations on two machines. The local engine
works the **candidate pool**, names discovered from other sources and never yet dated, which is the
discovery half. A second host works **bracketed gaps**, a missing year Y on a domain already held for
Y-1 and Y+1, which is the completeness half. Batches are 600 queries at 8 concurrent workers with a
0.5 second base delay, adapting between 0.15 and 3.0 seconds under load, and a 70 second timeout.
A single request returns every in-window year for one domain at once, so one answered query can yield
up to six pairs.

| Collector prefix | Journals | Queries | Answered | Success | In-window hit rate | Distinct domains | In-window pairs |
|---|--:|--:|--:|--:|--:|--:|--:|
| `cdx_pool` | 148 | 97,888 | 82,221 | 84.0% | 41.6% | 82,807 | 51,176 |
| `cdx_q1` | 198 | 59,241 | 52,235 | 88.2% | 70.7% | 52,323 | 116,189 |
| `cdx_gap` | 104 | 41,816 | 35,964 | 86.0% | 98.4% | 36,355 | 134,864 |
| `cdx_q0` | 67 | 39,928 | 39,779 | 99.6% | 71.3% | 39,781 | 83,880 |
| `cdx` | 72 | 34,779 | 26,392 | 75.9% | 95.5% | 28,508 | 89,168 |
| `cdx_gap_vps` | 44 | 11,894 | 10,508 | 88.3% | 98.8% | 10,529 | 40,370 |
| `cdx_disc` | 6 | 3,222 | 3,192 | 99.1% | 44.6% | 3,193 | 2,032 |
| **All** | **639** | **288,768** | **250,291** | **86.7%** | **68.7%** | **251,664** | **517,679** |

**How failures were handled, and what the failures actually were.**

Of 288,768 queries, 250,291 were answered (86.7%). The 38,477 that were not divide into two kinds, and the smaller kind is the one usually discussed. **HTTP-level errors are 2,770 (0.96%)**: 0 rate limits (429), 1,994 server errors (500, 502, 503, 504) and 776 refusals (403). **Transport-level failures are 35,707 (12.37%)**: 27,520 connections refused or reset and 8,187 timed out. So the binding constraint is not a status code we could read and obey, it is the connection being dropped before a status exists. Rate limits and server errors are retried with exponential backoff honouring `Retry-After`; refusals and timeouts are retried with a widening delay and then requeued, so no domain is lost by one failure; a 403 is treated as a permanent answer for that host and is not retried.

**Two tuning levers were tested and both are closed on measurement.** Halving concurrency to 4 workers
made throughput worse, not better: 236 requests an hour against 378, with the failure share rising from
17% to 23%. Shortening the timeout is rejected in our own code, where 30 seconds answered 51 of 100
domains against 82 of 100 at 180 seconds. Raising concurrency is the only lever that would close the gap
arithmetically, and it is declined deliberately: this project has been refused by the archive three times
and the cost of a fourth exceeds the value of a round.

**Whether the CDX route is worth further expansion: yes, with a qualification.** It is not exhausted.
The queue is not the constraint while millions of candidates sit unasked against an engine clearing a few
hundred an hour, and the in-window hit rate above shows the population is still productive. The
qualification is that its yield per unit of wall-clock is bounded by a service we do not control, so it
should run continuously in the background and should not be the thing a round's target depends on.

## 6. External datasets and repositories searched

The reviewer's 2026-08-15 update asks for this explicitly, including identifiers where available, and
asks that the search not stop at one successful dataset. `docs/sources.md` is the complete register: it
carries every family evaluated, the measurement that closed it where one was closed, and the download
address where one exists. This section summarises rather than replaces it.

A closure is recorded with the number that produced it, and closures are re-probed automatically, because
a source recorded as unreachable may simply have had a host down on the day it was tried. That re-probe
distinguishes three ways a dead source answers HTTP 200 without being a source: a parking page, a bot
wall, and a stub that serves HTML where a data file should be. The third was added this round after the
largest closed prize in the register reported itself revived; the check is anchored on a positive
control, a file we demonstrably hold that returns the same stub.

**111 source families have been searched and recorded**: 24 developed far enough to earn their own section, and 87 evaluated and closed, each with the measurement that closed it. The developed ones:

- `prior_task`: the supplied baseline
- `isc_survey`: Internet Domain Survey host lists
- `afnic_fr`: `.fr` registry open data
- `ukwa_link_source` and `ukwa_link_target`: UK Web Archive host link graph
- `arquivo_ia` and `arquivo_roteiro`: Arquivo.pt capture indexes
- `odp`: Open Directory Project (DMOZ) RDF content dumps
- `early_web_cdx`: Internet Archive Early Web CDX dataset
- `ia_cdx_bulk`: Wayback CDX verification engine
- `rdap` and `rdap_snapshot`: registry creation dates
- `page_directory` and `page_expansion`: archived curated directory pages
- `internet_scout`: Internet Scout Report archive
- `ncsa_whats_new`: NCSA "What's New" announcement pages
- `ia_cdx`: per-year CDX verification (superseded)
- NYPW first-capture index: assessed and rejected on measurement
- Australian Web Archive: the CDX endpoint is reachable again
- `trade_press` and `trade_press_mention`: scanned computer magazines
- `usenet_address` and `usenet_address_mention`: the addresses the extractor never read
- `usenet_bare` and `usenet_bare_mention`: the bare `foo.com` in the message bodies
- `uucp_map_registry`, `uucp_map_creation`, `uucp_map_mention`: the UUCP maps
- `rtfm_faq` and `rtfm_faq_mention`: the Usenet FAQ mirror
- `usenet_announce` and `usenet_mention`: dated website announcements from Usenet
- `tucows_catalogue` and `tucows_mention`: the Tucows Software Library
- `maillist_archive` and `maillist_archive_mention`: public pipermail list archives
- `enron_email` and `enron_email_mention`: the FERC Enron corpus

The 87 closed families are listed under `## Evaluated and rejected` in `docs/sources.md`, one row each, naming the verdict and the number behind it. They are recorded so that negative results stay visible and the same ground is not broken twice.

**What the search has established about its own shape.** Two rules did most of the closing this round,
both derived from measurement rather than argument, and both are stated in section 2. The more useful
one for a reader planning further work is the exception to the second: a corpus derived from the same
archive as the baseline cannot be net-new against it, **unless** it is a bulk index of that archive, in
which case it is extremely valuable because it converts our binding constraint from a rate limit into a
download. The DRUM result described in section 1 is precisely that shape, and it is why the search is now
aimed at bulk dated corpora in research repositories rather than at directory pages.

## 7. New methods identified this round

**Re-applying an unchanged rule to a grown corpus.** A domain typed in a dated artifact is admitted only
if some other source independently places it in an annual file. Names that failed that test when first
read have since been dated by the collectors, so the same rule re-run promotes them. This round that was
worth **94,051 pairs and 61,196.7 equivalent-English for zero requests and zero new sources.** The
general form is worth more than the instance: in a mature corpus, re-examining held evidence against new
knowledge outperforms looking for new evidence, and nothing about it depends on a third party.

**Pricing before building.** Any dated corpus can be measured against the live store before a collector
is written: net-new records, net-new domains, mean weight, a contamination bound, and a saturating
projection beside the linear one. This has closed sources that would have looked plausible in a proposal
indefinitely, at a cost of a few requests each. Two figures show why it matters: one raw extraction
overstated a source 24-fold, and one linear projection overstated by thirty times.

**Adversarial verification of our own findings.** Source proposals are now checked by an independent pass
whose instruction is to refute rather than confirm, defaulting to rejection when it cannot verify a
load-bearing claim itself. This round that pass corrected proposals that had mistaken a maximum index for
a count, a collection-level date for a per-item date, and a physical line count of a file with embedded
newlines for a record count.

**Measuring the instruments, not just the data.** Five of our own alarms were found reporting the
opposite of the truth this round, including one that counted a single background process as two and would
have destroyed a healthy collector on every check, and one that reported the largest closed source in the
register as revived when the host was serving a 159-byte stub. Each is now pinned by a test. An alarm
that cries wolf is worse than no alarm, because it trains the reader to skip it.

**Testing a structural assumption instead of sampling for it.** The single most productive method change
of the round is one line long. A parser had been reading 6.76% of a two-gigabyte file for three weeks
because a comment said the file was sorted by year and the window was its head. That claim had been
verified, by checking that no in-window row appeared in the next five million lines; the file is fifteen
concatenated shards and the first boundary is at line 11,908,464, so the check stopped short by a factor
of 2.4. **The cheap form of that question is not a sample at all: ask whether the sort key ever
decreases, in one pass.** It admits no judgement about how far is far enough, and it recovered 92,646
pairs.

**Screening a public dataset against the baseline's own merge audit before pricing it.** The reviewer's
baseline ships a JSON audit naming what was merged into it. Checking that file first would have closed
the round's most attractive-looking lead, the exemplar dataset named in the brief, in one minute rather
than several agent-days: it had already been delivered in full by another contributor, and measures 0
net-new for us.

## 8. Limitations, and where further expansion is worthwhile

**Limitations of the result.**

- **Coverage of the archive is bounded by our query rate, not by its holdings.** Section 5 quantifies
  this. Any statement here about a domain having no capture means we did not obtain one, not that none
  exists.
- **The corroboration split costs real volume, deliberately.** Every typed address that no other source
  attests is refused rather than asserted, which is why figures quoted from section 3 are always smaller
  than a raw extraction would give. This is the guarantee that an invented name cannot reach an annual
  file, and it is bought with yield.
- **A registry creation date reads late for a re-registered name.** Where `whois_creation` is the
  evidence, the direction of error is loss rather than fabrication, which is the safe direction.
- **The candidate pool is large, mostly unattested, and part of it is names that never existed.** This
  round put a number on that for the first time, and it is worth stating plainly because the pool ships
  as its own artifact. Measured from our own CDX journals, the in-window capture rate among *answered*
  queries varies enormously by namespace:

  | TLD | answered | in-window | rate |
  |---|--:|--:|--:|
  | `.net` | 2,016 | 1,863 | 92.41% |
  | `.ca` | 9,003 | 8,164 | 90.68% |
  | `.org` | 30,352 | 26,845 | 88.45% |
  | `.com` | 58,975 | 50,672 | 85.92% |
  | `.uk` | 82,832 | 48,506 | 58.56% |
  | `.edu` | 3,370 | 1,357 | 40.27% |
  | `.gov` | 563 | 135 | 23.98% |
  | `.mil` | 8,234 | 21 | **0.26%** |

  The pool holds 216,303 undated `.edu` names, against an all-time `.edu` registrant population on the
  order of seven thousand. A sample shows why: `osartyrvrb.edu`, `rjhxf.mil`, `yjwuuxuqqa.gov`. They
  come from Usenet address mentions and are anti-harvester address munging. **So any equivalent-English
  ceiling computed over the pool is dominated by namespaces measured to be largely fictional**, and the
  high-weight ones are the worst offenders: `.mil` is nominally worth 185,927 at weight 0.9981 and about
  483 at its measured rate. The pool is delivered as it stands, with this measurement rather than
  without it, because trimming a delivered artifact on the last day is a worse answer than describing
  it accurately. None of this touches the annual files: a candidate cannot date a year, and the two
  integrity checks in section 3 enforce that on every build.
- **The equivalent-English metric is an aggregate TLD estimate**, as the brief states, and not a language
  classification of any individual site.

**Where further expansion is worthwhile, in order.** The first entry is measured rather than argued,
which is the form this question deserves.

1. **The bracketed gaps we already hold and have never asked about.** A domain dated in year Y-1 and
   Y+1 but not Y is the highest-probability query this project has: the domain is known to have existed
   on both sides of the gap, and the completeness engine answers such queries at 85 to 97%.
   **285,842 of them have never been queried.** Priced on 514 live queries rather than projected, that
   is **103,000 to 164,000 net-new pairs and 73,061 to 85,627 equivalent-English**, which is 0.88 to
   1.03 percentage points. It needs no new source, no download and no permission; it needs request
   throughput, which section 5 explains we do not have in quantity. A first estimate of this was 1.6 to
   1.9x higher and was cut on measurement before being written down here.
2. **Bulk dated corpora in research repositories.** The result described in section 1 establishes both
   that they exist and that they dwarf per-domain querying. Note the qualification the search
   established: the capture census found this round appears to be singular rather than the first of a
   family, since six further sweeps of the same repositories and collections returned nothing in window.
3. **The three evidence routes the 2026-08-15 update widened**: dated DNS survey presence, Arquivo.pt
   capture indexes, and UK Web Archive host and link graph records where the year association is explicit.
   The third is the most valuable to us because our holdings in that namespace are large and `.uk` carries
   the highest English weight of any namespace we hold in volume. Each is being verified against the
   actual record schema before anything is claimed, because a collection-level date presented as a
   per-item date is exactly the failure the evidence rules exist to prevent.
4. **Continued CDX querying**, as a background process rather than as a plan.
5. **Namespaces where the weight is high and our coverage is measurably thin**, principally the `.us`
   locality space: the store holds 217,619 in-window `.uk` domains against 18,278 `.us`.

**Where it is not worthwhile**, so the ground is not broken twice: sources that select for authority,
which cannot be net-new however large, and corpora derived from the same archive as the baseline unless
they are bulk indexes of it. Both rules are stated with their measurements in section 2 and applied in
`docs/sources.md`.

## 9. How to reproduce

All commands below are run from the **root of the unpacked archive**. `README.md` beside this file
gives the same three steps in more detail; if the two ever disagree, `README.md` is the one kept in
step with the packaging script.

**1. Check what shipped, about ten seconds, no rebuild.** Needs only `shasum` and `python3`.

```bash
bash verify.sh
```

**2. Rebuild the result from the shipped evidence, about a minute, no source data and no network.**
The code ships inside the archive and has to be unpacked first, which is why there is no `justfile`
at this level.

```bash
tar -xzf source/source.tar.gz -C source/ && cd source
uv sync
uv run ark rebuild ../provenance     # annual files, masters, candidates, manifest
uv run ark check                     # the integrity invariants
```

Then, still inside `source/`, confirm the rebuild matches what was shipped:

```bash
for y in 1996 1997 1998 1999 2000 2001; do
    cmp output/netnew/$y.txt ../additions/$y.txt
    cmp data/exports/$y.txt  ../masters/$y.txt
done
cmp output/netnew/evidence_manifest.csv ../additions/evidence_manifest.csv
cmp output/candidate_unverified.txt     ../candidates.txt
```

**3. Rebuild from the original sources**, a download and about twenty minutes. From inside `source/`:

```bash
cp -R ../baseline/original/. legacy-data/
just reproduce
```

That replays the collectors' stored journals in `data/raw/` rather than re-requesting the network, so
it gives the same answer every time. `source/README.md` documents each stage, and `sources.md` has the
download address for every source plus every family evaluated and **rejected** with the measurement
that killed it.

To collect **new** evidence rather than replay it, `just --list` inside `source/` shows one recipe per
source. Those need the network.
