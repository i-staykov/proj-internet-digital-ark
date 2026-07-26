# Internet Digital Ark: Delivery Report

Evidence-backed annual domain lists for 1996-2001, built on the supplied ~8.2M-line baseline and
shipped as a separate, verifiable set. The baseline is never modified.

Per-source detail is in `sources.md`. How to reproduce and verify is in the archive `README.md`.

## 1. Results

| | Domains | Pairs |
|---|--:|--:|
| **Net-new (this work)** | **463,566** | **1,322,365** |
| Baseline (read-only) | 4,824,656 | 6,866,913 |
| Merged total | 5,288,222 | 8,189,278 |

Net-new pairs by year: 1996 **100,650**, 1997 **1,039,572**, 1998 **15,849**, 1999 **26,873**,
2000 **57,644**, 2001 **81,777**. 1997 dominates because the supplied 1997 file held 219,918 pairs
against 1.21M in-window domains observed in that year's DNS survey.

Also shipped, and excluded from the score: **5,583 candidates** and **3,595,769 download seeds**
(section 5).

## 2. Counting unit, normalization, extraction

The counting unit is the **registered domain**. Every host or URL from every source, baseline
included, passes through one canonicalizer:

1. **Normalize.** Percent-decode, trim, lowercase; strip scheme, path, query, fragment, userinfo,
   port and stray edge punctuation.
2. **Require hostname syntax.** Letters, digits, hyphens, no hyphen at a label edge. IP addresses
   are not domains.
3. **Split against a pinned Public Suffix List** snapshot, committed with the code, plus a patch for
   the nine retired ccTLDs the list omits. Both a registered label and a public suffix must remain,
   which rejects bare suffixes (`ab.ca`) and suffix-less names (`localhost`).
4. **Keep the registered domain.** `www.example.com` and `shop.example.com` both become
   `example.com`.

Pinning the suffix list makes extraction deterministic and offline.

**Validity** is whatever survives step 3. **Salvage** is conservative: leading and trailing
punctuation is stripped (`.www.foo.com`) as a transcription artifact, but a leading hyphen never is,
because that would alter the name. Nothing is guessed, originals are never edited, and every
correction and drop is written to an audit file with its reason.

## 3. Dropped-domain statistics

8,224,963 supplied lines yield 4,824,656 domains over 6,866,913 pairs. The 1,358,050-line difference
is not lost domains:

- **12,220 lines (0.149%) excluded**, grouped by reason as 9,329 distinct entries in
  `dropped_domains.txt`: invalid hostname syntax 5,197, bare public suffix 1,418, no known public
  suffix 1,382, IP address 1,298, invalid character 34.
- **1,345,830 lines collapse**, because `www.foo.com`, `shop.foo.com` and `foo.com` are three
  supplied lines and one registered domain.

The supplied merge statistics count hostname lines while this counts registered domains, so the two
are not directly comparable. The normalization audit records ~1.45M corrected lines, in `audit/`.

## 4. Annual evidence logic and evidentiary standard

**A domain reaches an annual file only with item-level evidence for that specific year.** An earlier
appearance never implies a later year; a registration date never implies the years after it.

This is structural, not conventional: each annual assignment is backed by a `NOT NULL` foreign key
into one specific evidence row, and the function that creates assignments refuses candidate-only
evidence.
| Evidence type | What one row asserts | Annual file |
|---|---|---|
| `cdx_timestamp` | A web-archive capture, in-year timestamp, HTTP 200 | Yes |
| `artifact_listing` | A line in a dated file whose provenance fixes the year (DNS survey, directory dump) | Yes |
| `link_source` | The host was crawled that year, which produced the link-graph row | Yes |
| `dated_directory` | An editorial entry on a curated directory page captured on a known date | Yes |
| `whois_creation` | A registry record; two readings below | Yes |
| `prior_reused` | The baseline already lists this pair | Yes, excluded from the score |
| `link_target` | Merely linked to, which shows neither existence nor activity | **No**, candidate only |

**Two readings of registry data.** An RDAP response carries no history, so it attests **its creation
year only**. The `.fr` registry file attests every in-window year between creation and deletion,
because that registry documents its creation date as "the last creation date of the domain name",
placing it at or after any earlier deletion. Each row records its own basis, so either reading can be
recounted; rejecting the interval reading costs 69,111 pairs.

**Deduplication** is within each year, on `(domain, assigned_year)`. Cross-year repetition is
expected and required, since each year a domain appears in is evidenced independently.

**Per-domain basis.** `additions/evidence_manifest.csv` holds one row per added (domain, year) with
the source, evidence type and artifact behind it, so a domain in three annual files has three rows,
each documented separately. `provenance/trace.py` prints the same for any domain.

**Nine invariants** run over the whole store and exit non-zero on violation, so nothing ships
unverified. They check that every assignment points at eligible evidence for that exact year, that
no pair is duplicated or out of range, that every domain is well-formed, and that the net-new count
cannot be inflated.

## 5. Source contributions

**Eligible for the annual files.** Domains found by more than one source count in each row:

| Source | Type | Domains | Pairs |
|---|---|--:|--:|
| ISC DNS surveys | `artifact_listing` | 396,973 | 1,132,129 |
| `.fr` registry | `whois_creation` | 40,166 | 117,829 |
| UK Web Archive link graph | `link_source` | 16,235 | 23,821 |
| Arquivo.pt capture indexes | `cdx_timestamp` | 7,001 | 17,696 |
| Wayback CDX engine | `cdx_timestamp` | 207 | 11,943 |
| ODP directory dumps (2000, 2001) | `artifact_listing` | 3,369 | 8,423 |
| RDAP (journalled) | `whois_creation` | 5 | 5,341 |
| RDAP (legacy) | `whois_creation` | 833 | 3,106 |
| Archived directory pages | `dated_directory` | 20 | 1,577 |
| Internet Scout reports | `dated_directory` | 137 | 311 |
| Early Web CDX | `cdx_timestamp` | 175 | 182 |
| NCSA What's New | `dated_directory` | 1 | 7 |

**Candidate pool only: 5,583 domains**: 5,435 hosts linked to in the UK link graph, 87 from
archived ranked listings, 38 from the Stanford WebBase crawl host list, 19 named on directory pages
but attested nowhere else, 4 from earlier probes. WebBase carries no dates, so it seeds candidates
and never an annual file; 99.99% of its hosts were already held.

Evidence rows and pairs differ: Early Web CDX contributes 2.28M rows but 182 net-new pairs, because
the baseline derives from the same archive. Those rows are corroboration, and the net-new volume
comes from sources of different origin, which also explains the geographic skew.
**2,578,019 pairs carry two or more sources; 589,937 are confirmed by two or more genuinely
independent lineages**, 10,207 of them net-new.

**The seed pool** holds 3,595,769 hostnames and URLs over 2,195,955 domains, each dated by its
source, because the registered-domain unit discards what a crawler needs: given `foo.com`, a
downloader never reaches `shop.foo.com`.

## 6. Newly identified methods

**Registration intervals as per-year evidence**, but only after verifying a registry's own
documented creation-date semantics, and not extended to registries where those are unverified.
**Byte-range sampling** of a 47 GB index before committing to the download, which showed 11.9% of
sampled in-window domains were new. **Curated directory pages as dated evidence**, asserted only
where a page documents itself as an editorial catalogue. **Collection separated from
interpretation**: network stages write journals of raw responses and no evidence, so a change of
standard is a re-parse rather than a migration, and the result replays offline.

## 7. CDX execution notes

**Tools.** Two existing public interfaces: the `internetarchive` client
(`ia download early-web_cdx-lang-cdxa`) for the bulk Early Web CDX dataset, and a purpose-built
async client against the public CDX API at `web.archive.org/cdx/search/cdx` for targeted
verification.

**Seeds and strategy.** Targets are not arbitrary: a domain evidenced in two years but missing the
year between them is far likelier to have existed than a random name, so the queue is built from
those gaps, thinnest year first. One query per domain covers all six years by collapsing the result,
with client-side year deduplication and a per-year probe when a collapsed result returns truncated.
Requests run in batches of about 1,200 domains at 8 concurrent workers.

**Concurrency is the service's limit, and was measured.** Answered share by workers: 100% at 1-4,
82% at 8, 30% at 16, 17% at 32, so the operating point is 8. So was the timeout: the service kills
heavy queries at ~60.7 s, and a 30 s client timeout answered 51 of 100 domains against 82 at 180 s,
so the client waits 70 s.

**Errors and how they were handled.** An adaptive governor grows the delay 1.5x on 429/503/504
honouring `Retry-After` and eases 0.8x after five successes, floor 50 ms, ceiling 5 s. **A failure is
never recorded as an absence**: failures are counted per status and a domain is settled only by a
real answer. This was tested when the service refused connections for several hours: nothing was
corrupted and every refused domain stayed eligible. On recovery throughput had halved, so
concurrency was re-measured rather than assumed (185 answered/hour at 4 workers, 383 at 8, 262 at
12) and the optimum held at 8.

**Domains added.** 11,171 domains queried, 8,493 answered (76%), **11,932 net-new pairs**:
11,652 previously unevidenced years for domains already held, plus 199 new domains.

## 8. Page expansion and the discovery cycle

**Rounds and seeds.** Four rounds were run: a pilot on high-fanout early pages, then directory,
navigation and yellow-page sites; then the WWW Virtual Library's subject libraries, asserted as
curated catalogues; then further subject libraries found in the previous round's own outbound links.
That last round closes the loop: its seed list was produced by the pipeline, not by hand. Captures
use the Wayback `id_` modifier, which serves the original stored bytes rather than a rewritten page,
so the extracted links are the ones the author published.

**Depth decides yield.** Home pages returned 92 domains and zero new candidates, because a portal
front page links to its own categories rather than outward. Curated catalogues one level in returned
**1,577 pairs**, concentrated in 1998 and 1999.

**Why extracted names are split.** A curated page's capture date may evidence the domains listed on
it, which is sound for the page and unsound for the parser: archived HTML carries transcription
errors, and this route produced `arvard.edu` from a `harvard.edu` link. A sample put roughly 40% of
never-before-seen names in that class, so a name some other source already attests is kept as dated
evidence, and a name nothing else attests becomes a candidate.

**The cycle was closed, not just described.** Of 298 discovered candidates queried against the
archive, 233 answered and **198 (85%) held an in-window capture**, adding 278 pairs: high enough to
make discovered names worth verifying, against a 40% error rate that forbids trusting them.

## 9. Limitations

- **Geographic skew.** Additions over-represent `.fr`, `.pt` and `.uk`: the baseline already holds
  what a global crawl caught, so the complementary gains are national.
- **`.fr` undercounts.** The registry file omits names deleted before 28 January 2014, and the
  creation-date reset in section 4 drops re-registered names. It cannot overcount.
- **Uneven years.** 1998 and 1999 gained least; 2000 is partly served, since the surviving August
  2000 directory dump is a truncated prefix.
- **Negatives differ in strength.** An empty archive index is a stronger negative than absence from
  a survey, since that absence means only "not in that artifact".
- **One legacy tranche is weaker.** 3,106 pairs predate journalling and have no hashed source file.
  They were not re-queried: a re-query today returns different creation dates for domains that have
  changed hands, altering rather than reproducing the result. A rebuild from the original sources
  therefore returns 99.77% of the pairs, those domains falling back to the candidate pool.
- **Not exhausted.** 5,583 candidates await evidence and ~470,000 domains remain unqueried.

## 10. Whether further expansion is worthwhile

**Yes, in one direction.** Archive gap-filling converts hours into pairs at a stable measured rate
(1.07 pairs per domain queried against ~470,000 unqueried domains), so it is bounded by time spent
rather than by the source. Registry dates are worth running only because they use a different
service: 0.15 pairs per domain is structural, since a capture answers any year while a creation date
answers one. Page expansion is worth continuing only into leaf catalogues that document themselves
as curated.

**Everything exhaustible from a file has been exhausted:** the DNS surveys, the registry file, the
national archives and the early-web index are each complete datasets, fully ingested, with nothing
further found anywhere checked. Commercial WHOIS history, zone files and further national
archives are priced, gated or non-existent for this window; each check is recorded in `sources.md`.
