# Decision log - lightweight ADR

Short notes on why I made certain architectural design choices. Details belong in the report.

## 2026-07-21

- **uv** for Python, deps, environments
  - one tool, and `uv.lock` makes a fresh clone reproduce the exact environment
- **just** as command runner
  - familiar from work, self-documenting shortcuts; raw `uv run` stays the documented fallback
- **CI on GitHub Actions** (lint, format check, tests on every push)
  - familiar from work and cheap insurance that a clean machine still builds
  - unit tests only, network mocked: keeps CI fast and deterministic
- **Large data stays out of git**
  - legacy baseline (~1.2 GB) and intermediates are ignored; only net-new output + evidence manifest get committed
- **Baseline never modified, output is disjoint net-new**
  - legacy files load read-only for dedup; our additions ship separately so the group can verify before merging
- **DuckDB + SQLite**, one per workload
  - DuckDB: system of record + analytics (dedup, yield stats, exports)
  - SQLite (WAL): crawler work-queue, many tiny commits for crash-resume; stdlib, zero extra deps
    - `claim` is a single SQL statement, which is what makes double-claiming impossible without any locking code in future parallelization.
- **PSL (Public Suffix List) snapshot pinned in the repo** (for `tldextract`)
  - the registrable domain is our output unit; live-fetching the suffix list would make it depend on download day
- **PSL** used to canonicalize how domains are converted into registerables as per III.8
- **Evidence rule enforced by the schema**
  - `domain_year.evidence_id` is NOT NULL, so an unevidenced year assignment is impossible; tested
  - all writes go through helpers; `assign_year` takes only an evidence id and derives domain + year from that row, so a mismatched assignment cannot be expressed
    - **a piece of evidence valid for multiple years is regarded as different pieces of evidence**
- **Baseline unit is the registered domain (III.8)**
  - the legacy files contain hostnames (1.4M lines with subdomains like `001sun01.marshall.com`); we collapse to registered domains, so counts differ from the prior line counts (8.2M lines -> 6.87M domain-year pairs); documented, files untouched
- **2026 PSL + historical ccTLD patch, not a "2001 PSL"**
  - no authoritative 2001 list exists (the PSL started ~2007) and early lists were less complete; we pin today's PSL and add retired ccTLDs (`.yu`, `.an`, ...) as extra suffixes, recovering ~1.8k real early-web domains
- **Underscores tolerated in discarded subdomains only**
  - `a_ashe.howard.edu` -> `howard.edu` is recovered; an underscore in the registered label itself stays invalid
- **Full droplist is a committed deliverable**
  - `output/legacy_review/dropped_domains.txt`: every provided line we exclude (0.149%), grouped by reason, reproducible via `ark legacy-review`

## 2026-07-22

- **Optimization target: net-new volume** (Prof. Ding: "let's use the results to tell")
  - the scored metric is the count of non-overlapping, evidence-backed domains vs the provided baseline; source order now follows expected yield
  - validity and evidence rules stay unchanged: every counted domain remains deduplicated, evidence-backed, and valid

- **Prior URL seed files are near-exhausted for new domains**
  - probing 200k lines of `deduplicated_urls_2001-2002` yielded 3 domains not already in the baseline; the prior work evidently mined these files
  - consequence: bulk archive indexes (Arquivo.pt, UK Web Archive) move up the source order; seed files stay as a low-priority back-verification pool
- **Stray separator punctuation around a name is salvaged** (`.www.foo.com` -> `foo.com`)
  - only characters that cannot belong to any label (dots, commas); a leading hyphen would alter the name itself and stays invalid
  - recovered just 11 baseline lines; kept because the upcoming URL seed files are far messier
- **Percent-encoding is decoded, not stripped** (`%20foo.ab.ca` -> `foo.ab.ca`)
  - decoded characters either belong to the hostname or cause rejection; non-ascii results stay rejected, which matches the era (IDN only exists since 2003)

- **What "unverified" means (evidence standard for negatives)**
  - a candidate stays unverified only after deterministic empty answers from the index for all six year windows; transport errors are retried, empty answers are not
  - the first three unverified domains were re-probed without the status-200 filter: still zero captures, so IA genuinely never archived them in-window
  - absence in one archive is not proof of non-existence: WHOIS and other archives remain open routes, hence candidate pool, not rejection
- **Verification queries match `*.domain`** (domain plus all subdomains)
  - a 1998 capture of `shop.foo.com` proves `foo.com` existed in 1998; the earlier prefix form missed subdomain-only captures
- **Delivery spec adopted (Prof. Ding, feedback #2)**
  - approach confirmed: registered-domain unit, untouched originals, separate additions, conservative salvage
  - added obligations: normalization/salvage audit file, execution logs kept from every run, merged master lists + full archive (with checksum) at delivery
  - merged master lists (~180MB) ship in the archive, not in git; net-new additions stay committed in `output/`

- **UKWA bulk CDX (JISC 1996-2013) is not publicly retrievable in 2026 (finding)**
  - `data.webarchive.org.uk` is a stale DNS alias to a retired GitHub Pages domain; the successor path on `www.webarchive.org.uk` soft-404s even the correct filenames (`1996.cdx.gz` ... `2013.cdx.gz`, recovered from a 2015 Wayback snapshot of the directory listing)
  - the BL research repository record (`bl.iro.bl.uk`, dataset `3c39a755-...`) is metadata-only and its download link points back to the dead host; the dataset DOI 404s; Wayback never archived the files; no archive.org mirror; GLAM Workbench cites the dead DOI
  - path forward: request access from the British Library (`web-archivist@bl.uk`); Arquivo.pt promoted to bulk wave 1 meanwhile
  - report material: link rot took the SPEC's own primary source offline within ~15 years, which is itself the strongest argument for this project's premise
  - 2026-07-22: access request sent via the BL repository contact form (bl.iro.bl.uk/contact), citing the record and the broken link; treated as fire-and-forget, not a blocker

- **Arquivo.pt bulk CDXJ has no 1996-2001 coverage (finding, corrected same day, see below)**
  - 214 collection files (18-374 GB each, multi-TB total), named by collection not year
  - sampled AWP1 (the earliest-numbered collection): 40 MB slice = 227k captures, all timestamped 2008, none in our window
  - Arquivo's crawls begin 2008 (like Common Crawl); its bulk dumps are out-of-window and too large to mine for a sliver → not a source for 1996-2001
- **Reality check on bulk sources for 1996-2001 (strategic)**
  - of the SPEC's named bulk index sources, Arquivo = 2008+, UKWA = link-rotted (access requested), Common Crawl = 2008+
  - the Internet Archive (Wayback) is effectively the one archive with broad 1996-2001 coverage, and it is primarily per-domain via the CDX API, not a bulk download
  - consequence: the volume engine shifts from "download-and-parse bulk indexes" to (a) dated directory/portal snapshots where the snapshot date evidences every listed domain (no per-domain calls), and (b) a large candidate pool (DMOZ, seed files) verified against IA CDX at scale, which makes async throughput necessary rather than optional

### Survey of bulk domain sources for 1996-2001 (2026-07-22)

One-day investigation across six parallel research tracks. Goal: find sources of 1996-2001 domains that are bulkier than querying the Internet Archive (IA) one domain at a time. Every claim below was verified against the live source on 2026-07-22, by HTTP HEAD requests, byte-range samples of the actual files, or full small downloads, never from documentation alone.

Terms: CDX is the standard plain-text index format of web archives, one line per archived capture, carrying the URL, a 14-digit timestamp (YYYYMMDDhhmmss), and the HTTP status; CDXJ is its JSON-per-line variant. One capture line is exactly our unit of evidence: it proves the domain served content on that date.

**Correction of the earlier Arquivo.pt verdict**

- the earlier recon sampled only the AWP* files (Arquivo.pt's own crawls, which start in 2008) out of a 214-file directory; the collection list behind arquivo.pt/collections identifies two in-window collections in the same directory, https://arquivo.pt/datasets/cdxj/
  - `Roteiro.cdxj` (13.6 MB): a 1996 crawl of the Portuguese web, ~75,000 pages, all timestamps 1996
  - `IA.cdxj` (50.9 GB): the Internet Archive's donated collection of the Portuguese web 1996-2007, ~124M captures; byte-range samples at several file offsets show 5-20% of lines with pre-2002 timestamps, so roughly 7-25M in-window captures
- yield is bounded by the Portuguese web of the era (order 10^4 registered domains), but every line carries a full capture timestamp, so it meets our evidence bar
- lesson for the report: sampling one file of a multi-file dataset is not an evaluation; read the collection metadata first

**Tier 1: free, verified, downloadable today (adopted as the Phase 2 ingestion order, see the re-plan decision below)**

1. IA "Early Web" language-annotation dataset, 1996-1999
   - https://archive.org/details/early-web_cdx-lang-cdxa (part of IA's 2021 "Early Web Datasets" researcher release, collection `earlywebdatasets`)
   - 224 CDX files, ~290 MB total, ~4.6M captures covering 4M+ websites, timestamps 1996-1999 only
   - verified by downloading one file: standard CDX rows with HTTP status 200; this is our exact evidence format and covers our sparsest years
   - estimated yield: 10^5 to 10^6 registered domains
2. Stanford WebBase 2001 URL list, distributed by LAW (Laboratory for Web Algorithmics, University of Milan)
   - http://data.law.di.unimi.it/webdata/webbase-2001/webbase-2001.urls.gz (720,229,219 bytes; dataset page https://law.di.unimi.it/webdata/webbase-2001/)
   - 118,142,155 full URLs in the clear, one per line, from the 2001 crawl of Stanford's WebBase project; free, no registration (verified by decompressing a 64 KB range sample)
   - provenance: the LAW page states the dataset was built from the 2001 WebBase crawl (also documented in Boldi and Vigna, WWW 2004); Stanford's own download service no longer resolves, so this is the surviving public artifact
   - evidences year 2001 only; estimated yield 0.5-2M registered domains (the sample shows ~21 URLs per host)
   - disposition per the re-plan decision below: candidate seeds first (the brief's III.4 names StanfordWebBase), masters only via per-domain verification
3. JISC UK Web Domain Dataset, host link graph 1996-2010, by UKWA (UK Web Archive, British Library)
   - all original download hosts are dead, but the complete file survives as a Wayback capture of the old URL: http://web.archive.org/web/20200106181208id_/https://www.webarchive.org.uk/datasets/ukwa.ds.2/linkage/host-linkage.tsv.gz (2,148,135,247 bytes; verified: a byte-range sample gunzips cleanly)
   - format: `year|source_host|target_host<TAB>count`, hostnames in the clear; built from ~2.5 billion HTTP-200 captures in IA's .uk holdings; license CC Public Domain Mark 1.0, DOI 10.5259/ukwa.ds.2/host.linkage/1
   - distinct links per year: 184k (1996), 1.6M (1997), 2.1M (1998), 3.6M (1999), 4.3M (2000), 10.9M (2001); source hosts are .uk-biased, target hosts are worldwide
   - evidence note: a source host was crawled in year Y (strong); a target host was only linked to in year Y (weaker, needs its own evidence-type label)
4. Internet Domain Survey domain lists 1995-1997 (Network Wizards / Mark Lottor, later hosted by ISC, the Internet Systems Consortium)
   - a twice-yearly walk of the entire DNS; each `.domains` file lists every domain name observed with at least one host, one per line
   - intact copies survive only in a Nov 1996 Wayback crawl of nw.com and on the author's live site (all verified today; line counts match the published survey reports):
     - Jul 1995: http://web.archive.org/web/19961112163532id_/http://nw.com:80/zone/9507.domains.gz (120,202 domains)
     - Jan 1996: http://web.archive.org/web/19961112163635id_/http://nw.com:80/zone/9601.domains.gz (240,482)
     - Jul 1996: http://web.archive.org/web/19961112163826id_/http://nw.com:80/zone/9607.domains.gz (488,069)
     - Jul 1997: http://3waylabs.com/zone/9707.domains.gz (1,301,470)
   - bit-rot finding: every copy on ISC's own server (https://ftp.isc.org/www/survey/archive-data/) fails the gzip integrity check, and Wayback copies of ISC's server were already corrupt in 2003; the Jan 1997 file is corrupt in every known copy and effectively lost
   - evidence caveat: "seen in DNS with at least one host on the survey date" is narrower than the registry zone (Jul 1997: survey saw 749k .com against ~1.3M registered); arguably stronger evidence of a live domain than mere registration, but it is a new evidence type and must be documented as such
5. Arquivo.pt in-window collections (see correction above): `Roteiro.cdxj` now; `IA.cdxj` only if 51 GB of download is judged worth roughly 10^4 domains

**Tier 2: request-only routes (cheap to send, weeks to answer, potentially decisive)**

- the Internet Archive holds the only broad 1996-2001 index; TLD-scale queries against its public CDX API return HTTP 403 "requires authorization", but an authorization mechanism exists (`cdx-auth-token`, documented in the CDX server docs) and there is precedent: IA staff provided a sampled full-index extract to outside researchers for a 2025 paper (arXiv 2507.14752, IA staff as co-authors). The ask: a 1996-2001 CDX extract, small by their standards
- ARCH (Archives Research Compute Hub, https://arch.archive-it.org), IA's researcher service, builds domain-frequency and domain-graph derivatives from restricted collections "by arrangement with IA staff"; this is the sanctioned route to the two large restricted troves (restriction verified: file URLs answer 401/403):
  - Alexa crawls 1996-2007 (collection `alexacrawls`, 226,901 items; the crawl data behind early Wayback, with per-item CDX files)
  - the Wayback CDX shards (collection `waybackcdx`, the full index, ~12 TB, "not publicly downloadable" per its own description)
- already sent: British Library request for the UKWA per-year CDX files (1996.cdx.gz 52 MB through 2001.cdx.gz 6.5 GB; confirmed dead publicly, the file bytes were never Wayback-captured)
- 1998-2001 zone files: no public copies survive anywhere (checked DNS-OARC, commercial resellers, academic torrents); recovery would need direct asks (Verisign research access, ISC via survey@isc.org, Matthew Zook of zooknic.com who used them in published research, RIPE NCC for European country-code TLD raw data)

**Tier 3: small but highly defensible supplements**

- ODP (Open Directory Project, also known as DMOZ) published weekly full data dumps; Wayback captured some from inside our window:
  - Aug 2000 full dump, truncated: https://web.archive.org/web/20000815053618id_/http://dmoz.org/rdf/content.rdf.u8.gz ; the 2000-era crawler cut downloads at ~1 MB, so 1,048,293 of 122,809,149 bytes survive; the prefix decompresses cleanly to 19,086 URLs across 13,275 distinct hosts
  - "Kids and Teens" branch dumps, complete: https://web.archive.org/web/20010611215006id_/http://dmoz.org/rdf/kt-content.rdf.u8.gz (6,348 hosts) and https://web.archive.org/web/20011116104011id_/http://dmoz.org/rdf/kt-content.rdf.u8.gz (8,453 hosts)
  - dating is triple-sourced: the Wayback capture timestamp, the preserved origin Last-Modified header, and a generation timestamp inside the file; no complete 1999-2001 full dump survives anywhere we could find
- NCSA Mosaic "What's New" page for January 1996 (captured Dec 1996): ~1,300 hosts, double-dated (entries dated in-month, page captured in-year); our only 1996 directory artifact
- 100hot.com weekly top-100 category lists (heavily captured 1996-2001) and the WWW Virtual Library (captured Oct 1996): order 10^3 domains each, capture-dated

**Confirmed dead ends (verified negatives, kept for the report)**

- Common Crawl: earliest collection is CC-MAIN-2008-2009, starting 2008-05-09 (from its own index list, https://index.commoncrawl.org/collinfo.json); pre-2008 page content inside it fails our evidence bar because the capture timestamp is 2008+
- "Wayback bulk extractor" tools (Apify actor, cdx-tools, cdx_toolkit): all wrap the same rate-limited public API; none bypasses the 403
- SNAP web graphs (Stanford): nodes are anonymized integers, no URL mapping is distributed
- Yahoo! Webscope AltaVista graph ("circa 2002"): program unreachable in 2026, license forbade redistribution, crawl date too vague for per-year evidence
- TREC WT10g / VLC2 (subsets of a 1997 IA crawl): paid, small in domain terms, distributor (University of Glasgow) unreachable
- Yahoo! Directory: no machine-readable dump was ever published; scraping dated Wayback snapshots of category pages remains the only route
- GeoCities derivative datasets (crawl dates ~2009), DNS Census (2013), Stanford WebBase direct downloads (service dead): all out of window or gone

**Preservation and method notes**

- rescued files are in `data/raw/isc_survey/` (the four intact survey lists plus the Jul 1996 per-TLD .org host list) and `data/raw/odp/` (the three surviving dumps), with SHA-256 checksums in `data/raw/checksums.sha256`; large data stays out of git as usual
- IA CDX API, measured: `collapse=timestamp:4` returns one capture per year per domain in a single request (6x fewer calls than our current per-year loop); observed throttling suggests ~60 requests per minute per IP is the polite ceiling
  - caveat: measured on single-URL queries; the server collapses only adjacent rows sorted by URL key, so domain-wide (`matchType=domain`) queries return one row per year per URL key and years must be deduplicated client-side
- a Wayback capture's completeness can be checked by comparing its CDX `length` field against the preserved `x-archive-orig-content-length` response header; this is how the truncated ODP dump was diagnosed

- **Re-plan around the survey (tbd)**
  - the plan is re-sequenced around Tier 1 above; request-gated datasets (Tier 2) are excluded from architectural decisions: we assume no reply within the project window and treat any reply as a bonus
  - per-domain verification is re-scoped to one collapsed CDX query per domain (`collapse=timestamp:4`), spent first on a year-2000 gap-fill (the thinnest year after Tier 1) and on reliability sampling of weaker evidence types
  - one shared bulk ingester with small per-source parsers replaces per-source loaders, so droplist/audit parity and run metrics are structural
  - III.4/§VII routing (the brief decides, not us): StanfordWebBase is named in III.4, so webbase-2001 enters as candidate seeds, and link-discovered hosts (UKWA link targets) take the same route; annual masters gain domains only via per-domain year verification
  - `link_source` rows (host crawled with HTTP 200 in year Y) remain direct evidence: the brief itself lists "UK Web Archive host/link graphs" among its historical web-archive index sources (§V)
  - dated index files (ISC survey lists, ODP dumps) are used as direct evidence under §VII's "dated index files" time-evidence class; flagged for Prof. Ding's confirmation in the interim email
  - score consequence: candidates never count until verified, and at the ~60 requests/min ceiling (~86k domains/day) the webbase pool cannot be fully verified in-window; verification is priority-ordered (year-2000 gap-fill first, then sample-guided candidate batches)
  - DMOZ 2017 dump stays in scope as candidate-pool growth only (§IX: the pool "should be expanded proactively and made as large as practicable")
  - before adoption, the re-planned docs were adversarially reviewed against the brief (three independent review passes: spec coverage, consistency, feasibility); the review caught that the first draft routed webbase-2001 directly into masters, which III.4 forbids, and the plan was corrected to candidate-first

## 2026-07-23

- **Shared bulk ingester built (Phase 2), adversarially reviewed before first use**
  - one loader, small per-source parsers, one CLI entry: `ark ingest <source> <files...>`; per-file ledger keyed on (source, file name) with the sha256 compared on every hit, so same name + same bytes skips and different bytes fails loudly instead of silently dropping data
  - audit CSV per source in the `ark audit` format: every dropped line, corrections sampled at 100 per reason per file, exact totals in run_metrics; audit rows reach the CSV only after the file's transaction commits
  - a failing file is logged and skipped, the rest of the run continues; candidate queueing derives from durable evidence rows, so re-running the command repairs any crash window
  - the evidence CHECK constraint was migrated to the signed-off taxonomy (transactional rebuild + refill; store backed up first as `data/ark.duckdb.bak-pre-taxonomy`); `assign_year` now refuses candidate-only evidence outright, closing the one unguarded path into `domain_year`
  - validation: 87 tests green; 3 independent adversarial review passes (data integrity, taxonomy compliance, scale) ran before the code touched real data, and every finding was fixed the same night

- **Early Web CDX ingested: near-total baseline overlap (finding)**
  - 224 files, 4.38M lines, 2.16M distinct domains, 2,278,722 (domain, year) pairs with capture timestamps; runtime 2:00 min end to end
  - 99.992% of those pairs were already in the baseline: net-new = 175 domains / 182 pairs
  - conclusion: the baseline was evidently mined from the IA Wayback index for 1996-1999, so IA-derived bulk sources corroborate the baseline rather than grow it
  - the corroboration is itself a deliverable: 2.28M baseline pairs now carry independent capture-level evidence with a Wayback URL each (previously `prior_reused` only), which is the cross-validation obligation arriving early and at scale
  - strategy consequence: net-new volume must come from non-IA-derived sources; next in line are the ISC survey lists (DNS-observed, independent of web archives; the Jul 1997 list holds 1.3M domains against 220k in the 1997 baseline) and webbase-2001 (an independent Stanford crawl)

- **All 175 net-new domains are www-label registrations (finding)**
  - every single one is the label `www` registered directly under a public suffix (`www.cl`, `www.com.pk`, `www.mil.lv`); these are real registrable domains per the PSL, with live captures (5 of 5 spot-checked against web.archive.org, all resolving)
  - likely dropped by the prior work's normalization: stripping `www.` unconditionally turns `www.cl` into the bare suffix `cl`, which is then rejected and the domain disappears; our canonicalizer splits against the PSL first, so the registration survives
  - kept: they satisfy every signed-off validity and evidence rule; flagged as a class in the report

- **Audit policy for bulk sources (decision)**
  - every dropped line is written to the per-source audit CSV (completeness for the audit deliverable; early_web produced 1.22M drops, mostly era-typical bare-IP captures, a 131 MB CSV), corrections are sampled with exact totals in run_metrics
  - "earliest in-year capture" holds within one file; across files of one source the first-ingested file wins (documented; immaterial to the evidence bar, any in-year capture suffices)

## Definition: what we count as a valid domain

Implemented in [`src/ark/canonical.py`](../src/ark/canonical.py) (`to_registrable`); every domain from every source passes through it before touching the database. A line counts as a valid domain if, after the steps below, a registered domain remains:

1. **Normalize.** Percent-decode, trim whitespace, lowercase. Strip URL parts if present: scheme (`http://`), path/query/fragment, userinfo (`user@`), port (`:80`), plus stray separator punctuation around the name (leading/trailing dots and commas).
2. **Require hostname syntax.** Labels of letters, digits, hyphens (no hyphen at a label edge). Underscores are tolerated, but only in subdomain labels that get discarded anyway. IP addresses are not domains.
3. **Split against the Public Suffix List** (pinned snapshot of 2026-07-20, plus a documented patch of retired ccTLDs like `.yu`, `.an`). The result must have both a registered label and a public suffix. This rejects bare suffixes (`ab.ca` is a registry zone, not a registration) and suffix-less names (`localhost`).
4. **Keep only the registered domain** (registered label + suffix, e.g. `bbc.co.uk`), discarding subdomains (`www.`, machine names) per SPEC III.8.

Everything else is dropped with a stated reason; the droplist above holds every dropped baseline line for inspection.

## Definition: evidence types (what each proves, and where it can go)

Signed off 2026-07-23 before any ingester code. Every evidence row carries an `evidence_type`; the type fixes both the standard of proof and the disposition (whether the row may back an annual-master `(domain, year)` assignment, or only mark a candidate). Terms are defined in the survey section above (CDX, ODP/DMOZ, UKWA, ISC, IA, WHOIS). "Master-eligible" means a row of this type may create a `domain_year` row; "candidate-only" means it may not, ever.

Two structural rules hold across all types:

- **The scored metric** counts a net-new domain only when it has at least one master-eligible row from a non-`prior_reused` type. Candidates never count until verified.
- **Candidate-only evidence never assigns a year.** The row is still stored (for provenance and to prioritize verification), but it cannot reach an annual file except by first earning a master-eligible row (in practice a `cdx_timestamp`).

| Type | What one row asserts | What a negative means | Disposition |
|---|---|---|---|
| `prior_reused` | The provided baseline already lists this (domain, year); reused read-only per III.1 | n/a (we never generate baseline negatives) | Master; **excluded from the scored metric** (it is the baseline, not net-new) |
| `cdx_timestamp` | An IA CDX capture with an in-year 14-digit timestamp and HTTP 200 for the domain or a subdomain (`*.domain`) proves it served content that year | Deterministic empty CDX answers for all six year windows: IA never archived it in-window (not proof of non-existence, so it stays a candidate) | Master; the gold standard every candidate is verified against |
| `artifact_listing` | The domain is a line in a **dated data file** whose own provenance fixes the year (ISC survey list = survey date; ODP RDF dump = generation stamp) | Absence from a given dated file means only "not in that file", weaker than a CDX negative | Master (direct, §VII "dated index files"); ISC/ODP semantics flagged for Ding's confirmation in the interim email |
| `link_source` | From a UKWA host link-graph row `year\|source\|target`, the **source** host was crawled (HTTP 200) that year to produce the link | n/a per-domain (the graph is precomputed, not queried) | Master (brief lists UKWA host/link graphs among its index sources, §V) |
| `link_target` | From the same row, the **target** host was merely linked-to; this does **not** prove it existed or was active (dead links, typos, later registration are common) | n/a | **Candidate-only**; reaches masters only after per-domain verification (§IV/§VII route link-discovered hosts to the validation queue) |
| `dated_directory` | The domain is an editorial **entry** on a directory / yellow-page / portal page captured by a web archive on a known date | Absence from a page means only "not listed there", weak | Master (direct; brief blesses this route without further CDX validation, §IV/§VII) |
| `whois_creation` *(reserved)* | A WHOIS/RDAP creation date establishes existence no later than that date, supporting the **creation year only** (III.6); later years need their own evidence, never forward-filled | A missing/blocked WHOIS record is not evidence of anything | Master for the creation year only; activated only if the Phase 5 WHOIS spike runs |

Gray zone recorded for the ingester: on a `dated_directory` page, only curated **entries** count as `dated_directory`; incidental outbound links from the same page (nav bars, ads, reciprocal-link footers) are `link_target`-grade candidates. Drawing that line lives in the per-source parser.

