# Internet Digital Ark — Delivery Report

*Reconstructing evidence-backed annual domain lists for 1996–2001.*
Status as of 2026-07-24 (interim). Full decision history: [notes.md](notes.md). Plan: [plan.md](plan.md).

---

## 0. Executive summary

We grow the provided ~8.2M-line baseline with **net-new, evidence-backed** registered domains, shipped as a separate verifiable set (the baseline is never modified). Every annual-file entry is backed by item-level, per-year evidence recorded in a provenance database, so any line can be traced to its proof.

**Scoreboard (2026-07-24):**

| Metric | Value |
|---|--:|
| Net-new registered domains (absent from baseline) | **463,362** |
| Net-new (domain, year) pairs | **1,302,722** |
| Baseline domains (read-only) | 4,824,656 |
| Total domains in store | 5,288,021 |
| Total (domain, year) pairs in store | 8,169,635 |
| Evidence rows | 11,044,356 |

**Net-new (domain, year) pairs by year:**

| 1996 | 1997 | 1998 | 1999 | 2000 | 2001 |
|--:|--:|--:|--:|--:|--:|
| 97,031 | 1,038,067 | 11,384 | 25,697 | 52,415 | 78,128 |

The 1997 figure is dominated by the ISC DNS survey (the baseline barely covers 1997); the thin 1998–2000 years were lifted 5–6× by AFNIC `.fr` and materially by Arquivo `.pt` and the UK Web Archive.

---

## 1. Data definition & cleaning

- **Counting unit — the registered domain** (brief III.8). Every host or URL, from every source, is reduced to its registrable domain before it touches the database, via a canonicalizer built on a **pinned Public Suffix List snapshot** (committed with the package, so extraction is deterministic and offline) plus a documented patch of **retired 1996–2001 ccTLDs** (`.yu`, `.an`, `.cs`, `.gb`, `.tp`, `.zr`, …) that the modern PSL dropped. `www.example.com`, `foo.example.com`, and platform user-paths (`geocities.com/…`) all collapse to `example.com` / `geocities.com`.
- **Validity rules.** A name must have a registrable label plus a public suffix; bare suffixes (`co.uk` alone), IP addresses, and syntactically invalid hosts are rejected. Underscores are tolerated in subdomains (common in the era) but not in the registered label.
- **Salvage — conservative, deterministic, audited.** Leading/trailing punctuation is stripped (`.www.foo.com`, `,foo.com`); never leading hyphens (that would alter the name). Every correction and every drop is written to an audit CSV; nothing is guessed.
- **Baseline cleaning results.** 8,218,\* baseline lines → **4,824,656 registered domains / 6,866,913 (domain, year) pairs**. Normalization audit: **~1.45M lines corrected**; droplist: **12,220 dropped** across 5 reason groups (`dropped_domains.txt`, reason-grouped). Originals are never edited — suspect rows are flagged, not rewritten; merged master lists are exports.
- **Deduplication.** Within each year (the `domain_year` primary key is `(domain, assigned_year)`); cross-year duplication is required and expected (a domain appears in every year it is independently evidenced for — brief III.7).

## 2. Architecture

- **Provenance store (DuckDB).** Tables: `source`, `domain`, `evidence`, `domain_year`, `ingested_file`. The **evidence wall** is a database constraint, not discipline: `domain_year.evidence_id` is a `NOT NULL` foreign key into `evidence`, so no annual assignment can exist without a specific evidence row behind it. `assign_year` refuses candidate-only evidence outright.
- **One row per (domain, year) per source.** The `evidence` table records every observation; a pair can carry several rows from several sources. This makes cross-source corroboration free (no schema change) and lets net-new be defined robustly over the evidence table (a pair is net-new iff it is assigned and carries no `prior_reused` evidence).
- **Shared bulk ingester.** Every source is a small parser that yields `(raw, year, evidence_value, evidence_url)`; one audited loader handles canonicalization, set-based staging, evidence + `domain_year` writes, per-source audit CSVs, run metrics, and a **per-file sha256 ledger** (same name + same bytes skips; different bytes fails loudly). Per-file transactions; audit rows are written only after a file commits; a failed file is isolated and the run continues. Adversarially reviewed (3 passes) before first real use.
- **Work queue (SQLite, WAL).** Crash-safe queue for the per-domain verification path; enqueue derives from durable evidence rows, so re-running repairs any crash window.
- **Reproducibility.** `uv` + pinned lockfile + committed PSL; CI runs `ruff check`, `ruff format --check`, `pytest` (114 tests). Raw `uv run …` is the reproducibility contract; a `justfile` wraps it.
- **Integrity gate (`ark check`).** Six read-only invariants over the whole store, exiting non-zero if any is violated: (1) the evidence wall is intact (every assignment points at an evidence row for the same domain and year); (2) no annual assignment is backed by candidate-only evidence; (3) every assigned pair has ≥1 master-eligible evidence row for that exact year; (4) no duplicate (domain, year); (5) every year in 1996–2001; (6) every stored domain is a well-formed registrable name. **All six pass** on the current store (5.28M domains / 8.17M pairs).

### Evidence types (standard of proof; what a negative means)

| Type | One row asserts | Negative means | Disposition |
|---|---|---|---|
| `prior_reused` | Baseline already lists this (domain, year); reused read-only (III.1) | n/a | Master; **excluded from the score** (it is the baseline) |
| `cdx_timestamp` | A web-archive capture (IA / Arquivo) with an in-year 14-digit timestamp + HTTP 200 for the domain or a subdomain | Empty CDX for all six years = never archived in window (not proof of non-existence → stays candidate) | Master; gold standard |
| `artifact_listing` | A line in a **dated data file** whose provenance fixes the year (ISC survey list = survey date; ODP RDF dump = generation stamp) | "Not in that file", weaker than a CDX negative | Master (direct) |
| `link_source` | In a UKWA host-link-graph row `year\|source\|target`, the **source** host was crawled (HTTP 200) that year | n/a (precomputed graph) | Master |
| `whois_creation` | A registry record documents continuous registration spanning the year (creation date + a later withdrawal date or current registration) | Missing/blocked WHOIS proves nothing | Master |
| `dated_directory` | An editorial entry on a directory page captured by a web archive on a known date | "Not listed there", weak | Master (direct) |
| `link_target` | In the same UKWA row, the **target** host was merely linked-to | n/a | **Candidate-only** — never assigns a year |

**Evidence-standard ruling (Prof. Ding, 2026-07-24):** valid year evidence is not limited to web captures. Dated DNS surveys, archive indexes, host/link graphs, dated directory/index files, and WHOIS registration records all count as direct annual evidence, provided the year association is explicit and documented and the provenance (source name, dataset date, assignment method, record id) is retained. Our store retains all four fields per row.

## 3. Sources & methods

All figures are net-new **on top of the baseline** (measured per source; see notes.md for full method + caveats).

| Source | Evidence type | Years | Net-new domains | Net-new pairs | Note |
|---|---|---|--:|--:|---|
| IA Early Web CDX | `cdx_timestamp` | 1996–1999 | +175 | +182 | 99.99% baseline overlap → **the baseline is IA-derived** |
| ISC / Network Wizards DNS survey | `artifact_listing` | 1996–1997 | ~+397k | ~+1.13M | Largest tranche; DNS-observed, IA-independent; 1997 alone +1.03M |
| Arquivo `Roteiro` | `cdx_timestamp` | 1996 | +0 | +7 | 1996 already dense; corroboration |
| Arquivo `IA.cdxj` | `cdx_timestamp` | 1996–2001 | +6,715 | +17,689 | 98% `.pt`; thin years (1998 +89%, 1999 +165%, 2000 +183%) |
| UK Web Archive host link graph | `link_source` | 1996–2001 | +15,822 | +23,821 | mostly `.uk`; thin later years |
| AFNIC `.fr` open data | `whois_creation` | 1996–2001 | +39,367 | +117,829 | registration-interval; thin years **5–6×** |
| ODP / DMOZ dumps | `artifact_listing` | 2000–2001 | +3,339 | +8,423 | heavy baseline overlap; mostly 2000 |
| Internet Scout archive | `dated_directory` | 1996–2001 | +137 | +311 | curated non-IA long tail; most records undated |
| RDAP on UKWA link-targets | `whois_creation` | 1996–2001 | +831 | +2,320 | **Phase-4 engine**: undated candidates dated via RDAP, no CDX |

**Key strategic finding:** the baseline is Internet-Archive-derived (Early Web CDX overlapped it 99.99%). Net-new volume therefore comes from **non-IA sources** — DNS surveys (ISC), national registries (`.fr`), and national web archives (`.pt`, `.uk`) — which is also why the additions are geographically complementary.

**Candidate-vs-verified routing (brief III.4).** Sources without item-level year labels — StanfordWebBase/webbase, undated DMOZ, raw URL lists, UKWA link *targets* — are treated as **candidate seeds**, never written to annual files without per-item verification. Currently the candidate pool is small (3); the large candidate ingests are queued for the Phase 4 verification engine.

**Novel methods / directions pursued.** (a) A one-day live-verified **bulk-source survey** (six parallel research tracks); (b) a 12-agent **direct-evidence source hunt** (2026-07-24) that live-verified 51 sources, overturning a supplied report's flagship leads (see negative results); (c) treating a registry's **creation+withdrawal interval** as documented per-year registration evidence (AFNIC); (d) byte-range **sampling spikes** to size a source before committing to a large download (Arquivo IA.cdxj).

**Bit-rot rescue.** The ISC survey lists and ODP dumps were rescued from actively rotting hosts and pinned with sha256 checksums (`data/raw/checksums.sha256`); the UKWA graph was salvaged from a truncated Wayback stream (the year-sorted 1996–2001 head transferred intact); AFNIC and IA.cdxj were downloaded fresh (IA.cdxj: a resumable 50.9 GB download verified to the exact byte and checksummed).

### Negative results (evaluated and rejected, kept for the record)

| Source | Verdict |
|---|---|
| Common Crawl | Starts 2008 — out of window |
| InterNIC / historical gTLD zone files | No dated 1996–2001 SLD snapshot survives anywhere; IA never crawled the FTP zone data |
| DMOZ 1998/1999 RDF dumps | Never existed — earliest dated ODP RDF is 2000-07-20 |
| RIPE database dumps | All `domain:` objects are reverse `in-addr.arpa`; zero forward domains |
| DNS-OARC root zone | Member-gated + TLD-delegations only (no second-level domains) |
| CAIDA Skitter/DZDB, Route Views | IP/router-level or out of window; not registered domains |
| Kulturarw3 (`.se`), Netarkivet (`.dk`), BnF (`.fr`) | Reading-room / gated — no bulk download |
| Commercial WHOIS bulk | Paid; redundant with free RDAP |
| SNAP, Yahoo Webscope, TREC WT10g | Anonymized / defunct / licence-gated |
| DNS Census (2013), OpenINTEL (2015+), Rapid7 Sonar (2013+) | Out of window |

## 4. Annual evidence logic & result statistics

- **Per-year evidence, no forward-fill (III.7/III.1).** A domain enters a year file only with its own in-year evidence; first-appearance never infers later years. Cross-year duplication is required where independently evidenced.
- **Net-new domains vs net-new pairs.** Distinct metrics: 462,394 domains are entirely absent from the baseline; 1,300,091 pairs are new (domain, year) facts, which additionally include baseline domains gaining a missing year (notably 1997, which the baseline barely covered). Verified non-double-counting.
- **Cross-source corroboration.** Average **1.35** master-eligible sources per assigned pair; **2,556,568** pairs carry ≥2 sources. Honesty caveat: most current corroboration is Internet-Archive-on-Internet-Archive (baseline + Early Web + Arquivo all trace to IA); genuinely provenance-independent corroboration comes from ISC (DNS) and AFNIC (registry), which is where it matters.
- **Evidence rows by type:** `prior_reused` 6,866,913 · `cdx_timestamp` 2,310,422 · `artifact_listing` 1,682,024 · `whois_creation` 144,568 · `link_source` 39,454 · `dated_directory` 975.

## 5. CDX / verification execution notes

The Phase-4 verification engine is **RDAP-first** and is now implemented (`ark rdap`): registry RDAP returns exact registration years with no IA-CDX-style rate ceiling, so large *undated* candidate pools become dated `whois_creation` evidence far more cheaply than CDX-verifying each. A queryable RDAP record proves current registration, so (by the interval reasoning above) it dates every in-window year `[max(1996, creation), 2001]`.

**First run — UKWA link-target candidates.** The 6,266 UKWA link-target hosts (linked-to in 1996–2001, previously candidate-only) that were not already held were run through `ark rdap`: of 6,246 queried, **811 dated in window (net-new), 1,351 created after 2001, 4,084 no longer registered / no RDAP** — **+831 net-new domains / +2,320 net-new pairs**, in the mid/thin years. The ~13% in-window hit rate reflects link-target ephemerality; a less ephemeral pool would hit higher. The command is resumable (skips already-tried domains) and scales to larger pools (Domains Project, webbase, `deduplicated_urls`).

Per-domain IA CDX verification was re-scoped to **one collapsed query per domain** (`collapse=timestamp:4`, measured 2026-07-22) and is retained as the **fallback** for domains RDAP cannot date; it has not been run at scale. When run, it will report per brief §VI: tools, seeds queried, batching, success rates, failure handling (adapt batch size / concurrency / retry on 504/429, never quit), and net-new added.

## 6. Limitations & how to reproduce

**Limitations (stated plainly).**
- **Geographic skew.** Net-new additions over-represent `.fr` (AFNIC), `.pt` (Arquivo), and `.uk` (UKWA) relative to a global population — because the baseline already holds what IA's global crawl caught, so the complementary gains are national. Documented, not hidden.
- **Floor effects.** AFNIC retains only domains still registered or withdrawn within ~2 years, so `.fr` domains created in-window and dropped before ~2024 are absent — the yield undercounts, never over-counts.
- **Year coverage.** 1997 is inflated by ISC (a real gap the baseline had); 1998/1999 were thin and are now materially filled; 2000 is partially served (the surviving ODP Aug-2000 dump is a truncated prefix, and the full content dump is unrecoverable).
- **Evidence-type caveats.** `artifact_listing` / `link_source` / `whois_creation` negatives are weaker than a CDX negative; each type's standard and its negative meaning are stated in §2.

**How to reproduce.** With only `uv` installed:
```
uv run ark ingest-legacy               # load baseline read-only
uv run ark ingest early_web  data/raw/early_web/*.cdx.gz
uv run ark ingest isc_survey data/raw/isc_survey/*.gz
uv run ark ingest arquivo_roteiro data/raw/arquivo/Roteiro.cdxj
uv run ark ingest arquivo_ia data/raw/arquivo/IA.cdxj
uv run ark ingest ukwa_link_source data/raw/ukwa/host-linkage.tsv.gz
uv run ark ingest afnic_fr   data/raw/afnic/*.csv
uv run ark ingest odp        data/raw/odp/*.gz
uv run ark export            # net-new files + manifest + merged masters
uv run ark stats             # the scoreboard
```
Source URLs and exact rescue notes are per-source in [notes.md](notes.md). Downloaded data lives under `data/raw/` (git-ignored); the method is in git and the data regenerates.

---

## Appendix — status of the plan

**Done:** foundation + provenance store; baseline; nine sources (seven bulk + Internet Scout + RDAP-on-link-targets); evidence taxonomy; corroboration metric; the 2026-07-24 evidence ruling and source hunt; the `ark check` integrity gate (6 invariants, all pass); the `ark rdap` Phase-4 engine, demonstrated on UKWA link-targets.
**Pending (Phase 4+):** scale RDAP to larger candidate pools (webbase, Domains Project, `deduplicated_urls`); collapsed CDX verify as fallback; sparse-year gap-fill (1998/1999); feedback loop; final archive packaging (merged lists, candidates, droplist, audit CSVs, provenance export, logs, Word report + checksum).
