# Internet Digital Ark: round report

Additions to the 1996-2001 annual domain lists, measured against `merged260810`.

**Every figure in the tables** is generated from the store by `scripts/report_figures.py` and
substituted by `scripts/fill_report.py`, so a table here cannot drift from the shipped files. The
handful of one-off measurements quoted in the prose of sections 2 and 3 are not regenerated per round;
each describes a specific run and is recorded with that run in `sources.md`.

---

## 1. What this round adds

| | |
|---|--:|
| Net-new (domain, year) pairs | **170,186** |
| Over unique domains | 158,831 |
| Domains absent from the baseline in every year | **129,851** |
| Equivalent-English added | **101,139.4** |
| Growth on the 6,226,386.4 baseline | **1.6244%** |
| Mean equivalent-English weight per pair | 0.5943 |

| Year | merged260810, this counting unit | Additions | Capture-backed |
|---|--:|--:|--:|
| 1996 | 648,313 | 5,858 | 4 (0.1%) |
| 1997 | 1,340,527 | 43,218 | 94 (0.2%) |
| 1998 | 1,147,924 | 14,979 | 852 (5.7%) |
| 1999 | 1,797,655 | 26,840 | 2,445 (9.1%) |
| 2000 | 1,806,813 | 43,061 | 8,503 (19.7%) |
| 2001 | 2,990,654 | 36,230 | 15,090 (41.7%) |
| **Total** | **9,731,886** | **170,186** | **26,988 (15.9%)** |

## 2. How these were found

This round the method was the work, so it is reported before the sources are.

**The generative question, which produced the round's one new source.** Rather than listing more places
to look, we asked what the sources that actually paid have in common. Registry creation dates, dated DNS
survey shards and a defacement mirror are all **machine-generated records about whoever happened to be
there**, not human curation of who was notable. Every family this project has rejected on measurement
selects for authority: Usenet relay hops collapsed 7.1 million entries into 4,736 domains a
capture-derived baseline already held in every year, and institutional link directories, award galleries,
mailing lists and a dated software index all failed the same way. So the question is not "where is
another list" but **"what else recorded everyone, with a date, for its own reasons"**.

A domain-dispute docket is that shape. A proceeding exists only because the domain was registered and
someone filed a complaint about it, so the record attests existence in that year **without depending on a
crawler having visited the site**, which is the property that makes the earliest years hard to reach any
other way. Measured against the live database: **87.7% of the domains it names were absent**, the highest
share of any source assessed on this project, because a disputed name is often a typosquat withdrawn
within weeks and a crawler never sees it.

**Five programs now carry the parts of that process that can be made mechanical.** Each encodes a
mistake already paid for once:

| | what it does | the mistake it prevents |
|---|---|---|
| screen | checks a proposal against the closed families, and reports whether each was closed by a **measurement** or by something being **unreachable** | re-testing a lead already killed; and, worse, leaving a source closed because a host was down three years ago |
| re-probe | re-asks every unreachable-class lead automatically, since the record already names the hosts that failed | a permanent closure recorded from a transient failure |
| price | measures any dated corpus against the live database: net-new records, net-new domains, mean weight, a contamination bound, and a saturating projection beside the linear one | quoting a raw extraction (one such figure overstated a source 24-fold) or a linear projection (one overstated by thirty times) |
| ledger | records what was proposed, priced, adopted or killed, with status | an unattended process re-proposing its own ideas |
| state | regenerates the statement of where the round stands from the programs that own each figure | a hand-written summary going stale, which is how three claims in the previous one were wrong within a day |

**What the method produced, including the negative results.** One source adopted. **Two closed on
measurement**: a dated software index returned 86 records because 94.7% of what it names was already
held, and a 1996 CD-ROM directory returned 7 at a 92.2% overlap. Both closed inside an hour at a cost of
two or three requests. **One reopened after being wrongly closed**: a registry had been recorded as
blocking us after returning HTTP 403 for over nine thousand consecutive requests, and re-probing it
slowly showed that was a rate limit rather than a block. It answers every query at a gentle pace, **38%
of those answers carry a date inside the window against 8.7% for the largest registry**, and it is now
the round's single largest contributor. We had closed the best route available by misreading a throttle.

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
| `rdap_snapshot` | the registry's own `registration` event date | `whois_creation` | master | 87,395 | 53,400.3 |
| `ia_cdx_bulk` | Wayback capture timestamp | `cdx_timestamp` | master | 26,839 | 25,228.1 |
| `isc_survey` | survey run date | `artifact_listing` | master | 42,299 | 14,956.4 |
| `udrp_proceedings` | see `sources.md` | `artifact_listing` | master | 7,837 | 4,763.2 |
| `attrition_defacement` | see `sources.md` | `artifact_listing` | master | 5,816 | 2,791.4 |
| **Total** | | | | **170,186** | **101,139.4** |

**All 5 are master sources, so all 170,186 pairs are admitted to the annual files.** None of them is candidate-only. Names may pass through the candidate pool on the way in, and this round many did, but a pair is only counted once a master source dates it.

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

Beyond that, 190 of this round's pairs are confirmed by two or more independent collection lineages rather than one, and every asserted pair in the collection carries 1.8296 distinct sources on average.

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
