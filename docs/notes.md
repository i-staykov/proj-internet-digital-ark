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
  - likely dropped by the prior work's normalization: stripping `www.` unconditionally turns `www.cl` into the bare suffix `cl`, which is then rejected and the domain disappears; our canonicalizer splits against the PSL first, so the registration survives
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
  - validates the reusable CDXJ parser; informs the (Opt) `IA.cdxj` decision: Arquivo collections overlap heavily with what we already hold, so 51 GB of `IA.cdxj` is unlikely to be worth it unless a later gap analysis says otherwise

- **Arquivo `IA.cdxj` spike: GO, materially net-new in the thin years (finding; revises the Roteiro-based forecast directly above)**
  - method: 6 byte-range slices of 64 MB (402 MB total, 0.79% of the 50.93 GB file) spread evenly across the file; the server honors `Accept-Ranges`, and the file is SURT-sorted (TLD-then-host) so spread offsets sample different TLD/host bands rather than one alphabetical clump. Each slice parsed with the shipping `parse_arquivo_cdxj` + `to_registrable`, then classified read-only against the store (the store was ATTACHed READ_ONLY, so the spike could not mutate it)
  - in the sample: 168,409 in-window HTTP-200 captures -> 1,492 distinct registered domains, of which **177 (11.9%) are brand-new** (never in our `domain` table), 12 already net-new via another source, 1,303 baseline overlap
  - the brand-new domains land in exactly the thin years: 1998 (9), 1999 (19), 2000 (100), 2001 (91); their TLDs are .pt (96), .com (52), .br (24), i.e. Portuguese/Brazilian hosts the IA-global baseline missed. This is the UKWA `.uk` pattern repeating for the Lusophone web
  - this overturns the Roteiro forecast above: Roteiro was 1996-only (a year already dense), so its ~0 net-new did not predict IA.cdxj's 1998-2001 `.pt` yield. A curated national donation is complementary to the global crawl precisely where the global crawl is thin
  - linear rate-based extrapolation to the full file: **~22k net-new domains / ~105k net-new pairs**; treat as order 10^4, not precise (0.79% sample, `.pt` band density varies across the file). Comparable in absolute terms to UKWA's +15,822
  - evidence type is `cdx_timestamp` (a web-archive capture with in-year timestamp and status 200), III.1's least-controversial named evidence, so this tranche does NOT hinge on Prof. Ding's `artifact_listing` ruling; the parser already exists and is tested (Roteiro)
  - decision: **ingest**. Register source `arquivo_ia` (kind timestamped, `parse_arquivo_cdxj`); download the 51 GB once (resumable via byte-ranges, 740 GB disk free) -> ingest -> export -> stats -> yield entry. The cost is the ~10 h download (server ~1.5 MB/s), not code

- **Arquivo `IA.cdxj` ingested: +6,715 net-new domains, 98% `.pt`, concentrated in the thin years (finding). The spike's GO was right on direction, 3.3x high on magnitude**
  - the 50.93 GB file downloaded clean on a single 8.5 h connection (resumable loop, exact-size match, sha256 recorded in `data/raw/checksums.sha256`), then ingested in ~4.5 min: 140.8M lines -> 14.82M in-window HTTP-200 captures -> 14,188 distinct registered domains (122.2M lines out of window = the 2002-2007 bulk; 2.0M non-200; 1.8M malformed)
  - **yield: +6,715 net-new domains / +17,689 net-new pairs** (412,973 -> 419,688 domains; 1,156,150 -> 1,173,839 pairs); +28,247 `cdx_timestamp` evidence rows. The scoreboard delta equals the ingest's `year_rows` (17,689) exactly, so the numbers reconcile
  - **98.4% of the net-new domains are `.pt`** (6,896 of 7,005 net-new IA domains; then .com 58, .br 24): the Portuguese national web the IA-global baseline never indexed, exactly the geographic-complement thesis. Live-replay spot-checks of net-new captures return 200 (e.g. `arquivo.pt/wayback/.../100limite.pt`, `.../100mais.pt`)
  - **it fills our thinnest years**: new pairs by year 1998 +912, 1999 +2,667, 2000 +4,747, 2001 +9,323 (1996 +1, 1997 +39), i.e. **+89% on 1998, +165% on 1999, +183% on 2000, +50% on 2001** over the prior net-new pair counts. This is the strategic win: ISC stopped listing names after Jul 1997 and the baseline is thin post-1997, so a deep .pt crawl lands where we were weakest
  - corroboration: IA.cdxj also added a second capture to 7,183 already-baseline domains; the honesty caveat holds, IA.cdxj is IA-donated so this corroboration shares the baseline's IA lineage (cross-source, not provenance-independent). The net-new .pt domains are new facts regardless of lineage
  - **spike accuracy, recorded honestly for method:** the 0.79% byte-range spike predicted ~22k net-new domains; actual is 6,715, a 3.3x overshoot. Cause: distinct-domain count was extrapolated linearly by bytes, but distinct-domain density is highly non-uniform on a SURT-sorted file dominated by deeply-crawled .pt hosts (the full file averages ~1,044 in-window captures per domain vs 113 in the sampled slices, so most bytes are a few hosts repeated). The spike's qualitative calls (GO, thin-year concentration, .pt complement) all held; only the magnitude did not. Lesson for future spikes: extrapolate distinct-entity counts with a clustering caveat, not as if they scale with rows/bytes
  - the store was backed up before the write (`data/ark.duckdb.bak-pre-ia`) and the backup removed once the yield reconciled

- **UKWA host link graph ingested (link_source): complete for our window; recon size was overestimated (finding)**
  - download is unreliable: Wayback serves the ~2.0 GB gz stream but advertises a 20.9 GB Content-Length (the decompressed size), serves no byte-ranges (no resume), and drops the connection mid-transfer (curl exit 18). Our copy is a partial download.
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
  - **impact: this confirms our master taxonomy wholesale.** `artifact_listing` (ISC), `cdx_timestamp` (Arquivo / Early Web / IA CDX), and `link_source` (UKWA) are all direct master evidence. The ~1.13M net-new pairs that rested on the ISC `artifact_listing` type (the ~1.13M-vs-193 swing flagged in the interim email) stand as master; nothing downgrades to candidate. The single largest project risk is retired
  - **provenance already conforms** (verified 2026-07-24): every evidence row carries source name (`source.name`), the dated identifier (`evidence_value`: ISC `1997-07`, CDX full timestamp, UKWA `host_link_graph:2001`), the assignment method (`acquisition_method`), and a record id (`evidence_url` for captures; `evidence_value` + the `ingested_file` sha256 ledger for the rest). The §IX provenance export must surface these four fields per row
  - III.4 still governs genuinely UNLABELED sources (StanfordWebBase, undated DMOZ, raw URL lists): those remain candidate -> CDX-verify. The line Ding draws is per-item dated attestation (direct) vs. a bare list with no year (candidate)

- **`whois_creation` evidence standard: registration-interval (decided with the AFNIC data in hand, 2026-07-24)**
  - a BARE creation date, on its own, supports only the creation year - III.6 is explicit that a creation date alone does not establish later years. BUT a source that also shows the registration CONTINUED (a later withdrawal date, or that the domain is still registered now) documents a CONTINUOUS registration interval, because a .fr (and standard gTLD) creation date RESETS on any re-registration. So a 1998 creation date on a domain still registered in 2026 proves an unbroken 1998->2026 registration, hence registration in 1999, 2000 and 2001
  - III.6 accepts "a WHOIS record demonstrating continued registration in that year" as valid later-year evidence; a documented continuous interval IS exactly that for every year it spans. So for interval sources we assign every in-window year the domain was registered, not only the creation year. This is a documented fact, not the bare-creation-date inference III.6 declines
  - applies now to AFNIC (creation + withdrawal columns); applies to the Phase 4 RDAP engine too (a queryable RDAP record means currently registered), with a per-registry check that the registry resets the creation date on re-registration (true for .fr and standard gTLDs; some ccTLDs keep the first-ever date - verify before trusting the interval there)
  - considered a confirmation email to Ding, decided against it (Ivo, 2026-07-24): the interval is defensible directly from III.6 and is recorded per row, so a reader can verify each assignment themselves (see the AFNIC yield entry). This supersedes the earlier "creation year only" reading, which had not yet accounted for the withdrawal-date column
  - **SUPERSEDED FOR RDAP on 2026-07-25 (next entry): RDAP now assigns the creation year only. Still in force for AFNIC, pending a separate call**

- **RDAP restricted to the creation year, interval rows pruned (Ivo's call, 2026-07-25) - supersedes the entry above for RDAP**
  - trigger: Ivo asked what an RDAP response actually gives us per domain before trusting the interval reading. Checked live against `rdap.verisign.com` for `daastol.com`: top-level keys are `entities, events, handle, ldhName, links, nameservers, notices, objectClassName, rdapConformance, secureDNS, status`, and `events` holds exactly four - registration 1998-07-06, expiration 2027-07-05, last changed 2026-07-19, last update of RDAP database 2026-07-25
  - **so RDAP carries current state plus ONE historical timestamp. There is no registration history and no per-year attestation.** Two facts are extractable: created on date D, and registered now. Nothing observes 1999, 2000 or 2001
  - the III.6 test, sentence by sentence: "valid evidence of when a domain was created" = the `registration` event (fine); "may support inclusion in the annual file for the target year in which the creation date falls" = the creation year is explicitly blessed (fine); "a WHOIS Creation Date alone does not automatically establish that the domain remained registered ... in every subsequent year", and later years "still require ... evidence tied to that specific year" = our interval claim fails. For 1999 we held a record showing registration in 2026 plus a creation date in 1998; reaching 1999 needs a third premise (registry creation dates reset on re-registration) that is an external assumption about registry policy, and one never verified per registry here - the ~1,100 ccTLD rows (.uk 503, .nl 66, .ca 32, .br 31, .cz 28, .no 17, .fi 8) were the known hole. Ding's ruling uses the same qualifier, sources that "directly attest"; a bridging deduction across 28 years is not direct attestation
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
  - **new caveat we must carry: `crDate` also resets on a "transmission (trade or recover)", i.e. a change of holder.** So an AFNIC creation date is the later of (last registration, last holder change) and must NEVER be described as the first-ever registration date. It does not weaken continuity (it can only move the date later), but the wording in report and notes has been corrected accordingly
  - **gaps, stated rather than buried:** (a) the load-bearing sentence is from 2015 and was removed in AFNIC's 2019 documentation rewrite, absent from the current December 2024 guide, so the explicit statement is 11 years old and current behaviour rests on the 2026 live cases above (the 2015 text and the 2026 behaviour were both confirmed first-hand; the claim that the current guide omits it was not independently re-checked); (b) the 2017 edition could not be read, its Wayback capture truncates at 1 MiB, so the lineage has one hole; (c) R being true makes the interval SOUND, not year-TIED in III.6's sense. That residual is interpretive, and only Ding can close it, but it can now be put to him as documented registry semantics rather than an assumption
  - **RDAP stays narrowed to the creation year**, because R is documented for `.fr` only and RDAP spans ~590 registries. The split is now principled: verified premise vs unverified one, not two readings of the same claim. Ivo's call (2026-07-25): not worth chasing R per-registry to recover RDAP's ~9,664 pairs
  - method note: run as a 7-family parallel documentary hunt (naming policy, procedures manual, AFNIC EPP docs, IETF EPP/RDAP standards, open data docs, French regulation via CPCE L45, live registry behaviour plus third-party), with every citation re-fetched by an independent adversarial verifier instructed to reject paraphrased or fabricated quotes. 50 agents, ~2.0M tokens, 43 min. Most structural findings (charter para 134, the create/restore/delete lifecycle, CPCE L45-1) were correctly downgraded to context-only: they establish that a deleted name becomes registrable afresh, but say nothing about the date

- **RDAP re-architected: collection separated from interpretation, so its evidence replays from a hashed file (Ivo's call, 2026-07-25)**
  - the problem: `ark rdap` queried the network AND wrote evidence in one pass, keeping only the extracted year. Two costs fell out of that coupling. (a) Provenance: the resulting rows had no source file, so unlike every other source they could not be replayed from bytes we hold, only by re-querying a network that now answers differently. (b) Cost of change: the 2026-07-25 narrowing had to be a destructive database migration plus a guard script plus a 4 GB backup, purely because the responses were gone
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
  - coverage: ODP contributes 2000 (our Aug-2000 dump) and 2001 (Kids-and-Teens dumps we hold + the three downloadable full 2001 content dumps); no 1998/1999 (those dumps never existed - see the hunt)

- **ODP dumps ingested (`odp`, `artifact_listing`): +3,339 net-new domains / +8,423 net-new pairs (finding)**
  - three on-disk dumps: `c2000.gz` (Aug-2000 full content dump, but only a ~1 MB TRUNCATED prefix survives, so just the alphabetically-first categories `Top/Adult...`, year 2000), `kt200106.gz` + `kt200111.gz` (complete Kids-and-Teens subsets, year 2001). The `<!-- Generated at YYYY-MM-DD -->` stamp fixes each dump's year (2000-08-07, 2001-06-10, 2001-11-13)
  - parser pulls cataloged-site URLs by regex (`link r:resource=`, `ExternalPage about=`; internal `Top/...` topic refs excluded), tolerates the truncated gzip (c2000 EOFs mid-stream, handled like UKWA), then canonicalizes to registered domains
  - yield: 93,854 URLs -> 19,629 `artifact_listing` evidence rows over 19,367 domains. **+3,339 net-new domains, +8,423 net-new pairs** (2000 +6,477, 2001 +1,946); scoreboard 459,055 / 1,291,668 -> **462,394 / 1,300,091**. Each row records the dump date (e.g. `odp 2000-08-07`) so a reader can verify it
  - low net-new, as the hunt predicted: only 3,379 of 19,367 ODP domains are net-new (ODP curated popular live sites the IA baseline already holds); the value is mostly 2000 (a thinnish year) plus corroboration
  - caveats for the report: (a) `c2000` is a truncated 1 MB prefix of the ~170 MB Aug-2000 content dump, and the FULL 2000 content dump is not recoverable (Wayback archived only the 2000 `structure.rdf`, which carries no external links), so 2000 is badly undercounted here; (b) the KT dumps are the Kids-and-Teens theme only; (c) heavy baseline overlap
  - available but not done (low ROI): the three FULL 2001 content dumps (2001-01-22 / 06-16 / 10-20, ~170 MB each, downloadable via Wayback `id_`) would add more 2001, but 2001 is our least-thin year and ODP overlap is heavy, so deferred unless completeness is wanted

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
  - conclusion: like Early Web CDX (99.99% baseline overlap) and the `deduplicated_urls` files (which yielded 8 domains not already held, 6 of which other sources later dated), the popular 2001 web is already fully covered by our baseline + sources. webbase is a large crawl but adds essentially nothing net-new. Retired as a net-new source
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
  - the unit of work is the DOMAIN, not the gap, because one query answers every year. A run therefore harvests years we never asked about, which is where most of the yield turned out to be
  - **calibration (three measured runs, this is the finding).** 1 worker at 1.0 s pacing: 15 domains in 5:11 = **20.7 s/domain**, zero throttles. So the bottleneck is per-query LATENCY (a wildcard CDX query costs ~20 s), not a request-rate ceiling, and the lever is concurrency. 12 workers: **2.2 s/domain (~1,650/h)**. 24 workers at 0.15 s pacing: 120 domains in 2:02 = **1.0 s/domain (~3,540/h)**, 1 throttle, governor recovered to 92 ms. A 20x speedup over sequential
  - **governor lesson (my error, corrected).** The first pilot used 4 workers with `max_delay=30s`, `backoff_factor=2.0` and recovery of 0.9x per 20 successes. Six throttles drove the pace to the 30 s ceiling and it never came back: 40 domains took 7:28 (11.2 s/domain) with the tail crawling at 45 s/domain. For a latency-bound workload the ceiling must be low and recovery fast; retuned to `max_delay=5s`, `backoff_factor=1.5`, recovery 0.8x per 5 successes. Pacing exists only to stay under the limiter, not to regulate throughput
  - **yield, measured not estimated.** First 40 domains: 39 with captures, 136 in-window years found, ingested as **136 evidence rows -> 48 net-new pairs** (1.2 net-new pairs per domain queried, versus ~0.15 for RDAP on the same pool). Scoreboard 1,303,508 -> **1,303,556** (1998 +14, 2000 +34). Hit rate varies sharply by position in the priority list (97% capture in the first 40, 50% in the next 60, 22% in the next 120), so per-batch yield must be tracked rather than extrapolated from the head of the list
  - long run launched as **12 sequential batches of 5,000** rather than one job, so each journal completes and can be ingested while later batches still run; resume skips journalled domains, so a kill costs at most one batch's tail

- **CDX engine tuned by measurement; two of my own inferences were wrong and are corrected here (2026-07-25)**
  - **ERROR 1, silent and serious: failures were being recorded as absences.** The status distribution across the first journals was 200:354, **0:2,727**, 503:4. Status 0 is a transport failure, but the run counted any record without years as `no_capture`, so 88% of high-concurrency requests were failing and being reported as "IA never archived this". Two consequences: the apparent collapse in hit rate (97% at the head, 1.5% deeper) was an artefact of my instrumentation, and because resume skipped any journalled domain, **2,727 domains would have been dropped from every later run**. Fixed three ways: failures are counted per status (`failed_0`, `failed_503`, `failed_504`) separately from genuine `no_capture`; `journal.queried_domains` takes an `answered` predicate and CDX passes `status == 200`, so only a real reply settles a domain; the affected domains returned to the queue automatically
  - lesson, added to PersonalContext: an instrument that cannot distinguish "no answer" from "answer is no" will invent a finding. Check the status distribution before trusting any throughput or hit-rate number
  - **the concurrency ceiling is the service's, not ours.** Answered share by concurrent requests: 1 -> 100%, 4 -> 100%, 8 -> 82%, 16 -> 30%, 32 -> 17%. Past ~8 the server drops connections and emits its own 504s. **Operating point 8 workers, ~800-1,000 answered domains/hour.** The earlier "61,277/hour at 192 workers" was measuring refusals, not queries; 384 workers measured *slower* than 192, which was the first hint
  - **ERROR 2: "fail fast" was a false economy.** From the A/B test the server appeared to kill heavy queries at a consistent ~60.7 s, so I cut the client timeout to 30 s expecting to halve the cost per answer. Measured against the same 100 domains: 30 s answered **51** (695 answers/h), 180 s answered **82** (802 answers/h). Roughly a third of domains reply between 30 s and 60 s, and cutting them off loses more than the saved waiting gains. Since the server already fails fast for us, the client timeout only needs headroom above its limit: **70 s**
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
  - webbase `hosts.txt` seeded as the III.4-named candidate source: **738,625 hostnames -> 603,323 distinct registered domains**, of which **603,141 already confirmed from the baseline**, 64 already confirmed from our own sources, 1 already a candidate, and **39 genuinely new**. 78 invalid. The three-way split introduced with the seeding fix is what makes this legible: it restates the "99.99% already held" finding as a reproducible measurement rather than a claim
  - `deduplicated_urls_2001-2002` seeded: **1,097,867 lines -> 0 new candidates** (916,133 already baseline, 8 ours, 3 already candidate, 2,239 invalid). Exhausted, exactly as the 2026-07-22 probe predicted
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
  - now three states instead of one: `already_confirmed_baseline` (has a year, carries `prior_reused`), `already_confirmed_by_us` (has a year from our own evidence), `already_candidate` (on file, no year -> still queued). This also discharges the long-standing "split `already_known` into baseline vs earlier-seeded" item
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
  - so the whole scan went to the candidate pool instead: **3,453 hostnames seeded, 3,187 already confirmed from the baseline, 8 from our own sources, 258 genuinely new**, all queued for CDX verification, where a capture will settle each on its own evidence
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
  - consequence had it shipped: `output/netnew/` would have held **1,339,783** pairs instead of 17,418, re-claiming the whole of phase 1 as new against a baseline that already contained it. That is exactly what the feedback forbids: "do not report internal pipeline insertions as if they were new against the project". It would have been caught, but by Ding's merge rather than by us
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
  - `evidence_urls` stores the exact snapshot URLs that were read. **That column is the entire difference between this and a TLD prior**: a reviewer can refetch what we classified and recompute the verdict. Ding asked for archived-content evidence, and a verdict nobody can check is not evidence

- **Two thirds of our additions can be classified at all, and one third cannot. Measured, not assumed**
  - per net-new (domain, year), does any `cdx_timestamp` evidence exist for that exact pair? If yes the archive provably holds an in-year capture and there is body text to read; if no, the pair rests on a registry creation date or a DNS survey line and there may be nothing at all
  - result: **21,825 of 32,698 (66.7%) are capture-backed**. By year: 1996 0.4%, 1997 0.0%, 1998 86.5%, 1999 5.9%, 2000 93.5%, 2001 96.5%
  - this is a hard ceiling on the admissible set before language is even considered, and it is not something more crawling fixes: the Internet Archive did not capture those sites in those years

- **The planned year priority was exactly backwards, and a calibration run proved it before the code shipped**
  - the plan said to classify 1996 and 1997 first, because feedback section 5 puts both under 10,000 additions and therefore closest to the completeness threshold. Sound about completeness, wrong about this engine
  - the first calibration run spent its whole budget on 1996 and returned 74 answers, **every one `undetermined` with zero captures found**. Cross-checked against the measurement above (1996 is 0.4% capture-backed) and against four of those domains re-queried by hand on a healthy connection, which returned genuine HTTP 200 with zero rows. The engine was right; the priority was wrong
  - `write_lang_targets` now orders capture-backed pairs first, then by year volume within that group. Requests against the archive are the scarce resource and they go where a verdict can change the admitted set. The completeness argument for 1996 and 1997 has not gone away; it simply cannot be served by page-text classification

- **The archive refused us within four minutes, and the governor could not see it**
  - the first design sent up to 4 requests per pair (1 CDX query plus 3 snapshot fetches) at 4 workers with a 0.05 s floor. That is an order of magnitude more traffic than the CDX engine's sustained ~1,000 requests/hour. After roughly 400 requests `web.archive.org` began refusing TCP connections while ping and DNS stayed healthy. Third refusal in this project's history
  - the real defect was not the pace but the blindness. `RateGovernor` backs off on 429, 503 and 504. **A refused connection is status 0, which was not a throttle signal**, so the run kept dialling at full speed at exactly the moment it should have stopped. Silence was being read as success
  - two fixes. Status 0 now backs the governor off like an explicit 429. And `ark lang` carries a circuit breaker: 25 consecutive failures ends the batch, because an unbroken run of failures is not bad luck, it is the archive declining our traffic, and continuing turns a temporary refusal into a durable one. Nothing is lost, since an unanswered pair was never settled
  - `--min-delay` is now an explicit option rather than an inherited default. For an engine whose unit of work costs three requests, the floor is what bounds the load, not the worker count

- **Classifier decisions, each of which changes the measured English share**
  - **`charset_normalizer` over raw bytes, never UTF-8 over text.** Pages of this period are frequently latin-1, Shift-JIS or GB2312 with no declared charset. Decoding those as UTF-8 produces mojibake, mojibake classifies as undetermined, and undetermined pages leave the denominator, so the error would have **raised** the measured English share. This is why the module carries its own bytes fetcher instead of reusing `cdx.py`'s, whose fetcher decodes with `errors="replace"` and destroys the evidence before we see it
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
  - that is the specific gap the capture-backed measurement exposed. Our 1996 and 1997 additions are 0.4% and 0.0% capture-backed, so the archive holds nothing to verify against; a dated post does not need the site to have been crawled at all
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
  - `webarchive.nla.gov.au/awa/cdx` still serves an anti-bot challenge, but **`web.archive.org.au/awa/cdx` answers normally** and returns a 1996 capture for `abc.net.au`. Our rejection was stale, which is precisely what section 4 means by revisiting blocked sources, and the correction is worth keeping even though the source failed
  - the pool looked strong: 35,391 PANDORA registered domains, 29,595 of them in no annual file. A random **60-domain** sample returned 60 answers, zero transport failures and **zero in-window captures**. Rejected on a clean sample rather than on the 39-host probe that first suggested it

- **How much the Usenet post date can be trusted, measured against an independent source**
  - for the 217,113 Usenet-dated pairs whose domain the Internet Archive also evidences, the archive attests **the exact same year for 51.1%** and **a year within one for 88.7%**. An earlier 30-domain spot check suggested 47% and 77%, so the full measurement is kinder, but the shape holds
  - a disagreement is not automatically a Usenet error. The archive crawled sparsely in these years, so a site announced in 1997 and first captured in 1998 produces a mismatch in which the post is the better evidence. That is the whole reason this source reaches years the crawl cannot
  - but it bounds the claim honestly: for roughly half of these pairs we assert a year the archive does not independently confirm, resting on a dated public post. Brief III.1 accepts "a dated directory page, a dated index file", so this is a legitimate reading, and it is weaker than a capture. It goes in the next report's limitations rather than being left for a reviewer to discover

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
