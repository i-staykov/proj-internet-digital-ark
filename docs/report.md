# Internet Digital Ark: Delivery Report

Evidence-backed annual domain lists for 1996-2001, built on top of the supplied ~8.2M-line baseline
and shipped as a separate, verifiable set. The baseline itself is never modified.

Per-source documentation, including the acquisition method and licence for each source, is in
[sources.md](sources.md); this report does not repeat it.

## 1. Results

| Metric | Value |
|---|--:|
| Net-new registered domains (absent from baseline) | **463,566** |
| Net-new (domain, year) pairs | **1,322,365** |
| Baseline domains (read-only) | 4,824,656 |
| Total domains in store | 5,293,805 |
| Total (domain, year) pairs in store | 8,189,278 |
| Evidence rows | 11,196,444 |
| Candidate pool (no year evidence yet) | 5,583 |

Net-new pairs by year:

| 1996 | 1997 | 1998 | 1999 | 2000 | 2001 |
|--:|--:|--:|--:|--:|--:|
| 100,650 | 1,039,572 | 15,849 | 26,873 | 57,644 | 81,777 |

1997 dominates because the supplied 1997 file was unusually thin: 219,918 pairs, against 1.21M
in-window domains observed in the July 1997 DNS survey. 1998 and 1999 were the weakest years and
were the priority for targeted verification.

An auxiliary pool of **3,595,769 hostnames and URLs** ships alongside the domain lists as download
seeds. It is not part of the score and is described in section 6.

## 2. Counting unit, normalization and registered-domain extraction

The counting unit is the **registered domain**. Every host or URL from every source passes through
one canonicalizer before it reaches the database, so identical rules apply to the baseline and to
every addition.

1. **Normalize.** Percent-decode, trim, lowercase. Strip scheme, path, query, fragment, userinfo and
   port, plus stray leading and trailing dots and commas.
2. **Require hostname syntax.** Labels of letters, digits and hyphens, with no hyphen at a label
   edge. Underscores are tolerated only in subdomain labels, which are discarded anyway. IP
   addresses are not domains.
3. **Split against the Public Suffix List**, using a pinned snapshot committed with the code plus a
   documented patch for ccTLDs retired since the window (`.yu`, `.an`, `.cs`, `.gb`, `.tp`, `.zr`).
   The result must have both a registered label and a public suffix, which rejects bare suffixes
   such as `ab.ca` and suffix-less names such as `localhost`.
4. **Keep the registered domain only.** `www.example.com`, `shop.example.com` and platform user
   paths such as `geocities.com/...` all reduce to `example.com` and `geocities.com`.

Pinning the suffix list is what makes extraction deterministic and offline: the same input yields
the same domain on any machine, today or later.

## 3. Validity and salvage rules

**Valid** means a registrable label plus a public suffix survives step 3 above.

**Salvage is conservative, deterministic and audited.** Leading and trailing punctuation is stripped
(`.www.foo.com`, `,foo.com`), because that is a transcription artifact rather than part of a name. A
leading hyphen is never stripped, because that would alter the name itself. Nothing is guessed:
no spelling correction, no TLD inference, no reconstruction of truncated hosts.

Originals are never edited in place. Every correction and every drop is written to an audit CSV with
its reason, and the merged master lists are exports rather than modified inputs.

## 4. Dropped-domain statistics

The supplied files hold **8,224,963 hostname lines**, which yield **4,824,656 registered domains
over 6,866,913 (domain, year) pairs**. The 1,358,050-line difference is not lost domains:

- **12,220 lines (0.149%) are genuinely excluded** because no valid registered domain remains. Every
  one is listed with its reason in `dropped_domains.txt`, grouped into five categories: invalid
  hostname syntax (5,197), bare public suffix (1,418), no known public suffix (1,382), IP address
  (1,298), and an invalid character in the registered label (34).
- **1,345,830 lines collapse** onto a registered domain that is still present, because
  `www.foo.com`, `shop.foo.com` and `foo.com` are three supplied lines and one registered domain.

Per year, supplied lines against pairs held:

| year | supplied lines | pairs held | difference | % |
|---|--:|--:|--:|--:|
| 1996 | 617,750 | 510,577 | 107,173 | 17.3% |
| 1997 | 311,988 | 219,918 | 92,070 | 29.5% |
| 1998 | 1,204,391 | 906,846 | 297,545 | 24.7% |
| 1999 | 1,904,473 | 1,425,651 | 478,822 | 25.1% |
| 2000 | 1,416,486 | 1,318,871 | 97,615 | 6.9% |
| 2001 | 2,769,875 | 2,485,050 | 284,825 | 10.3% |
| **total** | **8,224,963** | **6,866,913** | **1,358,050** | **16.5%** |

1997 shows the largest reduction because it carries the most `www.`-style duplication, and 2000 the
smallest. The supplied `merge_stats` file counts hostname lines while this pipeline counts
registered domains, so the two are each correct at their own unit and must not be compared directly.

The normalization audit records ~1.45M corrected lines with their reasons and ships in `audit/`.

## 5. Annual evidence logic

**A domain reaches an annual file only with item-level evidence for that specific year.** An earlier
appearance never implies a later year, and a registration date never implies the years after it.

This is enforced structurally rather than by convention. Each row in the annual assignments table is
backed by a `NOT NULL` foreign key into a specific evidence row, so no assignment can exist without
a particular observation behind it, and the function that creates assignments refuses candidate-only
evidence outright.

Each evidence type carries its own standard of proof:

| Type | What one row asserts | Annual-file eligible |
|---|---|---|
| `cdx_timestamp` | A web-archive capture with an in-year timestamp and HTTP 200, for the domain or a subdomain | Yes |
| `artifact_listing` | The domain is a line in a dated data file whose own provenance fixes the year: a DNS survey taken on a stated date, a directory dump with a generation stamp | Yes |
| `link_source` | The host was crawled successfully that year, which is what produced the host-link-graph row | Yes |
| `dated_directory` | The domain is an editorial entry on a curated directory page captured on a known date | Yes |
| `whois_creation` | A registry record establishes registration; see the two readings below | Yes, under the rules below |
| `prior_reused` | The supplied baseline already lists this (domain, year) | Yes, but excluded from the net-new score |
| `link_target` | The host was merely linked to, which shows neither existence nor activity | **No.** 88,511 rows, every one routed to the candidate pool |

**Two readings inside `whois_creation`, deliberately and visibly different.** An RDAP response
carries no registration history, so it attests **its creation year only** and nothing later. The
`.fr` registry open data is treated differently: it attests every in-window year of the interval
between creation and deletion, because the registry's own registrar documentation states that its
creation date is "the last creation date of the domain name", which places it at or after any
earlier deletion and makes the interval continuous by construction. Every row records the basis it
rests on (`rdap creation 1998` against `registered 16-03-1999..active`), so either reading can be
recounted independently. If a reviewer rejects the interval reading, the exposure is 69,111 pairs.

**Deduplication** is within each year: the primary key is `(domain, assigned_year)`. Cross-year
repetition is required and expected, since a domain appears in every year it is independently
evidenced for.

**Nine integrity invariants** run over the whole store and exit non-zero on any violation, so no
result ships unverified: the evidence wall is intact; no assignment rests on candidate-only
evidence; every assigned pair holds at least one eligible evidence row for that exact year; no
duplicate pair; every year falls inside 1996-2001; every stored domain is a well-formed registrable
name; the year named inside an evidence value equals the year it is filed under, with registration
intervals excepted by the argument above; no pair counted as an addition also carries baseline
evidence for that year; and nothing that earned a year is left sitting in the candidate pool. Each
invariant has a test that plants the corresponding violation and confirms the gate catches it.

## 6. Source contributions

Additions eligible for the annual files, by source:

| Source | Evidence type | Net-new domains | Net-new pairs |
|---|---|--:|--:|
| `isc_survey` | `artifact_listing` | 396,973 | 1,132,129 |
| `afnic_fr` | `whois_creation` | 40,166 | 117,829 |
| `ukwa_link_source` | `link_source` | 16,235 | 23,821 |
| `arquivo_ia` | `cdx_timestamp` | 7,001 | 17,689 |
| `ia_cdx_bulk` | `cdx_timestamp` | 199 | 11,932 |
| `odp` | `artifact_listing` | 3,369 | 8,423 |
| `rdap_snapshot` | `whois_creation` | 5 | 5,341 |
| `rdap` | `whois_creation` | 833 | 3,106 |
| `page_directory` | `dated_directory` | 20 | 1,577 |
| `internet_scout` | `dated_directory` | 137 | 311 |
| `early_web_cdx` | `cdx_timestamp` | 175 | 182 |
| `ncsa_whats_new` | `dated_directory` | 1 | 7 |
| `arquivo_roteiro` | `cdx_timestamp` | 0 | 7 |

Evidence rows and pairs are different measures, and the gap between them is informative rather than
wasteful: `early_web_cdx` contributes 2.28M evidence rows but only 182 net-new pairs, because the
supplied baseline is itself derived from the same web archive and the two overlap almost completely.
Those rows are corroboration. The net-new volume comes from sources with a different origin: DNS
surveys, a national registry, and national web archives. That is also what produces the geographic
skew noted in section 8.

**Additions eligible only for the candidate pool: 5,583 domains**, exported separately and never
mixed into the annual files. Composition: 5,435 hosts linked to in a national web archive's link
graph, 87 hostnames read from archived ranked listings, 39 from a crawl host list, 19 named on
curated directory pages but attested by no other source, and 3 from earlier probes. A candidate
leaves the pool only by earning year-specific evidence, and promotion is per year rather than per
domain.

**Cross-validation.** 2,578,019 pairs carry evidence from two or more sources. That figure overstates
independence, because sources drawing on the same body of observation are not independent witnesses,
so the stricter measure is reported alongside it: **589,937 pairs are confirmed by two or more
independent provenance lineages, 10,207 of them net-new.**

**The auxiliary seed pool** holds **3,595,769 distinct hostnames and URLs** over 2,195,955 registered
domains, each labelled with the year its source dates it to. It exists because the registered-domain
counting unit necessarily discards granularity a crawler needs: handed `foo.com`, a downloader never
reaches pages that only ever existed at `shop.foo.com`. It is built by re-reading each source through
the same parser used to ingest it, keeping the raw value instead of the canonical one, so a seed can
never disagree with the evidence it came from. It is reported separately from the score because it is
mostly deeper granularity on domains already held rather than new domains.

## 7. Verification against the web archive

One collapsed index query per domain covers all six years, with client-side year deduplication and a
per-year probe fallback when a response is truncated.

**Concurrency is the service's limit, not ours.** Measured answered share by worker count: 100% at 1
and 4 workers, 82% at 8, 30% at 16, 17% at 32. Past roughly 8 concurrent requests the service drops
connections and returns its own gateway errors, so higher settings measure faster only because a
refused connection returns instantly. **The operating point is 8 workers.**

**Timeout, measured rather than assumed.** The service kills a heavily archived domain's query at a
consistent ~60.7 s. A shorter client timeout is a false economy: at 30 s a run answered 51 of 100
domains, at 180 s it answered 82 of the same 100, because roughly a third reply between 30 s and
60 s. The client timeout is therefore 70 s, just above the service's own limit.

**Errors and how they were handled.** Requests are paced by an adaptive governor: on 429, 503 or 504
the delay grows by 1.5x while honouring `Retry-After`, and after five consecutive successes it eases
back by 0.8x, with a 50 ms floor and a 5 s ceiling. **A failure is never recorded as an absence.**
Failures are counted per status code and a domain is settled only by a real answer, so an outage
costs time rather than data. This mattered: after several hours of sustained querying the service
began refusing connections outright, while other services stayed reachable from the same machine.
Nothing was corrupted, every refused domain stayed eligible, and the supervisor gained a
reachability probe so it holds work back rather than queuing it against a service that has stopped
answering. When the service returned it was slower, so concurrency was re-measured rather than
assumed: 185 answered/hour at 4 workers, 383 at 8, 262 at 12. Throughput roughly halved and the
optimum stayed at 8.

**Yield.** The engine answered 4,956 domains for **11,932 net-new pairs**, about 1.15 pairs per
answered domain, against a bracketed target pool of ~470,000 domains that remains available.

**Page expansion.** Four rounds of the discovery cycle were run: fetch archived directory pages,
extract the domains they list, then either date those domains from the page's capture or route them
to the candidate pool. Round 1, over directory home pages, returned 92 domains and zero new
candidates, because home pages link to their own categories and to sites the baseline already holds.
Rounds 2 to 4 targeted curated subject catalogues one level in and returned **1,577 net-new pairs**,
concentrated in 1998 and 1999. A page's capture date is used as evidence for the domains it lists
only where the page documents itself as an editorially curated catalogue, and names attested by no
other source are routed to the candidate pool instead, because archived HTML carries transcription
typos and a listing is ultimately a claim made by the linking page.

**The cycle was closed, not merely described.** 298 domains discovered by expansion and by listing
scans were queried against the archive: 233 answered, and **198 of those (85%) held an in-window
capture**, producing +278 pairs. That rate is precisely why discovered names are treated as leads
rather than as evidence.

## 8. Limitations

- **Geographic skew.** Additions over-represent `.fr`, `.pt` and `.uk` relative to a global
  population, because the baseline already holds what a global crawl caught, so the complementary
  gains are national.
- **`.fr` coverage undercounts.** The registry file holds every `.fr` name live at the file date plus
  every name deleted since 28 January 2014, so `.fr` domains deleted before that date are absent.
  Combined with the creation-date reset described in section 5, the `.fr` yield cannot overcount.
- **Year coverage is uneven.** 1997 is lifted by a DNS survey that filled a real gap in the supplied
  data. 1998 and 1999 were thin and were materially improved. 2000 is only partly served: the
  surviving August 2000 directory dump is a truncated prefix and the full dump is unrecoverable.
- **Negative results differ in strength.** An empty archive index is a stronger negative than absence
  from a survey or a directory, which means only "not in that artifact".
- **One legacy tranche has weaker provenance.** 3,106 pairs under the source name `rdap` were written
  directly from live queries before the journal architecture existed, so they have no hashed source
  file. They were deliberately not re-queried, because a re-query today returns different creation
  dates for any domain that has since changed hands, which would silently alter the result set rather
  than reproduce it. Everything collected since replays from stored responses.
- **The candidate pool is not exhausted.** 5,583 domains await year-specific evidence, and the
  bracketed verification pool holds ~470,000 unqueried domains.

## 9. Whether further expansion is worthwhile

| Route | Verdict | Basis |
|---|---|---|
| Archive gap-filling | **Continue; the only route that scales with time alone** | 1.15 net-new pairs per answered domain at a measured 380-1,000 answered/hour, against ~470,000 unqueried domains. Yield is bounded by hours spent, not by the source |
| Registry creation dates | Continue only while it costs nothing | 0.15 pairs per domain against 1.15. Structural: a capture answers any year, a creation date answers one. Worth running only because it uses a different service |
| Curated page expansion | Continue, selectively | Home pages returned nothing; curated subject catalogues returned pairs. Worth continuing only into leaf catalogue pages that document themselves as curated |
| DNS surveys, national registry, national archives, early-web index | Exhausted | Each is a complete dataset, fully ingested; no further in-window files exist |
| Directory dumps | Exhausted for the window | The one recoverable in-window dump is ingested; the others were never published or do not survive |
| Commercial WHOIS history, zone files, further national archives | Closed | Priced, gated or non-existent for 1996-2001; each check is recorded in [sources.md](sources.md) |

Everything that can be exhausted from a file has been. What remains is query-bound rather than
source-bound, and archive gap-filling is the direction that converts hours into pairs at a stable,
measured rate.

## 10. How to reproduce

With only [`uv`](https://docs.astral.sh/uv/) installed, and **with no network access**:

```
uv sync
just reproduce     # rebuild the result from the shipped data
just check         # lint, format-check and tests, then the nine data invariants
```

`README.md` in the code snapshot gives the same run as numbered steps, each with the output it should
print, so a mismatch is visible at the step that caused it. The archive's own `README.md` describes
what each folder holds and gives three levels of checking, from verifying the shipped result offline
in minutes up to rebuilding everything from the original sources.

The rebuild needs no network because the collectors are not re-run. Every archive, registry and page
query was written to a journal holding the raw responses, and those journals ship, so the result is
derived from bytes rather than from services that answer differently today. Re-running any step is a
no-op on work already done, and every ingested file is hashed into a ledger, so a file whose contents
changed is refused rather than silently loaded.

The provenance export in `provenance/` carries the full evidence graph as Parquet, so any single
(domain, year) line can be traced to the observations behind it without the source data or a copy of
the database.
