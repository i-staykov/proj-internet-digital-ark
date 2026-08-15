# Internet Digital Ark: round report

Additions to the 1996-2001 annual domain lists, measured against `[BASELINE]`.

**Every figure in the tables** is generated from the store by `scripts/report_figures.py` and
substituted by `scripts/fill_report.py`, so a table here cannot drift from the shipped files. The
handful of one-off measurements quoted in the prose of sections 2 and 3 are not regenerated per round;
each describes a specific run and is recorded with that run in `sources.md`.

---

## 1. What this round adds

| | |
|---|--:|
| Net-new (domain, year) pairs | **[TOTAL]** |
| Over unique domains | [UNIQUE] |
| Domains absent from the baseline in every year | **[NEWDOMAINS]** |
| Equivalent-English added | **[EE]** |
| Growth on the [EEBASELINE] baseline | **[EEGROWTH]** |
| Mean equivalent-English weight per pair | [EEMEAN] |

[PER_YEAR_TABLE]

**Against the 5% expected for this round, that is short, and the reason is measurable rather than
rhetorical.** 5% of the current baseline is 311,319.32 equivalent-English. The binding constraint this
round was not the supply of candidates and not the evidence rules: it was **request throughput against a
single archive**. Roughly 2.5 million candidate names sit unqueried: measured on 15 August 2026, 212,394
of them had ever been asked, because the two collectors together clear about 975 requests an hour and the
archive was that day refusing 437 of 600 queries from the busier one, holding it at its maximum back-off
of three seconds. Those three figures are a dated snapshot rather than a standing rate, which is why they
are given with a date. Raising concurrency is the
one lever that would close the gap arithmetically, and it is the one lever that risks losing the archive
altogether, which would cost far more than a round.

**The families that could have supplied a step change were searched and closed on measurement, not
assumed away**: historical zone files and bulk registry snapshots, research web crawl collections,
national web archives, and bulk archive indexes. Two of those closures are recorded as permanent. The
honest summary is that a corpus of this maturity grows by re-examining what it already holds and by
patient querying, and that a fivefold increase in a week would have required a bulk index that we
established does not exist in reachable form.

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

[EE_SOURCE_TABLE]

[ADMISSIBLE]

**What "admissible" means here.** A source may back an entry in an annual file only if the evidence it
produces is one of the master types: [MASTERTYPES]. Anything else, in practice a bare outbound link,
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

[CORROBORATION]

## 5. How to reproduce

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
