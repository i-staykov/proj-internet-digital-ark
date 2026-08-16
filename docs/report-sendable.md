# Internet Digital Ark: round report

## 1. What this round adds

| | |
|---|--:|
| Net-new (domain, year) pairs | **267,686** |
| Over unique domains | 202,704 |
| Domains absent from the baseline in every year | **112,236** |
| Equivalent-English added | **166,531.1** |
| Growth on the 8,346,839.4 baseline | **1.9951%** |
| Mean equivalent-English weight per pair | 0.6221 |

| Year | merged260815, this counting unit | Additions | Capture-backed |
|---|--:|--:|--:|
| 1996 | 649,765 | 6,095 | 5 (0.1%) |
| 1997 | 1,358,646 | 40,791 | 40 (0.1%) |
| 1998 | 1,363,435 | 19,427 | 567 (2.9%) |
| 1999 | 2,745,535 | 43,745 | 1,946 (4.4%) |
| 2000 | 4,675,256 | 58,856 | 4,087 (6.9%) |
| 2001 | 2,991,302 | 98,772 | 29,784 (30.2%) |
| **Total** | **13,783,939** | **267,686** | **36,429 (13.6%)** |

**Against the 5% threshold this is short, and the arithmetic is worth setting out exactly, because the
threshold moved during the round.** 5% of the current baseline is **417,341.97** equivalent-English, and
the shortfall is **250,810.84**.

**The baseline was reissued mid-round, and it changed both sides of the ratio at once.** `merged260810`
held 11,362,034 records and 6,226,386.4245 equivalent-English. `merged260815` holds 15,428,507
records and 8,346,839.3737, a **34.06% larger denominator**, both measured with the reviewer's own
`equivalent_english_domains.py` and its unchanged weight model. At the same time 39,492 pairs we had
collected became pairs the baseline already holds, worth **32,880 equivalent-English** of numerator.
Measured against the
release it was built against, this round reads 2.1641%; measured against the release that counts, it
reads 1.9951%. Both numbers are correct and only the second is the one being accepted against.

**The reason is the single most useful finding of the round, and it is not about us.** The new baseline
grew because another contributor delivered 4,063,995 accepted records drawn from one existing research
dataset, the University of Minnesota DRUM early-web link lists (DOI 10.13020/D62684). The per-year shape
of that delivery says what kind of artifact it was: 1,536 records for 1996 and 50 for 2001, against
950,371 for 1999 and 2,878,339 for 2000. **One bulk dated corpus was worth roughly twenty times our
entire round of per-domain archive querying.**

That is a measurement of our strategy, not our luck. This round's collection was optimised against the
constraint we could see, which was **request throughput against a single archive**: roughly 2.5 million
candidate names sit unqueried because the collectors clear a few hundred requests an hour between them,
and section 5 documents that campaign in full. A bulk dated corpus does not have that constraint at all.
It converts a rate limit into a file download.

The throughput constraint is real and measured. Over the round's last two days the engine querying from
our main host fell from **675 to 450 requests an hour** while the share of its requests carrying a usable
answer fell from **42.3% to 29.4%**. The second engine, on a different host, was flat over the same
period at 312 to 275 requests an hour and 85.8% to 84.5%. The two share their target-selection method
entirely and differ only in where they ask from, which identifies the archive rather than our queue or
our tuning as the cause. Raising concurrency is the one lever that closes the gap arithmetically and the
one lever that risks losing the archive altogether; reducing it was tried and measured worse; shortening
the request timeout is measured and rejected in our own code, where 30 seconds answered 51 of 100 domains
against 82 of 100 at 180 seconds.

**But that constraint is now the second-order problem.** The correct response to the DRUM result is not
to query faster. It is to search the same class of artifact that produced it, which is what section 6
reports and what the discovery system has been re-aimed at.

## 2. How these were found

This round the method was the work, so it is reported before the sources are.

**The question this round had to answer is what happens when the sources run out.** Each round consumes
the cheap ones, and the register of families closed on measurement now stands at roughly sixty. So the
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
web archives, bulk archive indexes, and the material already held on disk. Only the last paid. Some of
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
| `rdap_snapshot` | the registry's own `registration` event date | `whois_creation` | master | 87,657 | 54,209.7 |
| `usenet_announce` | post date of the announcement | `dated_directory` | master | 69,949 | 46,402.0 |
| `ia_cdx_bulk` | Wayback capture timestamp | `cdx_timestamp` | master | 36,335 | 31,033.5 |
| `isc_survey` | survey run date | `artifact_listing` | master | 38,780 | 14,013.3 |
| `usenet_address` | post date of the message carrying the address | `dated_directory` | master | 15,764 | 9,579.5 |
| `udrp_proceedings` | see `sources.md` | `artifact_listing` | master | 6,934 | 4,203.1 |
| `usenet_bare` | post date of the message carrying the address | `dated_directory` | master | 5,211 | 3,246.7 |
| `attrition_defacement` | see `sources.md` | `artifact_listing` | master | 3,929 | 1,874.9 |
| `enron_email` | the message `Date:` header | `dated_directory` | master | 2,163 | 1,360.2 |
| `maillist_archive` | the message `Date:` header | `dated_directory` | master | 633 | 395.3 |
| `trade_press` | the issue cover date | `dated_directory` | master | 212 | 134.7 |
| `tucows_catalogue` | software release date | `dated_directory` | master | 83 | 53.2 |
| `rtfm_faq` | the FAQ's revision header | `dated_directory` | master | 36 | 25.0 |
| **Total** | | | | **267,686** | **166,531.1** |

**All 13 are master sources, so all 267,686 pairs are admitted to the annual files.** None of them is candidate-only. Names may pass through the candidate pool on the way in, and this round many did, but a pair is only counted once a master source dates it.

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

Beyond that, 710 of this round's pairs are confirmed by two or more independent collection lineages rather than one, and every asserted pair in the collection carries 1.5932 distinct sources on average.

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
| `cdx_pool` | 144 | 95,488 | 80,248 | 84.0% | 42.1% | 80,801 | 50,551 |
| `cdx_q1` | 190 | 56,841 | 50,130 | 88.2% | 69.6% | 50,210 | 109,095 |
| `cdx_gap` | 104 | 41,816 | 35,964 | 86.0% | 98.4% | 36,355 | 134,864 |
| `cdx_q0` | 67 | 39,928 | 39,779 | 99.6% | 71.3% | 39,781 | 83,880 |
| `cdx` | 72 | 34,779 | 26,392 | 75.9% | 95.5% | 28,508 | 89,168 |
| `cdx_gap_vps` | 44 | 11,894 | 10,508 | 88.3% | 98.8% | 10,529 | 40,370 |
| `cdx_disc` | 6 | 3,222 | 3,192 | 99.1% | 44.6% | 3,193 | 2,032 |
| **All** | **627** | **283,968** | **246,213** | **86.7%** | **68.8%** | **247,546** | **509,960** |

**How failures were handled, and what the failures actually were.**

Of 283,968 queries, 246,213 were answered (86.7%). The 37,755 that were not divide into two kinds, and the smaller kind is the one usually discussed. **HTTP-level errors are 2,725 (0.96%)**: 0 rate limits (429), 1,994 server errors (500, 502, 503, 504) and 731 refusals (403). **Transport-level failures are 35,030 (12.34%)**: 27,151 connections refused or reset and 7,879 timed out. So the binding constraint is not a status code we could read and obey, it is the connection being dropped before a status exists. Rate limits and server errors are retried with exponential backoff honouring `Retry-After`; refusals and timeouts are retried with a widening delay and then requeued, so no domain is lost by one failure; a 403 is treated as a permanent answer for that host and is not retried.

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

**The register now stands at roughly sixty closed families plus the sources in the table in section 3.**
A closure is recorded with the number that produced it, and closures are re-probed automatically, because
a source recorded as unreachable may simply have had a host down on the day it was tried.

**26 source families are recorded in `docs/sources.md`**, each with what dates an item, where to obtain it, and the measurement that closed it where it was closed:

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
- Evaluated and rejected
- `usenet_announce` and `usenet_mention`: dated website announcements from Usenet
- `tucows_catalogue` and `tucows_mention`: the Tucows Software Library
- `maillist_archive` and `maillist_archive_mention`: public pipermail list archives
- `enron_email` and `enron_email_mention`: the FERC Enron corpus
- Measured, and each blocked on something other than work

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

**Measuring the instruments, not just the data.** Four of our own alarms were found reporting the
opposite of the truth this round, including one that counted a single background process as two and would
have destroyed a healthy collector on every check. Each is now pinned by a test. An alarm that cries wolf
is worse than no alarm, because it trains the reader to skip it.

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
- **The candidate pool is large and mostly unattested.** Its equivalent-English ceiling assumes every
  name earns a year, which will not happen; the realised figure is far lower and is not claimed.
- **The equivalent-English metric is an aggregate TLD estimate**, as the brief states, and not a language
  classification of any individual site.

**Where further expansion is worthwhile, in order.**

1. **Bulk dated corpora in research repositories.** The DRUM result establishes both that they exist and
   that they dwarf per-domain querying. This is the highest-value direction by a wide margin and it is
   where the discovery system is now pointed.
2. **The three evidence routes the 2026-08-15 update widened**: dated DNS survey presence, Arquivo.pt
   capture indexes, and UK Web Archive host and link graph records where the year association is explicit.
   The third is the most valuable to us because our holdings in that namespace are large and `.uk` carries
   the highest English weight of any namespace we hold in volume. Each is being verified against the
   actual record schema before anything is claimed, because a collection-level date presented as a
   per-item date is exactly the failure the evidence rules exist to prevent.
3. **Continued CDX querying**, as a background process rather than as a plan.
4. **Namespaces where the weight is high and our coverage is measurably thin**, principally the `.us`
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
