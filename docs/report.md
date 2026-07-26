# Internet Digital Ark — Delivery Report

*Reconstructing evidence-backed annual domain lists for 1996–2001.*
Status as of 2026-07-25. Full decision history: [notes.md](notes.md). Plan: [plan.md](plan.md).

---

## 0. Executive summary

We grow the provided ~8.2M-line baseline with **net-new, evidence-backed** registered domains, shipped as a separate verifiable set (the baseline is never modified). Every annual-file entry is backed by item-level, per-year evidence recorded in a provenance database, so any line can be traced to its proof.

**Scoreboard (2026-07-25):**

| Metric | Value |
|---|--:|
| Net-new registered domains (absent from baseline) | **463,364** |
| Net-new (domain, year) pairs | **1,303,508** |
| Baseline domains (read-only) | 4,824,656 |
| Total domains in store | 5,288,024 |
| Total (domain, year) pairs in store | 8,170,421 |
| Evidence rows | 11,048,009 |

**Net-new (domain, year) pairs by year:**

| 1996 | 1997 | 1998 | 1999 | 2000 | 2001 |
|--:|--:|--:|--:|--:|--:|
| 97,582 | 1,038,814 | 12,101 | 25,550 | 52,012 | 77,449 |

The 1997 figure is dominated by the ISC DNS survey (the baseline barely covers 1997); the thin 1998–2000 years were lifted 5–6× by AFNIC `.fr`, and materially by Arquivo `.pt` and the UK Web Archive.

These figures are **lower by 9,664 pairs and 1 domain than the pre-narrowing figure of the same day** (463,365 / 1,313,172), because RDAP evidence was narrowed to the creation year alone on 2026-07-25 (§2, "Narrowing applied to RDAP evidence"). The withdrawn rows were the only ones in the store resting on an inference rather than on a year-specific record.

---

## 1. Data definition & cleaning

- **Counting unit — the registered domain** (brief III.8). Every host or URL, from every source, is reduced to its registrable domain before it touches the database, via a canonicalizer built on a **pinned Public Suffix List snapshot** (committed with the package, so extraction is deterministic and offline) plus a documented patch of **retired 1996–2001 ccTLDs** (`.yu`, `.an`, `.cs`, `.gb`, `.tp`, `.zr`, …) that the modern PSL dropped. `www.example.com`, `foo.example.com`, and platform user-paths (`geocities.com/…`) all collapse to `example.com` / `geocities.com`.
- **Validity rules.** A name must have a registrable label plus a public suffix; bare suffixes (`co.uk` alone), IP addresses, and syntactically invalid hosts are rejected. Underscores are tolerated in subdomains (common in the era) but not in the registered label.
- **Salvage — conservative, deterministic, audited.** Leading/trailing punctuation is stripped (`.www.foo.com`, `,foo.com`); never leading hyphens (that would alter the name). Every correction and every drop is written to an audit CSV; nothing is guessed.
- **Baseline cleaning results.** **8,224,963** supplied hostname lines → **4,824,656 registered domains / 6,866,913 (domain, year) pairs**. The 1,358,050-line difference is **not** lost domains: 12,220 lines (0.149%) yield no valid registered domain and are listed with reasons in `dropped_domains.txt`, and the other 1,345,830 **collapse** because `www.foo.com`, `shop.foo.com` and `foo.com` are three supplied lines and one registered domain, which III.8 mandates as the counting unit. Per-year reconciliation in §1.1. Normalization audit: **~1.45M lines corrected**; droplist: **12,220 dropped** across 5 reason groups (`dropped_domains.txt`, reason-grouped). Originals are never edited — suspect rows are flagged, not rewritten; merged master lists are exports.
- **Deduplication.** Within each year (the `domain_year` primary key is `(domain, assigned_year)`); cross-year duplication is required and expected (a domain appears in every year it is independently evidenced for — brief III.7).

### 1.1 Per-year reconciliation: supplied lines against shipped pairs

The counting unit changes from the hostname to the registered domain (III.8), which is the whole of
the difference below. No domain is discarded for being a duplicate; duplicates *are* the same domain.

| year | supplied lines | pairs held | difference | % |
|---|--:|--:|--:|--:|
| 1996 | 617,750 | 510,577 | 107,173 | 17.3% |
| 1997 | 311,988 | 219,918 | 92,070 | 29.5% |
| 1998 | 1,204,391 | 906,846 | 297,545 | 24.7% |
| 1999 | 1,904,473 | 1,425,651 | 478,822 | 25.1% |
| 2000 | 1,416,486 | 1,318,871 | 97,615 | 6.9% |
| 2001 | 2,769,875 | 2,485,050 | 284,825 | 10.3% |
| **total** | **8,224,963** | **6,866,913** | **1,358,050** | **16.5%** |

Of that total difference, **12,220 lines (0.149%) are genuinely excluded** and enumerated with
reasons in `dropped_domains.txt`; the remaining **1,345,830 collapse** onto a registered domain that
is still present. 1997 shows the largest reduction because it carries the most `www.`-style
duplication, and 2000 the smallest.

The supplied `merge_stats_new0714.csv` counts hostname lines, and its `merged_unique` column matches
the supplied file line counts exactly. This pipeline counts registered domains. The two figures are
both correct at their own unit and must not be compared directly.

## 2. Architecture

- **Provenance store (DuckDB).** Tables: `source`, `domain`, `evidence`, `domain_year`, `ingested_file`. The **evidence wall** is a database constraint, not discipline: `domain_year.evidence_id` is a `NOT NULL` foreign key into `evidence`, so no annual assignment can exist without a specific evidence row behind it. `assign_year` refuses candidate-only evidence outright.
- **One row per (domain, year) per source.** The `evidence` table records every observation; a pair can carry several rows from several sources. This makes cross-source corroboration free (no schema change) and lets net-new be defined robustly over the evidence table (a pair is net-new iff it is assigned and carries no `prior_reused` evidence).
- **Shared bulk ingester.** Every source is a small parser that yields `(raw, year, evidence_value, evidence_url)`; one audited loader handles canonicalization, set-based staging, evidence + `domain_year` writes, per-source audit CSVs, run metrics, and a **per-file sha256 ledger** (same name + same bytes skips; different bytes fails loudly). Per-file transactions; audit rows are written only after a file commits; a failed file is isolated and the run continues. Adversarially reviewed (3 passes) before first real use.
- **Work queue (SQLite, WAL).** Crash-safe queue for the per-domain verification path; enqueue derives from durable evidence rows, so re-running repairs any crash window.
- **Reproducibility.** `uv` + pinned lockfile + committed PSL; CI runs `ruff check`, `ruff format --check` and `pytest` on every push. Raw `uv run …` is the reproducibility contract; a `justfile` wraps it.
- **Integrity gate (`ark check`).** Nine read-only invariants over the whole store, exiting non-zero if any is violated, so no result ships unverified. In order: the evidence wall is intact (every assignment points at an evidence row for the same domain and year); no assignment rests on candidate-only evidence; every assigned pair holds at least one master-eligible evidence row for that exact year; no duplicate (domain, year); every assigned year is inside 1996-2001; every stored domain is a well-formed registrable name; **the year named inside an evidence value equals the year it is filed under**, which machine-enforces the rule that a WHOIS creation date attests only its own year (registration spans are exempt, and only AFNIC qualifies as one, for the documented reason in §2); **no pair counted as an addition also carries baseline evidence for that year**, so the net-new figure cannot be inflated by rows the baseline already had; and **nothing earned is left unassigned**, so a domain cannot sit in the candidate pool while already holding proof of a year. Each invariant has a test that plants the corresponding violation and confirms the gate catches it.
- **Provenance coverage, stated as a rule and machine-checked rather than enumerated.** Every line in an annual master file is either (a) an addition, in which case it appears in `additions/evidence_manifest.csv` with its evidence, or (b) inherited from the supplied baseline file for that year. The two categories are disjoint and exhaustive, and that is enforced: the `additions_not_double_counted` invariant fails if any pair is in both, and `every_pair_has_master_evidence` fails if a pair is in neither. The store holds 11.05M evidence rows against the 1.3M exported, because corroborating rows are deliberately not exported: shipping them would add roughly 170 MB to restate what the store already contains, and the cross-validation figures in §4 are computed from the store. The residual is stated plainly: a reviewer picking a baseline-inherited line gets the rule plus the client's own supplied file for that year, not a bespoke row.

### Evidence types (standard of proof; what a negative means)

| Type | One row asserts | Negative means | Disposition |
|---|---|---|---|
| `prior_reused` | Baseline already lists this (domain, year); reused read-only (III.1) | n/a | Master; **excluded from the score** (it is the baseline) |
| `cdx_timestamp` | A web-archive capture (IA / Arquivo) with an in-year 14-digit timestamp + HTTP 200 for the domain or a subdomain | Empty CDX for all six years = never archived in window (not proof of non-existence → stays candidate) | Master; gold standard |
| `artifact_listing` | A line in a **dated data file** whose provenance fixes the year (ISC survey list = survey date; ODP RDF dump = generation stamp) | "Not in that file", weaker than a CDX negative | Master (direct) |
| `link_source` | In a UKWA host-link-graph row `year\|source\|target`, the **source** host was crawled (HTTP 200) that year | n/a (precomputed graph) | Master |
| `whois_creation` | A registry record fixes a registration date. **RDAP: the creation year and no other** (III.6). **AFNIC `.fr`:** the registry's documented `crDate` semantics make `[creation, deletion-or-now]` a continuous registration span, so every in-window year it covers | Missing/blocked WHOIS proves nothing | Master |
| `dated_directory` | An editorial entry on a directory page captured by a web archive on a known date | "Not listed there", weak | Master (direct) |
| `link_target` | In the same UKWA row, the **target** host was merely linked-to | n/a | **Candidate-only**, never assigns a year. Defined but **currently unpopulated** (0 rows): the target-side ingester is not yet built |

**Evidence-standard ruling (Prof. Ding, 2026-07-24):** valid year evidence is not limited to web captures. Dated DNS surveys, archive indexes, host/link graphs, dated directory/index files, and WHOIS registration records all count as direct annual evidence, provided the year association is explicit and documented and the provenance (source name, dataset date, assignment method, record id) is retained. The store retains all four per row, with one substitution worth stating: the dataset date is the ingest timestamp (`ingested_at`, always populated) rather than a capture timestamp, since `captured_at` is unpopulated across all evidence rows. The record identifier is `evidence_value` plus the source file's sha256 in the ledger; a per-record URL exists only for archive-capture rows, so 1,167,790 addition rows carry no clickable locator.

**Narrowing applied to RDAP evidence (2026-07-25).** An RDAP response was audited field by field against this standard. It returns the *current* state of a registration plus exactly one historical timestamp, the `registration` event; it carries no registration history. Two facts are therefore extractable: created on date D, and registered today. Those two facts had previously been read as a continuous registration interval, assigning every in-window year from the creation year onward. That reading needs a third premise, that registry creation dates reset on re-registration, which is an assumption about registry policy rather than a record of any particular year. III.6 anticipates it directly: a creation date alone "does not automatically establish that the domain remained registered ... in every subsequent year", and later years require evidence "tied to that specific year". **9,664 assignments and 22,864 evidence rows were withdrawn accordingly**, leaving RDAP to attest its creation year and nothing else. A domain RDAP dates outside 1996–2001 attests no year and remains a candidate. The rule is implemented in one tested function (`attested_years`) and the prune is reproducible via `scripts/restrict_whois_creation_to_creation_year.py`, which aborts if any affected assignment could have been re-pointed at other evidence instead of deleted (none could).

**Why AFNIC `.fr` keeps the interval reading: the premise is documented, not assumed (2026-07-25).** The interval reading needs one thing to be true, that the registry records a *new* creation date when a deleted name is registered again. Otherwise a creation date could predate an undetected gap. AFNIC states the behaviour in its own registrar documentation, *Technical Integration Guide* v3.0 (27 February 2015), on the `domain:info` fields:

> `<domain:crDate>` … in the current version of this interface, the timestamping information is **not aligned with the role described in RFC 5731** but copied from the "Whois" pattern. **The creation date is the last creation date of the domain name** or the date of the last transmission (trade or recover).

The same sentence appears in the authoritative French edition and in AFNIC's 2009 EPP specification and its 2008 predecessor, four editions over seven years. Note that AFNIC is explicitly warning registrars that its creation date does *not* follow standard EPP object semantics, so this could not have been settled by reasoning from the RFCs.

That yields a proof rather than an assumption. `crDate = max(last creation, last transmission)`, and both of those events necessarily fall after any prior deletion, since a deleted name must be created again to exist. So `crDate` is always at or after the last deletion, and the span `[crDate, deletion-or-now]` **contains no deletion event**. It is a continuous registration interval by construction, which carries both the 11,902 domains with a published deletion date and the 43,123 without.

Two consequences. First, **the tranche can only undercount**: because `crDate` is never earlier than the true first registration, a domain first registered in 1998 but traded or re-registered in 2010 reports creation 2010, falls outside the window and is dropped. We lose real domains; we cannot gain false ones. Second, **an AFNIC creation date is the later of (last registration, last holder change)** and is never described here as the first-ever registration date.

Live corroboration, reproducible by any reviewer from the open data file plus one `whois -h whois.nic.fr` query: `bennegens-couverture.fr` (open data: created 30-05-2020, deleted 28-06-2026; WHOIS today: created 2026-07-10) and `mintrocket.fr` (open data: created 22-04-2022, deleted 19-06-2026; WHOIS today: created 2026-07-10). Deleted in June, re-registered in July, creation date advanced, original gone.

**The remaining exposure is interpretive, not factual.** A verified premise makes the interval *sound*; it does not make it evidence *tied to* a specific year in III.6's literal sense. Discounting the AFNIC tranche to its creation years would remove **69,111** pairs, concentrated in the thin years (2001 -34,643, 2000 -21,225, 1999 -10,305, 1998 -2,811). Every affected row stores its interval verbatim (e.g. `registered 16-03-1999..active`), so that recomputation is mechanical if required. The same verification was **not** attempted for RDAP, which spans roughly 590 registries rather than one, which is why RDAP remains narrowed to the creation year.

### 2.1 Section III compliance map

Section III states that its rules have the highest priority and that all subsequent methods must
comply with them. Each rule is therefore mapped to the mechanism that enforces it, so compliance can
be inspected rather than trusted. "Check N" refers to the `ark check` invariants above.

| Rule | What it requires | Where it is enforced |
|---|---|---|
| **III.1** | Annual masters may hold only domains with evidence for that year; earlier-year evidence does not carry forward; prior item-level evidence may be reused | The evidence wall: `domain_year.evidence_id` is NOT NULL and `assign_year` derives both domain and year from the evidence row, so a mismatched assignment cannot be expressed. Checks 1 and 3. Reuse is the `prior_reused` type |
| **III.2** | Data without item-level year evidence may go only to a candidate, pending or seed pool | `CANDIDATE_ONLY_TYPES` in the taxonomy; `assign_year` raises on candidate-only evidence; check 2 |
| **III.3** | The aggregate DMOZ snapshot dated 2015-03-27 must not be spread across 1996-2001 | Never used. Only *dated* ODP dumps are ingested (Aug 2000, Jun 2001, Nov 2001), each assigning only its own generation year. No 2015 artifact touches an annual file |
| **III.4** | DMOZ, StanfordWebBase and undated collections start as candidate seeds and need per-year verification | StanfordWebBase was routed to candidates and then retired as a growth source (99.99% already held); undated host pools enter through `ark seed`; the ODP artifact ingested is a dated dump rather than an undated listing, argued in §2 and `sources.md` |
| **III.5** | Deliverables must clearly separate annual master results from candidates | Separate files and separate archive directories: `additions/<year>.txt` and `masters/<year>.txt` against `candidates.txt` |
| **III.6** | A creation date supports its own year only, not later years | `attested_years` returns at most the creation year, and is the single place the rule lives; check 7 machine-enforces that a value's own year equals the year it is filed under, for every source except the one documented registration span |
| **III.7** | A domain appears in every year it is evidenced for; deduplicate within a year, not across years; first appearance never implies later years | One `domain_year` row per (domain, year), each with its own evidence row; check 4 enforces within-year uniqueness; cross-year duplication is normal and expected |
| **III.8** | Registered domains as the output unit, not hostnames or user paths | Every domain from every source passes `to_registrable` before reaching the store; check 6; the consequence is quantified in §1.1 |
| **III.9** | `1996.txt` means evidence of existence during that calendar year, and likewise for each year | Parsers filter to the window at read time; check 5 confirms every assigned year is in range; check 7 ties each year to its own evidence value |
| **III.10** | A domain may enter an annual master only once year-specific evidence is obtained; otherwise the candidate pool | Assignment is impossible without an evidence row; both collectors journal an undatable outcome instead of assigning, and check 9 confirms nothing earned is left unassigned |
| **III.11** | Every collected list must be accompanied by its acquisition method | `sources.md` documents every source; the `ingested_file` ledger records each file with its sha256 and row count; every evidence row carries `acquisition_method` |

## 3. Sources & methods

All figures are net-new **on top of the baseline**. Per-source acquisition method, date semantics, the argument for each evidence type, caveats and reproduction commands are in [sources.md](sources.md); dated decisions are in [notes.md](notes.md).

| Source | Evidence type | Years | Net-new domains | Net-new pairs | Note |
|---|---|---|--:|--:|---|
| IA Early Web CDX | `cdx_timestamp` | 1996–1999 | +175 | +182 | 99.99% baseline overlap → **the baseline is IA-derived** |
| ISC / Network Wizards DNS survey | `artifact_listing` | 1996–1997 | ~+397k | ~+1.13M | Largest tranche; DNS-observed, IA-independent; 1997 alone +1.03M |
| Arquivo `Roteiro` | `cdx_timestamp` | 1996 | +0 | +7 | 1996 already dense; corroboration |
| Arquivo `IA.cdxj` | `cdx_timestamp` | 1996–2001 | +6,715 | +17,689 | 98% `.pt`; thin years (1998 +89%, 1999 +165%, 2000 +183%) |
| UK Web Archive host link graph | `link_source` | 1996–2001 | +15,822 | +23,821 | mostly `.uk`; thin later years |
| AFNIC `.fr` open data | `whois_creation` | 1996–2001 | +39,367 | +117,829 | registration span, premise verified from AFNIC docs (§2); thin years **5–6×** |
| ODP / DMOZ dumps | `artifact_listing` | 2000–2001 | +3,339 | +8,423 | heavy baseline overlap; mostly 2000 |
| Internet Scout archive | `dated_directory` | 1996–2001 | +137 | +311 | curated non-IA long tail; most records undated |
| RDAP on UKWA link-targets | `whois_creation` | 1996–2001 | +833 | +833 | **Phase-4 engine**: undated candidates dated via RDAP, no CDX; one creation year each |
| IA CDX verification engine (`ia_cdx_bulk`) | `cdx_timestamp` | 1996–2001 | +0 | +840 and rising | one collapsed query per domain answers all six years; still running (§5.1) |
| IA CDX per-year verify (`ia_cdx`, superseded) | `cdx_timestamp` | 1996–2001 | +8 | +11 | the original six-queries-per-domain path, kept because its rows are real evidence |
| RDAP gap-fill (selected by sandwich gaps) | `whois_creation` | 1996–2001 | +0 | +2,273 | adds a creation year to already-held domains; 42% RDAP hit rate because the selection favours survivors |

**Key strategic finding:** the baseline is Internet-Archive-derived (Early Web CDX overlapped it 99.99%). Net-new volume therefore comes from **non-IA sources** — DNS surveys (ISC), national registries (`.fr`), and national web archives (`.pt`, `.uk`) — which is also why the additions are geographically complementary.

**Candidate-vs-verified routing (brief III.4).** Sources without item-level year labels — StanfordWebBase/webbase, undated DMOZ, raw URL lists, UKWA link *targets* — are treated as **candidate seeds**, never written to annual files without per-item verification. The in-store candidate pool is small (4) because the large candidate lists are held as files under `data/raw/` and fed to the verification engine from there rather than parked in the store; they are queued for the Phase 4 engine.

**Novel methods / directions pursued.** (a) A one-day live-verified **bulk-source survey** (six parallel research tracks); (b) a 12-agent **direct-evidence source hunt** (2026-07-24) that live-verified 51 sources, overturning a supplied report's flagship leads (see negative results); (c) treating a registry's **registration span** as per-year evidence only after verifying the registry's creation-date semantics from its own documentation (AFNIC; deliberately *not* extended to RDAP, see §2); (d) byte-range **sampling spikes** to size a source before committing to a large download (Arquivo IA.cdxj).

**Bit-rot rescue.** The ISC survey lists and ODP dumps were rescued from actively rotting hosts and pinned with sha256 checksums (`data/raw/checksums.sha256`); the UKWA graph was salvaged from a truncated Wayback stream (the year-sorted 1996–2001 head transferred intact); AFNIC and IA.cdxj were downloaded fresh (IA.cdxj: a resumable 50.9 GB download verified to the exact byte and checksummed).

### Negative results (evaluated and rejected, kept for the record)

| Source | Verdict |
|---|---|
| webbase-2001 (Stanford, via LAW) | 603,245 domains but **99.99% already held** (baseline covers the popular 2001 web); only 43 net-new candidates → +3 via RDAP |
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
- **Net-new domains vs net-new pairs.** Distinct metrics: 463,364 domains are entirely absent from the baseline; 1,303,508 pairs are new (domain, year) facts, which additionally include baseline domains gaining a missing year (notably 1997, which the baseline barely covered). Verified non-double-counting.
- **Cross-source corroboration.** Average **1.35** master-eligible sources per assigned pair; **2,558,322** pairs carry ≥2 sources. Honesty caveat: most current corroboration is Internet-Archive-on-Internet-Archive (baseline + Early Web + Arquivo all trace to IA); genuinely provenance-independent corroboration comes from ISC (DNS) and AFNIC (registry), which is where it matters.
- **Evidence rows by type:** `prior_reused` 6,866,913 · `cdx_timestamp` 2,310,422 · `artifact_listing` 1,682,024 · `whois_creation` 148,221 · `link_source` 39,454 · `dated_directory` 975.

## 5. CDX / verification execution notes

The Phase-4 verification engine is **RDAP-first** and is now implemented (`ark rdap`): registry RDAP returns an exact registration year with no IA-CDX-style rate ceiling, so large *undated* candidate pools can be dated far more cheaply than CDX-verifying each domain. Since the 2026-07-25 narrowing (§2) each dated domain yields **exactly one** year, its creation year, and only if that year falls in 1996–2001. This is a much smaller yield per query than the interval reading gave, and it is the yield the evidence actually supports.

**Collection is separated from interpretation.** `ark rdap` queries the network and writes only a per-run **journal**: one gzipped JSON object per domain queried, holding the domain, the query time, the HTTP status, the extracted creation year, and the entire RDAP response. It writes no evidence and never opens the store. `ark ingest rdap_snapshot <journal>` then produces the evidence through the same audited loader every bulk source uses, so the journal is hashed into the file ledger with a row count, and re-ingesting is a no-op. Two reasons this shape was chosen over querying and writing in one pass. First, provenance: RDAP evidence now replays from a fixed artifact like every other source, instead of only from the live network. Second, cost of change: keeping whole responses means a future change of evidence standard is a re-parse, whereas the 2026-07-25 narrowing had to be done as a destructive database migration precisely because only the extracted year had been kept.

**First run, UKWA link-target candidates.** The 6,266 UKWA link-target hosts (linked-to in 1996–2001, previously candidate-only) that were not already held were run through `ark rdap`: of 6,246 queried, **811 dated in window, 1,351 created after 2001, 4,084 no longer registered or no RDAP**. Yield **+830 net-new domains / +830 net-new pairs**; a further +3 came from the separate webbase probe, so the source totals 833 and must not be counted twice. The ~13% in-window hit rate reflects link-target ephemerality.

**Second run, gap-fill on held domains.** The same engine adds in-window years to domains already held in other years. The **"sandwich gap" (assigned in Y and Y+2, missing Y+1) is a selection heuristic, not the evidence mechanism**: such domains are much likelier to have survived to the present, which lifts the RDAP hit rate to **42%** against 13% for link-targets. What gets assigned is still only the creation year, so a run fills the targeted gap year only when the creation year lands on it. Of **470,816** sandwich-gap domains, 15,000 were queried in two batches (5,676 dated) for **+2,273 net-new pairs** on held domains and +0 net-new domains. The remaining ~455k are a modest lever at roughly 1.5–2k pairs per 10k queried; closing a held domain's other missing years honestly requires year-tied evidence (collapsed CDX), not RDAP. `ark check` passes after every run.

### 5.1 IA CDX verification engine (brief §VI, §IX.5)

**Tools.** No third-party CDX client. `src/ark/cdx.py` calls the public Wayback CDX server
directly over `urllib` (Python 3.12 standard library), driven by `ark cdx`. An earlier
implementation used `cdx_toolkit` with six requests per domain; it was replaced because one
request can answer all six years. Everything is exercised by 15 offline unit tests with an
injected fetcher, so no test touches the network.

**Endpoint and query.** `https://web.archive.org/cdx/search/cdx` with:

```
url=*.<domain>   from=1996   to=2001   filter=statuscode:200
fl=timestamp     collapse=timestamp:4  limit=3000
```

`*.<domain>` matches the domain and every subdomain, so a capture of `www.example.com` evidences
`example.com`. `filter=statuscode:200` keeps only captures that served content. `fl=timestamp`
reduces each row to 14 bytes. `collapse=timestamp:4` asks the server to fold repeated years.

The collapse is treated as a payload optimisation only, never as correctness: the server collapses
*adjacent* rows and orders results by URL key, so a domain with many subdomains still returns a
year repeatedly. Years are therefore deduplicated client-side. A response that reaches `limit` may
have been truncated before some year appeared, so truncation is detected and each still-missing
year gets one `limit=1` probe.

**Seeds queried.** The bracketed-gap pool from `ark gaps`: domains already held in year Y-1 **and**
Y+1 but missing Y, so the flanking years bracket the missing one. **470,614 domains / 494,716 known
gaps**, ordered thinnest gap year first (1998, 1999, 2000, 2001, 1996, 1997) and spread
deterministically by `hash(domain)` inside each tier. Alphabetical ordering was rejected after it
was found to cluster numeric-prefix junk (`0171.com`, `1-800-…`) at the head of the run.

Because one query returns every year, the unit of work is the domain and the run records **all**
years returned, not only the bracketed gap. This is where most of the yield came from.

**Batching and concurrency.** Sequential batches of 1,200 domains, 8 concurrent requests per batch,
paced by an adaptive governor. Batches rather than one long job so each journal file completes and
can be ingested while later batches still run, and so an interruption costs at most one batch's
tail. Runs are resumable: a domain already *answered* in any journal is skipped.

**Measured throughput and the concurrency ceiling.** Concurrency, not pacing, is the lever: a
wildcard CDX query costs the server 2-16 s on a light domain. Measured 2026-07-25:

| Concurrent requests | Domains answered | Transport failures |
|--:|--:|--:|
| 1 | 100% | 0 |
| 4 | 100% | 0 |
| 8 | 82% | 16% |
| 16 | 30% | 70% |
| 32 | 17% | 83% |

Past roughly 8 concurrent requests the service drops connections and returns its own `504`s, so
**8 is the operating point and ~800-1,000 answered domains per hour is the ceiling.** Higher
settings measure faster only because a refused connection returns instantly; they do not produce
more answers. This is reported because it bounds what any candidate-verification programme of this
design can achieve against the public interface.

**Timeout, measured rather than assumed.** The server kills a heavily archived domain's query at a
consistent ~60.7 s, so it already fails fast on our behalf. A shorter client timeout is a false
economy: at 30 s a run answered 51 of 100 domains (695 answers/hour), at 180 s it answered 82 of
the same 100 (802 answers/hour), because roughly a third of domains reply between 30 s and 60 s.
The client timeout is therefore **70 s**, just above the server's own limit.

**Two query strategies, compared head to head** (8 capture-rich domains, sequential, 2026-07-25):

| Strategy | Mean per domain | Failures | Years found |
|---|--:|--:|---|
| One collapsed six-year query | **26.9 s** | 3/8 | identical |
| Six per-year `limit=1` probes | 73.6 s | 1/8 | identical |

Where both strategies answered, the years agreed **4/4 with no disagreement**, so they are
correctness-equivalent. The collapsed query is 2.7x faster and is the default; the per-year
strategy is slower but succeeds on the heavy domains the collapsed query cannot finish, so it is
retained as a second sweep (`ark cdx --per-year`) that picks up unanswered domains automatically.

**Error handling (brief §VI.c).** Retryable statuses are `0` (transport failure), `429`, `500`,
`502`, `503`, `504`, up to 4 attempts. On `429`/`503`/`504` the governor multiplies its pace by 1.5
and honours `Retry-After`; after 5 consecutive successes it eases back by 0.8, floor 50 ms, ceiling
capped (2 s in production runs) so that one bad patch cannot leave the run crawling. An early pilot
demonstrated why the ceiling matters: with a 30 s ceiling and slow recovery, six throttles drove
the pace to the ceiling and it never returned, the tail crawling at 45 s per domain. Rate limits
are treated as signals to adapt, never as grounds to abandon the route.

**A failure is never recorded as an absence.** A transport failure or 5xx means the question was
not answered, so the journal records the status and the domain stays eligible for a later run.
Only an HTTP 200 settles a domain. This distinction is load-bearing: an earlier version counted
failures as "no captures", which both understated the hit rate and would have permanently dropped
2,727 domains from every subsequent run.

**Success rate and yield.** Among domains that answered, **95-100% had at least one in-window
capture**, averaging **3.6 years per domain**. Ingested yield is **1.15 net-new (domain, year)
pairs per domain queried**. Calibration and pilot runs alone (roughly 2,400 domains) added **+840
net-new pairs**, all in the thin years: 1998 +231, 2000 +479, 2001 +130. Every batch is followed by
`ark check`, which has passed throughout.

**Reproduce.** From a store that already holds the bulk sources:

```bash
uv run ark gaps                       # -> data/raw/cdx/gap_candidates.txt (470,614 domains)
uv run ark cdx data/raw/cdx/gap_candidates.txt -n 1200 --workers 8 --timeout 70
uv run ark ingest cdx_snapshot data/raw/cdx/cdx_<stamp>.jsonl.gz
uv run ark cdx data/raw/cdx/gap_candidates.txt --per-year   # optional sweep of unanswered domains
```

Each journal is hashed into the file ledger with its record count, so the evidence replays from
bytes on disk rather than from the live service, whose answers change over time.

## 6. Limitations & how to reproduce

**Limitations (stated plainly).**
- **Geographic skew.** Net-new additions over-represent `.fr` (AFNIC), `.pt` (Arquivo), and `.uk` (UKWA) relative to a global population — because the baseline already holds what IA's global crawl caught, so the complementary gains are national. Documented, not hidden.
- **Floor effects.** AFNIC's File A holds every `.fr` name live at the file date plus every name deleted since **28 January 2014** (per its user guide, confirmed against the file: the 11,880 in-window domains carrying a deletion date spread evenly across 2014-2026). So only `.fr` domains deleted before that date are missing. Combined with the `crDate` reset described in §2, which drops in-window domains that were later traded or re-registered, the `.fr` yield undercounts and cannot over-count.
- **Year coverage.** 1997 is inflated by ISC (a real gap the baseline had); 1998/1999 were thin and are now materially filled; 2000 is partially served (the surviving ODP Aug-2000 dump is a truncated prefix, and the full content dump is unrecoverable).
- **Evidence-type caveats.** `artifact_listing` / `link_source` / `whois_creation` negatives are weaker than a CDX negative; each type's standard and its negative meaning are stated in §2.
- **The legacy RDAP tranche has weaker provenance than every other source.** Its 3,106 pairs (0.24% of the additions, source name `rdap`) were written directly from live queries before the journal architecture existed, so they have no hashed source file and no per-record URL; their provenance is the evidence value, the ingest timestamp, the run metrics, and the execution logs. Every other source replays from a file whose sha256 is in the ledger. **All RDAP evidence currently in the store is of this legacy kind:** the journal architecture described in §5 is implemented and tested but has not yet been run at scale, so no `rdap_snapshot` source row exists yet. The legacy rows were deliberately left in place rather than re-queried, because re-querying in 2026 returns *different* creation dates for any domain that has since changed hands, which would silently alter the result set.
- **One standard is not uniform inside `whois_creation`.** RDAP rows attest a single creation year (the strict III.6 reading, since RDAP spans ~590 registries whose creation-date semantics are not established). AFNIC rows attest every year their registration span covers, on the strength of AFNIC's own documented `crDate` behaviour. Two different strengths of claim under one type name, deliberately and visibly: every row records the basis it rests on (`rdap creation 1998` vs `registered 16-03-1999..active`), so either can be recounted independently. §2 gives the reasoning and the size of the AFNIC exposure (69,111 pairs).

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
uv run ark ingest internet_scout data/raw/scout/scout_oai.xml
uv run ark rdap  data/raw/ukwa/link_target_candidates.txt -n 6500   # network -> journal
uv run ark rdap  data/raw/gapfill_candidates.txt -n 15000           # network -> journal
uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz       # journal -> evidence
uv run ark export            # net-new files + manifest + merged masters
uv run ark stats             # the scoreboard
uv run ark check             # integrity gate, must print ALL PASS
```
The `ark rdap` steps are the only network-dependent stages, so their yield depends on which domains are still registered on the day they run. `ark rdap` writes a per-run **journal** (one gzipped JSON object per queried domain, holding the whole RDAP response) and no evidence; `ark ingest rdap_snapshot` turns journals into evidence through the same hashed-file loader as every other source. Re-running either step is a no-op on work already done. A store built **before 2026-07-25** carries the superseded interval rows and is migrated with `uv run python scripts/restrict_whois_creation_to_creation_year.py rdap --apply` (dry run by default); a store built with the current code needs no migration.
Source URLs and exact rescue notes are per-source in [notes.md](notes.md). Downloaded data lives under `data/raw/` (git-ignored); the method is in git and the data regenerates.

---

## Appendix — status of the plan

**Done:** foundation + provenance store; baseline; **12 sources carrying evidence** (eight bulk files, Internet Scout, RDAP, and both IA CDX paths); evidence taxonomy; corroboration metric; the 2026-07-24 evidence ruling and source hunt; the `ark check` integrity gate (6 invariants, all pass); the `ark rdap` Phase-4 engine, demonstrated on UKWA link-targets; **webbase-2001 evaluated (retired — 99.99% already held); the delivery archive packaged** (`scripts/package_delivery.sh` → one tar.gz with masters, additions, provenance, audit, logs, source snapshot, `report.docx`, README + SHA256).
Also done: the **2026-07-25 RDAP narrowing** (creation year only, 9,664 assignments withdrawn) with a reproducible migration script.
Also done: the AFNIC `crDate` semantics were verified from AFNIC's own registrar documentation, which is what licenses that source's registration-span reading (§2).
**Pending:** collapsed CDX verify as a corroboration/gap-fill fallback (1998/1999) and as the honest route to converting inferred years into year-tied evidence; untested niche sources (Domains Project long tail, more national archives); feedback loop. Net-new is now dominated by national registries/archives (`.fr`, `.pt`, `.uk`); global crawls overlap the baseline, so large new tranches are unlikely without new geographies.
