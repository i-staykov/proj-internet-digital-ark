# Experience summary

**D2 of the submission standard**: what worked, what did not, the measured yields, the limits, the
lessons, the techniques worth reusing, and where to go next. Deliberately short. The full register is
`sources.md`, which carries every family with its acquisition route and the measurement that closed
it; the full reasoning is `notes.md`, which is a dated log and not meant to be read end to end.

Every figure below is measured, not projected, and says what it was measured against.

## 1. What worked, with yields

**27 sources have contributed a dated record.** Measured over the store on 2026-08-18, excluding
records that arrived with the reviewer's baseline.

**These are cumulative across every round, and `report.md` section 3 is not.** That table is scoped
to the round being submitted, so the same source reads a smaller figure there, and neither is wrong:
this one answers "what has this method ever been worth", which is the question an experience summary
is for. A source can also appear here with a large figure and in section 3 with none at all, because
a round the reviewer has merged stops being net-new the moment he merges it.

| source | what dates a year | pairs | domains |
|---|---|--:|--:|
| `domain_creation_bulk` | registry creation date, one year each | 2,165,506 | 2,165,506 |
| `isc_survey` | the survey edition date | 1,252,609 | 1,173,608 |
| `usenet_announce` | the message date, under the corroboration split | 771,110 | 587,955 |
| `ia_cdx_bulk` | Wayback capture timestamp | 242,164 | 176,481 |
| `dartmouth_nber_captures` | the archive's own capture count per host-year | 227,273 | 197,749 |
| `rdap_snapshot` | registry creation date | 166,956 | 166,956 |
| `usenet_address` | message date, split | 123,068 | 109,372 |
| `afnic_fr` | registry record, a registration span | 117,829 | 53,871 |
| `ukwa_link_source` | the crawl date on the link record | 116,467 | 114,436 |
| `usenet_bare` | message date, split | 47,350 | 43,382 |
| 17 further sources | | 152,957 | |

**The single most useful ranking rule is yield per byte downloaded, not yield per request.** Measured
directly against each other: the capture census returned **997 net-new pairs per megabyte**, a Usenet
sample **15.5**. A 64x difference that no amount of extra querying closes, because one is a bulk file
and the other is prose to be mined.

**Bulk dated corpora beat per-domain querying by more than an order of magnitude.** One such file was
worth roughly twenty times a full round of archive querying. That is now the first thing looked for
rather than a lucky find.

**Two of the four largest gains in the last round were corrections to our own work, and cost nothing.**
A parser had been reading 6.76% of a UK Web Archive file held since July, because it assumed the file
was sorted by year and it is fifteen concatenated shards: fixing it recovered 92,646 pairs. And the
January 1997 Internet Domain Survey, recorded as unrecoverable because its host is dead, was intact in
the Wayback Machine under a successor hostname: 76,324 pairs. **Re-auditing what you already hold is
the cheapest source there is.**

## 2. What did not work

**91 source families are closed with the measurement that closed each**, in the rejected register.
The instructive ones:

- **Page-by-page outbound-link expansion.** Tested as a matched A/B over 240 archived pages. Seeding
  each dated site's home page harvested 53 domains for 3 net-new; selecting link-looking pages instead
  harvested 391, a 7.4x improvement, and yielded **5**. The reason is not the seeding but the coverage:
  **386 of those 391 were already held and every one was already dated.** A period page links to sites
  the store already has. So expansion earns archive requests only where a bulk link graph exists.
- **National web archives whose in-window holdings are an Internet Archive donation.** Repeatedly the
  same finding: every in-window row traces to an IA extraction, so a CDX-derived baseline holds all of
  it by construction. Most recently the Library of Congress Election 2000 CDX package, 1.97 GB of
  genuinely self-dating capture timestamps: a 10.7% sample gave 338 in-window domains and **zero** the
  store had never seen. The rejection is about redundancy, never about quality.
- **Per-domain RDAP over the candidate pool, past its first pass.** It was worth 166,956 pairs and is
  now spent: re-measured headroom is 0.107 points, not the 1.47 once claimed, and the Verisign pool is
  exhausted.
- **Authority-selected directories.** BUBL returned 386 of 388 already held; the `.edu` namespace
  measured 95.5% saturated. A curated list of important sites is the population everyone else has too.

## 3. Limitations, with the direction of the error

- **The capture census is a 2017 snapshot**, so its counts are a floor on what the archive holds now.
- **The registry compilation covers domains still registered in December 2024**, so it is
  survivorship-biased: a name created in 1998, dropped, and re-registered in 2015 reads 2015 and falls
  out of the window. The error direction is loss and the reverse cannot happen.
- **A creation date attests registration, not activity, and only for one year.** A domain registered
  in 1997 and live until 2001 gets 1997 from that route alone. Deliberately under-claimed: the parser
  emits one evidence row for one year, so a second cannot be written.
- **Human-authored corpora can contain hostnames that were never real.** The corroboration split asks
  whether the domain is dated in some annual file, never whether the mention was genuine, so an
  invented name later really registered passes. Measured on an RFC corpus, a large minority of
  surviving mentions are protocol placeholders. **Technical prose that invents plausible examples is
  the one typed shape where the split is not the wall.**
- **The local archive engine is request-rate bound, not candidate bound.** 2.29M pool targets sit
  unqueried against an engine clearing a few hundred an hour, and 12.34% of requests fail at transport
  level, which is the same throttling a status code cannot show.

## 4. Lessons learned

1. **A closure about one copy of an artifact is not a closure about the artifact.** Two of the largest
   recent gains were files recorded as unavailable that were available elsewhere. `just reprobe`
   re-asks every lead closed because something could not be *reached*, which is a different question
   from a lead closed on a measurement.
2. **To test whether a file is sorted, ask whether its key ever decreases.** Sampling it does not.
   A July check that verified a "year-sorted" claim stopped 2.4x short of the first shard boundary.
3. **Presence is not progress, and progress is not yield.** A journal full of misses grows exactly as
   fast as a journal full of hits. One collector ran 3,219 answered queries for zero captures against
   an exhausted shard while every health check read clean, for 31 hours.
4. **Never present a projection as a measurement.** The log records eleven distinct occasions on which
   this project fooled itself with a figure.
5. **A requirement that lives only in prose gets shipped unmet.** A build once filtered provenance to
   save disk and left 11,316,960 of 16,619,832 assignments citing evidence that was no longer there.
   All three existing checks passed, because every one read the additions manifest and none read the
   provenance. The fix was a fourth check, not more care.
6. **Falsification tests are only as wide as the constraint you thought of.** A registry source was
   admitted after checking that no TLD predated its own delegation, across the six TLDs delegated in
   2001. Seventeen records under a TLD delegated in **2010** were outside what that test could see.

7. **Prove a negative against a case known to be positive, and apply that to your OWN data and not
   only to sources.** Three filters were designed in one afternoon to remove domains that "could not
   have existed", and all three over-caught real names. "Nominet sold no second-level `.uk` until 2014"
   would have deleted `bl.uk`, the British Library. `.br` marked as never permitting second-level names
   holds `ansp.br`, the Academic Network at Sao Paulo. A narrow rule catching single-letter labels
   flags `0.com` and `x.com`. **The early DNS was heterogeneous, so short, odd and level-jumping names
   were often genuine**, and a registry's "opened in year X" date describes when a level opened to the
   public rather than when it began to exist. The exposure was 174.64 equivalent-English against a
   14,185 round, so the correct action was to leave the data alone.

## 5. Techniques worth reusing

- **Structural enforcement over convention.** `domain_year.evidence_id` is `NOT NULL` with a foreign
  key, so no code path can write a year without naming the observation that supports it. This is why
  an unattended agent can be given latitude about what to try and none about what counts as proof.
- **The corroboration split as a class decision.** Anything a human typed is admitted only if another
  source already places that domain in an annual file; self-dating records take no split. Which class
  a source belongs to is a judgement, and asserting it batch-wide is how a good source gets rejected:
  one survey family was worth 8,741 pairs correctly classified against 2,204 under the wrong one.
- **A human gate that reviews external evidence rather than an argument.** A source class cannot date
  a year until a person sets a `Decision:` line, and the request is machine-generated from a
  seeded-random sample with live links, the measured figures and the counterfactual. An agent arguing
  that its own find is master evidence is the least trustworthy artifact in the system.
- **Declarative probing before code.** A source is priced from a short TOML description with no Python
  written, which reproduced a 186-line collector's 8,923 records exactly from seven lines. A probe
  cannot date a year, so pricing is always safe.
- **Every reported figure generated from the store.** The report is a template of tokens filled by
  program, and the fill refuses to write a document containing an unfilled token. A hand-copied
  agreement count was already 219 stale a day after it was measured.
- **Two disjoint populations on two machines.** Bracketed gaps as an unattended completeness baseline,
  where the hit rate is flat across TLDs and ranking by English share is correct; the candidate pool
  beside the discovery loop that feeds it, where the hit rate varies from 36.9% to 90.6% by origin and
  the share must be multiplied by a measured rate.

## 6. Recommended directions

In order, each with what ranks it:

1. **Bulk dated corpora.** 997 net-new pairs per megabyte against 15.5. Nothing else comes close, and
   the search for them has no ceiling.
2. **National web-archive link graphs**, where the year association is explicit and the weight is
   high. `ukwa_link_source` returned a mean weight of 0.9803, the best of any source, because such a
   graph is almost entirely `.uk`. **Check first whether the in-window rows are an Internet Archive
   donation**, which is what closes most national archives.
3. **Registry datasets that publish creation dates as open data**, rather than behind a rate-limited
   query interface. This is the route that reaches 2001, where the web archives are thin: our 2001
   contribution was 982,881 accepted records against another contributor's 267.
4. **Academic repositories and replication packages** from early-web research. The reviewer's own
   worked example returned millions of records for another contributor. Papers from 1997 to 2003 that
   studied the web at scale generally deposited their crawl seeds somewhere.
5. **Re-auditing what is already held**, which has twice been the cheapest source available.

6. **Submitting sooner, which is not a source at all and outranks most of them.** The organisers score
   a cumulative total as the sum of the percentage increases awarded per submission, each measured
   against the benchmark as it stood when that submission arrived. Measured across the three intervals
   between published releases, other contributors added 8,511 then 424,091 then **1,082,013**
   equivalent-English per day, against our own 13,200. On the newest rate, work held for a week loses
   **38.5%** of its credit, and a 5% threshold recedes by 54,101 a day while per-domain querying closes
   it by 13,200, so that gap never closes. **The corollary is that a corpus you hold but have not
   submitted can be credited to somebody else**: the 4,063,995-record delivery that grew the benchmark
   most was measured here at 45,130 of 45,130 sampled pairs already held.

**Not worth expanding**: the 112 closed families, each recorded with its measurement so the same ground
is not broken twice.
