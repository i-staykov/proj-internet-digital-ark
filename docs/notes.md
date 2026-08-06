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
  - superseded 2026-07-23: `output/` is now git-ignored too (it grew to ~96 MB once real sources landed); see the 2026-07-23 policy entry
- **Baseline never modified, output is disjoint net-new**
  - legacy files load read-only for dedup; the additions ship separately so the group can verify before merging
- **DuckDB + SQLite**, one per workload
  - DuckDB: system of record + analytics (dedup, yield stats, exports)
  - SQLite (WAL): crawler work-queue, many tiny commits for crash-resume; stdlib, zero extra deps
    - `claim` is a single SQL statement, which is what makes double-claiming impossible without any locking code in future parallelization.
- **PSL (Public Suffix List) snapshot pinned in the repo** (for `tldextract`)
  - the registrable domain is the output unit; live-fetching the suffix list would make it depend on download day
- **PSL** used to canonicalize how domains are converted into registerables as per III.8
- **Evidence rule enforced by the schema**
  - `domain_year.evidence_id` is NOT NULL, so an unevidenced year assignment is impossible; tested
  - all writes go through helpers; `assign_year` takes only an evidence id and derives domain + year from that row, so a mismatched assignment cannot be expressed
    - **a piece of evidence valid for multiple years is regarded as different pieces of evidence**
- **Baseline unit is the registered domain (III.8)**
  - the legacy files contain hostnames (1.4M lines with subdomains like `001sun01.marshall.com`); the pipeline collapses to registered domains, so counts differ from the prior line counts (8.2M lines -> 6.87M domain-year pairs); documented, files untouched
- **2026 PSL + historical ccTLD patch, not a "2001 PSL"**
  - no authoritative 2001 list exists (the PSL started ~2007) and early lists were less complete; pin today's PSL and add retired ccTLDs (`.yu`, `.an`, ...) as extra suffixes, recovering ~1.8k real early-web domains
- **Underscores tolerated in discarded subdomains only**
  - `a_ashe.howard.edu` -> `howard.edu` is recovered; an underscore in the registered label itself stays invalid
- **Full droplist is a committed deliverable**
  - `output/legacy_review/dropped_domains.txt`: every provided line excluded (0.149%), grouped by reason, reproducible via `ark legacy-review`

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
  - sampled AWP1 (the earliest-numbered collection): 40 MB slice = 227k captures, all timestamped 2008, none in the window
  - Arquivo's crawls begin 2008 (like Common Crawl); its bulk dumps are out-of-window and too large to mine for a sliver → not a source for 1996-2001
- **Reality check on bulk sources for 1996-2001 (strategic)**
  - of the SPEC's named bulk index sources, Arquivo = 2008+, UKWA = link-rotted (access requested), Common Crawl = 2008+
  - the Internet Archive (Wayback) is effectively the one archive with broad 1996-2001 coverage, and it is primarily per-domain via the CDX API, not a bulk download
  - consequence: the volume engine shifts from "download-and-parse bulk indexes" to (a) dated directory/portal snapshots where the snapshot date evidences every listed domain (no per-domain calls), and (b) a large candidate pool (DMOZ, seed files) verified against IA CDX at scale, which makes async throughput necessary rather than optional

### Survey of bulk domain sources for 1996-2001 (2026-07-22)

One-day investigation across six parallel research tracks. Goal: find sources of 1996-2001 domains that are bulkier than querying the Internet Archive (IA) one domain at a time. Every claim below was verified against the live source on 2026-07-22, by HTTP HEAD requests, byte-range samples of the actual files, or full small downloads, never from documentation alone.

Terms: CDX is the standard plain-text index format of web archives, one line per archived capture, carrying the URL, a 14-digit timestamp (YYYYMMDDhhmmss), and the HTTP status; CDXJ is its JSON-per-line variant. One capture line is exactly the unit of evidence: it proves the domain served content on that date.

**Correction of the earlier Arquivo.pt verdict**

- the earlier recon sampled only the AWP* files (Arquivo.pt's own crawls, which start in 2008) out of a 214-file directory; the collection list behind arquivo.pt/collections identifies two in-window collections in the same directory, https://arquivo.pt/datasets/cdxj/
  - `Roteiro.cdxj` (13.6 MB): a 1996 crawl of the Portuguese web, ~75,000 pages, all timestamps 1996
  - `IA.cdxj` (50.9 GB): the Internet Archive's donated collection of the Portuguese web 1996-2007, ~124M captures; byte-range samples at several file offsets show 5-20% of lines with pre-2002 timestamps, so roughly 7-25M in-window captures
- yield is bounded by the Portuguese web of the era (order 10^4 registered domains), but every line carries a full capture timestamp, so it meets the evidence bar
- lesson for the report: sampling one file of a multi-file dataset is not an evaluation; read the collection metadata first

**Tier 1: free, verified, downloadable today (adopted as the Phase 2 ingestion order, see the re-plan decision below)**

1. IA "Early Web" language-annotation dataset, 1996-1999
   - https://archive.org/details/early-web_cdx-lang-cdxa (part of IA's 2021 "Early Web Datasets" researcher release, collection `earlywebdatasets`)
   - 224 CDX files, ~290 MB total, ~4.6M captures covering 4M+ websites, timestamps 1996-1999 only
   - verified by downloading one file: standard CDX rows with HTTP status 200; this is the exact evidence format needed and covers the sparsest years
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
  - why nothing after Jul 1997 (verified): the survey did not stop (ISC's reports run 1998 through 2007+), but the raw `.domains` name lists end at 9707; later editions publish only aggregate counts, not enumerated names. This coincides with the mid-1997 end of bulk public DNS names generally (NSI/InterNIC ended anonymous .com/.net/.org zone-file FTP around July 1997 over spam-harvesting abuse). So DNS-derived NAME evidence is a 1996-1997 window only; 1998-2001 must come from archive captures + CDX. This is a report limitation and explains the 1996-97 richness vs 1998-2001 sparsity in DNS data.
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

- ODP (Open Directory Project, also known as DMOZ) published weekly full data dumps; Wayback captured some from inside the window:
  - Aug 2000 full dump, truncated: https://web.archive.org/web/20000815053618id_/http://dmoz.org/rdf/content.rdf.u8.gz ; the 2000-era crawler cut downloads at ~1 MB, so 1,048,293 of 122,809,149 bytes survive; the prefix decompresses cleanly to 19,086 URLs across 13,275 distinct hosts
  - "Kids and Teens" branch dumps, complete: https://web.archive.org/web/20010611215006id_/http://dmoz.org/rdf/kt-content.rdf.u8.gz (6,348 hosts) and https://web.archive.org/web/20011116104011id_/http://dmoz.org/rdf/kt-content.rdf.u8.gz (8,453 hosts)
  - dating is triple-sourced: the Wayback capture timestamp, the preserved origin Last-Modified header, and a generation timestamp inside the file; no complete 1999-2001 full dump survives anywhere findable
- NCSA Mosaic "What's New" page for January 1996 (captured Dec 1996): ~1,300 hosts, double-dated (entries dated in-month, page captured in-year); the only 1996 directory artifact
- 100hot.com weekly top-100 category lists (heavily captured 1996-2001) and the WWW Virtual Library (captured Oct 1996): order 10^3 domains each, capture-dated

**Confirmed dead ends (verified negatives, kept for the report)**

- Common Crawl: earliest collection is CC-MAIN-2008-2009, starting 2008-05-09 (from its own index list, https://index.commoncrawl.org/collinfo.json); pre-2008 page content inside it fails the evidence bar because the capture timestamp is 2008+
- "Wayback bulk extractor" tools (Apify actor, cdx-tools, cdx_toolkit): all wrap the same rate-limited public API; none bypasses the 403
- SNAP web graphs (Stanford): nodes are anonymized integers, no URL mapping is distributed
- Yahoo! Webscope AltaVista graph ("circa 2002"): program unreachable in 2026, license forbade redistribution, crawl date too vague for per-year evidence
- TREC WT10g / VLC2 (subsets of a 1997 IA crawl): paid, small in domain terms, distributor (University of Glasgow) unreachable
- Yahoo! Directory: no machine-readable dump was ever published; scraping dated Wayback snapshots of category pages remains the only route
- GeoCities derivative datasets (crawl dates ~2009), DNS Census (2013), Stanford WebBase direct downloads (service dead): all out of window or gone

**Preservation and method notes**

- rescued files are in `data/raw/isc_survey/` (the four intact survey lists plus the Jul 1996 per-TLD .org host list) and `data/raw/odp/` (the three surviving dumps), with SHA-256 checksums in `data/raw/checksums.sha256`; large data stays out of git as usual
- IA CDX API, measured: `collapse=timestamp:4` returns one capture per year per domain in a single request (6x fewer calls than the per-year loop); observed throttling suggests ~60 requests per minute per IP is the polite ceiling
  - caveat: measured on single-URL queries; the server collapses only adjacent rows sorted by URL key, so domain-wide (`matchType=domain`) queries return one row per year per URL key and years must be deduplicated client-side
- a Wayback capture's completeness can be checked by comparing its CDX `length` field against the preserved `x-archive-orig-content-length` response header; this is how the truncated ODP dump was diagnosed

- **Re-plan around the survey (tbd)**
  - the plan is re-sequenced around Tier 1 above; request-gated datasets (Tier 2) are excluded from architectural decisions: assume no reply within the project window and treat any reply as a bonus
  - per-domain verification is re-scoped to one collapsed CDX query per domain (`collapse=timestamp:4`), spent first on a year-2000 gap-fill (the thinnest year after Tier 1) and on reliability sampling of weaker evidence types
  - one shared bulk ingester with small per-source parsers replaces per-source loaders, so droplist/audit parity and run metrics are structural
  - III.4/§VII routing (the brief decides): StanfordWebBase is named in III.4, so webbase-2001 enters as candidate seeds, and link-discovered hosts (UKWA link targets) take the same route; annual masters gain domains only via per-domain year verification
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
    - the migration was a one-time upgrade of the single existing store; its code + test and the backup were removed once it succeeded (a fresh clone builds the taxonomy schema directly, so nothing needs upgrading)
  - validation: 87 tests green; 3 independent adversarial review passes (data integrity, taxonomy compliance, scale) ran before the code touched real data, and every finding was fixed the same night

- **Early Web CDX ingested: near-total baseline overlap (finding)**
  - 224 files, 4.38M lines, 2.16M distinct domains, 2,278,722 (domain, year) pairs with capture timestamps; runtime 2:00 min end to end
  - 99.992% of those pairs were already in the baseline: net-new = 175 domains / 182 pairs
  - conclusion: the baseline was evidently mined from the IA Wayback index for 1996-1999, so IA-derived bulk sources corroborate the baseline rather than grow it
  - the corroboration is itself a deliverable: 2.28M baseline pairs now carry a second capture-level source (a Wayback URL each), previously `prior_reused` only, which is the cross-validation obligation arriving early and at scale (honesty caveat below: both sources are IA-derived, so this is cross-source, not yet provenance-independent, corroboration)
  - strategy consequence: net-new volume must come from non-IA-derived sources; next in line are the ISC survey lists (DNS-observed, independent of web archives; the Jul 1997 list holds 1.3M domains against 220k in the 1997 baseline) and webbase-2001 (an independent Stanford crawl)

- **All 175 net-new domains are www-label registrations (finding)**
  - every single one is the label `www` registered directly under a public suffix (`www.cl`, `www.com.pk`, `www.mil.lv`); these are real registrable domains per the PSL, with live captures (5 of 5 spot-checked against web.archive.org, all resolving)
  - likely dropped by the prior work's normalization: stripping `www.` unconditionally turns `www.cl` into the bare suffix `cl`, which is then rejected and the domain disappears; the canonicalizer splits against the PSL first, so the registration survives
  - kept: they satisfy every signed-off validity and evidence rule; flagged as a class in the report

- **ISC survey ingested: the first large net-new tranche (finding)**
  - 5 files, 2.45M lines, ~15s; the Jul 1995 file was skipped whole (pre-window; ledger row with 0 records)
  - net-new jumped from 183 domains / 193 pairs to **397,151 domains / 1,132,322 pairs**, dominated by 1997 (1,035,854 net-new pairs)
  - why 1997 explodes: the Jul 1997 ISC survey lists 1.21M in-window domains against only 219,918 in the 1997 baseline (IA barely archived 1997), so ~1.03M are net-new; verified by sampling (e.g. `00.co.nz` carries only ISC 1997 evidence; `microsoft.com/1997` correctly stays non-net-new, backed by prior_reused + cdx + isc)
  - this is the point of a DNS-derived source: ISC is independent of the Internet Archive, so unlike Early Web it GROWS the baseline instead of only corroborating it
  - **the whole tranche rests on the `artifact_listing` evidence type** (domain observed in DNS with >=1 host on the survey date), which is flagged for Prof. Ding's confirmation. If he accepts DNS-survey presence as year evidence, net-new is 1.13M pairs; if not, ISC becomes candidate seeds. The interim email must ask this explicitly, because it is the difference between ~1.13M and ~193 net-new pairs.
  - first provenance-independent corroboration: ISC also supplies evidence for ~530k already-assigned pairs, so those baseline pairs are now confirmed by a genuinely non-IA source (the earlier Early Web corroboration was IA-on-IA)
  - the Jul 1996 `.org` host list (`wb_nw_9607_org`) added only 14 net-new pairs, near-redundant with the 9607 domains list (its .org domains were already there); kept and documented as low-yield
  - evidence caveat for the report: "seen in DNS with >=1 host on the survey date" is narrower than the full registry zone but arguably stronger than an archive capture as proof a domain existed; state the semantics plainly

- **Arquivo Roteiro.cdxj ingested: tiny net-new, as expected (finding)**
  - 44,379 captures (all 1996, all status 200) -> 3,442 unique registered domains (201 bare-IP captures dropped, ~44k host URLs collapsed to their registered domain)
  - only **7 net-new 1996 pairs, 0 net-new domains**: 1996 coverage is now dense (baseline + Early Web + ISC), and Roteiro's mostly-European academic hosts were already present
  - value is corroboration not growth: +3,442 `cdx_timestamp` evidence rows (an Arquivo capture per domain, source `arquivo_roteiro`), 98 pairs newly reaching 2+ sources; and it is a second web archive (non-IA) for those pairs
  - validates the reusable CDXJ parser; informs the (Opt) `IA.cdxj` decision: Arquivo collections overlap heavily with what is already held, so 51 GB of `IA.cdxj` is unlikely to be worth it unless a later gap analysis says otherwise

- **Arquivo `IA.cdxj` spike: GO, materially net-new in the thin years (finding; revises the Roteiro-based forecast directly above)**
  - method: 6 byte-range slices of 64 MB (402 MB total, 0.79% of the 50.93 GB file) spread evenly across the file; the server honors `Accept-Ranges`, and the file is SURT-sorted (TLD-then-host) so spread offsets sample different TLD/host bands rather than one alphabetical clump. Each slice parsed with the shipping `parse_arquivo_cdxj` + `to_registrable`, then classified read-only against the store (the store was ATTACHed READ_ONLY, so the spike could not mutate it)
  - in the sample: 168,409 in-window HTTP-200 captures -> 1,492 distinct registered domains, of which **177 (11.9%) are brand-new** (never in the `domain` table), 12 already net-new via another source, 1,303 baseline overlap
  - the brand-new domains land in exactly the thin years: 1998 (9), 1999 (19), 2000 (100), 2001 (91); their TLDs are .pt (96), .com (52), .br (24), i.e. Portuguese/Brazilian hosts the IA-global baseline missed. This is the UKWA `.uk` pattern repeating for the Lusophone web
  - this overturns the Roteiro forecast above: Roteiro was 1996-only (a year already dense), so its ~0 net-new did not predict IA.cdxj's 1998-2001 `.pt` yield. A curated national donation is complementary to the global crawl precisely where the global crawl is thin
  - linear rate-based extrapolation to the full file: **~22k net-new domains / ~105k net-new pairs**; treat as order 10^4, not precise (0.79% sample, `.pt` band density varies across the file). Comparable in absolute terms to UKWA's +15,822
  - evidence type is `cdx_timestamp` (a web-archive capture with in-year timestamp and status 200), III.1's least-controversial named evidence, so this tranche does NOT hinge on Prof. Ding's `artifact_listing` ruling; the parser already exists and is tested (Roteiro)
  - decision: **ingest**. Register source `arquivo_ia` (kind timestamped, `parse_arquivo_cdxj`); download the 51 GB once (resumable via byte-ranges, 740 GB disk free) -> ingest -> export -> stats -> yield entry. The cost is the ~10 h download (server ~1.5 MB/s), not code

- **Arquivo `IA.cdxj` ingested: +6,715 net-new domains, 98% `.pt`, concentrated in the thin years (finding). The spike's GO was right on direction, 3.3x high on magnitude**
  - the 50.93 GB file downloaded clean on a single 8.5 h connection (resumable loop, exact-size match, sha256 recorded in `data/raw/checksums.sha256`), then ingested in ~4.5 min: 140.8M lines -> 14.82M in-window HTTP-200 captures -> 14,188 distinct registered domains (122.2M lines out of window = the 2002-2007 bulk; 2.0M non-200; 1.8M malformed)
  - **yield: +6,715 net-new domains / +17,689 net-new pairs** (412,973 -> 419,688 domains; 1,156,150 -> 1,173,839 pairs); +28,247 `cdx_timestamp` evidence rows. The scoreboard delta equals the ingest's `year_rows` (17,689) exactly, so the numbers reconcile
  - **98.4% of the net-new domains are `.pt`** (6,896 of 7,005 net-new IA domains; then .com 58, .br 24): the Portuguese national web the IA-global baseline never indexed, exactly the geographic-complement thesis. Live-replay spot-checks of net-new captures return 200 (e.g. `arquivo.pt/wayback/.../100limite.pt`, `.../100mais.pt`)
  - **it fills the thinnest years**: new pairs by year 1998 +912, 1999 +2,667, 2000 +4,747, 2001 +9,323 (1996 +1, 1997 +39), i.e. **+89% on 1998, +165% on 1999, +183% on 2000, +50% on 2001** over the prior net-new pair counts. This is the strategic win: ISC stopped listing names after Jul 1997 and the baseline is thin post-1997, so a deep .pt crawl lands where coverage was weakest
  - corroboration: IA.cdxj also added a second capture to 7,183 already-baseline domains; the honesty caveat holds, IA.cdxj is IA-donated so this corroboration shares the baseline's IA lineage (cross-source, not provenance-independent). The net-new .pt domains are new facts regardless of lineage
  - **spike accuracy, recorded honestly for method:** the 0.79% byte-range spike predicted ~22k net-new domains; actual is 6,715, a 3.3x overshoot. Cause: distinct-domain count was extrapolated linearly by bytes, but distinct-domain density is highly non-uniform on a SURT-sorted file dominated by deeply-crawled .pt hosts (the full file averages ~1,044 in-window captures per domain vs 113 in the sampled slices, so most bytes are a few hosts repeated). The spike's qualitative calls (GO, thin-year concentration, .pt complement) all held; only the magnitude did not. Lesson for future spikes: extrapolate distinct-entity counts with a clustering caveat, not as if they scale with rows/bytes
  - the store was backed up before the write (`data/ark.duckdb.bak-pre-ia`) and the backup removed once the yield reconciled

- **UKWA host link graph ingested (link_source): complete for the window; recon size was overestimated (finding)**
  - download is unreliable: Wayback serves the ~2.0 GB gz stream but advertises a 20.9 GB Content-Length (the decompressed size), serves no byte-ranges (no resume), and drops the connection mid-transfer (curl exit 18). The local copy is a partial download.
  - it does not matter: the file is year-sorted ascending and 1996-2001 is its head, fully transferred before any truncation (verified: clean 2001->2002 transition at line ~166,890, and zero in-window rows in the next 5M lines). The parser breaks at the first post-2001 row, reading only the in-window head.
  - the recon's "184k-10.9M links/year" was wrong for THIS file: 1996-2001 is only **~166,890 rows** total; the 20.9 GB decompressed bulk is 2002-2010 (out of window)
  - yield: 32,865 unique (.uk-heavy) source domains, 39,454 `link_source` evidence rows, **+15,822 net-new domains / +23,821 net-new pairs**, concentrated in the thin later years ISC could not reach (1998 +944, 1999 +1,584, 2000 +2,595, 2001 +18,643)
  - reproducibility: the partial-file checksum is not reproducible (truncation point varies), but the 1996-2001 content is deterministic (always the fully-transferred head); documented for the report
  - consequence for Phase 3: `link_target` candidates are likewise bounded by ~167k rows, so a modest candidate pool

- **Net-new output moved out of git (policy change, Ivo approved)**
  - the committed deliverable premise ("net-new is small") no longer holds: after ISC, `output/` is ~96 MB (`evidence_manifest.csv` 80 MB, `1997.txt` 14 MB) and growing with every source, heading for GitHub's 100 MB limit
  - `output/` is now git-ignored and ships in the Phase 7 delivery archive, regenerable on any machine via `ark export` (same treatment the merged masters in `data/exports/` already get); the repo commits code + docs only
  - reproducibility is unaffected: the method is in git, the data regenerates from `ingest-legacy` + `ingest` + `export`

- **"net-new domains" vs "net-new pairs" are different metrics (verified, not a bug)**
  - net-new domains (397,151) = domains entirely absent from the baseline; net-new pairs (1,132,322) = new (domain, year) facts, which include new years for domains that ARE in the baseline for other years
  - 1997 shows the split most: of 1,035,854 net-new 1997 pairs, 651,214 are baseline domains getting their missing 1997 year (IA barely archived 1997), 384,640 are brand-new domains
  - no double-counting: `domain_year` PK is (domain, year), 1997 has 1,255,772 rows = 1,255,772 distinct domains; and non-baseline domains (397,154) == net-new domains (397,151) + unassigned candidates (3), exactly
  - open question for the report/Ding: is "the score" distinct net-new domains or net-new (domain, year) pairs? the scoreboard prints both; the deliverable is per-year files, which argues for pairs

- **Corroboration metric in `ark stats` (for the report)**
  - the `evidence` table holds one row per (domain, year) per source, so a pair can carry several sources; no schema change was needed to track cross-validation (`domain_year` keeps its single representative FK, which is the evidence wall)
  - `ark stats` now reports, over all asserted (domain, year) pairs: total evidence rows, average distinct master-eligible sources per pair, count of pairs with 2+ sources, how many of those were already in the baseline, and a per-evidence-type row count
  - only master-eligible evidence corroborates; candidate-only (`link_target`) rows are excluded (they do not prove existence), enforced by filtering to the master types drawn from `evidence_types.MASTER_TYPES` so code and taxonomy cannot drift
  - net-new is defined over the evidence table too: a (domain, year) is net-new iff it is assigned and has no `prior_reused` evidence for that year, which is robust regardless of which row made the assignment (the earlier "assigned row's type" test agreed only by ingest order)
  - **honesty caveat (state it in the report):** "sources" means distinct source rows, not independent provenance. Today's figures (avg 1.33 sources/pair, 2,278,540 pairs with 2+ sources) are entirely baseline-vs-Early-Web, and both trace to the Internet Archive, so this is cross-source coverage, not provenance-independent confirmation. Genuinely independent corroboration begins when the non-IA sources land (ISC = DNS survey, webbase = Stanford crawl)
  - every `ark stats` run writes the exact figures to `run_metrics` (command `stats`), so the reported numbers leave a timestamped audit trail (the execution-log obligation)

- **Audit policy for bulk sources (decision)**
  - every dropped line is written to the per-source audit CSV (completeness for the audit deliverable; early_web produced 1.22M drops, mostly era-typical bare-IP captures, a 131 MB CSV), corrections are sampled with exact totals in run_metrics
  - "earliest in-year capture" holds within one file; across files of one source the first-ingested file wins (documented; immaterial to the evidence bar, any in-year capture suffices)

## 2026-07-24

> Filing convention: three entries below are dated 2026-07-25 in their titles. They are kept here,
> beside the 2026-07-24 decisions they revise, because a revision is far easier to judge next to the
> reasoning it overturns than in date order. Everything else from 2026-07-25 is under its own heading.


- **Prof. Ding ruled on the evidence standard (governs every annual assignment; resolves the III.1 question)**
  - dated DNS-survey presence is DIRECT annual evidence, no IA CDX confirmation required: ISC / Network Wizards recording >=1 host under a domain in an in-year survey is sufficient to place it in that year's file
  - the standard is not limited to webpage captures. Valid year-specific evidence includes dated DNS surveys, archive indexes, host/link graphs, dated directory/index files, and other reliable sources that directly attest a domain existed in the year. Explicitly blessed as direct: ISC survey records, Arquivo.pt capture indexes, and UKWA host/link graph records (the last "when their year association is explicit and documented"); none need the candidate pool merely for not being IA captures
  - required provenance per assignment: source name, survey/dataset date, year-assignment method, and record identifier / source-file reference, so each annual assignment is reproducible and auditable
  - **impact: this confirms the master taxonomy wholesale.** `artifact_listing` (ISC), `cdx_timestamp` (Arquivo / Early Web / IA CDX), and `link_source` (UKWA) are all direct master evidence. The ~1.13M net-new pairs that rested on the ISC `artifact_listing` type (the ~1.13M-vs-193 swing flagged in the interim email) stand as master; nothing downgrades to candidate. The single largest project risk is retired
  - **provenance already conforms** (verified 2026-07-24): every evidence row carries source name (`source.name`), the dated identifier (`evidence_value`: ISC `1997-07`, CDX full timestamp, UKWA `host_link_graph:2001`), the assignment method (`acquisition_method`), and a record id (`evidence_url` for captures; `evidence_value` + the `ingested_file` sha256 ledger for the rest). The §IX provenance export must surface these four fields per row
  - III.4 still governs genuinely UNLABELED sources (StanfordWebBase, undated DMOZ, raw URL lists): those remain candidate -> CDX-verify. The line Ding draws is per-item dated attestation (direct) vs. a bare list with no year (candidate)

- **`whois_creation` evidence standard: registration-interval (decided with the AFNIC data in hand, 2026-07-24)**
  - a BARE creation date, on its own, supports only the creation year - III.6 is explicit that a creation date alone does not establish later years. BUT a source that also shows the registration CONTINUED (a later withdrawal date, or that the domain is still registered now) documents a CONTINUOUS registration interval, because a .fr (and standard gTLD) creation date RESETS on any re-registration. So a 1998 creation date on a domain still registered in 2026 proves an unbroken 1998->2026 registration, hence registration in 1999, 2000 and 2001
  - III.6 accepts "a WHOIS record demonstrating continued registration in that year" as valid later-year evidence; a documented continuous interval IS exactly that for every year it spans. So for interval sources every in-window year the domain was registered is assigned, not only the creation year. This is a documented fact, not the bare-creation-date inference III.6 declines
  - applies now to AFNIC (creation + withdrawal columns); applies to the Phase 4 RDAP engine too (a queryable RDAP record means currently registered), with a per-registry check that the registry resets the creation date on re-registration (true for .fr and standard gTLDs; some ccTLDs keep the first-ever date - verify before trusting the interval there)
  - considered a confirmation email to Ding, decided against it (Ivo, 2026-07-24): the interval is defensible directly from III.6 and is recorded per row, so a reader can verify each assignment themselves (see the AFNIC yield entry). This supersedes the earlier "creation year only" reading, which had not yet accounted for the withdrawal-date column
  - **SUPERSEDED FOR RDAP on 2026-07-25 (next entry): RDAP now assigns the creation year only. Still in force for AFNIC, pending a separate call**

- **RDAP restricted to the creation year, interval rows pruned (Ivo's call, 2026-07-25) - supersedes the entry above for RDAP**
  - trigger: Ivo asked what an RDAP response actually gives per domain before trusting the interval reading. Checked live against `rdap.verisign.com` for `daastol.com`: top-level keys are `entities, events, handle, ldhName, links, nameservers, notices, objectClassName, rdapConformance, secureDNS, status`, and `events` holds exactly four - registration 1998-07-06, expiration 2027-07-05, last changed 2026-07-19, last update of RDAP database 2026-07-25
  - **so RDAP carries current state plus ONE historical timestamp. There is no registration history and no per-year attestation.** Two facts are extractable: created on date D, and registered now. Nothing observes 1999, 2000 or 2001
  - the III.6 test, sentence by sentence: "valid evidence of when a domain was created" = the `registration` event (fine); "may support inclusion in the annual file for the target year in which the creation date falls" = the creation year is explicitly blessed (fine); "a WHOIS Creation Date alone does not automatically establish that the domain remained registered ... in every subsequent year", and later years "still require ... evidence tied to that specific year" = the interval claim fails. For 1999 the store held a record showing registration in 2026 plus a creation date in 1998; reaching 1999 needs a third premise (registry creation dates reset on re-registration) that is an external assumption about registry policy, and one never verified per registry here - the ~1,100 ccTLD rows (.uk 503, .nl 66, .ca 32, .br 31, .cz 28, .no 17, .fi 8) were the known hole. Ding's ruling uses the same qualifier, sources that "directly attest"; a bridging deduction across 28 years is not direct attestation
  - **decision: RDAP evidence supports the creation year and nothing else, and only when that year falls in 1996-2001.** A domain RDAP dates outside the window attests no year and stays a candidate (still worth keeping: RDAP confirms it existed by then and exists now, which is exactly the candidate-pool case under III.4)
  - implementation: `attested_years()` in [`src/ark/rdap.py`](../src/ark/rdap.py) is the single place the rule lives (unit-tested, 2 new tests); `ark rdap` assigns only that year and counts `created_before_window` separately from `created_after_window`
  - rebuild: [`scripts/restrict_whois_creation_to_creation_year.py`](../scripts/restrict_whois_creation_to_creation_year.py), dry run unless `--apply`, parameterized by source. It aborts rather than guess if any creation year is unparseable, or if a doomed assignment could be re-pointed at other master evidence instead of deleted. Verified before applying: **0 of the 9,664 doomed assignments had alternative master evidence**, so the prune was a pure delete
  - lesson (DuckDB): deleting `domain_year` and `evidence` in ONE transaction trips the evidence-wall foreign key, because the FK is validated against the pre-commit index. The script commits the assignment delete first, then the evidence delete. The wall behaved exactly as designed, and the failed attempt rolled back with nothing lost (verified: all counts unchanged before retrying)
  - numbers: rdap evidence rows **28,837 -> 5,973**; rdap-backed pairs **12,770 -> 3,106**; scoreboard 463,365 / 1,313,172 -> **463,364 / 1,303,508**. Pairs removed by year: 1996 8, 1997 283, 1998 1,530, 1999 2,435, 2000 3,185, 2001 2,223. Surviving rdap pairs by year: 1996 559, 1997 806, 1998 889, 1999 345, 2000 355, 2001 152. `ark check` ALL PASS, 116 tests green
  - **correction to my own prediction:** I told Ivo the 537 RDAP domains created before 1996 would lose all their years. Wrong. 536 of them are baseline (`prior_task`) domains reached through gap-fill, so they keep their existing assignments and lose only the RDAP-inferred gap years. Exactly **1** domain (a UKWA link-target) is emptied and returns to the candidate pool, which is why net-new domains fell by 1 and not by 537
  - data preserved before the destructive step: the network-derived creation years are dumped to `data/raw/rdap/creation_years.csv` (6,510 rows, domain + creation year) so the RDAP layer is re-playable without re-querying, and `data/ark.duckdb.pre-rdap-strict.bak` holds the pre-prune store. That CSV is the only irreplaceable artifact here; everything else re-ingests from files
  - **AFNIC left unchanged at this point, as an open question. RESOLVED the same day by the next entry: the premise is documented for `.fr`, so the AFNIC interval reading stands.** The reasoning first offered for keeping AFNIC (that it records both interval endpoints, so its own record demonstrates continued registration) did NOT survive scrutiny and was withdrawn: Ivo pointed out that accepting the same shape of claim for AFNIC while rejecting it for RDAP needed a real justification, and a count of the raw file settled it - 10,050,194 rows, 10,050,194 distinct names, exactly one row per name, so the format cannot express a gap and the absence of a recorded gap is not evidence there was none. Two endpoints establish a span, not continuity. The distinction that does hold is auditability: one registry's policy is checkable, ~590 are not
  - had the strict reading been applied to AFNIC as well it would have cost **69,111 pairs** (not the ~88k first estimated: 87,324 interval evidence rows exist, but 18,213 sit on years another source already carries, so those pairs survive), concentrated in the thin years (2001 -34,643, 2000 -21,225, 1999 -10,305, 1998 -2,811, 1997 -102, 1996 -25) with 5 domains emptied

- **AFNIC `.fr` creation-date semantics VERIFIED from AFNIC's own documentation: the date resets on re-registration (2026-07-25). This validates the AFNIC interval reading**
  - the question (call it R): when a `.fr` name is deleted and the same name registered again later, does AFNIC record a NEW creation date, or retain the original first-ever one? R true makes the interval reading sound; R false breaks it. Method, at Ivo's direction: documentation from authoritative sources FIRST, examples only as corroboration, because positive examples can never establish a policy and the refuting counter-example is effectively unobservable (it needs a domain's true deactivation history from an independent source)
  - **decisive citation, AFNIC's own registrar documentation.** *Technical Integration Guide* v3.0, 27 February 2015, on `domain:info` fields: "`<domain:crDate>` ... in the current version of this interface, the timestamping information is **not aligned with the role described in RFC 5731** but copied from the \"Whois\" pattern. **The creation date is the last creation date of the domain name** or the date of the last transmission (trade or recover)." Retrieved from the Wayback Machine (`https://web.archive.org/web/20151017111200if_/https://www.afnic.fr/medias/documents/technique/integration-guide-en-2015-02-27.pdf`) and confirmed verbatim locally via `pdftotext -layout` (line 3366). The authoritative French edition carries the same sentence ("la derniere date de creation du nom de domaine ou de derniere transmission (volontaire ou forcee)"), as do AFNIC's 2009 EPP specification RC 3.0 and its 2008 predecessor, citing RFC 4931 where 2015 cites RFC 5731. Four editions over seven years
  - note what that document is doing: AFNIC is warning registrars that its creation date deliberately does NOT follow EPP object semantics. So the generic RFC 5731 argument could never have settled this, in either direction
  - **empirical corroboration, re-run independently rather than taken on trust.** `bennegens-couverture.fr`: open data (June 2026) created 30-05-2020, permanently deleted 28-06-2026; `whois.nic.fr` today reports `created: 2026-07-10`. `mintrocket.fr`: open data created 22-04-2022, deleted 19-06-2026; `whois.nic.fr` today reports `created: 2026-07-10`. Deleted in June, re-registered in July, creation date advanced and the original is gone from the record. AFNIC emits neither of RFC 9083's `reregistration` or `reinstantiation` event actions, so a re-registration is indistinguishable from a first-ever one. Both cases are reproducible by a reviewer from the open data file plus one `whois -h whois.nic.fr` call
  - **why this makes the interval a proof rather than an assumption.** `crDate = max(last creation, last transmission)`. Both of those events necessarily fall after any prior deletion, since a deleted name must be created again to exist. Therefore `crDate >= the date of the last deletion`, and the span `[crDate, deletion-or-now]` contains NO deletion event. It is a continuous registration interval by construction. This carries BOTH AFNIC subsets, the 11,902 with a withdrawal date and the 43,123 without, so the earlier worry about the blank-withdrawal majority dissolves
  - **errors are one-directional.** Since `crDate` can only be later than the true first registration, a domain first registered in 1998 but traded or re-registered in 2010 shows creation 2010, falls out of window and is excluded. The tranche undercounts and cannot over-count, which is the safe direction for a scored metric where a false positive is what costs credibility
  - **new caveat to carry: `crDate` also resets on a "transmission (trade or recover)", i.e. a change of holder.** So an AFNIC creation date is the later of (last registration, last holder change) and must NEVER be described as the first-ever registration date. It does not weaken continuity (it can only move the date later), but the wording in report and notes has been corrected accordingly
  - **gaps, stated rather than buried:** (a) the load-bearing sentence is from 2015 and was removed in AFNIC's 2019 documentation rewrite, absent from the current December 2024 guide, so the explicit statement is 11 years old and current behaviour rests on the 2026 live cases above (the 2015 text and the 2026 behaviour were both confirmed first-hand; the claim that the current guide omits it was not independently re-checked); (b) the 2017 edition could not be read, its Wayback capture truncates at 1 MiB, so the lineage has one hole; (c) R being true makes the interval SOUND, not year-TIED in III.6's sense. That residual is interpretive, and only Ding can close it, but it can now be put to him as documented registry semantics rather than an assumption
  - **RDAP stays narrowed to the creation year**, because R is documented for `.fr` only and RDAP spans ~590 registries. The split is now principled: verified premise vs unverified one, not two readings of the same claim. Ivo's call (2026-07-25): not worth chasing R per-registry to recover RDAP's ~9,664 pairs
  - method note: run as a 7-family parallel documentary hunt (naming policy, procedures manual, AFNIC EPP docs, IETF EPP/RDAP standards, open data docs, French regulation via CPCE L45, live registry behaviour plus third-party), with every citation re-fetched by an independent adversarial verifier instructed to reject paraphrased or fabricated quotes. 50 agents, ~2.0M tokens, 43 min. Most structural findings (charter para 134, the create/restore/delete lifecycle, CPCE L45-1) were correctly downgraded to context-only: they establish that a deleted name becomes registrable afresh, but say nothing about the date

- **RDAP re-architected: collection separated from interpretation, so its evidence replays from a hashed file (Ivo's call, 2026-07-25)**
  - the problem: `ark rdap` queried the network AND wrote evidence in one pass, keeping only the extracted year. Two costs fell out of that coupling. (a) Provenance: the resulting rows had no source file, so unlike every other source they could not be replayed from bytes held, only by re-querying a network that now answers differently. (b) Cost of change: the 2026-07-25 narrowing had to be a destructive database migration plus a guard script plus a 4 GB backup, purely because the responses were gone
  - Ivo's question that killed the first fix: an initial plan to post-hoc dump `creation_years.csv` and ingest it once would have needed redoing after every future run. Worse, it would have created a SECOND write path for the same evidence and the artifact was lossy (year only). Confirmed dead end in code: the loader keys the ledger on `(source_name, file_name)` and RAISES on a sha256 mismatch, so a single appended-to file can never be re-ingested
  - **new shape.** `ark rdap <candidates>` is now pure collection: it writes one immutable per-run journal (`data/raw/rdap/rdap_<UTC>.jsonl.gz`, one JSON object per queried domain with domain, queried_at, HTTP status, creation_year, and the WHOLE response) and touches no evidence table, indeed never opens the store. `ark ingest rdap_snapshot <journal>` is pure interpretation, running through the shared audited loader, so the journal earns a sha256 ledger row and a record count like any other source file. Future runs need no extra step: each run drops a new file, same shape as early_web's 224 files
  - side benefits that fell out: collection no longer contends for the single-writer store lock, so it can run alongside other stages; the interpretation step is offline and unit-tested; new rows carry an `evidence_url` (`https://rdap.org/domain/<d>`) and `acquisition_method=rdap_journal_file`, closing two provenance gaps for everything collected from here on; failures and 404s are journalled too, so a later run knows not to retry them and each run's coverage is auditable
  - **why NOT a new evidence type, though Ivo suggested it.** `evidence_type` answers "what kind of proof is this, and may it assign a year", and the taxonomy was signed off with Ding's 2026-07-24 ruling. Both tranches make the identical claim (a registry record fixes a creation date); what differs is only whether it can be replayed from a hashed file, which is provenance depth, not kind of proof. A new master type would add a §2 row describing no new evidence and would churn `MASTER_TYPES`. Used the fields built for that axis instead: a separate SOURCE NAME (`rdap_snapshot` vs legacy `rdap`) plus `acquisition_method`, both of which already surface in `evidence_manifest.csv` and the per-source stats, and `ingested_file` keys on source name so the ledger cleanly covers only the new source
  - **legacy rows left in place (Ivo, 2026-07-25), documented as a limitation.** The 3,106 pairs under source `rdap` keep no artifact. Not re-queried on purpose: re-querying in 2026 returns DIFFERENT creation dates for any domain that has since changed hands, so a backfill would silently alter the result set rather than reproduce it. Recorded in report §6
  - verified end to end on a throwaway store before touching anything real: 4 candidate lines -> 1 rejected by canonicalization, 3 queried, journal written (3.6 KB gzipped); ingest read 3 journal lines -> 2 evidence rows + 2 assigned pairs + 1 outside-window (`bbc.co.uk`, registration 1994-12-13, so `attested_years` correctly returns nothing) and one ledger row with sha256 + `record_rows=2`; re-ingest logged "already ingested, skipping"; re-running collection skipped all 3 and wrote no journal at all. 124 tests (8 new), ruff clean
  - `bbc.co.uk` is the honest illustration of what the strict rule costs: the BBC site provably existed across all six years, and RDAP alone now attests none of them, because its creation date sits before the window
  - measured response sizes for the design call: 2,820 B (`daastol.com`), 2,523 B (`004.com`), 11,480 B (`bbc.co.uk`), so roughly 18 MB raw / ~7 MB gzipped for the 6,510 domains already queried. Cheap enough that keeping whole responses was never a real trade-off

- **AFNIC .fr open data ingested (`afnic_fr`, `whois_creation`): +39,367 net-new domains / +117,829 net-new pairs, the thin years up 5-6x (finding)**
  - source: the AFNIC monthly .fr open-data file (https://opendata.afnic.fr/, `202606_OPENDATA_A-NomsDeDomaineEnPointFr`, 122 MB zip -> 697 MB UTF-8 semicolon CSV, 10.05M rows), exactly one row per domain NAME (verified: 10,050,194 rows, 10,050,194 distinct names) covering every .fr name live at the file date plus every name deleted since 28 January 2014, with its creation date (col 11) and permanent-deletion date (col 12), both `DD-MM-YYYY`
  - method (registration interval, per the `whois_creation` standard above): for each domain emit `whois_creation` evidence for every year in `[creation, withdrawal-or-now]` intersected with 1996-2001. Each evidence row records the interval verbatim, e.g. `01direct.fr` for 1999/2000/2001 carries `registered 16-03-1999..active` - the year assignment is verifiable from the row alone
  - yield: 142,706 in-window records -> 142,248 `whois_creation` evidence rows over 55,531 .fr domains (36 rejected by canonicalization, 428 corrected; 9.99M of 10.05M rows are fully out of window). **+39,367 net-new domains, +117,829 net-new pairs**; scoreboard 419,688 / 1,173,839 -> **459,055 / 1,291,668**. The ingest's `records` count (142,706) matched an independent awk pass over the raw file exactly
  - it lands squarely on the thin years - net-new pairs by year: 1998 1,942 -> 11,130 (**5.7x**), 1999 4,281 -> 25,148 (**5.9x**), 2000 7,345 -> 45,141 (**6.1x**), 2001 27,974 -> 75,312 (2.7x); 1996 +648, 1997 +1,992. Biggest single-source lift to 1998-2000 so far, and it is `.fr` (a geography the .com-heavy baseline barely covers): 40,166 of the 55,531 domains are net-new
  - **CORRECTED 2026-07-25 (this entry originally said "all withdrawals are recent, 2024-2026, a ~2-year retention window"; that was wrong).** The user guide, section "Perimetre d'analyse du fichier / Data file scope", states the file contains "All domain names existing in the whois at the file generation date" plus "**All deleted domain names deleted since 28 january 2014.** For those domain names, the Date of permanent deletion is fulfilled". Verified against the raw file: of the **55,025 rows whose creation date falls in 1996-2001**, the 11,902 carrying a withdrawal date spread evenly across **2014 to 2026**. (Two nearby figures count different populations and are not interchangeable: 55,025 is raw rows created in-window, while the store holds 55,531 distinct registered domains with in-window evidence, a set that also includes 615 domains created before 1996 whose span reaches into the window. The store's withdrawn/still-registered split is 11,880 / 43,652.) (1,342 in 2014, 834 in 2015, 1,192 in 2016, 898 in 2017, 1,105 in 2018, 1,100 in 2019, 884 in 2020, 645 in 2021, 1,303 in 2022, 563 in 2023, 957 in 2024, 733 in 2025, 346 in 2026), not clustered in 2024-2026. File-wide: 4,555,618 rows with a blank withdrawal (live) against 5,494,576 deleted
  - honesty caveats for the report: (a) the file omits only .fr domains deleted BEFORE 28 January 2014, so the yield is a floor that undercounts and never over-counts (a much smaller gap than the retired "~2 years" claim implied); (b) `.fr`-only (geographic skew, complementary to baseline / .pt / .uk); (c) the interval reading rests on AFNIC's documented creation-date semantics, now verified rather than assumed (see the 2026-07-25 crDate entry below); (d) IDN .fr domains are all post-2012, so none are in window and none reach the canonicalizer
  - column-order trap: the 2015 user guide lists File A with `Date de creation` 7th, but the 2026 file ships it 11th. The parser reads the live header positions (0-indexed name 0, created 10, withdrawn 11), verified against a real row (`aaa-aero.fr`, created `29-07-2001`). Compare code to the guide and they will look mismatched; the code is right
  - reproduce: download the monthly A file from opendata.afnic.fr, unzip, `ark ingest afnic_fr <csv>`; the parser filters to in-window registered years and stores the interval as the evidence value

- **ODP dumps are `artifact_listing`, not `dated_directory` (classification note, before the ODP ingest)**
  - the signed-off taxonomy files ODP under `artifact_listing`: "a line in a dated data FILE whose own provenance fixes the year." An ODP `content.rdf.u8.gz` dump is exactly that - a downloaded file with a generation stamp; every external-resource URL a human editor curated into the directory is a line in it, and the dump's date fixes the year for all of them (same shape as an ISC survey list)
  - `dated_directory` is a DIFFERENT mechanism, reserved for a directory PAGE captured by a web archive on a known date (a Wayback snapshot of a Yahoo / yellow-pages category page) - the Phase 4/5 page-harvesting route, not a downloaded dump. (A stray `dated_directory` label for ODP had crept into todo.md; corrected.)
  - why it is valid direct evidence (no CDX recheck): Prof. Ding's 2026-07-24 ruling explicitly blessed "archive indexes ... dated directory or index files" as direct annual evidence. A dated ODP dump is a dated index file, so a domain listed in the 2000-07 dump is direct evidence for 2000, and one in a 2001 dump direct for 2001. It is editorial (a human reviewed a live site and listed it). Negative caveat for the report: absence from a given dump means only "not in that dump", weaker than a CDX negative
  - coverage: ODP contributes 2000 (the Aug-2000 dump) and 2001 (the Kids-and-Teens dumps held + the three downloadable full 2001 content dumps); no 1998/1999 (those dumps never existed - see the hunt)

- **ODP dumps ingested (`odp`, `artifact_listing`): +3,339 net-new domains / +8,423 net-new pairs (finding)**
  - three on-disk dumps: `c2000.gz` (Aug-2000 full content dump, but only a ~1 MB TRUNCATED prefix survives, so just the alphabetically-first categories `Top/Adult...`, year 2000), `kt200106.gz` + `kt200111.gz` (complete Kids-and-Teens subsets, year 2001). The `<!-- Generated at YYYY-MM-DD -->` stamp fixes each dump's year (2000-08-07, 2001-06-10, 2001-11-13)
  - parser pulls cataloged-site URLs by regex (`link r:resource=`, `ExternalPage about=`; internal `Top/...` topic refs excluded), tolerates the truncated gzip (c2000 EOFs mid-stream, handled like UKWA), then canonicalizes to registered domains
  - yield: 93,854 URLs -> 19,629 `artifact_listing` evidence rows over 19,367 domains. **+3,339 net-new domains, +8,423 net-new pairs** (2000 +6,477, 2001 +1,946); scoreboard 459,055 / 1,291,668 -> **462,394 / 1,300,091**. Each row records the dump date (e.g. `odp 2000-08-07`) so a reader can verify it
  - low net-new, as the hunt predicted: only 3,379 of 19,367 ODP domains are net-new (ODP curated popular live sites the IA baseline already holds); the value is mostly 2000 (a thinnish year) plus corroboration
  - caveats for the report: (a) `c2000` is a truncated 1 MB prefix of the ~170 MB Aug-2000 content dump, and the FULL 2000 content dump is not recoverable (Wayback archived only the 2000 `structure.rdf`, which carries no external links), so 2000 is badly undercounted here; (b) the KT dumps are the Kids-and-Teens theme only; (c) heavy baseline overlap
  - available but not done (low ROI): the three FULL 2001 content dumps (2001-01-22 / 06-16 / 10-20, ~170 MB each, downloadable via Wayback `id_`) would add more 2001, but 2001 is the least-thin year and ODP overlap is heavy, so deferred unless completeness is wanted

- **Internet Scout Report archive ingested (`internet_scout`, `dated_directory`): +137 net-new domains / +311 net-new pairs (finding)**
  - source: the Internet Scout Report archive via OAI-PMH (archives.internetscout.org/OAI, `oai_dc`), harvested with a browser UA (the bot UA gets 403); 21,922 records across ScoutReport + 11 sibling publication sets. Each record is an editorial review of a live site; `<dc:date>` (when present) is the Scout Report publication year, which attests the site was live that year -> `dated_directory` (Ding: dated directory/index sources are direct)
  - parser: regex per `<record>`, take the `<dc:date>` year + `<dc:identifier>` site URL(s), with the OAI header id as the evidence reference; filter to 1996-2001
  - yield: **+137 net-new domains / +311 net-new pairs** (975 evidence rows over 686 domains; new pairs spread across all six years: 1996 +24, 1997 +70, 1998 +82, 1999 +57, 2000 +39, 2001 +39)
  - **low yield, stated honestly: 18,508 of 21,922 archive records carry NO `<dc:date>`** (verified genuinely absent, not a parse miss) and cannot be dated from this feed, so they are skipped; only the ~3,400 dated in-window records contribute. The 2026-07-24 hunt's ~2-5k estimate assumed per-record dates that mostly are not present
  - value: small, but a curated non-IA all-years long tail (scholarly / gov / edu / international). Reproduce: harvest the OAI feed (browser UA, follow `resumptionToken`), then `ark ingest internet_scout <file>`

- **RDAP verification engine run on UKWA link-target candidates (`rdap`, `whois_creation`): +831 net-new domains / +2,320 net-new pairs (Phase-4 engine demonstrated end-to-end)**
  - engine: `ark rdap` (`src/ark/rdap.py`) queries `rdap.org/domain/<d>` and reads the `registration` event year. Offline-tested (injected fetch); resumable (skips already-tried domains)
  - **REVISED 2026-07-25:** the figures in this entry were produced under the interval standard. After the creation-year restriction this run stands at **+830 net-new pairs over 830 domains** (one attested year each, its creation year) instead of +2,320 pairs. The source name totals 833 because the separate webbase probe contributed a further 3; those 3 must not be credited to this run as well. The net-new DOMAIN count is unaffected except for one domain created before 1996, which lost its only evidence and returned to the candidate pool
  - candidate pool: the **6,266 UKWA `link_target` hosts** (linked-to in 1996-2001, candidate-only) that were NOT already in the store, i.e. the deferred candidate side of the UKWA graph, turned into dated evidence with no IA CDX query at all
  - result over 6,246 queried: **811 dated in-window (net-new), 1,351 registered but created after 2001, 4,084 no longer registered / no RDAP.** 831 distinct rdap domains, **+831 net-new domains / +2,320 net-new pairs**, concentrated in the mid/thin years (1998 +172, 1999 +492, 2000 +758, 2001 +831; 1996 +8, 1997 +59). Scoreboard 462,531 / 1,300,402 -> **463,362 / 1,302,722**. Each row records `rdap creation <year>`; `ark check` still passes
  - significance: proves the Phase-4 strategy - undated candidate pools become dated `whois_creation` evidence via RDAP, far cheaper than CDX. The ~13% in-window hit rate reflects link-target ephemerality (many linked-to hosts are long deleted -> no RDAP, or re-registered post-2001); a less ephemeral pool would hit higher. The same `ark rdap <file>` scales to larger pools (Domains Project, webbase, deduplicated_urls)

## 2026-07-25

- **webbase-2001 evaluated via RDAP: ~99.99% already held, not a net-new source (finding)**
  - LAW's webbase-2001 URL list (720 MB, 118M URLs from Stanford's 2001 crawl; `data.law.di.unimi.it/webdata/webbase-2001/`) -> 738,625 distinct hosts -> **603,245 distinct registered domains, of which 603,202 (99.99%) were already in the store**; only 43 not-held candidates
  - RDAP'd the 43: **3 dated in-window (+3 net-new domains / +13 pairs)**, 5 created after 2001, 35 no longer registered / no RDAP. Scoreboard 463,362 / 1,302,722 -> 463,365 / 1,302,735. (Pair count recorded under the superseded interval reading; after the 2026-07-25 creation-year restriction these 3 domains contribute 3 pairs, not 13. The domain count is unchanged.)
  - conclusion: like Early Web CDX (99.99% baseline overlap) and the `deduplicated_urls` files (which yielded 8 domains not already held, 6 of which other sources later dated), the popular 2001 web is already fully covered by the baseline + sources. webbase is a large crawl but adds essentially nothing net-new. Retired as a net-new source
  - method note: dedup-before-verify saved a ~4 h RDAP run (planned 15-20k queries) that would have found ~0 net-new. "Measure before scaling" again
  - broader read: the direct net-new avenues are now largely exhausted (national registries / archives gave the wins: AFNIC .fr, Arquivo .pt, UKWA .uk; global crawls overlap the baseline). Remaining upside is niche (untested national archives, WHOIS creation dates for capture-less tails) or corroboration/gap-fill, not large tranches

- **Registry open-data re-check: no new free historical source (finding)**
  - looked again for AFNIC-style registry open data (per-domain creation dates) for other ccTLDs. Result: nothing free reaches 1996-2001. CENTR publishes only aggregate counts; OpenINTEL/DomainMetaData/WhoisFreaks publish current name lists or paid feeds (OpenINTEL measurements start 2015); commercial WHOIS bulk is paid. AFNIC `.fr` remains the one open registry file with in-window creation dates
  - the one repeatable avenue that remains: a **current ccTLD name list -> RDAP for creation dates** (the same pattern that gave +831 from UKWA link-targets). It is bounded by the ~few-per-second RDAP rate, so each run adds hundreds, not an AFNIC-scale tranche; parked as a future incremental lever if a free ccTLD zone/name list is located
  - **Phase-7 delivery packaged** this session: `scripts/package_delivery.sh` assembles `output/internet-digital-ark-delivery.tar.gz` (80 MB: merged masters, net-new additions, `evidence_manifest.csv`, candidates, droplist, audit CSVs, logs, source snapshot, `report.docx`, README) with per-file + archive SHA256. `report.md -> report.docx` via pandoc

- **Gap-fill via RDAP: +2,273 net-new pairs on held domains, 42% RDAP hit rate (finding, figures revised 2026-07-25)**
  - the existing `ark rdap` engine also adds in-window years to domains already HELD in other years. The **"sandwich gap" is a SELECTION HEURISTIC, not the evidence mechanism**: a domain assigned in Y and Y+2 but missing Y+1 is very likely to have existed continuously, so such domains survive to the present far more often than random candidates, which is what lifts the RDAP hit rate to 42% against 13% for link-targets. What actually gets assigned is the creation year, so a run fills the targeted gap year only when the creation year happens to land on it
  - found **470,816 sandwich-gap domains** (assigned Y and Y+2, missing Y+1); ran a 10,000 systematic sample: **4,192 dated (42% hit)**, 1,781 created after 2001, 4,027 no longer registered / no RDAP. Run 2 queried 5,000 more, 1,484 dated
  - **REVISED 2026-07-25:** under the interval standard these two runs were recorded as +7,655 and +2,782 pairs (combined +10,437), spread across every in-window year from each creation year onward. That spread is why the tallies showed 1996 +411 and 2001 +1,097 even though the target years were 1998-2000, and it is the clearest symptom that the mechanism was the interval, not the gap. After the creation-year restriction the two runs stand at **+2,273 net-new pairs over 2,273 held domains** (one attested year each); +0 net-new domains either way
  - the remaining ~455k sandwich-gap candidates are still a lever but a much weaker one than recorded before: at ~1 attested pair per dated domain, expect roughly **1.5-2k pairs per 10,000 queried** (~3.7 h/run at the current client speed), not 3-4k. The honest route to the rest of a held domain's missing years is year-tied evidence (collapsed CDX), not RDAP

- **IA CDX verification engine built; throughput is latency-bound, not rate-bound (finding, 2026-07-25)**
  - built to replace the 6-queries-per-domain loop in `verify.py`: ONE collapsed query per domain answers all six years (`url=*.domain`, `from`/`to`, `filter=statuscode:200`, `fl=timestamp`, `collapse=timestamp:4`). `src/ark/cdx.py` holds the query, the year extraction and the rate governor; `ark cdx` collects, `ark ingest cdx_snapshot` interprets. 16 new tests, all offline
  - same collection/interpretation split as RDAP, for a third reason beyond provenance and re-parsability: **DuckDB is single-writer**, so a multi-hour pass that wrote evidence directly would block every other stage for the length of the sprint. The collector never opens the store
  - `collapse=timestamp:4` is treated as a payload optimisation only, never as correctness: the server collapses adjacent rows and orders by URL key, so a year can still repeat and a response can hit `limit` before some year appears. Years are deduplicated locally, and a truncated response triggers one cheap `limit=1` probe per still-missing year
  - **`ark gaps` restricts the candidate set to bracketed gaps** (held in Y-1 AND Y+1, missing Y), ordered thinnest gap year first (1998, 1999, 2000, 2001, 1996, 1997). Ivo's call 2026-07-25: the adjacency rule (missing Y, present in Y-1 OR Y+1) is 17.5x larger (8,680,978 candidates over 5,256,682 domains) and too speculative for the time available. Bracketed pool: **470,627 domains / 494,764 known gaps**
  - the unit of work is the DOMAIN, not the gap, because one query answers every year. A run therefore harvests years never asked about, which is where most of the yield turned out to be
  - **calibration (three measured runs, this is the finding).** 1 worker at 1.0 s pacing: 15 domains in 5:11 = **20.7 s/domain**, zero throttles. So the bottleneck is per-query LATENCY (a wildcard CDX query costs ~20 s), not a request-rate ceiling, and the lever is concurrency. 12 workers: **2.2 s/domain (~1,650/h)**. 24 workers at 0.15 s pacing: 120 domains in 2:02 = **1.0 s/domain (~3,540/h)**, 1 throttle, governor recovered to 92 ms. A 20x speedup over sequential
  - **governor lesson (my error, corrected).** The first pilot used 4 workers with `max_delay=30s`, `backoff_factor=2.0` and recovery of 0.9x per 20 successes. Six throttles drove the pace to the 30 s ceiling and it never came back: 40 domains took 7:28 (11.2 s/domain) with the tail crawling at 45 s/domain. For a latency-bound workload the ceiling must be low and recovery fast; retuned to `max_delay=5s`, `backoff_factor=1.5`, recovery 0.8x per 5 successes. Pacing exists only to stay under the limiter, not to regulate throughput
  - **yield, measured not estimated.** First 40 domains: 39 with captures, 136 in-window years found, ingested as **136 evidence rows -> 48 net-new pairs** (1.2 net-new pairs per domain queried, versus ~0.15 for RDAP on the same pool). Scoreboard 1,303,508 -> **1,303,556** (1998 +14, 2000 +34). Hit rate varies sharply by position in the priority list (97% capture in the first 40, 50% in the next 60, 22% in the next 120), so per-batch yield must be tracked rather than extrapolated from the head of the list
  - long run launched as **12 sequential batches of 5,000** rather than one job, so each journal completes and can be ingested while later batches still run; resume skips journalled domains, so a kill costs at most one batch's tail

- **CDX engine tuned by measurement; two of my own inferences were wrong and are corrected here (2026-07-25)**
  - **ERROR 1, silent and serious: failures were being recorded as absences.** The status distribution across the first journals was 200:354, **0:2,727**, 503:4. Status 0 is a transport failure, but the run counted any record without years as `no_capture`, so 88% of high-concurrency requests were failing and being reported as "IA never archived this". Two consequences: the apparent collapse in hit rate (97% at the head, 1.5% deeper) was an artefact of my instrumentation, and because resume skipped any journalled domain, **2,727 domains would have been dropped from every later run**. Fixed three ways: failures are counted per status (`failed_0`, `failed_503`, `failed_504`) separately from genuine `no_capture`; `journal.queried_domains` takes an `answered` predicate and CDX passes `status == 200`, so only a real reply settles a domain; the affected domains returned to the queue automatically
  - lesson, added to PersonalContext: an instrument that cannot distinguish "no answer" from "answer is no" will invent a finding. Check the status distribution before trusting any throughput or hit-rate number
  - **the concurrency ceiling is the service's, not the client's.** Answered share by concurrent requests: 1 -> 100%, 4 -> 100%, 8 -> 82%, 16 -> 30%, 32 -> 17%. Past ~8 the server drops connections and emits its own 504s. **Operating point 8 workers, ~800-1,000 answered domains/hour.** The earlier "61,277/hour at 192 workers" was measuring refusals, not queries; 384 workers measured *slower* than 192, which was the first hint
  - **ERROR 2: "fail fast" was a false economy.** From the A/B test the server appeared to kill heavy queries at a consistent ~60.7 s, so I cut the client timeout to 30 s expecting to halve the cost per answer. Measured against the same 100 domains: 30 s answered **51** (695 answers/h), 180 s answered **82** (802 answers/h). Roughly a third of domains reply between 30 s and 60 s, and cutting them off loses more than the saved waiting gains. Since the server already fails fast, the client timeout only needs headroom above its limit: **70 s**
  - **A/B test of the two query strategies** (Ivo's hypothesis, 8 capture-rich domains, sequential, no competing load). One collapsed six-year query: mean **26.9 s/domain**, 3/8 failures. Six per-year `limit=1` probes: mean **73.6 s/domain**, 1/8 failures. Where both answered, years agreed **4/4, zero disagreements**, so the strategies are correctness-equivalent. Verdict: the collapsed query stays the default (2.7x faster), and the per-year strategy is kept as `ark cdx --per-year` for a second sweep, because it succeeds on exactly the heavily archived domains the collapsed query cannot finish (`fieldguides.com`, `oreck.com` failed under A and returned all six years under B). Individual figures: A 2.2 s / 3.2 s / 9.1 s / 16.0 s on successes against B 25.1 s / 30.1 s / 50.0 s / 57.8 s / 86.0 s
  - the hypothesis was therefore half right: per-year probes are more robust but materially slower, so they belong in the fallback rather than the primary path
  - **yield, measured after the instrumentation fix.** Among answered domains, 95-100% hold at least one in-window capture, averaging 3.6 years each, ingesting at **1.15 net-new pairs per domain queried**. Calibration and pilots (~2,400 domains) banked **+840 net-new pairs**, entirely in thin years: 1998 +231, 2000 +479, 2001 +130. Scoreboard 1,303,508 -> **1,304,348**, `ark check` ALL PASS
  - ordering fix: `ark gaps` now spreads domains by `hash(domain)` inside each year tier. Alphabetical order clustered numeric-prefix junk at the head, so a run that cannot finish the pool would spend its whole budget on the least promising names
  - full §VI/§IX.5 write-up, including the reproduce commands, is report §5.1

- **RDAP spiked against IA CDX on comparable work; CDX wins per hour, so both run concurrently (2026-07-26)**
  - question (Ivo): IA CDX turned out slow at ~1,000 domains/hour, so is a fast RDAP pass worth running too? His refinement made the test fair: RDAP evidence counts only for the registration year, so the population must be domains that existed in LATER years but not earlier ones, where a creation date can still land on something new
  - population initially defined as domains whose earliest held in-window year is later than 1996, on the assumption that a creation date must precede everything already held (**wrong, see the correction below**; the `--pre-first` flag this used no longer exists, it became `--creation`). **4,679,861 domains, 15,465,849 addressable year-slots**, an order of magnitude larger than the 470,614-domain bracketed pool. Ordered by E descending, since a later first-held year leaves more room
  - measured on 200 domains: **2,880 domains/hour** (sequential, 0.05 s pacing), 95 dated (47.5%), 105 not dated. Of the 95: **0** created before 1996, **66** created at or after the year already held (nothing gained), **29** landed on a genuinely new year. Examples: `mediater.net` created 1999 first held 2001, `prconsultantsgroup.com` created 2000 first held 2001
  - yield recorded at the time as 0.145 pairs/domain (~418/hour) against IA CDX at 1.15 per domain and ~1,000 domains/hour (~1,150/hour). **That RDAP figure came from a flawed test and is superseded by the correction below; the CDX figures stand.** The structural point holds regardless: CDX wins per hour despite being far slower per query, because a capture answers any year while a creation date answers one
  - **decision: RDAP does not replace CDX and is not worth optimising further.** rdap.org's own ceiling is ~1 request/second, so going faster means bypassing the redirector and resolving registry endpoints per TLD through the IANA bootstrap, which is real work for a source with one seventh of CDX's yield per query
  - **but both now run concurrently**, because they hit entirely different services and neither is CPU-bound: combined ~1,568 net-new pairs/hour, a free +36% over CDX alone. This is also the cross-validation the brief asks for, since a domain both engines answer is corroborated by two independent provenances
  - **CORRECTION, same day: the yield above understated RDAP because the analysis was wrong.** The test used was `creation_year >= earliest_held_year -> already covered`, which is false. A creation date is NOT bounded by the years already held: it resets when a name is dropped and re-registered, so a domain held in 1997 can legitimately report creation in 1999, and that evidences 1999. Ivo caught the reasoning. Re-measured against the actual `domain_year` rows, the same population gave **130 new pairs where the flawed test reported 29** (800 queried, 388 dated, 235 dated in-window, 105 of those already held). Corrected yield **0.163 pairs/domain**
  - **selector replaced with Ivo's rule (2026-07-26):** the population is every domain missing an in-window year ADJACENT to one it holds, ordered by how many such years are missing (each is another chance for the date to land somewhere new). `ark gaps --creation` -> `creation_addressable_domains` in `src/ark/gaps.py`. **5,256,528 domains / 8,680,273 addressable years**, replacing the earlier "earliest held year > 1996" rule which wrongly excluded post-held creation years
  - **honest outcome: the better rule did not produce a better yield.** Measured on 200 domains: dated share rose from 47.5% to **57.5%**, but new pairs per domain came out at **0.145**, statistically indistinguishable from the old selector's 0.163. Reason: "most missing years" selects domains held in few years, and for those the creation year is very often the single year already held (the ISC 1997 survey coincides with many 1997 registrations) - 48 of 77 in-window dates were already held. **RDAP yields ~0.15 pairs per domain however the population is chosen, so ~400-470 pairs/hour is this engine's ceiling.** The rule was kept because it is principled, not because it measured better
  - **resume bug fixed for RDAP (2026-07-26).** `ark rdap` was calling `queried_domains` with no predicate, so every journalled record counted as settled including transport failures - the same defect fixed for CDX a day earlier and missed here. RDAP's predicate is deliberately NOT identical to CDX's: a `404` IS an answer ("no RDAP record exists for this name", which re-asking will not change), while `0` and `5xx` are failures that must be retried. `rdap.answered` accepts `(200, 404)`; `cdx.answered` accepts `200` only
  - **rejected: refreshing the CDX gap list as the store grows.** A CDX query answers all six years at once, so a newly bracketed gap on an already-queried domain is already known, and for domains the run will never reach the refresh changes nothing (Ivo, 2026-07-26)

- **Reliability sampling per evidence type, done from existing journals at zero query cost (2026-07-26)**
  - method: the CDX engine records EVERY in-window year it finds, not only the gap it was sent for, so the 2,587 domains it has answered already carry an independent list of archive-confirmed years. Cross-referencing those against what each evidence type claims for the same (domain, year) gives a corroboration rate without spending a single new request, which matters while the archive is refusing most connections
  - rates: `cdx_timestamp` 100% (11,020/11,045), `artifact_listing` **35%** (1,184/3,342), `whois_creation` from RDAP 32% (24/74), `link_target` 98% (137), `link_source` 100% (25)
  - **the 35% for `artifact_listing` is the important one, and it is complementarity rather than error.** A DNS survey records that a domain resolved; the archive records that somebody crawled its pages. A registered, resolving, unarchived domain is the normal case in this era. A source agreeing with the archive 100% of the time would be redundant with it, so the 65% disagreement IS the coverage the archive lacks, which is exactly why the survey is the largest contributor. Stating the rate without that reading would invite it to be mistaken for an error rate
  - `cdx_timestamp`'s 100% is a self-consistency check, the archive confirming its own index. Its only value is as evidence the query path is sound, and it does confirm that
  - caveats recorded with the figures: a miss is not a disproof, since archive coverage is incomplete; and the population is the bracketed-gap pool rather than a random sample of all pairs, so the rates describe that population

- **`ark download`: page expansion implemented, and the §VII cycle closed (2026-07-26)**
  - `ark download` replaces a one-line stub: it resolves in-window captures of a seed page, fetches each with the Wayback `id_` modifier (original stored bytes, so hrefs are the author's rather than Wayback's rewrites), extracts outbound links, and journals one record per capture. Collection only, like the other two engines, so it never holds the store's write lock
  - **one record per capture, not per page**, because a directory captured in 1998 and again in 2000 evidences its entries for each year separately. That is the per-year rule applied to this route rather than an exception to it
  - **the link/entry distinction is asserted, not guessed.** A link is a claim by the LINKING page, not by the linked host: dead links, typos and later-registered names are all common, so an extracted host is `link_target` (candidate-only) by default. Section IV.i grants that a curated directory page's capture date is item-level evidence for its entries, but no markup rule reliably separates a catalogue entry from a navigation link, so a seed line must explicitly carry `<TAB>directory` to claim that. Two source specs read the same journal and each takes its half, which works because the file ledger keys on (source_name, file_name)
  - stdlib `html.parser` rather than adding lxml or bs4: extracting `href` values from the malformed HTML of this era needs leniency, not a DOM, and a full parser would only be needed for the structural judgement this module deliberately declines to make. It also keeps a C extension out of the fresh-clone reproduction path
  - `discovered_round` is now threaded through the loader and exposed as `ark ingest --round N`, so an expansion round is traceable on the domain row, which is what §VII.f/h ask for
  - 14 new tests, all offline with an injected fetcher

- **Internet Archive began refusing connections after hours of sustained querying (operational finding, 2026-07-26)**
  - symptom: `ark download`'s pilot failed on all three seeds with status 0, and a manual query returned `URLError [Errno 50] Network is down`. Diagnosis showed the local network was healthy (ping fine, `rdap.org` answering in 0.12 s) while **web.archive.org specifically refused TCP on 443**. Eight probes five seconds apart: **2 up, 6 refused, so roughly 25% availability**. Not a hard block, a flap
  - the CDX engine's own logs show the onset rather than a cliff: `failed_0` per 1,200-domain batch climbed to 436 and then 300, with `failed_503: 66`, against the 16% measured at calibration
  - **nothing was corrupted, because a failure is never recorded as an answer.** That decision, made on 2026-07-25 after the opposite bug cost 2,727 domains, is what turns an outage into lost time instead of lost data. Every refused domain stays eligible for a later run
  - **adaptation, per §VI's instruction to adjust rather than abandon:** the supervisor now probes `web.archive.org` before dispatching and holds the CDX engine while it is refusing, and CDX concurrency drops from 8 workers to 4. RDAP is untouched and unaffected, since it is a different service
  - **operational lesson worth keeping: killing a worker without killing its dispatcher just makes the dispatcher spawn another.** The original batch loop survived a `pkill` of its child and immediately re-dispatched CDX at 8 workers against a refusing host, which looked like the reachability gate failing. Diagnosed by listing dispatchers rather than workers

- **Undated pools seeded, and the legacy seed files measured to exhaustion (2026-07-26)**
  - webbase `hosts.txt` seeded as the III.4-named candidate source: **738,625 hostnames -> 603,323 distinct registered domains**, of which **603,141 already confirmed from the baseline**, 64 already confirmed from collected evidence, 1 already a candidate, and **39 genuinely new**. 78 invalid. The three-way split introduced with the seeding fix is what makes this legible: it restates the "99.99% already held" finding as a reproducible measurement rather than a claim
  - `deduplicated_urls_2001-2002` seeded: **1,097,867 lines -> 0 new candidates** (916,133 already baseline, 8 from collected evidence, 3 already candidate, 2,239 invalid). Exhausted, exactly as the 2026-07-22 probe predicted
  - **decision: the 2002-2003 through 2013-2014 legacy seed files are NOT seeded.** Twelve files exist. The one closest to the window yields zero new candidates, so files drawn from progressively later crawls cannot do better, and their populations are dominated by domains registered after 2001. Adding them would inflate the candidate pool with names that could not have existed in-window, which degrades what the pool means rather than growing it. §IX.2 asks for the pool to be as large as practicable, not as large as possible
  - **III.10.c ("if the acquisition method cannot establish a year, the domain may enter only the candidate pool") is currently satisfied by construction, and that was verified rather than assumed.** Of the 6,352 domains queried and left undatable by either engine, **6,352 already hold an assigned year**: both engines are fed from pools of already-held domains, so an undatable result is a held domain with an unfilled gap, not a candidate
  - that is a property of the current pools, not of the code, so both collectors now print a hint when they leave domains undated, telling the operator to run `ark seed` on the same list if it was not drawn from held domains. Interpretation deliberately keeps only years the service returned, so without that step an undatable unknown domain would leave no trace
  - candidate pool across B1 and B2: **4 -> 5,478 domains**

- **UKWA link targets ingested as candidates: the empty candidate pool is fixed (2026-07-26)**
  - `parse_ukwa_link_source` had always yielded only the source host, and its docstring promised a separate target-side source that was never written. That omission, not a bug in `ark stats`, was why the candidate pool held 4 domains
  - both sides now share one truncation-tolerant reader (`_parse_ukwa`) differing only in which column they take, so the target side inherits the tested year-window and stop-at-2002 behaviour rather than duplicating it
  - the loader already supported candidate-only specs, recording evidence and enqueueing the host while skipping year assignment, so this needed a parser and a `SourceSpec`, nothing more
  - result: **88,263 `link_target` evidence rows over 69,152 distinct target domains**, from 166,890 in-window rows (159,708 hostnames corrected to registered domains, 1,244 rejected). Candidate pool **4 -> 5,439 domains**. Zero `domain_year` rows are backed by `link_target`, as the taxonomy requires
  - **finding worth reporting: 63,716 of the 69,152 target domains (92%) were already held.** Being linked to from the `.uk` web in 1996-2001 is overwhelmingly a property of sites the baseline already covers, so the target side's value is the obscure 8% tail, not volume. That also explains why only 5,436 were enqueued for verification

- **`docs/sources.md` added as the per-source deliverable (2026-07-26)**
  - III.11 requires every collected list to be accompanied by an explanation of its acquisition method and time basis. That explanation was previously spread across this log, report §3 and the parser comments, which meant a reviewer had to reconstruct it. One file now carries it per source, from a fixed template: what it is, how obtained, how the year is established, the evidence type AND the argument for that type, measured yield, caveats, reproduction command, brief clause
  - every figure was re-measured from the store rather than quoted from earlier entries, which caught two errors: the AFNIC withdrawn/still-registered split is **11,880 / 43,652** over 55,531 domains (not the 11,879 recorded in the defect list), and those sum to one more than the total because a single registered domain carries both an active and a withdrawn span, two supplied rows having collapsed onto it
  - **decision: per-source net-new is reported as attribution against the finished store**, meaning domains that carry the source's evidence, hold an assigned year, and have no `prior_reused` row. That is deliberately not the same as the scoreboard delta at ingest time: a domain contributed by source A and later also evidenced by source B is attributed to both, while the delta credits only A. They differ by a few hundred out of ~460,000 (ISC: 396,973 attributed against the +397,151 delta recorded on ingest). Both numbers are correct for what they measure, so the file states which it uses and any delta quoted elsewhere is labelled as such
  - includes a 21-row evaluated-and-rejected table, so negative verdicts are visible in the delivery rather than only in this log (§VIII expects the search to be evidenced, not just the wins)
  - shipped in the delivery archive and linked from README, report §3 and the archive README

- **Seeding: only a confirmed year settles a domain (2026-07-26)**
  - `seed.py` classified a domain as `already_known` if it appeared in the `domain` table at all, and skipped it. That is wrong for exactly the population the candidate pool is made of: a domain on file with NO assigned year is a candidate, reached by a candidate-only source, or dated outside 1996-2001, or queried and unanswered. Those were counted as settled and never enqueued, while `ark export` still listed them as candidates
  - now three states instead of one: `already_confirmed_baseline` (has a year, carries `prior_reused`), `already_confirmed_own_evidence` (has a year from collected evidence), `already_candidate` (on file, no year -> still queued). This also discharges the long-standing "split `already_known` into baseline vs earlier-seeded" item
  - classification moved from one query per line to one set-based query, which matters at the 600k-domain seed files that section B will feed it
  - verified while here that both verification selectors already drop fully-covered domains: of 31,492 domains holding all six in-window years, 0 appear in the RDAP pool and 147 (0.03%) appear in the CDX pool, those being domains whose gaps the CDX run itself filled after the list was generated. Accepted as the staleness cost of not regenerating the list mid-run (Ivo, 2026-07-26)

- **`just` recipes for every documented command, and the `check` name collision resolved (2026-07-26)**
  - the collision Ivo flagged: `just check` ran lint plus tests while `ark check` runs the nine data invariants. Two different validations, one name, and the failure mode is running one and believing the other passed
  - resolved by refusing to give either the bare name: `just verify-repo` validates the code (lint, format-check, tests), `just check-data` validates the data (`ark check`), and `just check` runs BOTH, which is what someone typing it actually wants
  - the pipeline is now five named stages (`baseline`, `sources`, `candidates`, `journals`, `deliver`) with `just reproduce` chaining them, plus `cdx-batch`, `rdap-batch` and `expand-round` for the network collectors. Verified with `just --dry-run reproduce`, which prints the twenty underlying `uv run` commands in order
  - the raw `uv run` commands stay the reproducibility contract, because they need nothing but uv. `just` is a convenience layer over the same strings, never a second definition of the pipeline

- **A journal is published only when its run stops, or the ledger would record half a file (bug, 2026-07-26)**
  - found while writing the `just journals` recipe. The documented ingest command globs `data/raw/cdx/cdx_*.jsonl.gz`, and with the supervisor running there is almost always a journal being written. Confirmed empirically that `parse_cdx_snapshot` does not raise on a half-written gzip stream, it reports `truncated_tail` and yields the records it managed to read: 121 records out of the live journal
  - so the sequence was: ingest hashes the partial bytes, parses 75 lines, commits evidence plus a ledger row for that hash. The collector then finishes writing, the file's hash no longer matches the ledger, and every later ingest raises `ledgered with different content` with the whole tail of the run unreachable until someone deletes the ledger row by hand
  - checked whether it had already happened: 26 ledgered journals, 0 hash mismatches. Latent, not triggered, because every ingest so far landed between batches
  - fixed in `journal.py`, which owns the invariant: a run writes `<name>.jsonl.gz.part` and renames to `<name>.jsonl.gz` when it stops. The ingest glob no longer matches a live run, while `queried_domains` globs `{prefix}_*.jsonl*` and still reads `.part` files, so a killed run's answers are not queried again
  - the rename happens on any exit including Ctrl-C, an exception, and SIGTERM. SIGTERM needed a handler: Python exits on it without unwinding, so `finally` would not run and the journal would stay stranded as `.part`, and SIGTERM is exactly how `supervise_engines.sh` stops a collector
  - a `.part` file surviving a hard kill (SIGKILL) is deliberately NOT auto-promoted. Promoting it would race a collector that is still writing, and on POSIX the rename would not stop the writes, which reintroduces the same bug. Renaming it by hand is the documented recovery
  - 7 tests in `tests/test_journal.py`, one per property, including that a live journal is invisible to the ingest glob but visible to the resume scan

- **The test suite was overwriting a shipping artifact (bug, 2026-07-26)**
  - noticed while collecting real per-step output for the reproduction instructions: `data/reports/source_contribution.csv` held two rows, `prior_task` and `ia_cdx` with one evidence row each, instead of the fourteen real sources. Its mtime was the minute the test suite had last run
  - cause: `export_all` took `netnew_dir`, `candidates_path` and `masters_dir` as parameters but called `write_contribution_tables(conn)` with no directory, so that one table pair always went to the real `data/reports/`. `test_export_all` redirected the three destinations it could and silently clobbered the fourth
  - this sat in the delivery path. Packaging straight after a test run would have shipped a contribution table describing 2 domains instead of 5,293,498, and that table is the evidence behind every per-source claim in the report
  - fixed by making `report_dir` a parameter like the others: a caller that redirects the outputs must redirect all of them. The test passes `tmp_path / "reports"`, and a second test asserts both tables land where the caller asked
  - real tables regenerated with `ark export`. `netnew_pairs` across the fourteen sources sums to 1,308,314, matching the scoreboard exactly, which is the check that says the regenerated table is the real one

- **Two wrong file globs in the `just` recipes, caught by checking them against the ledger (2026-07-26)**
  - `isc_survey` was written as `data/raw/isc_survey/*.domains.gz`, which silently misses `wb_nw_9607_org.gz`, one of the five files actually ingested. `*.gz` matches all five
  - the candidate seeds were listed as the UKWA target list, but UKWA targets enter through `ark ingest ukwa_link_target`; the two files really seeded were `data/raw/webbase/hosts.txt` and `legacy-data/deduplicated_urls_2001-2002.txt`
  - both found by expanding every glob in the recipes and comparing the count against `ingested_file`: early_web 224, isc_survey 5, afnic 1, odp 3, all matching. Worth repeating for any documented glob, since a glob that quietly matches too little looks identical to a correct one

- **The section VII cycle closed end to end, and the conservative call paid for itself (2026-07-26)**
  - the loop the brief describes, run once on real data rather than described: **discover** (outbound links from archived directory pages, plus hostnames read from 100hot listings) -> **candidate pool** (because neither route is assertable: a text regex cannot tell an entry from an advertisement, and archived HTML carries typos) -> **verify** (`ark cdx` against the Internet Archive) -> **master evidence** for the years that came back
  - 298 discovered candidates queried, 233 answered, 65 failed and stay eligible. **198 of the 233 answered domains (85%) hold an in-window capture**, giving **+278 net-new pairs and +198 net-new domains**
  - by discovering source: 100hot listings 171 domains promoted (234 pairs), page expansion 27 (44 pairs). 106 remain unverified, nearly all of them retryable failures rather than negatives
  - this is the number that justifies the earlier refusal. The same 258 names could have been asserted from a regex over listing pages and counted immediately; instead they cost one 40-minute query batch and came back with **archive captures naming the specific years**. 85% is also a reasonable rate to quote for what a directory listing is worth as a *lead*, as distinct from as evidence
  - scoreboard after: **463,565 net-new domains / 1,310,558 pairs**

- **100hot.com: 258 new candidates, and a recommendation not taken (2026-07-26)**
  - a parallel source review ranked 100hot.com first of six, projecting 700-1,100 net-new domains as master `dated_directory` evidence from its 2001 `/list.gsp` pages, and prescribed a regex for host cells of the form `<td class="sm">www.example.com</td>`
  - that markup is not in the cached pages. Measured across all 130: the `/list.gsp` captures carry almost nothing but navigation chrome (`go2net`, `infospace`), while the productive pages are `/directory/<category>/<topic>.html`, at roughly 100 hostnames each. So the specific route recommended was not the productive one
  - the review was right about the underlying mechanism, though: the listed hosts are **plain text**, not links, so the pipeline's own link extractor sees 1,749 domains and 20 net-new pairs, while a text scan sees 3,453 domains and 488 net-new pairs
  - **the master-evidence recommendation was still declined.** A text regex cannot tell a listed entry from an advertisement, a prose mention or a navigation label, and this project's own rule (recorded with the evidence taxonomy) is that only curated *entries* on a directory page are `dated_directory`, while everything incidental on the same page is candidate-grade. Asserting 488 pairs from a regex would break the rule that makes the other 1.3M defensible
  - so the whole scan went to the candidate pool instead: **3,453 hostnames seeded, 3,187 already confirmed from the baseline, 8 from collected evidence, 258 genuinely new**, all queued for CDX verification, where a capture will settle each on its own evidence
  - recorded because the disagreement is the point: a projection of ~1,000 net-new domains became 258 candidates once the evidence standard was applied, and the difference is entirely in what counts as proof rather than in the data

- **Concurrency re-measured after the outage; 8 workers confirmed, 12 is worse (2026-07-26)**
  - the Internet Archive began answering again around 02:53 after refusing connections for hours, but degraded: 4 workers gave ~185 answered domains/hour at a 64% answered share, against the ~1,000/hour measured before the outage
  - stepped the pool up and measured each setting on live traffic rather than assuming the old calibration still held. **4 workers: ~185/hour, 64% answered. 8 workers: ~383/hour, 92.5%. 12 workers: ~262/hour, 84%.** So 12 is worse than 8 on both axes, and the pre-outage operating point of 8 survives a service that is otherwise much slower than it was
  - the shape matches the original calibration (answered share 82% at 8, collapsing above), which is the useful part: the service's concurrency ceiling is a property of the service and does not move when its latency does. Left running at 8

- **Section VII expansion, two rounds, and why round 1 had to fail first (2026-07-26)**
  - **round 1: 27 directory and navigation home pages, 19 fetched, 92 domains, 187 evidence rows, 0 new candidates and 0 net-new pairs.** A complete miss, and the useful kind: a directory HOME page links to its own category pages (same domain, excluded) and to the handful of major sites the baseline already holds. The catalogued sites live one level in
  - deliberately no page was asserted as a curated directory in round 1. Under IV.i that assertion makes a page's capture date master evidence for everything listed on it, and asserting it from the reputation of a hostname would be guessing
  - **the assertion was then made from the catalogue's own words.** The 1999-01-25 capture of `vlib.org` carries `<META name="description" content="Directory of the Virtual Library, an expert-run catalog of sections of the web">` and `DC.Type: Bibliography`, and lists 46 subject sections. So each of those URLs is an editorially maintained catalogue by the catalogue's own definition, which is what IV.i asks for
  - **round 2: those 46 subject libraries, 47 captures fetched, 1,332 domains, 2,741 evidence rows, +218 net-new pairs.** Yield lands where it is most needed: **1998 +100 and 1999 +82**, the two thinnest net-new years
  - checked for phantom domains before asserting anything, because HTML transcription typos turn `harvard.edu` into `arvard.edu` and a parallel source review measured roughly 40% of fully-new names from this route as typos. Of the 218 net-new pairs, **215 are on domains the store already knew from an independent source and only 3 are on new domains** (`eurofed.org`, `wwpress.com`). At that ratio the exposure is 2 domains out of 463,366, so the pairs were taken and the two names recorded here rather than hidden
  - seed lists live in `seeds/expansion/`, tracked, because they are authored inputs rather than downloaded data and section VII is not reproducible without them

- **The SIGTERM handler made the collectors unstoppable; fixed the same hour (regression, 2026-07-26)**
  - introduced by the `.part` fix earlier the same hour. Turning SIGTERM into `SystemExit` so the journal gets renamed was right, but it exposed something the old behaviour hid: the collectors submit the whole batch to the thread pool up front, and `with ThreadPoolExecutor(...)` waits for every queued task on the way out. So `SystemExit` propagated into `__exit__` and then waited for the remaining ~1,000 queued HTTP requests
  - before the change, SIGTERM killed the process outright (leaving a truncated file, which is what the change was fixing). After it, `pkill` was silently ignored: caught by noticing the supervisor had been restarted but the old 8-worker process was still running minutes later, and it took `kill -9` to stop
  - fixed with `_abortable_pool`, a context manager that shuts the pool down with `cancel_futures=True`. Cancelling loses nothing, because an unanswered domain was never journalled and the next run asks again
  - the `-9` left an orphaned `.part`, which was recovered exactly as documented: rename it, then ingest. 200 journalled domains, +246 pairs, nothing lost
  - lesson recorded because it generalises: making a process handle a signal is only half the job, and the half that is easy to miss is what the process then does on its way out. A test now asserts a stopped run returns in under 5 s rather than draining 200 queued tasks

- **Auxiliary seed pool shipped: 3,595,769 hostnames and URLs (2026-07-26)**
  - brief I asks for historical URL seeds alongside the domain lists, and III.2 allows an auxiliary seed pool for data with no year evidence of its own. III.8 makes the registered domain the counting unit, which is right for counting and wrong for downloading: a crawler given `foo.com` never reaches pages that only ever existed at `shop.foo.com`
  - built without a second parser. Every bulk parser already yields `BulkRecord.raw`, the value as the source wrote it, before canonicalization. `ark seed-pool` re-reads the same files through the same parser and keeps the raw form, so a seed cannot disagree with the evidence it came from. Only seeds differing from their registered domain are kept, since an identical one adds nothing the year files lack
  - yield by source: early_web 2,986,491 (URLs, the deepest granularity), isc_survey 512,804, ukwa_link_source 58,737, odp 36,157, internet_scout 1,630. **3,595,769 distinct seeds over 2,195,955 registered domains**, of which 19,699 domains are not in the baseline
  - the command is `ark seed-pool`, deliberately not `ark seeds`: `ark seed` loads candidate DOMAINS into the verification pool, and two commands one letter apart doing different things is the same trap as the `check` collision
  - two defects found and fixed while building it. The first cross-connection copy used `executemany` over 2.2M domains and ran for minutes holding the store's write lock; doing the anti-join in SQL against the part files takes 0.85 s. The second: ODP URLs contain commas (`.../0,6109,393333,00.html`), and although the CSV quoted them correctly, a reader that sniffs quoting from the first rows finds none and splits those URLs into extra columns, so the seed column is now always quoted
  - honest framing for the report: the pool is mostly deeper granularity on domains already held rather than new domains. Its value is for the downloading phase the brief describes, not for the scored pair count, and it is reported separately from the score for that reason

## 2026-07-26 (final review pass)

An independent audit of the whole delivery against the SPEC, with the report and the two READMEs treated as the graded artifacts. Every figure below was re-measured against `output/provenance/*.parquet` before the fix was written, and four of the audit's own claims did not survive that re-measurement; those are recorded here too, because a plan that is trusted rather than checked is how most of these defects got in.

- **`ark rebuild` overwrote the evidence it was handed (blocking)**
  - `rebuild()` passed `provenance_dir=` straight through to `export_all`, so the documented tier-2 command `uv run ark rebuild ../provenance` re-exported Parquet **into the folder it had just read**. A Parquet round-trip is not byte-identical, so a reviewer who ran tier 2 and then re-ran `verify.sh` saw files differ and would reasonably conclude the archive was tampered with; one who rebuilt first had the shipped evidence silently replaced by a re-derivation of itself, which destroys the independence of the whole check
  - fix: `export_all(conn)`, letting the destination default. The parameter itself stays, because it is what stops the **test suite** clobbering shipping artifacts; the lesson is that the same door it closed for tests it opened for reviewers
  - this is the defect the "run the reviewer path twice" step exists to catch, and it is the reason that step is not optional

- **The report's own results table did not add up (blocking)**
  - section 1 gave the merged domain total as 5,293,805, which is the store's whole `domain` table and therefore includes the 5,583 candidates the same section calls excluded. The shipped masters hold **5,288,222** (`cat data/exports/*.txt | sort -u | wc -l`), and 5,293,805 - 5,288,222 = 5,583 exactly. The Domains column now adds up (463,566 + 4,824,656) as the Pairs column always did. First table a reviewer reads

- **Two contributing sources were missing from the report's source table (blocking-adjacent)**
  - the Pairs column summed to 1,322,347 against the headline 1,322,365: the superseded `ia_cdx` route (8 domains, 11 pairs) and `arquivo_roteiro` (0 domains, 7 pairs) both ship and both appear in `sources.md`, but neither had a row. Folded each into the row for the same service rather than adding rows, so the column now sums to **exactly 1,322,365**
  - the Domains column sums to 465,122 against a headline 463,566 and **can never sum**, because a domain found by two sources counts in both rows. Kept the column, since the SPEC asks for additions counted by source, and said so in the table's lead-in instead of leaving a reviewer to find the discrepancy
  - one Arquivo figure everywhere now: **17,696**, both indexes, with each sentence's subject reworded to "the Arquivo indexes" rather than the single 47 GB file. Carrying both 17,689 and 17,696 was how the drift started

- **Section 7 stated an arithmetic impossibility (high)**
  - "199 net-new domains and 11,932 net-new pairs" cannot both be true: 199 domains across six years cannot carry more than 1,194 pairs. Measured split: the 11,932 are **280 pairs on 199 brand-new domains plus 11,652 previously unevidenced years on domains the baseline already held**. That is exactly what gap-filling is, the report never said it, and saying it makes the result look better rather than worse
  - the projection in section 9 used 1.40 pairs per *answered* domain against *unqueried* domains, but only 76% of queried domains answer, so it overstated expected yield by about a third. Now **1.07 pairs per domain queried**. This is the only number in the document arguing for future work, so it is the one that has to be conservative

- **A false claim about the test suite, deleted rather than narrowed (high)**
  - section 4 claimed each of the nine invariants has a test planting the violation. `tests/test_checks.py` has **four** such tests, plus a clean-store test and an exemption test. Deleted the sentence: it is a claim about tests inside a report about data, and the preceding sentence already carries the rigour

- **Contribution table could not be reconciled with the candidate pool (medium)**
  - `per_source` built `FROM evidence`, so the four sources that only ever fed the candidate pool vanished, and the shipped candidate column summed to 5,455 against the report's 5,583. Now `FROM source LEFT JOIN evidence`, with `count(e.evidence_id)`, so a candidate-only source appears with zero evidence rows. The column sums to **5,583**, matching both the report and `output/candidate_unverified.txt`
  - knock-on, decided deliberately: this widens the CSV from 17 rows to 21, so `sources.md`'s summary table can no longer be a row-for-row transcription of it. Rather than add four all-zero rows to a document a human reads, the table's caption now says it lists the sources that carry evidence rows, and points at the CSV for the seed lists. Its net-new pairs column sums to **1,322,365** after the missing `ncsa_whats_new` row was restored

- **The evidence behind the report's showcase result was not in the archive (blocking)**
  - `data/raw/cdx/verify_sample/cdx_discovered.jsonl.gz` sat one directory below a flat `cp data/raw/cdx/cdx_*.jsonl.gz` glob, and holds the **278 record rows** behind section 7's "198 (85%) held an in-window capture, adding 278 pairs". Moved it up one level; the ledger keys on file name only, so the store is untouched and the file stays "already ingested". Both the packaging and ingest globs reach it now: 32 journals, all at one level
  - the packaging script already carried a comment about this exact bug being hit once for the expansion journals, which is why that line uses `find`. The CDX and RDAP lines never got the same treatment; both now use `find` too, so the next journal that lands in a subdirectory does not repeat it a third time

- **Tier 3 could not complete: an undocumented input (blocking)**
  - the documented step `ark seed data/raw/100hot/candidate_hosts.txt` names a 49 KB authored file that no shipped document explains how to obtain, and the CLI declares the argument `exists=True`, so the step aborts and takes `just reproduce` with it. It is authored, not downloaded, so documenting a download route would be a fiction: copied it to `seeds/100hot_hosts.txt` and tracked it beside the already-tracked expansion seed lists, so it ships inside `source/source.tar.gz`. Only tracked files reach that archive, which is why this needed a commit rather than a `git add`

- **`report.docx` opened on a broken field (blocking)**
  - pandoc's `--toc` writes a TOC field with no cached result, so the first two rendered lines of the primary deliverable were the heading "Table of Contents" followed by the literal `TOC \o "1-3" \h \z \u`, in every viewer that does not refresh fields. It was also the only content in the docx not present in the markdown. Dropped `--toc`; nine numbered sections do not need one

- **A staleness guard that had stopped looking (medium)**
  - `scripts/refresh_report_figures.py` carried rewriters for the report, the archive readme and `sources.md` whose anchors none of those documents still use. It matched nothing, printed "already current" for each, and so reported success precisely because it had gone blind, while the README total it was supposed to protect sat 7 pairs and 1 domain stale. Reduced to the one demonstrably live rewriter, which now raises if its anchor disappears. A rewriter that cannot find its anchor is worse than no rewriter

- **Claims corrected against the code they describe (medium)**
  - the PSL patch covers **nine** retired ccTLDs (`.yu .an .bu .cs .dd .gb .tp .um .zr`), not the six the report listed: the report was understating its own work
  - the candidate breakdown read "39 from a crawl host list ... 3 from earlier probes"; measured by `discovered_source` it is 5,435 + 87 + **38** + 19 + **4** = 5,583. Two errors that happened to cancel, which is why the total looked right
  - "1998 and 1999 were thin and materially improved" was backwards. Against their own masters, 1998 gained 1.7% and 1999 1.9%, the two *least* improved years, while 2000, described as only partly served, gained 4.2%. Misstating the data in a limitations section undercuts the section's purpose
  - six sites in `src/` cited clause numbers that do not exist in the SPEC ("IV.i", "III.10.c"): `grep -c` returns 0 for both. Deleted the locators, kept the substance, since a reviewer cannot look up a clause that was never written
  - `verify.sh` was documented as confirming the annual files "hold the number of pairs claimed"; it prints the counts and compares them to nothing, so check 2 passed whatever the files contained. The description now says what it does

- **Audit claims that did NOT survive re-measurement, recorded so they are not re-adopted**
  - the `.fr` interval exposure was said to measure 69,111 "two ways". Only one gives that: pairs whose backing AFNIC row assigns a year other than the creation year = **69,111**; the same restricted to pairs no other non-baseline source backs = **69,044**. The figure shipping in the report was already right and `sources.md` was the stale one, so the fix stood, but the stated justification for it did not
  - the missing `output/candidate_unverified.txt` was filed as a documentation nit. It was live: the file was absent from `output/` at review time, and because the packaging script swallowed the copy with `2>/dev/null || true`, the next repackage would have shipped an archive with **no candidates.txt at all**, silently, and candidates are a deliverable the professor named explicitly. Dropped the `|| true`, so a missing result file now fails the build instead of quietly shrinking the delivery
  - the plan's own claim that the report needed cutting for length was wrong in the other direction: it renders to 1,678 words in the docx, already inside the target, and the higher markdown count is inflated by table pipes

- **Tier 3 executed for the first time, in an isolated clone: 99.77% of the shipped result (finding)**
  - the one delivery claim never actually run. Executed from a scratch directory beside the repo, built from the archive's own `source/source.tar.gz` plus the archive's `baseline/`, with `data/raw` brought in by APFS clone (`cp -Rc`, 51 GB in 0.64 s, copy-on-write so the repo copy cannot be touched). Every write path in `src/ark/` is a relative `Path`, so the working directory is the whole isolation boundary; the repo store was never opened
  - **runtime is not "hours".** Measured end to end at **17m14s**: baseline 3:34, sources 10:35, candidates 1:43, journals 0:27, seeds 0:46, deliver 0:09. The hours in the documentation were always the 47 GB download, and the two READMEs said "hours" in the cost column as though ingest were the cost. Both now say what it is
  - **result: 1,319,272 pairs over 462,726 domains against the shipped 1,322,365 / 463,566**, so 3,093 pairs and 840 domains short, and `ark check` still returns nine `[PASS]` and `ALL PASS`. The rebuild is internally consistent, just smaller
  - cause, and it reconciles exactly: two sources have no journal to replay. The legacy `rdap` tranche (833 domains / 3,106 pairs) and the superseded `ia_cdx` route (8 / 11). 841 candidate domains minus 840 actually lost = 1 that another source also backed; 3,117 candidate pairs minus 3,093 = 24 likewise. The 840 domains are not destroyed, they fall back to the candidate pool, which grows 5,583 -> 6,423, and the masters total moves 5,288,222 -> 5,287,382 by the same 840
  - this was predicted before the run from `files_ingested: 0` on both sources plus the report's own admission that the legacy tranche has no hashed source file. Worth recording that the prediction was checkable from the shipped artifacts alone, which is what a sharp reviewer would have done
  - **decision: document the delta rather than manufacture a journal.** Re-querying RDAP today returns different creation dates for domains that have changed hands, which the report already rejects as altering rather than reproducing the result. So README, `delivery_readme.md` and the report's limitations now state the 99.77% and why, and both READMEs distinguish tier 2 (reproduces the shipped files exactly, byte for byte) from tier 3 (re-derives what can be re-derived from files). The alternative, leaving "This reproduces the shipped numbers exactly" in the README, was a claim a reviewer would have disproved in twenty minutes
  - two fixes proved end to end here for the first time. `cdx_snapshot` ingested **32** files, so B4's recovered journal is genuinely reachable by the documented glob; before the move a tier-3 run would have landed 278 pairs short. And step 18's repointed `ark seed seeds/100hot_hosts.txt` returned `lines: 3453, new_candidates: 258` exactly as documented, so B3's tier-3 abort is really gone
  - every bulk source reproduced its evidence-row count exactly (early_web 2,278,722, isc_survey 1,662,395, afnic_fr 142,248, odp 19,629, ukwa 39,454 and 88,263, ncsa 4,916, arquivo_roteiro 3,442), and the seed pool came back at 3,595,769 over 2,195,955. The from-source path independently re-derived the merged master total, which is the strongest available confirmation that 5,288,222 is right
  - one cosmetic consequence of B3: a seed source is named after its file stem, so `candidate_hosts` becomes `100hot_hosts` in a fresh run. No count changes. Not worth renaming the file back, since the tracked name is what makes tier 3 runnable at all

- **Source drift: two sources cannot be hash-pinned, and one is already a month stale (finding)**
  - `data/raw/checksums.sha256` pins 235 files: early_web 224, isc_survey 5, odp 3, arquivo 2, ukwa 1. That is every source that can be pinned, and the ones that are pinned are exactly the ones rescued from archives, which is where a silent substitution would be most damaging
  - the `.fr` open data file cannot be. It is republished monthly; this delivery used `202606_OPENDATA_A` (June 2026) and `sources.md` tells the reviewer to download "the current A file", which as of today is the July edition. AFNIC is the second largest source at 117,829 pairs, so this is the largest single reproducibility exposure in the project, larger than the unjournalled RDAP tranche. The drift is one-directional in the same way the source is: a domain re-registered since June gets a later creation date and leaves the window
  - the Internet Scout OAI feed is live and keeps growing, so a later harvest can hold records this one did not
  - stated in both READMEs and in the two source sections rather than left for a reviewer to discover. It is also the clearest argument for why the archive ships the journals and the Parquet export at all: those are fixed, and the upstream files are not

## 2026-07-28 / 29 (phase 2: rebasing onto merged260727)

Ding's feedback set two binding rules for every future round: start from `merged260727`, and report true marginal additions after deduplication against it. Completeness is claimable only below 10,000 additions **and** below 0.1% growth. Phase 1 grew the reference set 17.38%, so the period is nowhere near closed. Two collectors ran throughout this work, which is why several of the findings below are about operating them rather than about the data.

- **RDAP was silently discarding a fifth of its own pool (blocking)**
  - `ark rdap` journals a record for every outcome, and `rdap.answered()` exists precisely so that only a 200 or a 404 settles a domain: its docstring says a transport error "means the question never landed, and treating that as settled would silently drop the domain from every later run". But `cli.py` called `queried_domains()` **without passing it**, so the default predicate counted every record as settled, rate limits and connection failures included
  - measured impact: **12,888 domains** marked permanently done that had never actually been answered. Fixed by passing `answered=rdap_answered`; the skip count fell from 45,378 to 32,490, which is exactly the correctly-settled figure, so all 12,888 returned to the pool
  - nothing was lost, and the reason is worth recording: journals are immutable and the predicate is applied **on read**. Correcting the rule retroactively restores wrongly-skipped work. `ark cdx` was never affected because it always passed its predicate
  - the same night showed why the predicate matters. `--delay 0.05` is 20 requests a second from one IP; across a 12-hour window that drew 7,895 rate-limit responses, after which the registries refused connections outright and one batch returned 1,864 transport failures out of 1,910. The registries' own notices state that bulk query access from a single source is detected and limited, so that pace was never defensible. The delay is now the third argument to `supervise_engines.sh`, defaulting to 0.5 s, and dating recovered to roughly 870 per 2,500

- **A second baseline could not be ingested at all, and failed quietly (blocking)**
  - `ingest_year_file` decides a file is already ingested by matching `evidence_value` against `path.name`, which is bare `1996.txt`. The phase-1 baseline holds exactly those markers, so pointing the command at `merged260727` would log "already ingested, skipping" six times and change nothing. Six skip lines look like success
  - fix: a `marker_prefix` threaded through `ingest_legacy`/`ingest_year_file` and exposed as `--marker-prefix`, so the release records as `merged260727/1996.txt`. Small, but it earned a test, because the failure mode is not an error: it is a whole round built on the wrong baseline and only discovered when the reviewer merges it
  - ingest result: six files, 0 skipped, **0 year rows added**. That zero is the informative part. At registered-domain granularity `merged260727` contains no pair the store did not already hold, which is the expected consequence of it being the old baseline merged with phase 1's own output

- **Export and stats disagreed about what "new" means, and only the rolling baseline exposed it (blocking)**
  - `export.py` defined an addition by following `domain_year.evidence_id` and asking whether **that row** is baseline. `stats.py` asks whether **any** baseline evidence exists for that `(domain, year)`. Under a fixed baseline those agree. Under a rolling one they diverge, because `INSERT OR IGNORE` leaves an already-assigned pair pointing at its original CDX evidence even after a later release absorbs it
  - consequence had it shipped: `output/netnew/` would have held **1,339,783** pairs instead of 17,418, re-claiming the whole of phase 1 as new against a baseline that already contained it. That is exactly what the feedback forbids: "do not report internal pipeline insertions as if they were new against the project". It would have been caught, but by Ding's merge rather than here
  - fix: export now uses the absence-of-baseline test, matching `stats.py` and `contribution.py`, which had it right all along
  - the defect was found only because `ark check` failed and the failure was diagnosed rather than silenced. Worth stating plainly, since the tempting move was to weaken the check until it passed

- **The double-counting check was moved off the store and onto the shipped artifact**
  - `additions_not_double_counted` reported 1,322,365 offending after the rebase. Diagnosis first: all of them were backed by the `merged260727` marker, none by the original, and exactly 17,418 pairs had no baseline evidence at all. So the store was correct and the check encoded a single-baseline assumption
  - a store-side reformulation would have been a tautology, since after the export fix "is an addition" and "has no baseline evidence" are the same predicate. So the check now reads `output/netnew/*.txt` and asserts that no shipped domain carries baseline evidence for that year. It tests the thing Ding actually receives
  - the export directory is a parameter rather than a constant in the SQL, for the reason `export_all` already documents: a hardcoded path makes the test suite assert against the real deliverable. A missing export reports `[SKIP]` with a reason, because an empty `output/` must not be mistaken for a satisfied invariant
  - the new test immediately earned itself: the year regex originally scanned the whole path and matched `output/netnew/` only by luck, failing against a temp directory. Now anchored to `([0-9]{4})\.txt$`

- **Result of the rebase: 17,418 net-new pairs against `merged260727`**
  - 1996: 2,220 | 1997: 1,319 | 1998: 3,465 | 1999: 336 | 2000: 5,598 | 2001: 4,480
  - CDX contributed 12,890 year rows and RDAP 4,528, so the total reconciles to the two engines exactly. Net-new **domains** is 0, which is correct and expected: every domain found so far is one the merged baseline now knows, and the additions are years gained on domains already held. That is what the sandwich-gap strategy is for
  - roughly one day of crawling, already above the 10,000-addition threshold, so the round cannot be claimed as approaching completeness
  - candidate lists regenerated against the new picture: CDX 466,434 domains over 488,629 gap pairs, RDAP 5,252,144 domains over 8,656,851 addressable years. Both were written to a `.new` path and `mv`-ed into place, since `mv` is atomic on one filesystem and the collectors were still dispatching; a batch that read a half-written list would have skipped real targets silently

## Definition: the two verification engines and how they work together

Both engines turn an undated or partially dated domain into per-year evidence, and both follow the
same collect-then-interpret shape, but they answer different questions and are therefore given
different populations. Neither writes to the store while collecting.

**The pipeline, per engine**

| | IA CDX | RDAP |
|---|---|---|
| Select | `ark gaps` -> `sandwich_gap_domains` | `ark gaps --creation` -> `creation_addressable_domains` |
| Population | bracketed: held Y-1 **and** Y+1, missing Y | any in-window year missing **adjacent** to a held one |
| Size | 470,614 domains | 5,256,528 domains |
| Ordering | thinnest gap year first, then `hash(domain)` | most missing years first, then `hash(domain)` |
| Collect | `ark cdx` -> `cdx.lookup_years` | `ark rdap` -> `rdap.lookup` |
| Journal | `data/raw/cdx/cdx_<UTC>.jsonl.gz` | `data/raw/rdap/rdap_<UTC>.jsonl.gz` |
| Interpret | `ark ingest cdx_snapshot` -> `cdx.evidence_years` | `ark ingest rdap_snapshot` -> `rdap.attested_years` |
| Evidence type | `cdx_timestamp` | `whois_creation` |
| Years per answer | **all six**, whichever have captures | **exactly one**, the creation year |

**Why the populations differ.** The engines are not interchangeable. A capture answers any year, so
CDX is asked about domains whose missing year is bracketed and therefore near-certain to have
existed. A creation date answers one year only, so RDAP is asked about domains where some missing
year could plausibly BE the creation year. Handing RDAP a "was this alive in 1999?" question it
structurally cannot answer is the waste this split avoids.

**The pools are nested, not disjoint.** Every bracketed gap is by definition adjacent-and-missing,
so the CDX pool sits entirely inside the RDAP pool (measured: 470,467 of 470,614, the small
shortfall being ingests that landed after the CDX list was written). RDAP adds 4,786,061 domains
CDX never sees. **The overlap is deliberate and is not waste**: the two engines ask different
questions about the same domain, and where both confirm the same (domain, year), `assign_year` keeps
the first assignment while the second evidence row is still stored. That is corroboration from two
genuinely independent provenances, which is what the project is otherwise weak on, since most
existing corroboration traces back to the Internet Archive on both sides.

**No shared queue, and none is needed at this scale.** Each engine skips only what its own journals
have answered. The SQLite work queue exists but is used solely by the older `ark verify`. Since a
night's run reaches under 1% of either pool, coordination would cost more than the duplication it
saves.

**The unit of work is the domain, not the (domain, year) pair.** One CDX query returns every year;
one RDAP query returns one date. Nothing tracks per-pair attempts, which is why the selectors encode
"which domains are worth asking about" rather than "which pairs remain unproven".

**Unconfirmed is handled by reason, not uniformly.** This distinction is load-bearing:

- **A definitive negative is final.** CDX returning HTTP 200 with no in-window years means the
  archive holds nothing for that domain in 1996-2001, and its index for those years does not change,
  so the domain is marked answered and never re-queried. RDAP returning 404 is the same kind of
  finding. Re-asking would burn a slot at ~1,000 queries/hour to receive the same answer.
- **A failure is not an answer.** A transport error or 5xx means the question never landed, so the
  domain stays eligible and the next batch picks it up, which is what makes the runs resumable.
  Recording failures as answers cost 2,727 domains once before it was caught.

**The store is written in exactly one place: `ark ingest <spec> <journal>`.** One journal becomes one
transaction (`bulk.py`): domain rows, evidence rows, year assignments, the `ingested_file` ledger row
and run metrics all commit together, and the audit CSV is written only afterwards. Collection writes
nothing, which is what lets an hours-long run proceed against a single-writer database. (`ark gaps`,
`ark stats` and `ark check` each append one `run_metrics` row, so they take the write lock, but only
for an instant.)

**Operational rule: never ingest a journal that is still being written.** The ledger stores the
file's sha256 and the loader raises on a mismatch rather than re-reading it, so ingesting a
half-written journal ledgers it at a partial hash; once the collector appends more, that file can
never be ingested again and its remaining records become silently unreachable. Ingest completed
journals only, meaning everything except the newest file in each directory while a run is live.

**Rates, measured 2026-07-25/26.** CDX ~1,000 answered domains/hour at 1.15 net-new pairs per
domain (~1,150 pairs/hour); RDAP ~2,800 domains/hour at ~0.15 (~420 pairs/hour). Run concurrently
they reach ~1,555 pairs/hour, because they are network-bound against different services.

## Definition: what counts as a valid domain

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
| `prior_reused` | The provided baseline already lists this (domain, year); reused read-only per III.1 | n/a (baseline negatives are never generated) | Master; **excluded from the scored metric** (it is the baseline, not net-new) |
| `cdx_timestamp` | A web-archive CDX capture (IA, Arquivo.pt, ...; the `source` names which) with an in-year 14-digit timestamp and HTTP 200 for the domain or a subdomain (`*.domain`) proves it served content that year | Deterministic empty CDX answers for all six year windows: IA never archived it in-window (not proof of non-existence, so it stays a candidate) | Master; the gold standard every candidate is verified against |
| `artifact_listing` | The domain is a line in a **dated data file** whose own provenance fixes the year (ISC survey list = survey date; ODP RDF dump = generation stamp) | Absence from a given dated file means only "not in that file", weaker than a CDX negative | Master (direct, §VII "dated index files"); ISC/ODP semantics flagged for Ding's confirmation in the interim email |
| `link_source` | From a UKWA host link-graph row `year\|source\|target`, the **source** host was crawled (HTTP 200) that year to produce the link | n/a per-domain (the graph is precomputed, not queried) | Master (brief lists UKWA host/link graphs among its index sources, §V) |
| `link_target` | From the same row, the **target** host was merely linked-to; this does **not** prove it existed or was active (dead links, typos, later registration are common) | n/a | **Candidate-only**; reaches masters only after per-domain verification (§IV/§VII route link-discovered hosts to the validation queue) |
| `dated_directory` | The domain is an editorial **entry** on a directory / yellow-page / portal page captured by a web archive on a known date | Absence from a page means only "not listed there", weak | Master (direct; brief blesses this route without further CDX validation, §IV/§VII) |
| `whois_creation` *(active)* | A WHOIS/RDAP creation date establishes existence no later than that date, supporting the **creation year only** (III.6); later years need their own evidence, never forward-filled | A missing/blocked WHOIS record is not evidence of anything | Master for the creation year only. This original reading was briefly widened to a registration interval for AFNIC and RDAP (2026-07-24), then restored for RDAP on 2026-07-25; AFNIC still runs on the interval reading, see the decision log |

Gray zone recorded for the ingester: on a `dated_directory` page, only curated **entries** count as `dated_directory`; incidental outbound links from the same page (nav bars, ads, reciprocal-link footers) are `link_target`-grade candidates. Drawing that line lives in the per-source parser.


## 2026-08-01 (phase 3: the English-website standard)

Feedback v3 section 6 imposes a new admission rule: a domain enters an annual file only if it belongs to an English-language website, or one where English is more than 50% of reliably classified body text, judged **at website level from archived page body text** and explicitly not from the domain spelling or the TLD. This is an admission criterion, not a post-hoc filter, so until a language pipeline existed the next submission had zero admissible additions regardless of how many pairs the engines collected. Ding also writes that his own language table is "a provisional aggregate estimate ... using a TLD-stratified Common Crawl 2024-10 page-language prior and is not a per-domain historical-language verification", and that future reports "must replace the provisional estimate with archived-content evidence". That is the deliverable this session builds.

- **Language is not evidence, so it is a new table rather than a new evidence type**
  - every existing `evidence_type` answers "did this domain exist in this year". A language verdict answers "what was this website in this year". The two are orthogonal: a domain can be perfectly evidenced and still inadmissible, and an inadmissible domain has lost none of its evidence
  - adding an eighth `evidence_type` would have put a non-existence claim inside a taxonomy that `MASTER_TYPES`, the schema CHECK constraint and four integrity checks all read as "proof this existed". `assign_year` would then have had to special-case it, which is the kind of exception that quietly becomes the rule
  - so: `domain_language (domain, assigned_year, verdict, english_share, samples, top_other, evidence_urls)`, keyed on the same pair as `domain_year`. Verdicts are `english`, `other`, `undetermined`
  - `evidence_urls` stores the exact snapshot URLs that were read. **That column is the entire difference between this and a TLD prior**: a reviewer can refetch what was classified and recompute the verdict. Ding asked for archived-content evidence, and a verdict nobody can check is not evidence

- **Two thirds of the additions can be classified at all, and one third cannot. Measured, not assumed**
  - per net-new (domain, year), does any `cdx_timestamp` evidence exist for that exact pair? If yes the archive provably holds an in-year capture and there is body text to read; if no, the pair rests on a registry creation date or a DNS survey line and there may be nothing at all
  - result: **21,825 of 32,698 (66.7%) are capture-backed**. By year: 1996 0.4%, 1997 0.0%, 1998 86.5%, 1999 5.9%, 2000 93.5%, 2001 96.5%
  - this is a hard ceiling on the admissible set before language is even considered, and it is not something more crawling fixes: the Internet Archive did not capture those sites in those years

- **The planned year priority was exactly backwards, and a calibration run proved it before the code shipped**
  - the plan said to classify 1996 and 1997 first, because feedback section 5 puts both under 10,000 additions and therefore closest to the completeness threshold. Sound about completeness, wrong about this engine
  - the first calibration run spent its whole budget on 1996 and returned 74 answers, **every one `undetermined` with zero captures found**. Cross-checked against the measurement above (1996 is 0.4% capture-backed) and against four of those domains re-queried by hand on a healthy connection, which returned genuine HTTP 200 with zero rows. The engine was right; the priority was wrong
  - `write_lang_targets` now orders capture-backed pairs first, then by year volume within that group. Requests against the archive are the scarce resource and they go where a verdict can change the admitted set. The completeness argument for 1996 and 1997 has not gone away; it simply cannot be served by page-text classification

- **The archive refused this project within four minutes, and the governor could not see it**
  - the first design sent up to 4 requests per pair (1 CDX query plus 3 snapshot fetches) at 4 workers with a 0.05 s floor. That is an order of magnitude more traffic than the CDX engine's sustained ~1,000 requests/hour. After roughly 400 requests `web.archive.org` began refusing TCP connections while ping and DNS stayed healthy. Third refusal in this project's history
  - the real defect was not the pace but the blindness. `RateGovernor` backs off on 429, 503 and 504. **A refused connection is status 0, which was not a throttle signal**, so the run kept dialling at full speed at exactly the moment it should have stopped. Silence was being read as success
  - two fixes. Status 0 now backs the governor off like an explicit 429. And `ark lang` carries a circuit breaker: 25 consecutive failures ends the batch, because an unbroken run of failures is not bad luck, it is the archive declining the traffic, and continuing turns a temporary refusal into a durable one. Nothing is lost, since an unanswered pair was never settled
  - `--min-delay` is now an explicit option rather than an inherited default. For an engine whose unit of work costs three requests, the floor is what bounds the load, not the worker count

- **Classifier decisions, each of which changes the measured English share**
  - **`charset_normalizer` over raw bytes, never UTF-8 over text.** Pages of this period are frequently latin-1, Shift-JIS or GB2312 with no declared charset. Decoding those as UTF-8 produces mojibake, mojibake classifies as undetermined, and undetermined pages leave the denominator, so the error would have **raised** the measured English share. This is why the module carries its own bytes fetcher instead of reusing `cdx.py`'s, whose fetcher decodes with `errors="replace"` and destroys the evidence before it is seen
  - **`py3langid`**: pure Python, no model download, deterministic, and with `norm_probs=True` it returns a real probability so a confidence threshold means something. `langdetect` is non-deterministic without a seed, which would make a verdict unreproducible
  - **under 200 characters of stripped text is "not reliably classified"** and leaves the denominator entirely. Under-construction notices, image-only splash pages and framesets are everywhere in this period, and identifying a language from a dozen words is noise presented as a measurement
  - **under 0.50 confidence is excluded rather than counted as non-English.** Section 6 puts low-confidence cases outside the annual files. Counting them as non-English instead would drag genuinely English sites out, which is a different error from the one the rule is guarding against
  - **captures are weighted by classified text length**, so a substantial English page outweighs a one-line non-English redirect notice instead of each counting once
  - **strictly greater than 0.50 admits**, so an exact half fails, per the wording "more than 50%"
  - **extracted text is joined across tag boundaries with a space.** Concatenating `<p>Test</p><p>Hello</p>` into `TestHello` invents n-grams the classifier reads as evidence of another language. Found by a test, not by reading the code
  - validated live before the refusal: `bbc.co.uk` 1999 returns `english` at share 1.0 from three distinct sampled pages, `lemonde.fr` 1999 returns `other` at share 0.0 with top other `fr`

- **`unclassified` is reported separately from `undetermined`**
  - a pair the engine has not reached yet is not the same claim as one it judged and could not resolve. Collapsing them would overstate how much of the list has actually been read, and section 6.1 is a reporting requirement, so an inflated denominator there is a misstatement to the reviewer

- **`init_db` split the schema on `;` including semicolons inside comments**
  - a semicolon in a new `--` comment cut a `CREATE TABLE` in half and failed with a parser error pointing at prose. Comment lines are now stripped before the split, which keeps the explanation in the source and out of the executed SQL
  - minor, but it is the second time this session that a defect surfaced only because a test ran the real code path rather than a description of it

- **`domain_language` is in the provenance export, and optional on load**
  - the English-verified annual files must rebuild in tier 2 like everything else, so the table is exported to Parquet with the rest of the evidence graph
  - it is optional on **load**, because an export written before the English standard existed has no such file, and a reviewer holding the earlier delivery archive must not meet a `FileNotFoundError`. A missing file creates the table empty rather than skipping it, so everything downstream can query it unconditionally

## 2026-08-01 (phase 3, later: Usenet as a dated source, and three sources measured)

Feedback section 4 asks for broader sources and for previously unavailable ones to be revisited. Two research sweeps ran against those families. **Every headline number they returned was re-measured against the store before anything was ingested, and two of the three did not survive that.** The method turned out to matter more than any individual result, so it is recorded first.

- **Estimates in this space are unreliable by one to two orders of magnitude, so nothing is ingested on an estimate**
  - the NYPW first-capture index was estimated at 27,276 net-new domains and measured at **53**. The estimate compared NYPW's *registered domains* against *raw hostname lines* from the *phase-1* baseline: a units error and a stale-baseline error, both of which inflate. Measured against the store, 2,354,914 in-window domains of which all but 53 are already held, a 99.998% overlap. That is exactly what a 1-in-6000 sample of the Internet Archive's own CDX should look like against a baseline already drawn from it
  - a separate vein was estimated at 1,000 to 5,000 net-new domains and measured at 5
  - the measurement scripts are committed (`measure_nypw_yield.py`, `measure_usenet_yield.py`) so every figure can be re-derived rather than believed. Two minutes of measurement avoided a 19.35 GB download

- **Usenet announcement archives adopted: the date is intrinsic to the artifact**
  - Giganews donated its Usenet archive to the Internet Archive. Announcement and commerce groups carry a posting date beside the URLs in each message, so the year comes from the artifact rather than from a crawl of the site
  - that is the specific gap the capture-backed measurement exposed. The 1996 and 1997 additions are 0.4% and 0.0% capture-backed, so the archive holds nothing to verify against; a dated post does not need the site to have been crawled at all
  - measured across eight groups of 302 shortlisted: net-new pairs **32,698 to 67,394**, and the gains land in the thin years. 1999 goes 696 to 5,098 and 1997 goes 3,534 to 13,820, against 2001 which moves 7,743 to 8,880. That distribution is the argument for the source, not a coincidence
  - **the Message-ID is the evidence value.** Usenet message IDs are globally unique by design, which makes them exactly the "opaque record identifier" the integrity checks already expect from a `dated_directory` row: a reviewer can name the precise post behind any year assignment

- **The admission rule: corroboration, applied per name, not per source**
  - the post date is trustworthy and the URL beside it is human-typed. 35.4% of never-before-seen names are within a single edit of a name the store already holds, and the corpus visibly contains `weddinqnetwork.com` and `dmjbuisness.co.uk`. Admitting those would put invented domains into an annual file, which is the one failure this project cannot afford
  - so the same split `expand.py` applies to archived directory pages. A domain **another source already places in an annual file** is real, and the only open question is the year, which the post answers: that half is `dated_directory`. A name appearing only in Usenet is `link_target` and goes to the candidate pool to earn its own evidence
  - **the test is "appears in `domain_year`", not "appears in `domain`"**. The latter includes the candidate pool, so a typo that an earlier round also recorded as a candidate would corroborate itself. That distinction is the whole guard
  - group purpose is **reported, not enforced**, and this is the one place a reviewer might reasonably disagree. The stricter alternative admits only moderated announcement groups. It was not taken because, once corroboration has established the domain is real, a URL in a dated public post is contemporaneous evidence of use whether the group was moderated or not. Every evidence row names its group, so a reviewer who disagrees can filter rather than reingest

- **Usenet is its own provenance lineage**
  - the corpus is a donation of posts with no common ancestor with any web crawl, so a pair confirmed by both Usenet and a Wayback capture is genuine cross-lineage corroboration rather than the Internet Archive agreeing with itself. Filing it under `internet_archive` because that is where the files are hosted would have quietly inflated the independent-corroboration figure, which is the one corroboration number worth quoting

- **Two parsing findings, both of which made a good source look barren**
  - the Giganews donation rewrote a large share of `Date:` headers as a bare `YYYY/MM/DD`, which `parsedate_to_datetime` rejects outright: **21,346 of 23,282 messages** in `comp.infosystems.www.announce`. Before that was handled the route measured 913 pairs and produced nothing at all before 2000; after it, 6,885 across all six years. A source can look exhausted purely because of a header format
  - **group size does not predict in-window content.** `alt.www.webmaster` is 170 MB and yielded one pair, being entirely 2006 to 2013. Out-of-window and unreadable dates are now counted separately, because they look identical under one counter and call for opposite responses: drop the source, or fix the parser
  - the moderated-group classifier first tested for an `.announce` suffix, which reports `news.announce.conferences` as an ordinary discussion group. It tests components now

- **Australian Web Archive: the endpoint recovered, the source still fails**
  - `webarchive.nla.gov.au/awa/cdx` still serves an anti-bot challenge, but **`web.archive.org.au/awa/cdx` answers normally** and returns a 1996 capture for `abc.net.au`. The rejection was stale, which is precisely what section 4 means by revisiting blocked sources, and the correction is worth keeping even though the source failed
  - the pool looked strong: 35,391 PANDORA registered domains, 29,595 of them in no annual file. A random **60-domain** sample returned 60 answers, zero transport failures and **zero in-window captures**. Rejected on a clean sample rather than on the 39-host probe that first suggested it

- **How much the Usenet post date can be trusted, measured against an independent source**
  - for the 217,113 Usenet-dated pairs whose domain the Internet Archive also evidences, the archive attests **the exact same year for 51.1%** and **a year within one for 88.7%**. An earlier 30-domain spot check suggested 47% and 77%, so the full measurement is kinder, but the shape holds
  - a disagreement is not automatically a Usenet error. The archive crawled sparsely in these years, so a site announced in 1997 and first captured in 1998 produces a mismatch in which the post is the better evidence. That is the whole reason this source reaches years the crawl cannot
  - but it bounds the claim honestly: for roughly half of these pairs it asserts a year the archive does not independently confirm, resting on a dated public post. Brief III.1 accepts "a dated directory page, a dated index file", so this is a legitimate reading, and it is weaker than a capture. It goes in the next report's limitations rather than being left for a reviewer to discover

- **The second sampled capture rarely changes the verdict, measured**
  - of 266 classified pairs, **156 got only one usable capture anyway**, because that is all the archive held for that domain in that year. Of the 110 that got two, only **3** came back mixed-language, meaning a share that is neither 0.0 nor 1.0. So the second sample could have altered at most about 1% of the answers
  - dropping to one sample would cut requests per pair from three to two, a 33% throughput gain against the binding constraint. **It was not taken.** The gain is 900 extra pairs out of 69,000, coverage moves from roughly 4% to 5%, and section 6 says "across the sampled captures" in the plural. Weakening the method for a rounding error in coverage is a bad trade
  - recorded because it is the right trade for someone running this to completion later, when the budget is hours rather than a night, and they should be able to make it knowingly rather than rediscover it

- **The first archived-content language measurement, and what it shows**
  - per year, of the additions the engine has reached and answered: 1998 **80.2% English**, 2000 **64.9%**, 2001 **61.6%**. Ding's TLD-stratified Common Crawl prior puts the *competitor's* 2000 and 2001 additions at 33.0% and 37.1%
  - those are different populations measured by different methods, so it is not a like-for-like comparison and must not be presented as one. It is still the difference between a number derived from what a TLD suggests in 2024 and one derived from what the site said in 2000, which is exactly the substitution the feedback asks future reports to make
  - coverage is the caveat and the reason `unclassified` is its own column: 799 of 87,458 additions reached. The claim is a measured rate per year with a stated sample size, not a census

- **The discovery cycle closed, and produced the first net-new DOMAINS**
  - net-new domains had been 0 for the whole project, because gap-filling adds years to domains the baseline already holds and the corroboration split does the same by construction
  - the chain now runs end to end: a Usenet post names a domain, it enters the candidate pool as `usenet_mention` with no year, `ark cdx` finds an in-window capture, and `ia_cdx_bulk` evidence promotes it into an annual file. `01ware.com`, `0800unlimited.com`, `080massage.com` and `090isp.co.uk` are the first four, all discovered by Usenet and confirmed by the archive
  - that is brief sections IV and VII working rather than being described: discover from a source without year labels, validate against a time-evidence service, feed back. Four is a small number, but it is the difference between a cycle that is documented and one that has been run
  - the input to it grew from 5,583 candidates to roughly 30,000, most of them Usenet-discovered, so the ceiling on this route is now set by how long the CDX engine runs rather than by how many names are known

- **The candidate-verification hit rate is 49%, which reframes what the Usenet route is worth**
  - the first completed batch: 337 Usenet-discovered candidates queried, **165 had an in-window archived capture (49%)**, 167 had none, 5 failed. Every one of the 165 became a net-new domain, because a candidate is by definition in no annual file
  - **net-new domains went 0 to 169**, the first movement in that metric in the project's life
  - at that rate the remaining candidates project to roughly 7,500 more. That is one 337-domain batch extrapolated 45-fold, so it is an order of magnitude and not a forecast, and the report should say so
  - the more interesting reading is what the 49% says about Usenet itself. Half of the names mentioned in dated posts and never seen by any other source do have archived captures, which means they were real sites rather than typos. It is independent support for the source that no amount of internal consistency checking could give
  - it also inverts the earlier priority. Usenet's *pairs* looked like the headline; its *candidates* are worth more, because a verified candidate is a new domain rather than a new year on a domain the baseline already had

- **Stopped the language engine at 06:03 to give the archive budget to candidate verification**
  - both engines share `web.archive.org` and the contention was measurable, not theoretical: `ark cdx` ran at 39 to 56 s/domain alongside `ark lang` and at **7.3 s/domain** once it had the service to itself, a six-fold recovery. Under contention its 250-domain batches were taking two hours, so their journals never landed and nothing was being ingested at all
  - the trade, stated plainly. `ark lang` had classified about 1,600 pairs and produced a measured English rate for three years. More of it improves the precision of a sample; it does not change any claim, because the deliverable feedback section 6 asks for is the **engine plus a measured rate**, and both exist, are tested and are documented
  - candidate verification moves a metric that had been **0 for the life of the project**. Measured hit rate across two batches: 165 of 337, then 74 of 122, so roughly half to three fifths of Usenet-discovered names have an in-window capture and become net-new domains
  - so: per request, `ark cdx` yields about 0.5 net-new domains and 0.8 net-new pairs, while `ark lang` yields one classified pair for three requests and adds neither. With a fixed request budget and three hours left, that is not a close call
  - **this is a scheduling decision, not a change of priority.** The English standard still gates admission and the engine still has 68,000 pairs to work through. It wants a long unattended stretch, which the next window can give it

## 2026-08-01, session close

Final position, all measured against `data/ark.duckdb` with the ten integrity checks passing:

    net-new (domain, year) pairs   32,698 -> 96,158   (+194%)
    net-new domains                     0 ->  1,065   (first movement in the project's life)
    candidate pool                  5,583 -> 41,289
    English-verified pairs                     689 across four years
    tests                             204 ->    253

- **The session's most useful habit was refusing to ingest anything on an estimate.** Three of five sources assessed were rejected, two after their headline numbers proved wrong by two orders of magnitude: NYPW at 27,276 estimated against 53 measured, and an ISP-directory vein at 1,000 to 5,000 estimated against 5. Both estimates came from comparing the wrong things (registered domains against raw hostname lines, a stale baseline against a current one), and both would have been believed without a measurement script. `measure_nypw_yield.py` and `measure_usenet_yield.py` are committed so the next assessment starts from a measurement rather than a claim
- **The Usenet finding generalises.** What made it work was not Usenet: it was that the date is *intrinsic to the artifact* rather than recovered from a crawl. That property is what reaches 1996 to 1999, where the archive's own coverage is thinnest and where every capture-based route necessarily fails. Mailing-list archives share the property and were assessed and rejected on population rather than structure; anything else with a dated record and a URL beside it deserves the same look
- **Discovery turned out to be cheaper than verification, which inverts the plan.** The candidate pool grew from 5,583 to 41,289 in one night while verification reached 1,730 of them. The bottleneck is no longer finding names, it is asking the archive about them, and that is bounded by a rate limit rather than by ingenuity

- **Three defects that put wrong domains in the English annual files, and why the verdicts were discarded**
  - an adversarial audit of the engine against live archived pages found three, each reproduced before being fixed:
    - **the index limit was the fetch count.** `classify_pair` passed `samples` as the CDX limit, so a run at `--samples 2` asked the index for two rows and reported `captures_found: 2` whatever the archive held. **869 of the 1,152 pairs with any capture, 75.4%, were censored this way.** `adguys.com` 2000 was stored `undetermined` on 2 rows while the same query at `limit=50` returns 33, including pages of 5,193 bytes
    - **captures were taken in index order**, which is URL-key order, so framesets and redirect stubs dominated the sample. The index reports each record's stored length, so the largest pages can now be chosen without spending a fetch
    - **placeholder pages were admitted as English websites.** A registrar parking page is fluent English, so the classifier was confident and wrong. `ajpca.com` served "ajpca.com currently has no web site", scored `english` at confidence 1.000, and reached `output/netnew_english/2000.txt`. A domain that provably had no site, admitted under a rule about websites. `alpinvest.com` scored `english` 1.0 on a Netscape-frames notice while its other capture was 2,110 characters of Dutch
  - verified live on those three pairs: `adguys.com` undetermined to **english** on 33 captures, `ajpca.com` english to **undetermined**, `alpinvest.com` english to **other** on 8,484 characters. One rescued pair and two false admissions removed
  - **the 1,164 verdicts collected before the fix were discarded rather than shipped.** They are known to contain false admissions of both kinds, and an English annual file whose contents cannot be trusted is worse than a shorter one. The journals are preserved under `data/raw/lang/superseded/`, so every discarded verdict is reproducible and the decision is auditable rather than a deletion
  - coverage went from 1,164 verdicts to zero and is rebuilding. That is the right direction: this project's whole claim is that a verdict is checkable, and a checkable verdict that is wrong is worse than none
  - **a test lesson worth more than the fix.** The first version of the limit test passed against the broken code, because the fake fetcher answered the same rows whatever limit it was given. A test that cannot observe the thing it asserts on is not a test. It records the requested URL now

## 2026-08-01 (phase 4: the English-verified set becomes the deliverable)

Ivo's instruction after reading feedback v3 again: from this round every annual
addition must be English-verified, all Internet Archive request budget goes to
that, and the deliverable ships two disjoint sets rather than one set with a
subset inside it. Non-CDX discovery continues as an explicitly secondary stream.

- **The open question to Ding is withdrawn, deliberately.** The previous plan
  ended with a question about admitting pairs whose evidence is a registry date
  rather than a capture. Ivo decided not to ask it: ship both sets and let
  the reviewer decide what to do with the second one. That is a cleaner contract
  than a negotiated exception and it removes a dependency on a reply
- **All CDX budget to the language engine, and this one is uncomfortable.**
  `ark cdx` candidate verification is what moved net-new domains off zero, at a
  62% hit rate, and it is stopped anyway. Both engines hit `web.archive.org` and
  the contention was measured, not assumed: 344 pairs/hour with CDX competing
  against **429 pairs/hour without it**, a 25% gain from doing less. The
  candidate pool does not decay, and English verification is the admission
  criterion for this round, so it cannot be deferred the way discovery can

- **"No capture in this year" was being claimed on a filtered question**
  - the capture query filters on `statuscode:200` and `mimetype:text/html`. A
    year holding only redirects, plain text, or records the archive labelled
    differently answers it empty, and the engine wrote that down as though the
    archive held nothing at all. **That is disqualifying a domain on an
    assumption**, which is the one thing this engine exists not to do
  - an empty filtered result now triggers one unfiltered index probe before
    anything is concluded. Nothing at all exists (`no_capture_in_year`),
    something exists but not as readable HTML (`no_readable_html_capture`), or
    the probe itself failed, in which case the pair stays unsettled and **no
    verdict is written**. It costs one cheap request on the ~23% of pairs that
    reach the branch
  - `cdx.year_probe_url` does the same job with a `statuscode:200` filter and is
    deliberately **not** reused. There a match only ever admits a pair, so a
    filtered question errs toward caution; here a match only ever withholds a
    rejection, so the same filter would point the caution the wrong way. Both
    functions now say so, because merging them would silently restore the defect

- **A rejection with no reason is an assertion, so rejections now carry one**
  - `undetermined` was covering at least five different situations and a
    reviewer could not tell an under-construction page from a registrar parking
    page from a site that could not be read. Closed vocabulary, stored per pair:
    `no_capture_in_year`, `no_readable_html_capture`, `insufficient_text`,
    `non_site_text`, `low_confidence`, `other_language`,
    `mixed_below_threshold`
  - `other_language` and `mixed_below_threshold` are split because both fail and
    they fail differently. A reviewer weighing whether the 50% line sits in the
    right place needs to see how many pairs are near it rather than nowhere near
    it
  - added by migration, not by editing the schema alone: `CREATE TABLE IF NOT
    EXISTS` does nothing to a table that already exists, so a new column would
    have reached fresh stores only and silently skipped every real one

- **The deliverable is a partition now, not a set and a subset**
  - the old shape shipped `netnew/` with every addition and `netnew_english/`
    with a subset of those same pairs. The two overlapped, so a reviewer adding
    them double-counted. Now a pair is on exactly one side and the sides sum to
    the total
  - three statuses, and the third is the one that matters. `verified` means the
    archived text was read and was more than half English. `disqualified` means
    the archive was asked and answered and the pair failed, with a reason and a
    row in the register. **`unchecked` means the engine has not reached it, and
    makes no claim about its language or about whether a capture exists**
  - two integrity checks assert the partition against the shipped files rather
    than the README claiming it, and `verify.sh` re-checks it from inside the
    archive with no dependencies. Writing the third test found a real bug: an
    `english` verdict was being counted as a disqualification

- **The watchdog tests progress, not presence.** A batch that hangs on a socket
  leaves the supervisor alive and the journal frozen, which a PID check reports
  as healthy. The archive has refused this project three times, twice overnight,
  so the expensive failure mode is precisely the quiet one
- **Usenet group selection is ranked by expected yield, not by size.** Ordering
  the 19,233 available groups by size put dead vanity archives at the head of
  the queue. Announcement forums go first, commerce second, size breaks ties
  within a tier. And short tokens are matched as whole dot-separated components,
  because `talk.bizarre` contains "biz": the same trap a suffix test hit on
  `news.announce.conferences`

## 2026-08-01 (phase 4, later: the engine audited twice, ten defects, verdicts discarded again)

Two adversarial reviews of `language.py`, briefed on opposite failure modes: one
hunting pairs that could reach the English files wrongly, one hunting pairs that
could be wrongly excluded. Both found real defects, and the overlap between them
was the interesting part.

- **The archive can answer a replay with a different year, and the audit trail
  would have hidden it.** A 302 to the nearest capture in time, in any year,
  followed silently by urllib and reported as 200. Verified: a request for the
  1997 capture of `1697.com` returned the capture of 17 October 2000. Since
  `evidence_urls` recorded the URL *asked for*, a reviewer refetching it would
  get the same substitution and see agreement. **A provenance record that
  confirms its own error is worse than none**, so the fetcher now returns the
  served URL, out-of-year samples are dropped, and what is stored is what
  answered
- **The sampler was choosing things that are not the website.** Largest-record
  selection under `matchType=domain` finds third-party application chrome:
  `1stflatrate.com` was certified English for 2001 on an Ipswitch IMail login on
  port 8383, and 68 evidence URLs behind `english` verdicts pointed at cgi-bin,
  webmail, guestbooks or non-web ports. `robots.txt` is indexed as HTML 200 and
  is often longer than a small site's homepage, so two domains were admitted on
  a robots.txt alone
- **The placeholder test had a hole exactly where the money was.** It returned
  early above 1,000 characters, so a 1,060-character keyword link farm
  (`2000s.com` 2001, English at confidence 1.000) was admitted on 60 characters
  of margin. Three shapes of non-site need three shapes of test: unambiguous
  phrases at any length, weak phrases judged on the residual text once the
  phrase is removed (a 299-char plumber's page mentioning "under construction"
  against a 55-char stub: 282 residual against 38), and a structural test for
  the link-farm family, which contains no giveaway phrase at all
- **A truncated sample was settling verdicts.** 124 of 839 `english` verdicts had
  rested on a single page after the other fetch failed. Now a verdict on a
  truncated sample stays unsettled, and `samples` is a budget of usable reads
  rather than of attempts, so a pair whose largest captures are unreachable no
  longer settles while 38 candidates sit unread

- **The structural fix underneath all of them: nothing could re-judge a pair.**
  Any verdict at all removed it from the work list for good, so every scoring
  defect became permanent at the moment it produced output. That is why the same
  class of bug has now cost this project two rounds of discarded verdicts.
  Verdicts carry an engine version, only current-engine verdicts can reach an
  annual file, and a pair leaves the queue only when asking again could not
  change the answer. `no_capture_in_year` is the one undetermined that is final,
  because the archive's index for a past year does not grow
- **All 297 verdicts discarded, journals preserved.** Second time. The trade is
  the same and so is the answer: this route's whole claim is that a verdict is
  checkable, and a checkable verdict that is wrong is worse than none

- **1996 and 1997 get a measured minority share of the budget.** They hold 25,599
  additions and 48 capture-backed pairs, so a strict capture-backed queue leaves
  both at zero English forever. A 200-pair unfiltered probe measured **5.4% of
  1996 and 12.6% of 1997** with an in-year capture, 9.1% overall, against the 0%
  an earlier sample of pre-Usenet 1996 domains suggested. The population changed
  when Usenet brought in domains live enough for someone to post about them. One
  early-year pair per ten capture-backed ones: roughly 65 verdicts gained there
  against 320 elsewhere, and the arithmetic is in the code so the choice can be
  reversed on evidence
- **A review finding I did not act on.** Both agents suggested collecting `alt`
  attribute text, since image-heavy pages of this era kept their English there.
  Declined: `alt` text is frequently English boilerplate ("click here", "home")
  on non-English sites, so it would bias toward admission. The asymmetry decides
  it, as it did for the weak markers, just in the other direction: a false
  admission is a claim made to a reviewer, a false exclusion is a pair that
  stays retryable. Recorded as a limitation instead

## 2026-08-01 (phase 4, evening: concurrency is not the lever, measured a third time)

- **A controlled A/B on the language engine, with the decision rule fixed before
  the result.** Batch 1 ended with the governor at its configured floor after 94
  throttles, which suggested headroom, so the next batch ran at 3 workers and a
  1.2 s floor against the measured 367 pairs/hour at 2 workers and 1.5 s.

      2 workers / 1.5 s   367/hour and 381/hour   throttles 94   final_delay 1500ms
      3 workers / 1.2 s   364/hour                throttles 95   final_delay 1428ms

  **Three workers was slower.** Reverted immediately. What the governor sitting at
  its floor actually indicates is that the *pacing* is not the constraint; it says
  nothing about whether more parallel requests will be served, and they are not
- **This is the third independent measurement of the same thing** and it should
  end the question. The first pilot lost the archive entirely at 4 workers. The
  phase-2 server-versus-laptop comparison found the server no faster despite more
  cores, and slower on CDX. Now a batch-level A/B. The limit is what
  `web.archive.org` will serve a single client. **The lever for throughput is
  requests per verdict, not requests in flight**, and the cheapest remaining one
  is merging the filtered capture query with the unfiltered probe, worth about
  10%, which needs an `ENGINE_VERSION` bump and so waits for the next round
- **The English share is 62.3% across all completed batches, not the 64.5% of the
  first.** It ranges from about a half to two thirds by batch, because the queue
  interleaves early-year pairs that yield less. The report derives it from the
  store now rather than quoting one batch, which is the same discipline as every
  other figure: a single-batch rate presented as the rate is an estimate wearing
  a measurement's clothes

## 2026-08-01 (phase 4, close: the deliverable, and what three review rounds cost and bought)

- **Shipped 1,541 English-verified pairs of 151,949 additions, with 1,056
  exclusions documented per item.** The English figure is 1.0% of the total and
  that ratio is the honest headline: the standard was imposed three days ago and
  verification is bound by what `web.archive.org` will serve one client, measured
  at 367 pairs/hour against a backlog of two weeks
- **Three adversarial review rounds, and they earned their cost.** Two on the
  engine found ten defects, four of which had already put a wrong domain in a
  generated file. One on the report found twenty-five problems, of which the most
  serious was that its headline claimed 93 English verdicts against files that
  shipped empty. A fourth pass verified the fixes and found twelve more, including
  two different "measured" rates for one engine and an estimate carried forward as
  a measurement. **None of this was found by testing; all of it was found by
  reading adversarially with a brief.** The lesson to carry: a green test suite
  says the code does what it was written to do, not that what it was written to do
  is right
- **The most valuable single finding was a provenance failure, not a logic bug.**
  The archive answers a replay it cannot serve exactly with a capture from another
  year, and because the engine stored the URL it asked for rather than the one
  that answered, a reviewer re-checking a wrong verdict would have seen agreement.
  An audit trail that confirms its own error is worse than no audit trail, because
  it converts a detectable mistake into an undetectable one
- **The deliverable was verified from outside the repo before shipping.** Checksum,
  unpack, `verify.sh` with six PASS and no vacuous check, then the full tier-2
  rebuild from the shipped Parquet: twelve invariants pass and 25 of 25 result
  files return byte-identical. That test has now found two defects nothing else
  did, and it is the reason it is written into the handoff as mandatory

## 2026-08-02 (phase 4, revision: one author, one round, half the words)

- **The report is rewritten to Ivo's brief and the deliverable re-cut before
  tonight's submission.** The instruction (`ivo-new-instructions.md`, 2 August):
  one authorial voice with no first-person plural anywhere; sections that
  compared this round against the previous IA CDX position now compare against
  the merged260730 baseline in the shipped counting unit; the syntax-anomalous
  column left the language tables because it describes the spelling of a name
  and not the language of a site (stated in prose with its 9,329-entry file
  instead); section 6 reports only this round's additions; section 9 keeps what
  the audit changed and drops the narration of how it went; and the whole
  document was cut from 4,694 to about 3,400 template words with no figure or
  claim removed. Rule of thumb applied throughout: WHAT, not how
- **Rounds are counted the way Ding counts them.** No submission happened on 29
  July, so nothing may call that "our second round". The earlier position is
  "the initial gathering" wherever it appears, and the 32,698 pairs it
  contributed to merged260730 stay separated from this round's harvest, as
  feedback section 3 asks
- **The measured rate is now derived from the supervisor log, not typed.**
  `fill_report.py` reads every completed batch whose journal is still current
  and quotes pairs, minutes and batches beside the rate. The hand-typed 367 was
  already stale at 356 across eleven batches, which is the same lesson as every
  transcribed figure this project has had to correct: a number that is not
  derived drifts
- **The how-and-why moved out of the READMEs into `docs/documentation.md`.**
  Both READMEs kept the what: the repo README is the command sequence with
  expected outputs, the archive README is the contents table and the three
  checks. Design reasoning (evidence wall, journals, rate governance,
  ENGINE_VERSION, the partition, determinism tiers) lives in the one file whose
  job that is, at meta level only, nothing a docstring already says
- **`just reproduce` gained the steps this round added.** The journals stage now
  replays Usenet, Tucows and the language verdicts, and the deliver stage runs
  `lang-report` after `export`. Before this, the recipe the README points tier-3
  readers at rebuilt the previous round's result and stopped
- **The re-cut archive was blind-verified before being called done.** From a
  directory unrelated to the repo: sidecar checksum, unpack, verify.sh six PASS
  (2,402 + 149,547 = 151,949, no overlap, 1,686 rejections over 6 reasons),
  tier-2 rebuild ALL PASS, and all 26 README comparisons byte-identical. 624 MB,
  381 files. The projection window is now computed from the watchdog's own
  deadline epoch at fill time instead of a hardcoded 48 hours, and the email
  quotes the size the English set reaches by Monday 12:00 UTC, current count
  included
- **Report shortened again on Ivo's review, sections merged.** The engine, the
  throughput, the two sets and the audit were four sections and are now one,
  and the lowest-value details went entirely (the Usenet header-format finding,
  the group-size note, the PANDORA endpoint correction, the estimate-error
  anatomy; all still in sources.md, which ships). 3,035 filled words against
  5,542 shipped yesterday. Feedback-document references now read "your section
  N" so the renumbered report's own sections cannot be confused with them
- **Final deliverable cut at 2,614 English of 151,949**, sha256
  0e7dd6018bf607d27f82f2ed91b5e564939c4e709113d16e09bcb977a247a051, 624 MB, 382
  files. Blind-verified from an unrelated directory: six verify.sh PASS with no
  vacuous check, tier-2 ALL PASS, 26 of 26 comparisons byte-identical, no
  unfilled tokens, no first-person plural in report.md, README.md or sources.md.
  The clean-tree guard fired twice during assembly, both times correctly: the
  engine kept verifying while the documents were being refilled, so the refill
  changed figures the committed copy did not have yet

## 2026-08-03 (phase 4: an outage the design already covered)

- **A one-hour network outage cost 25 pairs of work and nothing else.** Circuit breaker, supervisor
  backoff and watchdog restart all fired in sequence without intervention. The load-bearing piece was
  `answered()`, which admits only status 200: the four outage journals hold 100 records over 25
  distinct pairs, every one status 0, so not one was marked settled. **The check that mattered was
  the one written after a previous engine failed exactly this way**, and the cheapest way to confirm
  it worked was to read the journals rather than trust the invariant
- **Restarting deterministically beat relying on a scheduled handoff.** The supervisor's own window
  still ended at the old deadline, and the watchdog would have restarted it there, but that handoff
  would have happened at 14:00 with nobody awake. Killing and restarting both now, while the result
  could be verified, converts an unattended dependency into a checked fact. The cost was five minutes
  of an in-flight batch, whose pairs are retryable by the same `answered()` rule
- **Draining before restarting is not optional.** The supervisor's bash exited immediately but
  `ark lang` took ~40 s to finish its in-flight requests. Starting the replacement during that window
  would have put two engines on `web.archive.org`, which is the one thing this project has been
  careful never to do
- **A watchdog that measures progress must be able to see progress.** The stall
  test reads journal bytes, but the journal writer never flushes and gzip emits
  nothing until zlib fills a block. That is invisible at normal speed, where the
  first block lands inside the 10-minute window, and fatal at low speed, where a
  healthy batch would be killed every 10 minutes forever. Raised the interval to
  1800 s as the unattended mitigation; the correct fix is flushing per record so
  the metric means what the design says it means. **The bug was not in the
  watchdog's logic but in its assumption about the thing it observes**, which is
  the failure mode a liveness check is supposed to avoid and this one inherited

## 2026-08-03 (phase 4: engine extended to end of week, and one report claim found imprecise)

- **8,277 English-verified pairs, 3.2x the 2,614 shipped on 2 August**, over 6,040
  unique domains, with 6,094 rejections documented per item. The archive recovered
  from the overnight slowdown: batches are back to ~73 min for 400 pairs, about
  328 pairs/hour, of which **51% come back English** rather than the 58.8% quoted
  in the submitted report. The share is falling because the queue has worked
  through the capture-backed head and is now reaching thinner years, which is the
  expected shape and worth stating in the follow-up rather than leaving to be noticed
- **Run extended to Sunday 9 August 12:00 UTC** on Ivo's instruction ("keep this
  running until the end of the week"). Read as through the weekend rather than
  Friday, because over-running costs nothing while under-running loses days
- **A claim in the shipped report is imprecise, and measuring it proved it.** The
  report says a pair leaves the work queue "only when asking again could not
  change the answer", with `no_capture_in_year` as the single final rejection. In
  fact `answered()` skips any journal record at status 200, so
  `insufficient_text`, `no_readable_html_capture`, `mixed_below_threshold` and
  `non_site_text` are final too within an engine version: **0 of 14,371 answered
  pairs has ever been re-asked**. About 2,763 pairs are affected. Nothing shipped
  is wrong, and the cross-version path still works because superseded journals move
  to a subdirectory the skip set does not glob, but the sentence overstates
  within-version retryability. Fix is to make `answered()` consult the reason
  rather than the status; it belongs with the two other queued engine changes
- **The watchdog can see progress again, and the fix is one line.**
  `write_journal_line` now flushes per record, so the journal's size on disk
  tracks the run rather than lagging a zlib block behind it. Measured: the live
  journal reached 324 bytes **22 seconds** into a batch, against 12.7 minutes
  before, so the 600 s stall window is safe again and was restored. The test
  asserts the property with no explicit flush by the caller and **was confirmed to
  fail without the change**, because a test that passes either way tests nothing.
  Cost is a `Z_SYNC_FLUSH` per record against a monitor that cannot go blind
- **Ruff now excludes `feedback-*` and `legacy-data`.** Ding's new drop includes
  his own Python, and linting incoming material either fails the gate on someone
  else's file or invites reformatting it until it is no longer his

## 2026-08-03 (feedback v4: the scoring metric changed, and a privacy leak in the packaging)

- **Email drafts moved out of the tracked tree into git-ignored `private/`.** The
  2 August archive shipped `docs/email_draft_260802.md`, including its "notes for
  Ivo" section, because `package_delivery.sh` ships `git archive HEAD` and that
  means *every tracked file*. Nothing in it was deceptive, but private reasoning
  about how to present work to a reviewer reached that reviewer. **The lesson is
  about the packaging rule, not the draft: anything addressed to a person is
  correspondence, and correspondence does not belong in a repository that is
  archived wholesale.** `fill_report.py` now skips a missing template so a fresh
  clone still builds the report

## 2026-08-03 (the archive budget moves off English verification and onto the candidate pool)

- **The English engine is stopped and the CDX engine has its allowance.** Ivo's
  call, and the arithmetic backs it: verification re-reads captures for domains
  already in the master files, so it moves the *reported* English share and moves
  the equivalent-English score not at all. The score only rises when a name or a
  year is added. Final English figures, all ingested before the switch:
  **9,234 English-verified pairs over 6,803 unique domains**, 2,237 other, 4,576
  undetermined, 16,047 classified in total out of the 151,949 net-new pairs. The
  last batch published cleanly on SIGTERM (337 lines, 174 English), which is the
  `.part` rename doing its job
- **The candidate pool is the better buy and it is disjoint from the gap pool.**
  112,946 domains carried with no assigned year, of which 826 some journal has
  already answered, leaving **112,120 to query**. Mean English weight 0.6256
  against the gap pool's 0.562, and a hit adds a *name* rather than a year on a
  name already shipped. Worth **69,299 equivalent-English if every in-window name
  hits**, and the two populations overlap in exactly zero domains, so neither
  steals from the other
- **Ordering by English share alone put junk at the top, and a three-domain probe
  caught it.** The reviewer's model is built from CC-MAIN-2024-10, so it scores
  today's brand gTLDs near 100% English, and the pinned PSL accepts them as
  registrable. Parse noise out of Usenet headers and mail addresses
  (`stopspam.aol`, `redneck.nec`, `aaaa.aaa`, `uk.zero`) therefore sorted above
  every real target. The probe came back **3 of 3 with no capture**. Fix is a
  first sort key that is not a heuristic: a TLD that did not exist in the window
  cannot hold an in-window capture, so two-letter ccTLDs plus the original gTLDs
  plus the 2001 round rank first and the other **1,348 names go to the tail**,
  kept rather than deleted because the week will not reach them anyway
- **Era eligibility was not enough either, and the store held the signal that
  was.** Real ccTLDs cannot be filtered by era, so the two-letter coincidences
  survived and sorted first on a ~100% English share: `what.ev.er`,
  `bother.co.ck`, and a block of **241 forged `.mil` hostnames**
  (`dumicsamvfs.mil`, `zydagy.mil`, `pemtagon.mil`) out of Usenet headers. Watched
  live, the first 34 answers of the run were all from that head and returned
  **2 hits**. The separating measurement is dated domains per right-most label
  across the whole store: `.uk` 187,063, `.au` 78,952, `.nz` 24,365, `.gov` 1,017
  against `.mil` 69, `.gu` 69, `.vi` 67, `.bb` 64, `.ck` 54, `.gh` 53. A TLD
  contributing under a thousand dated domains to a 10.2M-pair store cannot move
  the score whichever way it goes, so its queue position is not worth an argument
  and it ranks behind every TLD that can. **2,591 names to the tail**, and the
  head is now `.au`, then `.uk`, `.edu`, `.ca`, `.org`, `.com`, `.net`. This does
  demote genuinely tiny ccTLDs along with the junk, correctly: the only question a
  queue answers is what to spend the next thousand requests on. Note the trap in
  the query, `domain.tld` holds the public suffix, so keying on it reports `.uk`
  as 28 rather than 187,063 and would have demoted the second-best TLD in the pool
- **The in-flight batch was left alone rather than restarted.** It read its 1,200
  targets from the old ordering at dispatch, of which 938 are `.au` and 262 the
  junk head, so 78% of it is work worth doing. Restarting to skip ~220 junk
  queries would save about 35 minutes of a 140-hour run and is not worth the
  churn; every later batch re-reads the list and gets the better order
- **Per-TLD hit rate does not re-rank anything, so share is the right sort key.**
  Measured over every CDX journal on disk: 26,625 answered records, **95.4%
  carrying an in-window capture**, and per-TLD rates sit in a 90-99% band against
  an English-share spread of 6.8% to 99%. That 95.4% is the *gap* pool's rate
  though, drawn from domains already known to exist, so it is an upper bound on
  what the candidate pool will do. The pool's own rate is measurable from the
  first batches and should be reported rather than assumed
- **One supervisor process, not the supervisor-plus-watchdog pair.** The pair
  existed because a supervisor blocked on a batch cannot notice the batch has
  hung. `scripts/supervise_cdx_pool.sh` backgrounds the batch and polls it
  instead, which gets the same stall detection with one PID for `caffeinate` to
  anchor to, and removes the failure mode where a watchdog restarts a supervisor
  using settings that have since been retuned. Stall window is 900 s because a
  single CDX query has been observed taking **183 seconds** to return, and the
  detector must clear the archive's slowest honest answer
- **Exhaustion is read from the batch's own output, never a tail of the shared
  log.** A killed batch writes no summary, so a shared tail would still be showing
  the previous batch's "nothing new to query" and the loop would stop about 90
  batches early. That is the silent-stop failure the whole script exists to
  prevent, so each dispatch truncates its own output file and the decision reads
  that
- **Pool journals are named `cdx_pool_<UTC>` and live in `data/raw/cdx/`
  alongside the gap runs.** A separate directory would have needed edits in six
  globs (README, justfile, `maintain_phase3.sh`, `maintain.sh`,
  `package_delivery.sh`, `sources.md`) and missing one means pool journals
  silently never ingest or never ship, which has happened before on this project.
  The `cdx_pool_` name matches every existing `cdx_*` glob, including the engine's
  own resume scan, so the two pools share a skip set (which is wanted: neither
  should re-ask what the other settled) while staying distinguishable by name.
  Proved end to end: the probe journal ingested as `cdx_snapshot` with the
  expected 3 lines and 0 evidence rows
- **Ceiling lowered from 5.0 s to 3.0 s.** On 29 July a throttle burst pinned a
  run at the 5 s ceiling and it managed 240 domains/hour for the rest of the
  batch. This workload is latency-bound, not pace-bound, so a low ceiling costs
  nothing and buys recovery. Running at `-n 1200 --workers 8` until Sunday
  9 August 12:00 UTC, with `caffeinate` anchored to the supervisor

## 2026-08-04 (the equivalent-English metric, verified against the reviewer's own calculator)

- **His worked example and his credited increment both reproduce exactly.** He
  asked to have the calculation double-checked independently, so it was done
  twice: once with his `equivalent_english_domains.py`, once with an
  implementation written from his README rather than his code. His three-domain
  example gives **1.2766**. Our increment gives **151,949 records and
  91,814.6880 equivalent-English**, identical to his figure to the last decimal.
  The merged 1996-2001 baseline after the merge measures **10,404,200 valid unique
  records and 5,622,984.6434**, and the two implementations agree on it to
  **0.0000**. So the metric is understood and applied the same way on both sides,
  which is what he was actually asking to confirm
- **His reported totals are the pre-merge baseline, not the post-merge one.**
  10,263,632 / 5,531,053.6089 plus his credited increment predicts 5,622,868.2969
  against the 5,622,984.6434 the merged files actually measure. The 116.35 gap is
  in his merge, and 1.659986% is exactly 91,814.688 / 5,531,053.6089, so nothing
  about the method is in dispute and it is not worth raising with him
- **11,568 records in the merged baseline score zero because his own validator
  rejects them, and none of them are ours.** All 151,949 of our net-new records
  pass. The rejected ones are embedded ports (`intermarket:81.net`), underscore
  labels (`server_http.italway.it`) and a few with no TLD at all
  (`chevrolet-online`). **7,348 of them normalise cleanly** by stripping the port
  and mapping `_` to `-`, and would then carry **3,785.5563 equivalent-English**,
  which is 4% of a whole round's increment sitting in text formatting. Offered to
  him as a normalised list rather than fixed unilaterally, because rewriting
  hostnames in someone else's baseline is his call and not ours
- **The metric confirms the pool ordering was the right call.** Mean weight of the
  increment is 0.6042 and of the whole baseline 0.5405, while the candidate pool
  ranked by TLD share is currently returning **0.98 equivalent-English per newly
  dated domain** in the `.uk` block. First 15 hours of the switched budget:
  16,186 records, **53.4% hit rate**, 5,894 newly dated domains, 9,135 pairs,
  **5,791 equivalent-English**
- **The stall detector in `supervise_cdx_pool.sh` was crying wolf, and the first
  estimate of what that cost was wrong by an order of magnitude.** Every completed
  batch logged `stalled: journal bytes N -> 0`, because `journal_bytes` stats the
  `.part` and a finishing batch renames it away, so a clean completion read as a
  frozen journal. First call was "no work lost, not urgent", which was true about
  the data and wrong about the throughput. **Measured from the log: the loop slept
  the whole 900 s stall window between checks, so a finished batch waited up to
  that long to be re-dispatched. Six restarts overnight show 5.2, 10.0, 13, 15.0
  and 15.8 idle minutes, averaging ~11 minutes against 50-90 minutes of work, so
  12-17% of throughput, roughly 6,900 equivalent-English over the remaining
  window.** The lesson is that "no data lost" is not the same as "not urgent", and
  the cost of a supervisor bug lives in the schedule, not in the store
- **Fix: noticing a finished batch and judging a stalled one are separate
  clocks.** Liveness is polled every `POLL=30 s`, journal growth is judged every
  `CHECK=900 s`, and the loop re-tests the PID after each sleep, because a dead
  process cannot be stalled. Both paths were tested against a fake batch before
  the swap, one that completes and one that stays alive writing nothing: the first
  reports `stalled=0` within one poll, the second is caught after two windows,
  which is the intended grace for a slow first block
- **Applied by rename, not in place, and the live supervisor was deliberately not
  restarted.** Editing a script bash is mid-execution corrupts its parse, because
  bash reads the file lazily by offset. So the edit went to a copy in the same
  directory and `mv` replaced the directory entry: inode 15314287 -> 15539531,
  while the running process keeps its descriptor on the old inode and finishes on
  the old logic. **The consequence to remember: the fix is on disk and NOT in
  effect. PID 18309 keeps logging false stalls and losing ~11 min per batch until
  someone restarts it**

## 2026-08-04 (a trap does not fire while bash sits in `sleep`)

- **The documented stop path was quietly broken, and the throughput fix repaired
  it as a side effect.** `kill <supervisor>` appeared to do nothing for 20 s and
  the process stayed up: bash defers a trapped signal until the currently running
  *foreign* command returns, and the old loop was inside `sleep 900`. So the
  advertised clean stop could hang for a quarter of an hour, and the only way to
  hurry it was to kill the `sleep` child so bash could reach its handler. The
  poll/stall split fixed this without being aimed at it, because the loop now
  sleeps in 30 s slices. **Measured on the fixed script: SIGTERM at 12:21:30,
  trap at 12:21:42, 12 seconds, and the in-flight journal published as a real
  `.jsonl.gz`.** One long sleep had been doing three jobs badly: pacing the stall
  check, noticing a finished batch, and bounding signal latency
- **Stopped deliberately at 12:22 so the laptop could be closed.** `caffeinate`
  holds off idle sleep, not clamshell sleep, so a lid close would have frozen the
  batch mid-socket. Stopping first means the journal publishes on our terms.
  Pool totals at the stop: **11,841 answered, 6,400 newly dated domains at a
  54.0% hit rate, 9,888 new pairs, 6,287 equivalent-English**, all 17 journals
  ingested and `ark check` ALL PASS

## 2026-08-04 (the queue is reordered by measured yield, and provenance beats the TLD table)

- **Ranking by English share alone was half right, and 14,686 real answers showed
  which half.** Share says what a hit is worth; it says nothing about whether
  there will be a hit, and the second factor varies far more. `.edu` scores 97.2%
  English and returned **5 hits in 1,709 queries**, `.gov` and `.mil` zero in 614,
  so roughly 2,300 queries and five hours went to blocks that returned almost
  nothing. Ordering is now by **expected equivalent-English per query, P(hit) x
  share**, with P(hit) measured from our own journals at the finest grain the
  sample supports: per (source, TLD) cell at >= 25 answers, then per source, then
  pool-wide
- **The predictor is provenance, which the store knew all along.**
  `ukwa_link_target` **90.0%** over 2,645 answers, `tucows_mention` **88.6%**,
  `usenet_mention` **37.2%** over 11,992. Links harvested from real archived pages
  hit; names merely *mentioned* in Usenet text mostly do not, and the `.edu` and
  `.mil` collapses are the forged-header family already met as `dumicsamvfs.mil`.
  Both factors are still needed, because source alone would rank a `.mil` Usenet
  name highly on its 99.8% share and only the (source, TLD) cell knows that block
  has never once hit. Effect: the first 10,000 queries now expect **0.351
  equivalent-English each against about 0.24 under the old order**, and 3,383
  names from the two 90% sources come out from behind 65,000 Usenet `.com` names
- **A subtle bug in the first attempt, caught because the output disagreed with a
  measurement taken an hour earlier.** Source was read from the pool query, but
  **a domain that hits is given a year by the ingest and therefore leaves the
  pool**, so the join saw only misses and reported the two sources at 1.5% and
  0.9% instead of 90.0% and 37.4%. A hit-rate estimate over a population that
  structurally excludes hits. Provenance for measurement is now asked separately,
  in chunks, over all domains rather than only unassigned ones. The lesson is that
  the sanity check was the earlier independent number, not the plausibility of the
  new one
- **The gap pool is now measurably the better target, and that reverses the
  2 August judgement.** Measured: **482,993 still queryable, 95.4% hit rate over
  26,625 answers, mean English weight 0.5618, so 0.536 equivalent-English per
  query and about 258,800 available in the block.** The remaining candidate pool
  averages 0.222 per query. The 2 August note called the candidate pool "the
  better buy" on weight alone (0.6256 against 0.562) without a hit rate for
  either, which was the same mistake as the TLD ranking one level up. Correct
  order of work is now: the ~3,400 high-yield candidate names first, then the gap
  pool, then the Usenet remainder. **Deferred on Ivo's instruction, not decided
  against**

## 2026-08-05 (the archive budget moves to the gap pool, and the 95.4% holds)

- **Switched at 00:55 on measured yield, not on the 2 August guess.** The
  candidate pool's high-value cells emptied out overnight exactly as the
  cell-level estimate predicted: equivalent-English per batch fell 415, 372, 383,
  348, 245, 249 and the batch in flight was tracking about 112. `ukwa_link_target`
  ended at **4,909 answered, 90.6% hit, 417 left**, `tucows_mention` at 536, 86.2%,
  210 left, leaving **93,336 `usenet_mention` names at 36.9% and roughly 0.22
  equivalent-English per query**. Total still reachable in the pool's measured
  cells was **343 equivalent-English over 1,167 queries**
- **The in-flight batch was killed rather than finished, and the arithmetic says
  that was right.** It had 637 queries left, worth about 127 equivalent-English on
  the pool against about 341 on the gap pool over the same 24 minutes. The 626
  records already written published on SIGTERM and ingested: 292 year rows over
  179 domains. Cost of the kill was the handful of in-flight HTTP requests
- **Gap list rebuilt before dispatch, and it grew.** 498,993 domains before,
  **505,169 domains and 527,915 gap pairs** after, because tonight's newly dated
  candidate-pool domains created 6,176 fresh bracketed gaps. Rebuilding rather
  than reusing the 2 August file is what picked those up
- **The main uncertainty is resolved: 98.2% on the unmeasured remainder.** The
  0.536 equivalent-English per query rested on a 95.4% hit rate measured over the
  gap pool's first 26,625 domains, which could have been a flattering head. First
  live batch on the fresh list: **55 hits in 56 answers, 259 years returned**. So
  the estimate was conservative rather than optimistic
- **One supervisor now drives either population, by environment variable.**
  `ARK_TARGETS` and `ARK_PREFIX`, defaulting to the candidate pool so every
  existing invocation and every documented `pgrep` still behaves. Journals are
  `cdx_gap_<UTC>` alongside `cdx_pool_<UTC>`, both inside the `cdx_*` glob that
  the ingest commands and the resume scan already use, so the shared skip set
  keeps either population from re-asking what the other settled. Two copies of a
  60-line script would have drifted apart within the week
- **A claim I wrote into `build_pool_candidates.py` this morning was false and is
  corrected.** It said the engine skips already-answered domains only after
  counting out `-n`, so a batch of 1,200 would query far fewer than 1,200 new
  names. `ark cdx` in fact appends only unanswered domains and stops when that
  list reaches `-n`, so no budget is ever wasted. Pre-filtering is still worth
  doing, but for different reasons: the rates and ordering are then computed over
  what is actually left, and the file stays readable

## 2026-08-05 (the gap pool is ordered by the metric, and the collector can be split across machines)

- **`ark gaps` now ranks by expected equivalent-English, and the thinnest-year
  order it replaced is kept as `--legacy-year-order`.** The key is the English
  share of the TLD times the number of bracketed years one query could fill. The
  hit rate is deliberately left out: measured 96.0%, 96.9%, 97.1% and 97.5% on
  consecutive batches, it is a near-constant factor over this population and
  scales every target equally, so it changes no ordering. Effect on the first
  50,000 queries, measured before the switch: **0.813 to 1.249 equivalent-English
  per query, about 54% better**. The old order was feeding 2,249 `.de` at 13.2%
  English, 833 `.dk` and 656 `.it` into the queue while 13,503 `.uk` at 98.1%
  waited behind them. New head of the first 50,000: **14,392 `.uk`, 13,498 `.com`,
  8,502 `.au`** against the old 31,555 `.com` plus the low-share ccTLDs
- **Why year priority was right once and is wrong now.** It predates the metric
  and served per-year completeness, which the SPEC asks for and the reviewer's
  tables show. It survives as the tiebreak inside an equal-value tier, so year
  balance still decides between two targets worth the same rather than overriding
  value. Worth remembering that the visible consequence of the old order was that
  1997 and 1999 received **zero** new pairs overnight: the queue never reached
  their tiers
- **The English-share table is vendored into `src/ark/data/tld_english_share.json`,
  and that was a latent bug, not tidiness.** `build_pool_candidates.py` read it
  from `feedback-phase-3/`, which is git-ignored since the packaging leak. A fresh
  clone, or a second machine collecting in parallel, would have loaded no weights
  and silently ranked every domain at zero. Pinned like the public suffix list and
  for the same reason. Verified after vendoring: his three-domain example gives
  **1.2766** exactly, over 1,306 TLDs with an English share
- **`--shards N --shard I` splits a list across machines, by content hash rather
  than by position.** Hash assignment needs no coordination, so slices stay
  disjoint and jointly complete however often either machine regenerates its list.
  Positional slicing would hand one machine the entire high-value head, which is
  where an equivalent-English ordering puts most of the score. `blake2b` not
  `hash()`: the built-in is salted per interpreter run, so two machines would
  disagree about the split, double-querying some domains and skipping others. That
  property is now pinned by a test that runs the hash in two subprocesses under
  different `PYTHONHASHSEED` values
- **Splitting is cheap only because collection was already separated from the
  store.** A remote node needs the repo, `uv` and its slice; it writes journals and
  never opens the database, so there is nothing to synchronise. The ledger keys on
  `(source name, file name)`, so distinct `ARK_PREFIX` values are all the isolation
  two nodes need. Had the SQLite work queue been the resume mechanism this would
  have required a shared queue and a protocol
- **The real constraint is the archive, not machines, and that bounds how much a
  VPS should be given.** Throttles are running 343-406 per batch with `failed_504`
  at ~74 and a steady single `failed_403`, so the service is limiting us without
  banning us, per source address. A second address is a second budget, which is the
  whole reason a split helps. It also means per-node concurrency should come *down*
  when a node is added: section VI requires treating a rate limit as a signal to
  adapt, and doubling load on a host that has already refused this project three
  times is only defensible if the total stays near what it has shown it tolerates.
  Recommended start for a second node is **4 workers, not 8**, with `failed_403`
  watched as the abort signal

## 2026-08-05 (source research: ordinary Usenet groups pay, and archive.org's books do not)

Full write-up in `docs/source_research_260805.md`. The decisions, and the numbers behind them:

- **The Usenet name filter is exhausted, and it was never the thing that mattered.** All 697
  archives under `data/raw/usenet/` are in `.processed` and the whole `biz.*` hierarchy is drained,
  which looked like the end of the route. It is not: the filter selected on names containing
  `announce`, `business`, `commerce`, so it had never once tried an ordinary discussion group. Eleven
  such groups measured (`uk.d-i-y`, `rec.food.recipes`, `comp.infosystems.www.misc` among them)
  return **8,819 net-new pairs from eight archives, mean equivalent-English weight 0.7389**. People
  quote URLs in ordinary conversation and every post carries its own date, so the announcement
  framing was an accident of how the first round happened to find the corpus. 18,536 groups remain
- **The next selector should be a hierarchy quota, not a token list.** Take `uk.*`, `aus.*` and
  `can.*` entire, 761 groups and 21.3 GB, because `.uk` is worth 0.9813 against 0.6321 for `.com` and
  those groups are small enough to finish. The 100 MB per-group cap bought breadth before there was
  evidence; there is evidence now, and five of the eighteen groups I asked for were skipped by it
- **The yield is late, 1999-2001, which is the opposite shape to `usenet_announce`.** Complementary
  rather than competing, but it does not help the years that are hardest to evidence
- **`uk.misc.mbox.zip` is 172.9 MB and parses to one record, and that is the group, not the parser.**
  Measured rather than assumed: 248,074 messages, 243,662 out of window, 4,411 unreadable dates, one
  in-window message left. The Giganews archive for that group is almost entirely 2003 onward, which
  is `alt.www.webmaster` again in a different hierarchy. Size does not predict in-window content, and
  the parser keeping `out_of_window` and `unreadable_date` on separate counters is what turned this
  from a suspected defect into a ten-minute diagnosis
- **Dated periodicals work, dated books do not, and the reason is licensing rather than OCR.** A 1997
  trade magazine printing `foo.com` is the same artifact shape as a dated directory page. Measured:
  Boardwatch **216 net-new pairs from 27 items** at mean weight 0.6716, `computermagazines` **116
  from 11 items** at 0.6323. But **57 of 60 sampled in-window books have no downloadable full text at
  all**, so the 632,683-item book collection, and the Internet Yellow Pages editions with it, are out
  of reach. The idea was right and the richest part of it is unavailable
- **Subject matter decides this source, not corpus size.** `magazine_rack` holds 34,279 in-window
  items and returns **0.4 net-new pairs per reachable item** against 10.5 for computing titles, a
  26-fold gap, because its in-window holdings are Amiga zines and laboratory newsletters that print
  no URLs. Recommending "archive.org texts" would have been recommending mostly nothing
- **Web rings, portal directory trees and award lists are one bet, and it was not placeable today.**
  All three are entirely `web.archive.org` workloads and both engines are on that host. The probe
  script is written and committed. The one thing measured before stopping is worth keeping:
  `nav.webring.yahoo.com` has **zero in-window captures**, so that hostname is wrong for the period
- **Three sources were asked for and two are being reported.** The third is not padded in. An
  unmeasured claim that reaches the client costs more than it gains, and this project has been wrong
  by two orders of magnitude twice already by trusting a plausible ranking over a measurement

## 2026-08-05 (the union is 147,271 net-new pairs, measured in one pass)

- **1,706 archives measured together: 147,271 net-new pairs over 85,721 net-new domains,
  98,066 equivalent-English at mean weight 0.6659.** Twenty-nine times the 5,000-pair acceptance
  floor, on bytes on disk, with no extrapolation in it. For scale, the whole of last round's Usenet
  work added 96,158 pairs and was the largest single addition the project has made
- **The figure is a floor, and finding that out was a near miss worth recording.** I first wrote it
  up as covering all 3,479 archives on disk. It does not: the shell expanded the glob when the
  measurement launched and the download was still running, so **1,773 archives arrived afterwards and
  have never been parsed**. Reconciling the log's line count against the directory listing is what
  caught it, and that reconciliation should be a habit, because attributing a number to the wrong
  population is the same class of error that made the NYPW estimate wrong by 500x
- **Measured as a union rather than summed, deliberately.** Each tranche had been differenced against
  the store separately, so adding 20,159 and 6,454 and the rest would double count every pair two
  tranches share. That is the units trap that made the NYPW estimate wrong by two orders of
  magnitude, and the cheapest defence against it is to re-measure the union in one pass rather than
  to reason about the overlap. An intermediate union over the first 574 archives gave 72,315 pairs,
  so the small-group tranche roughly doubled it
- **The headline overstates what can ship today, and the split says by how much.** 74,508 of the
  pairs are on domains another source already places in an annual file, so the post date settles the
  only open question and they enter as `usenet_announce` immediately, worth 48,821
  equivalent-English. The other 72,763 are on names seen only in Usenet and go to the candidate pool.
  Typo upper bound 35.8%, in line with the 35.4% of the previous round, which is why that rule stays
- **The uncorroborated half is deferred rather than lost.** The prior round measured a 62% hit rate
  when Usenet-discovered candidates were queried against the archive, so those 72,763 pairs are worth
  roughly 45,000 more once verified, which is work for the CDX engine after the gap run finishes
- **The mean weight fell from 0.7085 to 0.6659 as the corpus widened past `uk.*`, `aus.*` and
  `can.*`.** Expected, and the metric working: `.uk` is 0.9813 and `.com` 0.6321, so broadening away
  from British material converges on the `.com` weight. Still far above the 0.4 threshold at which
  volume would have to justify itself
- **Stopped cleanly on a network outage.** Downloads were killed with about 15,000 groups still
  unworked, and the four zero-byte `.tmp` partials the kill left behind were removed, because the
  fetcher's rename-on-success discipline is only a guarantee if interrupted partials are cleared




Third tranche, taken to test breadth rather than depth: the **smallest** unworked archives in `uk.*`,
`aus.*` and `can.*`, ascending by size.

- **116 archives, 174 MB, 6,454 net-new pairs, 4,647 equivalent-English at mean weight 0.7201.**
  That is **37.1 pairs per megabyte against 4.5** for the 28 large archives measured earlier, so the
  small groups are roughly eight times cheaper per pair
- **The mechanism is visible in the out-of-window share, 46% here against 76% there.** A small
  archive belongs to a group that died early, and a group that died early is one whose traffic falls
  inside the window. The large archives are large precisely because they ran on into the 2000s
- **This inverts the reasoning behind the 100 MB cap.** It was framed as deferring the big groups
  until there was evidence, which treated small groups as a compromise. They are the better
  material, so the download queue should run ascending by size and simply keep going
- **The two tranches were measured independently against the store, so their totals must not be
  added.** Some pairs are common to both; the union was not computed and is somewhat under 26,613.
  Saying 26,613 would be the same units error that made the NYPW estimate wrong
- **The obvious form of the in-window screen is broken, and measuring it caught that.** Reading the
  head of an mbox and dropping the group if the dates start after 2001 fails, because **the Giganews
  exports are not in chronological order**: `uk.finance` yields thousands of in-window pairs and
  reads as 2011-2013 over its first 2,000 messages. Striding across the whole archive fixes it, and
  the corrected screen scores `uk.transport` 0.0%, `uk.finance` 41.7% and `uk.misc` 0.0%, which
  matches their measured yields of zero, thousands and one record. `scripts/screen_usenet_archives.py`
- **What the screen honestly buys is less than I claimed.** Striding needs the archive downloaded and
  decompressed, so it prunes the ingest queue rather than the download queue. Given the size finding
  that matters less than it looked, because ascending-size ordering is a good enough download rule



Second half of the same session. The extrapolation above was the weakest thing in the report, so it
was replaced with a measurement.

- **28 groups, 20,159 net-new pairs, 14,266 equivalent-English, mean weight 0.7077.** Seventeen more
  archives were downloaded and `scripts/measure_usenet_decay.py` written to accumulate pairs in a
  fixed order and report, per batch of four, what is net-new against **both the store and every
  earlier batch**. That is the decay curve read directly instead of assumed
- **The cumulative curve fits `a * g^0.909`, so saturation has barely begun.** Against a store
  holding 8,812,701 assigned pairs, these groups keep finding names it does not have. Projecting the
  fit gives ~138,000 pairs at 200 groups and ~466,000 across all 761 groups of `uk.*`, `aus.*` and
  `can.*`. The earlier 50,000-to-150,000 band was not wrong so much as wrong-shaped: the answer sits
  at its upper end
- **The marginal column is bimodal, not noisy, and that is the actionable finding.** Per group it
  runs 989, 1386, 764, 314, 1041, 547, 0. A group whose archive covers the window yields about a
  thousand pairs and a group whose archive starts in 2003 yields nothing: the last batch of four
  contributed **exactly zero**. Across all 28 archives **4,023,027 of 5,283,482 messages are out of
  window**, so 76% of the bytes buy nothing
- **So the selector should gate on in-window date coverage, not on name or size.** Read the first few
  thousand messages of an archive and abandon the group if the `Date` headers start after 2001. Name
  filtering was the first round's rule and size capping the second; both are proxies for this
- **`uk.misc` was not a parser defect after all.** 248,074 messages, 243,662 out of window, 4,411
  unreadable dates, one in-window message. The group is late, exactly like the zero-yield batch, and
  the parser's separate counters for `out_of_window` and `unreadable_date` are what made that a
  ten-minute diagnosis. Corrected in the report, where I had called it a defect
- **The book half of the periodicals lead is now closed on a second measurement.**
  `folkscanomy_computer` was chosen specifically because it is not lending-restricted, and it still
  gave **2 net-new pairs from 40 items with 36 unreachable**. So the constraint is not only lending
  restriction, it is that in-window book scans largely carry no OCR text layer. Three collections
  tested, same answer
- **Web rings are not dead and my first pass was wrong about them.** `matchType=prefix` on
  `www.webring.org/*` returns zero captures; `matchType=domain` on `webring.org` returns in-window
  captures from 19961019, and `webring.com` from 19981212. The member lists were query strings off
  the site root, `?ring=railring;list`, so there is no path prefix to match. **A wrong CDX match type
  is indistinguishable from an absent source**, which is worth remembering the next time a probe
  returns a clean zero
- **Web rings then failed on the third pass, and the reason is the artifact rather than the access.**
  Sorting the CDX rows by `length` and taking the largest gives real pages: the `railring` list at
  20000422003921 is 14,154 bytes of genuine ring content. It **lists 20 member sites and contains 2
  member URLs.** Every member is linked through `go.webring.org/go?ring=X;id=N;go` and the visible
  text carries each site's title and description with no address at all, so the member domains are
  simply not in the page. Recovering them is one Wayback redirect per member, against pages holding
  about 20 members, which competes for the same IA budget as a gap engine already running at a 96%
  hit rate. **Rejected as a bulk source on that comparison**, not on the source in isolation.
  Sorting by `length` before judging a capture is the reusable half of this: the second pass called
  these stubs and they are not
- **Two more blocked payloads rechecked, both still blocked.** The Bibliotheca Alexandrina mirror of
  the Internet Archive (`web.archive.bibalex.org`) no longer resolves, which was the most promising
  non-IA route to early captures. `data.webarchive.org.uk` does not resolve either, a third distinct
  host tried for the UKWA bulk CDX. Zenodo's DMOZ holdings are 2018-2020 research derivatives

## 2026-08-06 (web.archive.org refuses connections, and the client could not see it)

Phase 4, overnight. The task was to improve CDX throughput by experiment. The
first experiment was void and the reason it was void is the finding.

- **Baseline, measured over 13 gap journals and 22.5 hours: 647 queries/hour and
  1,729 year-records/hour** on the local eight-worker engine. The number that
  matters is not the mean but the spread: per-batch yield ran from 202 to 3,871
  year-records/hour, a factor of 19. A mean over a distribution that wide is not
  a throughput figure, it is two different regimes averaged together, so the
  question became what puts a batch in the bad regime
- **A first probe looked fast and was actually failing.** Six extra workers
  alongside the running engine returned 93% transport failures at a flat ~3.5 s
  each. Fast because refused, not fast because efficient. Killed it inside two
  minutes. The lesson is narrow and worth keeping: **a latency figure means
  nothing until the success rate is next to it**
- **The refusals are web.archive.org's, not the local link's.** Eight requests
  each to four hosts, sequential: google.com 8/8, one.one.one.one 8/8,
  **archive.org 8/8, web.archive.org 2/8**. The failures gave up at a flat 3.3
  to 3.5 s with `time_connect=0.000`, so the TCP connect never completed, and the
  error was `OSError(50, 'Network is down')`. That error name is a red herring on
  macOS: the link was demonstrably up, since three other hosts including
  archive.org itself answered every time. Ruled out an IPv6 blackhole too, which
  was the first guess and would have been tidy: `web.archive.org` publishes no
  AAAA record at all, and forcing `curl -4` changed nothing
- **The client's response to a refusal made the refusal last longer.** In
  `_fetch_retrying`, `_THROTTLE_STATUSES` held only 429, 503 and 504, so a
  refused connection arrived as status 0, skipped the backoff entirely, and was
  retried up to four times at full pace. Those retries are themselves connection
  attempts. So the failure mode is self-reinforcing: concurrency slightly over
  the line produces refusals, refusals produce four times as many connection
  attempts, and the run holds itself in the penalty box until the batch ends.
  That is the mechanism behind the 19x spread, and it explains the worst batch
  observed, 978 transport failures out of 1,199 queries
- **Stopping the engine cleared it in under 90 seconds.** The host went from 2/8
  to answering every request. So the penalty is short-lived and forgiving, which
  is what makes pausing the right move rather than a costly one
- **A refused connection and a client timeout were the same status and want
  opposite handling.** Both arrived as 0. A refusal is evidence the pace is too
  high. A timeout is the server having accepted the question and failed to
  finish it, which is no evidence about pace at all, and asking again is close to
  pure waste because the server kills a heavily archived domain at a consistent
  ~60 s. They are now separated: `REFUSED = 0` backs the pace off and counts
  toward a breaker, `TIMED_OUT = -1` does neither and is asked exactly once
  instead of four times, saving up to three minutes of a worker per doomed domain
- **A breaker was added rather than only a slower pace.** Once the host has
  stopped taking connections, pacing does not help, because every queue position
  spent is a certain failure. Twenty-five consecutive refusals now push the
  governor's shared next-start time forward by 60 s, which holds the whole pool
  off rather than only the thread that saw the last refusal. Reusing `_next_at`
  meant no new machinery and no new lock
- **Seven tests added, 305 in the suite.** The one worth naming is
  `test_a_timeout_is_asked_once_and_does_not_slow_the_pace`, because the old code
  passed every existing test while doing the wrong thing four times in a row
- **Nothing was lost stopping the engine mid-batch.** The SIGTERM trap renamed
  the journal cleanly and its 1,118 answers are on disk and will not be
  re-queried, which is the `.part` design working as intended
- **Open, and being measured next: the 504s are a separate problem from the
  refusals.** At concurrency 1, on a quiet link, wildcard queries still returned
  504. `url=*.domain` forces a range scan over every subdomain, and the server
  gives up on the heavy ones. That is not a rate limit and backing off cannot fix
  it. The candidate answer is a cheaper query shape

## 2026-08-06 (the queue head was a clog of scans the server cannot finish)

- **The head of the unanswered queue was 100% domains earlier batches had already
  failed on.** Measured: of the first 200 unanswered domains in shard 0, 200 had
  a prior failure; of the first 1,200, 384 did, their last status either 504 (35)
  or a transport failure (349). The head was names like `warehouse.co.uk`,
  `vccs.edu` and `autotrader.co.za` on their fourth or fifth attempt. Since only
  an HTTP 200 marks a domain settled, and the engine always takes the first N
  unanswered in file order, these came back to the head of every batch forever.
  So roughly a third of every batch was being spent re-failing on the same names
- **This also invalidated my own first two experiments, which is the more useful
  lesson.** Both sampled "the first unanswered domains", believing that was the
  queue head the engine sees. It is, but it is also the hardest possible sample:
  a domain that answers leaves the population, so what accumulates at the front
  is exactly what cannot be answered. A frontier measurement over that sample
  read 0% served at every concurrency level and told me nothing about
  concurrency. **Sampling the survivors of a filter measures the filter, not the
  population**
- **`url=*.domain` matches every subdomain, so the server cannot stop early.**
  CDX returns rows ordered by URL key, so a wildcard has to walk the whole range
  before it can answer, and `collapse=timestamp:4` saves payload only. An exact
  host is ONE key, so its rows arrive in time order and collapse plus a small
  limit lets the server stop as soon as it has the years. That is a structural
  reason to expect the cheap shape to win, not a hope
- **Measured on `warehouse.co.uk`, five batches' worth of failure:** the wildcard
  gave 504 after 60.6 s and no years; apex plus www gave 200 in 20.5 s and four
  years; the six-probe per-year sweep gave 200 in 249.4 s and **the same four
  years**. So the cheap shape matched the expensive rescue at a twelfth of the
  cost, and `lookup_years_per_year` is not the right fallback after all
- **`lookup_years` now falls back to the hosts when the server gives up, and
  never otherwise.** A scan that answers is never second-guessed, so no recall is
  traded away on the healthy path. The doomed scan is also asked once instead of
  four times, since 504 now stops the retry loop instead of buying three more
  minutes of the same answer
- **Validated live rather than argued.** Restarted on the identical 8-worker,
  1,200-domain config so the code was the only variable. On the clogged head,
  which had been returning nothing: **121 records, 119 answered, 29 rescued by the
  fallback, 445 year-records, 2 failures.** Yield 1,670 year-records/hour against
  a 1,729 baseline, while still inside the clog and paying a failed 60 s scan for
  every rescue. The segment went from producing approximately zero to producing
  at the whole-run average
- **The recall cost of the fallback measured zero.** The ground truth was already
  on disk: 46,370 domains have a wildcard answer in the journals, so asking the
  hosts about a sample and diffing costs no second wildcard query. On 20 domains
  that both shapes answered, the year sets were identical 20 times out of 20,
  **0 of 64 year-records lost**. Small sample, but it bounds the risk of a change
  that only ever runs where the alternative was no answer at all
- **The 18.9% of answers that report no in-window capture are genuinely empty.**
  10,793 domains sit in that state and are settled forever, so it was worth
  checking. Of 14 sampled, the host query found years for 0, and dropping
  `filter=statuscode:200` found a year for 1. So the negative verdicts are close
  to right and there is no large recovery hiding there
- **A data-quality worry that turned out to be bounded.** That sample contained
  `nospamucdavis.edu`, `removenwu.edu` and `wwwultratech.net`, which are
  anti-spam-munged addresses rather than domains, and would explain empty answers
  neatly. Counted across the store: 2,093 dated domains match any such pattern,
  0.038%, and most of those matches are real names (`wwwshop.com`, `spamfree.org`,
  `removeme.org`). So the munged ones live in the candidate pool, not among dated
  records, and this is not worth building a filter for

## 2026-08-06 (two source agents, and what survived checking their work)

Two research agents ran on disjoint spaces, one on directories and periodicals,
one on non-IA web archives. Both reported honestly and both had a headline that
needed correcting.

- **The `matchType=host` finding is the night's biggest, and it verified.** The
  archives agent measured the host form at a 15.6x speed-up over the wildcard
  scan. Checked independently and by a different method, against the wildcard
  answers already sitting in our own journals rather than by re-querying: median
  **2.07 s against roughly 33 s**, and on every domain where both shapes answered
  the year sets were **identical**, 0 of 34 year-records lost. The agent's own
  independent count was 1 year lost in 49
- **`www.` comes free, which halves the cheap query.** IA canonicalises
  `http://www.abc.net.au/` and `http://abc.net.au/` onto the same SURT key prefix
  `au,net,abc)/`, so a host query on the apex already covers www. Verified by
  asking for `www.<domain>` explicitly and diffing: same year set every time.
  So the fallback built earlier tonight was doing two requests where one does,
  and `lookup_years_by_host` is now a single request
- **The ordering is therefore inverted: cheap query first, wildcard scan as the
  fallback.** Only an empty host answer falls through to the scan, because empty
  is the one case where a subdomain-only capture could be hiding. Kept switchable
  with `--wildcard-first` so an older run can be reproduced
- **The Australian Web Archive is a mirror of IA, not a second source, and the
  agent's "build this collector" ranking overstated it.** Its API is real and
  excellent: `web.archive.org.au/awa/cdx`, no key, median **0.98 s**, no throttling
  observed. But its in-window records live in files named
  `NLA-EXTRACTION-1996-2004-ARCS`, and `.arc.gz` is the Internet Archive's own
  container format, so the honest prior is that this is IA data the library
  obtained rather than a crawl of its own. Tested that prior two ways: on 30 `.au`
  domains where **our IA journal already says "no capture in window", AWA found
  years for 0**, and on 30 where IA did return years, AWA was **identical for 26,
  a subset for 3, a superset for 1, and held exactly 1 year IA did not**. So
  the verdict is: worth building as a **load-shedding route for `.au`**, which is
  1.7% of the queue but 87% of its first thousand under the equivalent-English
  ordering, and **never usable as independent corroboration**, because it is the
  same underlying crawl
- **`fl` and `collapse` are silently ignored by the AWA endpoint**, so the urlkey
  still leads every row and the timestamp is the SECOND field. Parsing it as the
  first returns a clean, confident zero, which is how this nearly got written off
  as an empty archive. Same shape of error as the `matchType` mistake recorded on
  2 August: **a wrong parameter and an absent source look identical**
- **Closed for good, with proof rather than a shrug:** the Memento aggregator was
  decommissioned by LANL in September 2025 and every service subdomain is NXDOMAIN;
  the UK Web Archive service is simply offline and says so on its front page, which
  means the 159-byte stub three earlier attempts read as an access problem *was*
  the outage page; Common Crawl's earliest crawl is 2008; `arquivo.pt` works but is
  `.pt`-only, 0 of 20 on `.com` and `.co.uk`, a ceiling of about 380 domains
- **The other agent's headline number is the extracted figure, not the admitted
  one, and the difference is 2.6x.** It found five signals in the 28 GB of Usenet
  already on disk that the parser never reads, and measured 25,710 net-new pairs
  and 16,555 equivalent-English over a 320-archive sample. But "net-new" there
  means "not already an admitted record", and a Usenet-only mention does not become
  a record: it waits in the candidate pool for corroboration. Of those 25,710 pairs
  only **9,991 are on domains the store already knows** and can enter at once,
  worth **6,343 equivalent-English**, with the other 15,719 going to the candidate
  pool. The store confirms the mechanism: 5,717,439 domains are known and only
  5,501,772 hold an admitted year, so 215,667 are already waiting that way
- **Even corrected it is the best-value lead open.** Scaling 6,343 by the agent's
  own measured saturation exponent of 0.911 over the remaining archives gives
  roughly **63,000 equivalent-English admitted, at zero network cost**, against the
  capture engine's projected 31,613 by 9 August. Two independent fits agreeing on
  that exponent, 0.911 from the new signals and 0.909 from the project's own
  earlier body-URL work, is the part that makes the projection worth trusting
- **The single cleanest piece of it is a hole in a regex.** `ark.usenet` requires
  `https?://`, so a bare `www.foo.com` written by a human is invisible, and in
  1996-1999 people wrote addresses that way constantly. That is the same kind of
  evidence as a linked URL, from the same dated artifact, and it measured 11,817
  net-new pairs on its own. The machine-written headers, `Message-ID` hosts,
  `NNTP-Posting-Host` and `Path:` hops, are a different kind of claim and are left
  for Ivo to rule on rather than switched on quietly
- **A useful negative that generalises.** HathiTrust's Extracted Features is open
  and domain tokens do survive OCR, but the net-new half of what it yields **is**
  the OCR-damaged half: `0fficemed.com`, `0rth04me.com`, `3enniferf8sffny.edu`.
  Real domains that appeared in print are already in the store, so what passes a
  "is this net-new?" test is disproportionately the corrupted. Worth applying to
  any print source before believing its projection

## 2026-08-06 (the cheap query is not one shape but three, and a wrong turn found it)

- **`matchType=host` is not the answer for a heavily archived domain, and
  believing it was cost a wrong turn.** Both the research agent's 1.29 s median
  and my own 2.07 s were measured on ORDINARY domains, because both samples were
  drawn from names the wildcard scan had already answered. Run against the actual
  clog it fails exactly as the wildcard does: `warehouse.co.uk`, `gigabyte.com`
  and `bbc.co.uk` each returned 504 after about 60 s. One host can still hold
  millions of rows. **A shape measured only on the easy cases is measured on the
  wrong population**, which is the same sampling error I made earlier tonight in
  the other direction
- **So there are three tiers, and each one exists for a failure the others
  measurably have.** `matchType=host` for the ordinary domain, about 2 s. The
  apex and www ROOT pages, single CDX keys, for the heavily archived one: same
  three domains answered in roughly 10 s each that way. The wildcard scan last,
  and only when tier 1 answered with NOTHING, because that is the one case where
  a subdomain-only capture could be hiding, and a domain with nothing on its own
  host is lightly archived enough for the scan to be cheap
- **A domain too big for one host is never sent to the wildcard.** The scan
  covers every subdomain, so it is strictly more work than the host match that
  just failed, and trying it would only buy another 60 s and another 504
- **Tier 1 gets a 15 s leash rather than the full 70 s.** A cheap query that is
  not cheap is by definition the wrong tier for that domain, and the tier answers
  at a p90 of 6.24 s, so the leash keeps essentially every real answer. Without
  it the ladder pays the server's own ~60 s timeout to learn a domain is heavy,
  on every heavy domain: measured 122 s end to end for `warehouse.co.uk` against
  an expected ~77 s with the leash
- **Measured live, same 8 workers and same 1,200-domain batch as the baseline, so
  the code is the only variable: 2,054 year-records/hour against the 1,729
  baseline, up 19%,** and that is while still inside the clog, where 25 of the
  first 55 answers came from the root-page tier and each one had paid a failed
  tier-1 query first. Queries/hour is lower, 509 against 647, which is the right
  trade: the clog domains cost two tiers but they are heavily archived, so they
  return captures in most years
- **The VPS journals were never brought home.** 1,569 records, 1,481 answered,
  **5,793 year-records worth 5,137.6 equivalent-English**, sitting on the VPS
  disk and absent from the store since it started. Rsynced; the maintain loop
  ingests them on its next pass. Worth a standing habit rather than a one-off,
  because a second machine's output is invisible to every measurement taken here
- **The bare-www Usenet signal is real but roughly a quarter of the size the
  agent's table suggests, and the difference is in what "net-new" was differenced
  against.** Their per-signal rows difference against admitted records only, so
  H4's 11,817 still contains pairs the shipped signal already sees; only their
  "union minus B0" row subtracts the existing signal. Measured here the other way,
  extracting with both regexes over the same 60 archives and 129,596 in-window
  messages: **1,533 pairs only the bare-www regex sees, 526 of them not already
  admitted, 337.0 equivalent-English, and only 296 of those on domains the store
  already knows** and therefore admissible at once under the corroboration rule,
  worth 186.7 equivalent-English. Scaling by the agent's own saturation exponent
  of 0.911 gives roughly **8,550 equivalent-English admitted across the whole
  corpus**, not the ~63,000 the five signals together promise
- **Still worth doing, and the regex is now in.** `www.foo.com` written without a
  scheme was invisible because `_URL` requires `https?://`, and that was the
  ordinary way to write an address in 1996-1999. Anchored on the `www.` label
  rather than accepting any bare host: a bare `foo.com` in prose is more often a
  company name or half an email address, and the evidence wall is worth more than
  the recall. **It changes nothing already shipped until the archives are
  re-ingested**, which the content-hash ledger will refuse without a force, so
  that is Ivo's call and not a decision to slip in overnight

## 2026-08-06 (the `.au` load-shedding route is designed and deliberately not built)

The Australian Web Archive would move `.au` queries off the Internet Archive
entirely. That is worth having: `.au` is 1.7% of the gap queue but 87% of its
first thousand under the equivalent-English ordering, because `.au` carries the
highest English share of any major TLD at 0.9904, and the endpoint answered every
one of 250-plus requests with no throttling at a 0.98 s median. IA is the
bottleneck, so moving that share off it is a real gain.

It is not built, and the reason is an integrity risk rather than the work:

- **It cannot be allowed to corroborate.** A candidate is promoted when two
  INDEPENDENT sources agree. AWA's in-window records live in files named
  `NLA-EXTRACTION-1996-2004-ARCS`, `.arc.gz` being the Internet Archive's own
  container format, and measurement agrees with that reading: identical year sets
  on 26 of 30 domains, and 0 finds on 30 where our IA journal already says
  "nothing in window". So it is the same underlying crawl. Wiring it in as an
  ordinary source would let it corroborate an IA capture, or a Usenet mention that
  IA had already been asked about, and **quietly inflate the shipped figure with
  agreement between two copies of one source**
- Doing it properly means a source family shared with `cdx_snapshot`, so the
  corroboration split treats the pair as one source, plus its own evidence type
  and URL form, plus a check in `ark check` that no promotion rests on the pair
  alone. That is an hour of careful work on the part of the pipeline whose whole
  purpose is that the shipped number cannot be inflated, and it is not work to do
  unsupervised at three in the morning against a deliverable already sent
- The throughput it would buy is also the thing tonight's query ladder already
  bought several times over, so the urgency is gone

Recorded rather than attempted. The measurements needed to build it are in
`handback-sources-B.md` and the corrections are in the 06 August source note above.
