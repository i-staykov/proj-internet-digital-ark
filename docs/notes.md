# Decision log - lightweight ADR

Short notes on why I made certain architectural design choices.

**How to read this.** Entries are dated and **never edited after the fact**, so every figure inside one
is historical by construction: it was true when written, against the baseline and the store of that
day. Nothing here is a statement about the current state. For that, read `README.md` for what to run,
`docs/sources.md` for what each source is worth and what remains in it, and `src/ark/baseline.py` for
which reviewer release the totals are measured against.

Rough index: phase-1 from 2026-07-21, phase-2 from 07-28, phase-3 from 08-01, phase-4 from 08-01
(overlapping, since the rounds ran close together), phase-5 from 08-10.

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
  - rebuild: [`legacy/scripts/restrict_whois_creation_to_creation_year.py`](../legacy/scripts/restrict_whois_creation_to_creation_year.py), dry run unless `--apply`, parameterized by source. It aborts rather than guess if any creation year is unparseable, or if a doomed assignment could be re-pointed at other master evidence instead of deleted. Verified before applying: **0 of the 9,664 doomed assignments had alternative master evidence**, so the prune was a pure delete
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

The session write-up this once pointed at was retired on 8 August; its durable conclusions live in
the relevant `docs/sources.md` sections. The decisions, and the numbers behind them:

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

## 2026-08-06 (the ceiling is IA's per-IP concurrency, so the ladder's win is years per query)

Spent the second half of the night trying to raise queries per hour and found the
wall instead. Recording it because it redirects where the next effort should go.

- **8 workers and 12 workers give the same throughput: 506 against 510
  queries/hour.** Doubling concurrency earlier in the night looked promising
  because the VPS went from 28.1 to 4.0 s/domain when it went from 4 to 8, but
  that gain was the query ladder arriving at the same moment, not the workers
- **The reason is that IA refuses the excess connection rather than queueing it.**
  Measured while the local engine ran 12 workers: ten sequential host queries from
  a separate process, so a 13th concurrent connection, and **6 of the 10 were
  refused** at the same flat ~3.3 s signature seen earlier in the night, while the
  engine's own failure count over the same window was 0 of 25. So the limit is on
  concurrent connections per IP, the engine's twelve were inside it, and the
  marginal one was not
- **So 12 workers was strictly worse than 8: the same throughput with less margin
  before the penalty box.** Settled both machines at 8
- **Which means the honest reading of tonight's gain is different from the one I
  first wrote.** Queries per hour did not move and cannot be moved from one IP.
  What moved is **year-records per query**: the ladder converts a scan the server
  gives up on, previously 60 seconds spent for nothing, into an answer. That is
  why year-records/hour rose 19% while queries/hour fell slightly. The metric Ding
  scores is equivalent-English, which follows year-records, so the improvement is
  real, but it is a yield improvement and not a rate improvement, and calling it
  the latter would have been wrong
- **Corollary, and the useful part for planning: more capacity means more IPs, not
  more workers.** The VPS is not a nice-to-have, it is the only lever that raises
  the ceiling, and a third address would raise it again. That reframes "free
  compute" as "a second rate-limit allowance"
- **A hypothesis I formed and the data killed, worth recording so it is not tried
  again.** Every batch's `final_delay_ms` looked pinned at the 3,000 ms ceiling,
  which would have capped starts at 1,200/hour, and 504 sits in the throttle set
  even though a 504 means *this query* was too big rather than that the service is
  overloaded. Removing it looked like an easy multiplier. But reading every batch
  summary rather than the worst two, `final_delay_ms` is **150, 224, 227, 466,
  1994, 2880, 3000** ms: usually near the floor, not the ceiling. Pacing is
  therefore not the binding constraint, and the change would have bought nothing
  while removing a real safety valve
- **Batches are now 300 domains rather than 1,200.** The governor's throttle count
  and final delay are only printed when a batch ends, so at 1,200 an unattended run
  reports its own health roughly every two hours. At 300 it reports every 35
  minutes. The cost is reloading the skip set more often, a few percent, and it is
  worth it for a run meant to go unwatched until Sunday

## 2026-08-06 (1996 cannot be bought from the Internet Archive, and that is the answer to give Ding)

The bracketed-gap queue can only target 1997-2000, because both flanking years
must be in window, so 1996 is only ever gained incidentally: 31 of its 1,358 new
records this round came from capture verification. 1996 is also the year furthest
from the completeness standard. So the obvious move was a queue of domains held in
1997 with no 1996 record, of which there are 812,177 never yet asked, a ceiling of
452,192 equivalent-English if every one filled.

Measured on 60 of them, 58 answered:

- **0 of 58 had a 1996 capture. None.** With no successes in 58 trials the rate is
  under about 5% at 95% confidence, and the true figure is probably far lower
- **The reason is the Internet Archive's own 1996 coverage, not our method.** Its
  earliest crawls were small. If a domain we hold for 1997 has no 1996 record from
  us, the archive does not have a 1996 capture of it either. **So no amount of
  capture verification will move 1996**, and the 812,177-domain queue with its
  452,192 ceiling is worth approximately nothing for the year it was built for
- **This is the honest answer to the completeness question rather than a hedge.**
  The interim report says 1996 grew 0.1993% and is sparse "for reasons of method
  rather than saturation". That is now measured rather than asserted, and sharper:
  the method that produced 96% of this round's records is structurally incapable of
  adding to 1996. Moving 1996 needs a different KIND of artifact, one dated by
  something other than a crawl: a dated Usenet posting, a dated directory snapshot,
  a periodical with a cover date
- **The same query population is nonetheless a good queue, for the other years.**
  Those 58 queries returned **78 marginal years, 1.34 per query, worth 0.642
  equivalent-English per query against the bracketed-gap queue's measured 0.536**.
  All of it in 1998-2001: 1998 5, 1999 27, 2000 24, 2001 22. So a domain held in
  1997 and missing later years is slightly BETTER value than a bracketed gap, just
  not for the reason it was tried. Worth queueing when the current 237,000-domain
  shard runs dry, which at the measured rate is weeks away
- Median 12.5 s per query, notably slower than the 2 s the ordinary domain costs,
  because a domain that survived from 1997 is an old and heavily archived one

## 2026-08-06 (the bare-www estimate, corrected upward on a bigger sample)

The 60-archive figure earlier tonight scaled to roughly 8,550 equivalent-English
admitted. Re-run over 400 archives, 1,454 MB and 1,459,120 in-window messages, it
is close to twice that, and the reason is a sampling artifact worth naming.

- **Measured on 400 archives: 13,825 pairs only the bare-www regex sees, 6,617 of
  them not already admitted, 4,481.1 equivalent-English. Of those, 2,933 are on
  domains the store already knows and can enter at once, worth 1,979.8.** The
  `.uk` share is good, 1,446 of 6,617 pairs
- **Scaled to the whole 12,999 MB of archives at or under 40 MB, an 8.94x step,
  and damped by the measured saturation exponent of 0.911, that is 7.36x:
  about 21,600 pairs admissible at once worth ~14,600 equivalent-English**, plus
  ~27,100 more going to the candidate pool
- **Why the first estimate was low.** Growth looked super-linear, 6.67x more
  archives giving 12.6x more pairs, which should not happen to a saturating
  process. It is not saturation reversing, it is that the shuffle put small
  archives first: 60 archives were 159 MB and 400 were 1,454 MB, so 6.67x more
  archives is 9.1x more bytes. Per byte the yield is nearly flat. **Scale by the
  quantity the yield actually depends on, not by the one that is easy to count**
- **The measurement ignores 55% of the corpus, but the corpus is not out of
  reach, and I nearly recorded the opposite.** The 178 archives over 40 MB hold
  15,713 MB of the 28,712 MB total, and both the research agent and I capped our
  samples there because `iter_messages` expands an mbox into memory. It is easy to
  read that cap as a loader limit and conclude that streaming would unlock new
  material. It would not: **all 178 are in `.processed`**, so the ingest already
  reads them and has done. The cap was sampling convenience, nothing more
- **Which means the estimate is a floor, not a ceiling.** ~14,600 equivalent-English
  covers the 45% of bytes that was sampled. If the yield per byte holds on the
  larger archives, and there is no reason it should not, the full-corpus figure is
  closer to **~30,000 equivalent-English admissible**, which makes the re-ingest
  more attractive rather than less. Worth measuring properly before acting, by
  sampling the large archives rather than assuming they behave like the small ones
- Still not re-ingested. The content-hash ledger will refuse the archives as
  already seen, and forcing it risks duplicate evidence rows in exactly the table
  whose integrity the delivery rests on. Ivo's call, with a real number now.

## 2026-08-06 (the bare-www signal, finally measured over both halves of the corpus)

Sampled the 178 large archives directly rather than assuming they behave like the
small ones, which closes the estimate.

- **10 large archives, 1,026 MB, 846,927 in-window messages: 5,966 pairs only the
  bare-www regex sees, 1,231 admissible at once worth 786.9 equivalent-English**
- **They yield 0.767 equivalent-English per MB against the small archives' 1.362,
  so 56%.** Extrapolating the whole corpus from the small sample would have
  overstated it by a third, which is what the earlier "likely nearer 30,000" guess
  did. Damping each half by the measured saturation exponent of 0.911 and adding
  them gives **14,565 from the 12,999 MB of small archives and 9,453 from the
  15,713 MB of large ones, so about 24,000 equivalent-English admissible at once**
  across the whole 28.7 GB, plus roughly 45,900 further pairs going to the
  candidate pool
- That is ~76% of what the capture engine is projected to add by 9 August, for no
  network at all, and it is the strongest remaining lead. It needs a forced
  re-ingest, which the content-hash ledger exists to prevent, so it stays Ivo's
  call, but the number behind the call is now measured on both halves rather than
  scaled from one
- **The 56% gap is the same effect the project already knew about**, recorded on
  5 August as smaller archives giving more domains per byte, and cut from the
  interim report as too fine a detail for Ding. Worth keeping internally: it means
  any per-byte projection from a sample of small archives is optimistic

The end-to-end check on tonight's engine change, done at the same time, is clean.
`warehouse.co.uk`, the domain five batches had failed on, now holds admitted
`cdx_timestamp` evidence for 1998, 1999, 2000 and 2001; `gigabyte.com` for 1997
through 2001; `vccs.edu` gained 2001. Twelve of twelve sampled rescues are admitted
records with an evidence row, so the ladder is producing real evidence and not just
faster journal lines.

## 2026-08-06 (the first completed batch on the ladder, before and after)

The 300-domain batch size exists so a summary arrives every half hour instead of
every two, and the first one is the cleanest before-and-after of the night.

```
before, 1,200 domains, wildcard-first, 8 workers
  with_capture 1056  years_found 4218  queried 1198
  failed_504 41  failed_503 22  failed_0 63  errored 2      throttles 507  final_delay 3000ms

after, 300 domains, three-tier ladder, same 8 workers
  with_capture  296  years_found 1144  queried  300
  failed_-1 2                                          throttles 103  final_delay 2880ms
```

- **Hit rate 88.1% to 98.7%.** The domains that used to fail were not undatable,
  they were being asked the wrong question
- **Failures 10.5% to 0.7%, fifteen times fewer**, and the two that remain are
  both `failed_-1`, the new TIMED_OUT status, so they are heavy domains rather
  than refusals. **Zero refusals, zero 504s, zero 503s** in the whole batch, where
  the old shape produced 126 failures in 1,198
- **Years per query 3.52 to 3.81**, up 8%, on top of answering 10 points more of
  the batch
- **22 minutes for 300 domains: 818 queries/hour and 3,120 year-records/hour**
  against the 647 and 1,729 baseline. So 1.26x the query rate and **1.80x the
  year-records rate**, which is the one the metric follows
- `throttles` fell from 507 to 103 even though the query rate rose, which is the
  self-reinforcing loop unwinding: fewer doomed requests means fewer throttles
  means fewer retries. `final_delay_ms` is still high at 2,880, so the governor is
  still cautious, and that is the remaining headroom if anything is

## 2026-08-06 (the bare-www re-ingest, done on disk and measured against the store)

Ingested. 22,400 new admitted pairs, **15,164.8 equivalent-English**, all twelve
integrity checks passing. Predicted 15,169.7 before running it, so the estimate
was 4.9 EE out. What made that possible was doing the whole comparison on disk.

- **The ingest never reads the archives, it reads journals**, 102 of them holding
  979,189 distinct (domain, year). So a re-split could be staged, diffed and
  filtered before the store saw any of it. No forcing past the content-hash
  ledger, no duplicates to clean up afterwards, and no need to touch the one
  table whose integrity the delivery rests on
- **Two safety gaps had to be closed first, and the first was nearly a mistake.**
  `split_usenet.py` wrote only to `data/raw/usenet`, which `maintain_phase3.sh`
  globs every cycle and ingests unconditionally. Writing a re-split there would
  have put 1,069,193 unreviewed pairs in the store within minutes. It also opened
  the store at the very end with no retry, after an hour of parsing
- **Full re-split: 4,175 archives, 48.6M messages, 1,069,193 pairs, 54 minutes.**
  Against the existing journals, 90,004 pairs were new
- **Verified those were the regex and not gaps in the old journals**, which is the
  claim the whole exercise rests on. Re-extracted the four highest-yield groups
  with `_BARE_WWW` disabled: **3,750 of 3,750 sampled new pairs disappear without
  it, 0 survive**. So the signal is real
- **The headline of the diff was wrong by 2.6x and the reason is worth keeping.**
  The diff compares against JOURNALS; equivalent-English is only earned against
  the STORE. Of 55,193 pairs absent from the journals, **34,390 were already
  admitted through another source**, mostly capture verification, so they buy an
  evidence row and no pair and no metric. Checking journals answers "is this new
  to this source", not "is this new to the collection"
- **My 24,000 projection was too high, and the error was adding two overlapping
  samples.** I projected small archives and large archives separately and summed
  them. But the same domains appear in both, so saturation is corpus-wide rather
  than per-subset. The small-archive projection ALONE was 21,577 pairs and 14,565
  equivalent-English against an actual 20,803 and 13,795.7, within 5%. **Adding
  the second projection was the whole mistake**
- Final ingest was the wider option: 59,347 dated, of which 4,154 promotions, plus
  34,811 candidates. 94,158 evidence rows for 22,400 admitted pairs. The 36,942
  that only deepen provenance on already-admitted pairs cost nothing next to
  23.7M `prior_reused` rows and strengthen the record
- **31,073 of the new candidates were enqueued** for the capture engine, which is
  where the remaining 23,882 equivalent-English of candidate-half value would come
  from if it corroborates them
- A pre-ingest copy of the store sits at `data/ark.duckdb.pre-barewww`, 5.2 GB.
  It is the only real rollback, because `ark ingest` commits and undoing it
  afterwards means deleting evidence rows that `domain_year` foreign keys point
  at. Delete it once the result has been looked at

Also answered, since it looked alarming: **23.7M `prior_reused` rows against 8.9M
pairs is three baseline releases, not duplication.** The originals,
`merged260727/` and `merged260730/`, each ingested under its own marker namespace,
which is exactly what `--marker-prefix` exists for. 6,866,913 pairs appear in all
three, 1,322,365 in two, 444,227 in one, which is 23,689,696 to the row. It cannot
distort anything: `domain_year` is keyed on (domain, year) so one admitted row per
pair, and all three carry the same `source_id`, so they cannot corroborate each
other.

## 2026-08-06 (the reviewer's reporting format, and whether our counting unit fits it)

- **He asked for five fields and they decode cleanly, but the growth rate is not
  the obvious one.** His example reads 10,263,632 records, 5,531,053.6089
  equivalent-English, an increment of 151,949 and 91,814.6880, and a rate of
  1.659986%. That rate is 91,814.688 / 5,531,053.6089, so **lines 1 and 2 are the
  database BEFORE the increment and line 5 divides by the pre-increment total**.
  Dividing by the post-increment total instead gives 1.688%, which is wrong by 2%
  of itself and looks perfectly reasonable, so the convention is now in code
  (`scripts/round_figures.py`) rather than in anyone's head
- **Our unit is not an approximation of his, it is the same unit, and that is
  measured rather than assumed.** This round's 148,444 records were written out
  per year and scored with his own `equivalent_english_domains.py`: 102,009.2509,
  agreeing with our implementation to **0.0000**, with **zero records rejected by
  his validator**. That matters more this round than last, because the bare-www
  regex widened what Usenet matches and a malformed hostname scores zero for him
  and full weight for us. `--verify` now refuses to print numbers that disagree
- **So lines 1 and 2 are quoted as his database, not ours.** 10,404,200 and
  5,622,984.6434, our measurement of his merged files, already given to him on
  4 August without objection. Our store holds 8,933,898 admitted pairs, which is
  smaller and always will be; reporting our own total would invite a question
  about why, when the answer changes nothing about the increment he credits
- **Checked whether the hostnames the registered-domain unit discards are worth
  claiming under his rule. They are not, and the number was tempting enough to be
  worth writing down.** 624,224 fall inside the window and pass his validator,
  carrying **434,951.97 equivalent-English**, which is 7.7% of his whole baseline.
  But 553,199 of them come from the ISC reverse-DNS survey and are machines rather
  than websites: the commonest leading labels are `pclan`, `dialup`, `hip`, `mail`,
  `ftp`, `s96`. Submitting them would pad the count with things that were never web
  pages and would contradict the English-website standard he set himself. Only the
  71,031 from the UK Web Archive link graph are defensible. Offered in the email as
  available on request rather than pushed, the same way the 11,568 malformed
  baseline records were offered on 4 August
- **The unit difference is stated once in the email even though it costs us
  nothing to omit.** We count `www.example.com` and `example.com` as one record and
  his validator would take both, so our increments are a floor. Worth one sentence
  purely as insurance: if hostname-level counts ever appear from elsewhere, ours
  must not read as weaker work at equal effort
- **Round so far, local engine only, VPS journals still held back by the VPN:**
  148,444 records and 102,009.2509 equivalent-English, 1.814148% growth, 119,674
  distinct domains, 150,858 more dated but held back uncorroborated. Mean weight
  0.6872 against last round's 0.6042, so **fewer records than last round's 151,949
  but 11.1% more equivalent-English**, which is the pool ordering by TLD English
  share doing what it was built to do

## 2026-08-06 (line 1 of the reviewer's format was the wrong count, caught by Ivo)

- **His line 1 counts RAW records; I had reported the validator-passing subset.**
  His calculator reads his merged 1996-2001 files as **10,415,768 unique nonempty
  records, of which 10,404,200 are valid**, the remaining 11,568 being the embedded
  ports and underscore labels found on 4 August. I put 10,404,200 in line 1. Ivo
  spotted that it does not line up with anything the reviewer has said, and he was
  right: **10,263,632 + 151,949 = 10,415,581**, which sits 187 from the raw count
  and 11,381 from the valid one. So line 1 tracks the raw count, and quoting the
  valid one reads as 11,568 records disappearing since his own last message. The
  187 is inside his merge, the same place the 116.35 equivalent-English gap lives
- **The lesson is narrower than "check the numbers" and worth keeping.** Both
  10,404,200 and 5,622,984.6434 came from the same measurement on 4 August and both
  were correct as measured. The error was pairing a validator-filtered record count
  with an unfiltered lineage, which no amount of re-running the calculator would
  have surfaced. **Reconciling against what the other side last said is a different
  check from verifying your own arithmetic**, and only the first one catches this
- **The increment was then checked against his actual annual files, which had never
  been done.** All 152,773 records compared line by line against his six files:
  **zero already present**. Our net-new definition rests on `verified_at` and the
  absence of a `prior_reused` marker, and neither knows what he holds: our store
  carries baseline releases only up to `merged260730`, while he has merged a round
  on top. The two could drift apart with nothing here looking wrong
- **Both checks now live in `scripts/round_figures.py --verify` and it exits
  non-zero on either**, alongside the existing check that his calculator agrees to
  0.0000 and rejects none of our records
- **Round after folding in the VPS journals:** 152,773 records, 105,676.0387
  equivalent-English, **1.879358%** growth, 122,381 distinct domains, 150,858 more
  dated but held back. Mean weight **0.6917** against last round's 0.6042, so this
  round beats 151,949 records on count and is **15.1% larger on equivalent-English**

## 2026-08-06 (projecting the round to Sunday, and two errors that cancelled)

- **Projection to Sun 9 Aug 12:00 UTC, the supervisor's own deadline (epoch
  1786276800), 72.5h out: +100,007 admitted pairs and +74,573 equivalent-English**,
  taking the round to 252,780 records and 180,249, a **3.206%** growth rate against
  the 5,622,984.6434 baseline. Range: 77,738 with no further stalls, 19,668 if the
  laptop stops now and only the VPS runs
- **Projected from the queue itself rather than from a trailing rate.** The target
  file is equivalent-English-ordered and `ark cdx` walks it in file order
  (`cli.py:629-643`), skipping domains already ANSWERED, so the next N lines are
  literally the next N queries. That makes the future readable instead of
  extrapolated. **The high-weight head is nearly spent on the local shard:** mean
  weight runs 0.973 for about 7 more hours, then decays to the .com floor of 0.632
  by roughly hour 22 and stays there. Quoting today's ~1,000 EE/h forward would
  have been wrong by a third
- **First error, mine: the VPS rate was 9% too high.** I computed it as
  `completed_batches * 300 / span`, but `cdx_gap_vps_20260806T004012Z.jsonl.gz`
  holds 5 lines, not 300. Weighting each interval by the closing journal's actual
  line count gives **288 domains/h, not 317**. Rule: never assume `-n` was reached
- **Second error, mine: the local rate blended two regimes.** There is a structural
  break at the batch dispatched 05:16 UTC (47 min against a ~14 min norm, 585
  throttles, 129/300 failures). Before it, 1,097 domains/h; after it, **954/h**,
  stable across 18 batches with no further escalation. Averaging across the break
  gave 974/h and quietly assumed a regime that has not recurred
- **Third correction, against both of the above: the .com body yields MORE than the
  .uk head, so the pair count was conservative.** Years found per answered domain
  is 3.849 for `.com` against 3.577 for `.uk/.au/.nz/.ie/.za`, a ratio of 1.076.
  The forward slice is .com-heavy where the measuring window was .uk-heavy, so
  pairs per domain rises from 1.118 to about 1.186 locally. **The two rate errors
  cost 8% and this recovers 4%**, which is why the first figure of 77,293 was only
  about 4% high rather than the 8.7% an audit that missed this effect concluded
- **What the projection does NOT rest on, all checked:** the queue does not run dry
  (225,642 and 236,952 still queued against ~86,000 consumption); the two shards
  are disjoint, `comm -12` returns 0; and **nothing else is feeding**, since all
  4,175 Usenet archives are processed with no download running. CDX is the only
  engine, so a stopped engine costs its full rate
- **The binding risk is power, not throughput.** `caffeinate -i` holds off idle
  sleep only: `pmset -g assertions` shows `PreventSystemSleep 0`, so a closed lid
  still sleeps, and the machine has been on battery for 42% of the last two days
  across 8 transitions. Local is 76% of the projection. Also worth an operational
  step rather than a number: the VPS journals must be rsynced and one maintain pass
  allowed to finish **before** the Sunday measurement, or roughly 700 EE of
  collected work sits outside the figure, rising to ~2,900 EE if the last pull is
  10 hours stale

## 2026-08-06 (the Usenet 330,000 EE projection is refuted, and why the error repeated)

Ivo asked for the projection to be re-measured before it was promised to the
reviewer. It does not survive.

- **The 5 August fit predicted ~466,000 net-new pairs / ~330,000 equivalent-English
  from the 761 groups of `uk.*`, `aus.*`, `can.*`. 740 of those 761 have since been
  processed, so the prediction has already been tested by reality.** Actual:
  **65,846 net-new admitted pairs, 46,565 equivalent-English**. The fit overstated
  by **7.1x on admitted pairs**. On the looser "found and not already held" basis it
  is 150,009 against 466,000, still **3.1x** over
- **Root cause, and it is not the exponent.** The fit came from 28 hand-picked
  probe groups (`uk.misc`, `uk.finance`, `aus.computers` and similar) which yielded
  720 net-new pairs per group. Measured over 3,594 real groups in deterministic
  random order, the corpus average is **122 found pairs and 76 equivalent-English
  per group**. The sample was **3 to 6x richer than the population it was
  extrapolated to**. The `g^0.909` exponent was roughly right; the constant was
  wrong, because the sample was chosen for being promising
- **A proper multi-point curve, built from the journals already on disk rather than
  by re-downloading, gives cumulative EE = `179.3 * n^0.896` over 1,200 to 3,594
  groups.** Marginal yield per 200-group batch runs 129, 93, 84, 77, 77, 52, 62, 80,
  64, 148, 62, 66, 120, 44, 63, 45, 53, 50 EE/group: noisy but plateauing near 50 to
  65, not collapsing. Saturation is mild. **`measure_usenet_decay.py` cannot produce
  this any more**, because it differences against the store and all 4,175 archives
  are now ingested, so every batch reads zero. The journals hold `group` per record,
  which makes the same measurement possible without touching the network
- **Why the earlier two-point tranche fit said `n^0.375` and was also wrong.** It
  used ADMITTED EE at 697 and 4,175 archives, and tranche 1 was the name-filtered
  announce/business selection whose dated fraction is far higher. So it conflated
  genuine saturation with a drop in the corroborated share. Measuring on the found
  basis separates the two
- **Half of what Usenet finds is not admitted.** 437,460 found pairs / 274,186 EE
  against 219,100 pairs / 137,867 EE admitted: **50.1%**. The other ~136,000 EE sits
  in the candidate pool awaiting corroboration. That is real inventory but it
  converts at roughly **0.358 EE per Internet Archive query** against the gap pool's
  **0.707**, so it is a slow reservoir, not a quick win, and the engines are
  correctly pointed at the gap pool for now
- **The decisive unknown has moved.** It is no longer the saturation exponent, it is
  **the quality of the 15,639 unprocessed groups**, which is a worse population than
  the processed one: the English, in-window hierarchies are largely done, and the
  5 August probe found 4,023,027 of 5,283,482 messages out of window with four of 28
  groups yielding exactly zero. The measured 76 EE/group cannot be carried over.
  Settling this needs a random sample of the UNPROCESSED remainder, which is a small
  download, and no projection should be given to the reviewer before it exists
- **Consequence for the reviewer's 10% request.** 10% is 562,298 EE; the round holds
  105,676 and projects 180,249 by Sunday. Known sources do not close a 382,049 EE
  gap on a short timeline, so the honest reply is a trajectory with a schedule rather
  than agreement to "ASAP"
- **Consequence for the harness decision, which this inverts.** The earlier
  recommendation put the deterministic bulk pipeline first because Usenet looked
  worth 330,000 EE. At 46,565 measured, the known reservoir is insufficient by
  itself, so the higher-value build is the **agent-driven discovery harness**: the
  10% now requires new source classes, not more of a source already worked

## 2026-08-06 (the stratified sample: what the 382 GB of unworked Usenet is worth)

- **Sampling design, chosen because the last projection died of a bad sample.**
  The 15,058 unprocessed groups have a median size of 1.0 MB and a mean of 25.4 MB,
  so a uniform draw is size-light against a heavy tail. Sampled 12 groups from each
  of four size strata instead, drawn by `blake2b` order so the pick is deterministic
  and not chosen for looking promising. 48 groups, 2.3 GB
- **`probe_usenet_groups.py` has a default 200 MB cap and it silently skipped the
  five largest groups in the sample**, all in stratum D: `alt.religion.scientology`,
  `alt.revisionism`, `alt.politics.democrat`, `soc.culture.yugoslavia`,
  `rec.motorcycles`. Stratum D holds 305 of the 382 GB, so measuring it with its top
  members dropped would have understated the one band that decides the answer.
  Re-fetched with `--max-mb 4000`. **The same cap was in force for the 5 August
  probe**, which skipped `aus.general`, `can.general`, `rec.arts.books`,
  `misc.consumers` and `soc.culture.british`. So that probe was biased in both
  directions at once: hand-picked rich groups, minus its biggest archives
- **Measured, per group, against the current store:** A `<0.5MB` 5.2 corroborated
  EE, B `0.5-5MB` 28.0, C `5-50MB` 145.2, D `>50MB` 414.2. 54.8% of messages are out
  of window, close to the 76% the 5 August probe saw
- **Scaling those linearly gives 1,520,908 EE (27 points) and is wrong**, because
  2,081 groups overlap each other; the sample only measures one group's yield against
  the store. Fitting saturation within each stratum failed too: 12 points each, with
  runs of identical values, and stratum A came out **superlinear at b=1.246**. The
  exponent dominates the answer and a 12-group sample cannot pin it
- **So the exponent was measured where the data already is.** The remainder is 82.8%
  `alt.*` and there are 2,365 processed `alt.*` groups on disk with pairs. Their
  cumulative corroborated-EE curve over 24 points fits **b = 0.746**. That is the
  population that actually matters and it cost no bandwidth
- **Central estimate: 385,683 EE, 6.9 points, from the 15,058 unprocessed groups.**
  With Sunday's projected 3.2% that is **10.1%**, which is the reviewer's target.
  Band on the exponent: b=0.65 gives 4.1 points, b=0.85 gives 12.0, so the honest
  range for the round total is **7.3% to 15.2%**
- **Where the value sits, and the download order that follows.** Stratum D is 60.3%
  of the value but only 762 EE per GB; C is 33.5% at 1,814 EE/GB; A and B together
  are 6% of the value but 5.9 GB and the best ratio on the board at 7,083 and 3,388
  EE/GB. So take **A, B, C first: 77 GB for 153,025 EE**, then decide on D's 305 GB
  for 232,658 EE
- **Feasibility: this is one night, not a project.** 382 GB at 20 MB/s is about
  5.3 hours, and splitting 4,175 archives took 54 minutes so 15,058 is roughly
  3.3 hours of CPU. Disk is 571 GB free, and archives can be deleted after splitting
  because the journals carry the evidence and `.processed` carries the ledger
- **Caveats that belong next to the number.** b=0.746 comes from PROCESSED `alt.*`
  groups, which were selected and may be richer than what is left; each stratum's
  anchor rests on 12 groups, and stratum D's total came mostly from 4 of its 12; and
  all of the above is corroborated EE, the half that enters annual files at once.
  The uncorroborated half is roughly 1.45x more, and it lands in the candidate pool

## 2026-08-06/07 (the bulk Usenet night: what worked, and the six hours that did not)

- **Round moved from 1.8794% to 3.3384%**, 152,773 pairs / 105,676.0 EE to
  **285,192 pairs / 187,719.4 EE**. Gained overnight: **132,419 pairs and
  82,043.4 equivalent-English, +1.4591 points**. 11,732 of 19,233 catalogue
  archives now processed, against 4,175 at the start of the night
- **Disk: 78 GB reclaimed before starting, all of it redownloadable or
  regenerable.** Arquivo `IA.cdxj` at 47 GB (documented `curl` at
  `docs/sources.md:185`; `Roteiro.cdxj` kept, it is 13 MB), seven superseded
  `ark.duckdb.pre-*` rollback copies at 31 GB, and the delivery tarball. This is
  what the architecture is for: the store rebuilds from journals, and the delivery
  rebuilds from the provenance export
- **The date-gated selector does not work and the negative result is the output.**
  A `.mbox.zip` inflates from its first byte, so a 256 KB range request should have
  dated each group's start for nothing, skipping most of a 382 GB download.
  Validated against the 48 sampled groups whose true yield was already measured, it
  **discarded 21 of them holding 88% of the sample's equivalent-English**. The
  archives are stored **newest-first**: `comp.cad.autocad` opens on 2011 and does
  not reach 2001 until 77.8% in. A prefix can only prove a group died before the
  window, which rejects 1 in 48. The tail that would answer the real question needs
  the whole file, because deflate does not decompress from the middle. Kept as
  `scripts/gate_usenet_groups.py` so nobody rebuilds it
- **Two throughput fixes, both measured.** `probe_usenet_groups.py` was serial at
  **0.6 groups/s**, which is six hours of pure latency for 77 GB the link carries in
  under one; `--workers 16` gives 9/s and 26.5 MB/s sustained. `split_usenet.py` was
  serial regex on a 14-core box; `--workers` puts the per-archive parse in a process
  pool and merges results in archive order, so output is **byte-identical** to
  serial, verified on 14 archives by sha1 on both journals, 21s to 9s. Then the
  maintain loop's 900s cadence became the limit, since 800 archives split in 30, so
  it was dropped to 150s
- **Stratum A is worthless and stratum C is the whole prize.** A's first 800
  archives yielded **11 admitted pairs**, with 90% of messages out of window. One
  2,483-archive C batch yielded **72,314 admitted pairs** and enqueued 106,184
  candidates. The download had been ordered smallest-first, which put the worthless
  band ahead of the valuable one; reordering to C, B, A was the single largest
  scheduling gain of the night
- **Six hours produced nothing, and the parser bug was the smaller half of why.**
  `Message.get` returns a `Header` rather than a `str` when the value is RFC 2047
  encoded, and `Header` has no `.strip()`, so `message_year` raised
  `AttributeError`. Latent and pre-existing: the serial path calls the same function
  and would have died identically, and 8,258 archives passed before one carried such
  a date. **The cost came from the batch shape.** `ingest_new_usenet.sh` splits every
  pending archive in ONE call, so one bad file aborted all 2,500, left them unmarked
  by design, and the maintain loop retried the identical batch every 150 seconds
  from 23:47 to 05:50. Roughly 145 retries, no progress, and no alarm anywhere: the
  27-minute checkpoints watched processes that were all healthily alive, and the
  progress log recorded an unchanging `processed=8258` that nothing was reading
- **So the guard that is missing is per-archive isolation, not a better parser.**
  One bad file should skip itself and be recorded, not void a batch. The maintain
  loop also needs a no-progress alarm: liveness is not progress, and every check
  that night confirmed liveness. After the one-line fix the same batch went straight
  through for 35,626 admitted pairs

## 2026-08-07 (the candidate pool is a million names, and most of them are not real)

- **`ark stats` reports a candidate pool of 1,022,127 and 1,021,297 of them are
  `usenet_mention`**, the uncorroborated half of the Usenet split: a domain that
  appears in a dated post but that no other source attests. The design routes them
  here rather than into annual files precisely because Usenet URLs are human-typed,
  and the bulk ingest multiplied the pool fourfold overnight
- **A large share of them never existed.** Sampling the pool turns up
  `mqegamrfaj.mil`, `rrkdpchn.mil`, `ixpaolw.mil`, `fkvgjq.com`,
  `gafbeehidbv.com`, `idiotsandliars.gov`, `get-that-spam-away-from-me.com`. These
  are **addresses munged against harvesters**, which was routine Usenet practice, and
  the domain part of a munged address parses as a perfectly well-formed name.
  **16.6% (169,893) are machine-generated on a deliberately conservative test**
  (no vowel in the second-level label, or a run of five or more consonants), and that
  is a floor: it does not catch pronounceable munges, of which `spam` alone appears
  in 36,212 names and `nospam` in 14,980. `.mil` at 29,631 and `.gov` at 29,760
  candidate domains is by itself proof of the problem, since neither TLD has
  anywhere near that many registrable names
- **Nothing has leaked into the deliverable.** `link_target` is candidate-only, so
  none of this can back an annual assignment, and `ark check` passes all twelve
  invariants including `no_candidate_leakage`. The cost is not contamination, it is
  that the capture engine is being pointed at a queue where a large fraction of the
  targets cannot possibly answer
- **`ark stats` now reports equivalent-English**, which it did not, so the scoreboard
  could not be read against the metric the round is actually scored on
- **And it exposed a trap worth naming, the same shape as the line-1 error.**
  "Net-new" means "carries no `prior_reused` evidence", and our store's baseline
  releases stop at `merged260730` while the reviewer has merged a round on top. So
  net-new is **614,413 pairs / 384,193.6292 EE**, of which **151,949 / 91,814.6880 is
  the round he already credited on 2 August**. Dividing the whole of it by his
  baseline gives 6.8326% and counts that round twice. The uncredited increment is
  **462,464 pairs / 292,378.9412 EE / 5.1997%**, and that is the only figure that may
  be quoted to him. The output now labels it `quote THIS as the increment` and states
  what was subtracted. It reproduces `scripts/round_figures.py` exactly, which is two
  independent code paths agreeing
- **The candidate pool's equivalent-English is reported as an explicit UPPER BOUND**,
  648,508, assuming every held name is real and earns exactly one year. Given the
  munging above, the realised figure will be a fraction of it, and the line says so

## 2026-08-07 (the 2 August baseline was never ingested, and what that cost)

- **`merged260802-2` sat on disk for five days without being loaded.** No decision
  was recorded anywhere; it was an omission. The mechanism already existed and had
  been used twice, `--marker-prefix` having loaded `merged260727` and `merged260730`
  under their own namespaces, and `round_figures.py` was already READING the 2 August
  files for its disjointness check while the store's baseline stopped two releases
  earlier
- **The cost was that net-new silently included work the reviewer already holds.**
  `ark stats` reported 614,413 net-new pairs of which 151,949 were the round he
  credited on 2 August, so its growth figure read 6.8326% where the honest number was
  5.1997%. This is the same failure shape as the line-1 error: not a wrong
  calculation, a right calculation against a stale reference
- **Measured before ingesting, because the risk was suppressing real claims.** His
  files hold hostnames and ours hold registrable domains, so `www.foo.com` on his
  side could mark our `foo.com` as baseline. Normalising his 10,415,768 host records
  the way we normalise ours gives 8,785,620 distinct (domain, year), and the overlap
  with our 794,097 net-new pairs was **exactly 151,949**, the credited round and not
  one pair more. So the hostname-folding risk was zero in practice
- **Ingested under marker `merged260802`: exactly 151,949 pairs reclassified**,
  matching the prediction to the row, plus 166 pairs he holds that we did not.
  12,572 of his lines were rejected by our validator, consistent with the 11,568
  found on 4 August
- **`ark check` then failed `additions_not_double_counted` with exactly 151,949
  offending**, which is the invariant doing its job: the exported annual files
  predated the ingest and still listed pairs that had just become baseline. The store
  was right and the export was stale. `ark export` plus `ark lang-report` fixed it and
  all twelve now pass
- **The fix is structural rather than a constant.** `src/ark/baseline.py` now holds
  which release is current, and `ingest-legacy`, `legacy-review`, `ark stats` and
  `round_figures.py` all read it, so the ingest default and the reported growth rate
  cannot drift apart. The hardcoded `ALREADY_CREDITED_EE` that patched this an hour
  earlier is gone: a constant needing a hand edit every time he merges fails silently,
  and it fails in our favour, which is worse than the bug it patched
- **Round after all of it: 648,249 pairs, 399,409.7010 equivalent-English, 7.1032%.**
  `ark stats` and `round_figures.py` agree to the digit from independent code paths

## 2026-08-07 (what the existing pools can still deliver, and by when)

- **Question: leaving both CDX engines running on the pools that already exist, when
  do we reach the reviewer's 10%?** Answered by integrating the remaining queue in
  its own order rather than extrapolating a trailing rate, because both queues are
  sorted best-first and a trailing rate measures where the engines have been
- **Three inputs, all measured, none assumed.** Realisation, from the ingest ledger:
  a gap query writes **31.6% of the in-window years it finds** as net-new pairs
  (27.1% on the last ten batches, the queue having descended), while a candidate-pool
  query writes **100%**, because those domains hold no year at all. Throughput, from
  journal timestamps over long windows rather than fast ones: local **916 q/h**
  sustained over 27.9h on gaps and **562 q/h** on the pool, VPS **262 q/h** over
  42.4h. Stock, from `sandwich_gap_domains` against the live store
- **The queue's own sort key predicts realised yield almost exactly.** Recent gap
  batches return 0.974 net-new pairs per query against 1.023 bracketed slots per
  queued domain, so realised equivalent-English is **0.95x the key**, slightly
  conservative. That is what makes an exact integration possible: every remaining
  domain's value is known, and the engines consume them in that order
- **Ceilings. The gap queue in full is 247,540 EE, 4.40 points. The curated
  candidate pool in full is 42,710 EE, 0.76 points.** With today's 7.1555% that caps
  the existing pools at about **12.3%**, so 10% is reachable but needs roughly half
  the gap queue, 250,000 more queries
- **Time. As configured this morning, 21.1 days. With the local engine moved back to
  gaps, 9.5 days.** The gap between those two numbers is the whole finding: the local
  engine has been on the candidate pool since 07:06 CEST, where it earns 0.476 EE per
  query at 562 q/h, against 0.95 EE per query at 916 q/h on gaps. Same machine, same
  archive, **3.3x the equivalent-English per hour**
- **The 50/50 shard split predates the speed gap between the machines** and now costs
  about 20 hours: the MacBook is four times the VPS, so half the queue each leaves it
  deep in its own cheap tail while the expensive head of the other half is untouched.
  A 78/22 split matched to measured throughput reaches 10% in 8.7 days
- **The shard files are stale in a way that lowers the ceiling below the goal.**
  They were written on 5 August, before 579,712 Usenet pairs landed, and Usenet
  created gaps as well as filling them. **102,628 gap targets worth 63,333 EE exist in
  the store and in neither shard file.** Working only the 5 August lists caps the gap
  queue at 187,374 EE, which puts the ceiling at **10.49%** and leaves no margin.
  Regenerating with `just gap-shards` raises it to 11.56% and is worth +5,703 EE over
  the first 50,000 queries on its own, the new arrivals being better than average
  (mean key 0.617 against 0.537)
- **Round at the time of measuring: 648,813 pairs, 402,354.7 EE, 7.1555%**, after the
  eleven VPS journals stranded by the VPN outage were rsynced home and ingested

## 2026-08-07 (one queue instead of two, and shares sized by engine speed)

- **The two populations were two lists, and the choice between them was being made
  by hand.** Ordering *within* `gap_candidates.txt` and *within* `pool_candidates.txt`
  had both been thought about carefully; the allocation *between* them had not, and
  that was the more expensive of the two. The MacBook spent this morning on
  candidate-pool targets worth 0.476 equivalent-English per query while gap targets
  worth twice that sat in the other file
- **There is now one queue, scored on the only scale that decides the allocation:
  expected net-new equivalent-English per archive query.** A gap target scores
  `realisation x English share x bracketed years it could fill`; a pool target scores
  `P(hit) x English share x years a hit returns`. `scripts/build_query_queue.py`
- **Both multipliers are measured, not assumed, and printed with the queue.**
  Realisation 0.95, from the ingest ledger over 137 journals: a gap query writes 31.6%
  of the in-window years it finds as net-new pairs, which is 0.974 net-new pairs per
  query against 1.023 bracketed slots per queued domain. Years per pool hit 1.580,
  from the journals. A pool hit realises 100% because the domain held no year at all
- **The hit rate that scores the pool must be measured over the pool alone.** A gap
  domain answers 85-99% and a pool domain 41%, so mixing them would roughly double the
  pool's apparent value and lift its whole tail to the head of the queue. The old code
  got this for free by globbing `cdx_pool_*`; the merged queue's journals carry both
  populations, so the manifest now records which population each target came from and
  the estimator restricts to it. Same trap as the line-1 and stale-baseline errors: a
  correct calculation over the wrong reference set
- **Era eligibility stays a hard gate ahead of the score.** The English-share model is
  built from 2024 crawl data and scores today's brand gTLDs near 100%, so Usenet header
  noise would otherwise sort to the very top of a list meant to hold the best targets
- **Shares are now sized by measured throughput, 78/22, not split evenly.** The MacBook
  sustains 916 queries an hour over 27.9h against the VPS's 262 over 42.4h. An even
  split leaves the fast machine grinding its own cheap tail while the expensive head of
  the other half is untouched, worth about 20 hours. `take_weighted_shard` keeps the
  content-hash assignment for the reason `take_shard` gives, and takes two bytes rather
  than one so 78/22 lands within a tenth of a percent. Because the hash is independent
  of the ordering, each share is a representative sample of the value curve: measured
  78.1/21.9 by count and 78.0/22.0 by value
- **Sustained rates, not fast windows.** The local engine's 1,188 q/h over a 1.8h night
  window became 916 over 27.9h. Quoting the fast one would have shortened every
  projection by a fifth
- **Switchover cost nothing.** Killing the supervisors leaves the in-flight `ark cdx`
  child to finish and publish; both partial batches (140 and 172 lines) landed. The
  shares are written with every already-answered domain removed, so re-sharding cannot
  make a machine re-ask a name the other settled, which is what made changing the split
  safe at all
- **Queue: 1,712,271 targets, 1,618,286 of them worth something.** 469,872 gap and
  1,148,414 pool, the pool having grown from 97,219 to 1,148,414 because the bulk Usenet
  run added 1.15M mentions and the list predated it. Whole-queue expected value 741,355
  EE against 159,468 needed, so the target arrives at **14% of the queue** rather than
  by scraping the bottom of it
- **Projection: 222,731 queries, 7.9 days at gap speed, 8.8 blended.** 27% of those
  queries are pool targets and a pool query runs at 0.61x the speed of a gap query, so
  quoting the gap rate over a mixed queue would understate the time by about a fifth
- **The one number here that is still a projection rather than a measurement** is the
  hit rate applied to 1.15M Usenet mentions that no query has touched: it is inherited
  from cells measured on the pre-bulk pool. The manifest records the predicted score of
  every target so the next few hours of answers can be checked against it

## 2026-08-07 (should the Usenet candidate pool be dropped for provenance?)

- **The question was whether to split the populations again and fill the round from
  bracketed gap fill alone**, on the grounds that the candidate pool is Usenet header
  munging and gap fill is not. Measured rather than argued, because the composition
  claim and the risk claim turn out to have different answers
- **The composition claim is right.** Names carrying a munging marker (`nospam`,
  `removethis`, `delthis` and relatives) are 3.98% of the candidate pool and 5.61% of
  the pool targets inside the first 250,000 queries, against **0.01%** of the gap
  targets in the same stretch. `iamspamboy.co.uk`, `delthis.co.uk` and
  `spamnicotine.co.uk` all sit in the pool head
- **The risk claim is not.** A pool domain enters nothing until the archive returns an
  in-window capture for it, so the pool is a work list and not evidence. End to end:
  **3.98% marker-matching in the pool, 0.0068% in the 5,503,423 domains shipped**, a
  585x reduction. And that residue is almost all false positives of the marker regex
  itself: `abacospamotel.com` is Abaco Spa Motel, `alwayspamperedpet.com` is always
  pampered pet, `americanspamag.com` is American Spa Mag. Real businesses with real
  captures. `dumicsamvfs.mil` costs one query and returns nothing
- **The cost of the contamination is queries, not correctness, and it is already
  priced.** It is why a pool target scores 0.83 against a gap target's 1.15 to 1.88,
  and why the first pool target sits at **queue position 24,799** with every slot above
  it held by gap fill
- **Going gap-only would have cost the reserve.** The whole gap stock is 247,366 EE,
  4.40 points, against 2.84 needed, so gap fill alone reaches 10% only by consuming
  52% of the queue on the scored estimate and 65% if head realisation is the 81%
  currently being measured: 8.6 to 10.8 days against the merged queue's 8.8, and
  nothing behind it afterwards
- **Decision: keep the merged queue unfiltered.** A marker exclusion on the pool half
  was offered at a cost of 4.3% of pool value and declined, the capture requirement
  being filter enough. Nothing was rebuilt or restarted, so the decision cost no
  collection time
- **Timing note worth keeping.** Both engines were 21 hours from touching a pool target
  when the question was raised, so there was no cost to answering it with measurements
  instead of quickly. Worth checking that distance before treating a queue question as
  urgent

## 2026-08-07 (the queue's realisation multiplier was measured and is wrong)

- **First merged-queue batch, scored against the store: 600 queries, 769 net-new
  pairs, 659.9 equivalent-English against 987.7 predicted. 66.8%.** Not the mean-weight
  approximation, the exact pairs those domains gained, weighted individually
- **The cause is that the queue values a bracketed slot as if a capture always fills
  it.** It does not. Per slot the fill rate is **64.1%**, and the shape says why: of 600
  two-slot domains, 104 filled neither, 225 filled one, 269 filled both. Independent
  slots at that rate would predict 34% filling both against 45% observed, so a domain
  is either well archived or it is not, and the correlation is at the domain rather
  than the slot
- **The 0.95 multiplier was an artifact of dividing by the wrong denominator.** It came
  from 0.974 net-new pairs per query against 1.023 bracketed slots per queued domain,
  but that 1.023 is the mean of the queue as it stands NOW, after the high-slot domains
  have been consumed. The queries that produced 0.974 were working a queue whose mean
  was higher, so the true per-slot rate was always nearer 0.64. Same error shape as
  line 1 and the stale baseline: a correct division by a reference set that had moved
- **What saves the estimate is that the remaining queue is almost all single-slot.**
  458,707 domains with one bracketed slot against 11,170 with two, so the overvaluation
  touches 9,936 EE of 247,366, about 4% of the gap queue. The 66.8% measured on a
  two-slot head does not automatically transfer to a one-slot bulk, and whether it does
  is now the single biggest open number in the projection
- **Both readings are live and the band is wide.** If one-slot domains fill at 64% like
  two-slot ones, the whole remaining gap queue is worth about 166,600 EE against 159,468
  needed, and the merged queue reaches 10% in roughly 13 days. If they fill nearer the
  historical rate, it is about 9. Nothing else in the projection is this uncertain
- **It also retroactively settles the gap-only question.** At 64% per slot the entire
  gap stock is 2.96 points against the 2.84 needed, so filling the round from bracketed
  gap fill alone would have required about 96% of the queue and left no margin at all.
  The decision to keep the pool was right for a reason not known when it was taken
- **Not rebuilding the queue yet, deliberately.** If gap realisation is 0.67 while pool
  realisation is 1.00 by construction, the fair comparison multiplies every gap score by
  0.705, which would rank the entire one-slot gap population BELOW the `.uk` pool head
  at 0.829. That is a large reordering to make on one batch of one slot-count. The
  engines are currently working the two-slot head, which ranks first under either model,
  so waiting costs nothing and the next few thousand queries supply the missing number

## 2026-08-07 (the open realisation question, answered: the bulk is fine)

- **Measured over 6,168 answered domains, split by how many bracketed slots the
  domain offers**, which is what the previous entry said was the missing number:

      slots  domains  offered  filled  per slot  act/pred
          1      475      475     421     88.6%     93.3%
          2    5,693   11,386   7,594     66.7%     70.0%

- **The 66.8% scare was specific to two-slot domains and does not generalise.**
  One-slot domains realise 93.3% of their predicted equivalent-English, so the 0.95
  the queue assumed was very nearly right for them. Since the remaining queue is
  458,707 one-slot against 11,170 two-slot, the whole gap population is worth about
  223,000 EE rather than the 166,600 the pessimistic reading implied
- **Projection holds: 232,513 queries, 8.0 days at gap speed, 8.9 blended**, against
  the 8.8 estimated before any of this was measured. Throughput re-measured over the
  day: local 930 q/h, VPS 278 q/h
- **`GAP_REALISATION` is replaced by a per-slot `GAP_FILL_RATE`**, 0.886 for one slot
  and 0.667 for two, with 0.60 for the deeper counts the queue does not currently hold.
  A flat rate was the wrong shape, not just the wrong number
- **Not rebuilding the live queue for it.** The correction only reorders high-weight
  one-slot domains above low-weight two-slot ones, and with roughly 5,500 two-slot
  domains left unanswered that is a rounding error against a 232,000-query journey.
  The corrected constant applies at the next rebuild, which is due after the next
  large ingest anyway
- **The VPS ran straight through the evening's outage**, as designed: `setsid`,
  own deadline, seven journals waiting on its disk. All fetched and ingested,
  2,254 net-new pairs from 2,100 queries. Stopping and restarting the laptop cost
  the round nothing
- **Round: 408,750.7 EE = 7.2693%**, short of the 10% goal by 153,548 EE

## 2026-08-08 (source sprint: ten families probed, one worth building)

- **Ten untried source families were probed in parallel and the positives adversarially
  verified.** Every probe differenced against a frozen snapshot of the store (5,503,423 held
  domains, 9,455,478 pairs) rather than the live database, so none of them could collide with
  the ingest loop or each other. Verdicts are in `docs/sources.md`
- **Nine are dead or deferred and together are worth about six hours of the engines already
  running.** The full rows are in the rejected table; the pattern is that a curated directory,
  an award list and an institutional link page all select for authority, and authoritative sites
  are exactly what a CDX-derived baseline holds first. Novelty ran 0.5% to 2.4%
- **One is worth 32,647 equivalent-English and it was already on disk.**
  `data/raw/usenet/comp.mail.maps.mbox.zip`, 205,143,394 bytes, has been marked done in
  `.processed` since 7 August. `domains_in_message` reads http(s) URLs, bare `www.` hosts and the
  `From:` address, and a UUCP map entry contains none of those, so **1,480,910 `#N` registry lines
  across 23,768 postings were parsed as the sender's domain and discarded.** Nothing needed
  downloading and nothing needed re-crawling
- **Three of the four verifications overturned their probe, all in the same direction and for the
  same reason: a raw set difference quoted as yield.** Research crawl datasets 6,137 EE claimed
  against +374 net once archive-query displacement was priced; regional portals 5,500 against
  ~1,200 once the corroboration split was applied; search-engine directories 21,000 against 9,503
  once the sample was drawn uniformly instead of hand-picked. **The family that survived is the
  one whose value is not denominated in archive requests.** That is the rule worth keeping: a
  source costing one `web.archive.org` request per unit must be scored marginally against
  `queue_manifest.tsv.gz` and benchmarked against the 0.6005 marginal displaced query, not quoted
  gross
- **DECISION REQUIRED, and it is a policy call rather than a measurement.** Applied literally, the
  Usenet corroboration gate would send every never-before-seen map name to `link_target`, which is
  candidate-only, leaving ~14,700 EE. Classifying the registry-generated entries as master evidence
  gives 32,647. **I have implemented the second reading** and the argument is that a URL typed into
  a Usenet post and a `.CA` registry dump are not the same artifact: the map file declares
  `#R Automatically generated from a .CA domain registration form`, is regenerated from the live
  registration database at posting time, and carries the registrar's own `approved:` date. That is
  the AFNIC `.fr` creation-date file's shape, not a posted URL's, so `artifact_listing` for the
  posting date and `whois_creation` for the approval date. **Ivo to confirm or overrule.** It
  clears 10,000 EE either way, which is why it was built before the call was made
- **The provenance gate inside it is not optional and is worth minus 578.6 EE.** Only
  `.CA`-registry-generated files are regenerated at posting time; classic hand-maintained maps are
  reposted containers whose entries refresh only when a site admin resubmits, and of 12,486
  in-window entries carrying a `#W` stamp only 1,031 are within a year of the posting date. Those
  are candidate-only. Verified rather than assumed: all 8,309 in-window registry postings carry an
  internal generation stamp in the same year as their `Date:` header, 569,157 of 569,157 entries at
  gap zero, and all 118,766 `approved:`/`received:` lines occur inside registry-generated files and
  none anywhere else
- **The finding does not generalise, which was checked rather than hoped.** The `#N` format is
  confined to one group: `alt.bbs.lists` 36 lines, `comp.mail.uucp` 64, `news.lists` 0, against
  `comp.mail.maps`' 1,480,910. A generic record-format extractor over the rest of the corpus is
  worth at most 193 EE and its sample is visibly contaminated. Fix the `#N` case and stop
- **Trap worth naming: the edit-distance-1 typo test is meaningless without a control.** It reports
  26-40% of net-new names within one edit of a held name, which reads as catastrophic. The baseline
  for names the project already believes is **41.7%**, because the held set has 5.5M entries. Only
  the excess counts, and here there was none

## 2026-08-08 (prioritising multi-source candidates: measured, and there are none)

- **The feedback asks to prioritise "candidates found in more than one independent
  directory", so with the candidate pool freshly grown to 2.47M names it was worth
  measuring how many qualify. Almost none do.** Counted by distinct provenance
  lineage: **2,474,139 candidates rest on one lineage, 451 on two, and exactly one
  on three**
- **The reason is structural rather than disappointing, and it validates a call made
  earlier the same day.** The pool is overwhelmingly Usenet-derived, and the recovered
  addresses were deliberately filed under the `usenet` lineage because a body address
  and an announcement post in the same message are one observation, not two. Having
  made that call correctly, the two cannot then corroborate each other. Filing them as
  their own family would have manufactured 1.4M fake corroborations and made this idea
  look brilliant
- **So no queue reweighting is worth building.** 451 domains cannot move a metric that
  needs 51,909 equivalent-English. The rule stays: a candidate earns its year from a
  capture, and the queue is ordered by expected equivalent-English per query
- **Also checked and closed: whether the click-tracker fix could recover value from
  captures already downloaded.** It cannot. The expansion journals store the extracted
  `domains` list and not the page body, and the whole `data/raw/expand` tree is 132 KB,
  so there is nothing to re-parse. The fix helps future expansion runs only

## 2026-08-08 (the header projection was wrong by 10x, and the reason is worth more than the source)

- **Projected ~10,889 equivalent-English, delivered 1,038.4.** Machine-composed headers
  (`Message-ID`, `Reply-To`, `Sender`, `NNTP-Posting-Host`) across the whole 404.8 GB
  corpus gave 1,025,582 pairs, of which 207,980 corroborated and **2,869 net-new**
- **The projection was not wrong because the sample was small. It was wrong because the
  reference set moved underneath it.** The header sample was measured against the
  snapshot exported at 04:12, and the recovered-address ingest at 07:17 wrote 102,577
  new pairs into the store. The two seams draw from the same messages and overlap
  almost entirely, so nearly everything the header sample counted as net-new had
  already been ingested by the time the header run finished
- **The ingest itself printed the proof: 207,980 journal lines produced 19,224 evidence
  rows.** 91% deduplicated against evidence the address run had already written
- **This is the same error the project has now made four times, in four costumes.** The
  line-1 count, the stale baseline, the flat gap-realisation denominator, and now a
  frozen snapshot used after the store moved past it. Every one was a correct
  calculation against a reference set that had changed. **Rule: a snapshot is only
  valid until the next ingest. Re-export it after any ingest, or measure against the
  store.**
- **Keep the source anyway.** 1,038.4 EE for a run that cost nothing but idle CPU is
  still positive, `ark check` passes all twelve, and the header seam is now exhausted
  and will not be re-proposed
- **What it does not change: the address finding stands.** That one was measured against
  the store at split time, not against the stale snapshot, which is why its 62,820.7 EE
  was accurate to the digit

## 2026-08-08 (the queue rebuilt, and why its headline projection is not quoted)

- **Rebuilt against today's store because the live queue was written on 7 August and is
  structurally blind to the 145,644 pairs added since.** New pairs create bracketed gaps
  as well as filling them, and this exact staleness cost the 5 August queue 102,628
  targets worth 63,333 key equivalent-English
- **New queue: 464,625 gap targets and 2,402,792 pool targets, whole-queue expected value
  1,465,811 EE.** The pool grew tenfold because the recovered addresses put 1.47M names
  into the candidate pool and the header run added more
- **It claims the round's shortfall is 2% of the queue away, 2.9 days. That number is not
  quoted anywhere and should not be.** The head is sound: the first entries are the same
  `.uk` names as before, scored at the **measured** `(usenet_mention, uk)` cell rate of
  0.534. But by 250,000 queries the queue is 97% pool targets, and the address-derived
  candidates are a brand-new source with no measured hit rate, so they fall back to the
  **pool-wide 51.7%** measured on a different population. An unmeasured rate applied to
  2.4M targets is exactly the shape of the estimate that produced 27,276-against-53
- **So it is being settled empirically rather than argued.** The local engine picks the
  new queue up at its next batch; the VPS is deliberately **left on its 7 August shard**
  rather than shipped the new one. That makes the next hour a natural A/B test between
  the two queues on two machines, at no cost, and the comparison decides whether the new
  ordering is kept or the hit rate is re-estimated and the queue rebuilt
- **The downside is bounded and worth naming.** If the new candidates hit poorly, the cost
  is an hour or two of one engine's time and the fix is a rebuild with a measured rate

## 2026-08-08 (two invariants still skip, and the reason is a real coverage gap)

- **`english_files_hold_only_verified_english` and `the_two_shipped_sets_are_disjoint`
  have skipped all day, and running `ark export` did not change that.** The exported
  English annual files are empty, so the checks correctly have nothing to read. They are
  skipping rather than failing, which is the honest behaviour, but "ALL PASS" over ten of
  twelve should not be read as twelve
- **The cause is coverage, not a defect.** The store holds 9,234 `english` verdicts, all
  at the current `ENGINE_VERSION = 3`, so none are stale. They sit on baseline domains
  classified in early August. **All 824,381 of this round's additions are
  language-unchecked**, and today's 147,502 new pairs are the largest part of that
- **It does not affect the reported increment.** Equivalent-English is computed from the
  right-most TLD's English share, which needs no per-domain classification, so the
  9.2626% figure is unaffected. What is missing is the separate page-level verification
  the feedback asks for alongside it, and the shipped English/unverified partition
  therefore currently puts everything in `unverified`
- **The cost of closing it is why it is open.** `ark lang` yields one classified pair per
  three archive requests and adds no year, against the gap engine's 0.5 net-new domains
  and 0.8 net-new pairs per request. With 824,381 pairs to classify it is months of
  archive budget, and it competes directly with the collection that is still producing.
  Worth raising with the reviewer as a scope question rather than silently absorbing:
  the metric he scores on does not need it, and the standard he wrote does

## 2026-08-08 (the rebuilt queue measured: no better, and the projection was inflated)

- **Measured realised equivalent-English per query across the cutover, same machine,
  same archive, 600-query batches:**

      OLD queue  07:58  0.8337 EE/query   514 net-new pairs
      OLD queue  08:33  0.9460 EE/query   586
      OLD queue  09:02  0.9876 EE/query   612
      NEW queue  09:31  0.8010 EE/query   592

- **The rebuild is not an improvement. On one batch it is slightly worse**, 0.801 against
  an old-queue mean of 0.922. Net-new pairs are comparable (592 against 514-612); what
  falls is the mean English weight of what it finds, 0.812 against 0.968, because the new
  head is pool targets drawn from Usenet addresses rather than the `.uk`-heavy gap
  population
- **So the queue's own projection of 2% of the queue and 2.9 days was inflated, exactly
  as suspected when it was written.** It rested on applying the pool-wide 51.7% hit rate
  to 2.4M address-derived candidates that no query had touched. Not quoting it was right;
  the discipline that mattered was refusing to report a number the moment it was
  attractive
- **One batch against three is a thin sample and the difference is small, so this is not
  a reason to revert.** It is a reason to re-score. `build_pool_candidates.hit_rates`
  needs `MIN_SAMPLE = 25` answers in a `(source, TLD)` cell before it trusts a measured
  rate over the fallback, and the address candidates now have their first few hundred
  answers. **Rebuild the queue again once those cells are populated**, and the ordering
  will rest on a measured rate rather than an inherited one
- **The experiment cost nothing because it was set up before the result was wanted.** The
  VPS was deliberately left on the 7 August shard, and the local machine's own three
  preceding batches turned out to be the better control anyway: same host, same throttle
  regime, same hour

## 2026-08-08 (the Usenet `Path:` header: 7.1 million parsed hops, 13.89 equivalent-English)

- **Assessed and rejected.** `Path:` records the relay chain that carried an article, and
  the article's own `Date:` dates it, so on paper it is the same shape as every Usenet
  seam that has worked: machine-written, item-level, already paid for on disk. It was
  measured on a 400-archive random sample, **6.60 GB, 9,136,539 messages of which
  4,156,456 in window, 7,201 (domain, year) pairs, 6,398 corroborated, 49 not yet held,
  worth 13.89 equivalent-English**
- **The parser is not the reason, and that was checked first so the verdict could not be
  a bug in disguise.** Of 9,719,750 hop tokens, 7,112,259 (73.2%) canonicalise cleanly;
  the rest are 1,516,019 dotless UUCP node names, 793,245 pseudo-hops (`not-for-mail`,
  `uucp`) and 298,227 public-suffix rejects that are overwhelmingly bare IP addresses.
  Stripping INN's `.POSTED` and `.MISMATCH` markers before canonicalising matters: leave
  them on and the suffix list reads `POSTED` as the TLD and drops `news.bt.com.POSTED`
  entirely
- **Reason one: 7.1 million accepted hops are only 4,736 distinct domains.** A relay is a
  large ISP or a university. That population repeats endlessly across the corpus and is
  exactly what a CDX-derived baseline holds first, in every year, so **99.32% of sampled
  pairs are already held or uncorroborated**. Saturation is visible in the run itself:
  41 archives give 2,432 pairs and 400 give 7,201. This is the same finding as the award
  galleries and the institutional link directories, in a third costume: **a source that
  selects for authority cannot be net-new, however large it is**
- **Reason two, and the one worth keeping: the Giganews donation carries no `Path:` before
  2000.** In-window `Path:` lines by year are **1996=197, 1997=278, 1998=202, 1999=210,
  2000=134,923, 2001=750,686**. So 887 lines across the four years the project is
  weakest in, against 750,686 for the year it is already fattest in. The net-new pairs
  land where the header does: **1996 zero, 1997 zero, 1998 two, 1999 zero, 2000
  twenty-eight, 2001 nineteen**. Verified as absence rather than truncation: only 138
  messages of 3,269,960 carried the header past the 4 KB head window the collector reads
- **Both projections were computed, and it fails under the generous one too.** Log fit on
  the saturation curve gives ~15,300 raw pairs and **~30 EE** for the whole 383 GB corpus.
  The linear extrapolation, which is the method that overstated the recovered-address
  seam 24-fold and is therefore known to run high, gives **668 EE**. The bar was 3,000.
  Quoting the raw 7,201 as yield would have overstated it 147-fold
- **A third quiet reason, worth naming because it is not obvious: the survivors are cheap.**
  Mean English weight of a net-new pair here is **0.2834**, against the 0.812 and 0.968
  measured on the two queues in this morning's A/B, because the relay domains the baseline
  has NOT already got are Japanese, German, Danish and Swiss ISPs. So even the 49 pairs it
  does find are worth about a third of what the same count is worth on the queue
- **Measured against the live store, not a snapshot**, per the rule the header run cost us
  this morning. The `usenet_address` and `usenet_announce` ingests are already in
  `domain_year`, so the overlap that sank the header projection is subtracted by
  construction here rather than assumed away
- **One quality note, for the record rather than for the verdict.** `Path:` is trivially
  forgeable and the sample contains random-string forgeries (`2dafkyapz7.net`,
  `9hehgkrs.net`, `3o4rihgoih.no`), the same family as the `dumicsamvfs.mil` headers
  already noted. The corroboration split routes them to candidates, so they would have
  cost nothing, but it confirms a relay hop is free text and had to take the split
- **Nothing was landed.** No collector, no source name, no `PROVENANCE_LINEAGE` entry. The
  seam is closed and should not be re-proposed

## 2026-08-08, evening: the printed directory books, and a third of the trade press we had already paid for

Assigned to chase scanned Internet Yellow Pages and directory books on archive.org as the densest
untried dated artifact of the era. That route is closed. The session's actual yield came from the
extractor bug found while reusing the trade-press machinery the brief pointed at.

- **The books exist and are unreadable, and the earlier entry was right for a weaker reason.**
  The 5 August rejection rested on a 60-item `subject:(internet)` sample. This time the family was
  enumerated rather than sampled: 34 titles, Hahn, New Riders, Que, Mecklermedia, Luckman, Krol,
  the AOL member's edition. **All 34 are `inlibrary`/`printdisabled`.** `_djvu.txt` and
  `_hocr_searchtext.txt.gz` both return HTTP 401; `fulltext/inside.php` returns 403 on the correct
  `path`. The open-access complement of the same title query is 144 items containing **no directory
  book at all**, so the restricted set is not a sample of a larger readable population, it is the
  whole population
- **The decisive argument is not access, it is that OCR print cannot be net-new.** HathiTrust
  Extracted Features already measured the legitimate non-consumptive route into in-copyright print
  at 15.7 net-new pairs a volume, and the net-new names are `0fficemed.com` and `0steopath0mline.com`.
  **The names that survive the "is it net-new?" test are disproportionately the names OCR damaged**,
  because the real domains in these books are already held. Any future print proposal has to answer
  that before it is worth an afternoon. That finding was sitting in `handback-sources-A.md` and not
  in `docs/sources.md`, which is why I re-derived it; it is now in the rejected table
- **Two other families measured and rejected, so nobody repeats them.** SEC EDGAR is born-digital
  with hard filing dates and is the right *shape*: 150 filings, 150 reachable, 61.1 MB, **1.9 EE**.
  And the "no surviving zone files" entry had never checked Wayback, which is how the ISC files were
  recovered; checked now, still nothing
- **A CDX trap that produced a false negative inside this session.** `url=host/path/*` together with
  `matchType=prefix` returns zero even for captures known to exist. My control query said the ISC
  survey files were not in Wayback, and they demonstrably are. Drop the `*`. Any CDX zero from a
  prefix query is worthless without a known-good control beside it
- **The yield: the trade-press extractor never read a bare two-label domain.**
  `probe_texts_corpus.DOMAIN_RE` required two labels before the TLD, so `www.foo.com` matched and
  `foo.com`, `http://foo.com/` and `bob@foo.com` did not. Printed copy drops the `www.` constantly.
  Re-reading the OCR already cached on disk, **sending no request**, took the corpus from 30,513
  rows to 43,816 and yielded **816 net-new pairs worth 509.84 EE** after the same corroboration
  split, against 887.7 EE for the entire original collection run. Gained TLDs are 654 `.com`,
  72 `.net`, 57 `.org`
- **The narrowness was deliberate and its reason was sound**, so it was not simply widened: a
  permissive dot rule over OCR turns `end.Company` into a hostname. The defence moved into a
  lookbehind that stops a match starting inside a longer dotted token, `end.Company` and
  `readme.txt` are still refused, and four tests pin the behaviour including the deliberate
  disagreement with `ark.usenet.domains_in_message`, which still refuses bare hosts because a name
  in conversational prose is a weaker claim than one in print
- **Third time the win was in bytes already on disk**, after the UUCP maps and the Usenet address
  forms. All three were found by asking what the parser actually reads, not by finding a new corpus.
  `split_rtfm_faqs.py` imports the same function and has the same hole, so the rtfm corpus is worth
  re-reading on the same argument. Not done this session

## 2026-08-08 (the archived Yahoo directory re-opened: the fix is real, the 1996 premise is not)

- **The deferral rested on two facts. The first is now false, and that was checked before
  anything was built.** `dir.yahoo.com/Business_and_Economy/` at 20000817191821, 8,111 stored
  bytes, returns **0 outbound domains on the pre-fix extractor and 3 on the current one**
  (`networksolutions.com`, `broadcast.com`, `zdnet.com`). `unwrap_redirect` does exactly what it
  was written for, so the family really had been measured barren on broken code and re-opening
  it was the right call
- **The second fact is true and worth nothing, which is the finding.** The 1996-1997 material
  does live under `www.yahoo.com/<Category>/` and nobody had enumerated it. Enumerated and
  measured now, it is empty of value
- **CDX cannot enumerate this population, and that is a finding rather than an obstacle.**
  `www.yahoo.com/*` returns 504 at a flat 60.5 s every time, and so does
  `www.yahoo.com/Business_and_Economy/*`: the prefix is one of the largest key ranges in the
  index. A full 14-category sweep was left running for 45 minutes and produced nothing before it
  was stopped. **The replacement costs strictly less than the plan did.** A dated snapshot
  request redirects to the nearest capture, so `web/<stamp>id_/<url>` returns the real capture
  timestamp in the redirect target, the stored bytes, and the next level's category links, all
  for one archive request. Enumerating first would have been a second request per page buying
  only the list
- **Measured, both years and the family's best case, after `split_by_corroboration` and a real
  ingest each time:**

      1997 walk    20 requests   17 usable   295 domains   year_rows 9   6.1161 EE   0.3058/req
      1996 walk    30 requests   30 usable   182 domains   year_rows 0   0.0000 EE   0.0000/req
      1996 fat      5 requests    3 usable   193 domains   year_rows 2   1.6134 EE   0.3227/req
      total        55 requests   50 usable   670 domains   year_rows 11  7.7295 EE   0.1405/req

  **Against the gap engine's 0.959 that is roughly seven times worse**, and the third row is
  the one that closes the argument. It was run deliberately as the family's best case, the
  fattest 1996 industry index in the catalogue: `Business_and_Economy/Companies/Construction/`
  at 35,953 stored bytes listing **173 sites in one page**. It produced **2 net-new pairs**.
  The thin end and the fat end of the same tree land within 0.02 EE per request of each other,
  so this is not a sampling accident
- **Page yield is not the problem and never was.** Median 7 domains a page in 1997, 4 in 1996,
  17 on the fat run, and **zero pages at zero** across all 50 usable pages, against 8 of 18 in
  the August measurement of `dir.yahoo.com`. The pages are full. The store already holds what
  is on them
- **The number that explains it, and it inverts the premise.** Of the 284 domains listed on the
  1997 pages, **284 are already held**, and their per-year coverage is 85.6% for 1996 and 96.8%
  for 1997. Of the 121 listed on the 1996 pages, **121 are already held and all 121 carry an
  assignment in every one of the six window years**. Store-wide only 8.0% of held domains carry
  a 1996 pair, so the argument that 1996 is thin and therefore a 1996 listing is likely net-new
  runs **10.7x backwards**: 1996 is thin because the store's 8.0M names are mostly
  Usenet- and registry-derived hosts with one year each, not because famous 1996 websites lack
  1996 captures. Yahoo's 1996 catalogue IS the set of sites the 1996 crawls covered
- **The corroboration split never fired in any of the three runs: 0 uncorroborated names out of
  594 claims.** Provenance-wise that is the cleanest possible result, every listed name
  independently attested by some other source, and economically it is the death certificate. A
  source that lists nothing new can only pay in years, and the years are already there
- **The cost is worse than one request per page, which is the part a request count hides.** The
  walk ran at 25-40 s a page against two CDX engines on the same address and tripped
  archive.org's per-IP connection refusal repeatedly, the flat ~3.4 s TCP failure `ark.cdx`
  already documents. A third consumer here does not spend its own budget, it spends the engines'
- **Verdict: reject the search-engine directory family, do not defer it again.** The deferred row
  in `docs/sources.md` now carries the measured number rather than the projected one. The 7.7295
  EE the three walks produced is kept, because the requests were already spent, and the 535
  evidence rows they added are real cross-source corroboration on names the store already holds
- **Two things worth keeping regardless.** `scripts/split_expansion_journal.py` had no store-lock
  retry and failed the moment a maintain pass held the writer, which is exactly when it gets
  used; it now waits. And the redirect trick generalises: any archived page whose date is not
  known in advance can be dated from the URL the snapshot request lands on, for free

## 2026-08-08, night: historical zone files (closed), and public mailing lists (small, landed)

Assigned the highest-ceiling untried family in the project, historical DNS zone files and bulk
registry snapshots, with public mailing-list archives as the fallback. The zone-file family is now
closed for 1998-2001. The fallback landed **1,458 net-new pairs worth 833.17 equivalent-English**,
and a side-finding inside the zone-file work is still paying while this is written.

- **The zone-file answer is "nothing datable survives for 1998-2001", and it is now checked from
  six directions rather than three.** archive.org holds no in-window zone file under any of the
  obvious queries; `"com.zone"` returns literally zero items and the 303 `title:(zone file)` items
  are all 2009 or later. The CD-ROM route (Walnut Creek, InfoMagic, Internet in a Box) is FreeBSD
  and shareware discs, not registry snapshots. Four classic academic FTP mirrors have **zero**
  Wayback captures matching `zone`, `domain-info` or `internic`. DNS-OARC starts at June 1999 and
  holds the **root** zone, which lists TLDs rather than domains. The sibling agent's Wayback check
  of `internic.net` is not re-run here; it is taken as done
- **The survey name lists genuinely stop at July 1997, and that is now established from the
  artifacts rather than inferred.** Two independent live directory listings agree:
  `ftp.isc.org/www/survey/archive-data/` and the survey author's own `3waylabs.com/zone/`. The
  author's site does carry `WWW-9801/` and `WWW-9807/` directories, which look like the missing
  1998 editions and are **aggregate report HTML with no name list in them**
- **ISC's own copies are corrupt in a way that will fool a partial-recovery attempt, so record how.**
  `9607.domains.gz` from ISC recovers 6,562,719 of 6,755,227 bytes and looks like a 97% success. It
  is not: it holds **3,835 newlines against the good copy's 488,069**, because the deflate stream
  desynchronises a few thousand lines in and everything after decodes as plausible-looking garbage
  (`vanoqoykoorrlykddoldnabykeec.gc`). The same is true of `9701.domains.gz`, which is why the
  January 1997 edition stays a permanent gap. **A partial gzip recovery is not a partial file.**
- **The one thing the zone-file brief did turn up is on the shelf we already own.** The 1996 Wayback
  crawl of `nw.com/zone/` captured not only the `.domains` lists but **583 per-TLD host files across
  three survey editions**, `9607.hosts/`, `9701.hosts/` and `9707.hosts/`, 116 MB in total. Only one
  of them, `9607.hosts/org.gz`, had ever been fetched. Four of the big English-weighted ones
  measured before ingest give **268 domains the store does not hold for 1996, worth 237.42
  equivalent-English**, and they take the master path as `artifact_listing` because the survey date
  is the file's own provenance. `parse_isc_survey` already reads the `IP hostname` form, so this
  needed no code beyond a resumable fetcher, `scripts/fetch_nw_host_files.py`. **Left running and
  unfinished**: the download is about two hours at three connections, so whoever picks this up runs
  the fetcher again to completion, then `uv run ark ingest isc_survey data/raw/isc_survey/*.gz`.
  Re-offering an already-ingested file is skipped on its hash, so running both twice costs nothing
- **Mailing lists: the structure is right, the rate is five times worse than Enron, and that decides
  the family.** Measured, not projected: `mail.python.org` gives **0.00145** equivalent-English per
  in-window message and `mail.gnome.org` **0.00121**, against **0.0067** for the Enron corpus. At
  that rate the 32,000 equivalent-English this round needs would take roughly **25 million in-window
  messages**. The two hosts together publish 579,808. So the family is worth having and cannot be
  the answer to a shortfall
- **Why a technical list is weaker than corporate mail, which is the finding that generalises.**
  83.6% of the pairs it finds are already held. A public list selects for an authoritative,
  heavily-crawled population, which is the same reason the Usenet `Path:` header, the award
  galleries and the institutional directories all failed. Corporate mail was different because its
  counterparties are long-tail commercial names nobody crawled
- **The lineage claim is honest only because the collector drops the gatewayed lists.**
  `python-list` and `python-announce-list` are bidirectionally gatewayed with `comp.lang.python`, so
  their messages are the Usenet corpus's messages. They are excluded at collection time, 64 month
  files, and a test pins it. Without that, `mailing_list` would corroborate `usenet` with its own
  data
- **Reachability is most of what is left of this family, and it is bad.** `lists.debian.org` has no
  per-month bulk file at all, only one HTML page per message; `lists.samba.org` answers 426,
  `sourceware.org` 403, `lore.kernel.org` sits behind an Anubis proof-of-work challenge. Pipermail
  hosts are the exception and are what made the measurement possible: one gzipped mbox per list per
  month, 740 MB for two hosts in six minutes, and **not one `web.archive.org` request**, so this
  competes with nothing the engines are doing

## 2026-08-08 (RDAP direct to the registries: 90x the rate, and the candidate pool asked for the first time)

- **The premise was that RDAP was slow. It was not: `rdap.org` was.** Every RDAP query this project
  has ever made went through the `rdap.org` redirector, and tonight's pilot measured what that
  costs: **0.83 queries a second with 18.8% of them refused with HTTP 429**. The redirector is a
  free service that meters the client; the registries behind it were never the constraint. Resolving
  each TLD to its authoritative endpoint from the IANA bootstrap file
  (<https://data.iana.org/rdap/dns.json>, 1,200 TLDs, cached and refreshed weekly) and asking
  Verisign, PIR and Nominet directly measured **75 q/s with zero refusals**, a 90x improvement on a
  route that had been treated as a hard ceiling for two weeks
- **Concurrency was settled by measurement, not by guessing.** 400 to 600 queries at each level,
  direct to Verisign: 4 workers 19.1 q/s, 8 workers 30.8, 16 workers 44.4, 32 workers 75.0, 64
  workers 46.2. **Not one 429 at any level**, and the turn above 32 workers is therefore local
  contention rather than the registry pushing back. 32 is the settled setting. Two processes at 32
  workers reach 94 q/s combined, so the ceiling really is in one Python process and not in the link
- **Registries are paced separately, one `RateGovernor` per endpoint host, and that earned its
  keep within the hour.** `.au` answered **11 queries in 10 minutes** while Verisign was running at
  full speed on the same machine. Under the old shared pace that one registry would have set the
  pace for all of them
- **The candidate pool had never been asked, and that was the real find.** `ark gaps --creation`
  addresses only domains that ALREADY hold a year. The pool is the other population: **2,537,091
  names the store carries with no year at all**, of which **2,008,557 sit in a TLD that both has an
  RDAP service and existed in the window**. A creation date landing in window gives such a name its
  FIRST year, so a hit is a net-new domain and not merely a net-new pair
- **Ranking a queue on expected value alone is a trap when the probability half is a guess, and
  `.au` is the proof.** Expected equivalent-English is P(creation in window) x English share. With
  no measured P for `.au`, the pool-wide 40.4% prior times its 0.9904 share sorted it **first in the
  whole queue**, ahead of 1.34M `.com` and `.net` names. Probed: **0 in-window dates from 3 datings,
  at 11 answers in 10 minutes.** auDA re-registered the namespace in 2002 and the creation dates
  come back stamped with the migration, not the original registration. The same prior put 184,692
  `.gov` and a head of `.you`, `.dot`, `.sucks`, `.box`, `.hot`, `.free` and `.aol` above `.com`,
  the last group because the reviewer's English-share model is built from 2024 crawl data and scores
  modern brand gTLDs near 100% English. A TLD delegated in 2014 cannot carry a 1996-2001 creation
  date, so era eligibility is now a **deletion** in the RDAP list builder rather than the demotion
  the CDX list builder makes: there the name might still hold a capture, here the query is a
  certain miss
- **Probe before sweeping, and probe the registry as well as the TLD.** 150 queries each settled
  where the night went. `.org` at PIR looked excellent on its head, 29.3% in window at a 0.7101
  share, and collapsed to **1.6% by the ten-thousandth name**, so it was stopped after contributing
  114 EE from 9,938 queries. `.uk` at Nominet returned three refusals in its first fourteen queries
  at 0.5 q/s and was stopped immediately, on the rule that a source blocked tonight is a source lost
  for the rest of the round. Verisign held **19.2% across 73,000 queries with no decay and no
  refusal**, which is what made the sweep worth running at all
- **A 429 still settles nothing, and the pilot journal was renamed before it was ingested.**
  `rdap_answered` counts only a 200 or a 404; the 78 refusals in the pilot leave those domains
  queryable. The pilot had been written as `pool_pilot_20260808.jsonl.gz`, which the `rdap_` prefix
  scan cannot see, so every one of its 418 domains would have been asked again. It is now
  `rdap_pool_pilot_20260808.jsonl.gz`
- **The journal record gained a `url` key and nothing else changed.** It records the endpoint that
  actually answered, so `whois_creation` evidence now cites the registry rather than a redirector
  the query no longer uses. Journals written before tonight have no such key and the parser falls
  back to the redirector URL for them, which is where those queries really did go

## 2026-08-08 (the American trade weeklies: the composition theory was wrong, and the win was in the cache again)

- **The brief was to widen `trade_press` to the American computer trade weeklies**, on the recorded
  theory that yesterday's 1,334 pairs / 887.7 EE came in 5x under projection because
  `collection:computermagazines` is European hobbyist titles printing `.de` and `.it` addresses.
  The corpus was found, worked in full, and measured. **The theory is refuted and the numbers say
  so twice**
- **The corpus that actually exists is 1,288 in-window items**, verified one term at a time rather
  than assumed from the brief: `collection:computerworld` 632, `collection:pub_computerworld` 309
  (the same weekly off microfilm), `collection:applemagazines` 290, and 57 Google Books scans of
  InfoWorld, Network World and PC Mag under `bub_gb_*`. **Most of the names in the brief do not
  exist as archive.org collections**: no `pub_infoworld`, `pub_network-world`, `pub_pc-week`,
  `pub_internet-world`, `pub_cio`, `pub_web-techniques`, and no `sim_*` microfilm run of any
  computing title except Computerworld. InfoWorld and Network World survive only as Google Books
  scans, which is why that query term is written by identifier and title rather than by collection
- **The sample check that was skipped last time was done first this time, and it looked excellent.**
  A Computerworld issue prints 116 domains of which 106 are `.com`; an InfoWorld issue 91 of which
  86 are `.com`. Reachability came in at 79.2% against the hobbyist corpus's 34.3%, and 80.0% of
  extracted rows were corroborated against 32.3%. **Every quality signal was 2-3x better and the
  yield was still worse**: 0.449 EE per reachable item against 0.641
- **Because the constraint is saturation, not composition.** Mean weight of a net-new pair is 0.638
  here and 0.665 there, so the pairs cost the same; there are just fewer of them, because a store
  holding 9.6 million pairs already holds nearly everything Computerworld printed. A cleaner, more
  American, more `.com` corpus buys accuracy, not increment. **A source that selects for authority
  cannot be net-new**, which is the same finding as the award galleries, the institutional link
  directories and the Usenet `Path:` header, now in a fourth costume
- **The `.de`/`.it` explanation could never have been the mechanism, and one grep would have shown
  it.** `DOMAIN_RE` only ever matched `com|net|org|edu|gov|us|uk|au|ca|nz|ie|za|sg`, so a German or
  Italian address is not extracted at all and cannot dilute anything. Measured over the journals the
  hobbyist corpus's domains carry a **higher** mean English weight than the American corpus's,
  **0.6825 against 0.6494**, because 6.7% of them are `.uk` at 0.9813 and 6.0% `.au` at 0.9904
  against 86.6% `.com` at 0.6321. A stated cause that the code makes impossible should not survive
  one reading of the regex, and it survived a whole day
- **The larger half of tonight's yield was in the cache, not in archive.org.** The bare-name fix to
  `DOMAIN_RE` landed at 19:33 while the American collector was already running with the old pattern
  loaded, so its 1,007 issues were read narrowly. Re-reading the whole cache afterwards, 1,703 items
  rather than 855, gives **881 further net-new pairs worth 551.83 EE against 452.50 for the ninety
  minutes of collection**. Fourth time on this project the win was in bytes already on disk
- **247 of those pairs are hobbyist-corpus names that only became corroborated because the American
  ingest had just put their domains into `domain_year`.** The corroboration split runs in both
  directions: a new source rescues candidates the old one could not admit, which is an argument for
  re-splitting older free-text journals whenever a new lineage lands
- **Landed: 1,590 net-new pairs, 1,004.33 equivalent-English.** Computerworld scanned 678 (430.56),
  Computerworld microfilm 521 (330.42), hobbyist newly corroborated 247 (152.38), InfoWorld/Network
  World/PC Mag 130 (82.05), Macworld/MacAddict 14 (8.93). By year 1996:94, 1997:164, 1998:315,
  1999:416, 2000:387, 2001:214. **Attributed store-side** by joining `domain_year.evidence_id` to
  the `trade_press` evidence rows, because the scoreboard moved 20,636 EE over the same two hours
  and almost all of that is the two CDX engines, not this
- **Against the 33,259 EE the night needed, this is 3.0%.** Worth landing and worth reproducing, but
  the honest read is that the trade press seam is now closed: 5,318 in-window items across both
  corpora is the whole of the reachable American and hobbyist computing press on archive.org, and
  `sim_microfilm` at large is the `magazine_rack` trap at 45x the size (57,245 in-window items, but
  a 1,500-item sample is scientific journals, government gazettes and "Table of Contents" stubs)
- **Ingest hygiene, for the next person.** The ledger keys on `(source_name, path.name)`, so a
  second corpus cannot reuse `tradepress_dated.jsonl.gz`. `split_trade_press.py` grew `--journal`
  and `--tag` for exactly this, and both of tonight's ingests went in under their own names
  (`_american`, `_american_bare`) and stay separately attributable

## 2026-08-08 (the bare host in the Usenet bodies: +28,460.3 EE, and the wall was never the pattern)

- **`_BARE_WWW` was anchored on the literal `www.` label and the comment said why: a bare
  `foo.com` in running prose is more often a company name, a file name or half an email
  address than an address, "and the evidence wall is worth more than the extra recall".
  That is right about prose and wrong about where the wall is.** Every row from this corpus
  passes `split_by_corroboration`, so a (domain, year) becomes a dated master record only
  when an independent lineage already places that domain in `domain_year`. A company name is
  not a registered domain any independent lineage attests, so it cannot reach an annual
  file: it goes to the candidate pool and asserts nothing. **The split is the wall, not the
  pattern**, and once that is seen the recall costs nothing the wall does not catch
- **Measured: 36.3% of the extracted rows were uncorroborated and went to the pool.** That is
  the wall doing its work in public rather than in an argument
- **+28,460.3 equivalent-English over 42,139 net-new pairs, measured as the scoreboard delta
  across the ingest.** Whole corpus, 411.0 GB, 515,079,416 messages of which 219,447,104 in
  window, zero archive failures, about three hours at 8 workers and not one network request.
  Round moved 9.9464% to **10.4525%**, so this is the addition that crossed 10%
- **`domains_in_message` was left exactly as it was, and that was the right call.** The bare
  form is a separate function with its own source name, `usenet_bare`. The two can be
  compared, the addition can be measured on its own, and a reviewer can drop it without
  disturbing a single row `usenet_announce` already claimed
- **Overlap was most of the gross, which is why only the marginal figure is quoted.** 601,738
  pairs extracted; **269,773 of them already asserted by `usenet_announce` or
  `usenet_address`**, 340,963 already assigned by some source. The gross is worth 416,446.4
  EE, so quoting it would have overstated the source 15-fold
- **The projection held this time, and the two fixes are the reason.** A 400-archive sample
  measured 837.08 EE and projected 40,245 linear, 31,724 saturating, 18,873 on a power law
  fitted to its own curve; the truth was 28,460.3, inside that spread. The header-mode
  failure of the same morning projected 10,889 and delivered 1,038 because it was measured
  against a snapshot taken before an intervening ingest. This one was measured against the
  **live** store and deduped explicitly against both existing Usenet sources
- **A saturation fit with a linear K scan reports its own ceiling and it reads like a
  measurement.** The first version pegged K at the top of its range and printed "half-yield
  at 20,000 archives", which was the scan boundary and not the data. K is now scanned on a
  log grid running far past the corpus, so a fit that finds no saturation says so
- **Six guards, each answering something actually in the corpus.** A TLD allowlist, because
  the TLD is the only anchor a bare name has. A lookbehind that stops a match starting inside
  a longer dotted token, which keeps this off hosts already inside a URL or an email address.
  A lookahead that refuses `end.Company` and refuses `john.com@example.org`. Greedy labels so
  `foo.com.au` is not read as `foo.com`. An all-digits rule, because `4.0.2.au` canonicalises
  to the invented name `2.au`. And **body text only**: `Path:`, `Xref:` and `Newsgroups:` are
  dotted tokens by construction, and a bare rule over them turns news servers and vanity
  newsgroup names like `alt.isd.net` into announced websites
- **The largest single contributor is `can.domain`, the CA registry newsgroup, at 7,137
  net-new pairs.** Then `alt.domain-names.forsale` at 1,858 and `alt.sources` at 844. By TLD
  the yield is 25,898 `.com`, 7,640 `.ca`, 4,145 `.net`, 1,977 `.org`, 1,689 `.uk`
- **One limitation, named rather than hidden.** 1,200 of the 42,139 pairs are first seen in
  `comp.mail.maps` or `can.uucp.maps`, which `ark.uucp` already parses as registry data under
  the `registry` lineage. Reading them again as prose files those rows under `usenet`, so a
  pair carrying both could look independently corroborated when it is one posting read twice.
  2.8% of the yield, the same treatment `usenet_announce` already gives those groups, and
  every evidence row names its group, so filtering them out is a query and not a reingest
- **Secondary, and it cost four minutes: the rtfm FAQ mirror re-read, +1,570 pairs and
  +1,167.4 EE.** `split_rtfm_faqs.py` imports `probe_texts_corpus.domains_in` rather than
  copying it, so it inherited that extractor's bare-domain fix for free. The same 8,408
  in-window documents went from 34,216 rows to 46,583. **An imported extractor spreads its
  fixes silently: when `domains_in` changes, every corpus reading through it is stale and
  nothing in the pipeline says so.** `--tag` was added to the script because the ingest
  ledger keys on content hash and refuses a rewritten journal under an ingested name
- **Fourth time this project has found the win in bytes already on disk**, after the UUCP
  maps, the Usenet address forms and the trade-press re-read. All four were found by asking
  what the parser actually reads rather than what corpus to fetch next

---

## 2026-08-08 (documentation becomes a source of truth, and the submission stops overwriting itself)

Ivo's brief: the phase-4 report is for Ding, who knows the framework and wants the **quality** of the
new domains, not the machinery. Where they come from, why they are viable, how to reproduce them.
Everything else subtracts. And the documentation should read as a timeless reference rather than a
log, because a report distilled from logs inherits their shape.

- **One generated report, not one per round.** `docs/report.md` is now generated from
  `docs/report.template.md` by `scripts/fill_report.py`, replacing `report_260802`,
  `interim_report_260805`, their templates, and a 26 July `report.md` still tracked. 136 lines against
  341. Dated filenames meant `package_delivery.sh` had to be repointed every round, and the round it
  was not repointed shipped the previous round's figures beside this round's data.
- **The report and the archive both named the wrong baseline.** `report_figures.py` and
  `fill_report.py` hardcoded `merged260730` in their labels, and worse, `package_delivery.sh`
  **shipped** `merged260730` in `baseline/` while asserting in `baseline/README.txt` that it was the
  reference the figures mean. The store has counted against `merged260802` since 2 August. A reviewer
  scoring our additions against the shipped baseline would have got a different answer than the report
  claims, with nothing in the archive to reveal why. All three now read `ark.baseline`, the shipped
  line count is measured rather than quoted, and a missing baseline is a refusal instead of a warning.
- **Equivalent-English was absent from the report generator**, though it is the metric the round is
  scored on. Added per source and in total; the per-source table is ordered by it, because ordering by
  pair count puts the weaker source first.
- **`prior_round_pairs = 32698` dropped rather than updated.** Once the reviewer reissues the
  baseline, the harvested/absorbed split answers itself: everything net-new against the current
  release was harvested since he last merged. A hardcoded subtrahend silently understates the round
  the moment it goes stale.
- **One folder per submitted round**, Ivo's suggestion, mirroring `feedback-phase-*/`. Archives land
  in `submissions/<round>/`, defaulting the round to the git branch. The staging directory is rebuilt
  from scratch every run, so for three rounds the only copy of a submission was whatever had been
  emailed. The tarball is git-ignored; `report.md`, `sources.md`, the checksum and a `MANIFEST.txt`
  naming the commit and baseline stay in git, which is enough to say later exactly what was claimed
  and to prove a rebuilt archive matches, without keeping gigabytes.
- **`just journals` never learned this round's sources**, so `just reproduce` rebuilt a store missing
  every one of them, and `collect_enron.py` had no recipe at all. Both fixed.
- **The maintain loop never learned to ingest RDAP.** It folds in Usenet, language and CDX journals
  and nothing else, so 24,422 in-window creation dates, roughly 15,400 equivalent-English, sat unread
  on disk while `ark stats` reported a round that did not include them. Added. Note the trap: editing
  a running bash script does **not** change the running loop, because bash parses a `while` body as
  one compound command, so the fix only takes effect on restart and the banked journals had to be
  ingested by hand.
- **`docs/source_research_260805.md` retired.** A session log whose durable conclusions were already
  in `docs/sources.md`; the two pointers into it were replaced with the substance they pointed at.

Signed off by Ivo: pending.

## 2026-08-08 (the RDAP sweep finished: 391,461 queries, and a 403 that nobody was counting)

- **The sweep as run.** 391,461 queries to the registries, **3 refusals in total (0.001%)**,
  48,695 in-window creation dates, worth **29,214 equivalent-English** and every one of them a
  candidate-pool name earning its first year. Verisign carried it: 244,223 of 244,279 `.com`
  queries answered, no decay in the answer rate, sustained ~70 q/s for two and a half hours
- **PIR does not throttle, it blocks, and the run could not see it.** `.org` answered its first
  ~850 queries and then returned **403 for 9,253 consecutive requests**. 403 was not in the
  throttle set, so the governor treated each one as a plain error, never backed off, and the run
  spent nine thousand requests being told no. That is the tight loop of refusals the collection
  rules forbid, and it happened because the monitoring counted only 429 and transport failures as
  refusals. **On queries `.org` looked like a yield collapse from 29.3% to 1.6%; on answers it was
  24.9%, the best rate of any TLD measured.** The rate that means anything is per answer
- **Fixed:** 403 is now a throttle status and the harsh kind, so a run of them trips the breaker and
  holds every thread off that registry. It is deliberately still not retryable and still not an
  answer, so a blocked domain is not re-asked inside the run and does not settle either
- **Verisign's ceiling is per-IP, not per-process.** Two processes at 32 workers against
  `rdap.verisign.com` settled at 31 q/s each, exactly halving the 70 q/s one process gets, because
  `.com` and `.net` share a host. Splitting the work across TLDs bought nothing; the right move was
  to put the whole budget on whichever list had the higher expected EE per query at that moment
- **Yield decays down the list and that is what ends a sweep, not the registry.** `.com` returned
  19.2% over its first 100,000 queries, 11.4% over the next 100,000, then 8.4%. `.net` went 20.3% to
  4.1% over 114,000. The list is ordered by how many distinct sources saw a name, so this is the
  ordering working: the pool runs out of names real enough to have been registered. Roughly 359,000
  of the 1,345,949-name Verisign list is consumed, and the rest is worth less per query than the
  first hour was

---

## 2026-08-09 (the report answers the admissibility question, and the English standard leaves the delivery)

Ivo relayed the reviewer's feedback on the phase-4 draft. Three things, and a fourth that fell out of
checking the first three.

- **The English verification standard is retired.** The metric is equivalent-English now, so the
  report should not discuss page-level language verification at all. Removed from the report, and then
  from the delivery: `additions_english/`, `additions_unverified/`, the rejection register and the
  English engine review no longer ship. They were not merely redundant, they were misleading. The
  English folder came out empty, the unverified one was `additions/` under another name, and
  `verify.sh` printed three vacuous WARN lines about a partition of nothing. An archive documenting a
  rule nobody applies reads as a rule still in force. `ark lang-report` still writes the files under
  `output/` and the language journals still ship, so this is a change to what the delivery asserts.
- **"Only when an independent source already places that domain in some year" was unclear**, and the
  reviewer could not tell from it whether every addition is admissible as a master pair. Fixed by
  making it per source and derived: the table gained an evidence-type column and an admissible column
  read from the shipped rows, and the sentence under it is generated, so a candidate-only source would
  be named rather than the claim repeated. The real ambiguity was that two different things were being
  conflated: `whois_creation`, `cdx_timestamp` and `artifact_listing` are **self-dating** and involve
  no corroboration whatsoever, while `dated_directory` is a human-typed address inside a dated artifact
  and is the only kind taking the extra filter. The report now says so, and gives the corroboration
  test its exact mechanical definition.
- **Corroboration is a nice-to-have.** Reduced from a table to one sentence.

**An adversarial pass over the finished report found four claims wrong**, run as a workflow of 164
agents that extracted 99 checkable claims and re-derived each against the store and the code, with a
second reader over every flag. Worth recording because three of the four were in prose I had written
confidently.

- *"Every figure here is generated, none is typed by hand"* was **false**, and refuted two screens
  later by the report's own hand-typed 601,738. Now scoped to the tables.
- *"The database enforces this with a CHECK constraint generated from the same list"* was **false**.
  The CHECK is generated from `ALL_TYPES`, the legal vocabulary; it does not know master from
  candidate. Admissibility is enforced by `no_candidate_leakage` and `every_pair_has_master_evidence`,
  which are now named in the report instead.
- RDAP was called *"the only evidence class that needs no corroboration"*, contradicting the paragraph
  two screens above naming three such classes.
- The `comp.mail.maps` caveat said **"about 1,200 pairs"**. Measured from the journal it is **50,250**
  `usenet_bare` rows drawn from `can.uucp.maps` and `comp.mail.maps`, the two groups the UUCP parser
  also reads. The caveat understated itself roughly fortyfold. A caveat that flatters itself is worse
  than no caveat.

**A third staleness guard in packaging**, because the same pass caught the report and the archive
quoting different totals. Two guards kept the code and the data in step and neither looked at the
document describing both, so the report drifted: regenerated against a store the collectors had grown
by 10,000 pairs since the archive was cut. Packaging now regenerates the report and refuses if that
changes anything.

**The baseline question.** Ivo placed `merged260802-2/` in the repo root believing it a new release.
It is byte-identical to `feedback-phase-3/merged260802-2/`: same 20 files, all six year files matching
on SHA-256. So the round was already measured against it and nothing moved. The reviewer's 9 August
mail links a fresh download described as the current list of existing domain files; if that turns out
to be a newer merge than what is on disk, every net-new figure has to be re-derived against it.

Signed off by Ivo: pending.

---

## 2026-08-10 (phase 4 accepted in full, and the baseline moves to merged260810)

The reviewer's feedback arrived with a reissued corpus. **946,266 records over 684,523 distinct
domains accepted, 76,538 of them domains that had never appeared in any of the six baseline years,
worth +603,401.7811 equivalent-English, a 10.730988% increase.** New totals: 11,362,034 pairs and
6,226,386.4245 equivalent-English.

- **His arithmetic was re-derived rather than trusted, in `Decimal`, and it is exact.** The six
  per-year increases sum to 603,401.7811 with zero residual; the six new per-year totals sum to
  6,226,386.4245; 603,401.7811 / 5,622,984.6434 is 10.730988% to six places; and each per-year growth
  rate he quotes reproduces from his own numbers to six places. Nothing needed adjusting.
- **"Accepted in full" is now proved from the files, which it never was before.** `wc -l` gives
  merged260810 minus merged260802-2 as exactly 946,266 lines. `comm` on LC_ALL=C-sorted copies gives
  **zero** lines dropped in either direction, and the lines he added are **byte-identical** to
  `sort output/netnew/<year>.txt`. He merged precisely what was exported and added nothing of his own.
  That closes the open question from 9 August: no phase-4 figure needs re-deriving, and the transfernow
  link he sent was this corpus.
- **The switch is one file, and it took.** `src/ark/baseline.py` now names `merged260810`, its pair and
  equivalent-English totals, and its per-year totals. Nine consumers follow automatically. `ark stats`
  prints the marker it measured against, which is the check that the switch landed at all; per that
  file's own docstring the failure mode is silent and flatters us.
- **Net-new dropped to 1,959 pairs on the load, and that is the correct answer.** 1996 and 1997 to
  zero, then 14 / 70 / 559 / 1,316. The 1,959 is exactly the increment collected after the phase-4
  archive was cut at 2026-08-09T13:51:03Z, which is why the round window is now `CURRENT_ROUND_SINCE`
  in `baseline.py` beside the marker: a release and its window are the same fact, and kept apart they
  drift.
- **Two traps found while doing it, both silent.**
  1. `ark ingest-legacy --legacy-dir <new release>` without `--marker-prefix` ingests **nothing**. The
     prefix defaults to the marker in `baseline.py`, so the composed marker already exists and all six
     files are skipped behind six reassuring "already ingested" lines. Edit the constants first.
  2. **`ark export` must precede `ark check`.** The `additions_not_double_counted` invariant reads the
     exported annual files, so running the gate first compares this round's files against a store whose
     baseline has moved and reports all 946,266 already-credited pairs as violations. `just deliver`
     had the order right; a hand-written sequence did not.
- **The 10% target is not carried forward.** It was met at 10.7310% and no new target has been set.
  `build_query_queue.py` used to size the queue against a tenth of the baseline, which after the switch
  would have silently retargeted a tenth of a *larger* baseline, so that default is gone and `--need`
  is now explicit.

**Signed off by Ivo: pending.**

## 2026-08-10 (the repository becomes a source of truth, and `legacy/` is where the rest goes)

A full audit ahead of handing the project to a fresh agent: every markdown file, all 53 scripts, all 31
modules, 26 test files, the justfile and the working directories, each classified with the evidence for
the verdict, then re-checked by three adversarial passes that overturned nine of them.

- **The English verification standard leaves the tree.** Retired by the reviewer in August 2026 and
  replaced by equivalent-English, it still had residue in eleven places, including `ark ingest-lang`
  inside the **live** `just maintain` loop and inside `just journals`, which `just reproduce` depends
  on. `language.py` and `verify.py` are in `legacy/src/`, the three partition invariants are out of the
  gate (twelve becomes **nine**), and `verify_delivery.sh` loses three checks that had been printing
  SKIP about folders the archive stopped shipping. **A check that examines nothing reads like a check
  that found nothing wrong**, which is worse than not having it.
- **One atomic commit, because the alternative is a dead CLI.** The five `from ark.language import`
  blocks in `cli.py` are module-level above the Typer app, and `ark = "ark:main"` is the only console
  script, so moving that file alone breaks `ark export`, `ark stats` and `ark check`, not just the four
  lang commands. The same held for `verify.py`, which is how it was caught: the suite failed on import
  four collection errors deep.
- **`legacy/` is tracked but not shipped and not linted.** Tracked, because `package_delivery.sh` ships
  `git archive HEAD` and git-ignoring the retired engine would silently drop the audit trail behind
  `domain_language` rows the reviewer already holds in every provenance export. Not shipped, via a new
  `export-ignore` in `.gitattributes`. Not linted, via `legacy` in ruff's `extend-exclude`, since
  several archived files import modules that also moved and are preserved rather than runnable.
  `legacy/notes/` stays **git-ignored**: those eight session logs have never been in git, and archiving
  them must not be the act that commits them.
- **Nine facts were promoted out of git-ignored files before anything moved.** The most important is
  the reviewer's own framing for this round, which existed in no tracked file anywhere: the task "should
  not be considered simply as a conventional data collection or download problem". That is now
  `docs/brief_amendments.md`, alongside a transcription of the 2026-08-10 feedback, which existed only
  as a `.docx`. The acceptance bar for a new source and the four ways this project has got a projection
  wrong are now `docs/discovery.md`. **`docs/SPEC.md` was left byte-for-byte untouched**: 21 files cite
  its clauses by roman numeral, and appending our reading of the metric inside his document would send
  him a brief that appears to have him saying things he did not.
- **A measurement in an archived handback was wrong and the synthesis nearly carried it forward.** A
  320-archive sample table put the unexploited Usenet header seams at about 16,500 equivalent-English.
  The full-corpus runs are in this log and say otherwise: the machine-written headers delivered
  **1,038.4 EE** and are exhausted, and `Path:` projects to about **30 EE** because 7.1 million relay
  hops are only 4,736 distinct domains. **A sample measured against a store that has since grown is not
  a measurement.** What is real there is a reproduction gap, not headroom: `data/raw/usenet_hdr/` had no
  ingest line, so a rebuild was 19,224 evidence rows short. Fixed.
- **`just reproduce` did not run at all, and had not for days.** `just sources` aborted on
  `data/raw/arquivo/IA.cdxj`, deliberately deleted at 47 GB once its evidence was in the store. That is
  the reviewer-facing path. The line is commented with the re-download route beside it, and
  `README.md` now says to expect 234 checksum lines rather than 235. Also added: the missing
  `usenet_hdr` and yahoo96 journal replays, and a fix to `just usenet-addresses`, whose `mode`
  parameter reached the collector but not the split or the ingest, so `mode=headers` collected into one
  directory and then ingested the other.
- **`just engines` was reporting a false all-clear.** With the VPN down, ssh failed, the remote listing
  came back empty, the loop body never ran and it printed "none, everything is home" about a machine it
  had not been able to ask. That is precisely the failure the section exists to catch: this project once
  ran a second machine for a day and a half with 5,793 year-records sitting on its disk. Unreachable now
  reads **UNKNOWN**.
- **`just --list` was showing sentence fragments** for ten recipes, because `just` prints only the last
  comment line before a recipe and the reasoning had been written last. The one-line description now
  sits immediately above the name.
- **14 GB reclaimed, no raw data touched.** Two store backups protecting ingests that have since
  shipped and been accepted, the delivery staging tree that `package_delivery.sh` deletes and rebuilds
  anyway, and the retired partition's empty output. Everything under `data/raw/` stays, because the
  reviewer's first priority for this round is unprocessed files and low-recall extraction over corpora
  already paid for. `legacy/docs/retired-data.md` labels the directories nobody reads any more, which is
  a different state from unmined, and confusing the two costs either a wasted pass or a missed lead.

**Signed off by Ivo: pending.**

## 2026-08-10 (`docs/sources.md` gains a Residual field, which is what the round was actually asked for)

The reviewer's first priority is what remains unexhausted **inside** each source already used, and that
document ships to him. Audited against it, six sections answered the question properly, three partly,
and twelve not at all, with the worst gap being `ia_cdx_bulk`, the main engine, at 26 lines with no pool
size, no hit rate and no query count.

- **A fixed `**Residual.**` field per section**, shaped like the `rdap` section, which already had it:
  addressable pool, what was processed, what failed to parse, and what a next pass costs per unit of
  equivalent-English. Where the number is a guess it now says so in the same sentence.
- **`enron_email` had no section at all**, despite standing behind 5,134 net-new pairs in an annual
  file, which brief IX and XI both require documented. Written.
- **Two measured sources that are not rejected are now documented as such**: attrition.org (6,458
  net-new pairs, 3,174.08 EE, 33 index files already on disk, blocked on a `CC-BY-NC-SA` licence
  question rather than on work) and the UK Government Web Archive (real coverage from 1996-11-11,
  government-only, 250 addressable domains, where the collector costs more than the answers). Both had
  lived only in an untracked handback. Filed outside the rejected register on purpose, so nobody closes
  them by mistake.
- **Seven more dead leads recorded**, each with the measurement that killed it: IRCache and NLANR proxy
  traces, the Internet Traffic Archive, shareware CD-ROM catalogues, DMOZ on archive.org, InterNIC
  snapshots, other released email corpora, faqs.org. An automated discovery agent will walk straight
  back into all of them otherwise, which is the whole point of writing them down.
- **`data/raw/ukwa/host-linkage.tsv.gz` is exactly 2^31 bytes and fails `gzip -t`.** That looked like a
  finding and is not: the file is year-sorted and runs 1995 to mid-2004, so the truncation cuts well
  past our window and the 1996-2001 head is complete. The existing note asserted this without a figure;
  it now has one. **Recorded because a closed question is worth as much as an open one.**
- **Four directories under `data/raw/` have downloaded bytes and no parser**, which is the literal answer
  to the priority: `pandora-titles/` (a National Library of Australia title index, `.au` at 0.9904 the
  highest weight in the table, mentioned nowhere in the tree), the HathiTrust extracted-features
  residue, attrition.org, and the `usenet_hdr` reproduction gap. Listed with sizes.

**Signed off by Ivo: pending.**

## 2026-08-10 (fixing the broken reproduction path found 496 unprocessed files, worth 14,956 EE)

Unplanned, and the most valuable thing that happened today. `just sources` had been aborting at stage 2
on `data/raw/arquivo/IA.cdxj`, a file deliberately deleted at 47 GB once its evidence was in the store.
Commenting that line out and documenting the gap made the stage run to completion **for the first time
since the file was removed**, and its glob `data/raw/isc_survey/*.gz` then swept up **496 per-TLD
Network Wizards survey shards that had been on disk since 5 August and never ingested**.

- **+42,299 net-new pairs, +14,956.3877 equivalent-English**, at mean weight 0.3536. The store now
  holds 581 shards over three editions: 179 for 1996-07, 192 for 1997-01, 209 for 1997-07.
- **It lands where the collection is thinnest.** 1996 gained 4,899 records and 1997 gained 37,400,
  which is **+0.7001%** and **+1.4313%** against those years' own baselines, against 0.0042% to 0.1700%
  for the other four. Those are the two years the archive cannot supply in bulk: measured, only 5.4% of
  1996 pairs and 12.6% of 1997 pairs have an in-year capture at all.
- **Admissible without qualification.** `isc_survey` carries `artifact_listing`, a self-dating master
  type: a dated survey edition enumerating hostnames. No corroboration split applies, and the nine
  invariants pass.
- **Re-scored with his own calculator: 19,522.3766 against our 19,522.3766, difference 0.0000, zero
  records rejected, zero already in his merged files.** The round now stands at 46,952 records and
  0.313543%.
- **The mean weight is honest and low**, 0.4158 across the round against 0.6377 last round, because
  per-TLD shards are dominated by small non-English ccTLDs. Quoting the record count without the weight
  would overstate this by roughly a third.

**Two lessons, and the second is the one worth keeping.**

The narrow one: a broken step in a six-stage reproduction path hides everything downstream of it.
Stage 2 aborting meant stages 2 to 6 had not run end to end for days, and nobody noticed because the
individual ingests were being run by hand.

The general one: **this is the reviewer's first priority, and it was answered by running the pipeline
rather than by looking for it.** He asked us to "identify unprocessed files, failed parses, truncated
runs, unqueried candidates". 496 downloaded files that no ingest had ever read is the purest possible
instance, and it was invisible to every measurement taken this round because those measurements all
started from the store. **A residual-opportunity audit should begin by diffing what is on disk against
what the ledger has read.** That diff is cheap, it needs no network, and it should be the discovery
harness's first check rather than an accident.

**Signed off by Ivo: pending.**

## 2026-08-10 (attrition.org ingested, and gzip made journals reproducible)

Ivo's ruling on the licence question: if there are validated, evidenced domains sitting around, ingest
them and document it.

- **Built in the tree rather than trusting the probe's TSV.** `scripts/collect_attrition.py` reads the
  33 index pages already on disk and sends no request. **5,816 net-new pairs worth 2,791.4410
  equivalent-English** at mean weight 0.4800, re-scored with the reviewer's own calculator: zero
  rejected, zero already his, agreement to 0.0000.
- **`artifact_listing`, and deliberately no corroboration split.** The mirror operators saved a copy of
  the page at that host on that date, so a name that did not resolve could not be in the index: the
  hostname is verified by the act of mirroring rather than typed from memory, which is the property the
  split exists to supply for a hostname written into a Usenet post. Same class of claim as `isc_survey`
  and `uucp_map_registry`. Filed under its own provenance lineage, `defacement_mirror`, since a break-in
  is independent of every crawl, of Usenet and of the registries.
- **The date is carried twice and the cross-check is scoped to the year.** 13,647 of 13,793 rows carry
  both the `[99.11.30]` prefix and a `1999/11/30/host/` mirror path and agree. Fourteen disagree: twelve
  by a single day, which cannot move a record between annual files and are kept, and **two by a whole
  year, which is exactly the error that would file a domain wrongly, so those are dropped**. Dropping all
  fourteen would have been tidier and would have thrown away twelve real observations to guard a risk
  they do not carry.
- **The 6 August estimate was 11% high**, 6,458 pairs and 3,174.08 EE against 5,816 and 2,791.44. Same
  mechanism as every other overshoot in this log: the store grew between the measurement and the ingest,
  so pairs counted as net-new then were already held by the time it ran.
- **On the licence, recorded so the position is auditable rather than assumed.** What is taken is facts,
  `(hostname, year)` pairs, not the mirror's pages, prose, selection or arrangement. Attribution is given
  in `sources.md` and in the report, and every row carries an evidence URL pointing at the individual
  mirror entry, which is stronger attribution than `CC-BY-NC-SA` asks for. It contributes 5,816 of 11.4M
  records. **The decisive property is reversibility**: the rows carry their own `source_id`, so the source
  can be deleted and the export regenerated in minutes if the view ever changes.

**A wrong turn worth recording, because it names a real distinction.** The out-of-window hosts were first
written as a journal for a `link_target` source. Both records came back `malformed`, because the shared
journal parser requires `year in YEARS` by design: a journal of out-of-window rows is rejected wholesale.
**The candidate pool is entered by seed file, not by journal.** The two hosts turned out to be in the
baseline already, so the pool gained nothing, but the spec that could never work is gone and the seed
file is what a wider pass would use.

**Then a defect the ingest surfaced, and it was ours rather than the source's.** Re-writing the journal
with unchanged records was refused as "ledgered with different content (sha256 mismatch)", because
`gzip.open` stamps the current time into the header. So **every collector journal in this project was
byte-nondeterministic**, and tier 2's byte-identical rebuild claim was quietly false for all of them.
Fixed: `gzip.GzipFile(..., mtime=0)`, verified by writing the same 500 records twice and comparing
hashes. Re-offering an ingested journal is now a no-op by construction rather than usually.

The audit below found the same defect had already fired once, undetected: the 148-archive batch of
8 August was split twice, under tags `sprint083312` and `auto084548`, and **both journals were ingested**
because content-identical gzip files hash differently. It cost nothing, and the reason is worth knowing:
`bulk.ingest_files` inserts evidence under `WHERE NOT EXISTS (domain, year, source_id)`, so the loader is
idempotent per source whatever it is offered. Measured: 0 exact duplicate rows in `usenet_announce`.

**Store and disk were reconciled rather than papered over.** The first ingest had already loaded the
records under a hash no file now matched. Options were to edit the ledger's hash by hand, or to remove
the source's rows and re-ingest. The second is the honest one, so: 12,653 evidence rows and 5,816
assignments deleted (verified first that **none** of those 5,816 pairs had other master evidence, so the
delete restored the exact pre-ingest state), the ledger rows cleared, and one clean ingest. It reproduced
12,653 / 5,816 / 12,309 exactly, which is itself the proof the content never changed. Two things learned:
DuckDB's foreign-key check does not see a delete made earlier in the same transaction, so the statements
must be separate; and **the ledger keys on `source_name`, not on the spec key**, so a delete written
against `attrition_dated` silently matches nothing.

**Signed off by Ivo: pending.**

## 2026-08-10 (the three empty Usenet directories: drained, not broken, and the corpus audited in full)

Ivo asked for the empty probe directories to be explained and the whole Usenet story documented. Two
investigators and one adversarial verifier, all read-only, every figure re-derived independently.

- **They are empty because they were successfully drained.** `ingest_usenet_batched.sh` globs across all
  `usenet_probe*/` directories into one queue and `mv`s archives into `data/raw/usenet/` in batches of
  400. **A `mv` out of a directory updates the source directory's mtime**, so 23:08:07, 23:20:14 and
  23:42:29 are removal times, not creation times, and they match three of the nine "moving N archives"
  lines in `data/logs/usenet_batched.log` to the second. That log ends "4175 archives in
  data/raw/usenet, 4175 marked processed".
- **Nothing was lost, checked four ways.** All 3,479 archives the probe logs recorded are on disk and in
  `.processed`, which is written only after both journal halves ingest cleanly. Every one of the 19,231
  archives on disk **matches its catalogue size to the byte**, with no partial or `.tmp` file anywhere,
  which is the check that would catch a move-then-truncate and which neither investigator ran until the
  verifier did. The union of every `fail` line in every log gives 722 names, all on disk bar two. And the
  12 and 22 minute mtime gaps are ingest work, not backoff: six further batches ran inside the 22.
- **Both of the hypotheses I put to the investigators were wrong**, and were excluded rather than merely
  not chosen. A zero-group run cannot have made these directories, because `probe_usenet_groups.py`
  guards `if not groups: raise SystemExit` **before** its `mkdir`; and the one-shot
  `mv data/raw/usenet_probe*/*.mbox.zip` the handback suggested would have stamped all four with a single
  second, where the observed mtimes span three.
- **The corpus is complete and fully processed.** Catalogue 19,233 groups over 12 hierarchies,
  411,214,378,850 bytes. On disk 19,231, 411,023,158,296 bytes. `.processed` 19,231, set-identical to
  disk in both directions: **zero unread archives, zero orphans**. The two absent groups are `alt.irc`
  and `alt.music.oasis`, refused with HTTP 500 and 502 across two separate retry runs, together 0.05% of
  the corpus. Declare the download done.
- **Two documented claims were stale, in opposite directions.** "1,773 archives on disk have never been
  opened" is now zero under the ingestion reading; under the document's own reading, which is
  *unmeasured*, it is far worse than 1,773: the newest whole-corpus yield run covered 1,706 archives, so
  **17,525 have never been priced**. And `alt.*`'s "14,910 groups, 229 GB, the only untested population
  at scale" was the **remainder unprocessed at the end of 1 August**, which reproduces from the ingest
  log to the byte (378 groups processed, 4,502,811,697 bytes, remainder 229,554,674,237). `alt.*` is
  15,288 groups and 218.0 GiB, of which 15,286 are downloaded and all 15,286 processed. It is 79% of the
  groups and 57% of the bytes and its yield is entirely unknown, which makes it the largest open question
  about the project's largest source, answerable by a screening pass over local files.
- **Two precise coverage gaps found.** The header pass and the first address pass each read 19,083
  archives rather than 19,231, because the 148-archive `auto084548` batch landed between them; so those
  148 were never header-scanned. And the bare-host pass enumerated all 19,231 but **only 9,759 produced a
  single row**, which is the fact to know before extrapolating from a sample of it.
- **A 22-batch failure loop on 6 and 7 August was lossless**, and the guard is why. Every batch died in
  about nine seconds on `AttributeError: 'Header' object has no attribute 'strip'`, and because
  `ingest_new_usenet.sh` appends to `.processed` only after a clean ingest, each retry re-offered the same
  2,500 archives until the fix landed. None of the 22 tags' journals reached disk or the ledger.
- **Three measurement traps worth carrying forward.** `ls data/raw/usenet/*.mbox.zip | wc -l` returns
  **0**, because 19k arguments overflow the exec limit and `2>/dev/null` swallows the error: use `find`.
  `command grep -c "A|B|C"` is BRE, so the pipes are literal and it returns 0 by construction. And
  `split_usenet_addresses.py` globs `usenet_*.jsonl.gz` in its own `--in-dir` and writes its output back
  into that same directory, so a second run there would re-consume its own output.
- **The verifier overturned four claims and caught two citation errors**, including a search scoped to
  `data/raw/usenet*` that missed two journals one directory over in `data/staging/`. That is the same
  scoping trap the audit was warned about, so it is worth naming again: **a search that finds nothing has
  either proved something or been pointed at the wrong place, and those look identical.**

**Signed off by Ivo: pending.**

## 2026-08-10 (the query queue could not be built at all, and what merged260810 did to it)

- **Five VPS journals were stranded and are now banked.** The VPN came up, `engine_status.sh` listed
  five of 221 journals missing locally, and the documented rsync plus `ark ingest cdx_snapshot` folded
  them in: 1,500 journal lines, 2,141 evidence rows, 879 year-rows, 796 distinct domains. Scoreboard
  moved 52,768 to **53,647 net-new pairs**, 22,313.8176 to **23,123.9945 EE**, 0.3584% to **0.3714%**,
  at a mean weight of 0.9217 because shard 1 is `.uk`-heavy. The VPS itself was healthy, up 3 days
  5 hours, its last batch 300 queried for 244 captures and 905 year-records.
- **`just query-queue` and `just query-queue-preview` had both been failing outright since this
  morning.** `10ec347` moved the round window into `ark.baseline`, which was the right fix for a stale
  window, and rewrote `WHERE y.verified_at >= TIMESTAMPTZ '2026-08-03 18:09:00+00'` as
  `WHERE y.verified_at >= TIMESTAMPTZ ?`. DuckDB's parser accepts a type name before a *literal* and
  not before a placeholder, so `build_query_queue.py` raised `ParserException` before reaching any of
  its work. Both recipes share that code path, so the preview could not report the problem either.
- **So the shards on disk were not stale through neglect: they were the newest anybody could have.**
  `queue_shard0.txt`, `queue_shard1.txt` and `queue_manifest.tsv.gz` are all stamped 2026-08-08T07:05Z,
  which is the last moment the builder ran. Worth recording as a pattern rather than a typo: the fix for
  one trap in section 6 of the handoff created another one in the same list, and the only visible symptom
  was a file date that looked like a discipline problem.
- **Fixed by naming the query.** The cast is now `CAST(? AS TIMESTAMPTZ)`, and the SQL moved out of
  `main()` into `round_netnew_by_tld(conn, since)` so it can be tested at all. Two tests in
  `tests/test_build_query_queue.py` pin the parse, the window filter and the exclusion of
  already-credited baseline pairs. Verified against the live store: it returns 53,647 pairs and
  23,124.0 EE, which agrees with `ark stats` through an independent code path.
- **What the release did to the queue, measured rather than assumed.** Built in memory against the
  current store and diffed against the preserved 2026-08-08 shards, so the unit is a target and not a
  pair: 2,965,226 targets then, 2,974,560 now, but **197,977 created and 188,643 gone**. The net size
  barely moved and the membership churned by about 6.7%.
- **The churn is concentrated where it costs most.** Of the 197,977 new targets, **2,826 sit inside the
  current best 10,000** and only 3,766 inside the best 100,000, with a median rank of 1,894,458 of
  2,974,560. So 28% of the head of the queue was invisible to the shard the VPS was working, while most
  of the churn is tail that no run this round will reach. New targets are `com` 103,837, `ca` 30,681,
  `net` 21,922, `org` 11,850, `uk` 9,992. Their summed score is **98,916.7 EE, which is an expectation
  built from measured hit rates and not a measured yield**; the realised figure will be lower.
- **Decision: rebuild before restarting, and extend the VPS deadline.** Ivo asked for the collector to
  keep running through the round as the backup while attention goes to discovery, so the supervisor is
  restarted on a freshly built shard 1 rather than left to expire at 2026-08-19T11:30Z.

**Signed off by Ivo: pending.**

## 2026-08-10 (`alt.*` is priced from the store, and it is proportionate rather than exceptional)

- **The largest open question about the largest source was answerable in SQL, not by a screening pass
  over 383 GB.** Every Usenet evidence row carries its newsgroup as the first token of
  `evidence_value`, and `domain_year.evidence_id` names the one row that won each assignment, so the
  yield partitions by group with no double counting. That is the same store-side attribution the trade
  press used instead of trusting a collector's own count.
- **Measured, read-only:** `alt.*` holds **439,717 assigned pairs over 352,489 domains, worth 237,158
  equivalent-English, from 8,262 of its 15,288 groups**. It is 57% of the bytes and **54% of the
  assigned equivalent-English**, at 1,013 EE per GB against a corpus mean of 1,065. The parse is
  validated by two figures reproducing `sources.md` exactly: 15,288 `alt.*` groups over 234.1 GB, and
  19,233 groups over 411.2 GB for the catalogue.
- **The standing `[GUESS]` is half right and its conclusion was wrong.** 7,026 of 15,288 `alt.*` groups
  won nothing at all, so the vanity-archive intuition holds at group level. It does not hold at
  hierarchy level, which is the level the decision is taken at, so screening `alt.*` will not find a
  hidden tranche.
- **Density ranks the small worked hierarchies first, not the big unworked one:** `biz` 3,105 EE/GB,
  `can` 2,478, `comp` 2,441, `misc` 1,158, `aus` 1,030, `news` 1,025, `alt` 1,013, `rec` 1,008, `uk`
  1,001, `sci` 671, `soc` 297, `talk` 60.
- **"17,525 archives have never been through `measure_usenet_yield.py`" is the wrong frame, and running
  it would have proved nothing.** That script measures what an archive *would* add, and every archive is
  already ingested, so it reads near zero by construction. It is trap 9 inverted: a population that
  structurally excludes the outcome being counted.
- **Confirmed independently from the same query:** net-new equivalent-English is **0.0 for every
  hierarchy**, because `merged260810` absorbed all of phase 4. The store's 53,647 net-new pairs are
  isc_survey 42,299, attrition 5,816 and ia_cdx_bulk 5,532, and nothing else.
- **Consequence for the round.** The only Usenet lever left is a fourth extraction seam, the three
  worked seams already cover the whole corpus, and the machine-written header seams are closed on
  measurement. No candidate fourth seam is currently known, so `alt.*` leaves the priority list.

**Signed off by Ivo: pending.**

## 2026-08-10 (priority (d) implemented: discovery and completeness, scored separately)

- **The reviewer asked for two outcomes to stay visible and only one was being scored.** `ark stats`
  counted `netnew_domains` but attached equivalent-English to **pairs** alone, so "genuinely unknown
  domain" and "year filled on a domain he already has" could not be quoted side by side, which is
  exactly what priority (d) asks for.
- **Implemented as a partition rather than two independent counts**, because the near miss here is
  trap 11. `_equivalent_english` now classifies each net-new pair by whether its **domain** carries any
  `prior_reused` evidence at all: no baseline evidence anywhere is `discovery`, baseline evidence for
  some other year is `completeness`. The two are disjoint and exhaustive over the net-new pairs by
  construction, and a test asserts both the pair totals and the equivalent-English totals add back to
  the headline.
- **Breadth is scored once per domain, not once per pair.** `ee_netnew_domains` sums the weight over
  distinct discovered domains, so a domain found in four years is one discovery worth one domain's
  score. A second test pins that with a two-year domain, which is the shape that produced the
  1,161,961-against-463,566 error.
- **Measured on the live store the same evening:** 53,647 net-new pairs worth 23,123.9945 EE split
  **29,375 discovery pairs worth 14,729.1125** and **24,272 completeness pairs worth 8,394.8820**, over
  **25,152 discovered domains worth 11,349.3654 as breadth**. Both partitions add back exactly.
- **Worth reporting to him plainly: 63.7% of this round's equivalent-English is discovery**, which is
  the half he asked to be prioritised. That figure did not exist before this change.
- The five fields in `round_figures.py` are his own format and are untouched. Carrying the split into
  `docs/report.template.md` is a report decision and belongs with the round's write-up, not here.

**Signed off by Ivo: pending.**

## 2026-08-10 (`just residual`: the reviewer's first priority, mechanised)

- **Built because the highest-yield check the project has ever run was run by hand, once.** The 496 ISC
  survey shards worth 14,956 equivalent-English were found by diffing disk against the ingest ledger,
  and they had been on disk for five days while every measurement taken here was blind to them. Every
  measurement starts from the store, so nothing that starts from the store can see a file the store has
  never read. `scripts/audit_residual.py` is that diff, generalised into five checks, wired as
  `just residual`.
- **The two directions are both needed, and finding only one reads as clean.** `unread` is a documented
  glob matching files the ledger has never read, which is lost yield. `glob_too_narrow` is the opposite,
  a file the ledger holds that the documented glob cannot reach, which loses nothing today and makes
  `just reproduce` rebuild a store missing it. Both have happened, the second twice on 2026-07-26.
- **It found five reproduction gaps on its first run**, each a file that is in the store and unreachable
  from the documented path: `cdx_gap_frontier_20260805T225930Z.jsonl.gz` under `ia_cdx_bulk`,
  `usenet_addr_dated.jsonl.gz` and `usenet_addr_candidates.jsonl.gz` (the recipe names the `_r2`
  journals only), and `usenet_dated_resplit260806new.jsonl.gz` with its candidates pair. That is the same
  class as the `usenet_hdr` gap already documented in `sources.md`, found automatically rather than by
  reading.
- **And two genuinely unread journals, both now ingested.** `cdx_q1_20260810T164516Z.jsonl.gz`, the batch
  the VPS published when it was stopped for the restart, worth **101 further year-rows over 120
  domains**; and `expand_20260726T004331Z.jsonl.gz`, which is three failed fetches and no evidence, now
  ledgered so it stops being reported and the replay path is complete.
- **`stale_derived` is anchored on evidence, not on the file ledger.** The legacy loader writes no
  `ingested_file` row a glob can find, so the check dates the release from the newest `prior_reused`
  evidence row instead, which is the thing that actually changed. `merged260810` landed 2026-08-10
  10:35:55Z. It reads the timestamp as epoch seconds inside SQL, because DuckDB needs `pytz` to hand a
  TIMESTAMPTZ to Python and that is not a dependency here.
- **Verified against today's own failure:** run before the rebuild it flags all three queue artifacts as
  STALE, and after it flags none. It currently reports `gap_candidates.txt` (2026-08-05) and
  `creation_candidates.txt` (2026-07-31) as stale, both of which predate the release.
- **Deliberately not a gate, and the reason is worth keeping.** Unread material on disk is a fact about
  the round, not a broken invariant, and a check that failed the build for it would be turned off within
  a week. It reports and exits 0. The distinction is the same one `ark check` already makes between a
  check that found nothing wrong and one that examined nothing.
- **The `ACCOUNTED` table is the part that will rot**, and it is named here so the next person knows. It
  lists the directories under `data/raw/` that are collector inputs or measured rejects, with the reason
  per entry, so `unreferenced` reports only genuinely unaccounted material instead of every OCR cache
  file. A new download with no ingest line will appear there correctly; a new download that is
  deliberately input-only needs a line adding.

**Signed off by Ivo: pending.**

## 2026-08-10 (`just screen`: the dead-lead register becomes a check rather than a reading assignment)

- **`docs/discovery.md` already says an automated discovery agent will walk straight back into fifty
  closed families unless it reads the register first, and that reading it is the cheapest step in the
  process.** It is also the step most likely to be skipped, because it means reading a 1,549-line
  document before every idea. `scripts/screen_hypothesis.py` does it mechanically, wired as
  `just screen`.
- **The register is parsed out of `docs/sources.md` at run time and never copied.** That is the whole
  design constraint: a hand-kept second copy of those verdicts is exactly how they come to disagree, and
  that file already carries the scar, a snapshot table claiming to be generated that had omitted the
  round's largest contributor by the time anyone checked. Three shapes in the document carry a verdict
  and all three are read: rows of the `Evaluated and rejected` table, `## ` headings that say rejected,
  and inline `**Verdict: REJECT ...**` lines. It currently parses **59 closed leads**.
- **Gate 2 is what dates one item, and it refuses rather than warns.** `self`, `typed` or `undated`, and
  with no claim stated it exits 2. That is not ceremony: the answer decides what the source can ever be,
  and it also decides whether widening extraction is safe. A `self`-dating source has no wall behind its
  pattern, so a bad match becomes a master claim and the advice is to tighten; a `typed` source takes the
  corroboration split, which is why `usenet_bare` could afford recall.
- **Two calibration decisions worth recording, because both are the difference between a useful tool and
  an ignored one.** A stop list removes the words that do not discriminate in this domain: without it
  `archive` alone collides with most of the register, every proposal is flagged, and the reader learns to
  skip the output. And a collision needs two shared terms, except that a single term occurring in exactly
  one register entry counts, since `ircache` or `geocities` is decisive on its own.
- **Tested against the real document on purpose.** Three tests read `docs/sources.md` itself and assert
  the parse finds at least 40 leads including `ircache`, `geocities`, `edgar`, `common crawl` and
  `webbase`. A parser that quietly stopped matching the file would report "no collision" for everything,
  which is the worst available failure here because it reads as permission.
- **Verified on three real cases:** a reproposed shareware CD-ROM catalogue collides with both closed
  entries at 4 and 3 shared terms; `NLANR IRCache proxy trace logs` collides with the entry recording the
  squatted domain and dead FTP; `municipal library card catalogue microfiche` does not collide.
- **What it deliberately does not do is price anything.** Pricing is a sample measured against the live
  store and needs a parser per source, so a generic pricer would have to guess at one and would produce
  exactly the confident wrong number section 6 of the handoff lists eleven ways to produce. The honest
  automation boundary is: propose, screen, state the dating claim, then measure by hand with the existing
  discipline.

**Signed off by Ivo: pending.**

## 2026-08-10 (PANDORA title index read and seeded, seed-only, with the expectation stated as near zero)

- **One of the four "bytes nothing reads" directories is now read.** `data/raw/pandora-titles/` held the
  National Library of Australia's PANDORA Title Entry Page index with its schema and crawl documentation
  beside it, and no file in the tree mentioned it. It is the reviewer's first priority in its most literal
  form, so it was measured before anything was written.
- **Measured 2026-08-10, read-only and offline:** 87,732 rows, 87,658 carrying a `gathered_url`, 2,285
  URLs from which no registrable name could be read, **35,391 distinct registrable domains of which 29,432
  the store did not know at all**. By TLD: `au` 16,658, `com` 8,271, `org` 3,002, `net` 757. That
  reproduces the figure already in `sources.md` (29,594 unknown) to within the store's own growth since it
  was taken, which is the check that the reading is right.
- **It is seed-only and permanently so.** The index has no date column of any kind, so nothing in it can
  evidence a year. Writing these names into annual files would be the DMOZ error `SPEC.md` III.3 names
  explicitly. They enter the candidate pool carrying no evidence row and claiming nothing.
- **Seeded anyway, and the reason is not optimism.** He asked for the pool to be as large as practicable
  (III.2, IX) and `.au` carries the highest English share in the table at 0.9904. The **UPPER BOUND** if
  every new name earned exactly one year is **24,571 EE**, and that is a bound rather than a projection.
  The measured expectation is close to zero for two reasons already on record: a 60-domain sample of this
  same list against the working AWA endpoint returned **zero** in-window captures, and the index spans
  PANDORA's whole run rather than the window, so a large share of its titles postdate 2001 outright. The
  cost is one local pass and no requests, and the pool scorer ranks by measured hit rate, so worthless
  names sit in the queue's tail rather than displacing anything.
- **A canonicalisation fact worth knowing before anyone reads the `.au` count as government sites.**
  `lawlink.nsw.gov.au` collapses to `nsw.gov.au`, because the pinned Public Suffix List snapshot carries
  `gov.au` and not the per-state `nsw.gov.au`. That is left alone rather than corrected: the whole corpus
  was canonicalised through this list, III.8 asks for registered domains, and changing the pin would move
  every figure the project has ever quoted. The 35,391 count is already post-collapse, so it is not
  inflated by it.
- Reproducible as `just pandora-seed`, documented as its own section in `sources.md` per XI, and the four
  unread directories are down to three.

**Signed off by Ivo: pending.**

## 2026-08-10 (the residual auditor failed its first real test, which is why it now waits 15 minutes)

- **Found by running `just residual` while `ark seed` held the write lock**, which was an accident of
  timing rather than a designed test and is the only reason it surfaced tonight. Two defects, both in the
  new tool:
- **The retry budget was sized against the wrong writer.** 40 attempts at 3 s is 117 s, justified in the
  docstring against `just maintain`, which holds the lock for seconds every 15 minutes. The writers that
  actually exist are longer: `ark seed` over 29,432 names held it for **more than twenty minutes**, and a
  multi-journal ingest holds it for minutes. So a read-only audit gave up at exactly the moment the audit
  was worth running. Patience is now 900 s, and it prints one line when it starts waiting so it does not
  look hung.
- **And it ended in a raw DuckDB traceback.** For a read-only reporting tool that reads as a defect in the
  tool rather than as a busy store, which is the same distinction `documentation.md` already draws between
  a verdict and a question that did not land. It now exits with one line naming the writer's PID and
  saying plainly that waiting is the correct behaviour.
- **A non-lock error is still raised untouched**, and there is a test for it: waiting is right for a lock
  and wrong for a missing or corrupt file, and swallowing the difference would turn a corrupt store into
  "busy, try later".
- **The general point, which is why this is worth an entry at all:** the tool was written and tested
  against a quiet store, and the first thing it met was a loud one. Both tests added here assert
  behaviour under a writer, so the next change cannot quietly reintroduce either failure.
- **Separately, `ark seed` is far slower than it needs to be, measured but not changed.**
  `seed_from_file` calls `add_candidate` in a Python loop, so seeding 35,391 names is **29,432 single-row
  `INSERT`s into a columnar store**, and `to_registrable` runs twice per line (once in the loop, once
  inside `add_candidate`). Measured at 106% CPU for over twenty minutes for work a batched insert would do
  in seconds. Not touched tonight because it is a core write path and the round's priority is discovery,
  but it is a small, well-scoped fix and it blocks every other store write while it runs.

**Signed off by Ivo: pending.**

## 2026-08-10 (the RDAP candidate-pool sweep, and the crossover question answered the other way round)

- **The handoff's open question was "where does the RDAP tail's marginal EE per query fall below the
  archive queue's head?" Asked that way it has a misleading answer.** Measured tonight, RDAP returns
  **0.0552 equivalent-English per query** against the rebuilt archive queue's **0.7869** at its head, so
  per query the archive is 14x better and the RDAP tail looks finished. Per **hour** it is the reverse:
  the archive is capped by per-IP concurrency at about 506 queries an hour, while RDAP direct to Verisign
  sustained **118 queries a second** tonight, so the same wall-clock hour buys roughly 400 EE from the
  archive and roughly 23,000 from the registries. **The two do not compete for the same resource, so
  marginal value per query is the wrong denominator; the right one is per hour of the constraint each
  route actually binds on.** That is why this ran underneath the round rather than instead of anything.
- **Measured rate, 32 workers, direct to the registry:** 300,000 queries in 55 minutes, **118 q/s**,
  against the 75 q/s recorded on 8 August. 17 throttles from `rdap.verisign.com` in a 100,000-query batch
  and no refusals, so the ceiling is not yet found. `ark rdap` paces each registry with its own governor.
- **Yield decay is real and now quantified.** `build_rdap_pool_list.py` expected a 12.7% in-window rate
  and 0.077 EE per query from the pool-wide prior. Realised over the first 300,000 queries of this sweep:
  30.2% returned any creation date, **8.73% returned one in window**, and **0.0552 EE per query, which is
  72% of the expectation**. The list is ordered by how many distinct sources saw a name, and about 311,000
  had already been asked before tonight, so this is the tail of the head rather than the head.
- **Ingested: 26,193 records over 26,193 distinct domains**, one year each. Every one is a candidate that
  held no year at all, so **every one is a net-new DOMAIN and not merely a net-new pair**, which is the
  half of priority (d) he asked to be prioritised. Journal-side and store-side counts agree exactly, which
  is the check that the ingest read what the collector wrote.
- **Round after this ingest: 79,941 pairs, 51,345 net-new domains, 39,765.0763 EE, 0.638654%.** Up from
  53,647 / 25,152 / 23,123.9945 / 0.3714% before it. By source the round is now `isc_survey` 42,299 pairs
  and 14,956.3877 EE, **`rdap_snapshot` 26,193 and 16,556.5953 at mean weight 0.6321**,
  `attrition_defacement` 5,816 and 2,791.4410, `ia_cdx_bulk` 5,633 and 5,460.6523 at mean weight 0.9694.
  RDAP is the round's largest single contributor by equivalent-English.
- **Verified with his own `equivalent_english_domains.py`: 79,941 records scored, 0 rejected, 0 already in
  his merged files, agreement to 0.0000.** That matters more than usual here, because 26,193 records
  arrived tonight from a route whose output his validator had only seen 48,394 of before.
- **Where it lands is the useful part.** 1998 net-new pairs went from 84 to 4,362 and 1999 from 1,582 to
  8,767, because a creation date does not need the site to have been crawled. Per-year growth on each
  year's own baseline is now 1996 0.7416%, 1997 1.5629%, 1998 0.3406%, 1999 0.4454%, 2000 0.7089%,
  2001 0.4154%.
- **Two figures that look like a contradiction and are not.** `round_figures.py` reports 75,045 distinct
  domains in the increment and `ark stats` reports 51,345 net-new domains. The difference, 23,700, is
  domains the baseline already holds that gained a year, which is exactly the distinction priority (d)
  exists to keep visible. The new discovery/completeness split reports both halves and they add back to
  the headline exactly: 31,285.7078 plus 8,479.3685 is 39,765.0763.
- **Discovery is 78.7% of the round's equivalent-English**, up from 63.7% before this ingest.

**Signed off by Ivo: pending.**

## 2026-08-10 (a fabricated namespace ranks high on expected value: the pool/held ratio catches it for one query)

- **Looking for RDAP headroom beyond com and net turned up `.gov` fourth in the queue, and it is junk.**
  Measured: 81 askable TLDs hold 2,069,480 candidate-pool names, 786,349 already asked, so **1,357,792
  never asked**. By unasked volume: `com` 357,948, `net` 323,352, `org` 308,231, **`gov` 185,803**,
  `uk` 66,590, `ca` 28,191, `au` 22,596. At a 0.9825 English share `.gov` carries an upper bound of
  182,551 EE, which ranks it above `.uk` and `.ca` together.
- **It is fabricated, and the discriminator costs one query.** Names holding a year against names in the
  pool: `.com` 0.3, `.uk` 0.3, **`.gov` 182.0, `.mil` 2,623.6**. Against a baseline 11.4M records deep a
  real namespace cannot have 182 undated candidates for every dated one. The sample settles it:
  `wavohsdojde.gov`, `xkgnmoaeg.gov`, `whpcsygq.gov`, `xquhue.gov` are invented, and `empty.gov`,
  `unit.gov`, `higher.gov`, `dessert.gov` are prose words a bare-host rule read as hostnames. `.mil` is
  already excluded because no RDAP service answers for it, which is luck rather than design.
- **This is the `.au` mistake in a new place**, and worth naming as a class rather than an instance:
  ordering by `P(hit) x English share` will do this whenever the probability half is a prior rather than a
  measurement, and **a 0.9825 share times an invented name is still zero**. `.au` cost 1,709 queries for
  five hits by the same mechanism.
- **Implemented as a printed warning in `build_rdap_pool_list.py`, not as an exclusion.** `pool_plausibility`
  reports dated, pooled and the ratio per askable TLD and warns above 10x. Which TLDs to exclude is a
  judgement about the corpus rather than a fact about the pool, and `--tlds` already exists to act on it.
  Run tonight it flags 8: `gov` 182.0, then seven tiny ones (`name` 62.0, `sd` 30.0, `ht` 24.0, `re` 21.0,
  `pm` 19.0, `pro` 16.5, `cm` 15.9) whose absolute volumes are in the tens.
- **The threshold is not tuned.** Real namespaces measure 0.3 and fabricated ones 182 and 2,624, so
  anything between 1 and 100 separates them; a test asserts the constant stays in that range rather than
  asserting the value.
- **Consequence for the sweep still running:** it is `com,net` only, so it is unaffected. The next sweep
  should be `com,net` again plus a decision on `.org`, which is the best in-window rate measured anywhere
  (24.9% on answers) and whose registry returns 403 for thousands of consecutive requests after about 850.
  That is a rate-limit negotiation rather than an engineering problem.

**Signed off by Ivo: pending.**

## 2026-08-10 (the screener run on ten fresh hypotheses, which found a defect in the screener)

- **Ran `just screen` over ten hypotheses to see whether the harness does anything**, which is the round's
  ask in miniature: generate, screen, keep survivors. Result: **seven survive gate 1, three collide**, and
  two of the three collisions were **false positives caused by the screener itself**.
- **"INET conference proceedings 1996-2001" was reported as colliding with "SEC EDGAR filings
  1996-2001".** Their only shared term was the window. Every source in this project is about 1996-2001, so
  the range appears throughout the register, and it happens to occur in exactly one entry *name*, which is
  what made the single-rare-token rule fire on it. **A date says when, never what.** Tokens that are
  purely numeric or a numeric range are now dropped.
- **"Apache Software Foundation project release announcements" collided with "OCLC Web Characterization
  Project" on the word `project`.** Added to the stop list with `programme`, `record`, `entry`, `metadata`
  and `content`, all of which name a shape rather than a source.
- **The remaining collision was correct and useful:** university course syllabi hit "Institutional link
  directories: university, library, government, museum", which measured 2 net-new domains over 388 and
  ~0.02 EE per page fetch. That is the tool doing its job, and it would have cost an afternoon.
- **Verified with negative controls, per the handoff's rule that a search finding nothing has either
  proved something or been pointed at the wrong place.** Two known-closed leads were re-screened after the
  fix and both still fire: shareware CD-ROM ISO catalogues, and IRCache/NLANR proxy traces. So the fix
  narrowed the matcher without disabling it, and two tests pin exactly that: the year-range case must not
  collide while "SEC EDGAR quarterly filings" still must.
- **The seven survivors, all `typed` (a hostname a human wrote inside a dated artifact, so all would take
  the corroboration split), unpriced and in no order:** RFC and Internet-Draft documents; CPAN/PAUSE module
  release metadata with author homepage fields; Linux Software Map entries with `Entered-date` and `Site`;
  Debian changelogs and upstream homepage metadata; INET conference proceedings 1996-2001; the W3C
  technical reports index; the hobbes OS/2 archive index; Apache release announcements; Netcraft monthly
  survey hostname lists.
- **Surviving the screener is not a recommendation and none of these is priced.** Several look like the
  authority-selecting shape that has killed four families already: RFCs, W3C and Apache are exactly the
  heavily-crawled institutional population a CDX-derived baseline holds first, and Netcraft published
  aggregate counts rather than hostname lists as far as anyone here knows. The two worth pricing first on
  the project's own pattern are the ones whose items are **dated records naming a third-party site**:
  **the Linux Software Map** and **CPAN/PAUSE**, both of which are the Tucows shape, which worked.

**Signed off by Ivo: pending.**

## 2026-08-10 (the loop run end to end on one hypothesis, and it closed on measurement in an hour)

- **This is the round's ask done once, small, with a real verdict at the end.** `just screen` generated the
  Linux Software Map as a survivor, the structure checked out, pricing killed it, and it is now a row in
  the rejected register that the screener itself will match next time. Total cost: **two HTTP requests to
  a non-IA host and about an hour**, no Internet Archive budget.
- **Why it looked right, and it genuinely did.** `https://www.ibiblio.org/pub/Linux/docs/LSM/` serves
  dated snapshots inside the window, and each record is a `Begin3 ... End` block carrying its own
  `Entered-date` next to `Primary-site`, `Alternate-site`, `Author` and `Maintained-by`. So the date is
  intrinsic to the record and the hostname sits beside it, which is the shape of every large win this
  project has had, and specifically the Tucows shape.
- **Measured against the live store: 4,560 records, 3,946 in window, 3,951 distinct in-window pairs over
  2,066 domains, of which 3,743 (94.7%) are already held.** Of the 208 remaining, the corroboration split
  admits **86 pairs worth 37.3 equivalent-English at mean weight 0.4338**; 122 pairs and 56 names go to the
  candidate pool. Against an acceptance bar of ~5,000 net-new pairs that is a reject by two orders of
  magnitude.
- **The reason is the standing structural one, now on its fifth family.** A Linux author's own homepage is
  the heavily-crawled population a CDX-derived baseline holds first, after Usenet relay hops, institutional
  link directories, award galleries and mailing lists. **A source that selects for authority cannot be
  net-new, however well dated it is.** Worth noting that the dating was never the problem: it was the best
  dating of anything assessed this round.
- **The pre-split figure was 208 pairs and 96.1 EE, so quoting it would have overstated the source 2.6x.**
  Small in absolute terms and the same error class as the 24-fold Usenet case.
- **Two parser facts recorded so a future pass does not lose the corpus.** The snapshots are **not** purely
  cumulative: 1999-08-29 carries 897 in-window pairs that 2001-12-01 does not, so reading only the latest
  loses a fifth of the source. And `Entered-date` appears in at least four formats (`27OCT97`,
  `1999-08-29`, `12/03/98`, `Oct 1997`), so a single-format parser silently drops most records and the
  source would read as barren rather than as unparsed. That is the same failure mode as the Giganews
  `YYYY/MM/DD` headers, which cost 21,346 of 23,282 messages before it was found.
- **What the round should take from this is the loop, not the source.** Nine other hypotheses survived the
  screener tonight and none is priced. On this evidence the ones to price are those whose records name a
  **third party's** site rather than the author's own, because that is the only variant of this shape that
  has ever been net-new.

**Signed off by Ivo: pending.**

## 2026-08-10 (the defacement-mirror family closed, and the class that actually pays named)

- **Worth stating the pattern the round has actually demonstrated, because it is the useful output of the
  night's exploration.** The three sources that produced this round's equivalent-English are
  `rdap_snapshot` (registry creation dates), `isc_survey` (dated DNS survey shards) and
  `attrition_defacement` (a dated defacement index). What they share is not their format: they are
  **machine-generated records about every domain in scope, not human curation of notable ones.** The five
  families that have failed on measurement all share the opposite property, and the Linux Software Map
  priced tonight is the fifth. **A source that selects for authority cannot be net-new; a source that
  selects for nothing can.**
- **So the best remaining idea in that class was another defacement mirror**, since attrition's own index
  states it copied its pre-1999 entries from earlier mirrors, meaning siblings existed. It is
  self-dating `artifact_listing`, takes no corroboration split, and the population is whoever was hacked
  rather than whoever was famous.
- **Closed on availability, not on value.** archive.org returns **0** items for `alldas` and **0** for
  `safemode defaced`, and its 212 hits for `defacement` are a 2011 news clip, a malware source dump and
  Indian parliamentary library scans. GitHub is the only reason attrition's own mirror still exists, after
  a 2021 republication, and it holds no sibling: `alldas` gives 14 unrelated modern dashboards, and the
  one defacement archive there is `Mirror-H.org`, a 2010s collection out of window. Recorded with the
  condition that would reopen it: a named surviving mirror.
- **Both of tonight's closures are reportable results in their own right**, per `SPEC.md` IX, which asks
  for limitations and whether further expansion is worthwhile. The honest answer for the curated-directory
  and software-index shape is no, on five independent measurements.

**Signed off by Ivo: pending.**

## 2026-08-10 (the RDAP decay curve flattened, which changes whether to keep sweeping)

- **Measured per batch, in-window records per 100,000 queries:** batch 1 **10,238 (10.24%)**, then 7,841,
  8,114, 8,193, 7,989, 8,128, so **7.84% to 8.19% and flat** after the first batch. The collector's
  any-year date rate is flat too, 27,603 / 28,304 / 28,042 / 27,836 / 28,022 per batch, about 28%.
- **That is not what the 8 August sweep saw and the difference is the reason.** Then, `.com` went 19.2%
  to 11.4% to 8.4% over three 100,000-query blocks. This sweep starts where that one stopped, roughly
  311,000 names deep in a list ordered by how many distinct sources saw each name, so **the steep part of
  the curve was already spent and what is left is the flat tail.** Batch 1 catching 10.24% is the last of
  the shoulder.
- **The decision it changes.** A decaying tail argues for stopping; a flat one argues for continuing until
  something else is worth the hour more. On 8.1% and a `.com` weight of 0.6321, the **~587,000 com/net
  names still unasked project to roughly 47,500 records and 30,000 equivalent-English**, and that is a
  **PROJECTION off a flat six-batch measurement, not a measurement**. At 118 q/s it is about 80 minutes of
  unattended machine time that competes with nothing.
- **The honest caution against over-reading it.** The flatness is measured over 600,000 queries of one
  ordered list, and the ordering is by source count, which is a proxy for realness rather than for
  in-window age. Nothing here says the next 587,000 behave like the last 600,000; it says they are not
  currently decaying. Re-measure per batch and stop when a batch drops materially below 8%.

**Signed off by Ivo: pending.**

## 2026-08-10 (where the round stands at the end of the evening)

Recorded as the historical position, measured after the last ingest and verified with the reviewer's own
calculator. Every figure below is against `merged260810`.

| | at 18:31Z | at 19:22Z |
|---|--:|--:|
| net-new pairs | 52,768 | **120,222** |
| net-new domains | 24,790 | **91,154** |
| equivalent-English | 22,313.8176 | **64,971.6888** |
| growth on his 6,226,386.4245 | 0.3584% | **1.043490%** |
| mean weight | 0.4229 | 0.5404 |

By source: `rdap_snapshot` 66,002 pairs and 41,327.9934 EE at mean weight 0.6262, `isc_survey` 42,299 and
14,956.3877, `ia_cdx_bulk` 6,105 and 5,895.8667 at mean weight 0.9657, `attrition_defacement` 5,816 and
2,791.4410. Per-year growth on each year's own baseline: 1996 0.8011%, 1997 1.7680%, 1998 0.8508%,
1999 0.9903%, 2000 1.4272%, 2001 0.6641%, so every year is now above 0.66% where four of the six were
below 0.17% this morning.

The two outcomes: **95,377 discovery pairs worth 56,057.1059** over **91,154 newly discovered domains
worth 52,677.3588 as breadth**, and 24,845 completeness pairs worth 8,914.5829. The two add back to the
headline exactly. **Discovery is 86.3% of the round's equivalent-English**, which is the half he asked to
be prioritised.

Verified with his `equivalent_english_domains.py`: 120,222 records scored, **0 rejected, 0 already in his
merged files, agreement to 0.0000**. Nine invariants ALL PASS after `ark export`. 320 tests pass.

**Left running deliberately:** the VPS collector, on a freshly built shard 1 with deadline `1788177600`
= 2026-08-31T12:00Z. **Left incomplete deliberately:** the PANDORA seed, 7,843 of 29,432 candidates
landed before it was interrupted to free the write lock for the RDAP ingest; `just pandora-seed` resumes
it idempotently and should follow the batched-insert fix. **Left unasked:** roughly 587,000 com/net pool
names, projecting to about 30,000 EE on tonight's flat 8.1% rate.

**Signed off by Ivo: pending.**

## 2026-08-11 (current state becomes generated, and the handoff retires to legacy)

- **The diagnosis, which is a category error rather than a maintenance failure.** `phase5-handoff.md`
  was a hand-written statement of the **current state** of the project. It was accurate on the day it
  was written and wrong the next morning: `alt.*` had been called the largest open question about the
  corpus and turned out to be proportionate, `just query-queue` which it tells you to run before
  ordering a queue could not run at all, and its state table was two ingests old. **Current state is
  the one category of memory that cannot be hand-maintained**, because it moves faster than anyone
  updates prose, and a stale statement of it is worse than none: it reads as authoritative.
- **Three categories of memory, handled differently from now on.** *Constitution*, which never changes,
  in `CLAUDE.md`, loaded automatically at every session start. *Current state*, generated, in
  `docs/ROUND.md`. *History*, append-only, in `notes.md`. Plus `docs/key-decisions.md` as the short
  review surface for what a human might want to overrule, which is Ivo's idea and fills a real gap:
  `notes.md` at 4,200 lines is not something anyone skims for pivot points.
- **`docs/ROUND.md` restates nothing.** It assembles the output of the programs that already own each
  figure: `ark stats` for the scoreboard and the two outcomes, `round_figures.py` for the five fields
  and the per-source split, `engine_status.sh` for both collectors including its UNKNOWN case, and
  `audit_residual.py` for what is unread. So a producer changing changes the document, and no number
  exists in two places. Written by `just state` in about 39 seconds.
- **Staleness is made detectable rather than prevented, which is the honest guarantee.** The file ends
  in a machine-readable state line, and `just state --check` recomputes those counts against the store
  and exits 1 if they have moved. It cannot promise the file is current; it can tell you in one command
  whether it is, which is what the handoff could not do.
- **The handoff moves to `legacy/docs/` with a banner** saying it is retired and naming the three
  claims that went stale, because its traps and its rejected-source reasoning are still worth having
  and `legacy/` is exactly where things go that are kept for their negative results. `legacy/**` was
  already export-ignored, so its individual `.gitattributes` rule was dropped as redundant.
- **`CLAUDE.md` did not exist**, which is why every session so far had to be told the evidence rules,
  the house rules and the four search traps by hand in a prompt. It now holds only what never changes,
  and points at the generated file for anything that moves.

**Signed off by Ivo: pending.**

## 2026-08-11 (`.org` was never blocked, only paced, and it is the best rate measured anywhere)

- **The register said PIR "blocks rather than throttles": 403 for 9,253 consecutive requests after about
  850 queries. That reading was wrong, and it cost a source for three days.** Probed today at 0.5 q/s
  with one worker and the pace floored so the governor could not ease up: **150 queries, 104 dated,
  zero refusals and zero errors.** A second step at ~2 q/s took the cumulative count past 1,200 with
  still no refusal, which settles the question the original verdict could not: the wall was a **rate
  limit**, not a daily quota and not a block. `SPEC.md` VI is explicit that a rate limit is a signal to
  adjust batch size and concurrency rather than stop, and that is what had not been tried.
- **And it is the best-value registry measured on this project.** Of 150 queries, **52 carried an
  in-window creation date, 34.7% of queries and 50.0% of answers**, against 8.7% of queries for `.com`.
  At a 0.7101 share that is **0.2462 equivalent-English per query, 4.5x `.com`'s realised rate**. By
  year: 1996 3, 1997 7, 1998 11, 1999 11, 2000 14, 2001 6.
- **Per hour it beats the archive queue even at a deliberately crawl-slow pace.** The archive is capped
  by per-IP concurrency at about 506 queries an hour and its queue head is worth 0.7869 per query, so
  roughly 400 EE an hour. `.org` at 0.5 q/s is 1,800 queries an hour at 0.2462, so about 443. At 2 q/s
  it is four times that. **This is the crossover argument again: per query the archive wins, per hour of
  the constraint each route actually binds on it does not.**
- **Two honest cautions.** 34.7% is the head of a list ordered by how many sources saw each name, so it
  will decay as `.com` did from 19.2% to 8.1%. And 308,231 unasked `.org` names times the head rate is
  an **upper bound near 76,000 EE, not a projection**: the realised figure depends on both the decay and
  the pace PIR tolerates, and only the first of those is measured.
- **Ivo's standing rule, adopted: a source closed on availability is a source to re-probe.** He is right
  and it is the documented pattern rather than a new idea, since feedback section 4 asks for previously
  unavailable sources to be revisited and the register's own best case is the Australian Web Archive.
  The screener now classifies every closed lead as closed on MEASUREMENT or AVAILABILITY and says which
  it hit: 42 and 19 of the 61.

**Signed off by Ivo: pending.**

## 2026-08-11 (the availability-closed register re-probed mechanically, and nothing has come back)

- **`scripts/reprobe_closed.py` is the one genuinely autonomous discovery step in the harness**, because
  it needs judgement neither to generate a candidate nor to decide whether an answer is interesting: the
  register already names the hosts and URLs that failed, so the tool extracts them from the verdict prose
  and re-asks them. A dead host that answers 200 is interesting by construction.
- **Result: 19 leads closed on availability, 7 of which name a re-askable URL, 11 URLs asked, and no
  genuine revival.** `webarchive.loc.gov` still 403, `www.faqs.org` still 429, `data.webarchive.org.uk`
  still does not resolve, `web-caching.com` still does not resolve, `api.archivelab.org` still gone. That
  is a reportable negative result under SPEC IX rather than an absence of one.
- **The first version cried wolf, and fixing that is the interesting part.** It flagged `ircache.net` and
  `vefsafn.is` as revivals. Both answer, and **both verdicts already said they would**: the register
  records that `ircache.net` "now serves a squatted blog", and Iceland was closed on a measurement of
  867 projected equivalent-English rather than on reach. So a 200 is only news when the verdict did not
  predict one, and the tool now quotes the sentence from the verdict that mentions the host and separates
  "answers, as the verdict said" from "answers, unexpected". **A re-probe that cries wolf gets switched
  off, which would cost more than the false positives.**
- **One transient worth recording as a caution about single probes.** `Mirror-H.org` failed DNS on the
  first run and resolved on the second, minutes apart. It is out of window by a decade so nothing turns
  on it, but it is the same lesson the register already carries: one negative probe is not a proof.
- **A coverage limit, named rather than hidden.** Only 7 of 19 availability-closed leads name a URL the
  tool can extract; the rest describe a route in prose ("reading-room terminal only", "agreement-gated")
  with no address to ask. Requiring three labels in a host pattern found 4 of them and allowing two found
  7, which is the whole difference between a real re-probe and a token one.

**Signed off by Ivo: pending.**

## 2026-08-11 (the two populations go to two machines, which is Ivo's design)

- **The split.** The VPS works **pure bracketed gaps**, a missing year Y with Y-1 and Y+1 already held,
  as an unattended completeness baseline: 467,619 targets worth 219,760 EE expected. The local engine
  works the **candidate pool**, 2,534,284 targets worth 1,269,380 EE expected, beside the discovery loop
  that keeps feeding it.
- **Ivo is right about the part my earlier note had corrected, and the correction was aimed at the wrong
  pool.** A gap query answers 96.0% to 97.5% of the time and that rate is flat across TLDs, so with the
  probability factor near 1 and uniform, expected value really does collapse to English share times the
  years one query can fill. The candidate pool is the opposite: 36.9% for a name merely mentioned in
  Usenet text against 90.6% for a link harvested off an archived page, so there the share must be
  multiplied by a measured rate or `.au` sorts to the top again. **One of the two populations lets you
  drop a factor and the other does not.**
- **It maps onto the two outcomes the reviewer asked to keep separate, which is the sign it is the right
  cut.** A gap hit adds a pair and never a domain, so the VPS is completeness. A pool hit makes a name
  net-new, so the local engine is the discovery half he asked to be prioritised. The machine allocation
  and the reporting split are now the same distinction.
- **Consequences.** Gap targets change slowly, so the VPS needs a rare refresh rather than a periodic
  one, which was the weakest part of yesterday's rule. And the local CDX engine goes back on, pointed at
  the discovery pool, superseding this morning's decision to leave it off. Implemented as
  `build_query_queue.py --population gap|pool --out PATH`, reusing the existing ranking, era gate and
  measured multipliers rather than a second implementation.
- Running from 09:10Z under `caffeinate` with the ingest loop beside it, deadline 2026-08-12T12:00Z.

**Signed off by Ivo: pending.**

## 2026-08-11 (correction: the slow seed is a classification query, not the inserts)

- **Yesterday's diagnosis was wrong and the fix was aimed at the wrong line.** `ark seed` was recorded
  as slow because `seed_from_file` called `add_candidate` in a Python loop, issuing 29,432 single-row
  inserts into a columnar store. That is true and worth fixing, and it was **not the bottleneck**:
  batched through one `executemany`, the same seed still held the write lock for **33 minutes** before it
  was stopped.
- **The actual cost is `_CLASSIFY_SQL`.** For each of 35,391 candidate names it evaluates a correlated
  `EXISTS` against `evidence`, which is **53.9 million rows**, to decide whether the name carries
  baseline evidence. The comment above that query says it exists to avoid per-row round trips at
  600k-domain seed files, which is the right instinct; what it costs at 54M evidence rows was never
  measured.
- **Why it mattered today rather than in July.** The ingest loop now runs continuously beside two
  collectors, so the store has real contention for the first time. A 33-minute writer is a 33-minute
  outage for every reader: the pricer, `just state` and `audit_residual` all sat behind it, and the two
  new tools only survived it because their lock patience is 15 minutes rather than the 2 they shipped
  with yesterday.
- **Stopped rather than finished, because it is the least valuable thing running.** PANDORA is seed-only
  and measured at an expectation near zero, so it was starving a pricing run and the state generator for
  nothing. Interrupting is safe and idempotent: inserts autocommit, so 7,843 of 29,432 names landed
  yesterday and a re-run adds the rest through `INSERT OR IGNORE`.
- **Left as an open decision rather than hacked now.** Rewriting the classification wants a measurement
  of the alternatives against the real store, and it is a core write path used by every seeding route.
  The batched insert stays: it is correct, it is tested, and it removes a second `to_registrable` call
  per name. It simply was not the thing that was slow.
- **The general lesson, which is the same one this project keeps relearning:** a plausible cause measured
  once at the wrong scale is not a cause. 29,432 inserts sounded like the expensive half because it was
  the visible half.

**Signed off by Ivo: pending.**

## 2026-08-11 (PIR's tolerance measured properly, and the cycle's first real bug was a silent skip)

- **The pace PIR tolerates is now bracketed rather than guessed.** Two workers at a 1 s floor ran 550
  queries with **only 200s and 404s**. Four workers at the same floor produced **140 × 403 in 2,887
  queries, 4.8%**, and the governor's backoff then dragged throughput down to about 1 q/s, which is worse
  than the slower setting in both respects. So the sweep runs at two workers: the register's original
  "blocks rather than throttles" was wrong, and "any pace will do" would have been wrong too.
- **A yield figure that looks like a pace effect and is not.** In-window rate fell from 34.7% and 38.0%
  in the probes to **23.0%** in the first sweep batch. That is decay down a list ordered by how many
  sources saw each name, exactly as `.com` went 19.2% to 8.1%, and the probes consumed the head. Worth
  stating because the obvious reading, that going faster costs yield, is not what happened.
- **The discovery cycle's first run had a real bug and it was the dangerous kind.** Its residual audit
  timed out behind the 33-minute seed and the section simply **vanished from the report**, so the cycle
  looked clean while the check that finds unread files had not run at all. That is the failure `ark check`
  already guards against by printing SKIP rather than PASS, and `documentation.md` states as a principle:
  a check that examined nothing must not read like one that found nothing wrong.
- **Fixed by making every step return whether it ran.** A step that could not complete now prints
  `COULD NOT CHECK` and adds itself to the needs-judgement list, and the per-step ceiling is an hour so a
  long writer no longer causes it. The cycle's value is entirely in being trustworthy when it says
  nothing is wrong, so a silent omission is worse than a crash.
- **Everything else in cycle 1 was correct**: it flagged the VPS as unreachable with the right reasoning,
  listed the eight unfinished hypotheses as needing judgement, and regenerated a stale `ROUND.md`.

**Signed off by Ivo: pending.**

## 2026-08-11 (a new source found by asking what the sources that worked have in common)

- **The method, because it is more reusable than the source.** Instead of listing places to look, I asked
  what this round's three paying sources share. `rdap_snapshot` (registry creation dates), `isc_survey`
  (dated DNS survey shards) and `attrition_defacement` (a dated defacement index) are all
  **machine-generated records about whoever happened to be there**, not human curation of who was
  notable. Every family that has failed on measurement here, five of them now, selects for authority:
  relay hops, institutional directories, award galleries, mailing lists, the Linux Software Map. So the
  generative question is not "where else is there a list" but **"what else recorded everyone, with a
  date, for its own reasons"**.
- **A domain-dispute docket is that shape, and nothing in the register covered it.** WIPO publishes every
  UDRP case with a number whose year is the filing year and the disputed domain in its own table column.
  A case exists only because the domain was registered and in dispute, so it attests existence **without
  depending on a crawler having visited the site**, which is the property that makes 1996-1997 hard.
- **Measured against the live store: 3,325 cases, 6,069 distinct (domain, year) pairs over 6,041 domains,
  of which only 680 are already held.** **88.8% absent is the highest share of anything measured on this
  project**, and it is structural rather than lucky: a disputed name is often a typosquat taken down
  within weeks, exactly the population a crawl never visits.
- **Read as `artifact_listing` it is 5,389 net-new pairs and 3,281.0 equivalent-English at mean weight
  0.6208; read with the corroboration split it is 956 and 593.5.** A 5.5x difference, so the
  classification is recorded as an open decision rather than assumed. The case for self-dating is that
  `attrition_defacement` already sits in that class on identical logic, and that the domain is in a
  structured column rather than in prose, which is the property that made Tucows' `creator` field
  trustworthy. The case against is that self-dating leaves no wall behind the extraction.
- **The typo bound inverts here, and it is worth naming as a general caution.** It reports 36.3% of
  net-new names within one edit of a held name, and for this corpus **that is the signal rather than the
  noise**: a typosquat is one edit from a famous name by construction. A metric built to bound OCR
  damage measures the opposite thing on a corpus of deliberate near-misses.
- **The extraction was narrowed before the figure was believed.** The first pass read every hostname
  between one case number and the next and picked up `www3.wipo.int` from the page furniture. Taking the
  second table cell alone fixed it, and for a self-dating source that narrowing is not optional: my own
  screener says widening extraction is safe on a split source and unsafe on a self-dating one.
- **Cost: 133 requests to a non-IA host**, so no archive budget, and about four minutes. The 6,079 names
  are seeded as candidates regardless of the classification, since a candidate claims nothing.
- **Residual named as a projection, not a measurement.** WIPO is one of several UDRP providers and the
  National Arbitration Forum handled a comparable caseload over the same years, so the family plausibly
  holds two to three times this. That is a **[PROJECTION]** and the only measured part is WIPO.

**Signed off by Ivo: pending.**

## 2026-08-11 (UDRP ingested as master artifact_listing, and the integrity gate caught a real defect)

- **Ingested on Ivo's decision, recorded as ADR-002.** ICANN's consolidated list of domain-dispute
  proceedings across all five providers that heard cases in the window: **7,837 net-new pairs worth
  4,763.1808 equivalent-English at mean weight 0.6078**, from 8,923 evidence rows over 8,892 domains.
  Round moved 133,991 to **141,828 pairs**, 71,823.8124 to **76,586.9932 EE**, 1.1483% to **1.230039%**.
  Verified with his own calculator: zero rejected, zero already in his merged files, agreement to 0.0000.
- **The nine invariants failed on the first ingest, which is the wall doing exactly what it is for.**
  `evidence_year_matches_its_value` reads the **first** four-digit run in an evidence value and compares
  it to the year the row is filed under. The value was written `UDRP <number> commenced <date>`, and that
  fails twice over: a NAF number like `FA0092016` offers `0092`, and a `D2000-` series case that actually
  commenced in January 2001 offers 2000 against an assigned 2001. Eleven rows, and the gate refused the
  whole ingest rather than letting eleven bad values through.
- **Fixed by leading with the date**, `commenced <date> UDRP <number>`, so the first four-digit run is
  the assigned year by construction. Both halves were fixed rather than one: the parser, so a journal
  replay produces the right form, and the 8,923 stored values, reformatted in place, so the store and the
  replay cannot disagree. Reformatting rather than deleting and re-ingesting because it changes no facts
  and touches no assignment, where a delete would have had to reason about pairs whose only master
  evidence was this source. A test now pins the ordering with the exact `D2000-1762 commenced 2001-05-15`
  case that broke it.
- **Worth naming as a general point about the taxonomy.** This is the second time a self-dating source
  has needed its extraction or its value format tightened before it could be trusted, after the
  Microsoft Bookshelf ISO. Master evidence has no wall behind it, and the invariants are that wall's
  replacement: they caught this in seconds where a reviewer reading 8,923 rows would not have.
- **Per-source standing after the ingest:** `rdap_snapshot` 79,057 pairs and 47,479.4688 EE,
  `isc_survey` 42,299 and 14,956.3877, **`udrp_proceedings` 7,837 and 4,763.1808**, `ia_cdx_bulk` 6,819
  and 6,596.5149, `attrition_defacement` 5,816 and 2,791.4410. Per-year growth is now above 0.81% in
  every year, with 2000 at 1.8948% and 1997 at 1.8177%.
- **Lineage `dispute_docket`**, its own family, so a pair UDRP confirms alongside an RDAP creation date
  is genuine cross-lineage corroboration. A test already enforced that every source declares a lineage,
  and it failed until this one was assigned, which is the second guard that earned its place today.

**Signed off by Ivo: pending.**

## 2026-08-11 (the packaging path tested end to end, and it was failing silently)

- **Tested now rather than at submission time**, because packaging is where this project's rounds have
  broken before. Result: it works. **1.4 GB, 928 files, sha256, 6m06s**, and the archive's own checks pass
  all three: 927 files match `SHA256SUMS`, 141,828 pairs in the annual files, and **all 141,828 trace to
  an observation**.
- **But it first exited 1 with no output whatsoever**, which is the worst failure mode a guard can have.
  The guard compares `output/` against the store so a stale export cannot ship, and its own comment says
  the store read is "Retried, and not silenced". **Neither was true.** `set -e` is on, so a bare
  `STORED=$(cmd)` whose command fails aborts the script immediately: the 60-attempt retry loop was dead
  code and the diagnostic below it was unreachable.
- **It went unnoticed for four rounds because nothing else ever held the store.** It surfaced today only
  because the ingest loop now runs continuously beside two collectors, which is new. Fixed with `|| true`
  on the assignment so the retry can retry; it now names the reason it refused, which it demonstrated by
  correctly reporting my own uncommitted edit.
- **The general shape is worth recording**, since it is the third instance today. A retry that cannot
  retry, a residual check that vanished when it timed out, and a lock patience sized against the wrong
  writer: all three were latent, all three were exposed by the store finally having contention, and all
  three failed **quietly**. Continuous operation is not just more throughput, it is a different test
  regime.
- **The interim archive was deleted after verification.** It was built as `phase-5-interim` to avoid
  colliding with the real `phase-5` submission at the weekend, and the tarball is git-ignored anyway.

**Signed off by Ivo: pending.**

## 2026-08-11 (approvals: a source class may not date a year until a human classifies it)

- **Ivo's proposal, and it closes the gap I had named as the harness's boundary.** The agent can propose,
  screen, fetch and price a source unaided; it cannot decide whether that source's records belong in the
  annual files, because that is a judgement about what counts as proof. Until today that happened by
  email, with the reasoning in an ADR only the agent had read, which puts **the least trustworthy artifact
  in the repository on the critical path**.
- **Implemented as a gate rather than a convention.** `docs/open-approvals.md` holds one `Decision:` line
  per (source name, evidence type). `ark ingest` refuses any master-eligible class that is `pending`,
  `rejected` or absent, **before it opens the database**, so an unapproved ingest does not even take the
  write lock. `src/ark/approvals.py` enforces it and `ingest_files` is the choke point every caller passes.
- **One refinement to the proposal, and it is strictly stronger.** The sketch had the harness collecting
  `master_candidates` into a quarantined state. The quarantine is **outside** the store instead:
  collectors already write journals and never open the database, so "collected but unclassified" needs no
  new state at all. **An unapproved source cannot contaminate anything, having never been written**, which
  beats any flag that every future query has to respect. It is also less code and no schema change.
- **What makes a request decidable without trusting the agent**, which is the whole point. Each request
  carries a **seeded-random** sample of real records with a **live link each**, the seed printed so it is
  reproducible and demonstrably not agent-chosen; the measured figures by program; the **counterfactual**,
  what the source is worth under each possible decision, so the stake is visible before deciding; the
  nearest already-closed family from the register; and reasons to refuse written by the agent against its
  own request. The one judgement it contributes is the dating claim, labelled as a claim.
- **The links had to be per-record or the mechanism was theatre.** The first version pointed every sample
  row at the index page, which proves nothing. WIPO publishes each decision at a composable address, so
  5,945 of the 8,923 rows now cite the exact page a reviewer can open and see the domain on; NAF's ids are
  opaque and its index is client-side, so those rows honestly cite the table instead. **The path year
  comes from the case number, not the commencement date**: `D2000-1762` is published under `/2000/`
  although it commenced in 2001.
- **Consistency kept in both directions.** Improving the journal's URLs made the store disagree with it,
  so 8,923 stored `evidence_url` values were updated to match and the ledger's sha256 was set to the
  regenerated journal. Store and replay agree, which is the same discipline the value-order fix needed.
- **The gate immediately broke fourteen tests, which is the gate working.** Unit tests build specs with
  invented source names, so they were all refused. `tests/conftest.py` now relaxes the gate for unit tests
  and `tests/test_approvals.py` is the only place it is genuinely exercised, testing the gate rather than
  the convention: nine cases including that an unparseable decision word **fails closed**, and that
  approving a source `candidate-only` does not let a master spec through.
- **A test asserts every master-eligible spec has an entry**, so adding a source without classifying it
  fails in the suite rather than at three in the morning in an unattended run.
- **The awkward part, named rather than buried:** 24 of the 25 existing classes were grandfathered in one
  sitting. The authority is cited per entry, the reviewer merging and crediting the round or Ivo deciding
  by name and date, so it is not the agent approving its own past work. It is still a retrospective batch.
- **Collection never waits on a human and promotion always does.** Candidate-only evidence is deliberately
  ungated: it can never date a year, the reviewer asked for the pool to be as large as practicable, and
  gating it would stall collection to protect nothing. Full reasoning in ADR-003.

**Signed off by Ivo: pending.**

## 2026-08-11 (the idleness was real, and one collector had been dead for four days)

Ivo, watching the harness work: "You seem pretty idle to me. Don't just start doing something, let's
talk about a technical fix." He was right, and the diagnosis found three separate causes plus one
failure nobody had noticed.

- **Cause one: the loop could see problems it could not fix.** `discover_cycle` reported a stale derived
  list and then moved on, so the same finding reappeared every hour and nothing acted on it. It now owns
  `rebuild_derived()` and regenerates a list the store has outgrown, with `REBUILD_AFTER_HOURS = 1.5` so
  it does not thrash.
- **Cause two: the staleness check was comparing against the wrong thing.** It asked whether a target
  list predated the current **baseline**, which is a question about releases and changes about once a
  month. What actually invalidates a list is the store moving underneath it, and the two lists are
  invalidated by different marks: a gap queue goes stale when new **pairs** land, a pool queue when new
  **candidates** land. `DERIVED` gained an `against` column and `freshness_marks()` returns all three
  epochs. On the first run the new check reported **three stale lists the old one called fine**:
  `queue_gap_vps.txt` 4.2 h behind the newest pairs, `queue_pool_local.txt` 1.9 h behind the newest
  candidates, `pool_targets_org.txt` 1.7 h behind. That is the bug Ivo saw from the outside.
- **Cause three: the wake schedule was wrong.** The cron fired four times a night. It now fires every
  15 minutes, on Ivo's instruction, with a `CLAUDE.md` section governing what a cron-started session
  does.

**The finding that matters more than any of the three.** A bracket-safe process check showed the local
CDX pool engine had not run since **7 August 13:15**. It was stopped deliberately that day under the
rule "do not restart the local engine", C-10 re-authorised it four days later, and nothing ever started
it again, because no check asked. Restarted on the rebuilt pool queue at 15:59 with 4 workers and a 1.0 s
floor, the VPS being unreachable so nothing else is on `web.archive.org` right now. **A status line that
reads healthy while a collector is absent is worse than no status line**, so the cron section makes the
first question "is anything stopped" rather than "is anything failing".

**The cron section, and the one sentence it exists for.** `## If you were started by a cron job` in
`CLAUDE.md`: continue if mid-task; otherwise `just cycle`, act on what needs judgement, bring the
documentation into one story, then one piece of real work sized to fit. The definition that carries it is
**"the collectors are running" is not you being busy**, which is precisely the confusion that let an
engine stay dead for four days while every report looked fine. "Everything is fine" is recorded as a
valid outcome, so a wake has no incentive to invent work. `just cycle` is the new one-shot entry point,
in the justfile and the README table.

**Two of my own claims corrected, both found by checking rather than by argument.**

- I said re-pointing the engine would recover 4,333 stranded UDRP candidates. **False**: of the 6,079
  UDRP names, 5,953 already carry a year because the ingest dated them, 114 sit in the pool and 12 are
  unknown to the store. The rebuild was still right, for the staleness reason above, but the reason I
  gave for it was wrong.
- `pkill -f 'supervise_cdx_pool.sh'` **killed my own watcher**, because the pattern sits in the watcher's
  command line, and the `pgrep` that followed matched the same self-reference and reported the supervisor
  still running when it had stopped. Second occurrence today. Now a trap entry in `CLAUDE.md`: bracket one
  letter, `pgrep -f 'supervise_cdx_poo[l]'`, which cannot match itself.

**Also fixed, from Ivo's correction on the UDRP block.** "The UDRP decision is not a pending request at
all, it is a made decision, which would also fix the problem with the measured 0s." Moved out of
`## Pending requests` into `## Decided, with the request that was reviewed`, carrying the figures as they
stood **at the decision** (7,714 net-new pairs, 4,708.9 equivalent-English) and stating why the request
block now reads zero: every pair it names is held, because it was ingested. `request_approval.py` now
refuses outright to write a request for a source the store already holds evidence for, since such a
request states zero at stake for a decision that had plenty, which is misleading rather than unhelpful.

**Signed off by Ivo: pending.**

## 2026-08-11 (correction: the local engine was never dead, and I killed it)

The entry above says the local CDX pool engine had not run since 7 August. **That is false, and I am the
reason it briefly became true.** The correction matters more than the original finding, because the
original finding was the justification for an action that destroyed work in progress.

**What actually happened.** `supervise_cdx_pool.sh` writes `data/logs/${ARK_PREFIX}.log`. The script's own
header documents exactly two prefixes, `cdx_pool` for the candidate pool and `cdx_gap` for the gap pool.
The run working the pool this morning had been started under a third, invented prefix, `cdx_disc`, at
11:10, `batch=600 workers=8`, already reading `data/raw/cdx/queue_pool_local.txt`. It had completed five
batches and was 19 minutes into a sixth, finding a steady 384 to 392 in-window years per 600 domains
queried. **Its log was perfectly current. I read the other one**, found `cdx_pool.log` last written on
7 August, and reported a dead engine.

Then `pkill -TERM -f 'supervise_cdx_pool.sh'` matched it, because the prefix lives in an environment
variable and not in the command line, so the name I was searching for was present in a process I believed
did not exist. It logged `supervisor asked to stop` at 15:55:22 and dropped its sixth batch. The journal
survived, 4,447 bytes against the usual 11,300, so the loss is roughly two thirds of one batch.

**Three claims of mine to strike.**

1. "The local engine has been down since 7 August." False. It ran from 11:10 to 15:55 today.
2. "Re-pointing it at the rebuilt queue recovers work." It was already reading
   `queue_pool_local.txt`, and a supervisor re-reads its target list at every dispatch, so the rebuild
   was picked up automatically. **The re-point was a no-op wrapped around a kill.**
3. "This is the largest single piece of the idleness Ivo saw." No. The staleness check comparing against
   the baseline instead of the store marks was the real bug, and it stands: three lists were stale and
   the old check called them fine.

**What this is really an instance of.** Presence is not progress, which this script's own header argues at
length, has a converse the header does not state: **absence in a log is not absence of a process.** A log
file answers "what did this name do", never "is anything running". The process table answers the second
question and nothing else does. `CLAUDE.md` now carries that as a rule in the cron section, together with
the constraint that made it possible: an undocumented prefix hides a running collector from anyone
following the documentation, so the two documented prefixes are the only ones allowed.

**Restarted correctly.** Same population, the documented `cdx_pool` prefix, `batch=600 workers=8` and the
`0.5/0.15/3.0` pacing that was measured working this morning, rather than the gentler improvisation I
started at 15:59 which was running about 23% slower for no measured reason.

**Signed off by Ivo: pending.**

## 2026-08-11 (the declarative fetcher, narrowed to a probe, and validated against a known answer)

Ivo's second fix for the idleness: make the fetcher declarative, so a source can be tried by describing it
rather than by writing a program. Adopted for **measuring** a source and refused for **ingesting** one.
Full reasoning in ADR-004; the short version is that the bottleneck was mis-identified, including by me.

**What the measurement said about the bottleneck.** Adding UDRP cost 186 lines of collector, 71 of parser
and spec, and eight tests. But the Linux Software Map and the Microsoft Bookshelf ISO were each found,
fetched, priced and **closed inside an hour**, on two or three requests, and neither ever needed a parser.
So of the last four sources considered, two were settled before any code existed. The expensive step is
finding out whether a source is worth 186 lines, not writing them.

**What was built.** `scripts/probe_source.py`, driven by a TOML file: a URL, one of three shapes
(`html_table`, `lines`, `jsonl`), which column or field carries the hostname, which carries the date. It
writes the `{item, year, text}` journal `price_items.py` already reads, so a URL becomes a measured net-new
figure with no Python written. `tomllib` is stdlib and the table extraction is the same regex pair the UDRP
collector already proved, so this adds no dependency. `just probe`, and the README table says what it is.

**Validated against a known answer, which is the only validation worth having here.** The first spec
written was not a new source but a self-test against one already ingested by hand: seven lines pointed at
the ICANN dockets. The bespoke collector produced 8,923 pairs. The probe produced **8,923 pairs over 8,892
domains, agreeing on all 8,923, with nothing in either set the other missed.** A declarative extractor that
merely looks like it works is the obvious trap, so it was pointed at the case where a wrong answer would be
visible.

**One real shape found while doing it.** The dockets list every disputed name of a case in one cell. A cell
taken whole refuses those rows, and the yield then reads low for a reason that has nothing to do with the
source, which is exactly the lie a pricing tool must not tell. So `domain_pattern` mines within a cell, and
every drop is counted under a named reason with a warning printed when less than half the rows survive.

**What was deliberately refused.**

- **A declarative path to master evidence.** A parser's value is in its refusals and refusals do not
  generalise: UDRP refuses a row with no proceeding number, refuses a value whose date does not name the
  year it is filed under, and had to be taught to read one cell instead of the text between two case
  numbers. A configuration language able to state those is a programming language with worse tooling.
- **Column sniffing.** It is the feature that makes a demonstration impressive and a corpus unreliable. The
  spec names the column or the tool refuses to run.
- Both refusals rest on the same point as ADR-003: making it cheap to **add** a source is safe, making it
  cheap to **promote** one is not, and a declarative ingest would have done both at once.

**The boundary moved by exactly one step**, from "cannot try a source" to "cannot promote one", and the
README's honest statement of the split was corrected to say so rather than still claiming a fetcher always
needs a person.

**Signed off by Ivo: pending.**

## 2026-08-11 (the largest unread pile on disk was not one, and the screener had sent me there)

The residual audit had been reporting **982 MB under `data/raw/source_probe_260806` as "downloaded bytes
with no parser and no ingest line"** since 6 August, which is the check whose one previous hit was worth
14,956 equivalent-English. Traced all four parts. None of it is opportunity.

- `enron.tar.gz`, 423 MB, is the **only** copy of the corpus and is the path
  `scripts/collect_enron.py` names directly. `sources.md` documents a download to
  `data/raw/enron/enron_mail.tar.gz`, which does not exist, so the reproduce line is wrong in a way that
  would cost a future session a 423 MB re-download.
- `mlists` 500 MB and `attrition` 2.7 MB fed sources already ingested: 21,882 and 5,816 evidence rows.
- `hathitrust_ef` 12 MB is the HathiTrust Extracted Features route, and it was **already closed on a
  measurement on 8 August**, inside the printed-directory verdict.

**The part worth keeping is why I re-measured it anyway.** `just screen` collided the proposal with that
verdict, classified it `closed on: AVAILABILITY`, and printed "RE-PROBE THESE". That classification is
correct as far as it goes, the archive.org text files really do return 401 and 403, and the bias toward
availability is deliberate and right. But **that one entry closes two different routes**: archive.org on
reach, and HathiTrust on yield, and `closed_on` returns a single value, so the measurement was invisible.
The tool told me to do something the register had already done.

Fixed rather than noted: `Closed.also_measured` tests the verdict for phrases that only appear when
someone counted, and the screener prints `AVAILABILITY, AND IT ALSO CARRIES A MEASUREMENT` with the
instruction to re-probe only the part that could not be reached. Two tests, one on a synthetic entry and
one against the **live** register, so a rewrite of that verdict that drops its numbers fails in the suite
instead of quietly sending the next session down the same path.

**The re-measurement itself, since it exists and confirms the verdict.** 69 in-window volumes, 2,551
hostname-shaped tokens, 1,425 distinct in-window pairs, 1,124 of 1,284 matched pairs already held,
**74 net-new pairs and 49.4 equivalent-English after the corroboration split** against a ~5,000-pair bar.
Recorded beside the original verdict. One detail is worth having: EF tokenisation **does** preserve
hostnames, `www.adobe.com` and `bubl.bath.ac.uk` survive as single tokens, so the family did not fail on
extraction. It fails on population, like the five before it. The 64.4% typo bound is the opposite of the
UDRP case: there a high edit-distance score measured signal, here it measures OCR damage, and
`onftp.lib.berkeley.edu` in the sample shows the line-wrap mechanism doing it.

**And the audit now says so.** `source_probe_260806`, `probes` and `udrp` are named in `ACCOUNTED` with
what consumes each, so `unreferenced` reports material that is genuinely unaccounted for. A check that
cries 982 MB every cycle is a check that gets ignored, which is worse than not having it.

**Signed off by Ivo: pending.**

## 2026-08-11 (the first cron wake found the cycle crashing, and the cycle killing collectors)

The 15-minute wake did on its first run exactly what it was added for: it ran `just cycle` and the cycle
**crashed**, on code I had written three hours earlier.

**Why nobody had seen it.** `rebuild_derived` parses the audit's staleness line and read the hours field
`0.9h` with a bare `float(p)`, which raises. It had never fired: the hourly loop was started at 12:10 and
Python had loaded that module before the function existed, so the loop kept running the older code, kept
printing the older wording, and kept looking healthy. **A long-running loop is a frozen copy of the code**,
and that is now the second time today a healthy-looking log hid the real state. Only a fresh invocation
touched the new path, and the wake was the first fresh invocation.

**The more serious find in the same function.** `repoint_pool_engine` restarted the local collector after a
rebuild, and it was the mechanism of this afternoon's incident encoded to run unattended, hourly, forever:
it shelled `pgrep -f supervise_cdx_pool.sh` and `pkill -TERM -f supervise_cdx_pool.sh` from a subprocess
whose own command line contains that pattern, so the presence check could never be false and the kill could
match its caller; it hardcoded `ARK_PREFIX=cdx_disc`, which is **where the invented third prefix came
from**; and it hardcoded a deadline epoch that silently becomes the past.

**Deleted rather than guarded, because it was never necessary.** A supervisor re-reads its target list at
every dispatch, so rewriting the file is the whole job. The rule is now stated where it belongs, in the
module docstring and in a test: **an unattended loop does not get to kill collectors.** The test asserts
the function is absent and that no `"pkill"` argument appears in the source, matching the quoted form so
that the docstring may still explain why the rule exists. A test that forbids describing a mistake deletes
the reason for the rule.

**Two more fixes, both about a report staying worth reading.**

- The `stale_derived` ATTENTION line was raised on any staleness at all. Candidates arrive continuously, so
  a pool queue is minutes stale almost always, and the alarm would have fired every cycle forever while
  `rebuild_derived` deliberately declined to act below its 1.5h threshold. Removed: the rebuild owns the
  condition and asks for a human only when it cannot act, which is the VPS list or a failed rebuild. **An
  alarm nobody can clear is the same defect as the 982 MB** the unreferenced check used to report.
- A rebuild lock, because an hourly loop and a 15-minute wake can now both rebuild the same list into the
  same path, and two writers to one target file give a truncated queue that a collector reads as a short
  list rather than as an error. The lock is taken only when something will actually be rebuilt, it records
  the pid, and it is ignored if the holder is gone or the lock is over an hour old, so a crashed cycle
  cannot become the outage the lock was meant to prevent. Five tests.

**State after the wake.** The cycle completes, and its judgement list is down to two items, both real: the
VPS is unreachable until the VPN is up, and five screened hypotheses need a decision. The hourly loop was
restarted so it is no longer running a frozen copy from 12:10. All four collectors up.

**Signed off by Ivo: pending.**

## 2026-08-11 (one surface asks Ivo for things, and it is enforced)

Ivo, reading the last report: "You don't need my sign-off for notes... I had no idea there are
hypothesis for me to sign-off. Everything I have to sign-off should be in one place, so I know about it.
That was key-decisions, it pointed to ADRs if necessary." Plus: rename `open-approvals.md`, and anything
open and waiting on him must also appear in key-decisions.

**Why the third item is the one that matters.** The failure was not unanswered questions. It was that the
harness believed it had asked them. Unfinished hypotheses were surfaced by `discover_cycle` as "needs
judgement, not a program", 37 notes entries each asked for a countersignature, and `pending` approval
classes sat in a file he had no reason to open. **A question raised where nobody reads it has done the
reporting and none of the communicating**, and the harness then reports the silence as "the queue
working", which looks handled from the inside. Reasoning in ADR-005, C-16 in key-decisions.

**What changed.**

- `docs/open-approvals.md` -> `docs/approved-sources-list.md`, his wording. Twelve files referenced it;
  the eleven live ones were updated and `notes.md` was left alone, because a past entry is history and
  referred to the file as it was then named.
- `src/ark/key_decisions.py` owns the `## OPEN` block: `open_titles`, `is_open`, `raise_open`. Idempotent,
  removes the "nothing needs your input" placeholder when something does, newest first, and it raises
  `ValueError` rather than silently doing nothing if the section is missing.
- A `pending` class is mirrored **twice**, deliberately, because the failure being prevented is silent by
  nature: `request_approval.py` raises the entry when it writes the request, and `check_approvals` raises
  it on any cycle that finds one unsurfaced. The reverse direction is checked too: an OPEN entry naming a
  class that is no longer pending is reported, since a surface that lies about what is waiting loses the
  trust that makes it work.
- **The mirror writes a stub, not an argument.** What is waiting, what is at stake under each decision,
  and where the checkable evidence is. Generating the reasoning would produce the confident filler the
  approvals design exists to distrust.
- `build_round_state.py` had its own copy of the OPEN-block parser; it now calls the module, so the two
  cannot come to disagree about what counts as open.
- Notes entries no longer ask for a sign-off, and `CLAUDE.md` no longer requires the trailer. The 37
  existing ones keep it: the log is append-only and tidying history is a different failure.
- `check_ledger` reports unfinished hypotheses as **findings**, never attention, with the wording "yours
  to settle without asking".

**Enforced rather than agreed, which is the part worth keeping.** CLAUDE.md already said to raise things
where a human would see them, and that did not prevent any of this, because a convention cannot notice it
has been broken. A test over the two **live** documents fails if a pending class is not named in
key-decisions, and three more test the wiring in the cycle rather than the convention. 382 tests pass.

**The latitude this grants, and what makes it safe.** The agent now settles hypotheses alone, which is
more than it had this morning. It is safe only because the approvals gate is downstream: a lead can be
adopted, collected and priced on the agent's judgement and **its records still cannot date a year until a
human classifies the source**. If anything ever lets a hypothesis reach the annual files without passing
that gate, ADR-005 stops being safe and needs revisiting rather than reapplying. Noted there as the
consequence to watch.

## 2026-08-11 (`ark check` and `ark stats` wait for the writer instead of raising a traceback)

Found by running the gate after the rename: `uv run ark check` died with a DuckDB `Conflicting lock`
traceback because `scripts/maintain.sh` was mid-ingest. Both commands record a metrics row, so unlike the
read-only tools they genuinely need the write lock, and neither had any patience.

**Why this is worse than an inconvenience.** The ingest loop takes the lock every fifteen minutes and a
long ingest holds it for tens of minutes, so an unattended run hits this routinely, and **a lock traceback
out of the integrity gate reads as a broken invariant when the database is merely busy.** That is the exact
confusion `ark check` was built to avoid on the other axis, where it reports SKIP rather than PASS for a
check it could not run. A cron wake every fifteen minutes would have produced this regularly.

`db.connect_patiently` waits up to 900s for the lock and re-raises anything that is not contention; `stats`
and `check` use it, every other caller is untouched. Waiting is also the correct priority rather than
merely the polite one: ADR-001 says banking a collector's finished journal outranks measuring, so the
reporting side is the side that yields.

After waiting out the ingest, all nine invariants pass, which is what the rename needed to confirm.

## 2026-08-11 (five hypotheses settled, four rejected on measurement, and the fifth is now the only thing waiting on Ivo)

Ivo's instruction the same afternoon: "Hypothesis should be tested and confirmed by yourself until a
relevant key decision that I would have to sign off can be formulated. Otherwise, you make your own
judgment on them and continue." So all five screened leads were measured, each verdict then checked by a
separate agent whose only job was to refute it. Ten agents, 844,541 subagent tokens, 374 tool calls.

**Four rejected on measurement, all confirmed by their skeptic**, and every one of them is the same failure
the register already records five times: the population is notable or institutional domains, which is what
a CDX-derived baseline holds first.

| lead | net-new pairs after the split | EE | against the ~5,000 bar |
|---|--:|--:|---|
| H003 RFCs and Internet-Drafts | 140 | 88.2 | whole-source estimate ~770 pairs, 6x short |
| H004 W3C technical reports | 56 | 36.1 | a census, so that is the ceiling, 87x short |
| H005 Debian changelogs | 21 | 14.4 | ~2 EE for the whole potato release |
| H007 INET proceedings | 19 | 12.7 | estimate 116 EE for ~750 papers, 40x short |

**Three findings that outlive their verdicts.**

1. **The corroboration split does not protect against a hostname that was never real.** It asks whether
   the domain is dated in some annual file, never whether the mention was genuine, so an invented name
   later really registered passes. The RFC corpus is full of them by editorial habit: `acmecorp.com`,
   `bigco.com`, `widgetco.com`, `john-doe.com`. RFC 2606 reserved `example.com` in June 1999 precisely
   because authors kept inventing plausible ones. Now in `CLAUDE.md` beside the split itself, because it
   qualifies a guarantee the whole design leans on.
2. **The Debian hypothesis named a mechanism that did not exist in window.** A `Homepage:` field appears in
   0 of all 36 in-window index files; it entered Debian policy around 2007. Any future proposal resting on
   it can be killed without a fetch.
3. **W3C retrofits post-window status banners into archived recommendations**, so the page served today is
   not the artifact that was published, and the first extraction dated `github.com` to 1999 from a 2021
   banner on a 1999 recommendation.

**H008 Netcraft is the one that matters, and its skeptic overturned it.** The measuring agent filed it
`reject-on-measurement`. The skeptic confirmed every number and rejected the disposition, on the grounds
that the arithmetic was correct under a **classification nobody had tested**, and that classifying a source
class is explicitly not the agent's call. It was right, and the mistake was **mine**: the workflow prompt
asserted batch-wide that "every one of these leads is dating class typed". An archived Netcraft
`/domains/cache/` page is a machine dump from a survey database with no author, no prose and no per-item
date, dated only by its Wayback capture timestamp, which is the self-dating shape `isc_survey` already
holds as `artifact_listing` with 1,719,409 records.

Both agents were also partly wrong, and the fix was cheap: the reject rested on a **2-page projection**
where the two pages differ 4x in yield. 18 further polite requests settled it. Measured over 19 of the 20
in-window captures, 11,309 distinct pairs over 11,299 domains, 2,568 already held, **77.3% absent**, mean
weight 0.6616:

- as self-dating `artifact_listing`: **8,741 net-new pairs, 5,708.4 EE**, which clears the bar;
- taking the corroboration split: **2,204 pairs, 1,458.2 EE**, which fails it 2.3x short.

So the answer is a measurement and the decision is a judgement, which is exactly the boundary ADR-003
draws. Raised as a `pending` request in `approved-sources-list.md` with a seeded sample of the net-new rows
and a live Wayback link each, and as the single `## OPEN` entry in `key-decisions.md`. **Independent of the
decision, 6,314 names are new to the candidate pool and need no approval**, since the CDX and RDAP engines
can date them on their own evidence.

**A bug in today's own mechanism, found by using it.** The first mirror wrote its entry into the middle of
`key-decisions.md`'s header, because `_split` matched the literal `## OPEN` as a substring and the header
explains the rule in prose with the words "an `## OPEN` entry". It cut that sentence in half. The markers
are now line-anchored headings, the file is repaired, and a test builds a document that mentions the marker
in prose. **Matching a structural marker as a substring is the same defect as a glob that matches too much:
it works until the prose mentions itself.**

## 2026-08-11 (the discovery engine was querying a queue with a measured zero hit rate, and I built it)

A cron wake found all four collectors up and every mechanical check clean, so this would have been an
"everything is fine" wake. It was not, and the thing that gave it away is in the collector's own log rather
than in any check: since the 16:33 restart the local pool engine had run two batches, **600 queried each,
`no_capture: 600` both times.** No `years_found` key at all, no `failed_403` or `failed_0`, and throttles
pinned at the 3000ms ceiling. The healthy 11:10 run on the pre-rebuild queue had `years_found: 392` per 600.

**The queue I rebuilt at 15:53 is the cause.** Its head:

    decwrl.arpa / 212.in-addr.arpa / fdgvhe.nr / 128.in-addr.arpa / jaring.mh / asencrn.mh ...

and **2,675 of its first 3,000 rows are `.mil`**. Across the whole 2.54M-row queue, 371,465 `.gov` and
`.mil` names stood in front of the first real domain: at the measured rate, about **25 days of the
prioritised discovery half producing nothing**. So the two batches at zero were not bad luck, they were the
queue working as ranked.

**The cause is a factor that was missing, and this project has already named it once.** The pool score is
`P(hit) x English share x years per hit`, and `P(hit)` comes from `cell_rate.get((source, tld), ...)` with
fallbacks to a source rate and then a pool-wide rate. For a TLD nothing has ever measured, the fallback
hands it an optimistic rate and English share does the rest. `build_rdap_pool_list.py` documents exactly
this and calls it "the `.au` mistake in a new place": ordering by expected equivalent-English does it
"whenever the probability half of the estimate is a guess, and 0.9825 times a fabricated name is still
zero". C-2 acted on it for RDAP by excluding `.gov` and `.mil` by hand. **The CDX queue never got that
judgement**, and its own comment beside `ATTESTED_MIN` says the attestation tiebreak is "kept as a tiebreak
only: measured hit rate now does this job directly and better", which was true except where nothing had
been measured.

**Fixed with the measurement instead of a list.** A hand-maintained exclusion would have covered those two
TLDs and rotted. `pool_plausibility` computes `dated / (dated + pool)` per TLD from data already in memory,
so it costs no extra query, and the same discriminator the RDAP builder reports now multiplies the pool
score. Measured against the live store today:

| tld | dated | pool | pool/dated | plausibility |
|---|--:|--:|--:|--:|
| com | 3,239,150 | 913,012 | 0.3 | 0.78 |
| uk | 207,964 | 65,268 | 0.3 | 0.76 |
| org | 288,254 | 306,606 | 1.1 | 0.48 |
| net | 297,312 | 412,664 | 1.4 | 0.42 |
| edu | 6,438 | 216,185 | 33.6 | 0.029 |
| gov | 1,021 | 185,803 | 182.0 | 0.0055 |
| mil | 71 | 186,278 | 2,623.6 | 0.00038 |

The `.mil` and `.gov` ratios reproduce the RDAP builder's recorded 2,624 and 182 exactly, which is a useful
cross-check that both are measuring the same thing. `.mil` drops about 2,000x and `.com` is barely touched,
**with no TLD named anywhere in the code**. The tiny ccTLDs that also littered the head land in between
(`.nr` 0.18, `.mh` 0.08), which is the right answer: unproven is not impossible, and the only way a
namespace earns its first dated domain is by being queried.

Reverse-DNS zones are excluded outright rather than down-weighted. `212.in-addr.arpa` is not a website and
never was, so a capture query against one is wasted by construction; 57 were in the queue and 41 in its
first 3,000, because `arpa` is an in-window gTLD with a high English share. That is a fact about the
namespace rather than a judgement about the corpus, which is why it is enforced where the ranking factor is
not.

**After the rebuild** the head is `.za`, `.nz` and `.uk`, and the first 50,000 targets hold zero `.gov`,
`.mil` or reverse-DNS names. Four tests pin the separation using the live ratios rather than an arbitrary
threshold, and the factor is printed with every build, because a ranking factor nobody can see is one
nobody checks. Nothing was restarted: a supervisor re-reads its target list at every dispatch.

**What this says about the checks.** `just cycle` reported everything clean while the engine was at a zero
hit rate, because no check reads collector *yield*. Presence is checked, progress is checked by journal
growth, and a journal full of `no_capture` rows grows normally. That is a real gap and it is the obvious
next piece of harness work.

## 2026-08-11 (progress is not yield: the check that would have caught this afternoon by itself)

Logged at the end of the previous wake as the obvious next piece of harness work, and built in this one.
`supervise_cdx_pool.sh` argues at length that **presence is not progress**: a batch stuck on a socket leaves
the process alive and the journal frozen, so it watches journal growth rather than the PID. That closed the
gap it was aimed at and left a wider one, because **a journal full of misses grows exactly as fast as a
journal full of hits.** Every record is written either way.

That gap is what let this afternoon happen. 1,200 archive queries returned zero in-window captures while
the process was alive, the journal was growing, and `just cycle` reported every mechanical check clean. The
only place the truth appeared was a `no_capture: 600` counter in a log line nothing reads, and I found it by
eye.

`src/ark/yield_check.py` asks the question none of the other checks did: **of the domains the archive
actually answered, what share held a capture?** Wired into the cycle as its own step. Pointed at the live
journals the first time it ran, it reported:

    cdx_pool: 6.8% of 1,008 answered held a capture, against 51.6% of 22,928 before that  -> COLLAPSED
    cdx_gap:  99.6% of 669 answered held a capture, against 98.5% of 45,803 before that
    cdx_disc: 45.8% of 1,418 answered held a capture, against 43.7% of 1,774 before that

**Three decisions worth recording, because each one is a way this check could have been useless.**

- **Judged against the collector's own history, not a constant.** The gap pool answers 96-97.5% and the
  candidate pool 36.9-90.6% depending on where a name came from, so one hardcoded floor either misses a pool
  collapse or condemns a healthy pool every cycle. And the real reading was **6.8%, not a clean zero**,
  because the recent window straddled the rebuild: an absolute floor low enough to be safe for the candidate
  pool would have let it through. The fraction test caught it, which is the case the design exists for.
- **Zero is caught separately, with no history needed.** A population that answers and never holds a capture
  is not worth querying whatever it did last week.
- **Only status 200 counts in the denominator**, the same rule `journal_outcomes` already uses. Counting a
  transport failure as a miss would report a refusing archive as a dead population, which is the opposite
  diagnosis and the opposite action.

Also: the two populations are measured separately, since folding them together would hide a pool collapse
behind the gap pool's 96%; in-flight `.part` files are skipped, because a batch two records in is not
evidence; and a collector with no journals at all is not a failure, so a fresh checkout does not look broken.
Nine tests, 396 passing.

**It is currently lit, correctly.** The reading is now 0.1% of 1,477, because the batch that finished after
the rebuild was still working the old list, and the alarm will stay up until the re-ranked queue's batches
land. That is the honest behaviour and suppressing it would defeat the point.

**The rule now sits where a reader would look for it**, which is the part that makes it stick: the
supervisor's own header carries the converse of its "presence is not progress" argument and points at the
yield check, saying plainly that this is a thing the script cannot see. `CLAUDE.md` and the README say it
too.

## 2026-08-11 (the write-lock cause found by measurement, and I inverted the priority before fixing it)

The wake's intended work was to bank the 13,078 Netcraft names into the candidate pool. That needs no
approval, since candidate-only evidence never waits on a human, and it would also produce the seed phase
timings ADR-001 has been Open waiting for. It did not get done, and what happened instead is worth more.

**`ark seed` died on the write lock with a DuckDB traceback**, because the ingest loop was banking. That is
the same defect class fixed for `check` and `stats` this afternoon, so I gave `seed` 600s of patience.

**That inverted ADR-001's priority, and I caught it by watching the consequence.** Four minutes later the
seed held the lock and **`ark ingest` was the thing crashing against it**. Patience did not make the seed
polite, it made it *queue*: it won the lock the moment the ingest pass finished and then held it for its own
long run. **Moving a traceback onto the job that outranks you is not an improvement.** The seed was
interrupted under ADR-001's own rule, which is safe because inserts autocommit and the insert ignores
duplicates, and its log was empty so it had not reached the insert phase.

**Corrected, and the rule is now in the code rather than in prose.** ADR-001 decision 4 says priority
follows expected net-new equivalent-English, banking first and seeding last. **Nothing implemented that.**
Neither command had any patience, so whichever process reached the store first won and the other died; the
stated ordering had no effect on which. It is now expressed as asymmetric patience, the smallest mechanism
that encodes an ordering: `ark ingest` waits 2400s because a pass that gives up leaves collected work on
disk, and `ark seed` waits 20s and then yields with a message saying it yielded and that a re-run is
additive. Verified: the seed now prints that message and the ingest keeps the lock.

**And then the actual cause, which supersedes ADR-001's "cause is unidentified".** Sampling the lock 18
times over 90 seconds: **held 16, free 2, so 89% occupancy.** `maintain.sh` runs one `uv run ark ingest`
**per journal file** across 400-plus files every 900 seconds, and each invocation opens the store
read-write, reads the ledger, finds the file already banked and closes. The log carries **7,646
`already ingested, skipping` lines across 6,156 invocations.** So the contention that has blocked the
pricer, the state generator and the residual auditor all day is not a slow seed. It is the banking loop
holding a write lock near-continuously **to do almost nothing.**

The fix is one invocation per source instead of one per file: `ingest_cmd` already takes a list of paths and
`ingest_files` already skips per file from the ledger, so 400-plus acquisitions per pass become one.
**Deliberately not done in this wake.** ADR-001's own first decision is not to restructure a write path
every seeding route depends on without knowing which line is slow, and one unknown remains: what
`ingest_files` does when a single file in a batch fails. Per-file invocation contains a bad file to itself
and a batch might not. That is cheap to check and belongs before the change, not after. Recorded as an
addendum to ADR-001 with the measurement, so the next session starts from a number.

**Still outstanding from this wake:** the 13,078 Netcraft names are prepared at
`data/raw/probes/H008-pool-names.txt` and not yet seeded, because seeding correctly yields to a loop that
currently holds the lock 89% of the time. Fixing the loop is what unblocks it.

## 2026-08-11 (the write lock: 89% occupancy to 0%, and the queue fix is only half a fix)

The previous wake identified the cause and deliberately stopped short of the change, naming one unknown:
what `ingest_files` does when a single file in a batch fails. **Settled by reading it.** Each file is
already wrapped in its own `try/except Exception` which counts `files_failed`, logs it and continues, so a
bad file is contained exactly as it was under per-file invocation, and now shows up in the summary instead
of scrolling past in a shell loop. Batching was therefore never the risk it looked like.

**The measurement, on both sides of the change.**

    409 CDX journals, one invocation : 2 seconds, one lock acquisition, 408 skipped, 1 banked
    occupancy before                 : held 16 of 18 samples over 90s, 89%
    occupancy after                  : held  0 of 18 samples over 90s,  0%

`maintain.sh` now calls `ark ingest` once per **source** rather than once per **file**. At current file
counts the four per-file loops were spawning **636 invocations per pass**, each a Python interpreter start
that took the write lock to read one ledger row, **every 150 seconds** (the loop runs `900 150`, so the
pause is 150s and not the 900 I first read). That is the entirety of ADR-001's contention. It also
collapses 636 `record_metrics` rows and 636 `_enqueue_unverified` passes into one each.

**Editing a running bash script is its own hazard**, since bash can re-read from a byte offset, so the
order was: stop the loop by PID, wait for its in-flight `ark ingest` child to finish, edit, syntax-check,
verify one batched pass by hand, restart. The ingest loop is not a collector under the no-restart rule:
it holds no in-flight network state and every file is ledger-checked, so a restart between passes loses
nothing. Recorded here so that reading is on the record rather than assumed.

**The seed then ran immediately**, which is the proof the contention was real: `ark seed` had yielded
twice today against a lock it could never get, and with occupancy at zero it took the lock at once.
13,078 Netcraft names, in flight as this was written. It is holding the lock with the ingest loop waiting
patiently behind it, which is the correct ordering now that nothing is pending to bank, and it should
finally produce the per-phase seed timings ADR-001 has been Open for. Its silence so far is itself
suggestive: read-and-canonicalise and classify are both measured fast, so the time is going somewhere
ADR-001 listed as untested, most likely the SQLite enqueue into a 358 MB queue file.

**And the honest half of the queue fix.** The plausibility factor cured the pathological case and did not
restore the collector. Measured on the first batch to read the re-ranked queue, in flight:

    old head, all .mil        : 600 records, 599 answered, 0 captures, 0.0%
    re-ranked head, .nz + .za : 422 answered, 40 captures, 9.5%
    the pool's own history    : 51.7% over 23,058 answered

So 0% to 9.5%, and still a collapse by the yield check's own standard, which is why it correctly keeps
flagging. **Plausibility is not capture rate**: `dated / (dated + pool)` answers "is this namespace real",
and `.za` and `.nz` are entirely real namespaces that the Internet Archive simply holds thinly for
1996-2001. The score multiplies English share by a *measured* hit rate only where a `(source, TLD)` cell
has been measured, and for these it still falls back. The next piece of work is to make that fallback
conservative rather than optimistic, so an unmeasured cell ranks behind a measured good one instead of
ahead of it on English share. Named rather than started, and not claimed as fixed.

## 2026-08-11 (ADR-001 closed: one phase was 99.9% of the seed, and it was the hypothesis eliminated first)

The instrumentation this ADR added in the morning finally ran on a real seed, and the answer is not close:

    read_and_canonicalize = 0.1 s
    classify              = 0.7 s
    insert_candidates     = 1207.1 s
    enqueue               = 0.7 s

**One phase is 1,207 of 1,208.6 seconds.** `classify` at 0.7 s confirms the second hypothesis was rightly
eliminated. `enqueue` at 0.7 s clears the SQLite queue that ADR-001 listed as the leading untested
suspect, and which I had assumed all afternoon. The row-at-a-time insert, blamed **first** and declared
fixed by switching to `executemany`, was the cause the whole time.

**Why the first fix did not fix it: `executemany` is not a batch.** It is N prepared-statement executions,
and DuckDB is columnar, so each row pays a whole statement's overhead against an 8 GB store. Measured
directly at ~971 rows/s against a 4M-row table, and about 11 rows/s against the live 8.25M-row store,
which is where the 20 minutes went.

**A third hypothesis of mine, tested and refuted, which is why I tested it.** I was confident the cost was
per-row autocommit inside `executemany`. Wrapping the whole batch in one explicit transaction measured
**12.03 s against 11.88 s: no difference at all.** Three guesses have now been wrong on this one function,
which is exactly why ADR-001 forbade changing the write path on any of them.

**The fix was already in the repository.** `bulk.py` has always registered an Arrow table and inserted
set-wise; `add_candidates` was the one write path still going row at a time. `INSERT OR IGNORE` becomes
`WHERE NOT EXISTS`, which is the same thing said set-wise. Against a 4,000,000-row table, inserting 13,078:

    executemany, row at a time      13.47 s        971 rows/s
    set-based from an Arrow table    0.05 s    259,242 rows/s      267x, identical row counts

Two tests pin what the anti-join has to keep doing that `OR IGNORE` did implicitly: **deduplicate within
the batch**, since the anti-join tests each row against the table and two identical names in one batch
would both pass it and collide on the primary key, and **leave an existing row untouched** rather than
overwriting its source and round.

**And the seed did its actual job**, which was the point of the wake: 13,078 Netcraft names in, 5,608
already confirmed in the baseline, 54 on our own evidence, 2,634 already candidates, and **4,782 new
candidates with 7,186 enqueued** for the CDX engine. That is the H008 pool half banked while its
classification is still pending, which is the property ADR-003 was designed for: collection never waits on
a human, promotion always does.

**Two consequences recorded in ADR-001 rather than left implicit.** The interim allocation rule justified
interrupting a seed by "inserts autocommit, so a stopped seed keeps what it wrote"; a single statement
rolls back instead. That is a better trade at 0.05 s than at 20 minutes, and a re-run stays additive, but
the reason is now "the window is negligible" and not "partial work survives". And the phase marks only
printed at the end, so an eighteen-minute seed emitted nothing and could not be told from a hung process:
each mark now logs as it is taken, because a timing you cannot see until the run finishes does not measure
a run that has not finished.

## 2026-08-11 (the missing grain: a TLD measured at zero over 1,372 answers that nothing consulted)

The named next work was to make the pool score's rate fallback conservative. Measuring first changed what
the fix should be.

**The chain was (source, TLD) -> source -> pool-wide. It skipped the TLD.** And the TLD level already held
the answer, from journals on disk the whole time:

    .mil  0.000 over 1,372 answers        .com  0.898 over 2,492
    .gov  0.000 over   394               .net  0.915 over   330
    .edu  0.003 over 1,709               .uk   0.640 over 9,310
    .bb   0.004 over   262               .org  0.468 over 4,298
    .arpa 0.000 over    36               .za   0.309 over   392 / .nz 0.210 over 676

The spread across TLDs is roughly 900x, far wider than across sources, so it is the grain that matters most
when a cell is thin. **The `.mil` catastrophe was not a missing measurement, it was a measurement never
read**: `usenet_mention .mil` was on record at 0.000, and a *different* source's unmeasured `.mil` cell
inherited a source average, with English share doing the rest.

`expected_hit_rate` now coarsens (source, TLD) -> the **lower** of the TLD and source rates -> pool-wide.
The lower of the two is the conservative reading: with two partial views and no measurement of the pair, an
unmeasured cell must not outrank one that has been measured well. A TLD nothing has answered still falls
through to the pool rate rather than to zero, because the only way a namespace earns a first measurement is
by being queried. Four tests, including that an exact cell still beats both parents even when it disagrees
with them.

**What the rebuild did, measured.** The first 3,000 targets went from 2,675 `.mil` names to 100% `.com`,
and expected value per query rose: 0.6515 to 0.6877 over the best 50,000, 0.6110 to 0.6424 over the best
100,000. Pool targets in the best 50,000 went from 8,798 to 24,726, so the discovery half is now
competitive with gap targets at the head rather than sitting behind them. The whole-queue estimate **fell**
from 578,632 to 545,879 EE, which is the fix working: the old figure was inflated by optimism on
unmeasured cells.

**And the part that is not fixed, checked rather than assumed.** Every source at the new head has an
**unmeasured** `(source, .com)` cell and no source-level rate at all: `trade_press_mention` 869 names,
`pandora_hosts` 456, `H008-pool-names` 391, `enron_email_mention` 232. They all inherit `.com`'s 0.898,
which was measured over *good* sources (`candidate_hosts` 0.975, `ukwa_link_target` 0.915). **So the
optimism moved from the source axis to the TLD axis rather than going away.**

That is defensible where the `.mil` case was not, and the difference is worth stating precisely. `.mil` had
1,372 answers saying zero and the ranking ignored them. These sources have **no** answers, so a high rate
is a guess rather than a contradiction of evidence, and querying them is the only way to learn: with
MIN_SAMPLE at 25 a single 600-domain batch measures every source it touches, after which the exact cell
binds. The head is therefore an *exploration* head, not a proven-good one, and the yield check is the
instrument that will say within one batch whether it was worth it. The Netcraft names banked an hour ago
are among them, which is the right place for 1999-attested live web servers to be.

## 2026-08-11 (23% of the candidate pool is forged, and one figure that turned out NOT to need fixing)

Two measurements this wake, one of which produced a deliberate no-change.

**The `.edu` pool is forged, at a hundred times the volume of the `.mil` case already on record.**
`.edu` is the largest measured-dead block in the pool: 216,185 names at a measured **0.003 hit rate over
1,709 answers**. A seeded sample says why:

    mxmutpnxw.edu   uvttiyud.edu   kjmpstbnqc.edu   bqcgoppodjp.edu   texmnehxp.edu

**213,703 of the 216,185, or 98.8%, come from `usenet_address_mention` and `usenet_mention`**: anti-harvester
munged addresses, where a poster randomises their own address and a bare-host rule reads the result as a
hostname. `.edu` takes the worst of it because academic posters dominated Usenet. The check that settles it
is the other direction: the store's *dated* `.edu` names come from the supplied baseline (6,418) with
**five** from `usenet_mention`, so Usenet has contributed essentially no real `.edu` name at all.

A second mechanism appeared in the same sample: `erkeley.edu`, from `enron_email_mention`, is
`berkeley.edu` missing its first letter. A truncation artefact rather than a forgery, and it wants the same
treatment. Both are now recorded in `sources.md` under the extractor that produces them, so a future
session reading 216,185 unqueried `.edu` names as headroom finds the measurement first.

**Pool composition, measured.** With `.gov` (185,803 at 0.000) and `.mil` (186,278 at 0.000), that is
**589,739 names, 23% of the candidate pool, in TLDs measured under a 1% hit rate.** The pool's effective
size is nearer 1.98M than its headline 2.57M. Nothing is deleted and nothing needs to be: the corroboration
split means a candidate claims nothing, and C-17's plausibility factor and C-18's TLD grain now rank all of
it last by its own measured numbers.

**The no-change, which is the part worth recording.** I expected `ark stats`'s pool line to be badly
misleading, since it prints "equivalent-English if every one earned a year, an UPPER BOUND: 1,773,823".
Computing a measured expectation instead, `names x measured TLD rate x years-per-hit x English share`, gives
**1,384,175 EE**, so the upper bound overstates by **1.3x and not the order of magnitude I assumed.** The
sub-1 hit rates are largely offset by the 1.564 years a pool hit returns. A figure explicitly labelled an
upper bound and landing within 1.3x of a measured expectation is not a reporting defect, so the line stays
as it is. **Measuring first turned a planned change into a decision not to make one**, which is the cheaper
outcome and the reason the measurement came before the edit.

**Still pending, and not hurried.** The batch dispatched at 20:06 predates the C-18 rebuild, so it is
working the old `.za`/`.nz` head at 14.0% (17 captures in 121 answered), which sits neatly between their
measured 0.210 and 0.309. C-18's `.com` head gets its first real test on the next dispatch. I did not
restart the collector to bring that forward, per the standing rule.

## 2026-08-11 (I quoted four different yields off one batch, and the finished number is none of them)

The yield check reports a three-batch window, which is the right thing to alarm on and the wrong thing to
read after a queue is re-ranked: it averages over hours, so it stays low long after a fix and cannot say
whether the fix worked. So across four wakes I answered that question by hand, reading the in-flight
`.part` journal. The numbers I got, all from the same two batches: **19%, then 9.5%, then 14.0%, then
27.9%.**

**The finished batch is 8.2% of 598 answered.** None of my four readings was right.

The mechanism is one I had already designed around and then ignored. A `.part` is a gzip stream still being
appended, so a reader truncates at the last complete block, and the prefix of a batch is not a sample of
it. `ark.yield_check` skips `.part` files deliberately and says so in a comment I wrote this afternoon; I
then hand-inspected them three more times, and quoted the results to Ivo each time. **Building the
instrument and then not using it is worse than not having it**, because the instrument was right and I was
confident.

Fixed by making the check answer the question instead: it now reports the newest **finished** batch beside
the window, so a recovery shows up in one line and nobody has to open a journal. Three tests, including one
that asserts the newest reading never comes from a `.part`.

    cdx_pool: 2.7% of 1,797 answered, against 51.0% of 23,336 before; newest finished batch 8.2% of 598
    cdx_gap: 99.6% of 669 answered, against 98.5% of 45,803 before;  newest finished batch 98.7% of 150

**So the honest state of the queue work, restated.** C-17's plausibility factor took the head from a
measured 0.0% to a finished **8.2%**. That is a real gain over querying `.mil`, and it is nowhere near the
51.0% the pool used to return. C-18's `.com` head, which the TLD-grain rebuild produced, is **still
untested**: the batch dispatched at 20:06 predates the rebuild. I have not restarted the collector to bring
that forward.

**One allocation fact worth having on record while the VPS is down.** The combined queue's own report says
gap targets dominate the head: of the best 10,000 targets, **8,826 are gap and 1,174 pool**, because a gap
query answers at 96-97.5% against a pool query's 47.1%. 467,759 gap targets are ranked and waiting, and the
machine that works them is unreachable, so the better population is idle while the local engine works the
worse one. That follows C-10, which is Ivo's design and deliberately prioritises discovery because the
reviewer asked for net-new domains, and he has said the VPN is coming back shortly. **So this is recorded
rather than raised**: if the VPS stays down through tomorrow it becomes a real allocation decision for him,
and the numbers to decide it with are here.

## 2026-08-11 (the round's biggest collector had no yield check at all, and now does)

The CDX yield check closed a real gap this evening and left the same gap open one collector over. The RDAP
sweep is **this round's largest single contributor, 81,216 records and 49,012 equivalent-English**, and
nothing measured whether it was still finding anything. Presence is not progress, progress is not yield, and
that argument is not specific to CDX.

**Measured, and it is healthy: 35.1% of its newest 784 answers carry an in-window creation year, against
10.6% over 1,577,271 before that.** That is H001 doing exactly what its ledger entry predicted for `.org`
at a paced rate (34.7% in window, the best rate measured on this project), and 3.3x its own lifetime
average because the lifetime mixes in the `.com` sweeps at 8.7%.

**One number worth keeping for its own sake.** Of 1,656,921 RDAP queries, **1,107,164 returned 404**: the
registry saying the name was never registered. That is 67% of every registry query this project has made,
and it is the forged half of the candidate pool seen from the other side, independently of this evening's
`.edu` and `.mil` findings.

**RDAP needed its own verdict rather than the CDX one**, and the differences are the interesting part.

- **A 404 counts as answered.** For CDX a non-200 says nothing and must stay out of the denominator; for
  RDAP "no such domain" is information and the largest category there is. But a throttle (429, 54,097 of
  them historically), a refusal (403, 426) or a transport failure (0) is still not an answer, or a registry
  that starts rate-limiting would read as a population that stopped existing.
- **The year must be in window.** 28.4% of queries return *some* creation year and only 10.1% return one
  that counts. Scoring the first would report a sweep of 2015 registrations as productive.

**A bug my own change introduced, caught by running the cycle rather than the tests.** RDAP journals are
written under their final name and flushed as they go, where the CDX supervisor writes `<name>.part` and
renames on exit. So the newest RDAP journal is *always* a truncated gzip stream, reading one raises
**`EOFError`, which is not an `OSError`**, and my `except OSError` let it escape and kill the whole cycle.
Fixed by catching truncation and keeping what parsed.

That reopens the question this evening's correction was about, and it is answered differently for the two
collectors because they differ. CDX can wait for a renamed file, so it does, and mid-write ones are
excluded. RDAP cannot, because excluding mid-write files would exclude the newest one always, so it reads
the prefix and **says so**: the line reads `newest batch SO FAR` instead of `newest finished batch`.
Quietly trusting a prefix is what produced four different rates off one batch, so the flag exists to stop
the same mistake being available.

    cdx_pool: 2.7% of 1,797, against 51.0% of 23,336;    newest finished batch 8.2% of 598
    cdx_gap:  99.6% of 669, against 98.5% of 45,803;     newest finished batch 98.7% of 150
    rdap:     35.1% of 784, against 10.6% of 1,577,271;  newest finished batch 38.0% of 550

Six new tests, 408 passing. The `.com` head from C-18 is still untested: no batch has been dispatched since
that rebuild, batches run about 70 minutes, and I have not restarted the collector to hurry it.

## 2026-08-11 (bringing the constitution back into line with the day, which falsified three of its claims)

Nothing was broken this wake: four collectors up, tree clean, RDAP healthy at 35.1%, and the one pending
verification is waiting on a batch I must not hurry. So this is the third step of a cron wake rather than
the fourth, and it found the worst place in the repository to leave a false claim: **`CLAUDE.md`, which is
loaded at the start of every session.**

Three statements in it were true this morning and are not now.

1. **"That is safe: inserts autocommit and a re-run is additive."** The reason a seed is safe to interrupt.
   `add_candidates` became a single set-based statement this evening, so a stopped seed now **rolls back**
   rather than keeping what it wrote. The conclusion survives and the reason does not: a re-run is still
   additive, and the window is now a fraction of a second instead of twenty minutes, so interrupting still
   costs nothing. Rewritten to say that, and to record that the ordering is now **enforced in code** by
   asymmetric lock patience rather than stated in prose, with the note that a long patience does not make a
   low-priority job polite, it makes it queue and then hold.
2. **"A 20-minute ingest is a 20-minute outage for the auditors."** Both causes of that are fixed and
   measured: the ingest loop's 636 invocations a pass (89% lock occupancy, now 0%) and the row-at-a-time
   insert (1,207 of a 1,208-second seed, now 267x faster). The DuckDB single-writer rule still matters, but
   for correctness rather than for waiting, so the trap now says that instead of quoting a number that no
   longer happens.
3. **"It checks both collectors"**, in the cron section, which has been three since the RDAP yield check
   went in an hour ago.

The measured before-and-after figures are now in the standing rules themselves, because the surrounding
advice was written while the store was effectively unusable and a reader needs to know that the constraint
it was written under is gone.

**Why this is worth a whole wake.** `CLAUDE.md`'s own first paragraph says it holds only what never
changes, precisely because `phase5-handoff.md` was accurate for one day and had three claims disproved by
the next morning. Today I disproved three of `CLAUDE.md`'s own claims in eight hours. The file was not
wrong to contain them, they were true when written; the failure mode is leaving them there, and the only
defence is that a wake with nothing broken spends itself checking.

## 2026-08-11 (a pre-registered prediction, and the ranking learning inside two batches)

**One batch is a noisy estimate, and the data says so.** The two batches that worked C-17's `.za`/`.nz`
head returned **8.2% and 32.2%** of ~600 answered each: same population, same queue file, same ordering,
a 4x spread. That qualifies the instrument I added an hour ago. The `newest finished batch` line is a
**leading indicator, not a measurement**, and the three-batch window remains the thing to judge on. It also
means C-18 cannot be called either way on the single batch that lands next, which is worth writing down
before that batch lands rather than after.

**So the prediction is pre-registered.** The batch dispatched at 21:08 is the first to read the queue the
TLD-grain rebuild produced. Its 600 targets, taken by replaying the engine's own skip set over the queue
file, are 100% `.com` from four sources, and the ranking's own expected hit rate for exactly those names is
**28.4%**. Recorded here before the answer exists, so the next wake is a test of the ranking's calibration
rather than a reading of it. Against: the pool's 49.8% history, and the 8.2%/32.2% pair above.

**The ranking learned inside two batches, exactly as designed.** Two wakes ago every source at the head had
an unmeasured `(source, .com)` cell and I flagged that the optimism had merely moved axis. With
`MIN_SAMPLE` at 25, the batches since have measured three of the four:

    trade_press_mention   cell(.com) 0.086     was unmeasured, inheriting .com's 0.874
    pandora_hosts         cell(.com) 0.111     was unmeasured
    H008-pool-names       cell(.com) 0.536     was unmeasured
    enron_email_mention   still unmeasured, so it inherits 0.874

That is the self-correcting property the design was betting on, and it took about two hours rather than the
"one batch per cell" I estimated. The exact cell now binds for three of the four, so `trade_press_mention`
and `pandora_hosts` will sink on the next rebuild. **The current queue file still carries them at its head
because it was built before those cells existed**, which the cycle's own `rebuild_derived` will correct
once the file passes 1.5 hours old, at about 21:38. No action needed, which is the point of having built it.

**The finding worth keeping: `H008-pool-names` measures 0.536.** The 13,078 Netcraft names banked at 19:52
are hitting at **53.6%**, the best of the four head sources and above the pool's own 47.1%. So that source
is productive through the CDX engine **whatever Ivo decides about its classification**: `candidate-only`
would still leave 4,782 new candidates converting at better than the pool average. The approval decision
governs whether its own records can date a year, not whether the names were worth having, and the names
were worth having.

## 2026-08-11 (the pre-registered test: predicted 28.4%, measured 24.2%, and a third staleness mark)

**The prediction held.** The batch dispatched at 21:08, the first to read the TLD-grain queue, finished at
**24.2% of 599 answered** against the **28.4%** written down before it landed. That is 4.2 points low, about
15% relative, from a model built entirely out of measured `(source, TLD)`, TLD and source rates. So the
scoring is roughly calibrated and the queue ordering can be trusted going forward, which is the useful
result rather than the rate itself.

What one batch still cannot do is separate C-17 from C-18: the `.za`/`.nz` head gave 8.2% and 32.2%, the
`.com` head 24.2%, and the batch-to-batch spread inside one population is larger than the gap between the
two heads. That was said in advance and it stays said. The windowed rate is meanwhile recovering on its own:
2.7%, then 13.5%, now **21.5%** against a 48.5% history, and it no longer trips the collapse alarm.

**Then the wake found a staleness the check could not see, and the reason is instructive.** The pool queue
was two hours old and `stale_derived` correctly reported it **fresh**, because a pool queue is compared
against the newest *candidate* and no candidate had arrived since the Netcraft seed. But the queue's
**ordering** was out of date, because in those two hours three of the four sources at its head had had their
`(source, .com)` cells measured for the first time: 0.086, 0.111 and 0.536, against the 0.874 they had all
been inheriting from the TLD.

**A pool queue is invalidated by a new journal, not only by a new candidate**, because its ordering is
`measured hit rate x English share` and the rate is measured out of the journals. Nothing in the store moves
when a journal lands, since the misses never become rows, so no store mark could ever have seen it. There is
now a `journals` mark, the pool queue is checked against the later of it and `candidates`, and a derived file
may declare several marks with the most recent one binding. It immediately reported the queue **2.2h behind
the newest journals**, which is the thing I had just found by hand.

This is the second correction to the same check and they rhyme. The first compared everything to the
baseline release, which changes monthly, and missed three stale lists. This one compared against store rows
only, and missed a stale *ranking*. Both times the check was internally consistent and asking the wrong
question.

**The cycle then acted on it unattended, which is the part worth having.** `rebuild_derived` rebuilt the
queue, reported that the running collector picks it up at its next dispatch, and restarted nothing. The
re-rank moved the head from `.com` to **`.uk` from `usenet_mention`**, 1,899 of the top 2,000, and that is
correct rather than surprising: `.uk` measures a 0.640 hit rate against a 0.9813 English share for 0.628
expected equivalent-English per query, where `.com`'s better 0.874 rate against a 0.6321 share gives only
0.552. The metric rewards `.uk`, so the queue does.

**No prediction is registered for the next batch.** The one dispatched at 22:20 predates this rebuild and so
still reads the `.com` queue; the `.uk` head is first tested on the batch after it.

## 2026-08-11 (the round crossed 1.3%, and the interim report was refreshed to verified figures)

The interim draft had carried its 16:52 figures all afternoon and its own status line told Ivo to re-run the
verifier before sending. With the round having moved 1,694 equivalent-English since, that instruction was
worth honouring for him rather than leaving as a chore.

Re-measured and re-verified at 23:07 with `round_figures.py --verify`:

    3. Increment                    147,584 records      was 145,305
    4. Equivalent-English increment  81,107.3232         was 79,413.4525
    5. Growth rate                    1.302639%         was 1.275434%

    his validator: 147,584 scored, 0 rejected, 0 already his, difference 0.0000

**The round crossed 1.3% during the evening.** Per-year growth is now 1996 +0.8242%, 1997 +1.8398%,
1998 +1.0285%, 1999 +1.1763%, 2000 +2.0234%, 2001 +0.9511%.

**One improvement over the afternoon version rather than just fresher numbers.** That draft had to quote the
discovery split as a percentage, because the split came from a `docs/ROUND.md` run half an hour off the
figures and quoting both as absolutes would have shown a 547-record drift. This time both halves came out of
the same measurement and sum exactly to fields 3 and 4: **121,361 + 26,223 = 147,584** and
**71,336.4416 + 9,770.8816 = 81,107.3232**, so the email states them as absolutes. 88.0% of the increment's
equivalent-English is on 116,253 domains absent from all six annual files.

**Two claims in the body are now independently confirmed** rather than resting on the measurement that
produced them. The email says 38% of `.org` RDAP answers carry an in-window creation date; tonight's yield
check, which reads the journals rather than the store, put the newest finished RDAP batch at **38.0%** and
the three-batch window at 35.1%. And `rdap_snapshot` is still the round's largest contributor at 82,943
records and 50,238.9 equivalent-English, which is what the `.org` paragraph claims.

The one sentence I still cannot verify is unchanged and still flagged in the notes block: "both machines are
collecting continuously" is true of this machine and inferred for the VPS, which has been unreachable all
evening.

## 2026-08-11 (two .com batches say the ranking runs optimistic, and the .uk batch will say where the bias lives)

**The `.com` head, both batches, against a prediction registered before either landed:**

    predicted   28.4%
    measured    24.2%  (599 answered)
    measured    21.4%  (599 answered)

Consistently below, and tightly so. That is a firmer result than the single batch I refused to draw a
conclusion from earlier: the ranking is not noisy around the truth here, it is **biased optimistic by
roughly 20% relative**. Worth contrasting with the `.za`/`.nz` head, whose two batches were 8.2% and 32.2%:
the `.com` pair differs by 2.8 points where that pair differed by 24, so the variance is a property of the
population rather than of the measurement.

**Where the bias comes from is now testable, because the next batch is a natural control.** The queue was
re-ranked at 22:22 and the batch dispatched at 23:22 is the first to read it. Its 600 targets are 100%
`.uk` from `usenet_mention`, and **600 of 600 have an exactly measured `(source, TLD)` cell: nothing falls
back at all.** The `.com` batch had 68 of 600 falling back to `.com`'s TLD rate of 0.874, which is the most
likely source of its optimism, since `enron_email_mention` has never been queried and was inheriting a rate
measured over `candidate_hosts` and `ukwa_link_target`.

**So the prediction is 53.3%, and it discriminates.** If it lands near 53.3%, the exact cells are well
calibrated and the bias lives in the fallback, which is the part C-18 changed and the part I already
flagged as having only moved axis. If it lands 20% low like the `.com` pair, the bias is in the cells
themselves and the fallback is exonerated. Either answer is worth having and neither is available from a
batch that mixes the two, which this one does not.

For scale: 53.3% is close to the pool's own 47.6% history and more than double the `.com` head's ~22.8%
mean, so if the ranking is right the re-rank roughly doubles the engine's yield. The windowed rate has
meanwhile climbed to 25.9% of 1,797 and the collapse alarm stays clear.

## 2026-08-12 (the control batch refutes my fallback hypothesis: the bias is in the measured cells)

The pre-registered discriminating test resolved, and it went against the explanation I favoured.

    head    cells exact    predicted    measured              ratio
    .com    532/600        28.4%        24.2%, 21.4%          0.85, 0.75
    .uk     600/600        53.3%        43.0%                 0.81

**The `.uk` batch had no fallback at all and is just as optimistic as the `.com` one.** I had reasoned that
the `.com` over-prediction came from its 68 falling-back targets inheriting `.com`'s 0.874, and said so in
advance precisely so it could be wrong. It is wrong. **The bias is in the exactly measured `(source, TLD)`
cells**, and the fallback C-18 changed is not the culprit.

**A hypothesis for the mechanism, labelled as one because it is not measured.** A cell's rate is computed
over the domains of that cell **already answered**, and the queue works down in expected-value order, so
the part of a cell that has been consumed is systematically the part that was ranked best. What remains is
the tail. If that is right, every cell rate is an estimate taken on the better half of its own population,
the ranking is optimistic by construction as a population depletes, and the size of the bias should grow as
a cell is worked through. That last part is testable and has not been tested.

**What follows practically, which is the useful half.** The consistent ratio near 0.80 across three batches
and two populations means **the ordering is still trustworthy even though the absolutes are not**: if every
cell is inflated by roughly the same factor, the ranking between cells survives. So the queue should keep
being built the way it is, and any figure quoted from it as an expectation should be read about 20% high
until this is understood. Written here rather than corrected in code, because applying a 0.8 fudge factor
to a model whose error I have one hypothesis and no measurement for is exactly the kind of guess ADR-001
took three wrong tries to stop making.

**And the re-rank plainly worked.** 43.0% against the `.com` head's 24.2% and 21.4%, approaching the pool's
own 47.2% history, with the windowed rate climbing 2.7% to 13.5% to 21.5% to 25.9% to **29.5%** as the
`.mil` batches age out. The discovery engine is roughly twice as productive per query as it was four hours
ago, and the sequence that got there was: measured a zero, found a missing ranking factor, found a missing
grain, found a missing staleness mark, and let the cycle rebuild unattended each time.

## 2026-08-12 (depletion refuted too, and the over-prediction is left unexplained on purpose)

Two hours ago the control batch refuted my fallback explanation for the ranking's ~20% optimism, and I
offered a replacement: **depletion**. A cell's rate is measured over its already-answered domains, the queue
works down in expected-value order, so the consumed part is the better part and what remains is the tail.
I labelled it a hypothesis and said it was testable and untested. It is now tested, from the journals alone.

Reading all 27,527 answered pool domains in chronological order and splitting each cell into its first and
last third:

    cell                        n     first third   last third   change
    usenet_mention .uk      7,201        52.2%        51.0%       -1.2%
    usenet_mention .org     4,029        44.5%        44.2%       -0.3%
    ukwa_link_target .uk    2,568        91.6%        91.5%       -0.1%
    usenet_mention .au      2,111        33.9%        28.3%       -5.5%
    ukwa_link_target .com   1,874        90.7%        92.3%       +1.6%
    usenet_mention .za        688        45.9%        36.7%       -9.2%
    tucows_mention .com       537        84.4%        83.8%       -0.6%

    mean change across 13 cells with 300+ answers: -0.9 points, and 3 of the 13 ROSE

**Depletion is real and far too small.** A mean drift of about one point cannot explain a ten-point gap
between the 53.3% predicted for the `.uk` head and the 43.0% it returned, and a third of the cells move the
wrong way entirely. Two of my explanations for this bias have now been refuted by measurement inside two
hours, the fallback and depletion.

**The gap is a discontinuity rather than a trend, which is the actual finding.** `usenet_mention .uk` has
answered 7,201 domains at a stable 51-52% across its whole history, and the very next 600 of the same cell
returned 43.0%. Nothing in the cell's own trajectory predicts that step. Something distinguishes the names
this batch drew from the names the same cell drew before, and the ordering within a cell is a content hash,
so it is not an obvious candidate.

**I am not proposing a third mechanism.** ADR-001 took three wrong guesses on one function before
measurement settled it, and the rule that came out of that is not to restructure on a guess. So the state
of knowledge is recorded as it stands: the ranking runs about 20% optimistic, consistently, across two
populations and three batches; the fallback is exonerated; depletion is refuted; the cause is unknown; and
because the ratio is consistent, **the ordering remains trustworthy even though the absolutes are not.**
That is enough to keep building the queue exactly as it is and to read any expectation quoted from it about
20% high, which is what the previous entry already concluded and what this entry does not change.

## 2026-08-12 (four explanations tested, none sufficient, and stopping the hunt deliberately)

Two more candidates measured and neither holds.

**Recency of the names, refuted.** If the `.uk` batch drew newly seeded candidates while the cell's 7,201
historical answers were older names, that would distinguish them. It does not: the batch's median
`first_seen_at` is 2026-08-07 04:12 against 2026-08-06 08:31 for the whole 60,652-domain
`usenet_mention .uk` population, and inside the batch the hits and the misses are the same age to within
forty minutes (04:12 against 04:56). Age separates nothing.

**Archive conditions, not supported.** The supervisor logs throttles per batch, so this is checkable
against 39 batches with 100+ answers. The correlation between throttles-per-query and hit rate is **-0.34**,
which is weak, and it is confounded by the two `.mil` batches whose 0.0% has a known population cause.
Against it directly: on 7 August batches throttled 0.62 to 1.03 times per query and returned 40.8% to 50.5%,
while on 11 August they throttled **less** per query, 0.56 to 0.72, and returned 0%, 0%, 32.2% and 21.4%.
Less throttling, worse yield. The direction is wrong for the story.

**So four explanations have now been tested and refuted: the fallback, depletion, recency, and archive
throttling.** The ranking runs about 20% optimistic, consistently, across two populations and four batches,
and I cannot say why.

**Stopping here on purpose.** The practical conclusion has not moved since the first measurement and does
not depend on the mechanism: the ratio is consistent, so **the ordering is trustworthy while the absolutes
are not**, the queue should keep being built exactly as it is, and any expectation quoted from it reads
about 20% high. Four cron wakes of hypothesis-and-test have added confidence in that conclusion and no
mechanism, which is the point at which continuing becomes the thing ADR-001 warns about: guessing at a
system that is working, in small increments, because the guessing is available. If the mechanism matters
later it deserves a deliberate piece of work with a design, not another twenty minutes between collector
batches.

What is worth carrying forward is the negative result itself. A future session that notices this gap will
otherwise spend its own evening on the same four ideas, and all four are now closed with numbers.

---

## 2026-08-12 (early hours): Ivo's Netcraft condition, tested three ways and failed

He answered the one open approval conditionally: the domains do not look human typed to him, and *if you
are sure of how these lists came about and that they hold domains which were actually active during the
year they were surveyed, then they can be master evidence*. Both halves had to hold. The first does and
the second does not, so the class is filed `candidate-only` (C-19).

**Provenance, settled by reading the pages rather than reasoning about them.** `/domains/cache/<word>.html`
is an alphabetical dump of every hostname in Netcraft's database containing the search word, one `<H3>`
every tenth entry and `<LI>` for the rest, titled "<word> hosts". No prose, no author, no per-item date.
So nobody typed these hostnames, the corroboration split was never the right question, and the original
rejection of this lead as `typed` was wrong on its facts. That much of the earlier argument survives.

**Contemporaneity, which nobody had tested.** Three instruments, two controls. The positive control is 230
domains the store dates to 1999 from an archive capture, so known live that year; the negative control is
the undated candidate pool, names carrying no claim to any year.

| instrument | netcraft | live in 1999 | undated pool |
|---|--:|--:|--:|
| earliest archive capture 1999 or earlier | 9.4% (127) | 100% by construction | 10.9% (12,836) |
| still registered today | 52.2% (230) | 94.3% (230) | n/a |
| registered continuously since 1999 or earlier | 25.0% (120) | 74.7% (217) | 16.6% (413,942) |

**The first row is the one that decides it**, because it is the only one with no survivorship bias in it:
both populations were queried by the same engine, against the same archive, on the same days, so the
archive's own thin 1999 coverage applies equally to both. Netcraft's names are no likelier to have been
captured by 1999 than names with no claim to 1999 at all. The other two rows agree in direction and are
weaker: the live-in-1999 control is drawn from archive-captured domains, which skews to prominent sites
that were likelier to keep a registration for 27 years.

**A test that cannot settle this, recorded so it is not run again.** Registry creation dates were the first
instrument I reached for and they are the wrong one: a 1999 domain that lapsed and was re-registered
reports the later date, so "created 2004" is equally consistent with a real 1999 site and an invented name.
Twelve sampled names with creation dates from 2003 to 2026 were each verified as genuinely printed on the
archived 1999 page, which confirms the extraction is faithful and leaves the inference untested. The 25.0%
against a 16.6% base rate is a real but weak enrichment, and on its own it would not have decided anything.

**The cost of refusing is close to nothing, which is what makes this an easy call rather than a brave one.**
The forgone reading was 8,741 pairs and 5,708.4 equivalent-English. All 13,078 names were banked as
candidates on 11 August, the engine has been querying them since, and 127 are already dated on their own
capture evidence, which needs no approval and asks nobody to trust Netcraft's list. **The names still pay;
they just pay through evidence that does not depend on the source being what it looked like.**

## 2026-08-12: the discovery loop closes, on Ivo's instruction

His words: as it gets harder to find new domains, grow the candidate pool by querying IA CDX over the pool,
scanning the captured sites for mentions of other domains, scanning those in turn, and so on. Keep hunting
master sources, but do not let their absence stop collection. This is now a standing rule in `CLAUDE.md`.

**The pieces all existed and the edge between them did not.** `ark download` has fetched archived pages and
extracted their outbound domains since round 1, but every one of the five rounds run so far was fed by a
seed list a human chose: Yahoo categories, the WWW Virtual Library, a curated directory. That makes page
expansion a *source*, and sources run out. `scripts/build_expand_seeds.py` feeds it from the engine's own
journals instead, which turns it into a cycle that regenerates its own input:

    pool candidate -> CDX dates it -> fetch that capture -> read the domains its page names
      -> those become pool candidates -> the engine queries them -> they become seeds in their turn

**Why the population is good.** A domain the engine has just dated is by construction a site that was live
in the window, and the sites a period page links to are overwhelmingly period sites. That is a far better
targeted population than any list of guessed names, and unlike a corpus it cannot be exhausted while the
engine is still finding anything.

**Ranking is a proxy and is labelled as one in the script.** What a seed is worth is the count of domains on
its page we do not already hold times their English share, and none of that is knowable before fetching.
Two knowable things correlate with it: links are local, so an English-region page mostly names
English-region domains, which makes the seed's own TLD weight a stand-in for its harvest's; and a site
captured in several in-window years was maintained rather than parked, so its page carries more links.
Replace it with measured net-new-per-page once the loop has produced enough journals to measure.

Seeds are emitted in both `www.` and bare form, because the engine queries by host and never learns which
form the archive holds. The wrong form costs one CDX query returning no captures and is then skipped
forever; the page fetch, which is the expensive part, only happens where captures exist.

## 2026-08-12: the VPS ran 31 hours at zero yield, and the check built to catch that was blind to it

A VPN window opened unprompted, so per the standing rule I fetched first and asked questions
afterwards. `just engines` reported the VPS up for 1 day 7 hours, its journal growing, its supervisor
healthy, every journal already copied home. **And its last finished batch was 300 queried, 274
no_capture, no `with_capture` key at all.**

Measured over its twelve most recent journals rather than inferred from one: **3,219 answered queries,
0 hits, 0.0%, across roughly 15 hours.** Its own history is 49.5% over 25,767. It was grinding the tail
of `queue_shard1.txt`, built 10 August and long exhausted, skipping 6,000 to 8,600 already-journalled
names per batch and asking only the leftovers, which are the names that never had a capture.

**Why nothing caught it, which is the part worth keeping.** `yield_check` exists precisely for this and
had `COLLECTORS` hardcoded to `cdx_pool`, `cdx_gap` and `rdap`, on the authority of the supervisor
header's statement that those are the prefixes the population may use. **The header states intent; the
directory holds the facts.** `data/raw/cdx` holds six: `cdx_gap` 104 journals, `cdx_q1` 101, `cdx` 72,
`cdx_q0` 67, `cdx_pool` 65, `cdx_gap_vps` 44, `cdx_disc` 6. The VPS has always run `cdx_q1`. So the one
check designed to notice a collector finding nothing could not see the collector that was finding
nothing, and `CLAUDE.md` asserted the false pair as a rule with "do not invent a third" attached.

Fixed by asking rather than listing: `active_cdx_collectors` enumerates every prefix that has written a
journal in the last 24 hours, so a collector started under any name is measured. Activity is judged
including a `.part`, since a live collector's newest file is usually the one it is still writing, while
the measurement still excludes `.part` files. Three tests pin it. First run after the change:
`cdx_q1: 0.0% of 796 answered held a capture, against 49.5% of 25,767 before that`, raised as attention.
The false claim is corrected in `CLAUDE.md` where it was made, not only here.

**The repair, done inside the window.** A fresh gap queue built against the current baseline:
466,239 targets, 218,611 equivalent-English expected, `completeness: every hit is a new pair on a domain
already held`. Shipped, and then **not** installed by restarting anything. A supervisor passes `$TARGETS`
to `ark cdx` at every dispatch and `ark cdx` reads the file at batch start, so overwriting the file it
already points at is the whole job: the old list was copied aside as `queue_shard1.txt.exhausted-20260812`
and the gap queue written in its place. No process was touched, nothing was killed, and the batch in
flight was not thrown away. Its dispatch stamp is 39 minutes before the file's mtime, so the batch after
it is the first one reading the new list.

**A clock note, because this project has already been bitten by timestamps.** Both machines' clocks were
about 10 hours behind and were corrected by NTP mid-session, which is why `engine_status.sh` printed a VPS
time of 00:31 UTC and, fourteen minutes later, the same machine reported 10:47 UTC. Nothing was decided on
a wall clock, and the one ordering that mattered was settled from file mtimes on the VPS's own filesystem
rather than from either clock.

## 2026-08-12: the closed loop, measured as a matched A/B, and why it will not run this week

Ivo's instruction was to grow the pool by scanning captured sites for mentions of other domains and
scanning those in turn. The loop is built and is standing policy. It is also, measured, not worth archive
requests at our present coverage, and both halves of that belong on the record.

**The population is the best we have.** Hit rate by where a candidate came from, over 27,955 answered pool
queries in the same days: `ukwa_link_target` 90.4% of 5,123, `tucows_mention` 85.8%, `enron_email_mention`
58.2%, `H008-pool-names` 49.0%, `usenet_mention` 38.9% of 18,767, `usenet_bare_mention` 7.2%,
`trade_press_mention` 8.6%, `pandora_hosts` 2.9%, `usenet_address_mention` 0.1%, pool-wide 46.0%. Names
taken from a link graph are twice as datable as the pool average and 900x the worst seam we hold.

**The retail version does not reach.** 240 archived pages, two arms of 120, same budget:

| | home pages | discovered link pages |
|---|--:|--:|
| pages settled | 120 | 120 |
| had an in-window capture | 98 | 104 |
| of those, zero outbound domains | 60 | 66 |
| distinct domains harvested | 53 | **391** |
| already held, and already dated | 50 | **386** |
| net-new pool names | 3 | 5 |

Seeding a site's home page harvests almost nothing, because a small site of the period links inward: 60 of
98 captured home pages carried no outbound domain at all. Asking the archive which pages a site has and
choosing the link-looking ones fixed that and harvested **7.4x more domains**, 391 against 53. **It moved
net-new from 3 to 5.** The binding constraint is not page selection, it is that a 1996-2001 page links to
sites the store already holds: 386 of 391, every one of them already dated. `ark ingest` confirmed it
independently at `enqueued: 7` over both journals.

So the conclusion is about scale, not about the idea. The bulk form of exactly this idea is our single best
population; the retail form would need roughly 600,000 page fetches at 20 seconds each to reach a million
mentions. **Expansion earns archive requests when a bulk link graph can be found, and the queue is never
the constraint while 2.5M candidates sit unqueried against an engine clearing 600 an hour.** Recorded in
`CLAUDE.md` beside the standing rule so the next session does not spend a week on page fetching.

## 2026-08-12: the gap engine's repair, verified rather than asserted

The first batch drawn from the rebuilt gap queue finished at 14:26 local and is the number the earlier
entry could not give. `cdx_q1_20260812T112626Z`, dispatched 11:26:26 UTC, which is 41 minutes after the
file was replaced, so it is unambiguously the first batch reading the new list:

    {'with_capture': 238, 'years_found': 765, 'no_capture': 27,
     'failed_-1': 32, 'failed_0': 2, 'failed_403': 1, 'queried': 300, 'throttles': 63}

Measured from the journal rather than the log line: 265 answered, **238 held a capture, 89.8%**, 765
year-records, spread 1996: 42, 1997: 53, 1998: 88, 1999: 186, 2000: 181, 2001: 215. Banked the same hour as
765 evidence rows, 261 new pairs, 238 unique domains. **Zero of 3,219 before the swap, 238 of 265 after**,
against that machine's own healthy batch of 7 August at 247 of 300.

**2.55 dated records per request** is the figure worth carrying, against roughly 0.46 for the discovery
half. The two halves are not competing for the same metric: the gap engine buys pairs on domains already
held and the pool engine buys domains, which is why the round quotes them separately.

**A `.part` was read for an early signal and deliberately not quoted.** Thirty minutes before the batch
finished, a truncated read of the in-flight file showed 172 captures in 186 answered. That is 92.5% and it
is not the number, because a gzip stream still being appended ends at its last complete block and the
prefix is not a sample; this project has quoted 19%, 9.5%, 14.0% and 27.9% off one batch that finished at
8.2%. It was used only for the question a partial read can answer, which is whether the count is zero.

**The round after the repair and one pool batch:** 157,682 pairs, 122,624 net-new domains,
90,024.2699 equivalent-English, **1.445888%**, his calculator agreeing to 0.0000 with nothing rejected and
nothing already his. Up from 150,355 and 1.338051% five hours earlier.

**The handover worked, which is the other thing that needed observing rather than trusting.** The three
local engines expired at 12:00:35 UTC; `extend_engines.sh` started their replacements on the
2026-08-15 00:00 UTC deadline in the same second, and a supervisor on the new deadline was confirmed
running a minute later. `maintain.sh` was excluded by design and the reason is now in the script: it takes
an iteration count rather than a deadline, and at pass 124 of 900 after 18h33m it has about 4.8 days of
headroom.

## 2026-08-12: what Ding wants a report to be, and the rewrite that followed

Ivo, on reading the interim report: too long, wrong focus. **"Ding doesn't care about technical details or
problems we encountered, but more about our meta-level approach and the results it yielded and how we
continue."** Worth recording as a durable fact about the reviewer rather than as a note about one document,
because it governs the weekend submission too.

Rewritten from roughly 1,600 words to 904, and restructured from a narrative of the week into four ideas:
the evidence wall as auditability rather than as bookkeeping; the separation of measuring a source from
admitting it, as the thing that makes delegation safe; selecting sources by the property that somebody had a
reason to write a name down on a date, rather than by subject; and the corpus regenerating its own inputs.
Then the two populations as a floor and an upside, then how it continues.

**Everything self-critical came out.** The lost day, the monitoring blind spot, the partial-read trap, the
7.4x pilot that yielded nothing, the `.org` throttle misdiagnosis and the Netcraft control tables are all
gone. Two survive in abstracted form, because they are method rather than incident: "curated collections of
notable sites add almost nothing, because prominence is what a crawl-derived baseline already contains", and
"a process that cannot reject its own best find is not measuring anything". The Netcraft rejection is
referred to without being named.

**The limitations belong in the round report, not in an interim note.** That is where the lost day, the
contention fixes and the refuted hypotheses should appear, and the material is already in this file.

**Numbers appear exactly once**, in section 1, so the document has nothing to keep in sync with itself. The
two figures quoted later are properties of the method rather than of the round: 2.55 records per request for
the completeness engine, and 466,239 addresses still unasked.

The 11 August draft is deleted. Superseded documents are not history worth keeping in `private/`, and
`docs/notes.md` already holds every figure they carried.

## 2026-08-12: the second gap batch, and why the report quotes 2.29 rather than 2.55

A second batch off the rebuilt queue finished and was banked: 300 queried, 254 answered, **205 held a
capture, 80.7%**, 607 year-records, 207 new pairs. So the first batch's 89.8% was not a one-off and it was
the better of the two.

**Over both batches: 600 requests, 519 answered, 443 holding a capture, 85.4%, and 1,372 records, which is
2.29 records per request.** The report quoted 2.55 off the first batch alone for about half an hour, and
that figure is now replaced everywhere it appeared. Nothing was sent with it, but the pattern is the one
this project keeps rediscovering: a single batch is a sample of one, and the honest denominator is every
request issued rather than every request answered. Quoting per-answered would have given 2.64 and flattered
the engine by excluding its own transport failures.

Round after banking both: **158,488 pairs, 123,118 net-new domains, 90,752.0780 equivalent-English,
1.457540%**, his calculator agreeing to 0.0000 with nothing rejected and nothing already his. Discovery is
87.6% of the increment by value. Both documents refreshed to that set at 15:40.

## 2026-08-12: the interim report cut a third time, and where the candidate pool comes from

Ivo again: still too verbose, too specific where it need not be, each idea sayable in fewer words, and one
thing missing, namely why we have 2.5M spare candidates and where they come from. 906 words to 809 to **717**,
with the structure untouched.

**The addition is measured, not characterised.** The undated pool is 2,566,149 names and it is overwhelmingly
one source: `usenet_address_mention` 47.8%, `usenet_mention` 45.0%, `usenet_bare_mention` 5.3%, so **98.1% is
Usenet**, then `pandora_hosts` 0.7%, `trade_press_mention` 0.5%, the Netcraft names 0.3%, and a long tail
including `ukwa_link_target`.

**The concept it illustrates is the one worth keeping**: a name and its date need not come from the same
place. Every source mentions far more domains than it can date, and a human-typed mention names a domain
without establishing that it existed, so the mention yields a candidate and no year. The archive then dates
that name from its own capture, which needs no trust in the mention at all. That is the same asymmetry the
corroboration split rests on, seen from the collection side rather than the evidence side, and it is also why
the loop can feed itself.

**The report says explicitly that 2.5M names are not 2.5M future records**, because yield by origin runs from
0.1% for munged Usenet addresses to 90.4% for link-graph names. Without that sentence, "the queue is not the
constraint, its quality is" reads as an excuse for not finding more sources; with it, it is the argument for
ranking.

**A note on measuring length here.** There is no Word or LibreOffice on this machine, so a `.docx` cannot be
paginated directly, and the `<Pages>` value pandoc writes into `docProps/app.xml` is a placeholder that always
reads 1. Believing it would have been a confident wrong answer. Rendering the same markdown to PDF at
Word-like settings is the honest proxy: 2 pages with page 2 a third full, so about 1.4 pages of content.

Figures refreshed in both documents at 16:05: **159,787 pairs, 123,893 net-new domains, 91,908.4230
equivalent-English, 1.476112%**, 87.5% discovery by value, his calculator agreeing to 0.0000 with nothing
rejected.

## 2026-08-12: the cron was not broken, the schedule now gets checked anyway, and idle stops being acceptable

Ivo: he had seen no 15-minute wake in hours and assumed the schedule was dead. It was not. The job was
still registered, and the contract explains what he saw: **a cron job fires only while the session is idle,
never mid-query.** I had been in continuous multi-hour turns, so every wake that fell inside one had nowhere
to land. The cure is bounded turns, not a new job, and the diagnosis matters because deleting and recreating
a healthy schedule is a way to break the thing you were worried about.

Two properties worth having on the record, both of which look like a broken schedule and are not:

- **Idle-only firing.** A long turn swallows wakes. A missing wake is more often the agent working than the
  cron failing, so the check is "is a job registered", not "did one fire recently".
- **Session-only, seven-day expiry.** The `durable` flag has no effect: nothing is written to disk and the
  schedule dies with the session. **The collectors do not depend on it**, holding absolute deadlines of
  their own, which is the property that makes an unattended stretch safe. If the session dies, collection
  continues and only the agent stops.

Both are now step 0 of the cron checklist in `CLAUDE.md`, on his instruction that the schedule be checked on
every call.

**And "everything is fine" is no longer a complete outcome**, which `CLAUDE.md` had said it was. His words:
*"don't forget to continue to look for new sources every time you are called. Never stop looking. Idle time
is the enemy, you have been way too idle."* So step 5 makes hunting a source the standing default for a wake
that finds healthy engines, which is exactly the case the old rule told the agent to write one line about
and stop.

**The mechanism, because an instruction without one decays.** `docs/approved-sources-list.md` gains
`## Found, awaiting triage`, an append-only queue of sources found, screened and reachability-checked but
**not yet priced**. His two answers map onto the existing gate with no new vocabulary: *add to the candidate
pool* is `candidate-only`, *fold in directly* is `master`.

**The part that needed code rather than prose.** The cycle mirrors every `pending` class into
`key-decisions.md` as its own OPEN entry, which is right for a priced request carrying a sample and a
counterfactual, and catastrophic for a queue designed to grow without bound: forty found sources would have
become forty entries on the one surface he reads, and that surface stops being read the moment it stops
fitting on a screen. So `approvals.load` now records which `##` section an entry sits under, `Approval.is_triage`
distinguishes the two populations, and the triage queue is mirrored as **one entry naming the count**. The
gate itself is unchanged: a pending class cannot date a year either way, so nothing is blocked while the
queue sits there.

**A second bug fixed on the way.** The parser did not reset on a `##` heading, so an entry whose `Decision:`
line had been forgotten would silently adopt the decision of the next section's first entry. Against a file
where the next section is "Approved before this mechanism existed", that reads as **approved**. Now a section
heading ends any unfinished block, with a test.

**Schedule.** Full report on **Sunday evening**, so the engines were re-armed to 2026-08-17 00:00 UTC, and
`extend_engines.sh` gained an atomic `mkdir` lock: the deadline has moved twice in one round, so re-arming is
routine, and two waiters blocked on the same pattern would both see an empty slot in the same instant. Ivo
expects internet gaps Thursday night, Friday morning and Friday afternoon; collection is unaffected, since
the deadlines are absolute and the collectors need no agent.

## 2026-08-12: the standing source hunt, pass 1

First run of the new standing work: five independent lenses proposing sources, a sceptic per lens colliding
each against the closed register and probing whether the data is retrievable in 2026, then one synthesis.
Eleven agents, 21 proposals, **11 survivors and 10 closed**, written into
`docs/approved-sources-list.md` under `## Found, awaiting triage`.

**The sceptics earned their place, which is the part worth recording.** They did not rubber-stamp; they
falsified the prospectors' own claims:

- **Nominet .uk WHOIS returns the CURRENT registration, not the original.** Proved 2 of 2: `0345.co.uk`,
  which the store dates to 1997, reads 28-Dec-2022. So the route loses every dropped and re-registered
  name silently. The failure direction is loss rather than a fabricated in-window year, which is why it is
  still worth banking, and it is the same lapse-and-re-register effect that made registry dates useless for
  the Netcraft question. The service is also end-of-life on 9 February 2027.
- **The UCSF Solr date filter does not filter.** A range query for 1996-2001 returned numFound 3,843,392
  and its top hits read "1995 March 20", so the handler is matching year tokens in text. That number is not
  an in-window count and must not be quoted as one.
- **`ripe_db_lastmodified` had its `artifact_listing` reading disproved outright**, so it can only ever be
  candidate-only.
- **The Domains Project vendor host returns 401** and its landing page now sells the same volume for EUR 100
  to EUR 1,200, so the free GitHub mirror at 1.8 GB is the only route and the 3.235 billion figure is a
  vendor claim, not a measurement.

**The headings had to be normalised before the file would parse, which is worth knowing for pass 2.** The
synthesiser wrote nuance into the heading itself, for example `### ucsf_industry_documents /
dated_directory (corroborated half), link_target (rest)`. `ark.approvals` requires exactly
`### slug / evidence_type`, so nine of eleven parsed and two did not; left alone the queue would have read as
empty and the mirror would have raised nothing. Fixed by moving the nuance to a `- class note:` bullet.
**The synthesis prompt should specify the heading grammar next time.**

**One claim was verified here rather than taken on trust:** 60,468 undated `.uk` names in the pool, which
measures exactly. Everything else in those entries is the hunt's own figure, and each entry says what its
next step is, because none of them is priced yet.

**Next wake should look at RDAP headroom.** `pool_targets_org.txt` holds 221,887 names and the running sweep
is 40 batches of 5,000, so it will consume 200,000 of them and the replacement handover asks for 120
batches. The .org list therefore runs dry well before Sunday, and the sweep stops early when its list is
exhausted. Widening that list to other TLDs is the concrete next piece of engine work, and two of the
triage entries exist precisely to feed it.

## 2026-08-12: I committed through a red gate, and the shell reason it happened

Worth recording as a trap rather than an apology, because it will recur otherwise. The gate was run as:

    uv run ruff check . >/dev/null && uv run pytest -q 2>&1 | tail -2 && git add -A && git commit ...

**A pipeline's exit status is its LAST command's**, so `pytest | tail` exits 0 whether pytest passed or
failed, and `&&` proceeded into the commit. One test was failing at the time and the commit landed anyway.
This is the same shape as the `grep -c "A|B|C"` trap already on record: a construct that reports success by
construction.

The rule that follows: **never put the gate through a pipe.** Either check the exit code explicitly, or run
`set -e` and redirect to `/dev/null` rather than piping to `tail`.

**What was failing, and why it was a real failure rather than a flaky one.**
`test_every_pending_approval_is_named_under_open_in_the_live_files` enforces ADR-005: every `pending` class
must be named under `## OPEN`. My own change had deliberately broken that invariant for triage entries,
which are represented by one collective entry rather than eleven individual ones, so the test was correct to
fail and the fix belonged in the invariant rather than in the code.

It is now `test_every_pending_approval_is_surfaced_in_the_live_files` and asserts the invariant in the two
shapes it has: a priced request must be named individually, and a non-empty triage queue must have its
collective entry. **"Surfaced" rather than "named", because a triage queue with no collective entry is
exactly as invisible as an unnamed priced request**, and the weaker reading would have let the queue go dark
silently.

## 2026-08-12: the queue sorts itself, and the cron was recreated to be provably fresh

Ivo: keep hunting without stopping, sort the queue by potential so he signs off the best first, and make
the cron actually fire every 15 minutes until Sunday night.

**The cron.** The old job was healthy but I recreated it anyway so its state is provable rather than
inferred: created `dd2a6f56` first, verified it, then deleted `a9f57670`, so the schedule was never empty.
Moved off the `*/15` marks to `3,18,33,48` because every job asking for "every 15 minutes" lands on :00 and
:15 and :30 and :45 together. **The real fix is not the job, it is turn length**: a cron cannot fire while a
turn is running, so a three-hour turn silently cancels twelve wakes. The new prompt says so in its own text,
and short turns are now the rule.

**Sorting is a program because the queue grows forever.** `scripts/rank_triage.py`, wired as
`just triage-rank`, rewrites the section in descending `- potential:` order. The judgement stays human: each
entry declares its own score with the drivers written out so it can be argued with, and the tool only
applies it. **An entry with no score is a hard error rather than a silent zero**, because an unscored entry
sorts to the bottom and is then precisely the one nobody ever looks at. `--check` exits 1 on drift, and a
test asserts the live file is in order so a hand edit that breaks it fails the suite.

Two things the tool must not do, both tested: it must not swallow a later `##` section into the sort, since
the same file is the gate `ark ingest` enforces and moving an approved entry would be a correctness bug
rather than a cosmetic one; and equal scores sort by title so a re-run produces no diff.

**Pass 1 scored and ordered.** UCSF industry documents 78 leads, on a per-item date over 28.3M litigation
records that are the least prominence-selected population available. Nominet .uk 72, on the highest English
weight TLD at 0.9813 with 60,468 undated .uk names verified in the pool, capped because it returns the
current registration and closes in February 2027. The three legal corpora sit at 52 to 60. The undated seeds
land at 12 to 30, since without a per-item date they can never date a year whatever their volume.

**Pass 2 is running** with the two defects from pass 1 fixed in its prompt: the heading grammar is stated as
strict and machine-read, and every entry must carry its own `- potential:` score on the same rubric. Its
five lenses are deliberately disjoint from pass 1: abuse and security listings, education and membership
registries, commerce and ISP directories, the highest English-weight national sources, and non-web protocol
registries.

## 2026-08-13: hunt pass 2, and two defects in the harness that produced it

Eleven more survivors from five lenses disjoint from pass 1. The queue now holds **19 entries, 18 open**,
sorted by declared potential.

**The heading fix worked**: 8 of 8 entries parsed strictly first time, against 9 of 11 last pass. Stating the
grammar in the prompt was enough.

**Defect 1: the synthesiser silently dropped three survivors.** The script counted 11 and the markdown
carried 8. Two of the apparent losses were only slug renames; the rest are real. Seen in the transcripts and
never written: `bugtraq_security_list_archive`, `fidonet_nodelist_weekly_archive`,
`freebsd_ports_master_sites`, `irr_changed_attribute_non_ripe`, `ncua_5300_call_report_webaddr`,
`scout_report_dated_back_issues`, `untroubled_spam_archive`. Two of those look genuinely good and should be
re-proposed deliberately: **weekly FidoNet nodelists** and **a dated spam corpus**, both being exhaustive
machine-generated listings of ordinary hosts, which is the shape that has worked here. The fix for pass 3 is
to make the synthesiser account for every survivor by name, and to diff its output against the input count
rather than trusting it.

**Defect 2: the ranker sorted a rejected entry to rank 3.** `educause_edu_whois_activation` scored 78 and
had already been refused, and it sat above eight open sources in a queue whose whole purpose is showing what
still needs a decision. Anything decided now sinks below everything open, whatever it scored, with a test.

**One source was refused by me rather than queued, on terms rather than yield.** The EDUCAUSE .edu WHOIS
banner reads *"The use of electronic processes to harvest information from this server is generally
prohibited except as reasonably necessary to register or modify .edu domain names"*, and a 6,438-name sweep
is unambiguously that shape. That is the standing good-citizen rule applying, not a judgement about evidence
quality, so it did not need Ivo. It is recorded in the queue with the quote and marked overrulable. Its
measured yield was 1 net-new pair per 20 queries in any case, and the sceptic found the reason: a .edu site
registered in year Y was crawled in year Y, so the baseline already holds the activation year, while the
registry has deleted precisely the defunct institutions where a capture was the only surviving record.

**Top of the queue now**: `uk_historic_hansard` 84 and `oireachtas_debates_xml` 77, both parliamentary
transcripts with a per-item date in the URL, the title and the printed citation, on the highest English
weight namespaces; `eric_fulltext_1996_2001` 83 on a measured 52,354 in-window documents each carrying its
own publication year. The Hansard entry carries its own warning, that hostname density measured **zero in a
199-word sample**, so density must be priced before anyone writes a crawler.

## 2026-08-13: the two engines are disjoint, verified rather than assumed

Ivo asked whether the local engine is on the net-new candidate pool and the VPS on the gap-fill pool, and
whether the two are disjoint. Measured rather than asserted, because the VPS list was replaced by hand on
12 August and a hand-shipped file is exactly where this would go wrong.

| | local | VPS |
|---|---|---|
| list | `queue_pool_local.txt` | `queue_shard1.txt`, the gap queue shipped 12 Aug |
| names | 2,513,474 | 466,239 |
| of 20,000 sampled, already holding a year | 5 | 20,000 |

**Set intersection of the two lists: 0.** So the split holds exactly, and each list is the population it
claims: 99.975% of the local sample holds no year, 100% of the VPS sample holds one.

**The 5 exceptions are drift, not leakage.** A queue is a snapshot, and those names were dated by the engine
after the file was written. It costs nothing: a re-query is additive and `ark cdx` skips anything already
journalled.

**The nuance worth writing down: disjointness is a build-time property, not an invariant.** The two files
are disjoint because `build_query_queue.py --population gap|pool` partitions on whether a domain holds any
year, at the moment of the build. As the pool engine dates names they migrate into the gap population, so
the guarantee is refreshed only when the lists are rebuilt. The cycle rebuilds the pool list regularly and
the gap list changes slowly by design, so it self-corrects; but a gap list rebuilt by hand while a stale
pool list is still in flight would overlap, and the overlap would be silent. If either list is ever rebuilt
alone, re-measure the intersection.

## 2026-08-13: hunt pass 3, and the first triage entry that is measured rather than estimated

Seven survivors, ten dropped, and **7 of 7 written**: the synthesis-loss defect from pass 2 is fixed, by
requiring an entry for every survivor and returning the survivor names so the count can be diffed rather
than trusted. Queue now holds **26 entries, 25 open**.

**The top of the queue changed, and on a measurement.** `ncua_5300_call_report_webaddr` scores 88, above
everything found in two previous passes, and unlike the rest it is not an estimate: the agent downloaded
`QCR199906.zip`, 6,625,659 bytes, unzipped 38.8 MB, parsed table FS220D end to end and measured **1,913
net-new pairs worth 1,293.3 equivalent-English from one quarter**, mean TLD weight 0.6845, with 431 of them
pure bracketed gaps where 1998 and 2000 are already held. Every row carries its own `CYCLE_DATE`, so the
hostname and its date sit in the same record with no inference. It is `artifact_listing` and therefore
master-eligible, so it cannot bank until Ivo decides it, which is the gate working rather than a delay.

**Why credit unions are the right shape**, and it is the same argument that made UDRP dockets pay: small US
institutions with no reason to have been linked, printing a contact block into a statutory quarterly return.
That is administrative and exhaustive, not prominence-selected.

**The sceptic disproved three of its own prospector's claims**, which is why the entry is trustworthy: the
field is in `FS220D` and not `FOICU`; whole-window coverage is false, since `QCR199612` carries both columns
with **0 of 11,573 rows populated** against a positive control of 11,479 non-empty phone numbers, so 1996 is
dead and the start quarter is unpinned between 1997-03 and 1999-06; and 16.3% of raw values are malformed
(`WWW.NDCU.ORGFPSFCU`, `HTTP:/WWW.LATFCU.COM`), so the extraction must be **tightened, not widened**, since
nothing downstream catches a fabricated host on a self-dating source that takes no corroboration split.

**A second disproof worth keeping generally.** `govinfo_cbd_bulk`'s prospector cited a machine-readable
listing at `govinfo.gov/bulkdata/json/CBD` as "measured, not recalled". It returns 200 with an HTML body
reading "Govinfo Bulkdata Service Error", byte-identical to the page that already closed `govinfo_fedreg`.
**A 200 carrying an error page is the failure mode this project keeps meeting**, and the rule that catches it
is the one already on record: a search that finds nothing has either proved something or been pointed at the
wrong place, and the two look identical.

**Still outstanding, and unchanged since yesterday:** the RDAP sweep's `.org` target list holds 221,887 names
against a run that will consume 200,000, so it runs dry before Sunday and the sweep stops early. Widening it
to other TLDs is the next engine job.

## 2026-08-13: stop relying on cron, because nothing inside the session can see whether it fired

Ivo has now reported the schedule silently missing twice. The job is registered and correctly configured
both times, and that is precisely the problem: **a cron that is registered and dead is indistinguishable
from one that is registered and working**, because nothing inside the session can observe a firing. The one
diagnosis available, that a long turn swallows wakes, was true on 12 August and does not explain 05:03
today, when the session was idle.

So the mechanism changes. **A background task ending provably re-invokes the agent**, since its completion
notification is delivered whether or not the session happened to be idle at a particular minute. Every turn
now starts the next heartbeat before ending:

    Bash(run_in_background=true): sleep 540; echo "HEARTBEAT: continue the round"

Cron becomes the backup rather than the mechanism, and a second schedule `e0362d85` was added at
`11,26,41,56` so the two offsets give four chances an hour between them. A workflow left running counts as a
heartbeat in its own right, which is why launching the next hunt before ending a turn is both the work and
the wake.

**The general lesson, which is the one worth keeping:** prefer a mechanism whose success you can observe
over one whose failure is silent. This is the same rule that produced the yield check, `just engines`
reporting UNKNOWN rather than "everything is home", and the refusal to quote a rate off a `.part` file.

## 2026-08-13: the RDAP list was about to run dry, and widening it was worth 2.5x

The heartbeat woke this. `pool_targets_org.txt` held 221,887 names against a sweep that consumes 200,000,
so the registry engine would have stopped early well before Sunday and then sat idle.

**Measured headroom by TLD before deciding anything**, since "widen it" is not a plan:

| tld | undated pool | ever asked |
|---|--:|--:|
| com | 917,549 | 1,068,844 |
| net | 413,225 | 440,817 |
| org | 302,128 | 159,460 |
| edu | 216,185 | 70 |
| mil | 186,278 | 1 |
| gov | 185,803 | 11 |
| co.uk | 41,198 | **0** |
| ca | 20,681 | 23,341 |

`.com` and `.net` are effectively exhausted, asked more times than the pool holds. **`.edu` is the largest
untouched pool and is off limits**: EDUCAUSE's banner prohibits exactly this harvesting, which is why that
source was refused yesterday, and the pool figure does not change that. `.mil` and `.gov` are the
fabricated namespaces already on record at 0.000 over 1,372 and 394 answers.

**The find is `.co.uk`: 41,198 names never asked, and `.uk` measures the highest in-window rate of any
namespace at 15.3%**, against `.com` 9.8%, `.ca` 9.4%, `.org` 6.2% and `.net` 5.8%. It also carries the
highest English weight at 0.9813. Rebuilding for `org,uk,co.uk,ca` gives 247,546 targets worth an expected
**17,967 equivalent-English at 0.073 per query**, against 162,438 targets worth 7,193 at 0.044 for `.org`
alone. **2.5x the value and 66% better per query**, and the list head is all `.uk`.

Installed by overwriting the file the sweep already reads, the same in-place pattern used for the CDX
queues: `rdap_pool_sweep.sh` re-reads `LIST` at every batch and `ark rdap` rescans journals to skip settled
domains, so nothing was restarted and the batch in flight was not disturbed. Old list kept as
`pool_targets_org.txt.superseded-20260813`.

**One thing to watch.** The sweep runs `--delay 1.0 --min-delay 1.0`, a floor tuned for PIR, which meters.
`ark rdap` paces each registry with its own governor from the IANA bootstrap, so mixing TLDs is safe, but
every registry now inherits that 1 q/s floor. That is polite rather than optimal, and it is the right
default while nobody is watching. The file name is now wrong for its contents and is left alone
deliberately: renaming it would need the running sweep restarted, which costs more than the confusion.

## 2026-08-13: the fix was committed, the running loop never saw it, and it flooded the review surface

The exact failure the triage collapse was built to prevent happened anyway: `docs/key-decisions.md` held
**25 individual OPEN entries**, one per queued source, beside the collective one. Ivo's two-minute review
surface was a wall of text.

**The code was right and the test was green.** `check_approvals` splits triage entries from priced ones and
mirrors the queue as a single line, `approvals.load` records the section, and the suite passes. What was
wrong was the *running process*: `discover_cycle.py --every 3600` imports its modules once at start, and
the copy doing the mirroring had been started at 14:00 on 12 August by the deadline handover, **before the
change existed**. It carried on executing yesterday's logic every hour, re-adding an entry per source.

**The general trap, which is new to this register and will recur:** a committed fix does not reach a
long-running loop. Green tests and a clean diff prove the code, not the behaviour of a process that started
before it. `CLAUDE.md` now says to restart any background loop after changing what it imports.

**The restart order matters and is why it was done by hand.** The handover waiters block on a bracketed
pattern and start exactly one replacement when the slot empties, so killing the loop while they were armed
risked a waiter launching a second copy into the gap. Waiters were stopped first, then the loop, then the
loop was restarted on the current deadline 1786924800, then the waiters were re-armed. Verified: one
logical cycle process, and a full cycle on the current code leaves **1** OPEN entry where the old one left
26.

**Also this wake:** the VPS gap engine now measures **92.7% of 772 answered** against its own history of
51.6%, which is the 12 August queue repair paying off; and the RDAP swap has not taken effect yet because
the batch in flight started before it, exactly as predicted.

## 2026-08-13: the VPS gap-list alarm was a false positive by design, and it was training the reader to skip

`just cycle` raised "the VPS gap list is stale, rebuild it, scp it and restart the supervisor" on every
pass, at 26.9 hours behind. **That is the list working exactly as designed**: `CLAUDE.md` says gap targets
change slowly and the VPS wants a rare refresh rather than a periodic one. An alarm that fires hourly for a
condition that is correct teaches a reader to skim the judgement section, which is the only part of the
cycle output worth reading closely, so the cost is not the noise itself.

**The fix ties the alarm to the outcome instead of the clock.** Age is now reported as a finding and the
attention item fires only past seven days. The real staleness signal already exists and is better: the
yield check measures each collector against its own history, and it is what caught the VPS at 0.0% for 31
hours on 12 August and now reports 92.7% after the refresh. A gap queue that has genuinely gone stale stops
finding things, and that is observable; a timestamp is not.

The wording also corrects an instruction that was wrong. It said "restart the supervisor there", and the
refresh on 12 August specifically did **not** restart anything: a supervisor re-reads its target list at
every dispatch, so overwriting the file it already reads is the whole job, and restarting would have thrown
away the batch in flight.

**Judgement list after the change: two items**, both real, where it had been four. The remaining ones are
the triage queue, which is Ivo's, and one unread journal, which is the batch the local engine published
minutes ago and the ingest loop has not reached yet.

## 2026-08-13: hunt pass 4, aimed at the shape that scores best

Four survivors, six dropped, 4 of 4 written. Queue now **30 entries, 29 open**. The pass was pointed
deliberately at the statutory-return shape that produced the current leader, a regulator collecting a web
address from thousands of ordinary entities on a dated cycle, and it found a second one.

**`fac_sfsac_historic_1998_2001` enters at 86, second overall.** Federal Audit Clearinghouse Single Audit
returns, every entity spending above the $300,000 threshold: school districts, counties, tribes and
nonprofits. The date and the address sit on the same row, `AUDITEEDATESIGNED` beside `AUDITEEEMAIL`.

**Its sceptic disproved the proposal's central claim, which is the reason to trust the entry.** There is no
website column anywhere in `ELECAUDITHEADER`; it is an e-mail source, so the deliverable is a mail domain,
the same shape as the NCUA field already queued. It also corrected the dating: `AUDITYEAR` is the wrong
column, because a return for audit year 1998 is signed months after fiscal year end, so folder-dating claims
a year **before** the address was attested, which is the dangerous direction. Signature dates across five
folders give 1998-2001, not the four the proposal named.

**The strongest argument in the entry is a measurement of absence.** The store holds 18,278 distinct
in-window `.us` domains against 3,239,423 `.com`, so the RFC 1480 locality namespace where every school
district and county lived is **0.3% of in-window domains**. Nobody linked to a school district site, which
is precisely why UDRP dockets and the NCUA returns pay.

**And it carries its own kill condition, from the dictionary's own words:** "This field was not populated
before 2001" is documented for a different column, which is exactly how `QCR199612` died with both columns
present and 0 of 11,573 rows populated. So pricing starts with the populated rate against a positive
control, then the share of addresses on an own domain rather than `aol.com`.

`sec_form_adv_part1_2000_2001` enters at 58 with the in-window slice corrected from fifteen months to
**2001 alone**, on the Federal Register release text, and with the honest warning that if the zip holds one
current-state row per adviser rather than one per filing, the source is worth nothing.

## 2026-08-13: exactly one heartbeat, and pass 5 aimed at a measured gap

**The heartbeat needed a rule within an hour of being adopted.** Relaunching one at the top of a turn and
again at the bottom left two in flight, which means two wakes, two agents doing the same bounded work and
two sets of commits racing. Fixed by stopping all and starting one, and `CLAUDE.md` now says to check
`pgrep -f 'slee[p] 540' | wc -l` first. The failure is the same family as starting a second collector, and
the same discipline applies: count before you launch.

**Pass 5 is pointed at a measurement rather than a theme.** Four passes have produced a usable model of
what pays here, and it is now written into the hunt's own prompt: the winning shape is a statutory return
where a regulator collects a contact address from thousands of ordinary entities on a dated cycle, and the
losing shape is any curated list of notable sites. Two of the four highest-scoring entries in the queue are
that shape.

The sharpest input is the `.us` measurement from pass 4: **18,278 in-window `.us` domains against 3,239,423
`.com`**, so the RFC 1480 locality namespace where every US school district, county, library and
municipality lived is **0.3% of in-window domains**. That is a hole rather than a hypothesis, so one whole
lens is aimed at it: NCES school directories, the IMLS public libraries survey, Census of Governments,
E-rate applications filed annually from 1998.

Two lessons from earlier passes are now schema fields rather than prose, so a sceptic cannot skip them:
`row_shape`, per-filing or per-entity current state, which is the dated-dataset fallacy that would make a
source worthless; and `positive_control`, the column to test population against, which is how the 1996
credit union file died with both columns present and zero rows filled.

## 2026-08-13: the wider RDAP list is live, and the first bytes agree with the prediction

The batch that started 03:57 UTC is the first drawn from the widened list, and its first 200 answers are
**all `.uk`**, which is what the ranking intended: `.uk` carries both the highest measured in-window rate,
15.3%, and the highest English weight, 0.9813.

**In-window rate on those first 200: 11.0%.** That is a partial read of a `.part` and is quoted as one, so
it is a sanity check rather than a measurement; the batch is 5,000 queries and the honest number arrives
when it publishes. What it does establish is direction: the previous `.org` batch was running at 4.3%
in-window over 4,086 answers.

Rough value per query, and labelled ESTIMATE: `.uk` at its historical 15.3% times 0.9813 is about 0.150
equivalent-English per answer, against `.org` at 6.2% times roughly 0.6, about 0.037. The builder's
whole-list figure of 0.073 per query sits between them because the list is mixed, and the head being all
`.uk` is what front-loads the value.

**The swap cost nothing.** The file was overwritten in place, the batch in flight at the time finished on
the old list undisturbed, and the sweep picked the new one up at its next dispatch, exactly as the CDX
queues behave. No process was restarted at any point.

## 2026-08-13 06:10: the round crosses 1.6%, and the gate is green after a night of ingestion

Nine invariants **ALL PASS** after `ark export`, run in that order because one invariant reads the exported
annual files. The gate had not run since 02:08 and the store has taken a night of collector output since.

| | at 16:05 on 12 Aug, when the interim figures were sent | now |
|---|--:|--:|
| pairs | 159,787 | **170,186** |
| net-new domains | 123,893 | **129,851** |
| equivalent-English | 91,908.4230 | **101,139.3788** |
| growth | 1.476112% | **1.6244%** |

**Plus 9,231 equivalent-English in about fourteen hours**, and the interim report Ivo sent is understated by
that much, which is the safe direction and was stated as such in its own notes.

Mean weight per pair has risen from 0.5541 to 0.5943, which is the `.uk` work showing up: the VPS gap engine
running at 92.7% on the rebuilt queue, and the RDAP sweep now leading with `.uk` at 0.9813 rather than
`.org` at 0.6. The discovery half remains dominant at 87,475.5875 of the 101,139.3788, or 86.5%.

## 2026-08-13: the round report generator would have failed on Sunday, and it failed today instead

Preparing Sunday's deliverable early, on the principle that a generator is best broken on a Thursday.
`fill_report.py --check` crashed outright:

    _duckdb.IOException: Could not set lock on file "data/ark.duckdb": Conflicting lock is held

**DuckDB's single writer excludes readers too**, so anything opening the store read-only meets the lock
every few minutes while the ingest loop banks journals. `connect_patiently` has existed for a while and
covers the commands that also write a metrics row, `ark check` and `ark stats`. What had happened since is
the worst possible split: `round_figures.py` and `build_round_state.py` each hand-wrote their own retry
loop, while `fill_report.py` (three call sites) and `report_figures.py` (one) had none at all.

**So the one command that had no patience was the round report generator**, which by definition is only ever
run at the end of a round, when both collectors and the ingest loop are at their busiest. It would have
failed on Sunday evening, in front of the deadline, for a reason nobody would have diagnosed quickly.

Fixed with a shared `connect_read_only_patiently` in `ark.db` rather than a fifth hand-written loop, with
two tests: it retries the lock, and it re-raises anything that is not the lock immediately, because
patience applied to a corrupt file turns a real fault into a fifteen-minute silence.

**The template itself came out clean**, which was the other thing worth checking. Five hardcoded figures in
`report.template.md` are all fixed historical measurements about named sources, 4,736 Usenet relay domains,
94.7% and 92.2% overlaps, 8.7% for the largest registry, and not round totals that would drift. The 13
placeholder tokens cover everything that moves, and `--check` now confirms it would fill cleanly.

## 2026-08-13: hunt pass 5, and the sceptic that downgraded its own find

Four survivors, five dropped, 4 of 4 written. Queue: **34 entries, 33 open**. The pass was aimed at the
measured `.us` locality gap and it hit it.

**`nces_imls_pls_web_addr_1998_2001` enters at 82, and it is the best-evidenced entry in the queue**, because
the agent did not estimate: it downloaded `pupldf99_csv.zip`, parsed 17,057 outlet rows, canonicalised every
address through this project's own `ark.canonical.to_registrable`, and differenced against the live store.
**Post-split: 348 net-new pairs, 280.1 equivalent-English, mean weight 0.805**, composed of 135 `lib.XX.us`,
127 `.org`, 42 `.com`, 28 city and county `.us`, 11 `k12.XX.us`. That is the locality namespace the store is
thinnest on, arriving by name.

**The finding that matters most is that the sceptic downgraded its own source.** The prospector filed it as
`artifact_listing`, self-dating and taking no corroboration split, which is the reading worth four times
more. The sceptic measured why that is wrong: of the 122 domains never held at any year, **48, or 39.3%, sit
at edit distance 1 from a domain the store already holds** (`crytstallakelibrary.org`,
`nrewburghlibrary.org`, `punamco.lib.oh.us`, `soffolk.lib.ny.us`). `WEB_ADDR` is keyed by state library
staff, so it is typed, and admitting it unsplit would mint year claims for domains that never existed.
**Typos are by construction the never-held names, so the split removes exactly that population and almost
nothing else.** This is the Netcraft lesson applied by an agent to its own find, which is what the class
decision being a human's is supposed to protect against and here did not need to.

**Two schema fields added yesterday did real work.** `positive_control`: `PHONE` on the same row is
populated 16,912 of 17,057, or 99.15%, against `WEB_ADDR` at 26.5%, which proves the sparsity is genuine
1999 web adoption and not an unpopulated column, the exact test that killed `QCR199612`. `row_shape`: the
26.5% rate is itself the argument against the dated-dataset fallacy, since a backfilled current-state
address in a 2013 repackaging would be near-universally filled.

It also carries the one thing not yet observed as its stated kill condition: if `WEB_ADDR` does not change
between FY1998 and FY1999 for the same `FSCSKEY`, every year claim is void. That diff is free once the
second file is on disk and is the first test to run.

## 2026-08-13: pass 6 launched, and the hunt prompt now carries what five passes learned

Pass 6 is running on three lenses not yet tried: research funding award records (CORDIS covers FP4 and FP5
across the whole window, NSF and NIH reach back before 1996), clinical and health registries
(ClinicalTrials.gov opened in 2000 with sponsor and contact fields), and multilateral participant
directories.

**The prompt is now the accumulated model rather than a brief**, which is the part worth keeping. It states
the winning shape and the losing shape with the measurements behind each, the `.us` gap at 0.3%, and three
traps as hard rules: a column that exists is not a column that is populated, one current-state row per
entity does not date an address, and a human-keyed field is the typed class however much the unsplit
reading is worth. `who_keyed_it` joins `row_shape` and `positive_control` as a required schema field, so a
sceptic cannot return without answering it. Each of those three came from a specific failure: the 1996
credit union file, the FDIC current-state trap, and the library survey typos.

Sceptics are also told they may measure against the store read-only, since that is precisely what made the
library survey entry credible: it was differenced against the live database rather than estimated.

**A note on the tooling.** The first launch failed to parse because the script is a template literal and I
put backticks inside it. Rewritten with joined string arrays. Worth remembering: workflow scripts are plain
JavaScript in a template context, so markdown backticks in a prompt are a syntax error rather than
formatting.

## 2026-08-13: dress-rehearsing Sunday's delivery, and a fix that turned out to protect it

Sunday's deliverable is not a document, it is a packaged delivery archive, and `just package` has not been
run this round. Started a full rehearsal in the background rather than finding its faults on Sunday
evening.

**This morning's lock fix turns out to have been directly load-bearing for it.** `package_delivery.sh` line
100 calls `fill_report.py` and refuses to package unless the output contains "filled cleanly". Until three
hours ago that script had no patience for the write lock, so **the packaging run would have crashed on a
DuckDB lock message** whenever the ingest loop happened to be banking a journal, which it does every few
minutes. The fix was made for the report generator and the packaging path inherited it.

The other preconditions look sound from reading the script: it refuses a dirty tree, excludes
`submissions/` from its own inputs since that is its output, and regenerates the report rather than
trusting a stale copy. The tree is clean because every wake commits and the collectors write only to
git-ignored paths.

**What the rehearsal is actually testing** is the part no reading can settle: whether the export, the
provenance bundle, the checksums and `verify_delivery.sh` still agree with each other after a week in which
the store grew by 170,186 pairs and four engines were repaired. Result at the next wake.

## 2026-08-13: the delivery rehearsal refused, which is exactly what it was for

`package_delivery.sh` stopped at its own guard:

    refusing to package: output/ holds 170186 net-new pairs, the store holds 170787

**The guard is right and must not be weakened.** It exists so a delivery cannot ship annual files that
disagree with the store. What the rehearsal exposed is a procedure problem hiding behind it: the comparison
is `[ "$SHIPPED" != "$STORED" ]`, exact equality, and **the store moves every time the ingest loop banks a
journal**, which is every few minutes. `ark export` itself takes minutes. So a hand-run
`ark export && just package` races the loop and refuses, and it would have refused repeatedly on Sunday
evening in front of the deadline, looking like a broken packager rather than a race.

**The fix is a sequence, not a looser guard**, and the insight that makes it cheap is that only *ingestion*
moves the store. Collectors writing journals do not, so they need not stop:

    just ship    # pause maintain.sh, wait out any ark ingest in flight, export, ark check, package, verify

It prints the command to restart the ingest loop when it is done. Nothing is lost by pausing it, because
journals are ledgered by content hash and re-offering an ingested one is skipped in milliseconds.

**Two findings from one rehearsal, both invisible from reading the code.** This one, and the confirmation
that this morning's `connect_read_only_patiently` fix was load-bearing here too: packaging calls
`fill_report.py` and refuses unless it prints "filled cleanly", so before that fix the packaging run would
have crashed on the write lock as well. Two independent Sunday-evening failures, found on a Thursday
morning, for the cost of one background command.

## 2026-08-13: the .uk RDAP batch is answering everything, and the widening looks like roughly 3.7x

Partial read of the in-flight batch at 40% through, labelled as one and not quoted as a rate: 2,000
records, **2,000 answered**, 284 in-window. Two things stand out and neither needs the batch to finish.

**Nominet answers every query.** A 100% answer rate against `.org`, where a share of queries return nothing
usable, which matters because an unanswered query costs the same as an answered one. The triage entry for
`nominet_whois_port43` carries a warning that Nominet's RDAP refused this project three times in fourteen
queries at 0.5 q/s; at the sweep's 1 q/s it is not refusing at all, which is worth knowing before that
entry is decided.

**The in-window share is tracking the historical figure.** 14.2% so far against the 15.3% measured across
all previous `.uk` answers, so the ranking was not fitting noise.

Rough per-batch value, ESTIMATE and only that: 5,000 queries at 14.2% times the 0.9813 weight is about 697
equivalent-English, against `.org` at 6.2% times roughly 0.6, about 186. Call it **3.7x for the same number
of requests**, which is what the list rebuild bought. The honest number arrives when the batch publishes.

The batch is slower than `.org` was, 40% in about an hour against 5,000 in 83 minutes, so Nominet is pacing
harder. That is the adaptive governor doing its job and costs nothing worth chasing.

## 2026-08-13: the shipping rehearsal, three failures deep, and the one that mattered

Ran `just ship` twice. Everything up to packaging passed both times: export wrote all six annual files and
a 693 MB provenance bundle, and **all nine invariants passed** over 9,902,673 domain-year rows.

**Failure 3, and the dangerous one: a failed ship left ingestion dead.** The recipe pauses `maintain.sh`
first, and `package_delivery.sh` then refused because `docs/report.md` was stale, so the run exited with
the ingest loop stopped. It was noticed only because somebody was watching the output, and on the evening a
round ships nobody is. **A step that stops a running system must restore it on every exit path, not on the
happy one.** The recipe now sets an EXIT trap before it stops anything, and the second run proved it: the
packaging refusal was followed by "== ingest loop restarted ==".

**Failure 4, which is procedure rather than code.** The second run refused because the `justfile` itself
was modified: the guard requires a clean tree, since `source/` in the delivery comes from `git archive HEAD`
and a dirty tree would ship code that does not match the results. Correct, and worth stating in the README
next to `just ship`: **commit before shipping**, because the recipe cannot commit on your behalf what it
does not understand.

**What the report guard taught.** `package_delivery.sh` regenerates the report and refuses if it changed, so
a human reviews the diff. That is right for a hand-run package and wrong inside a sequence, where it turns
a one-command ship into a two-command one at the worst moment. `ship` now regenerates the report itself,
prints the diff stat and commits it, which leaves exactly the same reviewable record in git history. The
diff is by construction nothing but regenerated figures: 14 numbers, 14 replacements.

**Four Sunday-evening failures found on a Thursday morning**, for the cost of three background commands: the
lock crash in the report generator, the export race against the ingest loop, a failure path that killed
ingestion, and a dirty-tree refusal. None was visible from reading the code.

## 2026-08-13: failure 5, and the reason quiescing the ingest loop is not enough

The third rehearsal died at `ark export` with a raw DuckDB traceback:

    IOException: Could not set lock on file "data/ark.duckdb": Conflicting lock is held ... (PID 98453)

**And the ingest loop was paused at the time**, which is the interesting part. The assumption behind
`ship` was that `maintain.sh` is the only thing that touches the store. It is the only thing that *writes*,
and that is not the same condition: **DuckDB blocks a write connection against any other process holding
the file, including a reader.** This project always has readers, since the discovery cycle measures the
store every cycle and every reporting command opens it. So quiescing the writer removes the writer and
leaves the block.

`ark export` opened with the plain writable `connect()`, so it crashed instead of queueing. Under a
deadline that reads as a broken exporter rather than a busy database, which is exactly the confusion
`connect_patiently` was introduced to prevent for `ark check` and `ark stats` weeks ago. Export never got
the same treatment because nothing had ever run it against a live loop.

Fixed by making `export` patient, and `gaps` with it, since that one also runs unattended from the engines.
The three left impatient are deliberate: `init`, the baseline load and `rebuild` are one-off human commands
where crashing loudly is correct and patience would mask a real conflict.

**The generalisation worth keeping: "stop the writer" is not "quiesce the store".** The store is quiet only
when nothing holds the file at all, and the cheaper answer is not to stop more processes but to make the
reader patient, since a shipping step that waits thirty seconds costs nothing and a shipping step that
crashes costs the evening.

## 2026-08-13: failure 6, and the delivery that was valid all along

The fourth rehearsal **packaged successfully**: a 1.4 GB archive, 1,062 files, sha256 recorded, alongside
MANIFEST, report and sources in `submissions/phase-5/`. Then verification failed with
`additions/1996.txt is missing`, on a delivery whose `additions/` holds all six years.

**The delivery was fine and the check was pointed at the wrong place.** `verify_delivery.sh` does
`cd "${1:-$(dirname "$0")}"`, so with no argument it verifies **its own directory**. That default is right
when the script ships inside a delivery, which is its main job, and wrong when it is run from this
repository, where it lands in `scripts/`. The justfile's `verify-delivery` recipe passes the path
explicitly and my `ship` recipe did not. Fixed by passing it.

Run by hand against the real path, the same delivery reports: **checksums PASS, 1,061 files match
SHA256SUMS; annual additions PASS, 170,787 pairs; evidence for every addition PASS, all 170,787 traced to
an observation.** So the artefact was correct at the first successful packaging.

**This is the failure mode this project keeps meeting in new clothes**, and it is already on the register:
a search that finds nothing has either proved something or been pointed at the wrong place, and the two
look identical. Here it was a checker rather than a search, and it took a valid 1.4 GB delivery and called
it broken.

**On the rehearsal's own output.** `submissions/phase-5/` is left untracked on purpose: those artefacts get
rebuilt on Sunday, and committing a rehearsal's MANIFEST would put it in history as though it were the
submission. The tarball cannot reach git in any case, ignored at `.gitignore:49`, which was verified rather
than assumed before anything was staged, since this project has swept a gigabyte into history once already.

## 2026-08-13: `just ship` is green end to end, four days early

The fifth rehearsal ran the whole sequence clean: pause the ingest loop, export, nine invariants,
regenerate and commit the report, package, verify, restart the loop.

    checksums                 PASS  1061 files match SHA256SUMS
    annual additions          PASS  170,787 pairs (1996:5,858 1997:43,218 1998:14,983
                                    1999:26,931 2000:43,246 2001:36,551)
    evidence for every addition PASS  all 170,787 traced to an observation
    All checks passed.
    == ingest loop restarted ==

**Six failures, none of them visible from reading the code**, and the reason to write them down together is
that they are one family. Every one was a component that worked correctly in isolation and wrongly in
composition:

1. `fill_report.py` had no lock patience, and packaging calls it.
2. `output/` goes stale against the store within minutes, and the guard demands exact equality.
3. A failed ship left the ingest loop dead, because the recipe stopped it before a step that could fail.
4. Packaging refuses a dirty tree, correctly, and a sequence must therefore be run from a clean one.
5. `ark export` crashed on the lock even with the writer paused, because a reader blocks a writer too.
6. `verify_delivery.sh` with no argument verifies its own directory, so it called a valid delivery broken.

**The lesson is about rehearsal, not about any of the six.** Each component had been exercised; the
*sequence* never had, and a round is shipped by the sequence. The cost of finding them was five background
commands on a Thursday morning. The cost of finding them on Sunday evening would have been the deadline,
one refusal at a time, each looking like a different problem.

The artefact itself was sound throughout, which is worth saying plainly: the first successful packaging
produced a delivery that verified perfectly once the checker was aimed at it.

## 2026-08-13: hunt pass 6, and a rubric that rewarded a dead source

Six survivors, seven dropped, 6 of 6 written. Queue: **40 entries, 38 open**.

**One entry was closed by me rather than queued, on a measurement its own sceptic made.**
`nlm_medline_affiliation_email_1996_2001` mines the email at the end of a PubMed affiliation, dated by the
citation's own PubDate. The sceptic pulled a live sample of 581 citations and measured **0 net-new pairs
after the corroboration split**: 108 emails, 90 distinct domains, 100 pairs, 97 already held, and all 3
remaining held in no year, so all 3 fail the split. The positive control passed first, affiliation
populated on 369 of 475 in-window citations, so the zero is the corpus and not the parser. Of 90 distinct
domains sampled, 75 already hold all six years.

That is a close on measurement, which is the agent's to make, and it needed making because **the rubric
scored it 66 and put it second in Ivo's queue.** The rubric gives +40 for a per-item date existing at all,
and MEDLINE has an excellent one; what it has no credit for is that the yield was measured at zero. A
scoring scheme that ranks a dead source above live ones spends the reviewer's attention on nothing, and the
attention is the scarce thing here.

**Fix for pass 7: a measured yield outranks the rubric.** If an agent has actually measured net-new against
the store, the score is that measurement's verdict and the component scores do not apply. Absence of a
measurement stays an estimate and keeps the rubric.

Also worth keeping: MEDLINE's terms are unusually green, bulk download is the documented channel and there
is no prohibition on automated retrieval, so this was closed on yield alone. And email presence rises
steeply across the window, 0 of 32 affiliations in 1996 against 38% in 2001, so it could not have served
1996, which is the thinnest and most valuable year.

The pass leader, `usac_erate_form471_contact_email_1998_2001` at 84, is E-rate applications from US school
districts and libraries, exactly the 0.3% locality namespace. It is gated: the portal serves only the last
ten years and older records need a request to `opendata@usac.org`. Its positive control is already
measured on the published years, phone 100% against billed-entity email 46.2%.

## 2026-08-13: turning queued sources into pool growth without waiting for a decision

The triage queue holds 38 open sources and none of them can date a year until Ivo classifies it. **But the
names in them can enter the candidate pool today**, because candidate-only evidence needs no approval, and
the engines then date those names on their own capture evidence, which needs no approval either. That is
exactly what happened with Netcraft: refused as master, banked as 13,078 candidates, and 127 of them dated
from their own captures within a day.

So a harvest is running over the two best-evidenced queued sources, taking names only:

- **NCUA call reports.** Both the website and the e-mail column, since a mail domain is as good a candidate
  as a web one. 1996 is already known dead, both columns present and zero rows populated, so the fetch
  starts at 1999.
- **The IMLS library survey.** FY1999 measured 1,489 distinct registrable domains from 4,519 populated
  rows, and its value is the locality namespace, `lib.XX.us` and `k12.XX.us` and city or county `.us`,
  which is 0.3% of in-window domains.

**The harvest is constrained to this project's own canonicaliser**, `ark.canonical.to_registrable`, rather
than a hand-rolled regex, and told to report what it rejects rather than repair it. 16.3% of the NCUA values
are malformed and the rule on a self-dating source is to tighten extraction, not widen it; here it matters
less, since a bad candidate name simply never earns a capture, but the count is worth having.

**Why this is the right shape of work while waiting.** It needs no decision from Ivo, it costs a handful of
static government downloads, and it feeds the engine that is already running rather than proposing a new
one. The queue keeps growing for him; the pool grows meanwhile.

## 2026-08-13: 2,350 candidate names banked from two queued sources, with no decision needed

The harvest ran and the names are in the pool. **Neither source can date a year yet, and neither had to.**

| | rows read | raw values | domains | already held | **new candidates** |
|---|--:|--:|--:|--:|--:|
| NCUA call reports, 1999/2000/2001 | 31,839 | 26,165 | 7,091 | 4,957 | **2,134** |
| IMLS library survey, FY1997-FY2001 | 85,284 | 17,346 | 1,901 | 1,685 | **216** |

**2,350 new candidates**, seeded in under four seconds each, and every one now queued for the CDX engine
which will date whatever it can on its own capture evidence. The library names are the locality namespace
this project is thinnest on: `aacpl.lib.md.us`, `acadia.lib.la.us`, `ada.lib.id.us`.

**The agent disproved a figure from its own briefing, which is the habit worth having.** I passed it "16.3%
of raw values are malformed" from the pass-3 entry. Measured across three years the reject rate is **6.7%**,
and 11.4% for 1999 alone; the 17.4% figure belongs to one column in one year. The triage entry will be
corrected. Reject reasons were reported rather than repaired: 849 invalid hostname syntax, 733 no known
public suffix, 151 bare public suffix, and the dominant cause is **a hard 25-character truncation in the
source data**, which takes the TLD with it and is unrecoverable rather than fixable.

**Two facts worth keeping about the sources themselves.** The NCUA e-mail column is dirtier in the useful
sense and cleaner in the parsing sense: 4.3% rejected against 10.4% for the website column, and
`to_registrable` already strips userinfo at the last `@`, so `XCU@IX.NETCOM.COM` reduces natively. And its
head is free-mail, `aol.com` 2,355 times, so the value is entirely in the 2,291 names that occur exactly
once. For IMLS, `to_registrable` was verified **not** to collapse four-label `.us`: `detroit.lib.mi.us` and
`pen.k12.va.us` survive intact, which is the whole reason that source is interesting.

The IMLS agent also reports that roughly half its 461 drops are recoverable scheme typos
(`http//:metronet.lib.mi.us`, `www/flint.lib.mi.us`) and estimates 150 to 250 further names from a
normaliser. It correctly did not write one, since that is a change to shared code rather than a harvest.
Worth doing deliberately later; on a candidate-only route the risk is low, because a name that was never
real simply never earns a capture.

## 2026-08-13: the entry was right and my briefing was wrong

Correcting my own correction. I said the NCUA triage entry's 16.3% malformed figure was disproved by the
harvest. It was not. The entry says **406 of 2,484**, which is explicitly the website column in 1999, and
the harvester measured 433 of 2,484 for exactly that slice, a difference of canonicaliser strictness rather
than of fact. **The generalisation to a corpus-wide rate was mine, in the brief I wrote for the harvester**,
and the harvester was right to flag that its measurement did not reproduce it.

So the entry is extended rather than corrected, with the wider measurement beside the narrower one: 6.7%
corpus-wide across three years, e-mail 4.3% against website 10.4%, 7,091 distinct domains, 2,134 now in the
pool.

Worth stating as a habit rather than an incident: **when a measurement contradicts a recorded figure, check
the scope of the recorded figure before rewriting it.** A per-column, per-year number and a corpus-wide
number are different claims, and the register is more often precise than wrong. Rewriting a correct entry
to match a broader measurement would have destroyed the more useful of the two figures, since the website
column in 1999 is precisely what an extractor would be pointed at first.

The seeded names carry their own source labels, `ncua_call_report_candidates` and
`imls_library_survey_candidates`, so the queue builder treats each as its own population with no measured
hit rate yet and falls back accordingly. One batch of each measures them, and the yield check reports it
against their own history from then on.

## 2026-08-13: harvesting the next two statutory returns, and warning the agent about the trap first

Second harvest running, on the two queued sources of the same proven shape:

- **FAC Single Audit returns**, scored 86, aimed squarely at the `.us` locality gap: school districts,
  counties, tribes and nonprofits above the $300,000 threshold. Its column is `AUDITEEEMAIL`, and the
  brief carries the disproof a previous agent already made, that there is **no website column at all** in
  `ELECAUDITHEADER`, so the e-mail is the deliverable and nobody needs to rediscover that.
- **FFIEC bank call reports**, scored 60, the same shape as the NCUA return that gave 7,091 domains.

**The FFIEC brief carries a warning rather than a task**, which is the part worth recording. An FDIC
institution table is one **current-state** row per bank with the website as it is today, and a bank site
registered in 2015 was never a 1996-2001 domain. That is the dated-dataset fallacy, and it is the easiest
thing in this batch to get wrong, because such a table is far easier to find than a per-filing extract. The
agent is told to prefer a per-filing in-window quarter, to say which it used, and if only current-state
data exists to write what it finds and **mark it as current-state in the notes** rather than quietly mixing
it in.

Also told, in as many words, that a negative result reported honestly is worth more than a padded one, and
to write an empty file if the column is not there. The previous harvest earned that trust by disproving a
figure I had given it.

## 2026-08-13: the harvested names reached the queue, and where they landed matters more than that they did

Verified the loop closes rather than assuming it. The queue was rebuilt at 07:37, six minutes after the
seeding, and **2,451 harvested names are in it**: 2,224 NCUA and 227 IMLS, more than the 2,350 "new
candidates" because some already-known-but-undated names were promoted too.

**Membership is not the useful question in a 2.5M-line ranked queue. Position is.**

| | queued | best rank | median rank | in the first 20,000 |
|---|--:|--:|--:|--:|
| NCUA | 2,224 | 1,972 | 575,662 | **873** |
| IMLS | 227 | 2,014 | 576,671 | **30** |

The first 20,000 is roughly a day of engine work, so **about 900 of the 2,451 will actually be asked before
Sunday** and the rest sit in the tail. That is not a fault, and the reason is worth writing down: these
names arrived under brand new source labels with **no measured hit rate**, so `build_query_queue.py` scores
them on a fallback, exactly as C-18 describes. A source with no evidence is neither promoted nor punished.

**The system corrects this itself and that is the design, not a hope.** The 903 names in the head get
queried within a day, which measures a real `(source, TLD)` hit rate for `ncua_call_report_candidates` and
`imls_library_survey_candidates`; the next queue rebuild then ranks the remaining 1,548 on that measurement
rather than on a prior. If the shape pays as the source register suggests it should, they rise; if it does
not, they are correctly buried, and either outcome is information the queue did not have this morning.

**So nothing is done about it deliberately.** The alternative, hand-promoting the names because the shape
looks good, is precisely the reasoning that put 2,675 `.mil` names at the head of the queue on 11 August and
cost 1,200 archive queries for zero captures. A prior dressed as a measurement is the failure this project
has paid for most often.

## 2026-08-13 08:10: the judgement list is down to one item, and it is Ivo's

Cleanest cycle of the round. Every mechanical check clean, and the section that names what no program can
decide holds **exactly one line**: the 38 sources awaiting triage. Nothing else needs a human.

    cdx_pool  43.4% of 1,797 answered, against 45.1% of 47,024 before that
    cdx_q1    91.6% of 790 answered, against 52.3% of 30,512 before that
    rdap      35.1% of 784 answered, against 10.2% of 1,692,022 before that

**The VPS number is the one to look at.** It has held above 91% for hours against a lifetime history of
52.3%, which is the 12 August queue repair still paying. Its history figure will keep climbing toward the
new rate as the old zero-yield stretch is diluted, and when the two converge the repair is fully absorbed.

Three items that used to appear here are gone for good reasons rather than by being ignored: the VPS gap
list alarm now fires on yield rather than the clock, the individual approval entries collapsed into one
count, and the re-probe no longer re-raises a lead its own verdict already answered.

The `.uk` RDAP batch is still in flight after four hours, which is Nominet pacing rather than a stall: the
partial read showed every query answered. It publishes when it publishes, and the honest per-batch number
comes then rather than from another partial read.

## 2026-08-13: FAC pays, FFIEC is dead, and the agent was right to withhold something

Second harvest, two opposite outcomes, both useful.

**FAC Single Audit: 8,598 domains, 1,665 new, seeded.** All four year-zips fetched and **verified against
their published SHA1s**, which nobody asked for and is exactly right. Its positive control is the cleanest
yet: `AUDITEEPHONE` populated on **139,978 of 139,978 rows, 100.00%**, against `AUDITEEEMAIL` at 15.64%, so
the sparsity is a property of 1998-2001 filings and not a parse failure. The rate climbs 11.64%, 13.94%,
16.34%, 19.86% across the four years, which is e-mail adoption in school districts and counties showing up
in a statutory return.

**The TLD mix is the point**: `.org` 3,168, **`.us` 1,845**, `.com` 1,497, `.net` 1,077, `.edu` 930, and
within `.us` the shapes are `k12.ca.us` 73, `k12.ga.us` 69, `k12.pa.us` 57. **298 of the new names are
`.us`**, about 1.6% on top of the 18,278 in-window `.us` domains the store holds. It also re-disproved the
website claim independently: no column in any of the four years contains WEB, URL, SITE, HTTP, WWW or
HOMEPAGE.

**And it withheld something rather than widening its own brief.** The same table carries `CPAEMAIL`, the
audit firm's address, 4,848 domains of which 2,071 were new, **a larger novelty pool than the column it was
asked for**. It reported it, saved it, and did not put it in the deliverable, on the grounds that widening
the definition of an output file without being asked was not its call. That is the right instinct and it
should be said out loud. I took the decision it left open and seeded them: **2,068 more candidates**, an
audit firm printing its address on a 1998-2001 filing is exactly the same kind of evidence as the auditee
doing so.

**FFIEC is closed on measurement, and the shape of the negative is worth keeping.** The field exists: the
Federal Reserve MDRM dictionary confirms TEXT4087 runs from 1999-03-31, so banks did report a website for
three of the six window years. **The values were never published.** The CDR bulk distribution offers no
period before 2001-03-31, and across all four 2001 quarters actually downloaded and parsed, 35,094 filing
rows, TEXT4087 is populated on **0 rows**, as are name, city, state, zip, e-mail, contact, phone and fax.
What remains is a 2005 quarter and an FDIC current-state table, and a bank website recorded in 2005 was
very likely never a 1996-2001 domain. Its 8,588 harvested domains were deliberately **not** seeded.

**"The reporting item is real; the publication is not"** is a distinction this register did not have, and it
is a cheaper kill than fetching: check whether the bulk file carries the column's values before believing
that a documented field means available data.

## 2026-08-13: I committed through a red gate again, by a different route

The FFIEC harvester wrote five working scripts into `scripts/`, and `git add -A` swept them into the
commit. Two failed line-length lint, so **the tree was committed red**, for the second time this round and
by a different mechanism than the first: last time a pipe hid pytest's exit status, this time the failure
was visible and the sequence continued past it anyway.

Fixed by moving all five into `legacy/probes/ffiec-2026-08-13/`, which `pyproject.toml` already excludes
from lint, and which is where this project keeps spent probes for their negative results. They belong
there rather than in `scripts/`: `scripts/` holds tools that are documented in the README and run again,
and these are one-off working files whose value is entirely the finding they produced, that the CDR
publishes TEXT4087 empty through 2004 and as the redaction marker CONF through 2005-09-30.

**The rule that keeps failing is `git add -A` after a subagent has been running**, and it is the same rule
that once swept a 1.3 GB baseline copy into history. An agent working in the repository leaves files
behind, and staging everything is a bet that all of them belong. Stage the paths you changed, or look at
`git status` before staging, which takes one command and would have caught this.

Gate is green again: ruff, format, 423 tests.

## 2026-08-13: the gate is now enforced rather than remembered

Two red commits in one round, by two different routes, is a rule that does not work. So there is a
pre-commit hook: `hooks/pre-commit`, installed with `just hooks`, which runs ruff, the format check and the
tests and refuses the commit if any fail. Proved by trying to commit a deliberately misformatted file and
being refused.

**Deliberately the CODE gate only.** `ark check` validates the data over a store that takes one writer and
is busy every few minutes, so putting it in a hook would make every commit wait on the ingest loop, and a
hook that makes committing slow gets disabled within a day. The data invariants already run in `just ship`
and in the cron checklist, which is where they belong.

**Hooks live in `hooks/` and are installed by a recipe**, because `.git/hooks` is not versioned, so a hook
that only exists in one clone is not a project rule. `--no-verify` still works and that is correct: it
leaves a visible choice in the shell history rather than a silent failure.

**The two routes are both recorded in `CLAUDE.md` next to the rule they broke**, since a trap belongs where
the reader already is: never put the gate through a pipe, because a pipeline exits with its last command's
status; and never `git add -A` after a subagent has run in the repository, because staging everything is a
bet that everything belongs, and it is the same habit that once swept a 1.3 GB file into history.

## 2026-08-13: the RDAP sweep had been stalled for over two hours, and it has no stall detection

Caught by asking the one question the project keeps having to ask: **is it finding anything, or merely
running?** The `.uk` batch had been in flight since 03:57 UTC and the process was alive at 2h40m. The
journal had not grown in seven minutes, which could be gzip block buffering, so I counted **records**
rather than bytes, twice, forty-five seconds apart: **2,000 both times.** At 1 q/s that should have added
about forty-five. Its own progress line confirms it: `2000/5000 [2:42:29<4:03:43, 4.87s/domain]`, frozen at
exactly 2,000 with the average degraded from 1.00 to 4.87 seconds per domain.

**The gap this exposes is structural.** `supervise_cdx_pool.sh` backgrounds its batch, polls journal growth
and kills a frozen one, and its header argues the case at length. `rdap_pool_sweep.sh` runs `ark rdap`
**synchronously and waits forever**: no growth check, no watchdog, no ceiling. So a hung batch hangs the
whole sweep silently, and the only reason it was noticed is that the yield check reports per collector and
somebody read it. That is exactly the failure the CDX supervisor was built to prevent, on the one collector
that never got the same treatment.

**Killing it lost nothing and gained the measurement I had been waiting for.** `ark rdap` finalised its
partial journal on the way out rather than discarding it, so the 2,000 answers are banked and published:
**2,000 answered, 284 in-window, 14.2%.** That is the honest per-batch figure for `.uk`, no longer a partial
read, against `.org` at 6.2% and with an English weight of 0.9813 rather than about 0.6. The list rebuild is
worth roughly 3.7x per request, as estimated, now on a published number.

A fresh batch is running at 1.03 domains per second on a new stamp. Two details for whoever fixes the
watchdog: `pkill -f '[a]rk rdap'` killed only one of the two processes in the `uv run` chain and the python
child carried on, so the second kill had to be by PID; and the sweep writes its journal as `.part` and
renames on exit, contrary to a claim in `yield_check`'s docstring that it writes its final name from the
start.

## 2026-08-13: the RDAP sweep gets the watchdog the CDX engine has had all along

Fixed the gap found an hour ago. `rdap_pool_sweep.sh` now backgrounds each batch, polls liveness every 60
seconds, judges journal growth every 900, and kills a frozen batch so the sweep moves to the next one. That
is the same two-clock design `supervise_cdx_pool.sh` argues for in its own header, and the reason it took a
stall to notice the asymmetry is that the RDAP sweep was written later and nobody ported the lesson.

**Bytes are a sound growth test here and would not be everywhere.** At 1 q/s a 15-minute window writes
roughly 190 KB, far above any gzip block boundary. Against a fast registry, Verisign sustained 118 q/s, the
window would need raising rather than the test changing, and the comment says so.

**Two things learned the hard way this morning are encoded rather than described.** `journal_bytes` checks
both `$out` and `$out.part`, because the run writes the partial name and renames on exit. And `stop_batch`
kills children before the parent, because `uv run` spawns a python child and a `pkill -f` on the wrapper
this morning left that child querying: the stall survived its own remedy, and the second kill had to be by
PID.

**A wrong claim is corrected where it was made.** `yield_check`'s docstring said the RDAP sweep "writes its
final name from the start and flushes as it goes", which is how the `.part` handling came to differ between
the two collectors. It writes `.part` and renames, exactly like the CDX engine. The reading stays
truncation-tolerant rather than excluding `.part`, because an RDAP batch runs over an hour and excluding it
would leave the newest hour unmeasured, which is a different mistake from the one being fixed.

## 2026-08-13: the watchdog was written and the running sweep could not have it, and my restart used the wrong list

Two mistakes in one wake, both worth recording because both are patterns rather than slips.

**A running bash script cannot pick up an edit, and editing one is worse than useless.** The sweep was a
process started a day and twenty hours earlier, so the watchdog committed an hour ago existed only on disk.
This is the same failure as the `discover_cycle` loop running pre-fix code, with a sharper edge: **bash reads
a script incrementally by file offset**, so editing a script mid-execution can corrupt the parse of the
running instance rather than merely being ignored. The rule in `CLAUDE.md` about restarting a background loop
after changing what it imports applies to shell scripts more strongly than to Python, and for a different
reason.

Restarted in the careful order that is now routine: stop the handover waiters so they cannot race the gap,
kill the batch child before its parent, restart, re-arm the waiters. The interrupted batch published its
partial journal on the way out, as designed.

**Then I restarted it without `LIST`, so it silently swept the wrong file.** `rdap_pool_sweep.sh` defaults
to `LIST="${LIST:-data/raw/rdap/pool_targets_verisign.txt}"`, and the original invocation had set the
variable. My restart did not, so the batch began against an 18 MB Verisign list that is almost entirely
already journalled: it reported **147 domains to query** out of a 5,000 limit. That number is what caught it.
A batch that finds almost nothing to do looks exactly like an exhausted pool, and I nearly recorded the
engine as spent.

**Measured before believing it, which is the only reason this was caught.** The intended list holds 160,474
unique names of which **159,193 have never been asked**, against 1,696,276 names asked across all RDAP
journals ever. So there is plenty of headroom and the "147" was a wrong-file artefact, not exhaustion.

Restarted again with `LIST` set explicitly, confirmed from the child's own command line rather than from the
log, and it is running at 1.03 domains a second on the right file. **The lesson for the handover script:
`extend_engines.sh` passes the CDX prefix and targets explicitly through `env` for exactly this reason, and
its RDAP branch does not. That asymmetry is now a known bug** and the next wake should fix it, because the
Saturday handover will otherwise restart the sweep on the Verisign default and quietly do nothing.

## 2026-08-13: pass 7, and the measured-yield rubric changed what the entries say

Seven survivors, nine dropped, 7 of 7 written. Queue: **47 entries, 44 open**. The rubric change landed:
entries now lead with MEASURED figures rather than estimates, because the instruction was that a
measurement is the score and the rubric does not apply.

**`gias_england_school_website_domains` enters at 82 on a measurement**: the DfE all-establishment extract
for England, 64.5 MB downloaded and parsed, `SchoolWebsite` populated on 24,886 of 52,485 rows, giving
**20,905 net-new registrable domains at mean weight 0.9095**. Its `sch.uk` slice of 6,349 names prices at
about 5,568 in-window domains on a **measured 87.7% registry answer rate, 65 of 65 names answered**, so that
slice alone clears the bar. It is `link_target`, candidate-only, so **collecting it waits on nobody** and the
year would come later from the CDX engine or from the pending Nominet decision.

**Three disproofs from this pass are worth more than the entries.**

- **The ".uk is our .us gap" analogy is false and I had been leaning on it.** The store holds **217,619
  in-window `.uk` domains against 18,278 `.us`**. `.uk` is not thin at all; only `sch.uk` is, at 2,646
  in-window names of which this snapshot covers 32.1%. Any future argument that a `.uk` source is valuable
  *because* the namespace is underrepresented is wrong, and the reason to want `sch.uk` is that nobody links
  to a primary school, not that `.uk` is missing.
- **A HEAD request would have wrongly closed the best find.** `HEAD` on the DfE bulk endpoint returns
  **HTTP/2 500** with a 146-byte JSON body while `GET` returns 200 and 64.5 MB. The standing instruction to
  prefer HEAD is a politeness rule that can produce a false negative, and this is the case that proves it.
- **The charity register has no historical contact at all**, measured by the right control: `contact_web`
  and `contact_email` on rows carrying a `date_of_removal` are populated on **exactly 0 of 211,694**. So a
  register with 265,086 pre-2002 charities still cannot say what any of their domains were in 1999.

Also recorded from the winner: Nominet returns the **current** registration, so a dropped and re-registered
name reads late, and the direction of error is loss rather than fabrication; and 7 of 57 in-window hits read
exactly `01-Aug-1996`, a registry floor artefact, so 1996 there means "existed by August 1996".

**And the handover bug flagged last wake is fixed**: `extend_engines.sh` now passes
`LIST=data/raw/rdap/pool_targets_org.txt` through `env` on its RDAP branch, so Saturday's handover cannot
restart the sweep on the Verisign default and silently do nothing. Re-armed on the corrected script.

## 2026-08-13, late: agent stood down on request, collectors left running

Ivo: *"good work, stop for a moment, until I wake you back up."* So both self-wake mechanisms are
deliberately off: cron jobs `dd2a6f56` and `e0362d85` deleted, and no heartbeat started. **This is the
one case where an absent schedule is correct**, and it is recorded because a wake that finds no cron and
no heartbeat otherwise looks exactly like the mechanism failing again, which is the confusion CLAUDE.md
step 0 exists to prevent. Re-arm with `CronCreate` plus one `sleep 540` background task, not two.

The four unattended engines were left alone and are healthy: `supervise_cdx_pool` (11834),
`discover_cycle` (82739), `rdap_pool_sweep` (50272), `maintain.sh` (16620), with `extend_engines`
(31400) holding four armed waiters for the handover to deadline 1786924800, Mon 17 Aug 02:00 CEST.
They carry absolute deadlines and need no agent, which is the property that makes a quiet stretch safe:
collection, banking and the yield checks continue at full rate while nobody is awake.

Nothing is mid-flight. Working tree clean at `45f6011`; last gate green through the pre-commit hook.

## 2026-08-13, late: the full check-in, and the 5% target measured against the actual rate

Ivo asked for a full check-in rather than more collection, and relayed the number that reframes the
round: **Ding expects 5% this round.** Recorded in `brief_amendments.md`, which until now said no
phase-5 target had been set. Everything below is measured, not projected, except where it says so.

**Everything is running and nothing is stuck.** `just cycle` is clean: local collector running, VPS
reachable with all 289 journals home, 0 unread residual, derived lists fresh apart from the gap list
whose staleness is expected by design, 10 hypotheses with 0 unfinished, `ROUND.md` regenerated. The
one item needing judgement is the 44-source triage queue, which is Ivo's and blocks nothing.

**The scoreboard, up from 170,787 pairs at the ship rehearsal this morning:**

| | now | at 06:10 today |
|---|---|---|
| net-new pairs | **184,086** | 170,787 |
| net-new domains | **137,194** | - |
| equivalent-English | **111,704.4818** | 101,139.3788 |
| growth on 6,226,386.4245 | **1.7940%** | 1.6244% |

Discovery remains dominant: 148,762 pairs worth 94,699.1780 EE over 137,194 domains, against 35,324
completeness pairs worth 17,005.3038. That is 84.8% discovery, the half the reviewer asked to be
prioritised.

**The three engines and their populations, since the question was asked directly.** Two of the three
work the candidate pool and one works gaps, which is the split Ivo designed on 2026-08-11:

| engine | population | targets | never asked | last 24h | hit rate |
|---|---|---|---|---|---|
| local `cdx_pool` | candidate pool | 2,500,701 | **2,500,009** | 16,211 requests, 675/h | 42.2% |
| VPS `cdx_q1` | bracketed gaps, shard1 | 672,864 | **661,206** | 7,200 requests, 300/h | 82.6% |
| local `rdap_pool_sweep` | candidate pool, `.org` | 2,080,998 bytes of list | - | ~85,700 requests, 3,570/h | 38.0% in-window of 550 answered per batch |

**No engine is anywhere near exhausting its targets**, which kills the assumption that the queue is
the constraint. 98.3% of the VPS shard and 100.0% of the local pool queue have never been asked. At
675 requests an hour the local pool alone is 154 days of work. **The constraint is request
throughput, and specifically the Internet Archive's throttling**: the last local batch took 342
throttles across 600 queries and ended on a 2,880 ms delay, against 66 throttles and 1,228 ms on the
VPS. Adding a third heavy client is exactly what this project has been refused for three times.

**A per-request comparison I had backwards, and the reason it is worth writing down.** Reading the
per-batch counters, gap work looks about **12x** better than pool work: the VPS finished 300 queries
for 864 `years_found` while the local engine finished 600 for 138. That comparison is wrong, because
`years_found` counts **every in-window year with a capture, including years already held**, and on a
bracketed-gap domain most of them are held by construction. Against banked net-new EE over the last
24 hours the true ratio is **1.24x**: 0.499 EE per request on the discovery half against 0.618 on the
completeness half. Same trap as the dated-dataset fallacy, one layer down: a counter that exists is
not the counter you want.

So **the allocation question is nearly EE-neutral.** Moving the VPS onto the candidate pool would cost
about 20% of that machine's yield, roughly 900 EE a day out of about 15,000, and would give up a 96.5%
hit rate for a 37.3% one. Nothing was changed; the split stands until Ivo says otherwise.

**What 5% costs, and this is the part that matters.** The round banks **624.1 EE/h** measured over the
last 24 hours and 649.1 over the last 72, steady at 560 to 690 across every 12-hour bucket since the
11th. Sunday evening is 68.3 hours away.

- 5% of 6,226,386.4245 is **311,319.32 EE**. We hold 111,704.48, so the deficit is **199,614.84**.
- That needs **2,921.3 EE/h**, which is **4.68x the measured rate**.
- At the measured rate Sunday lands at **154,349 EE, or 2.4790%**. On the 72-hour rate, 2.5064%.

**No lever of that size has been measured anywhere in this round.** The largest single source of the
whole round is `rdap_snapshot` at 55,151.9 EE, and closing the gap needs 3.6 of those in three days.
The CDX engines cannot be run 4.7x harder without the ban. RDAP is the one engine not competing for
the archive's budget, and it is already sweeping at 3,570 requests an hour for 2,438 EE a day. The
candidate pool's upper bound is 1,759,758 EE, so the material exists; the verification throughput to
convert it does not exist by Sunday.

Recording this now rather than on Sunday, because a target missed by 2x is a planning fact and a
target missed by 2x reported on the day is a surprise. It goes to `key-decisions.md` as one OPEN
entry, since what to do about it is Ivo's call and not mine: the honest options are to send at about
2.5% with the arithmetic shown, or to move the deadline.

## 2026-08-13, late: the review surface was under-reporting its own queue by 4x

Found during the check-in, not by a test. `key-decisions.md` told Ivo **11 sources** were awaiting
triage while the file it points at held **44**. The mirror's docstring said "one entry naming the
count, refreshed in place as the queue grows" and the code did not: `raise_open` is append-once and
returns False when the entry exists, so `_mirror_triage_count` returned early and the number froze at
whatever it was the first time it was written, on 2026-08-12.

**Worse than an absent number, because nothing about it looks stale.** He is being asked to work a
queue and told it is a quarter of its real size, on the one surface he reads, which is the exact
failure this file already records in another form: a question raised where nobody looks is not a
question asked, and here it was asked with the wrong number.

Fixed with `key_decisions.refresh_open(needle, body)`, which rewrites an existing entry's body and
leaves its heading alone so a heading improved by hand survives. Three properties are now tested:
that a refresh replaces the figure, that refreshing the **last** entry does not swallow the `---`
above `## CLOSED` and merge the two blocks, and that a refresh of an absent entry returns False
rather than quietly creating one.

**And a second bug inside the first, caught by looking at the output rather than the test.** The
heading pattern ends `\s*$`, `\s` matches newlines, so `match.group(0)` greedily swallows the blank
lines under the heading; re-emitting it added a blank line **per refresh**, which at one cycle an
hour is a visibly broken entry by morning. The entry is now rebuilt from `group('title')`, and the
test asserts the file's newline count is unchanged across four refreshes.

The loop was restarted twice for this, waiters down first each time, because the first restart
happened between the two fixes and would have carried the gap-growing copy for the rest of the round.
That is the trap this file records: **a long-running loop keeps the code it started with.**

## 2026-08-14: 5% made hard, the RDAP reserve measured away, and two orphaned collectors

Ivo, 2026-08-13: 5% by Sunday night is a requirement, not a target. Recorded as one in
`brief_amendments.md` and in the OPEN entry. He also asked whether the local RDAP sweep was still
running and on what pool, which turned out to be the more productive question.

**It was running, on `.org` alone, and that was the bug.** `pool_targets_org.txt` was pinned into the
handover on 2026-08-13 to give PIR a slow pace, and pinning the pace pinned the population with it.
`build_rdap_pool_list.py` already ranks every askable TLD by expected equivalent-English per query, so
the sweep was working a 0.048 EE/query list while a 0.070 one could be built in two minutes.

**Then the reserve was measured and it is not a reserve.** `RDAP candidate-pool headroom` has been
carried since 2026-08-11 as about 1.54M names never asked and 1.47 percentage points. Against the
journals it is **0.107 points**, and the collapse is worth recording step by step because each step is
a different mistake:

| | names | expected EE |
|---|---|---|
| carried in memory since 2026-08-11 | 1.54M | ~82,700 (1.47 pts) |
| Verisign `.com`/`.net`, now exhausted | 71 unasked of 1,345,949 | ~0 |
| every askable TLD, builder's own estimate | 461,466 | 32,474 |
| minus `.uk`, which Nominet's terms block | 407,505 | ~16,500 |
| restricted to TLDs with a **measured** rate | **149,816** | **6,655 (0.107 pts)** |

**The fallback rate is the interesting failure.** The builder estimates P(in-window) per TLD and falls
back to the pool-wide 8.3% where it has no sample. Multiplied by a high English share that puts `.vi`,
`.bm`, `.pn` and `.pg` above `.com` in the ranking. Their first **97 queries returned 1 in-window
date**, against 8.3% expected. A namespace with no sample is not an average namespace, it is usually a
namespace nobody registered in, and the builder's own "fabricated namespace" warning already says so
for eight other TLDs. The list is now restricted to `com,net,org,ca,nl`, the five with a real sample.

**Nominet was started and stopped after 140 queries.** `.uk` lands an in-window date on 30.6% of
queries at share 0.9813, six times better than `.org`, so the ranked list puts 20,000 `.uk` names at
its head. The RDAP response itself carries terms prohibiting *"high volume, automated, electronic
processes"* and re-use of *"all or part (quantitatively or qualitatively) of the contents"*, and
`sources.md` records Nominet refusing this project three times in fourteen queries. Raised in
`key-decisions.md` rather than decided here: it is Ivo's name on the User-Agent, it is worth 0.26
points, and a registry block is not recoverable in a weekend.

**And a trap that cost two unintended collectors, which is the real lesson of the evening.**
`pkill -f 'rdap_pool_swee[p]'` kills the supervisor shell and **leaves the `ark rdap` child running,
reparented to init**. So the `.org` sweep I believed I had stopped an hour earlier was still querying,
and the Nominet sweep I believed I had stopped after 23 queries was at 140 and climbing. Three RDAP
clients were live at once and the process table was the only place that said so. The script's own
`stop_batch()` has always killed children before the parent; a hand kill has to do the same, and
`pgrep -f` on the supervisor pattern **cannot see the child** because the child's command line is
`ark rdap ...` and matches nothing. **Check `ps -eo pid,ppid,command | grep 'ark rda[p]'` after any
kill**, not the supervisor pattern.

## 2026-08-14 14:00: check-in through the internet gap, and the derived alarm was watching a retired file

Ivo reported an internet gap and offered a short VPS window. Window used first, questions after.

**Nothing stopped, and the gap cost nothing.** All five long-running processes alive, and both
collectors wrote continuously through it: local CDX journals at 08:28, 09:13, 10:28, 11:50 and 12:59,
RDAP at 06:42, 08:36, 11:17 and 12:54. That is the property the absolute deadlines were built for, and
this is the first time it has been tested by a real outage rather than argued for.

**Four VPS journals were not home and are now banked.** `rsync` brought `cdx_q1_20260814T0726/0829/
0928/1024Z` across; by the time an explicit `ark ingest` ran three minutes later all four reported
"already ingested", because `maintain.sh` had taken them in the interval. Worth knowing rather than
worrying about: the loop is doing its job, and an explicit bank after an rsync is a no-op, not a
duplicate.

**The round now:**

| | 2026-08-14 14:06 | 2026-08-13 23:34 |
|---|---|---|
| net-new pairs | **198,120** | 184,086 |
| net-new domains | **145,439** | 137,194 |
| equivalent-English | **121,992.3109** | 111,704.4818 |
| growth | **1.9593%** | 1.7940% |

That is **+10,287.83 EE in 14.5 hours, or 708 EE/h**, against 665 measured over the trailing 24 and 536
over the trailing 12. The 12-hour figure is depressed by my own restarts overnight and by the `.vi`
detour, not by the collectors.

**The RDAP reallocation is visible and modest.** `rdap_snapshot` banked 4,765.7 EE in 24 hours against
2,438.3 the day before, so nearly double. The measured-TLD list is running at **3.2% to 3.7% in-window**
against the builder's 5.6% prediction for `.org`, which is the same direction of error as the fallback
rate and worth remembering: the builder is optimistic at both ends.

**And the derived-file alarm was watching a file nothing reads.** `audit_residual.py` and
`discover_cycle.py` both tracked `pool_targets_org.txt`, retired the night before, so the staleness
check reported cheerfully on a list the sweep had stopped reading and said nothing about
`pool_targets_measured.txt`. Identical in shape to the yield check that hardcoded three journal
prefixes and missed the VPS for 31 hours: **an alarm pointed at the wrong artefact reads exactly like
an alarm with nothing to report.** Both now name the live list and rebuild it with the restricted TLD
set, and the loop was restarted so the running copy has the change.

## 2026-08-15 04:45: the harness restarted, and the triage queue is now a counter rather than a request

Ivo, 2026-08-15: start the harness and look for new sources, schedule the last wake for Sunday
evening, and **"I will not review it, until you have found a source, or a combination of sources,
which could measurably get us to 5%."**

**That last clause changes what the triage queue is for.** Until now it was a growing list of things
waiting on his judgement. It is now a work register that he has explicitly deferred, and the one thing
that reopens it is a find at the right scale. The mirrored entry in `key-decisions.md` says so in its
own text, so the surface cannot go on quietly implying it wants him.

**The bar, stated once so every later measurement can be checked against it.** 5% of 6,226,386.4245 is
311,319.32 EE. The round holds **125,617.03** (202,756 pairs, 148,951 domains, **2.0175%**), so the
deficit is **185,702.29 EE**. At the round's mean weight of 0.6195 that is about **300,000 net-new
in-window (domain, year) pairs**.

**Why the raw size of a source is the wrong number, and always has been here.** The store holds
8,264,176 domains. Any corpus of 1996-2001 names will overlap it heavily, and the measured example is
the expansion A/B: 391 harvested domains, of which **386 were already held and every one already
dated**. So a candidate source is priced on how many names it dates that we do not already date, never
on how many names it has.

**Three prospectors are running, on deliberately different shapes:**

- **Bulk research crawl corpora**, aimed at TREC VLC2, WT2g, WT10g and Stanford WebBase. These derive
  from 1997 Internet Archive crawls, so a crawl date is an `artifact_listing` for every host in it,
  master-eligible. The question is whether a host or URL list can be had without the full corpus and
  without a signed agreement.
- **National archive bulk host lists and link graphs**, because that is the best-performing shape ever
  measured here: UKWA link-graph names hit **90.4%** against 46.0% pool-wide. Weighted, so a large
  German or Japanese archive is a small source.
- **Residual inside material already on disk**, the reviewer's own first priority, which needs no
  download and no permission.

Cron re-armed: a recurring wake, plus a one-shot **final wake at 18:03 Sunday 2026-08-16** that ships
rather than collects.

## 2026-08-15: the crawl-corpora angle closes, and it leaves a rule that is worth more than the leads

First prospector home. Every lead on its brief collided with the closed register, which is the register
doing its job, but the pass produced two durable things.

**The TREC family is now closed on measurement rather than availability, because the availability half
was false.** The entry read "agreement-gated, distributor unreachable". Glasgow took the collections
over from CSIRO and is alive: the page returns 200 and sells WT2g at 350 GBP, WT10g at 500, `.GOV` at
500, `.GOV2` at 650, DVD only, behind a signed organisational agreement. **A stale availability closure
is worse than no entry**, because it invites exactly the re-probe that cost this pass most of its
requests. What actually closes it:

- **The free files are a trap and were checked by GET rather than assumed.** `wt10g_inlinks.gz` and
  `wt2g_inlinks.gz` need no agreement and contain **only opaque docids**, 8,063,026 lines of
  `WTX001-B01-1`, with the docid-to-URL table on the paid media. Same failure mode as the SNAP graphs
  already in the register.
- **Size closes it whatever the price.** Bailey et al., IPM 39 (2003), give VLC2 as **117,101
  servers**, and VLC2, WT2g and WT10g all come from one 1997 Internet Archive crawl, so that is the
  ceiling for the entire in-window family and the year is 1997 alone.
- **`.GOV` was crawled January 2002 and `.GOV2` in 2004**, so both are out of window entirely and need
  never be looked at again. That was not previously written down.

**And the rule, now in `discovery.md` section 4 beside its sibling.** A source that selects for
authority cannot be net-new; **a corpus derived from the Internet Archive cannot be net-new against a
baseline that is itself IA-derived.** The evidence is measured, not argued: Stanford WebBase returned
**0.01%** net-new over 603,245 domains, Early Web CDX 99.99% overlap, and the Australian Web Archive
priced at exactly zero AWA-only pairs because it is Internet Archive data wearing a different
interface. The tell is a dataset described as built from a crawl donated by the Internet Archive, and
it settles the lead **without a request**. Given that our own two CDX engines are IA clients, this
rules out most of the "big 1990s crawl" family in one question.

Also upgraded to permanent: `webscope.sandbox.yahoo.com` no longer resolves in DNS, so the Yahoo
AltaVista graph is a dead host rather than a closed programme and does not want re-probing.

**Nothing from this angle goes in the triage queue**, because a closed lead with a measured verdict
belongs in `sources.md`, and the queue is for things that might still be worth collecting.

## 2026-08-15: the biggest lever of the round was already on disk, and verifying it cut it by a third

Third prospector home, and unlike the other two it found something. Re-running the corroboration split
against today's store promotes mentions that failed it when they were written: a domain typed in a
dated Usenet post is admitted for that year only if another source already places it in an annual
file, and the CDX and RDAP engines have dated tens of thousands of those domains since. The category
is not new. `diff_usenet_resplit.py` has called it `PROMOTED` since 2026-08-06, when it was 4,154
pairs. It is now two orders of magnitude larger.

**I re-measured it independently rather than accepting the number, and the number survived: 159,952
pairs, 102,661.1 EE, exactly reproducing the agent's strict figure.** Then the controls changed it.

**The negative control that cut a third of it.** 35.0% of the promotion set carries a mention year
EARLIER than the registry creation date of the same domain, against **16.5%** of the Usenet pairs the
store has already accepted. Same corpus, twice as contradicted. Registry dates read late for a
re-registered name so both figures are inflated, but the comparison is what matters, and the reason
the promotion set is worse is mechanical: my corroboration test admits a domain whose only dating is a
`whois_creation`, so a 2001 creation was "corroborating" a 1997 mention. Dropping those leaves
**110,409 pairs, 72,034.2 EE, 1.1569 points**.

**A first positive control that was wrong, and worth recording because it looked decisive.** I asked
how often the mention year falls inside the domain's own capture span and got **0.5% against a 20.6%
chance rate, a lift of 0.02x**, which reads as a devastating refutation. It is an artefact. The
promotion set excludes pairs already assigned, and the `nothing_earned_is_left_unassigned` invariant
guarantees every captured year IS assigned, so a mention year can only survive inside the span by
being a **gap** in it. The test was measuring gaps, not membership. **A result 40x worse than chance
is almost always a broken test rather than a broken dataset**, and this project's own rule already
says so: a search that finds nothing has either proved something or been pointed at the wrong place.

**The corrected controls, both against a fair null built from the same domains' undated years:**

- mention year inside the observed capture span: **5.52x** over the null
- mention year within one year of a real capture: **68.5% against 22.1%**, a **3.10x** lift

So the mention years are genuine observations that cluster on real activity, not noise.

**Not banked.** The class is already `master` and the mechanism is the designed one, so this is
arguably mine to do; against that, it puts 110,409 pairs into the annual files on typed evidence whose
population my own control shows is weaker than what is already accepted, and CLAUDE.md's standing
warning is that the split does not stop a plausible name that was never real. Waiting costs nothing:
no requests, and banking is minutes. Raised in `key-decisions.md` with a recommendation to bank the
110,409 and drop the 49,608 permanently.

**Honest arithmetic: this is +1.1569 points, taking 2.0175% to about 3.17%, and with the engines to
Sunday about 3.6%. It does not reach 5%.**

The other two angles closed with nothing, but the national-archive pass left a finding that reframes
the whole search: **every national archive holding in-window data holds it because the Internet
Archive donated it**, shown five times over (Australia, Iceland, Arquivo.pt, the BnF acquisition, and
the JISC UK dataset, which the British Library describes as Internet Archive resources on `.uk`
domains). Native national harvesting starts 2002 at the earliest. So the UK link graph did not pay
90.4% because it was non-IA data. It **is** IA data; it paid because a link graph is a different
*projection* of IA's holdings, naming hosts that IA's own CDX rows do not surface as captured sites.
The productive question is not which archive holds non-IA in-window data, to which the answer is none,
but which publishes a derived projection of IA data in bulk.

## 2026-08-15: the IA-derived rule needed an exception, and it is the exception that matters

Wrote a rule this morning that would have closed the best family we have. It said a corpus derived
from the Internet Archive cannot be net-new against an IA-derived baseline, which is true of the TREC
collections, Stanford WebBase and the Australian Web Archive, all measured at or near zero. Applied
literally it also closes the UK Web Archive host link graph, **which is IA data and is the
best-performing source ever measured here at 90.4%**. A rule that closes your best source is wrong.

**The distinction is not provenance, it is which constraint binds.** Our coverage of the Internet
Archive is limited by our own query rate, not by IA's holdings: **212,394 domains have ever been asked
at CDX** against 2.5M sitting in the pool, and the two engines clear about 975 requests an hour
between them. So:

- A source that **re-serves captures the baseline already drew on** is worthless. That is the TREC and
  WebBase failure, and it is why the AWA priced at exactly zero AWA-only pairs.
- A source that is a **different projection of IA's holdings, delivered in bulk**, is the opposite of
  worthless, because it converts our scarcest resource into a file download. The link graph pays
  precisely because it surfaces hosts that IA's own CDX rows do not return as captured sites.

Recorded in `discovery.md` section 4 immediately under the rule, because separating them by even a
paragraph invites the next pass to read the first and stop. Such a source is judged on the English
share of what it covers and on whether it actually downloads, never on its upstream.

A fourth prospector is out on exactly that shape: other British Library derived datasets from the
JISC UK Web Domain Dataset, Archives Unleashed derived data, index-rather-than-content items on
archive.org, and the other Arquivo.pt CDXJ collections. It carries the reachability traps that have
produced false negatives here, in particular that a 200 response can be a 159-byte error stub.

## 2026-08-15: the bulk-index family exists, is locked, and the VPS throughput lever does not pay

Fourth prospector home. **Nothing downloadable at scale**, but the closures are precise enough to stop
this ground being broken again, and one of them changes what we know rather than only what we tried.

**The stub is the tree, not the file.** `webarchive.org.uk/datasets/ukwa.ds.2/geo/` returns the same
159-byte "400 Redirect" body under HTTP 200 as `linkage/host-linkage.tsv.gz`, a file we are known to
hold. That is a **positive control**, so it answers every future probe of any path under `/datasets/`
in advance. The full Geoindex behind it is 700,641,549 lines over 1996-2010, about 8 GB gzipped, all
`.uk` at 0.9813. It is the largest reachable-looking prize still closed and the only route left is a
letter to the British Library, not another URL.

**The bulk index we want demonstrably exists and is access-controlled**, which is a different and more
useful closure than "does not exist". In-window Alexa and IA donated crawl items on archive.org carry
per-item CDX files, 104 MB and 631 MB, exactly the shape that would convert our query-rate constraint
into a download. A ranged GET returns **HTTP 401 with a 172-byte body**, so **the restriction covers
the index files and not merely the payload WARCs**, which this project had assumed rather than tested.

Also closed: the other JISC derived files are hostless by construction (MIME-by-year counts,
suffix-to-suffix counts, and a classification file with no year at all); Archives Unleashed builds on
Archive-It, which starts in 2005; and every non-`AWP` Arquivo.pt CDXJ collection sampled out of window,
including the 62 GB Internet Memory Foundation legacy, whose predecessor was founded in 2004. One file
did download, the UKWA Geoindex E17 slice, and it is worth **123 pairs and 120.7 EE** after the split,
two orders below the bar.

**And a lever I measured and am deliberately not pulling.** The VPS is throttled far less than the
local engine, 108 refusals per 300 queries against 437 per 600, and its adaptive delay sits at 1,179 ms
against local's 3,000 ms ceiling, so it looked like free headroom. Timing its journals kills the
attractive version of that idea: batches start 01:02:11 and finish 02:17:07, 23:50:10 to 01:00:50,
22:40:09 to 23:48:46, so **each 300-query batch takes about 70 minutes and the next starts within a
minute.** There is no idle gap, so batch size is not the lever and raising it buys nothing.

Raising **workers** would buy something, and the arithmetic says not enough. The VPS banks 0.68 EE per
request against local's 0.39, so a 50% concurrency increase is about 200 EE/h, roughly **0.116 points**
by Sunday. Against that, the Internet Archive has refused this project outright three times and is
already refusing 36% of the VPS's queries. **Trading a 0.1 point gain for a non-trivial chance of
losing both engines is a bad trade**, and doing it anyway would be effort that looks like progress.
Recorded so the next wake does not rediscover the idea and reach a different conclusion.

## 2026-08-15: the heartbeat check counted double, so "exactly one" was never being tested

Checked the process table this wake and read **2 heartbeats**, which is the one thing CLAUDE.md says
must never happen. It was a false alarm, and the check itself is the bug.

A background heartbeat is two processes: the zsh wrapper that `eval`s `sleep 540; echo "HEARTBEAT..."`,
and the `sleep` it forks. **Both command lines contain the pattern**, so
`pgrep -f 'slee[p] 540' | wc -l` returns **2 for a single healthy heartbeat**. Verified directly: pid
19238 is the wrapper, pid 19242 its `sleep 540` child, one heartbeat.

So the documented rule has been reporting a violation every time it was run, and its documented remedy,
"stop them all and start one", would have killed a working heartbeat on every wake. The rule was
adopted after two heartbeats really were in flight; **whether that original incident was two heartbeats
or one miscount cannot now be established**, and it is worth saying so rather than quietly assuming the
convenient answer.

The correct check counts the wrapper only, which is the process whose command line carries the `echo`
as well as the `sleep`:

    ps -eo command | command grep -c 'slee[p] 540; echo "HEARTBEAT'

One per heartbeat, verified. `pgrep -x sleep` is not a substitute, since it counted 8 unrelated sleeps
on this machine. CLAUDE.md corrected in place, because a check that cries wolf every wake trains the
reader to ignore it, which is the same failure as the gap-list alarm that was firing by design.

## 2026-08-15: a dead lead came back to life and it was a parking page

`just cycle` reported a closed-on-availability lead answering unexpectedly:
`https://web-caching.com/`, the third host for the **IRCache / NLANR proxy traces**, which the register
of 2026-08-06 calls "dated squid logs holding millions of real URLs, the most promising lead on that
day's list". It had timed out then. It returns **HTTP 200 and 27,223 bytes** now.

**It is a consent-manager parking page.** Fetched and read rather than trusted: no title, one `href="#"`,
and a body that is entirely a GDPR consent stub. Same fate as `ircache.net`, which the register already
records as "now serves a squatted blog". So all three hosts for this lead are squatted or parked rather
than dead, and the traces are still unlocated. **The verdict does not change.**

**The re-prober was reading status and not content**, so a squatter buying a dead domain reads exactly
like an archive coming back. That is the third check this round found crying wolf, after the gap-list
alarm that fired by design and the heartbeat counter that read 2 for one heartbeat, and the failure mode
is the same each time: **an alarm that fires on something harmless trains the reader to skip it**, and
then it is worth less than no alarm at all.

Fixed where it belongs, in the checker rather than in this entry. `reprobe_closed.py` already read 2 KB
of body for its size line, so matching a short list of parking and consent signatures against those
bytes costs nothing. A parked answer now prints "parked page, not a source" and, more importantly, does
not set `changed`, so it stays out of the summary that asks for pricing. Four tests pin it, including
that a real directory listing survives the filter, which is the case that matters: the thing we are
hunting must not be filtered out by the thing that filters out the squatters.

## 2026-08-15: section 2 of the report now tells this round's story

The template's section 2 is the part every round rewrites, and it still carried the previous round's
narrative: the generative question, the dispute docket at 87.7% net-new, the registry reopened after a
throttle was misread as a block. All true, all last round. Rewritten, keeping the parts that are not
round-specific: the five-programs table, the boundary paragraph about what a program cannot do, and the
paragraph on why an unattended process is safe at all.

**The new narrative, which is the honest one.** The question this round had to answer is what happens
when the sources run out, and the answer is that the scarce resource stopped being places to look and
became judgement about which places are worth a request. Two rules now close whole families with no
request at all: a source that selects for authority cannot be net-new, and a corpus derived from the same
archive as the baseline cannot be net-new against it. The second carries the exception that matters more
than the rule, that a **bulk index of that same archive** is enormously valuable because it converts our
rate limit into a file download, which is why the best source ever measured here hits 90.4%.

**And the finding worth reporting as a shape rather than as a source**: the largest opportunity of the
round was already on disk. Re-applying an unchanged admission rule to a corpus that has grown promotes
names that failed it when first read. **In a mature corpus, re-examining old evidence against new
knowledge outperforms looking for new evidence.** That generalises past this project, which is what makes
it worth a paragraph in a report to a reviewer who asked for scientific discovery rather than downloading.

The negative results are reported as the majority, because they are: four families searched, one paid.
Two closures are recorded as permanent in a useful way, one priced at its ceiling from a published figure
instead of by buying the corpus, and one settled by finding that the access restriction covers the
**index** files and not merely the content, which had been assumed and never tested.

**The three crying-wolf alarms are in the report too**, and deliberately. A report about method that
omits its own instrument failures is not a report about method. All three now have tests.

No number was written by hand. Every figure in the document still comes from `fill_report.py`, which
reports `would fill cleanly`, so the narrative can be finalised now and the numbers refreshed on Sunday
from whatever the store then holds.

## 2026-08-15: building the promotion corrected its own headline figure

Started building the tool that would execute the Usenet re-split so Ivo's answer costs minutes rather
than an afternoon, and the build found an error in the number I had given him.

**The good news first: it is a re-file, not a re-parse.** `usenet_dated` and `usenet_candidates` are two
`SourceSpec` entries over the **same parser and the same journal format**, differing only in which
source name and evidence type they file under: `usenet_announce` / `dated_directory`, which is master
and already approved, against `usenet_mention` / `link_target`, which is candidate-only. So promotion
means writing the same lines under the other key. Nothing needs re-reading from the 411 GB, and the
journal line can be reconstructed from the evidence row, since `evidence_value` is stored as
`"{group} {message_id}"` and the URL is stored beside it.

**Eight families have that exact one-to-one shape**, and the per-source split is worth recording because
the concentration is extreme: `usenet_mention` 79,819 pairs and 52,915.4 EE, `usenet_address_mention`
47,483 and 30,017.5, `usenet_bare_mention` 8,769 and 5,552.0, then `enron_email_mention` 2,623,
`maillist_archive_mention` 1,049, `trade_press_mention` 296, `rtfm_faq_mention` 135, `tucows_mention` 92.
The three Usenet families are 96% of the value.

**And the correction. `ukwa_link_target` cannot be promoted at all, and I had counted it.** Its only
relative is `ukwa_link_source`, which is `link_source`: that dates the page **doing** the linking, not
the page linked **to**. Promoting a link-graph edge to a dated assignment on its target is exactly what
the `link_target` class exists to forbid, and no amount of corroboration changes that, because the
corroboration split answers "is this domain real" and never "does this edge date its target".
`uucp_map_mention` and `page_expansion` fail identically.

So the defensible figure drops from **110,409 pairs and 1.1569 points to 106,604 pairs, 69,337.4 EE and
1.1136 points.** The OPEN entry is corrected in place rather than only here, because a number he has
already read is the one that has to be right.

**Worth noting how it was caught**: not by re-checking the arithmetic, which was correct, but by asking
what each row would be written **as**. A figure can be measured perfectly and still count things that
cannot legally exist in the destination.

## 2026-08-15: the promotion is built, tested and deliberately unrun

`scripts/build_promotion_journals.py` now turns Ivo's answer into one command. It reproduces the
corrected figure exactly on a dry run: **106,604 deduplicated pairs, 69,337.4 equivalent-English**,
across eight families whose concentration is extreme, `usenet_mention` 79,819 and
`usenet_address_mention` 47,483 being 90% of it, down to `tucows_mention` at 92.

**It writes journals and never ingests, and that is a design decision rather than caution.** Banking is
a judgement about the corpus; emitting the journals is mechanical. So the script prints the exact
`ark ingest` lines and stops, which also means the tranche can be inspected on disk before anything
touches the store.

**Five tests, and the round-trip one is the point.** A written line is parsed back through the real
`usenet_dated` SourceSpec and must return the same domain, year and `evidence_value`. That is what makes
the re-file provably lossless: these 106,604 rows go in under a MASTER source, so a mangled field would
become a year assignment whose Message-ID names the wrong post, and no invariant would catch it because
the wall only checks that an evidence row exists. The other four pin the mapping itself: every target
must exist, must not be candidate-only, and **must share a parser with its mention source**, which is
the whole safety argument; plus an explicit test that `ukwa_link_target`, `uucp_map_mention` and
`page_expansion` are absent from the mapping, so the mistake I nearly made cannot be reintroduced
silently.

One small thing the build refused to do: when `evidence_value` has no space there is no group, and the
parser's own default of `usenet` is left to apply rather than inventing a newsgroup name. A fabricated
newsgroup in an audit trail is worse than an absent one.

Gate green, 439 tests. README carries the command.

## 2026-08-15 06:20: two things that looked wrong and were not, checked rather than assumed

**The scoreboard read identical to four decimal places across two wakes**, 128,607.0203 EE both times,
which is the signature of a stalled ingest. It is not one. The last bank was 05:32:34, `maintain.sh` is
on pass 318, and both CDX batches take about 70 minutes, so two readings 30 minutes apart fell inside one
inter-bank gap. **An unchanged number is only evidence of a stall if the interval is longer than the
cycle that changes it**, which is the same mistake in miniature as reading a quiet log as a dead
collector.

**And a genuine Sunday risk that turned out to be already handled.** `docs/report.md` is git-tracked and
regenerating it leaves the tree dirty, while `package_delivery.sh` refuses to package a dirty tree. That
would have stopped the delivery at 18:03 tomorrow. Reading `just ship` rather than guessing: it
regenerates the report, and if the file changed it stages and commits it with its own message before
packaging, precisely so the run is a single pass. So the path is safe, and the guard and the recipe were
built to work together. Committing the current regeneration anyway, because a clean tree going into
Sunday costs nothing and a dirty one invites exactly this question again.

## 2026-08-15: the ship rehearsal is green, and the NAF headroom never existed

**Ship rehearsed end to end after the template rewrite and four new scripts, and it passed**: nine
invariants ALL PASS, report regenerated and committed by the recipe itself, **1,196 files matching
SHA256SUMS**, 207,397 pairs each traced to an observation, 1.4 GB archive. The previous rehearsal found
six failures, which is the argument for repeating it after changes rather than trusting a green from two
days ago.

**And the UDRP reopen came back a measured negative that kills a projection.** The register said NAF
"plausibly holds one and a half to two times what is ingested", labelled a projection. Zenodo 21310923
counts Forum decisions at 658 in 2000 and 768 in 2001, **1,426 total, against 2,573 NAF domains this
store already holds.** There was never a shortfall. The reasoning error is worth naming: ICANN describes
its own table as incomplete, and that was read as evidence that **our** coverage was incomplete. Those
are different claims, and only the first was ever evidenced.

**I made a worse version of the same mistake this morning and told Ivo about it.** I said the store held
"WIPO only, all 8,923 rows `UDRP WIPO D...`". It holds **WIPO 5,963, NAF 2,575, DeC 210, eResolution 133,
CPR 42**. I had run `LIMIT 4` and generalised from four rows, with the section heading `udrp_wipo`
confirming what I expected to see. **A sample is not a census, and a heading is not a schema.** The whole
hunt was aimed at a gap that a single `GROUP BY` would have shown was already filled.

**One genuine trap found, and it is the dangerous kind.** Zenodo 16954717's `submitted` field is corrupt:
`D2002-0431` carries 1999-08-26, `FORUM 94730` carries 1998. Trusting it raises net-new from 158 to 769
by inventing **518 fabricated 1999 pairs**. On a self-dating source a bad date field is not noise, it is a
master year claim manufactured by a parse error, and it would have passed every invariant we have because
the evidence row would exist and be well-formed. The case number is the trustworthy field, since it
encodes its own year.

Two ICANN plain-text exports found that the repo never referenced, `domains-list.txt` (4,666,685 bytes,
34,027 lines) and `proceedings-list.txt`: **90 net-new pairs**. The entire remaining UDRP family is worth
about **90 equivalent-English**. Closed on measurement, and the register now says do not reopen it on
availability.

## 2026-08-15: a coverage audit that found nothing wrong, and a hunt that walked into a closed lead

Generalised this morning's `LIMIT 4` mistake into a check: **for every source in the store, what years
does it actually cover?** If a family were wrongly believed complete, a truncated year range is where it
would show. The audit is worth keeping as an instrument even though its verdict was clean.

**Every narrow source is explained, and each explanation is already in the register.** `isc_survey`
27/73/0/0/0/0 because the survey name lists genuinely stop at July 1997. `odp` 0/0/0/0/63/37 because
archive.org holds exactly one ODP item. `udrp_proceedings` 0/0/0/0/59/41 because UDRP began in December
1999. `ncsa_whats_new` and `arquivo_roteiro` are 1996-only. `uucp_map_*` stop in 1998 with the maps
themselves. No unexplained gap anywhere.

**The one that looked like a find was `early_web_cdx`**, the largest source in the store at 2,278,722
rows, covering 1996-1999 with **exactly zero** in 2000 and 2001. The item is titled "Language Annotations
of the Early Web (**1996-1999**)", so the gap is the dataset's definition rather than our ingest.

**Then I nearly recorded a shortfall that does not exist.** The file listing ends `...00235, 00236,
00237` and we hold 224 files, so I inferred fourteen were never fetched. The item contains exactly 224
`.cdx.gz` files; the numbering has gaps and merely runs to 00237. **A maximum index is not a count**, and
this is the same error as reading a heading as a schema, made twice in one day and caught only because I
listed the item's files instead of subtracting.

**And the hunt that followed was a straight failure of process.** Finding `early_web_cdx` sits in
`collection:webarchivedatasets`, I searched that collection and found a sibling,
`early-web_parallel-language-urls`, which looked like an unscreened bulk URL dataset. It is in
`sources.md` twice: closed because its 1,164,183 URL patterns carry **no timestamps of any kind**, so
there is no per-year evidence, and separately measured at **+374 EE against a marginal displaced query,
which the project's own estimator scores negative.** The enumeration I performed is also recorded
verbatim: "`collection:webarchivedatasets` exactly 8 items with only the two already-documented
`early-web_*` in window."

Two requests spent re-deriving a recorded answer. `discovery.md` section 5 says reading the register is
the cheapest step in the process, and I probed first. The register was right, it was current, and it was
not consulted.

## 2026-08-15: the report did not mention the target it is judged against

The report reported growth as a bare number and never named the 5% expectation. Delivering about 2.5%
against a target of 5% without saying so reads as either oblivious or evasive, and both are worse than
the shortfall. Section 1 now states it directly, after the figures and before the method.

**The paragraph is measurement rather than excuse**, which is the only version worth writing. The binding
constraint was not candidate supply and not the evidence rules but **request throughput against a single
archive**: about 2.5M names unqueried, 212,394 ever asked, both collectors clearing roughly 975 requests
an hour, and the archive refusing 437 of 600 queries from the busier one at its three-second ceiling.
Raising concurrency is the only lever that closes the gap arithmetically and the one that risks losing
the archive, which costs more than a round. The families that could have supplied a step change are named
as searched and closed on measurement: zone files and registry snapshots, research crawl collections,
national archives, bulk archive indexes.

**Two corrections to my own paragraph before it could ship.** The throughput figures are a dated snapshot
rather than a standing rate, so they now carry the date and say so; a hand-written number in a generated
report is exactly how a document goes stale while looking authoritative, and `fill_report.py` cannot
refresh what it does not own. And I typed **2025** for the year of the measurement in a document about
1996-2001 growth measured in 2026, which would have put a wrong date in front of the reviewer. Caught by
re-reading the rendered output rather than the diff.

## 2026-08-15: the whole triage queue priced against the target, because that was the standing question

Ivo's condition of 2026-08-15 was that he would not review the queue until a source **or a combination**
could measurably reach 5%. I had been answering that one source at a time, which never answers it. So the
queue was measured whole.

**48 entries, none decided. Nine carry a measured figure and they sum to 16,792.1 EE, which is 9.19% of
the 182,712 EE deficit.** The largest single entry is 5,463.0. Closing the gap from 48 sources needs an
average of 3,806 EE each; the measured mean is **1,866** and the measured maximum is 5,463.

**Projection, labelled: if the 39 unpriced entries resemble the 9 priced ones, the queue is worth about
90,000 EE, roughly half the deficit.** Only if all 48 matched the best entry ever measured would it
reach the target.

**And two corrections I made to my own reasoning while measuring it.** I first assumed most of the queue
was `link_target` and therefore pool growth rather than equivalent-English. It is not: **79% is
master-eligible** (dated_directory 11, typed 9, link_source 8, artifact_listing 6, whois_creation 3)
against 21% `link_target`. But the correction cuts the other way too, because 9 of the master-eligible
ones are `typed` and take the corroboration split, so their raw figures fall by half or more on
admission. The generous reading and the strict reading both land well short.

Recorded on the review surface itself, replacing a line that had been a bare count. **The queue is not
urgent and reviewing it would not change Sunday**, which is a more useful thing to tell him than the
number 48.

## 2026-08-15 08:40: the un-banked tranche compounds, and the Sunday forecast

Re-ran the promotion builder against the store rather than trusting this morning's number, and found a
second-order effect worth recording: **the promotable tranche grows on its own.**

It is now **106,703 pairs and 69,407.7 EE**, against 106,604 and 69,337.4 a few hours ago. The mechanism
is the corroboration split itself: every domain the CDX and RDAP engines newly date can unlock that
domain's **other** mention years, which were sitting as `link_target` waiting for exactly that. So
collection feeds the tranche as well as the round.

**Measured, not assumed: the tranche grows at 11.1% of the round's rate**, 70.3 EE against 635.5 in the
same interval. Useful, and much smaller than the compounding story would suggest if left unquantified,
which is why it is worth a number rather than an adjective.

**The Sunday forecast, from a 640 EE/h rate measured over the last three days and 33.3 hours to run:**

| | equivalent-English | growth |
|---|--:|--:|
| now | 129,242.6 | 2.0757% |
| Sunday, engines only | ~150,600 | **~2.42%** |
| Sunday, with the promotion banked | ~222,300 | **~3.57%** |
| 5% would need | 311,319.3 | 5.00% |

Both projections are labelled projections. The engines-only figure is the safe one and the one the
report currently states its shortfall against; the promotion figure needs a word from Ivo that has not
come, and I have not banked it.

Worth being plain in the log as well as in the report: **neither number reaches the target, and the
difference between them is a decision rather than any further work.** Nothing else available between now
and Sunday moves the round by more than a few hundred equivalent-English.

## 2026-08-15: the local engine was being throttled into the ground, so it now pushes less

Measured rather than hunted this wake, and it found the one operational problem left. **The archive has
been throttling the local engine progressively harder and it is returning less for it.**

| batch start (UTC) | minutes | requests/hour | throttles per 600 | failed outright |
|---|--:|--:|--:|--:|
| 08-14 17:28 | 64 | 566 | 417 | 1 |
| 08-14 21:07 | 66 | 542 | 537 | 0 |
| 08-15 00:01 | 79 | 456 | 631 | 3 |
| 08-15 01:21 | 92 | 390 | 896 | 101 |
| 08-15 02:55 | 95 | 378 | - | - |

Three trends, all monotonic: throughput down from **566 to 378 requests an hour**, refusals up from 417
to **896 per 600 queries**, and the last batch losing **101 requests outright**, 17% of everything it
asked. The adaptive delay has been pinned at its 3.0 second ceiling throughout, which means the governor
has no room left to give.

**The project already knew this shape and wrote it down one ceiling higher.** `supervise_cdx_pool.sh`
carries the comment that on 29 July a throttle burst pinned a run at 5 seconds and it managed 240 domains
an hour for the rest of the batch, concluding that "pacing is a safety valve". We are in the same state
at 3 seconds, and pacing has stopped being able to help because the pressure is concurrency rather than
delay.

**So workers go from 8 to 4** on the local engine, and `extend_engines.sh` is updated so Saturday's
handover cannot revert it. The expectation, stated in advance so it can be checked against rather than
rationalised afterwards: **fewer refusals, the governor recovering its delay below the ceiling, and
completed throughput at or above the 378/h it has fallen to.** If throughput does not recover within two
batches, the change was wrong and should go back.

**The reason to do it even if throughput only breaks even** is the standing rule rather than the
arithmetic. This project has been refused outright by the Internet Archive three times, "modest
concurrency" is one of its five good-citizen commitments, and an engine losing 17% of its requests to
refusals is not being a modest client. The upside is a couple of thousand equivalent-English; the
downside it avoids is losing both engines 32 hours before a delivery.

Stopped child-first, which is the orphan trap this round already paid for once, and the supervisor needed
a `-9` after the ordinary kill left it running.

## 2026-08-15: the early read on the back-off is bad, and I may have diagnosed it wrong

Held myself to the falsifiable prediction from the previous entry and checked. **The first 4-worker batch
is running at about 170 requests an hour against the 378 it replaced.** That count is a floor rather than
a measurement, because the last gzip block of an in-flight journal is unflushed and only 37 records were
decodable at 13.2 minutes, but the direction is clear enough to take seriously.

**A hypothesis I should have considered before acting.** I attributed the collapse to concurrency
pressure, on the reasoning that more workers draw more refusals. But the previous batch lost **101
requests to `failed_0`**, which is a connection failure or timeout, and the timeout is **70 seconds**.
101 failures at up to 70 seconds each is roughly 7,000 worker-seconds of dead time. If the batch is
**timeout-bound rather than throttle-bound**, then worker count is the wrong knob entirely and halving it
halves throughput directly, because each worker spends most of its life waiting on a socket that will
never answer. The correct lever for that failure is a **shorter timeout**, not fewer workers.

Both stories fit the same evidence I used, which is the problem: rising refusals and falling throughput
are equally consistent with "we are pushing too hard" and with "a growing share of requests hang until
they time out". I picked one and acted on it without a measurement that could separate them.

**Not changing anything again until this batch finishes.** Thrashing a collector on a partial read is how
a tuning decision becomes two, and the stated criterion was two batches. What will separate the
hypotheses when the batch lands is `failed_0` per 600: if it stays near 101 the problem is hanging
sockets and the timeout comes down to about 25 seconds; if it falls sharply then concurrency really was
the pressure and 4 workers was right. Recording the discriminator now, before the data, so the answer
cannot be fitted to whichever result arrives.

## 2026-08-15: the back-off was wrong, reverted, and the next lever was already measured and rejected

The discriminator I wrote down before the data has answered, and it went against me. **Reverted to 8
workers.**

**What the 4-worker batch actually did.** Two in-flight samples: 37 records at 13.2 minutes, 74 at 22.6,
so about **236 requests an hour in the interval against the 378 it replaced**. The status mix decided it:
**17 failures in 74 records, 23%**, against 17% at 8 workers. My stated test was whether failures fell
sharply. They rose. So the pressure was never concurrency: fewer workers just meant less parallelism
against the same hanging sockets, and each one still burned its full timeout.

**The obvious next move was to cut the timeout, and the project had already measured that and rejected
it.** `src/ark/cdx.py` carries the figures: at 30 seconds a run answered **51 of 100** domains for 695
answers an hour, at 180 seconds it answered **82 of the same 100** for 802 an hour, because roughly a
third of domains reply between 30 and 60 seconds. The 70-second default already sits just above the
server's own ~60.7 second cutoff. **Cutting in earlier is a false economy and it is written down as
one.** I was about to do it anyway and only read the constant's own comment because I stopped to check
whether a timed-out domain is retried or permanently skipped.

That check was worth doing on its own account: `journal.py` takes an `answered` predicate precisely so a
transport failure is **not** treated as settled, so failures are re-asked on a later pass and nothing is
lost permanently. That is the property that makes accepting a lower rate safe.

**So the conclusion is that the degradation is the archive's behaviour and not our tuning**, and the
right response is to stop turning knobs. Both the failed attempt and the measured reason the next lever
is closed are now recorded in `extend_engines.sh` beside the setting, because the comment there said
"four workers, and the reduction was measured" for about an hour, which would have been a confident wrong
answer for whoever read it next.

Cost of the whole experiment: two restarts and roughly one batch of throughput, both recoverable, since a
re-run is additive and the killed batch's journal was renamed on the way out and kept.

## 2026-08-15: a hunt that cost nothing, which is what the register is for

Screened anti-spam blocklists, 1997-2001. **No collision in the register**, so genuinely new ground, and
the shape was the one that has actually paid here: a machine-generated dated record about whoever
happened to be there, selecting for short-lived spam domains that a crawler-derived baseline
systematically misses. That is precisely why the dispute dockets measured 87.7% net-new.

**It dies on the unit, and no request was needed to establish it.** Every in-window blocklist is
IP-based: MAPS RBL, ORBS, the Dial-Up List and SPEWS publish addresses and netblocks. Our output unit is
the registered domain, so there is nothing to extract. Domain-based URI blocklists, SURBL and URIBL,
begin in 2004 and are out of window.

**And the domain-bearing version of the idea is already banked**, which the store answered for free: spam
sightings were posted to `news.admin.net-abuse.*`, **13 of those groups are on disk**, and they have
yielded **173,526 evidence rows over 168,075 domains**. So the good half of this idea arrived with the
Usenet corpus and the half that is left has no domains in it.

Worth recording as a positive about the method rather than only as another closure: **screen, then ask
what the source actually contains, then probe** cost zero requests and produced a durable register entry.
Two wakes ago I probed first and spent two requests re-deriving a recorded answer. Same agent, same day,
opposite order.

## 2026-08-15: the hunt found a registry inside our own Usenet corpus, and the archive is refusing a second client

Two findings, and the operational one matters more than the source.

**The Internet Archive refused every one of the prospector's 12 budgeted requests**, `http=000`, zero
bytes, failing at a flat ~10.4 seconds, while `supervise_cdx_pool` was running 8 workers and logging
**1,155 throttles and 14 refusals**. `example.com` and `arquivo.pt` answered 200 throughout, so it was
archive-specific rather than a network fault. **We are not blocked**, checked directly: a plain CDX query
from this host returns **200 in 8.5 seconds** right now. But the collector's own failure share has
roughly doubled, **57 failures in 140 records, 41%**, against 17% twelve hours ago.

So the collector is saturating this host's allowance to the point where a second, entirely legitimate
client cannot get a connection at all. **That is not a throughput question, it is a citizenship one**,
and it is the strongest argument yet that the local engine is at its limit. I am still not tuning it
again: 4 workers was measured worse, the timeout lever is measured and rejected in `cdx.py`, and I have
already spent a batch proving the first of those.

**And the source: the CA Domain Registry's own registration notices, sitting in our Usenet corpus.**
`can.domain.mbox.zip`, 71,391,651 bytes uncompressed, carries one notice per approved `.ca` registration
with `Subdomain:`, `Date-Received:` and `Date-Approved:` as structured fields. **I verified the structure
myself rather than taking it on report**: whole-file scan gives `Subdomain:` 37,782, `Date-Approved:`
37,578, `Date-Received:` 37,576 and 37,692 subject lines containing "register". The hunt's measurement,
which I have not re-derived, is **12,893 net-new pairs, 11,954 net-new domains, 10,785.0 EE** at mean
weight 0.8365, with `can.uucp.maps` adding 1,795 pairs for a union of **13,341 pairs and 11,143.0 EE**.

**A near-miss worth recording.** My first check sampled 400 KB and found **zero** of those fields, which
looked like a flat refutation. The notices simply start later in the file. 400 KB of 71 MB is 0.6%, and I
have made the "a sample is not a census" mistake once already today, so I scanned the whole member before
concluding. **The same instinct that produced this morning's `LIMIT 4` error nearly killed a real find
eight hours later.**

This is the same shape as `uucp_map_registry`, which CLAUDE.md already describes as "a .CA registry dump
the Usenet parser read as prose". The group is ingested as prose already, 80,086 rows over 66,158
domains, so this is a second and better reading of held material. Queued as
`can_domain_registry_notices / whois_creation` at potential 90, the highest in the queue. It is
master-eligible, so it cannot be banked without a decision, and at **0.18 points** it does not change
this round.

## 2026-08-15: priced the .ca registry find, and the hunt's figure was wrong in both directions

Wrote the extractor, which was the only honest way to check the number I had queued four hours earlier
with the caveat that I had not re-derived it. Good thing: **the hunt's 12,893 net-new pairs and 10,785.0
EE matches neither of the two defensible answers.**

Parsed 37,575 notices carrying both fields into **36,892 in-window items, 36,133 distinct pairs over
35,895 domains, of which 24,715 are already held.** Then priced against the live store:

| reading | net-new pairs | equivalent-English |
|---|--:|--:|
| as a self-dating registry record, no split | **11,418** | **9,551.2** |
| if it takes the corroboration split | **936** | **783.0** |

**A 12.2x spread on a single classification decision**, which is the exact situation CLAUDE.md warns
about: which class a source belongs to is a decision rather than an attribute, and asserting it
batch-wide is how a good source gets filed as rejected, or a weak one waved through. The argument for no
split is that the registry generated the notice about its own namespace and stamped it with its own
`Date-Approved:`, which is machine-generated rather than human-typed. The argument for the split is that
it arrives as a Usenet post like everything else in that corpus. **I am not deciding it**, and the entry
now carries both numbers with the decision named.

**Two warnings the pricing turned up that no amount of enthusiasm should survive.** The post-split years
are 1996: 2, 1997: 53, 1998: 630, 1999: 251, with **nothing at all in 2000 or 2001**. And the typo bound
is bad: **375 of 1,500 sampled net-new names, 25.0%, are one edit away from a name already held.** For a
registry feed that should be near zero, so either the parse is picking up corrections and re-posts, or
the corpus carries typo'd re-transmissions.

Potential lowered from 90 to **55**, and it drops from first in the queue to below the two statutory
returns. Even the generous reading is **0.153 points** and the strict one is 0.013.

The lesson is the cheap one and I keep relearning it: **the extractor is the measurement.** A structural
check told me the fields were there, which is necessary and nowhere near sufficient; only parsing them
and differencing against the store said what they are worth, and that took twenty minutes.

## 2026-08-15: Sunday's covering email drafted as a template, not as prose with numbers in it

The interim went out as two documents on Ivo's instruction: a short email that is only the figures, and
the report carrying the method. Sunday needs the same pair and only the report existed, so
`private/final-email-20260816.md` is now drafted. Git-ignored, confirmed by `git check-ignore`, so it
cannot ship.

**Written with `[TOKEN]` placeholders rather than numbers**, deliberately. Anything I typed today would be
a remembered figure by Sunday evening, and this project's own rule is that the round's numbers come from
the store at ship time. The tokens match what `report_figures.py` already produces, so the email and
`docs/report.md` can be filled from the same run and cannot disagree with each other.

**It also carries the verification step, because he checked it last time.** `round_figures.py --verify`
runs his own calculator over our increment and refuses the numbers if his total differs or his validator
rejects a record we counted. Confirmed the flag exists rather than assuming it: the tool's own help
describes it. The email quotes the difference and the rejection count, as the interim did.

**And it states the shortfall in one sentence and points at the report** rather than arguing in the
email. The rule was that the email is only the numbers; a submission that is short of the expectation
still has to say so, but the reasoning belongs where there is room for it.

A checklist sits at the bottom: ship green, calculator verified, figures from one run, the `.docx` built
because that is the format he asks for, and the archive's SHA256 recorded. The one judgement left in it is
Ivo's, whether the promotion tranche is banked first, which moves the increment by about 1.1 points.

## 2026-08-15: pre-flight on the two Sunday steps that have never been run end to end

Everything on Sunday's checklist has been rehearsed except the last two, so they were run today rather
than discovered at 18:03 tomorrow.

**The `.docx` builds and nothing internal leaks into it.** `pandoc` is present, and
`build_report_docx.py` turned the current `docs/report.md` into an 18,673-byte `.docx` with a 15,528-byte
sendable markdown beside it. The check that mattered was not that it built but what survived: grepped the
sendable copy for `ivo`, `key-decisions`, `notes.md`, `approved-sources`, `triage`, `promotion`, `agent`,
`prospector`, `heartbeat` and `cron`, and **found none of them**. Nine lines were stripped, which is the
generated-figures status block, and all five report sections came through intact. So the document that
would reach the reviewer contains the round and none of the machinery that produced it.

That is worth having checked rather than assumed, because the report now discusses the harness at length
in section 2 and it would have been easy for an internal reference to ride along.

## 2026-08-15: patents screened and deprioritised, labelled as a projection rather than dressed as a measurement

Screened URLs cited in US patents, 1996-2001. **No collision in the register**, so new ground, and the
data really is free and bulk-downloadable from USPTO.

**It fails on the authority rule before it fails on volume**, which is why it did not need a request.
`discovery.md` section 4: a source that selects for authority cannot be net-new, however large. A cited
reference in a patent is the definition of an authority-selected population, and that shape has already
collapsed 7.1M Usenet relay hops into 4,736 domains and returned 2 net-new pairs from 11 archived BUBL
LINK pages. On top of that it is `typed`, so the corroboration split applies, and the extraction cost is
many gigabytes of full text per year for an expected yield in the hundreds of pairs.

**Recorded as a projection and labelled as one inside the entry.** The register's standard is
measurement, and most of it is measurement; writing a reasoned estimate in the same voice would let a
later reader take it for one. The entry also names the only reopen worth having: a **pre-extracted**
dataset of patent-cited URLs, which would make pricing cheap. Explicitly not a reopen: the bulk data
being available, because it always was, and availability was never the objection.

This is the second closure this round that cost nothing because the structural question was asked first.
The blocklists died on the unit, patents die on the population.

## 2026-08-15 09:16: the Sunday forecast revised down, because the rate I forecast with no longer holds

Two point readings looked like a slowdown, which is not a rate, so I measured it properly from
`verified_at` over four windows:

| window | equivalent-English | rate |
|---|--:|--:|
| last 3h | 1,306.6 | 435.5 /h |
| last 6h | 4,469.3 | 744.9 /h |
| last 12h | 5,822.3 | 485.2 /h |
| **last 24h** | **9,916.5** | **413.2 /h** |

The short windows swing because banking is granular: a 70-minute batch lands all at once, so a 3-hour
window catches one or two. **The 24-hour figure is the one to use, and it is 413 EE/h against the 624 to
665 measured yesterday**, a decline of roughly a third.

**Revised forecast, replacing the 2.42% recorded this morning:**

| | equivalent-English | growth |
|---|--:|--:|
| now | 129,913.6 | 2.0865% |
| Sunday at the measured 413 EE/h | ~143,400 | **~2.30%** |
| Sunday with the promotion banked | ~214,300 | **~3.44%** |
| 5% would need | 311,319.3 | 5.00% |

**Two causes and I will not hide behind either.** The archive is refusing more of our traffic, 41% of
records in the current batch against 17% a day ago, which is outside our control. And I spent two batches
proving a tuning change wrong and reverting it, which is not. Both are in the same number.

The honest reading is that the earlier 2.42% was a projection built on a rate that had already started
falling when I quoted it, which is precisely the failure this project's own rule about projections exists
to prevent. **A projection is only as current as the rate underneath it**, and that rate needs
re-measuring before each restatement rather than carried forward.

## 2026-08-15: the decline is diagnosed, it is entirely the archive, and there is no lever left

Separated the two possible causes of the rate falling from 640 to 413 EE/h, which I should have done
before touching anything yesterday.

| engine | requests/h | with a capture |
|---|--:|--:|
| `cdx_pool`, prior 24h | 675 | 42.3% |
| `cdx_pool`, last 24h | **450** | **29.4%** |
| `cdx_q1` on the VPS, prior 24h | 312 | 85.8% |
| `cdx_q1` on the VPS, last 24h | 275 | 84.5% |

**The VPS is untouched**, 12% off on throughput and flat on yield, which is noise. **The whole decline is
the local engine**, and it lost throughput and apparent yield together: 675 to 450 requests an hour, and
42.3% to 29.4% carrying a capture, so captures fell 6,847 to 3,178, a 54% collapse.

**The apparent yield drop is not a worse queue, and that distinction matters.** A refused request
journals with an empty year list, so it counts as "no capture" in any file-level measure. `just cycle`
measures the hit rate among **answered** requests only, and there it reads **67.1% against a 42.4%
lifetime average**, which is up rather than down. So the candidates are fine; a third of the questions are
simply never getting an answer.

**Which means the diagnosis is complete and unwelcome: it is the archive, not the queue and not our
tuning.** The two engines share a queue-building method and differ only in which IP they ask from, and
only the one asking from this host degraded.

**And there is no lever left, which is worth stating positively rather than as a shrug.** Fewer workers
was measured worse yesterday. A shorter timeout is measured and rejected in `cdx.py`, 51 of 100 answered
at 30 seconds against 82 of 100 at 180. Raising the delay floor cannot do anything because the adaptive
governor already sits pinned at its 3.0 second ceiling. Every knob is either tested, documented as
counterproductive, or already at its limit. **So the right action is none**, and the round takes the rate
it is given.

## 2026-08-15: the report's one hand-written paragraph rewritten as a trend

The throughput paragraph in report section 1 was the only place in the document carrying figures that
`fill_report.py` does not own, and I dated them deliberately so they could not read as current. Two days
later they had drifted anyway: 975 requests an hour between the collectors is now nearer 725, and "437 of
600 refused" understates what the engine is now seeing.

**A dated snapshot is honest and still ages badly**, because a reader takes the most recent thing in front
of them as the state of the world whatever date is attached. So the paragraph now states the **trend**
instead, which is both more robust and a better argument: 675 to 450 requests an hour and 42.3% to 29.4%
answered on the host that degraded, against 312 to 275 and 85.8% to 84.5% on the host that did not. **The
two engines share their target-selection method entirely and differ only in where they ask from**, which
is what identifies the archive rather than our queue or our tuning, and that is a stronger claim than any
single-day number.

It also now records that the two obvious remedies were tried and rejected on measurement: reducing
concurrency was worse, and shortening the timeout is rejected in our own code at 51 of 100 answered
against 82 of 100. A reviewer asking "why did you not simply slow down or time out sooner" has both
answers in the document.

Added to the Sunday checklist as the one paragraph to re-read before sending, precisely because a stale
hand-written number would sit beside generated ones and look equally authoritative.

## 2026-08-15: the domain aftermarket, screened, queued and deliberately not probed

Screened the 1999-2001 domain aftermarket, GreatDomains and early Afternic. The screener raised two
collisions and **neither is the population**: a zone file is a registry dump, a Netcraft page is a survey
of live servers, and a for-sale listing is marketplace inventory. Recorded that distinction beside the
proposal, which is what the screener asks for.

**It has the property the register keeps rewarding.** A speculative or parked name is registered and was
never built out, so no crawler captured it, which is precisely why the dispute dockets measured 87.7%
net-new, the highest of any source assessed here.

**And it has the property that killed Netcraft, more strongly.** Netcraft's names failed the
contemporaneity test: a name printed on a page captured in 1999 was no likelier to hold a 1999 capture
than a name with no claim to 1999 at all. A parked for-sale domain has *less* to capture than a surveyed
live server, so the same instrument would very likely reject it as master too. The honest expectation is
candidate-only, which is pool growth, and the pool is not the constraint.

**Not probed, and the reason is not caution but arithmetic.** Pricing it needs Wayback requests, and the
archive is currently refusing about a third of our collector's. Spending requests on a lead whose most
likely outcome is candidate-only, while the engine that produces actual equivalent-English is being
refused, is the wrong trade. Queued at potential 40 with the next step named: run the three-instrument
test that settled Netcraft **before** any extraction, not after.

That ordering is the lesson from Netcraft itself, where the extraction was faithful and it was the
inference from listing to liveness that failed. Extracting first would have produced a large, correct,
worthless number.

**Postscript, same entry.** The commit was refused by the pre-commit hook: `test_the_live_queue_is_in_order`
failed, because I appended the new entry at the head of the section and a potential of 40 landed above an
88. That test exists for Ivo's instruction of 2026-08-12, "always sort the open sources by potential, such
that I sign-off more promising sources first", and it checks the **live file** rather than a fixture, so a
hand edit that breaks the order fails the suite. Fixed by running `rank_triage.py`, which is the tool that
owns the ordering; 49 entries, highest first, `--check` clean.

Worth noting which safeguard caught it. Not the ordering tool, which I did not think to run, and not me
re-reading the file. **The gate refused the commit**, which is exactly the argument for having made it a
hook on 2026-08-13 rather than a rule to remember, after the rule was broken twice in one round.

## 2026-08-15 10:00: throttles doubled again, and the citizenship trade is now worth stating

The newest finished local batch: **600 queries, 1,830 throttles, 188 outright failures (31%), the delay
pinned at 3.0s.** Throttles have doubled since this morning's 896 and quadrupled since yesterday's 417.

**The queue is not the problem and the batch proves it.** Of the 412 queries that were answered, **312
carried a capture, 75.7%**, which is the best hit rate this engine has recorded. The candidates are good.
A third of the questions never get an answer.

**The arithmetic that makes this worth raising rather than just recording.** To get 412 answers the engine
generated roughly 2,430 HTTP requests. Over the 30 hours to delivery the local engine is worth about
450 requests an hour at 0.39 equivalent-English each, so **its entire remaining contribution is around
5,300 EE, or 0.085 percentage points.** That is the return we are buying with three throttled requests per
answer against an archive that has refused this project outright three times, and that refused a second,
entirely legitimate client from this host every one of 12 attempts today.

**I am not changing it, and the reason is not confidence.** Every lever is tested: fewer workers measured
worse, a shorter timeout is measured and rejected in `cdx.py`, and the 3.0s delay ceiling is itself a
deliberate throughput-over-politeness choice made on 29 July when a 5s pin dropped a run to 240 domains an
hour. Raising the ceiling is the one untried move and it is untried because the project already measured
what it costs.

So this is a values question rather than a technical one: **0.085 points against a load profile that is
visibly antisocial**, on a standing rule that is Ivo's, not mine. Recorded here and flagged to him. The
VPS is on a different host, so stopping the local engine would not touch the 84.5%-hit engine that is
doing the better work anyway.

## 2026-08-15: "flagged to him" was not true, and the fix is one line of process

Last entry ended "recorded here and flagged to him". **Only the first half was true.** It went into
`notes.md`, which is the agent's own working and which Ivo does not read. `key-decisions.md` is the single
surface that asks him for anything, and CLAUDE.md is explicit that putting a question anywhere else is the
same as not raising it.

This is the exact failure `key_decisions.py` was written to prevent, described in its own module
docstring: **a question raised in a file nobody reads is not a question asked, and worse, because the
asker believes it was.** I wrote a careful analysis, told him it was flagged, and left it where he would
never see it.

Now an `## OPEN` entry: 1,830 throttles and 188 failures per 600 queries, 2,430 HTTP requests for 412
answers, buying about 5,300 EE or 0.085 points over the remaining window, against an archive that has
refused this project three times and that today refused a second legitimate client from this host on all
12 attempts. Every technical lever is closed, so the question is only whether that trade is acceptable,
and "be a good citizen" is his standing rule rather than mine to overrule. The engine keeps running while
it waits, and the entry says so.

**The general lesson, which is cheap and I keep paying for it anyway:** writing a good analysis is not the
same as delivering it, and "flagged" is a claim about the reader rather than about the writer.

## 2026-08-15: the review surface had grown to six screens, and shrinking it nearly broke the mirror

`key-decisions.md` is described in its own header as a two-minute review surface, "one entry, one screen
at most". Measured: **6 entries, 195 lines, 2,166 words**, five or six screens. I wrote nearly all of it,
each entry reasonable on its own, and the aggregate is a document nobody opens the evening before a
delivery. Rewritten to **59 lines and 538 words**, a quarter of the size, each entry now the decision, the
number and a pointer to the working in `notes.md` where it already lives. Also corrected a stale figure in
a heading: the promotion entry still said 110,409 pairs after the count was corrected to 106,604.

**And the rewrite nearly did real damage.** I retitled the triage entry to something clearer, and the
suite refused the commit. `_mirror_triage_count` finds that entry by the literal `TRIAGE_HEADING`, so a
renamed entry is invisible to it: `refresh_open` would have missed, `raise_open` would have succeeded, and
the hourly cycle would have written a **second** triage entry onto the surface I had just spent the wake
shrinking. The test read "44 sources sit in the triage queue with no collective entry", which is exactly
right and looks nothing like "you renamed a heading".

**The underlying defect was a duplicated literal**, the phrase living both in `discover_cycle.py` and
again in the test. So the test now imports `TRIAGE_HEADING` rather than repeating it, and a future rename
fails in one place with an obvious message instead of two places with a misleading one. The live title
keeps the phrase and adds the count.

Third time this round the pre-commit hook has caught something my own reading did not: a red gate on
2026-08-13, the triage queue sorted wrongly this morning, and this. The argument for making it a hook
rather than a rule keeps paying.

## 2026-08-15: compacting the surface by hand would have lasted an hour

Caught this before the cycle did it rather than after. The triage entry I shortened last wake is **owned
by `_mirror_triage_count`**, which rewrites it every cycle with its own text, so my compact version had
about an hour to live. Shrinking the surface by hand and leaving the generator verbose is not a fix, it is
a fix with an expiry.

So the generator's body is now the compact one: five lines carrying the count, the reason it is not a
request, and where to look, replacing four paragraphs. The comment above it says why the length is a
standing choice rather than a one-off, because this entry is rewritten every hour and its size is a
recurring tax on the one surface Ivo reads.

Applied once by hand to check: the OPEN block sits at **58 lines and 583 words**, against 195 and 2,166
yesterday. Loop restarted so the running copy carries the new text, which is the trap this file already
records: **a long-running loop keeps the code it started with**, and on 2026-08-13 that difference flooded
this same surface with 25 entries an hour.

The general shape is worth keeping: **when a surface is generated, edit the generator.** Editing the
output is the same mistake as hand-writing a figure into `report.md` instead of letting `fill_report.py`
own it, and this project has a rule against that one already.

## 2026-08-15 10:45: the rate recovered, nothing we did caused it, and that is the point

The banking rate doubled over six hours, 819 EE/h against a 24-hour average of 420. Traced it rather than
celebrating it.

**It is not throughput and it is not the queue. The archive simply answered more of what we sent.**

| window | `cdx_pool` requests | captures | hit rate |
|---|--:|--:|--:|
| 6h before last | 2,660 (443/h) | 519 | 19.5% |
| last 6h | 2,141 (**357/h**) | **934** | **43.6%** |

The local engine made **fewer** requests and got **nearly double** the captures. A refused request
carries no capture, so a hit rate that doubles while throughput falls means refusals collapsed. The VPS
was flat throughout, 250 requests an hour at 83%, which is the control that makes this specific to the
throttled host.

**This confirms yesterday's diagnosis from the other direction.** I concluded the decline was the archive
rather than our tuning, and stopped turning knobs. The recovery happened with **no change on our side at
all**, which is the evidence that the earlier decline was not something we caused and not something we
could have fixed. Both the fall and the rise belong to the archive.

**So the forecast is a range, and quoting a point estimate would be false precision:**

| | Sunday equivalent-English | growth |
|---|--:|--:|
| at the 24h rate, averaging both regimes | ~143,700 | **~2.31%** |
| at the last-6h rate, favourable regime | ~156,200 | **~2.51%** |
| either, with the promotion banked | ~214,600 to ~227,100 | **~3.45% to ~3.65%** |

The 24-hour figure is the one to plan on, because it averages a good regime and a bad one and we do not
control which we get. The six-hour figure is what happens if the archive stays generous.

## 2026-08-15: trademark filings screened and closed, and the second reason is the interesting one

Screened US trademark filings for domain-name marks, 1998-2001. No collision, and the bulk XML really is
free and complete. Closed without a request on two grounds, both labelled as reasoning rather than
measurement.

**The first is the patent objection repeated**: a trademark application costs money and legal work, so the
population is businesses notable enough to file, which is authority selection, which `discovery.md` closes
by rule.

**The second is specific to this source and is the better objection.** A mark may be filed on an
*intent-to-use* basis, which evidences an intention and not a live domain. Only a *use-in-commerce* filing
with a specimen attests that the site existed on the filing date, and telling the two apart means reading
the filing basis per record. **The cheap version of this source would assert years its own evidence does
not support**, which is exactly the error the `link_target` class exists to prevent. An abandoned
application is worse than useless here: it is weak evidence in the wrong direction, since a company that
filed for a name in 1999 and abandoned it may never have built the site.

Both entries now name the same narrow reopen: **a pre-extracted dataset**, not the bulk data being
available, because availability was never the objection and saying so stops the next pass re-probing it.

Three closures in three wakes, none costing a request: blocklists on the unit, patents on the population,
trademarks on the population and the dating basis. That is what the register is for, and the pattern
across all three is the same question asked first: **what would date one item, and what population does
this select?**

## 2026-08-15: the aftermarket lead measured for free, and my prediction about it was wrong

Went looking for other registry-like feeds inside the Usenet corpus, the way `can.domain` turned up, and
found something better: **`alt.domain-names.forsale`, `.registries`, `.wanted` and `.disputes` are all on
disk**, which is the domain-aftermarket lead I queued two wakes ago and deliberately did not probe because
pricing it needed Wayback requests. The Usenet half of it needed none.

**All four are already ingested**: 30,552 evidence rows over 27,055 domains from `forsale` alone, 36,425
rows and about 32,685 domains across the four. Same conclusion as the blocklists, reached the same cheap
way: the good half of the idea arrived with the Usenet corpus years ago.

**And the population behaves the opposite of how I predicted.** When I queued the lead I wrote that a
parked for-sale domain "has less to capture than a surveyed live server", so it should date worse than
average. Measured: **23.0% of for-sale domains hold a year against 10.3% of all Usenet-mentioned domains**,
2.2x more likely, not less.

**Then the obvious confound, tested rather than left as a happy result.** 14.6% of for-sale names are in
the reviewer's baseline against 4.8% of Usenet mentions, a 3x gap: those groups discuss famous domains as
much as they trade obscure ones. Net of baseline the advantage is about 1.5x, real but modest, and far
from the story the raw 2.2x tells.

Entry updated from potential 40 to **22**, with the measurement replacing my speculation, and re-ranked.
The lead is not dead but its remaining value is only whatever the web listings add beyond a population
already worked.

**The wake's own lesson: I nearly spent archive requests on a question the disk could answer.** The
instinct to reach for the network before the store is the same one that cost two requests re-deriving a
register entry yesterday, and free evidence has now beaten paid evidence three times in two days.

## 2026-08-15: promoted "ask the disk first" from the log into the method

The lesson has now paid three times in two days and it lived only in `notes.md`, which is 7,000 lines and
grep-only. `discovery.md` is what a pass actually reads before proposing a source, so it is now section
4a there, with the three cases as evidence rather than as advice:

- **blocklists**: the domain-bearing half was 13 `news.admin.net-abuse.*` groups on disk, 173,526 rows
  over 168,075 domains
- **the domain aftermarket**: four `alt.domain-names.*` groups on disk, 36,425 rows over ~32,685 domains,
  and measuring them moved the lead from potential 40 to 22
- **the CA Domain Registry**: `can.domain.mbox.zip`, already held, 37,578 `Date-Approved:` fields

**The general form is the part worth keeping**: a question about a *population* is usually cheaper to
answer than a question about a *source*. "Do names of this kind earn years?" is one query against the
store. "Does this website still exist?" costs a request and answers a worse question. And the store
answers honestly about overlap, which is the number that decides everything here and the one a fetch never
tells you.

The section closes with the corollary that has cost the most this round, all three instances of it in one
line: **`LIMIT 4` is not a census, a heading is not a schema, and a maximum index is not a count.**

Placed as 4a rather than appended, because it belongs immediately after "measure against the store" and
before "check it is not already dead": the order of the sections is the order of the work.

## 2026-08-15: a residual check that came back empty, recorded so it is not asked again

Applied section 4a to the store rather than to a source: **is any evidence we already hold undated, or
dated outside the window?** If so it would be free yield.

**It is not. 54,076,874 evidence rows, 0 with a null year, 0 outside 1996-2001**, and 0 domains carrying
an out-of-window master row while holding no in-window year at all. The loader only ever writes in-window
dated rows, so the population this question imagines does not exist.

A clean negative in one query, and worth a line precisely because it is clean: the next pass wondering
whether there is undated evidence to rescue can read this instead of writing the query. **Recording a
definitive nothing is cheaper than rediscovering it.**

Not making it a tenth invariant in `ark check`. The loader guarantees it structurally, and an invariant
that can only fail if the loader is rewritten is a test of code that does not exist yet.

Cron confirmed at both jobs: the recurring wake, and the one-shot at 18:03 tomorrow that ships rather than
collects. That check is on Ivo's instruction of 2026-08-12 to make it part of every call, after several
hours once passed with no wake he could see.

## 2026-08-15: multi-source attestation predicts a CDX hit 6.6x, and the queue does not use it

Asked the store the population question the RDAP builder already acts on but the CDX queue does not:
**does the number of distinct sources attesting a pool name predict whether the archive holds it?**
Measured over the 77,054 pool domains this engine has ever asked:

| distinct sources | asked | hit rate |
|---|--:|--:|
| 1 | 35,485 | **14.8%** |
| 2 | 24,565 | 48.7% |
| 3 | 9,468 | 87.4% |
| 4 | 4,188 | 94.4% |
| 5+ | 3,348 | **98.1%** |

**A 6.6x spread, unambiguous at that sample size.** `build_rdap_pool_list.py` already uses this as a
tiebreak, on the reasoning that "a name three independent collectors saw is far likelier to be a real
registration than one that appeared once in one Usenet message". The CDX queue scores per (source, TLD)
and per-TLD plausibility, both good, but a domain enters its model under **one** source, so the *count*
is invisible to it.

**The headroom, which is the number that decides whether this matters:**

| sources | unasked | expected EE per query |
|---|--:|--:|
| 3+ | **11,919** | **0.87** |
| 2 | 213,386 | 0.44 |
| 1 | 2,250,254 | 0.16 |

The engine currently returns about **0.39 EE per request**, so the 11,919 best names are worth **2.2x the
marginal query**, and their still being unasked after 77,054 queries is itself the proof the queue does
not rank on this.

**Worth about 0.09 points, and I am not changing the queue builder tonight.** 11,919 queries is roughly
the whole remaining window at the current rate, so capturing it fully would yield ~10,400 EE against
~4,600 on the present mix. That is real and it is also a twentieth of the gap. Against it: this is the
program that feeds the engine 28 hours before a delivery, I have already spent two batches today proving
one tuning change wrong, and the failure I would be risking is subtler than a crash. **The finding is
worth more than the 0.09 points**, because it is a permanent property of the data and belongs in the next
round's queue rather than in a rushed edit to this one.

Recorded here and left as the top item for whoever builds the next queue: **add distinct-source count as
a factor in `pool_plausibility`, not a tiebreak.** The effect is far too large to be a tiebreak.

## 2026-08-15: correcting my own claim about the queue, with the number I should have taken first

I wrote that the 11,919 unasked multi-source names "prove the queue does not rank on this". **Too strong,
and I checked it because it was the load-bearing sentence.** The queue does favour them, mildly:

| sources | in pool | asked | share asked |
|---|--:|--:|--:|
| 1 | 2,298,191 | 47,937 | **2.1%** |
| 2 | 233,724 | 20,338 | 8.7% |
| 3 | 13,005 | 1,492 | **11.5%** |
| 4 | 503 | 126 | 25.0% |
| 5+ | 36 | 7 | 19.4% |

A 5.5x preference for three-source names over one-source names, so the per-(source, TLD) scoring
correlates with source count without naming it. **The claim should have been that the queue
under-weights the signal, not that it ignores it**, and the gap between those two statements is the whole
argument: a 5.5x ranking preference against a 6.6x difference in outcome is close enough to look
deliberate and far enough to leave 11,500 names at 87% expected hit sitting unasked.

**A second thing the first measurement got wrong and this one exposes.** My earlier count found 17,004
asked domains with 3+ sources; this one finds 1,625. Both are right, and the difference is the point:
**a domain that was asked and hit is no longer in the pool.** The first query joined asked-domains to
source counts across all evidence, so it counted the successes that have since graduated. Measuring a
queue's coverage against the population it still faces is a different question from measuring it against
everything it ever touched, and I asked the second while believing I had asked the first.

Decision unchanged: **not editing the queue builder 28 hours before delivery** for 0.08 points, with two
failed tuning changes already today. But the recommendation for the next round is now sharper: the signal
is present in the ranking at roughly 5.5x and needs to be present at roughly 6.6x, as an explicit factor
in `pool_plausibility` rather than as whatever correlation the per-source rates happen to carry.

## 2026-08-15 12:00: one VPS journal home, and the round crosses 2.10%

Routine wake. `just engines` reported **1 of 325 VPS journals missing**, fetched immediately rather than
left for the next pass, which is the standing rule after 5,793 records once sat stranded on that machine
for a day and a half. Banked directly: 300 journal lines, **892 evidence rows, 278 year rows over 254
unique domains**, 36 queries that failed on the VPS side and will be re-asked because a transport failure
is not treated as settled.

Round now **210,156 pairs, 150,863 net-new domains, 130,875.0758 equivalent-English, 2.1019%.** All five
processes healthy.

Worth noting what the single-journal gap means and does not mean. It is not a fault: the VPS writes
locally and the copy is pulled on a check, so at any moment the newest finished journal is usually still
over there. **The reason to fetch it anyway is that the machine is private and the VPN is not always
up**, so the cheap move is always to take whatever is available while the window exists rather than to
reason about whether it matters.

## 2026-08-15: the RDAP sweep was five batches from stopping, and my estimate of what is left was 3.9x optimistic

Checked how far through its list the registry sweep is: **27,358 of 149,816 targets left, 18.3%**, about
five batches. `rdap_pool_sweep.sh` **stops when its list runs out**, so it would have gone quiet around
21:00 tonight with twenty hours still to run, and nothing would have reported that as a fault because a
finished sweep looks exactly like a healthy one that has nothing to do.

**So the TLD set is widened, in the generator rather than in the file**, which is this morning's lesson
applied: `discover_cycle.py` rebuilds that list hourly, so editing the list alone would have lasted an
hour. Five TLDs had a measurable in-window rate when the restriction was written; **122,458 queries later,
twelve do.** `.sg` is the pick at 28.6% in-window on weight 0.9476. `.uk` stays out for Nominet's terms
rather than for arithmetic.

**And my own estimate of the remaining value was wrong by 3.9x, which is the part worth recording.** From
the journals I priced the non-`.uk` remainder at **3,648 EE**. The builder, which owns this calculation
and has been calibrated against exactly the failure I was reproducing, prices the rebuilt 46,590-target
list at **931 EE, 0.020 per query.** The gap is that I used raw per-TLD rates while the builder applies
its minimum-sample rule and its fabricated-namespace discriminator. **When a tool exists for a
calculation, its number is the number**, and a quick query that disagrees with it is evidence about the
query.

So the honest position: the sweep keeps working for roughly fifteen more hours and will return about
**931 EE, 0.015 points**. That is worth having because registry queries cost the archive nothing, and it
is not worth more than that. Loop restarted so the running copy carries the wider set.

## 2026-08-15: a 3.5M-domain "unexploited population" that the design correctly excludes

Asked a population question that looked like a large miss and turned out to be a measured design choice.
Recording it because the parameter underneath it is one I did not know and should have.

**The apparent finding.** 3,472,376 domains hold a year and have **never been asked at the archive**, of
which 2,647,398 hold exactly one year. A single-year domain has no bracketed gap, so `ark gaps` excludes
it by construction, and it is not in the pool because it is dated. Invisible to both engines. Weighted, the
population is 1.37M equivalent-English if every one of them gained a year.

**The parameter that dissolves it.** A CDX query does not return a domain's whole history. Measured over
the 2,242,775 domains that have CDX evidence:

- **mean 1.20 in-window years returned per domain, median 1**
- **90.3% returned exactly one year**, only 5.7% returned three or more
- and of 2,697,841 CDX (domain, year) observations, **just 1.5% were years no other evidence type
  already held**

So querying a single-year domain would mostly return the year we already have. The expected net-new is a
fraction of a pair per request, well under the pool engine's 0.39 equivalent-English and far under the gap
engine's.

**Which is exactly why `ark gaps` targets brackets.** Its own docstring says the bracketed set "is the
population an archive query addresses", and the queue builder carries measured fill rates of 0.886 for a
one-slot domain and 0.667 for a two-slot one. A bracket gives the query a specific missing year to fill;
an unbracketed domain gives it nothing to aim at. **I had read that sentence as a scoping convenience and
it is a measurement.**

Cost: three queries against the store, no requests, one idea tested to destruction in a wake. The general
form is the one from section 4a: **a population question is cheap, so ask the expensive-looking idea
early rather than saving it.**

## 2026-08-15 12:40: every engine's stopping condition checked against the delivery, not assumed

I have said "the engines carry absolute deadlines and outlive Sunday" several times without once reading
the numbers back. Read them:

| engine | stopping condition | outlives Sun 18:03? |
|---|---|---|
| local `supervise_cdx_pool` | epoch 1786924800 = **Mon 17 Aug 02:00 CEST** | yes, by 32h |
| `discover_cycle` | same epoch | yes |
| VPS `cdx_q1` | epoch 1788177600, **31 Aug** | yes, by 15 days |
| `rdap_pool_sweep` | 120 batches, or its list running out | yes on count; the list was the real risk and was widened this morning |
| `maintain.sh` | **900 iterations**, not a deadline | yes: 42 passes in 6.07h is 8.7 min each, so 900 is **5.4 days**, and Sunday needs 203 more of the 858 left |

**The ingest loop was the one worth checking** and the only one whose limit is a count rather than a
clock, which is exactly the case `extend_engines.sh` documents as needing a handover if it is ever started
with a smaller count than the window. It was restarted by `just ship` this morning with the recipe's own
`900 150`, and at the measured 8.7 minutes a pass that is four times the remaining window.

Nothing needed doing, which is the point: **an unverified assurance and a verified one read identically
until the day they do not.** The RDAP list was the same shape of risk this morning and did need doing.

## 2026-08-15: "measured 0% in-window" and "the registry never answered" are different facts

Checked whether the zero in-window rates I recorded for the high-weight ccTLDs rest on a real sample.
They rest on something else entirely.

| tld | asked | HTTP 200 | carried a creation year |
|---|--:|--:|--:|
| `.au` | 39,371 | **130** | **0** |
| `.de` | 4,380 | 0 | 0 |
| `.dk` | 1,620 | 0 | 0 |
| `.jp` | 1,471 | 0 | 0 |
| `.it` | 1,111 | 0 | 0 |
| `.se`, `.nz`, `.at`, `.us`, `.za`, `.ie` | 183 to 850 each | **0** | 0 |

**None of these registries answers RDAP at all.** So "0.0% in-window" does not mean the names were not
registered in the window; it means the question never landed. I had written those zeros into a ranking
table as though they were measurements of the population, and they are measurements of the service.

**The distinction matters because the two imply opposite actions.** A genuine 0% rate says stop asking:
the population is fabricated or out of window, which is the `.mil` and `.gov` case the queue builder
already handles. A 0% *answer* rate says the population is untested and must be reached another way, and
`.au` at weight 0.9904 with 33,058 unasked names is exactly that: unreachable by registry, perfectly
reachable by the archive, and therefore a pool question rather than an RDAP one.

**The live list is clean**, checked rather than assumed: `nl` 15,923, `org` 11,617, `fr` 8,411, `pl`
2,821, `no` 2,462, `sg` 1,529, `fi` 1,454, `br` 1,340, `ar` 1,028, and no `.au`, `.de` or `.nz` at all.
`build_rdap_pool_list.py` filters on the IANA bootstrap service list, which is the right discriminator and
was already doing this job.

The sunk cost is worth naming so it is not repeated: **39,371 `.au` queries returned 130 answers**, from a
wide sweep before the bootstrap filter was in place. Nothing to recover, but it is the clearest possible
argument for filtering on service before scoring on yield.

## 2026-08-15: the engine will not run out of good targets, and that closes the last open worry

Measured CDX hit rate by TLD over every pool query this engine has made, then crossed it against what is
still unasked. It answers a question I had been carrying implicitly: **does the local engine's yield decay
because the queue head is spent?** No.

Measured hit rates, pool population: `.com` **50.2%** over 17,986 asked, `.uk` **44.5%** over 34,425,
`.org` 42.1%, `.to` 34.0%, `.za` 27.2%, `.nz` 23.2%, `.au` 19.5%, `.ca` 18.1%. And the discriminator
working exactly as designed at the bottom: **`.edu` 0.1% over 3,895 asked, `.mil` 0.0% over 1,394,
`.gov` 0.0% over 665.**

Crossed with what remains unasked, in expected equivalent-English per query:

| tld | unasked | hit | EE/query |
|---|--:|--:|--:|
| `.uk` | 22,742 | 44.5% | **0.677** |
| `.com` | **906,843** | 50.2% | 0.492 |
| `.org` | 294,126 | 42.1% | 0.463 |
| `.ca` | 44,672 | 18.1% | 0.235 |

**Over 1.2 million unasked names at 0.46 to 0.68 expected equivalent-English per query**, against an
engine clearing roughly 400 requests an hour. At that rate even the thin `.uk` slice is 57 hours of work,
which is longer than the window. The queue head is nowhere near spent.

**And the gap between 0.49 and the 0.39 the engine actually returns is the refusals, not the targets.**
A third of requests never land, so the realised yield is the queue's value discounted by the failure rate,
which is precisely what has been measured all day from the other direction.

So the last worry about the final day is closed: **the engine's output is bounded by the archive alone**,
and the 413 to 820 EE/h range is a statement about how generous the archive is feeling rather than about
anything we control or could improve by re-ranking.

Also worth keeping from the same table: `.au` is 19.5%, not the zero its RDAP answer rate suggested. The
two channels disagree about the same 27,000 names because one of them has no service, which is the
distinction from the previous entry made concrete.
