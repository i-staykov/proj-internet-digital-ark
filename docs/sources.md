# Sources

Every source that contributes evidence, with its acquisition method, how its year is established,
why it carries the evidence type it does, and what it actually yielded. Brief §III.11 requires that
each collected list be accompanied by an explanation of its acquisition method and time basis;
this file is that explanation, per source.

Figures are measured from the provenance store, not estimated. `net-new` means absent from the
supplied baseline. Two sources are still accumulating (`ia_cdx_bulk` and `rdap`), so their figures
are a floor.

**How per-source attribution is counted, since it is easy to misread.** A source's net-new domains
are those carrying its evidence, holding an assigned year, and having no `prior_reused` row. This is
attribution measured against the finished store, which is not the same as the scoreboard delta
observed when that source was ingested: a domain first contributed by source A and later also
evidenced by source B is attributed to both, while the delta credits only A. The two differ by a few
hundred out of ~460,000. Where a source's yield is quoted as a delta elsewhere, it is labelled.

## Summary

| Source | Evidence type | Files | Evidence rows | Net-new domains | Net-new pairs |
|---|---|--:|--:|--:|--:|
| `isc_survey` | `artifact_listing` | 5 | 1,662,395 | 396,973 | 1,132,129 |
| `afnic_fr` | `whois_creation` | 1 | 142,248 | 40,166 | 117,829 |
| `ukwa_link_source` | `link_source` | 1 | 39,454 | 16,235 | 23,821 |
| `arquivo_ia` | `cdx_timestamp` | 1 | 28,247 | 7,001 | 17,689 |
| `odp` | `artifact_listing` | 3 | 19,629 | 3,369 | 8,423 |
| `ia_cdx_bulk` | `cdx_timestamp` | 26 | 14,154 | 199 | 5,719 |
| `rdap` | `whois_creation` | live | 5,973 | 833 | 3,106 |
| `rdap_snapshot` | `whois_creation` | 8 | 5,626 | 3 | 2,373 |
| `page_directory` | `dated_directory` | 3 | 12,872 | 20 | 1,577 |
| `internet_scout` | `dated_directory` | 1 | 975 | 137 | 311 |
| `early_web_cdx` | `cdx_timestamp` | 224 | 2,278,722 | 175 | 182 |
| `ia_cdx` | `cdx_timestamp` | live | 11 | 8 | 11 |
| `arquivo_roteiro` | `cdx_timestamp` | 1 | 3,442 | 0 | 7 |
| `prior_task` | `prior_reused` | 6 | 6,866,913 | baseline | baseline |
| `ukwa_link_target` | `link_target` | 1 | 88,263 | 0 | 0 |
| `page_expansion` | `link_target` | 3 | 248 | 0 | 0 |

Generated from `data/reports/source_contribution.csv`, which `ark export` rewrites, so it is a
measurement of the shipped store rather than a hand-kept tally.

Note the difference between evidence rows and pairs: `early_web_cdx` contributes 2.28M evidence
rows but only 182 net-new pairs, because almost everything it holds was already in the baseline.
Those rows are not waste, they are corroboration.

---

## `prior_task`: the supplied baseline

**What it is.** The six annual files provided with the task (`1996.txt` through `2001.txt`),
holding 8,224,963 hostname lines, plus `merge_stats_new0714.csv` describing how they were built.

**How obtained.** Provided. Loaded read-only and never modified: `ark ingest-legacy`.

**Date semantics.** The file a line appears in *is* its year. No inference.

**Evidence type: `prior_reused`.** Prior evidence reused under III.1. Excluded from the scored
metric, because it is the baseline rather than an addition.

**Yield.** 8,224,963 supplied lines become **6,866,913 (domain, year) pairs over 4,824,656
registered domains.** That 1,358,050-line difference decomposes as:

- **12,220 lines (0.149%) excluded** as yielding no valid registered domain (bare IP addresses,
  malformed names, bare public suffixes). Every one is listed with its reason in
  `dropped_domains.txt`.
- **1,345,830 lines collapsed, not lost.** `www.foo.com`, `shop.foo.com` and `foo.com` are three
  supplied lines and one registered domain, which III.8 mandates as the counting unit.

Per year, supplied lines against pairs held:

| year | supplied lines | pairs held | difference | % |
|---|--:|--:|--:|--:|
| 1996 | 617,750 | 510,577 | 107,173 | 17.3% |
| 1997 | 311,988 | 219,918 | 92,070 | 29.5% |
| 1998 | 1,204,391 | 906,846 | 297,545 | 24.7% |
| 1999 | 1,904,473 | 1,425,651 | 478,822 | 25.1% |
| 2000 | 1,416,486 | 1,318,871 | 97,615 | 6.9% |
| 2001 | 2,769,875 | 2,485,050 | 284,825 | 10.3% |

**Caveat that matters for comparison.** The supplied `merge_stats` counts hostname lines; this
pipeline counts registered domains. Neither is wrong, they count different things, and the two
figures must not be compared directly. 1997 shows the largest reduction simply because it has the
most `www.`-style duplication.

**Brief clause.** III.1 (reuse prior evidence), III.8 (registered domain as the unit).

---

## `isc_survey`: Internet Domain Survey host lists

**What it is.** The Network Wizards / Lottor / ISC Internet Domain Survey `.domains` lists, a DNS
census taken on a stated date. Five intact files survive for 1996-1997.

**How obtained.** Rescued from rotting hosts and pinned by checksum in `data/raw/checksums.sha256`.
Copies on `ftp.isc.org` fail gzip integrity, and Wayback copies were already corrupt in 2003. The
January 1997 file is corrupt in every known copy and is a permanent gap.

**Date semantics.** The survey date is the `YYMM` code in the filename (`wb_nw_9607` = July 1996).
Every host in that file was observed in DNS on that date, so the file's own provenance fixes the
year for all of its lines. Files dated outside 1996-2001 are skipped whole.

**Evidence type: `artifact_listing`, and why.** A line in a dated data file whose provenance fixes
the year. The brief lists dated index files among valid time-evidence sources (§VII), and this
reading was confirmed in writing on 2026-07-24 as direct annual evidence needing no archive
recheck.

**Yield.** 2,450,346 records read, **1,662,395 evidence rows, +396,973 net-new domains / +1,132,129
net-new pairs.** The single largest contribution, and 1997 alone accounts for over a million pairs
because the supplied baseline barely covered that year (the July 1997 survey lists 1.21M in-window
domains against 219,918 in the supplied 1997 file).

**Caveats.** The evidence is narrower than a registry zone: "seen in DNS with at least one host on
the survey date" rather than "registered". That is arguably *stronger* than an archive capture as
proof a domain was live, but it is a different claim and is stated as such. Absence from a survey
means only "not seen in that survey", which is weaker than an empty archive index.

**Reproduce.** `ark ingest isc_survey data/raw/isc_survey/*.gz`

**Brief clause.** §VII (dated index files), III.1.d.

---

## `afnic_fr`: AFNIC `.fr` registry open data

**What it is.** The monthly `.fr` open-data file published by AFNIC, the French registry:
`202606_OPENDATA_A-NomsDeDomaineEnPointFr`, 122 MB zip expanding to a 697 MB semicolon-delimited
UTF-8 CSV of 10,050,194 rows, exactly one row per domain name.

**How obtained.** Downloaded from `https://opendata.afnic.fr/`. Open licence, attribution only.

**Date semantics, and the argument for using a span.** Each row carries a creation date (column 11)
and a permanent-deletion date (column 12, blank when the name is still registered). The evidence
claim is that the domain was registered in every year the span covers, which needs one thing to be
true: that the registry records a *new* creation date when a deleted name is registered again.
Otherwise a creation date could predate an undetected gap.

AFNIC states the behaviour in its own registrar documentation, *Technical Integration Guide* v3.0
(27 February 2015), on the `domain:info` fields:

> `<domain:crDate>` … in the current version of this interface, the timestamping information is
> **not aligned with the role described in RFC 5731** but copied from the "Whois" pattern. **The
> creation date is the last creation date of the domain name** or the date of the last transmission
> (trade or recover).

The same sentence appears in the authoritative French edition and in AFNIC's 2009 EPP specification
and its 2008 predecessor: four editions over seven years. Note that AFNIC is explicitly warning
registrars that its creation date does *not* follow standard EPP object semantics, so this could
not have been settled by reasoning from the RFCs.

That yields a proof rather than an assumption. `crDate = max(last creation, last transmission)`, and
both of those events necessarily fall after any prior deletion, since a deleted name must be created
again to exist. So `crDate` is always at or after the last deletion, and the span
`[crDate, deletion-or-now]` **contains no deletion event**. It is a continuous registration interval
by construction, which carries both the 11,880 domains with a published deletion date and the 43,652
without. (Those sum to one more than the 55,531 total because a single registered domain receives
both an active and a withdrawn span, two supplied rows having collapsed onto it.)

Live corroboration, reproducible from the open-data file plus one `whois -h whois.nic.fr` query:
`bennegens-couverture.fr` (open data: created 30-05-2020, deleted 28-06-2026; WHOIS today: created
2026-07-10) and `mintrocket.fr` (open data: created 22-04-2022, deleted 19-06-2026; WHOIS today:
created 2026-07-10). Deleted in June, re-registered in July, creation date advanced, original gone.

**Evidence type: `whois_creation`.** Master, for every in-window year the span covers. Each row
stores its span verbatim (for example `registered 16-03-1999..active`), so any single assignment can
be checked from the row alone.

**Yield.** 142,706 in-window records, **142,248 evidence rows over 55,531 `.fr` domains, +40,166
net-new domains / +117,829 net-new pairs.** The largest lift to the thin years: 1998, 1999 and 2000
each rose 5.7x to 6.1x.

**Caveats.**
- **The errors are one-directional.** Because `crDate` can only be later than the true first
  registration, a domain first registered in 1998 but traded or re-registered in 2010 reports
  creation 2010, falls outside the window, and is dropped. The tranche undercounts and cannot
  over-count.
- **A creation date here is the later of (last registration, last holder change)**, since a
  transmission also resets it. It must never be described as the first-ever registration date.
- **File scope is a floor.** The guide states the file holds every name in the WHOIS at generation
  plus every name deleted since 28 January 2014, so `.fr` domains deleted before that date are
  absent. Verified against the file: the 11,879 in-window domains carrying a deletion date spread
  evenly across 2014-2026.
- **Geographic skew.** `.fr` only, which is complementary to the `.com`-heavy baseline.
- **Column-order trap.** The 2015 guide lists `Date de création` seventh; the 2026 file ships it
  eleventh. The parser reads the live header positions, verified against a real row. Code compared
  against the guide will look mismatched; the code is right.
- **Standards residual.** A verified premise makes the span *sound*; it does not make it evidence
  *tied to* a specific year in III.6's literal sense. Discounting the tranche to creation years only
  would remove 69,105 pairs, and every row stores its span, so that recomputation is mechanical.

**Reproduce.** Download the monthly A file from `opendata.afnic.fr`, unzip, then
`ark ingest afnic_fr data/raw/afnic/*.csv`

**Brief clause.** III.6, III.1.d.

---

## `ukwa_link_source`: UK Web Archive host link graph

**What it is.** The JISC UK Web Domain Dataset host link graph 1996-2010, rows of
`year|source_host|target_host<TAB>count`.

**How obtained.** The only surviving copy is a Wayback capture; the original host is a stale DNS
alias to a retired GitHub Pages domain, the successor path soft-404s the correct filenames, and the
dataset DOI 404s. Downloaded from the Wayback capture, which drops the connection partway, but the
file is year-sorted so the 1996-2001 head transferred completely.

**Date semantics.** The row's own year field. A source host produced a link in that year, which
means it was crawled and served content then.

**Evidence type: `link_source`, and why only the source host.** The *source* host of a link was
fetched with HTTP 200 in that year to produce the link, so its existence that year is directly
attested. The *target* host was merely linked to, which proves nothing about it: dead links,
typos and not-yet-registered names are all common. Targets are therefore candidate-only
(`link_target`) and never assign a year.

**Yield.** 166,890 in-window rows, **39,454 evidence rows over 32,865 source domains, +16,235
net-new domains / +23,821 net-new pairs**, concentrated in the later thin years.

**Caveats.** Source hosts are `.uk`-biased. The partial download's checksum is not reproducible
because the truncation point varies, but the 1996-2001 content is deterministic since it is always
the fully-transferred head. A recon estimate of "184k to 10.9M links per year" was wrong for this
file: 1996-2001 is only ~166,890 rows, and the 20.9 GB bulk is 2002-2010.

**Reproduce.** `ark ingest ukwa_link_source data/raw/ukwa/host-linkage.tsv.gz`

**Brief clause.** §V (host/link graphs), III.1.d, III.2 (targets to the candidate pool).

---

## `arquivo_ia`: Arquivo.pt `IA.cdxj` capture index

**What it is.** A 50.93 GB CDXJ capture index donated to Arquivo.pt by the Internet Archive,
covering the Portuguese web 1996-2007, roughly 124M captures.

**How obtained.** A resumable single-connection download of 8.5 hours, verified to the exact byte
and checksummed. Committed to only after a byte-range spike: six slices totalling 402 MB (0.79% of
the file) were parsed with the shipping parser and classified read-only, which showed 11.9% of
sampled in-window domains were new.

**Date semantics.** The 14-digit capture timestamp on each line.

**Evidence type: `cdx_timestamp`.** A web-archive capture with an in-year timestamp and HTTP 200 for
the domain or a subdomain. The gold standard, and the type every candidate is verified against.

**Yield.** 140.8M lines read, 14.82M in-window HTTP-200 captures over 14,188 domains, **+7,001
net-new domains / +17,689 net-new pairs**, 98.4% `.pt`, filling the thin years (1998 +912,
1999 +2,667, 2000 +4,747, 2001 +9,323).

**Caveats.** Its corroboration of baseline domains shares the baseline's Internet Archive lineage,
so it is cross-source but not provenance-independent; the net-new `.pt` domains are new facts
regardless. The spike over-predicted magnitude 3.3x (about 22k domains forecast against 7,001
actual) because distinct-domain density is not uniform across a SURT-sorted deep-crawl file. The
qualitative call held.

**Reproduce.** `ark ingest arquivo_ia data/raw/arquivo/IA.cdxj`

**Brief clause.** §V (archive indexes), III.1.d.

---

## `odp`: Open Directory Project (DMOZ) RDF content dumps

**What it is.** Three surviving ODP content dumps: a truncated prefix of the August 2000 full dump,
and two complete Kids-and-Teens dumps from June and November 2001.

**How obtained.** Rescued from Wayback and pinned by checksum. The full August 2000 dump is
unrecoverable: Wayback archived only the 2000 `structure.rdf`, which carries no external links. The
three full 2001 content dumps were checked in 2026 and are **not** retrievable: the URL serves a
2,392-byte "Page Has Moved" stub and the CDX index for `dmoz.org/rdf/content.rdf.u8.gz` holds
exactly one in-window row, the Aug-2000 prefix already held.

**Date semantics.** Triple-dated: the Wayback capture timestamp, the preserved origin
`Last-Modified` header, and a generation stamp inside the file itself
(`<!-- Generated at YYYY-MM-DD ... -->`).

**Evidence type: `artifact_listing`, and why this is not the III.4 candidate case.** III.4 names
DMOZ as a source without item-level year evidence, which would route it to the candidate pool. The
distinction that matters is *what artifact was ingested*. An undated DMOZ listing carries no year
and would indeed be candidate-only. What is ingested here is a **dated dump**: a downloaded file
with a generation stamp, where every curated external URL inside it is a line in that file and the
file's own date fixes the year for all of them. That is the same shape as an ISC survey list, and it
is the class the 2026-07-24 ruling blessed as direct annual evidence "when the year association is
explicit and documented". The year association here is explicit and triple-corroborated.

For the same reason the type is `artifact_listing` and not `dated_directory`: `dated_directory` is
reserved for a directory *page* captured by an archive on a known date, which is a different
mechanism (page harvesting) from a downloaded dump.

**Yield.** 93,854 URLs, **19,629 evidence rows over 19,367 domains, +3,369 net-new domains / +8,423
net-new pairs** (2000 +6,477, 2001 +1,946).

**Caveats.** Low net-new because ODP curated popular live sites that the baseline already holds.
The 2000 figure is badly undercounted: only a ~1 MB prefix of the ~170 MB August 2000 dump survives.
The 2001 dumps are Kids-and-Teens themed only, not the full directory. Directories also lag reality,
so a listing proves the domain was catalogued that year rather than that it served content, which is
weaker than a capture. Absence from a dump means only "not in that dump".

**Reproduce.** `ark ingest odp data/raw/odp/*.gz`

**Brief clause.** §VII (dated index files), III.4 (addressed above), III.1.d.

---

## `ia_cdx_bulk`: IA CDX verification engine

**What it is.** Per-domain queries against the public Wayback CDX server, asking which in-window
years hold a capture. One collapsed query answers all six years.

**How obtained.** `ark cdx` writes a per-run journal holding one JSON object per queried domain;
`ark ingest cdx_snapshot` turns journals into evidence. Collection never opens the store, so a
multi-hour run cannot block anything else. Full execution notes, including the measured concurrency
ceiling and error handling, are in report §5.1.

**Date semantics.** The 14-digit capture timestamps returned by the index, filtered to
`statuscode:200` and the 1996-2001 window. A year counts only if the archive returned a capture in
it, so there is no inference of any kind.

**Evidence type: `cdx_timestamp`.** Same standard as any archive capture.

**Yield so far.** Still accumulating: **2,286 evidence rows, 840 net-new pairs** over ~1,500
answered domains. Measured 1.15 net-new pairs per domain queried, and 95-100% of the bracketed-gap
population has at least one in-window capture, averaging 3.6 years each.

**Caveats.** Throughput is bounded by the service, not the client: ~1,000 answered domains per hour,
with concurrency past 8 producing connection failures rather than answers. Failures are never
recorded as absences, so a transport error leaves the domain eligible for a later run.

**Reproduce.** `ark gaps` then `ark cdx data/raw/cdx/gap_candidates.txt --workers 8` then
`ark ingest cdx_snapshot data/raw/cdx/cdx_<stamp>.jsonl.gz`

**Brief clause.** §VI (CDX as key infrastructure), VII.c, III.1.d.

---

## `rdap`: registry creation dates via RDAP

**What it is.** Registry RDAP lookups through the `rdap.org` redirector, reading the `registration`
event year.

**How obtained.** Originally written directly to the store; since re-architected so `ark rdap`
writes a per-run journal holding the whole response, and `ark ingest rdap_snapshot` interprets it.

**Date semantics.** The `registration` event date, and nothing else. An RDAP response carries the
current state of a registration plus that one historical timestamp: there is no registration
history, so it cannot speak to any other year.

**Evidence type: `whois_creation`, creation year only.** III.6 blesses "the annual file for the
target year in which the creation date falls" and rules out more: a creation date alone "does not
automatically establish that the domain remained registered ... in every subsequent year". An
earlier version of this pipeline read a creation date plus present registration as a continuous
span, which required an unverified premise about each registry's re-registration policy; 9,664 such
assignments were withdrawn on 2026-07-25. A domain dated outside 1996-2001 attests no year and
remains a candidate.

Note the deliberate asymmetry with `afnic_fr`, which does use a span: that premise is documented and
verified for one registry, and RDAP spans roughly 590 registries whose policies are not established.

**Yield.** **5,973 evidence rows, +833 net-new domains / +3,106 net-new pairs.** Measured ~0.15
net-new pairs per domain queried, against 1.15 for the CDX engine, because a capture answers any
year while a creation date answers one.

**Caveats.** The 3,106 pairs under this source name predate the journal architecture, so they have
no hashed source file and cannot be replayed from bytes on disk, unlike every other source. They
were deliberately not re-queried, because a 2026 re-query returns a *different* creation date for
any domain that has since changed hands, which would silently alter the result set rather than
reproduce it. `bbc.co.uk` illustrates the standard's cost: registered 1994-12-13, demonstrably alive
across all six years, and RDAP alone attests none of them.

**Reproduce.** `ark gaps --creation` then `ark rdap data/raw/rdap/creation_candidates.txt` then
`ark ingest rdap_snapshot data/raw/rdap/rdap_<stamp>.jsonl.gz`

**Brief clause.** III.6, III.10.c.

---

## `early_web_cdx`: IA Early Web CDX dataset

**What it is.** The Internet Archive's "Early Web" CDX language dataset, 224 classic-CDX files
covering 1996-1999.

**How obtained.** `uvx --from internetarchive ia download early-web_cdx-lang-cdxa --glob='*.cdx.gz'`

**Date semantics.** The 14-digit capture timestamp.

**Evidence type: `cdx_timestamp`.**

**Yield, and the strategic finding it produced.** 4,210,462 records, **2,278,722 evidence rows, but
only +175 net-new domains / +182 net-new pairs: a 99.99% overlap with the supplied baseline.** That
result established the project's direction, because it demonstrates the baseline is
Internet-Archive-derived, so net-new volume has to come from non-IA populations: DNS surveys,
national registries and national archives.

**Caveats.** Its 2.28M evidence rows are corroboration rather than growth, and that corroboration is
Internet-Archive-on-Internet-Archive, so it is cross-source but not provenance-independent. All 175
net-new domains are `www`-label registrations under a public suffix (`www.cl`, `www.com.pk`), and
five of five spot-checked resolve on Wayback.

**Brief clause.** §V, III.1.d.

---

## `page_directory`: archived curated directory pages (section VII expansion)

**What it is.** Wayback captures of pages that are curated catalogues, read for the sites they
list. Brief §IV.i grants that such a page's capture date is item-level evidence for every domain
listed on it, with no further validation, which is what makes this route worth the care it takes.

**How obtained.** `ark download <seeds>` fetches each seed page's in-window captures and extracts
its outbound registered domains, writing a journal; `ark ingest expansion_directory <journal>` turns
that into evidence. Seed lists are tracked in `seeds/expansion/`. For the WWW Virtual Library
subject pages already harvested to `data/raw/wwwvl/` during a source survey,
`scripts/journal_from_wwwvl.py` writes the same journal format from the bytes on disk rather than
re-fetching them, and the ingest path is then identical.

**Date semantics.** The 14-digit Wayback capture timestamp of the directory page. A listing dated
1998 evidences its entries for 1998 only; nothing is carried into adjacent years.

**Why the curated assertion is made per seed, on the record.** The `directory` marker in a seed file
is what promotes a page's links from candidate-only `link_target` to master `dated_directory`, so it
is never asserted from a hostname's reputation. For the Virtual Library it was taken from the
catalogue's own 1999-01-25 capture, which declares itself "an expert-run catalog of sections of the
web" with `DC.Type: Bibliography` and lists its subject sections; those sections are the pages
seeded.

**Guard against phantom domains.** A listing is a claim by the linking page, and archived HTML
carries transcription typos: this route produced `gov.edu` and `gintysuooly.com`, and a review of
the same source measured roughly 40% of never-before-seen names as typos. So a name that no other
source attests is written to a separate journal and ingested as `expansion_links`, which is
candidate-only, while names already attested independently are asserted under IV.i. Of 1,267
net-new pairs, all but a handful sit on domains corroborated elsewhere.

**Yield.** 11,336 evidence rows, **1,267 net-new pairs over 15 net-new domains**, concentrated in
the thinnest years: 1998 +485 and 1999 +464. Per-round figures and the round 1 negative result are
in the decision log.

**Caveats.** (a) English-language and academically weighted, since the Virtual Library is a
university-maintained subject catalogue; (b) the corroboration split depends on what the store
already held when the journal was written, so it is run after the bulk sources, not before;
(c) 28 of 46 round 2 seed pages had no usable in-window capture, which is normal for 1990s hosts.

---

## `internet_scout`: Internet Scout Report archive

**What it is.** The Internet Scout Report, a weekly curated review of scholarly, government and
educational sites, harvested over OAI-PMH.

**How obtained.** OAI-PMH bulk harvest with a browser user agent (a bot user agent returns 403).

**Date semantics.** The `dc:date` on each record gives the issue year; the `dc:identifier` gives the
reviewed URL.

**Evidence type: `dated_directory`.** An editorial entry on a dated directory artifact.

**Yield.** 21,922 records, **975 evidence rows over 686 domains, +137 net-new domains / +311 net-new
pairs**, spread across all six years.

**Caveats.** Low yield for a structural reason worth recording: 18,508 of 21,922 records carry no
`dc:date` at all (verified genuinely absent from the feed, not a parse miss) and cannot be dated. An
earlier estimate of 2,000-5,000 net-new domains assumed per-record dates that mostly do not exist.

**Reproduce.** `ark ingest internet_scout data/raw/scout/scout_oai.xml`

**Brief clause.** §IV.c, §V.1, III.1.d.

---

## `arquivo_roteiro`: Arquivo.pt `Roteiro.cdxj`

**What it is.** A 13.6 MB CDXJ index of a 1996 crawl of the Portuguese web, about 75,000 pages.

**Date semantics.** Capture timestamps, all 1996.

**Evidence type: `cdx_timestamp`.**

**Yield.** 44,379 captures over 3,442 domains, **+0 net-new domains / +7 net-new pairs.** 1996 was
already dense from the baseline, Early Web and ISC, and its European academic hosts were held.
Value is the 3,442 corroborating rows and a second, non-IA archive lineage.

**Reproduce.** `ark ingest arquivo_roteiro data/raw/arquivo/Roteiro.cdxj`

**Brief clause.** §V, III.1.d.

---

## `ia_cdx`: per-year CDX verification (superseded)

The original verification path, six queries per domain (one per year), used to prove the pipeline
end to end. **11 evidence rows, 8 net-new domains.** Superseded by `ia_cdx_bulk`, which answers all
six years in one query. Retained because its rows are real evidence and it carries a per-record
Wayback URL.

---

## Registered but not yet contributing

`rdap_snapshot` and `cdx_snapshot` are source specifications for the journal-ingest path;
`cdx_snapshot` writes under the source name `ia_cdx_bulk`. `deduplicated_urls_2001-2002` and
`mid_slice` are candidate-only source names with zero evidence rows, retained so earlier seeding
runs remain attributable.

`page_expansion` holds the candidate-only half of the section VII route: outbound links from pages
not asserted to be curated directories, plus names from directory pages that no other source
attests. 242 evidence rows and, by design, **zero pairs**. It is doing its job when it stays at
zero, because every domain it holds is queued for verification rather than credited on the say-so
of a page that linked to it.

---

## Evaluated and rejected

Recorded so that negative results are visible rather than silently omitted, as §VIII expects.

| Source | Verdict |
|---|---|
| Stanford WebBase 2001 (via LAW) | 118M URLs to 603,245 registered domains, **99.99% already held**. Retired as a growth source |
| `deduplicated_urls_*` (supplied seeds) | Effectively exhausted: 200k lines probed yielded 3 domains not in the baseline |
| Common Crawl | Earliest collection is 2008-05; capture timestamps fail the in-window evidence bar |
| Arquivo.pt bulk `AWP*` collections | 214 files, sampled slices are all 2008. Out of window (`Roteiro` and `IA.cdxj` are the in-window exceptions) |
| UKWA per-year bulk CDX | Not publicly retrievable in 2026: dead host, soft-404 successor, 404 DOI, never Wayback-captured. Access requested |
| ODP full 2001 content dumps | Verified unavailable in 2026: the URL serves a "Page Has Moved" stub |
| ODP full Aug-2000 content dump | Unrecoverable; only `structure.rdf` was archived, which has no external links |
| Public 1998-2001 zone files | None survive anywhere checked (DNS-OARC, resellers, academic torrents) |
| Australian Web Archive (PANDORA/Trove) | The CDX endpoints at `webarchive.nla.gov.au/awa/cdx` and `web.archive.org.au/awa/cdx` return **HTTP 200 carrying an Anubis anti-bot proof-of-work challenge**, not CDX data. Machine access would require solving the challenge, so the archive is not usable programmatically. Worth recording precisely, because an earlier check read the 200 status as a live endpoint without reading the body |
| Other ccTLD registry open data | Nothing free reaches 1996-2001. CENTR publishes aggregates only; OpenINTEL starts 2015; commercial WHOIS is paid. AFNIC `.fr` is the sole open registry file with in-window creation dates |
| SNAP web graphs | Nodes are anonymised integers with no URL mapping |
| Yahoo! Webscope AltaVista graph | Programme unreachable; crawl date too vague for per-year evidence |
| TREC WT10g / VLC2 | Agreement-gated, distributor unreachable, small in domain terms |
| Yahoo! Directory | No machine-readable dump was ever published |
| GeoCities derivatives, DNS Census | 2009 and 2013 respectively, out of window |
| Post-July-1997 ISC `.domains` lists | Do not exist; later survey editions publish aggregate counts only |
| ISC January 1997 file | Corrupt in every known copy. Permanent gap |
